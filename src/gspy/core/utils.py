# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#    http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Authors
#   Wilfried Visser

import math
import numpy as np
from math import log, exp
from scipy.optimize import root, root_scalar
import cantera as ct
import gspy.core.constants as c

atomweightC = 12.010914
molemassCO2 = 44.0098
atomweightO = 15.99940
molemassO2 = 31.9988
atomweightH = 1.0079832
atomweightN = 14
MM_NO2 = 46.00554

# functions for corrected rotor speed Nc and mass flow Wc
# divide N by GetRotorspeedCorrectionFactor to get Nc corrected
def GetRotorspeedCorrectionFactor(gas: ct.Quantity):
    return math.sqrt(gas.T/c.T_std)

# multiply W by GetFlowCorrectionFactor to get Wc corrected
def GetFlowCorrectionFactor(gas: ct.Quantity):
    return math.sqrt(gas.T/c.T_std) / (gas.P/c.P_std)

def set_enthalpy(gas, target_enthalpy):
    def equation(Titer):
        gas.TP = Titer, None
        return gas.enthalpy_mass - target_enthalpy
    solution = root(equation, x0 = gas.T)
    if solution.success:
        return gas.T
    else:
        print("Root not found")

def calculate_exit_velocity(gas, pressure_ratio):
    # Store the initial enthalpy for the stagnation state
    stagnation_enthalpy = gas.enthalpy_mass

    # Calculate exit state based on the pressure ratio
    exit_pressure = gas.P / pressure_ratio
    # keep entropy S constant
    gas.SP = gas.entropy_mass, exit_pressure  # Isentropic expansion to exit pressure
    exit_enthalpy = gas.enthalpy_mass

    # Calculate the exit velocity
    velocity = (2 * (stagnation_enthalpy - exit_enthalpy))**0.5

    return velocity, gas.T

def calculate_expansion_to_A(gas, pressure_ratio, A):
    # Store the initial enthalpy for the stagnation state
    stagnation_enthalpy = gas.enthalpy_mass
    stagnation_entropy = gas.entropy_mass

    # Calculate exit state based on the pressure ratio
    stagnation_pressure = gas.P
    exit_pressure = gas.P / pressure_ratio
    # keep entropy S constant
    gas.SP = gas.entropy_mass, exit_pressure  # Isentropic expansion to exit pressure
    exit_enthalpy = gas.enthalpy_mass

    # Calculate the exit velocity
    dh = stagnation_enthalpy - exit_enthalpy
    if dh < 0:
        # allow backwards flow during iteration (avoiding complex number for velocity)
        velocity = -(2 * abs(dh))**0.5
    else:
        velocity = (2 * dh)**0.5
    Mout = velocity / gas.sound_speed
    if Mout < 1:
        exit_enthalpy = gas.enthalpy_mass
        massflow = A * velocity * gas.density
        return exit_pressure, gas.T, velocity, massflow
    else:
        # exit_pressure = gas.P / pressure_ratio
        # keep entropy S constant
        def throat_H_error(Ps_throat):
            # 1.6.0.5
            # gas.SP = stagnation_entropy, Ps_throat  # Isentropic expansion to exit pressure
            gas.SP = stagnation_entropy, float(np.asarray(Ps_throat).squeeze())  # Isentropic expansion to exit pressure

            dh = stagnation_enthalpy - gas.enthalpy_mass
            # allow backwards flow during iteration (avoiding complex number for velocity)
            if dh < 0:
                velocity = -(2 * abs(dh))**0.5
            else:
                velocity = (2 * dh)**0.5
            velocity1 = gas.sound_speed
            return velocity - velocity1
        initial_guess = [stagnation_pressure/1.9] # 1.0 approx. critical PR
        solution = root(throat_H_error, initial_guess)

        massflow = A * gas.sound_speed * gas.density
        # Check if the solution converged
        if solution.success:
            return solution.x[0], gas.T, gas.sound_speed , massflow
        else:
            raise ValueError("Solution throat P did not converge")

