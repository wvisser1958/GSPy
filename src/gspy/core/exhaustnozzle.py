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

# v1.2 Propelling exhaust nozzle
import math
import numpy as np
import gspy.core.utils as fu
from gspy.core.flow_state import TFlowState
from scipy.optimize import root_scalar
from gspy.core.gaspath import TGaspath

class TExhaustNozzle(TGaspath):
    def __init__(self,
                *,
                station_throat,
                CXdes, 
                CVdes, 
                CDdes,
                ConDi_exit_throat_area_ratio = 1,
                **kwargs):    # Constructor of the class
        # CXdes, CVdes, CDdes are for propelling nozzle
        # PRdes = diffuser pressure loss (Psout/Ptin) in case of a (divergent) exhaust diffuser
        # If PRdes <> None then a divergent diffuser expansion is calculated, with PRdes as the diffuser
        # pressure loss. PRdes must be < 1. Psout then determines the diffuser exit area A9.
        super().__init__(**kwargs)

        # add nozzle throat station
        # 2.1
        self.station_throat = station_throat
        self.fs_throat = TFlowState.create_empty(self.system.gas, 
                                                self.station_throat,
                                                enable_liquid_water=self.enable_liquid_water)
        self.CXdes = CXdes
        self.CVdes = CVdes
        self.CDdes = CDdes
        self.ConDi_exit_throat_area_ratio = ConDi_exit_throat_area_ratio

    def determine_cd_nozzle_conditions(
        self,
        fs_total: "TFlowState",
        fs_exit: "TFlowState",
        fs_shock_up: "TFlowState",
        fs_shock_down: "TFlowState",
        *,
        A_throat: float,
        A_exit: float,
        P_amb: float,
        pressure_tol: float = 1e-7,
    ):
        """
        Determine the flow regime and exit conditions of an ideal
        convergent-divergent nozzle.

        Assumptions
        -----------
        - quasi-one-dimensional flow
        - adiabatic nozzle
        - isentropic except across a possible normal shock
        - equilibrium vapor/liquid phase split during smooth expansion
        - negligible wall friction
        - no liquid/gas slip
        - negligible condensed-water volume

        Returns
        -------
        dict with:
            regime
            P_exit
            V_exit
            Mach_exit
            A_shock       # None if no internal shock
        """

        if A_exit < A_throat:
            raise ValueError("A_exit must be >= A_throat")

        if P_amb <= 0.0:
            raise ValueError("P_amb must be > 0")

        Pt = fs_total.P
        Ht = fs_total.H_total
        St = fs_total.S_total
        m_dot = fs_total.W

        if m_dot <= 0.0:
            raise ValueError("Nozzle mass flow must be > 0")

        # ----------------------------------------------------------
        # Helpers
        # ----------------------------------------------------------

        def bulk_density(fs):
            """
            Effective mixture density, assuming condensed water occupies
            negligible volume and moves with the gas.
            """
            rho_gas = fs.gas_q.phase.density
            m_gas = fs.gas_q.mass

            return rho_gas * fs.W / m_gas


        def evaluate_isentropic(P_static, fs):
            """
            Isentropic equilibrium expansion from fs_total to P_static.
            """
            fs.copy_from(fs_total)

            fs.update_SP(
                S_target=St,
                P_target=P_static,
            )

            dH = Ht - fs.H_total

            if dH < 0.0:
                if dH > -1e-10 * max(abs(Ht), 1.0):
                    dH = 0.0
                else:
                    raise RuntimeError(
                        f"Static enthalpy exceeds total enthalpy: dH={dH:g}"
                    )

            V = math.sqrt(2.0 * dH / m_dot)

            rho = bulk_density(fs)
            a = fs.gas_q.phase.sound_speed
            M = V / a

            return M, V, rho


        def massflow_residual(P_static, A, fs):
            M, V, rho = evaluate_isentropic(P_static, fs)

            return rho * V * A - m_dot


        # ----------------------------------------------------------
        # 1. Find sonic throat state from the given throat area.
        #
        # First use the previous throat-pressure method to determine
        # the M=1 thermodynamic state.
        # ----------------------------------------------------------

        fs_star = fs_shock_up

        def sonic_residual(P_static):
            M, _, _ = evaluate_isentropic(P_static, fs_star)
            return M - 1.0

        sol_star = root_scalar(
            sonic_residual,
            bracket=(max(1.0, 1e-6 * Pt), Pt * (1.0 - 1e-10)),
            method="toms748",
            rtol=pressure_tol,
        )

        if not sol_star.converged:
            raise RuntimeError("Could not determine sonic throat pressure")

        P_star = sol_star.root
        M_star, V_star, rho_star = evaluate_isentropic(P_star, fs_star)

        A_required_star = m_dot / (rho_star * V_star)

        # Fixed-area off-design matching quantity
        throat_area_ratio = A_required_star / A_throat

        # The engine-cycle solver can use this as the nozzle matching
        # residual. Here we assume that it has already converged sufficiently.
        #
        # If A_required_star > A_throat, the requested mass flow cannot pass.
        # If significantly lower, the prescribed incoming mass flow does not
        # fill the choked throat.
        #
        # For the C-D regime calculation we proceed with the choked condition.

        # ----------------------------------------------------------
        # 2. Supersonic isentropic exit solution
        # ----------------------------------------------------------

        def supersonic_exit_residual(P_static):
            return massflow_residual(P_static, A_exit, fs_exit)

        # Supersonic branch is below P_star.
        P_low = max(1.0, 1e-6 * Pt)

        sol_sup = root_scalar(
            supersonic_exit_residual,
            bracket=(P_low, P_star * (1.0 - 1e-8)),
            method="toms748",
            rtol=pressure_tol,
        )

        if not sol_sup.converged:
            raise RuntimeError(
                "Could not determine supersonic C-D nozzle exit state"
            )

        P_exit_sup = sol_sup.root
        M_exit_sup, V_exit_sup, rho_exit_sup = evaluate_isentropic(
            P_exit_sup,
            fs_exit,
        )

        # ----------------------------------------------------------
        # 3. Normal-shock helper
        # ----------------------------------------------------------

        def normal_shock_at_area(A_shock):
            """
            Calculate equilibrium downstream state across a stationary
            normal shock located at area A_shock.

            Returns downstream state plus upstream/downstream velocities.
            """

            # ----------------------------------------------
            # Upstream supersonic state at this area
            # ----------------------------------------------

            def upstream_area_residual(P1):
                return massflow_residual(
                    P1,
                    A_shock,
                    fs_shock_up,
                )

            sol_P1 = root_scalar(
                upstream_area_residual,
                bracket=(P_low, P_star * (1.0 - 1e-8)),
                method="toms748",
                rtol=pressure_tol,
            )

            if not sol_P1.converged:
                raise RuntimeError(
                    "Could not determine pre-shock supersonic state"
                )

            P1 = sol_P1.root

            M1, V1, rho1 = evaluate_isentropic(
                P1,
                fs_shock_up,
            )

            G = m_dot / A_shock

            Ht_shock = Ht

            # ----------------------------------------------
            # Initial guess using ordinary normal-shock
            # relations only as a numerical starting guess.
            # Final solution below uses actual TFlowState
            # thermodynamics.
            # ----------------------------------------------

            phase1 = fs_shock_up.gas_q.phase
            gamma1 = phase1.cp_mass / phase1.cv_mass

            P2_P1_guess = (
                1.0
                + 2.0 * gamma1 / (gamma1 + 1.0)
                * (M1 * M1 - 1.0)
            )

            P2_guess = P1 * P2_P1_guess

            rho2_rho1_guess = (
                (gamma1 + 1.0) * M1 * M1
                / (
                    (gamma1 - 1.0) * M1 * M1
                    + 2.0
                )
            )

            T2_guess = (
                fs_shock_up.T
                * P2_P1_guess
                / rho2_rho1_guess
            )

            momentum1 = P1 + G * V1

            # ----------------------------------------------
            # Solve post-shock T2 and P2 from:
            #
            #   energy:
            #       Ht = H2 + 1/2 m V2²
            #
            #   momentum:
            #       P1 + G V1 = P2 + G V2
            #
            # Mass conservation is already imposed by:
            #       V2 = G / rho2
            # ----------------------------------------------

            def shock_residual(z):
                T2 = math.exp(z[0])
                P2 = math.exp(z[1])

                fs_shock_down.copy_from(fs_shock_up)

                if fs_shock_down.enable_liquid_water:
                    fs_shock_down.repartition_at_TP(T2, P2)
                else:
                    fs_shock_down.gas_q.TP = T2, P2
                    fs_shock_down._set_static_equal_total()

                rho2 = bulk_density(fs_shock_down)

                V2 = G / rho2

                energy_error = (
                    fs_shock_down.H_total
                    + 0.5 * m_dot * V2 * V2
                    - Ht_shock
                )

                momentum_error = (
                    P2 + G * V2 - momentum1
                )

                # Normalize equations for scipy.root.
                return np.array([
                    energy_error / max(abs(Ht_shock), 1.0),
                    momentum_error / max(abs(momentum1), 1.0),
                ])

            sol_shock = root(
                shock_residual,
                np.log([T2_guess, P2_guess]),
                method="hybr",
            )

            if not sol_shock.success:
                raise RuntimeError(
                    "Normal-shock calculation failed: "
                    + sol_shock.message
                )

            T2, P2 = np.exp(sol_shock.x)

            # Evaluate once more to leave fs_shock_down
            # exactly at the final state.
            shock_residual(sol_shock.x)

            rho2 = bulk_density(fs_shock_down)
            V2 = G / rho2
            a2 = fs_shock_down.gas_q.phase.sound_speed
            M2 = V2 / a2

            return {
                "A": A_shock,
                "P1": P1,
                "T1": fs_shock_up.T,
                "M1": M1,
                "V1": V1,

                "P2": P2,
                "T2": fs_shock_down.T,
                "M2": M2,
                "V2": V2,

                "S2": fs_shock_down.S_total,
            }


        # ----------------------------------------------------------
        # 4. Subsonic flow from shock to nozzle exit
        # ----------------------------------------------------------

        def exit_after_shock(A_shock):
            shock = normal_shock_at_area(A_shock)

            S2 = shock["S2"]

            # Preserve downstream shock state because fs_exit will be modified.
            fs2 = fs_shock_down

            def eval_subsonic(P):
                fs_exit.copy_from(fs2)

                fs_exit.update_SP(
                    S_target=S2,
                    P_target=P,
                )

                dH = Ht - fs_exit.H_total

                if dH < 0.0:
                    if dH > -1e-10 * max(abs(Ht), 1.0):
                        dH = 0.0
                    else:
                        raise RuntimeError(
                            "Negative kinetic-energy term downstream of shock"
                        )

                V = math.sqrt(2.0 * dH / m_dot)

                rho = bulk_density(fs_exit)

                return rho * V * A_exit - m_dot, V

            # Immediately after the shock, P=P2.
            P2 = shock["P2"]

            # Upstream total pressure is always a safe upper search limit;
            # total pressure downstream of a normal shock is lower.
            P_high = Pt * (1.0 - 1e-10)

            f_low, _ = eval_subsonic(P2 * (1.0 + 1e-9))
            f_high, _ = eval_subsonic(P_high)

            if f_low * f_high > 0.0:
                raise RuntimeError(
                    "Could not bracket downstream subsonic exit state"
                )

            sol_exit = root_scalar(
                lambda P: eval_subsonic(P)[0],
                bracket=(
                    P2 * (1.0 + 1e-9),
                    P_high,
                ),
                method="toms748",
                rtol=pressure_tol,
            )

            if not sol_exit.converged:
                raise RuntimeError(
                    "Could not determine downstream subsonic exit pressure"
                )

            P_exit = sol_exit.root

            _, V_exit = eval_subsonic(P_exit)

            rho_exit = bulk_density(fs_exit)
            a_exit = fs_exit.gas_q.phase.sound_speed
            M_exit = V_exit / a_exit

            return {
                "shock": shock,
                "P_exit": P_exit,
                "V_exit": V_exit,
                "M_exit": M_exit,
                "rho_exit": rho_exit,
            }


        # ----------------------------------------------------------
        # 5. Determine the back-pressure regime
        # ----------------------------------------------------------

        # First: normal shock located exactly at exit.
        shock_at_exit = normal_shock_at_area(A_exit)

        P_after_shock_exit = shock_at_exit["P2"]

        # Limiting case: shock approaches throat.
        #
        # Use a very slightly larger area because exactly at M=1 the
        # shock strength becomes zero.
        A_near_throat = A_throat * (1.0 + 1e-6)

        near_throat_result = exit_after_shock(A_near_throat)
        P_back_max_choked = near_throat_result["P_exit"]

        # ----------------------------------------------------------
        # Fully supersonic / shock outside
        # ----------------------------------------------------------

        if P_amb < P_after_shock_exit:

            # Internal nozzle flow stays supersonic all the way to exit.
            #
            # If Pamb == P_exit_sup: ideally expanded.
            # If Pamb <  P_exit_sup: underexpanded.
            # If Pamb >  P_exit_sup: overexpanded, external shocks.
            #
            # A 1-D nozzle model cannot determine the physical position
            # of a shock outside the nozzle because there is no downstream
            # duct area function to locate it.
            if abs(P_amb - P_exit_sup) <= pressure_tol * P_exit_sup:
                regime = "supersonic_ideally_expanded"

            elif P_amb < P_exit_sup:
                regime = "supersonic_underexpanded"

            else:
                regime = "normal_shock_outside"

            # Restore final supersonic exit state
            evaluate_isentropic(P_exit_sup, fs_exit)

            fs_exit.V = V_exit_sup
            fs_exit.Mach = M_exit_sup
            fs_exit.Ps = P_exit_sup
            fs_exit.Ts = fs_exit.T

            return {
                "regime": regime,
                "P_exit": P_exit_sup,
                "V_exit": V_exit_sup,
                "Mach_exit": M_exit_sup,
                "A_shock": None,
                "A_required_throat": A_required_star,
                "throat_area_ratio": throat_area_ratio,
            }

        # ----------------------------------------------------------
        # Shock exactly at exit
        # ----------------------------------------------------------

        if abs(P_amb - P_after_shock_exit) <= (
            pressure_tol * P_after_shock_exit
        ):
            normal_shock_at_area(A_exit)

            fs_exit.copy_from(fs_shock_down)

            fs_exit.V = shock_at_exit["V2"]
            fs_exit.Mach = shock_at_exit["M2"]

            return {
                "regime": "normal_shock_at_exit",
                "P_exit": shock_at_exit["P2"],
                "V_exit": shock_at_exit["V2"],
                "Mach_exit": shock_at_exit["M2"],
                "A_shock": A_exit,
                "A_required_throat": A_required_star,
                "throat_area_ratio": throat_area_ratio,
            }

        # ----------------------------------------------------------
        # Shock inside divergent section
        # ----------------------------------------------------------

        if P_amb < P_back_max_choked:

            def shock_location_residual(A_shock):
                result = exit_after_shock(A_shock)

                return result["P_exit"] - P_amb

            sol_A = root_scalar(
                shock_location_residual,
                bracket=(
                    A_near_throat,
                    A_exit,
                ),
                method="toms748",
                rtol=pressure_tol,
            )

            if not sol_A.converged:
                raise RuntimeError(
                    "Could not determine internal normal-shock area"
                )

            A_shock = sol_A.root

            final = exit_after_shock(A_shock)

            return {
                "regime": "normal_shock_inside",
                "P_exit": final["P_exit"],
                "V_exit": final["V_exit"],
                "Mach_exit": final["M_exit"],
                "A_shock": A_shock,
                "P_shock_up": final["shock"]["P1"],
                "P_shock_down": final["shock"]["P2"],
                "Mach_shock_up": final["shock"]["M1"],
                "Mach_shock_down": final["shock"]["M2"],
                "A_required_throat": A_required_star,
                "throat_area_ratio": throat_area_ratio,
            }

        # ----------------------------------------------------------
        # Back pressure too high to sustain choking.
        #
        # The complete nozzle is then subsonic and its mass flow is
        # controlled by back pressure and throat area.
        # ----------------------------------------------------------

        return {
            "regime": "unchoked",
            "P_exit": P_amb,
            "V_exit": None,
            "Mach_exit": None,
            "A_shock": None,
            "A_required_throat": A_required_star,
            "throat_area_ratio": throat_area_ratio,
        }

    def determine_nozzle_conditions(
        self,
        fs_total: "TFlowState",
        fs_throat: "TFlowState",
        fs_exit: "TFlowState",
        *,
        P_amb: float,
        exit_throat_area_ratio: float = 1.0,
        pressure_tol: float = 1e-7,
    ):
        """
        Determine nozzle flow regime, throat state, exit state, and required
        throat area for the current inlet total state and mass flow.

        Supports:
            - convergent nozzle: Ae/At = 1
            - convergent-divergent nozzle: Ae/At > 1
            - fully subsonic operation
            - choked operation

        DP:
            store A_throat_required as design throat area.

        OD:
            compare A_throat_required with stored design throat area.
        """

        R = float(exit_throat_area_ratio)

        if R < 1.0:
            raise ValueError(
                "exit_throat_area_ratio must be >= 1.0"
            )

        Pt = fs_total.P
        Ht = fs_total.H_total
        St = fs_total.S_total
        W = fs_total.W

        if W <= 0.0:
            raise ValueError("Nozzle mass flow must be > 0")

        if not 0.0 < P_amb < Pt:
            raise ValueError(
                f"Require 0 < P_amb < Pt; "
                f"P_amb={P_amb:g}, Pt={Pt:g}"
            )

        # ----------------------------------------------------------
        # Helpers
        # ----------------------------------------------------------

        def bulk_density(fs):
            """
            Effective bulk-flow density.

            Condensed water is assumed to move with the gas and occupy
            negligible volume.
            """
            return (
                fs.gas_q.phase.density
                * fs.W
                / fs.gas_q.mass
            )

        def eval_static(Ps, fs):
            """
            Isentropic expansion from nozzle total state to static pressure Ps.

            Returns:
                M, V, rho, a, A_required
            """
            fs.copy_from(fs_total)

            fs.update_SP(
                S_target=St,
                P_target=Ps,
            )

            dH = Ht - fs.H_total

            if dH < 0.0:
                if dH > -1e-10 * max(abs(Ht), 1.0):
                    dH = 0.0
                else:
                    raise RuntimeError(
                        f"Static enthalpy exceeds total enthalpy: "
                        f"dH={dH:g}"
                    )

            V = math.sqrt(2.0 * dH / W)

            rho = bulk_density(fs)
            a = fs.gas_q.phase.sound_speed
            M = V / a

            if V <= 0.0:
                A_required = math.inf
            else:
                A_required = W / (rho * V)

            return M, V, rho, a, A_required

        def sonic_residual(Ps):
            M, _, _, _, _ = eval_static(Ps, fs_throat)
            return M - 1.0

        # ----------------------------------------------------------
        # 1. Evaluate hypothetical isentropic expansion to ambient
        # ----------------------------------------------------------

        (
            M_amb,
            V_amb,
            rho_amb,
            a_amb,
            A_exit_amb,
        ) = eval_static(
            P_amb,
            fs_exit,
        )

        # ----------------------------------------------------------
        # 2. Find sonic state safely
        #
        # If M(Pamb) >= 1, Pamb already provides the low-side bracket.
        #
        # If M(Pamb) < 1, progressively reduce pressure until M > 1.
        # Do not jump directly to an extremely low pressure, because
        # Cantera may encounter an invalid low-temperature state.
        # ----------------------------------------------------------

        P_high = Pt * (1.0 - 1e-10)
        f_high = sonic_residual(P_high)

        if f_high >= 0.0:
            raise RuntimeError(
                "Unexpected nozzle state: Mach is already >= 1 "
                "near total pressure."
            )

        if M_amb >= 1.0:
            P_low = P_amb
            f_low = M_amb - 1.0

        else:
            P_low = P_amb
            f_low = M_amb - 1.0

            # Search downward progressively.
            for _ in range(30):
                if f_low >= 0.0:
                    break

                P_trial = 0.7 * P_low

                try:
                    f_trial = sonic_residual(P_trial)

                except Exception as err:
                    raise RuntimeError(
                        f"Could not safely bracket nozzle sonic state. "
                        f"Isentropic expansion became invalid at "
                        f"Ps={P_trial:g} Pa."
                    ) from err

                P_low = P_trial
                f_low = f_trial

            if f_low < 0.0:
                raise RuntimeError(
                    "Could not bracket nozzle sonic state before reaching "
                    "the valid thermodynamic range."
                )

        # Exact M=1 case at ambient
        if abs(f_low) <= 1e-12:
            P_star = P_low
        else:
            sol_star = root_scalar(
                sonic_residual,
                bracket=(P_low, P_high),
                method="toms748",
                rtol=pressure_tol,
            )

            if not sol_star.converged:
                raise RuntimeError(
                    "Could not determine nozzle sonic state."
                )

            P_star = sol_star.root

        (
            M_star,
            V_star,
            rho_star,
            a_star,
            A_star,
        ) = eval_static(
            P_star,
            fs_throat,
        )

        # ----------------------------------------------------------
        # 3. Check whether a fully subsonic solution exists
        #
        # For fully subsonic flow:
        #
        #     Ae / At = R
        #
        # At the limiting case where the throat approaches M=1:
        #
        #     R_max_subsonic = Ae(Pamb) / A*
        #
        # If R <= R_max_subsonic, a subsonic throat solution exists.
        # ----------------------------------------------------------

        fully_subsonic = False

        if M_amb < 1.0:
            R_max_subsonic = A_exit_amb / A_star

            if R <= R_max_subsonic * (1.0 + pressure_tol):
                fully_subsonic = True

        # ==========================================================
        # FULLY SUBSONIC
        # ==========================================================

        if fully_subsonic:

            # ------------------------------------------------------
            # Pure convergent nozzle
            # ------------------------------------------------------

            if abs(R - 1.0) <= 1e-12:

                fs_throat.copy_from(fs_exit)

                fs_throat.V = V_amb
                fs_throat.Mach = M_amb
                fs_throat.Ps = P_amb
                fs_throat.Ts = fs_throat.T

                A_throat_required = A_exit_amb
                A_exit_required = A_exit_amb

            # ------------------------------------------------------
            # Fully subsonic C-D nozzle
            #
            # Solve subsonic throat pressure from:
            #
            #     A_exit / A_throat = R
            #
            # with:
            #
            #     P_amb < P_throat < P_star
            # ------------------------------------------------------

            else:

                def area_ratio_residual(Ps_throat):
                    _, _, _, _, A_throat = eval_static(
                        Ps_throat,
                        fs_throat,
                    )

                    return (
                        A_exit_amb / A_throat
                        - R
                    )

                sol_throat = root_scalar(
                    area_ratio_residual,
                    bracket=(P_amb, P_star),
                    method="toms748",
                    rtol=pressure_tol,
                )

                if not sol_throat.converged:
                    raise RuntimeError(
                        "Could not determine subsonic nozzle throat state."
                    )

                P_throat = sol_throat.root

                (
                    M_throat,
                    V_throat,
                    rho_throat,
                    a_throat,
                    A_throat_required,
                ) = eval_static(
                    P_throat,
                    fs_throat,
                )

                fs_throat.V = V_throat
                fs_throat.Mach = M_throat
                fs_throat.Ps = P_throat
                fs_throat.Ts = fs_throat.T

                A_exit_required = A_exit_amb

            # Restore exact exit state at ambient pressure
            (
                M_exit,
                V_exit,
                rho_exit,
                a_exit,
                _,
            ) = eval_static(
                P_amb,
                fs_exit,
            )

            fs_exit.V = V_exit
            fs_exit.Mach = M_exit
            fs_exit.Ps = P_amb
            fs_exit.Ts = fs_exit.T

            return {
                "regime": "subsonic",
                "choked": False,

                "A_throat_required": A_throat_required,
                "A_exit_required": A_exit_required,

                "P_throat": fs_throat.P,
                "T_throat": fs_throat.T,
                "Mach_throat": fs_throat.Mach,
                "V_throat": fs_throat.V,

                "P_exit": P_amb,
                "T_exit": fs_exit.T,
                "Mach_exit": M_exit,
                "V_exit": V_exit,

                "pressure_thrust": 0.0,
            }

        # ==========================================================
        # CHOKED
        # ==========================================================

        (
            M_throat,
            V_throat,
            rho_throat,
            a_throat,
            A_throat_required,
        ) = eval_static(
            P_star,
            fs_throat,
        )

        fs_throat.V = V_throat
        fs_throat.Mach = M_throat
        fs_throat.Ps = P_star
        fs_throat.Ts = fs_throat.T

        A_exit_required = R * A_throat_required

        # ----------------------------------------------------------
        # Choked convergent nozzle
        # ----------------------------------------------------------

        if abs(R - 1.0) <= 1e-12:

            fs_exit.copy_from(fs_throat)

            fs_exit.V = V_throat
            fs_exit.Mach = 1.0
            fs_exit.Ps = P_star
            fs_exit.Ts = fs_throat.T

            pressure_thrust = (
                A_throat_required
                * (P_star - P_amb)
            )

            return {
                "regime": "choked_convergent",
                "choked": True,

                "A_throat_required": A_throat_required,
                "A_exit_required": A_throat_required,

                "P_throat": P_star,
                "T_throat": fs_throat.T,
                "Mach_throat": 1.0,
                "V_throat": V_throat,

                "P_exit": P_star,
                "T_exit": fs_exit.T,
                "Mach_exit": 1.0,
                "V_exit": V_throat,

                "pressure_thrust": pressure_thrust,
            }

        # ----------------------------------------------------------
        # Choked C-D nozzle
        # ----------------------------------------------------------

        cd = self.determine_cd_nozzle_conditions(
            fs_total,
            fs_exit,
            self.fs_shock_up,
            self.fs_shock_down,
            A_throat=A_throat_required,
            A_exit=A_exit_required,
            P_amb=P_amb,
            pressure_tol=pressure_tol,
        )

        cd.update({
            "choked": True,

            "A_throat_required": A_throat_required,
            "A_exit_required": A_exit_required,

            "P_throat": P_star,
            "T_throat": fs_throat.T,
            "Mach_throat": 1.0,
            "V_throat": V_throat,
        })

        return cd

    def Run(self, Mode, PointTime):
        super().Run(Mode, PointTime)
        self.fs_throat.copy_from(self.fs_in, overrule_enable_liquid_water=self.enable_liquid_water)
        
        Hin = self.fs_in.gas_q.enthalpy_mass
        Pin = self.fs_in.gas_q.P
        P_amb = self.system.ambient.Psa
        # propelling nozzle, expansion flow
        # PR is nozzle PR Pout/Pin, only calculated (not given)
        # # v1.2
        # self.PR = Pin/Pout
        self.PR = Pin/P_amb
        if Mode == 'DP':
            self.PRdes = self.PR

            result = self.determine_nozzle_conditions(
                self.fs_in,
                self.fs_throat,
                self.fs_out,
                P_amb=self.system.ambient.Psa,
                exit_throat_area_ratio=self.ConDi_exit_throat_area_ratio,
            )

            self.A_throat_des = result["A_throat_required"]
            self.A_throat = self.A_throat_des
            self.A_exit_des = result["A_exit_required"]
            self.A_exit = self.A_exit_des

            self.ierror_w = self.system.add_error(self.name + '_Wout', 0.0)

            # self.V_throat = self.fs_throat.V
            # if self.V_throat <= 0:
            #     self.V_throat = 0.001  # always assume a minimal flow velocity: 0.001 will result in a theoretical
                                    # very large exhaust area
            # self.Athroat_des = fu.scalar(self.fs_throat.W_gas) / self.fs_throat.gas_q.phase.density / self.V_throat
        else:
            # Off-design calculation
            # self.Athroat = self.Athroat_des # fixed nozzle are still here
            # self.Pthroat, self.Tthroat, Vthroat_is, massflow = fu.calculate_expansion_to_A(self.fs_in.gas_q.phase, Pin/Pout, self.Athroat)
            # self.fs_throat.TP = self.Tthroat, self.Pthroat
            # self.Vthroat = Vthroat_is * self.CVdes

            result = self.determine_nozzle_conditions(
                self.fs_in,
                self.fs_throat,
                self.fs_out,
                P_amb=P_amb,
                exit_throat_area_ratio=self.ConDi_exit_throat_area_ratio,
            )

            A_required = result["A_throat_required"]

            self.system.errors[self.ierror_w] = (
                A_required / self.A_throat
                - 1.0
            )
            # self.system.errors[self.ierror_w] = (fu.scalar(self.fs_in.mass) - massflow) / fu.scalar(self.fs_in_des.W_gas)
            # self.system.errors[self.ierror_w] = (fu.scalar(self.fs_throat.A) - fu.scalar(self.Athroat_des)) / fu.scalar(self.Athroat_des)


            # 1.301 use Vthroat_is for Mach number
            # self.Mthroat = self.Vthroat / self.GasThroat.phase.sound_speed
            # self.Mthroat = Vthroat_is / self.fs_throat.gas_q.phase.sound_speed

        # self.fs_out.TP = self.Tthroat, Pout # assume no further expansion
        self.V_exit = result["V_exit"] * self.CVdes
        self.P_exit = result["P_exit"] * self.CVdes

        self.T_throat = result["T_throat"] 
        self.P_throat = result["P_throat"] 
        self.V_throat = result["V_throat"] 
        self.M_throat = result["Mach_throat"] 

        self.FG = self.CXdes * (fu.scalar(self.fs_out.W) * self.V_exit + self.A_exit*(self.P_exit-P_amb)) / 1000 # kN
        # add gross thrust to system level thrust (note that multiple propelling nozzles may exist)
        self.system.FG = self.system.FG + self.FG
        self.A_throat_geom = self.A_throat / self.CDdes
        self.system.gaspath_conditions[self.station_throat] = self.fs_throat
        return self.fs_out

    def PrintPerformance(self, Mode, PointTime):
        super().PrintPerformance(Mode, PointTime)
        # Print and return the results
        print(f"\t\tExit static temperature: {self.fs_out.T:.1f} K")
        print(f"\t\tExit static pressure: {self.fs_out.P:.0f} Pa")
        print(f"\t\tExit velocity: {self.V_throat:.2f} m/s")
        if Mode == 'DP':
            print(f"\t\tThroat area (DP): {self.A_throat_des:.4f} m2")
        print(f"\t\tAthroat: {self.A_throat:.4f} m2")
        print(f"\t\tThroat static pressure: {self.P_throat:.0f} Pa")
        print(f"\tGross thrust: {self.FG:.2f} kN")

    # 2.0.0.0
    def get_outputs(self):
        out = super().get_outputs()

        sthr = self.station_throat
        sout = self.station_out

        out[f"T{sthr}"]  = self.T_throat
        out[f"P{sthr}"]  = self.P_throat
        out[f"V{sthr}"]  = self.V_throat
        out[f"Mach{sthr}"]  = self.M_throat
        out[f"T{sout}"]  = self.fs_out.T
        out[f"P{sout}"]  = self.fs_out.P
        out[f"A{sthr}"]  = self.A_throat
        out[f"A{sthr}_geom"]  = self.A_throat_geom
        out["FG_"+self.name]  = self.FG

        return out