def exit_T_and_enthalpy_for_pressure_ratio(gas, target_PR, eta_is) :
    # Set the initial state
    # gas.TP = gas.T, initial_pressure
    initial_enthalpy = gas.enthalpy_mass
    initial_entropy = gas.entropy_mass  # Store initial entropy for isentropic condition

    Pend = gas.P / target_PR
    gas.SP = initial_entropy, Pend  # Set entropy and pressure (isentropic condition)
    final_enthalpy_is = gas.enthalpy_mass
    # eta_is = (initial_enthalpy - final_enthalpy) / (initial_enthalpy - final_enthalpy_is)
    final_enthalpy = initial_enthalpy - (initial_enthalpy - final_enthalpy_is) * eta_is
    gas.HP = final_enthalpy, Pend
    return gas.T, gas.enthalpy_mass

def Compression(gas_in: ct.Quantity, gas_out: ct.Quantity, PR, Eta, Polytropic_Eta = 0):
    # v1.4 polytropic efficiency option
    if Polytropic_Eta == 1:
        R = ct.gas_constant / gas_in.phase.mean_molecular_weight
        Sout = gas_in.s + R*log(PR)*(1/Eta-1)
        Pout = gas_in.P*PR
        gas_out.SP = Sout, Pout # get gas_out at constant s and higher P
    else:
        Sin = gas_in.s
        Pout = gas_in.P*PR
        gas_out.SP = Sin, Pout # get gas_out at constant s and higher P
        Hisout = gas_out.enthalpy_mass # isentropic exit specific enthalpy
        Hout = gas_in.enthalpy_mass + (Hisout - gas_in.enthalpy_mass) / Eta
        gas_out.HP = Hout, Pout
        # bug fix: for Fan, gas_out<>gas_in: use gas_out as the mass being compressed
        # PW = gas_out.H - gas_in.H
    PW = gas_out.H - gas_out.mass * gas_in.phase.enthalpy_mass
    return PW

def TurbineExpansion(gas_in: ct.Quantity, gas_out: ct.Quantity, PR, Eta, Wexp, Eta_Polytropic = 0):
    # GSP code polytropic efficiency
    #   S:=Incond.S-FR(Composition)*ln(PR)*(Etapol-1);
    #   // Note that S already has pressure effect (ln(PR) therefore :
    #   // (Etapol-1 term)
    #   GetTfromS(S,Pt,Composition,Accy,Tt,ErrorComment);
    #   S:=FS(Tt,Pt,Composition);
    #   H:=FH(Tt,Composition);
    #   Etais:=(Incond.H-H)/(Incond.H-His);

    # 1.6.0.5 make sure Pout becomes a single value
    # Pout = gas_in.P / PR
    Pout = gas_in.P / float(np.asarray(PR).squeeze())

    if Eta_Polytropic:
        R = ct.gas_constant / gas_in.phase.mean_molecular_weight
        Sout = gas_in.s - R*log(PR)*(1/Eta-1)
        gas_out.SP = Sout, Pout
    else:
        gas_out.SP = gas_in.entropy_mass, Pout
        final_enthalpy_is = gas_out.enthalpy_mass
        # eta_is = (initial_enthalpy - final_enthalpy) / (initial_enthalpy - final_enthalpy_is)
        final_enthalpy = gas_in.enthalpy_mass - (gas_in.enthalpy_mass - final_enthalpy_is) * Eta
        gas_out.HP = final_enthalpy, Pout
        # if Wexp = None then assume mass flow in = mass flow out here (gas_in.mass = gas_out.mass), so:
    if Wexp == None:
        PW = gas_in.H - gas_out.H
    else:
        PW = Wexp * (gas_in.enthalpy_mass - gas_out.enthalpy_mass)
    return PW

#  2.0
# try the fastest first.
# For your case, a good practical order is auto → vcs → gibbs.
# Do not assume the fastest successful one is always the best-conditioned one.
# Log solver usage so you can see where robustness problems are coming from.
def robust_combustor_equilibrate(gas, max_iter=2000):
    methods = [
        ("auto",  dict()),
        ("vcs",   dict(solver="vcs", max_iter=max_iter)),
        ("gibbs", dict(solver="gibbs", max_iter=max_iter, estimate_equil=-1)),
    ]

    last_err = None
    for name, kwargs in methods:
        try:
            gas.equilibrate("HP", **kwargs)
            return name
        except Exception as err:
            last_err = err

    raise RuntimeError(f"All HP equilibrium solvers failed. Last error: {last_err}")

def stagnation_pressure_from_quantity(q, V):
    # Stagnation pressure p0 for a ct.Quantity state with speed V.
    # Uses h0 = h + V^2/2 and finds p0 so s(T0,p0,Y) = s(T,P,Y).
    # No clones: saves/restores the underlying phase state.
    ph = q.phase
    # Save phase state
    try:
        # Prefer explicit save (compatible across Cantera versions)
        T_save, P_save = ph.TP
        Y_save = ph.Y.copy()

        # Base static state (ensure phase matches quantity)
        ph.TPY = q.T, q.P, q.Y
        h = ph.enthalpy_mass      # J/kg
        s = ph.entropy_mass       # J/(kg·K)

        # Stagnation enthalpy and T0 at same pressure
        h0 = h + 0.5 * V * V
        ph.HP = h0, q.P           # sets T0 (composition fixed)
        T0 = ph.T

        # Root find p0 so that s(T0, p0, Y) = s
        def s_at_p(p):
            ph.TPY = T0, p, q.Y
            return ph.entropy_mass

        s_target = s

        # Bracket pressure in log-space
        P_ref = q.P
        p_lo = max(1.0, 0.02 * P_ref)
        p_hi = 50.0 * P_ref
        s_lo = s_at_p(p_lo)
        s_hi = s_at_p(p_hi)

        tries = 0
        while (s_lo - s_target) * (s_hi - s_target) > 0.0 and tries < 6:
            p_lo *= 0.2
            p_hi *= 5.0
            s_lo = s_at_p(p_lo)
            s_hi = s_at_p(p_hi)
            tries += 1

        if (s_lo - s_target) * (s_hi - s_target) > 0.0:
            # Couldn’t bracket: fall back to static pressure (conservative)
            return q.P

        # Bisection in ln(p)
        ln_lo, ln_hi = log(p_lo), log(p_hi)
        for _ in range(40):
            ln_mid = 0.5 * (ln_lo + ln_hi)
            p_mid = exp(ln_mid)
            s_mid = s_at_p(p_mid)
            if (s_lo - s_target) * (s_mid - s_target) <= 0.0:
                ln_hi, s_hi = ln_mid, s_mid
            else:
                ln_lo, s_lo = ln_mid, s_mid

        p0 = exp(0.5 * (ln_lo + ln_hi))
        return p0

    finally:
        # Restore original phase state
        ph.TPY = T_save, P_save, Y_save

#  2.0 for converting from Cantera 1-D arrays
def scalar(x):
    a = np.asarray(x)
    if a.size != 1:
        raise ValueError(f"Expected scalar-like value, got shape {a.shape}: {x!r}")
    return float(a.squeeze())

def scalar_dict(d):
    return {k: scalar(v) for k, v in d.items()}

#  under development ?
# def static_from_total(q_tot, A=None,
#                       p_lo_fac=0.05, p_hi_fac=0.999999, rtol=1e-8):
#     """
#     Map total (T0, p0, Y) to static (T, P, rho, V, M) using a 1D root solve in P.
#     Uses SciPy's root_scalar (Brent) for robustness and brevity.
#     - q_tot: ct.Quantity or ct.Solution with .T,.P as TOTAL (your convention), composition set
#     - Provide either (A & mdot) or mass_flux (G = mdot/A). If neither, returns low-Mach fallback.
#     """
#     ph = q_tot.phase
#     T0, p0 = float(q_tot.T), float(q_tot.P)
#     Y = q_tot.Y.copy()

#     # Low-Mach fallback if no velocity info
#     if A is None:
#         # return {"T": T0, "P": p0, "rho": q_tot.density, "V": 0.0, "Mach": 0.0,
#         #         "T0": T0, "p0": p0, "h0": q_tot.enthalpy_mass, "s0": q_tot.entropy_mass}
#         # return T, P, V, Mach
#         return T0, p0, 0.0, 0.0

#     # Mass flux
#     G = float(q_tot.mass) / float(A)

#     # Save/restore
#     T_s, P_s = ph.TP
#     Y_s = ph.Y.copy()
#     try:
#         # Total (frozen comp) properties
#         ph.TPY = T0, p0, Y
#         h0 = ph.enthalpy_mass
#         s0 = ph.entropy_mass

#         # Residual f(P) at fixed s=s0 (composition frozen)
#         def residual(P):
#             P = max(1.0, float(P))
#             ph.SP = s0, P                  # set static T via isentropic map
#             ph.set_unnormalized_mass_fractions(Y)
#             rho = ph.density
#             h = ph.enthalpy_mass
#             V = G / rho
#             return (h + 0.5 * V * V) - h0

#         # Bracket and solve in log(P) for stability
#         P_lo = max(1.0, p0 * p_lo_fac)
#         P_hi = max(1.0, p0 * p_hi_fac)

#         # If signs don't differ, gently widen the lower bound a few times
#         f_lo = residual(P_lo)
#         f_hi = residual(P_hi)
#         tries = 0
#         while f_lo * f_hi > 0.0 and tries < 8:
#             P_lo *= 0.5
#             f_lo = residual(P_lo)
#             tries += 1

#         if f_lo * f_hi > 0.0:
#             # Couldn’t bracket → very low Mach; return near-total values
#             ph.SP = s0, p0
#             ph.set_unnormalized_mass_fractions(Y)
#             rho = ph.density
#             V = G / rho
#             M = (V / ph.sound_speed)
#             # return {"T": ph.T, "P": p0, "rho": rho, "V": V, "Mach": M,
#             #         "T0": T0, "p0": p0, "h0": h0, "s0": s0}
#             # return T, P, V, Mach
#             return ph.T, p0, V, M

#         # Solve f(P)=0 (Brent)
#         sol = root_scalar(lambda lnP: residual(exp(lnP)),
#                           bracket=(log(P_lo), log(P_hi)), rtol=rtol, method="brentq")
#         P_star = exp(sol.root)

#         # Final static state at P_star, s=s0
#         ph.SP = s0, P_star
#         ph.set_unnormalized_mass_fractions(Y)
#         T_star = ph.T
#         rho_star = ph.density
#         V_star = G / rho_star
#         M_star = (V_star / ph.sound_speed)

#         # return {"T": T_star, "P": P_star, "rho": rho_star, "V": V_star, "Mach": M_star,
#         #         "T0": T0, "p0": p0, "h0": h0, "s0": s0}
#         return T_star, P_star, V_star, M_star

#     finally:
#         ph.TPY = T_s, P_s, Y_s

# def p0_out_isentropic(q_in, q_out, V_out=0.0):
#     """
#     Isentropic reference at constant static P:
#     - Keep inlet entropy and inlet (frozen) composition Y_in
#     - Use outlet stagnation temperature T0_out(real)
#     - Solve for p0_iso: s(T0_out, p0_iso, Y_in) = s_in
#     """
#     ph = q_out.phase
#     # Save state
#     T_s, P_s = ph.TP
#     Y_s = ph.Y.copy()
#     try:
#         # Inlet entropy with inlet composition
#         ph.TPY = q_in.T, q_in.P, q_in.Y
#         s_in = ph.entropy_mass
#         Y_in = q_in.Y.copy()

#         # Real outlet stagnation temperature (you may set V_out=0.0 if desired)
#         ph.TPY = q_out.T, q_out.P, q_out.Y
#         h_out = ph.enthalpy_mass
#         h0_out = h_out + 0.5 * V_out * V_out
#         ph.HP = h0_out, q_out.P
#         T0_out = ph.T

#         # Root for p0_iso with frozen inlet composition
#         def s_at_p(p):
#             ph.TPY = T0_out, p, Y_in
#             return ph.entropy_mass

#         P_ref = q_out.P
#         p_lo, p_hi = max(1.0, 0.02*P_ref), 50.0*P_ref
#         s_lo, s_hi = s_at_p(p_lo), s_at_p(p_hi)
#         tries = 0
#         while (s_lo - s_in)*(s_hi - s_in) > 0.0 and tries < 6:
#             p_lo *= 0.2; p_hi *= 5.0
#             s_lo, s_hi = s_at_p(p_lo), s_at_p(p_hi)
#             tries += 1
#         if (s_lo - s_in)*(s_hi - s_in) > 0.0:
#             return q_out.P  # conservative fallback

#         import math
#         ln_lo, ln_hi = math.log(p_lo), math.log(p_hi)
#         for _ in range(40):
#             ln_mid = 0.5*(ln_lo+ln_hi)
#             p_mid = math.exp(ln_mid)
#             s_mid = s_at_p(p_mid)
#             if (s_lo - s_in)*(s_mid - s_in) <= 0.0:
#                 ln_hi, s_hi = ln_mid, s_mid
#             else:
#                 ln_lo, s_lo = ln_mid, s_mid
#         return math.exp(0.5*(ln_lo+ln_hi))
#     finally:
#         ph.TPY = T_s, P_s, Y_s