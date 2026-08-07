# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#    http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Author
#   Wilfried Visser

from scipy.optimize import root_scalar
import numpy as np
import cantera as ct

from gspy.core.gaspath import TGaspath
import gspy.core.constants as c
import gspy.core.utils as fu

class TCombustor(TGaspath):
    def __init__(self, 
                 *,
                 Wfdes, # Design fuel flow, or first guess fuel flow in case Texitdes specified
                 Texitdes = None, 
                 PRdes = 1, 
                 Etades = 1,
                 Tfueldes = 288.15, 
                 LHVdes = None, 
                 HCratiodes = None, 
                 OCratiodes = None, 
                 FuelCompositiondes = None, 
                 A = None, 
                 FARdes = None,
                 **kwargs):
        super().__init__(**kwargs)
        self.Wfdes = Wfdes
        self.Wf = Wfdes
        # Texitdes: set as None, use None or not None to determine input type : Wf or Texit
        self.Texitdes = Texitdes
        self.Texit = None

        # 2.1 allow Fuel Air Ratio FAR control
        self.FARdes = FARdes
        self.FAR = None   # if using FAR for OD: must explicity assign self.FAR

        self.PRdes = PRdes
        self.A = A

        # On the combustor efficiency: note that it is only used to represent heat loss (multiplied with enthalpy change) and not reflected in a change in
        # combustion gas composition change (neither in for the LHV specification option nor for the Fuel composition specification option )
        self.Etades = Etades

        self.Tfueldes = Tfueldes
        self.LHVdes = LHVdes
        self.HCratiodes = HCratiodes
        self.OCratiodes = OCratiodes
        # fuel composition string, e.g. 'NC12H26:1', or a mixture like 'NC12H26:5, C2H6:1'
        # with 'NC12H26:5, C2H6:1' mole ratio if 5:1 if TPX is used, mass ratio if TPY is used, see Cantera documentation
        self.FuelCompositiondes = FuelCompositiondes

        # 1.4 set Fuel
        self.fuel = None  # initialize fuel quantity for later testing if None or already assigned
        self.SetFuel(Tfueldes, LHVdes, HCratiodes, OCratiodes, FuelCompositiondes)

        # 2.0 for OD equation if Texit specified instead of Wf
        self.istate_Wf = None
        self.ierror_Texit = None

        self.C_atom_weight = self.system.gas.atomic_weight(self.system.gas.element_index('C'))
        self.O_atom_weight = self.system.gas.atomic_weight(self.system.gas.element_index('O'))
        self.H_atom_weight = self.system.gas.atomic_weight(self.system.gas.element_index('H'))

        self.O2_molar_mass = self.system.gas.molecular_weights[self.system.gas.species_index('O2')]
        self.CO2_molar_mass = self.system.gas.molecular_weights[self.system.gas.species_index('CO2')]
        self.H2O_molar_mass = self.system.gas.molecular_weights[self.system.gas.species_index('H2O')]

        self.scratch_quantity = None  # scratch quantity for enthalpy calculations

    #  1.4 use separate routine, for allowing change of fuel for OD simulation cases
    def SetFuel(self, aTfuel, aLHV, aHCratio, aOCratio, aFuelComposition):
        self.Tfuel = aTfuel
        self.LHV = aLHV          # Lower Heating Value in kJ/kg
        self.HCratio = aHCratio  # H/C ratio for the virtual fuel
        self.OCratio = aOCratio  # O/C ratio for the virtual fuel
        self.FuelComposition = aFuelComposition
        return

    # 1.2 this routine is not actively used during simulation, but may be used separately
    #     to determine/compare LHV values or comparing values with vs without specified FuelComposion specified
    def GetLHV(self):
        # Stoichiometric combustion of methane (CH4 + 2 O2 + 7.52 N2)
        gas_reactants = ct.Solution('gri30.yaml')
        gas_reactants.TPX = 298.15, ct.one_atm, {'CH4':1, 'O2':2, 'N2':7.52}

        # Compute enthalpy of reactants
        h_react = gas_reactants.enthalpy_mass

        # Define products for *complete combustion* (CO2 + 2 H2O + 7.52 N2)
        gas_products = ct.Solution('gri30.yaml')
        gas_products.TPX = 298.15, ct.one_atm, {'CO2':1, 'H2O':2, 'N2':7.52}

        # Enthalpy of products (H2O as vapor)
        h_prod = gas_products.enthalpy_mass

        # LHV (kJ/kg fuel)
        # Compute mass fraction of CH4 in the reactant mixture
        Y_CH4 = gas_reactants.Y[gas_reactants.species_index('CH4')]
        LHV = -(h_prod - h_react) / Y_CH4 / 1e3  # convert J/kg → kJ/kg

        self.system.vprint(f"LHV of CH4 (H2O vapor): {LHV:.2f} kJ/kg")

    def fundamental_pressure_loss_rayleigh(self, A):
        """
        Fundamental (Rayleigh) total-pressure loss for constant-P, frictionless heating.
        Uses actual velocities from mdot and area (A_in=A_out=A).
        Returns {"p0_in", "p0_out", "loss"} with loss = 1 - p0_out/p0_in.

        Primary combustors (gas turbines/jet engines): fundamental (Rayleigh/thermodynamic)
        total-pressure loss is usually well under 1% at typical primary-zone Mach (≈0.02–0.05)
        and static-pressure-nearly-constant operation—even with large temperature rise.
        Most of the overall loss you see in specs (4–8%) is mechanical/aerodynamic.
        Afterburners: much larger ΔT_0and higher Mach (often 0.15–0.4) push the Rayleigh loss
        into a few percent. That’s the case where “fundamental” becomes a noticeable slice of the total.
        What drives it up
        Inlet Mach up > Rayleigh loss up (strongest driver).
        Stagnation-temperature rise up >  loss up (but at low Mach the effect is still modest).
        Lower dilution / lower γ> loss up slightly.
        Quick checks to ensure you’re in the right (<1%) regime:
        Compute Rayleigh fundamental strictly as 1-p_(0,"out" )/p_(0,"in" )using your real
        inlet/outlet states (same area, velocities from m ̇/A). For subsonic heating, this
        ratio must be positive and small.
        Re-run with V_"in" =V_"out" =0. If the loss jumps a lot when you include velocity,
        your exit Mach is probably too high for “primary-zone” assumptions.
        Verify constant static Pacross the reaction step in your model; mixing in a downstream
        diffuser/geometry change can contaminate the “fundamental” number.
        """
        q_in, q_out = self.fs_in, self.fs_out

        # velocities from continuity (A_in = A_out = A), mass flow mass = out mass flow for both in and out
        # because also the fuel flow must be accelerated during combustion
        V_in  = float(q_out.W_gas) / (q_in.density  * float(A))
        V_out = float(q_out.W_gas) / (q_out.density * float(A))

        p0_in  = fu.stagnation_pressure_from_quantity(q_in,  V_in)   # same helper as before
        p0_out = fu.stagnation_pressure_from_quantity(q_out, V_out)

        #  p0_out is now the "virtual" exit stagnation pressure as if there is no fundamental pressure loss,
        #  the loss is the difference between p0_out en p0_in, so

        # loss = 1.0 - (p0_out / p0_in)
        return p0_in / p0_out

    #    ********** under development ***************
    # def apply_rayleigh_and_fund_loss(self, A, mdot, iterate=False, iters=3):
    #     q1, q2 = self.gas_in, self.gas_out   # q2 after your Etades equilibrium

    #     G = mdot / A
    #     rho1 = q1.density
    #     V1 = G / rho1

    #     # start from your current outlet state (T2*, Y2*, rho2*)
    #     rho2 = q2.density
    #     for _ in range(iters if iterate else 1):
    #         # Rayleigh momentum: update P2
    #         P2 = q1.P + G*G*(1.0/rho2 - 1.0/rho1)
    #         # (strict) re-equilibrate at new static P2 while holding enthalpy/composition logic:
    #         # q2.HP = q2.enthalpy_mass, P2 ; q2.equilibrate("HP")
    #         # rho2 = q2.density

    #     # Total-pressure ratio (use your convention: P’s are totals)
    #     pi_fund = q2.P / q1.P
    #     loss = 1.0 - pi_fund
    #     # return {"P1": q1.P, "P2": q2.P, "loss": loss}
    #     return loss

    #    ********** under development ***************
    # def gas_out_total_pressure_from_static(self, T_static, P_static, T_total):
    #     """
    #     Compute total (stagnation) pressure p0 given static T,P and total temperature T0.
    #     Uses isentropic constraint (s = const) for a real mixture.
    #     """
    #     # Make a working copy
    #     # self.gas_out.TP = T_static, P_static
    #     # gas = self.gas_out.phase.clone()
    #     gas = ct.Solution(self.gas_out.phase.source)
    #     gas.TP = T_static, P_static
    #     s_static = gas.entropy_mass
    #     Y = gas.Y.copy()

    #     # Residual function for root solve: s(T0,p0) - s_static = 0
    #     def f(p):
    #         gas.TPY = T_total, p, Y
    #         return gas.entropy_mass - s_static

    #     # Bracket around static pressure (total pressure must be higher)
    #     sol = root_scalar(f, bracket=[P_static, P_static * 200.0], method="brentq")
    #     return sol.root

    # from GSP 12:
    #    ********** under development ***************
    # def CalcFundamentalDp(self, A):
    #     # // calc fundamental pressure loss: Recalculation of Cout.Pt using
    #     # // momentum balance ; assume static Cin cond. calculated !
    #     # // Force at entry station:
    #     try:
    #         q_in = self.gas_in
    #         q_out = self.gas_out
    #         w_out = self.gas_out.mass
    #         Ts_in, Ps_in, V_in, M_in = fu.static_from_total(q_in, A)
    #         Fin = Ps_in *A * (1+self.gas_in.phase.cp/self.gas_in.phase.cv * M_in * M_in)
    #         # // Force at exit station: (account for lower Cout.Pt due to normal pressure loss
    #         # //                         already calculated
    #         # //                         without normal pressure loss, of course Fout=Fin)
    #         Fout = Fin - A * (q_in.P- q_out.P)
    #         # starting value for M_out
    #         M_out = M_in
    #         Ts_out = Ts_in
    #         Ps_out = None
    #         Pt_out_no_loss = self.gas_out.P
    #         mach1_count= 0
    #         i = 0
    #         def W_residual(mach):
    #             # i += 1
    #             Csout = q_out.phase.sound_speed
    #             Hsout = q_out.enthalpy_mass - 0.5 * np.square(mach * Csout)
    #             # isentropic change to static H
    #             q_out.HP = Hsout, q_out.P

    #             Gammasout = q_out.phase.cp/ q_out.phase.cv
    #             Ps_out = Fout / A * (1+Gammasout * np.square(mach))
    #             R = ct.gas_constant / q_out.phase.mean_molecular_weight
    #             Wout1 = Ps_out / (R * q_out.T) * A * mach * Csout
    #             return (w_out-Wout1)/w_out
    #         solution = root_scalar(W_residual, bracket=[M_out, 1], method='brentq')
    #         M_out = solution.root

    #         Gammasout = q_out.phase.cp/ q_out.phase.cv
    #         Ps_out = Fout / A * (1+Gammasout * np.square(M_out))

    #         self.gas_out.P = self.gas_out_total_pressure_from_static(Ts_out, Ps_out, self.gas_out.T)
    #         return (Pt_out_no_loss - self.gas_out.P) / Pt_out_no_loss
    #     except Exception as e:
    #         print(f"Exception error {e} in {self.name} Fund. Press. Loss calculation, Hint: increase (burner) duct cross area.")

    def Run(self, Mode, PointTime):
        if isinstance(self.control, str):
            try:
                self.control = self.system.components[self.control]   # resolve by name -> object
            except Exception as e:
                raise ValueError(
                    f"Combustor '{self.name}': Control '{self.control}' cannot be resolved to an object. ({e})"
                )

        def CalcEndConditions(PointTime, Mode):
            # self.GetLHV()
            if (self.FuelComposition == '') or (self.FuelComposition is None):  # fuel specification based on LHV, HC and OC mole ratio
                #  2.1 use fs_out instead as the gas prior to mixing with fuel, 
                # as fs_out.Y has been corrected for any liquid water (using self.fs_out.disable_liquid_model(collapse=True): 
                # m_liq added to m_vap so that the gas composition is correct for the combustion calculation
                # Yin = self.fs_in.gas_q.Y
                # w_gas_in = self.fs_in.gas_q.mass
                # Yin = self.fs_out.gas_q.Y
                Yin = self.Y_out_0
                # w_gas_in = self.fs_out.gas_q.mass
                w_gas_in = self.W_gas_in_0

                # fuel moles of the virtual fuel based on the specified H/C and O/C ratios (normalized to 1 mole of C)
                fuel_moles = self.Wf / CHyOzMoleMass

                O2_in_mass  = w_gas_in * Yin[self.system.i_O2]
                CO2_in_mass = w_gas_in * Yin[self.system.i_CO2]
                # H2O_in_mass = self.fs_out.m_vap
                H2O_in_mass = w_gas_in * Yin[self.system.i_H2O]
                AR_in_mass  = w_gas_in * Yin[self.system.i_AR]
                N2_in_mass  = w_gas_in * Yin[self.system.i_N2]

                O2_exit_mass = (
                    O2_in_mass
                    + fuel_moles
                    * (self.OCratio / 2.0 - 1.0 - self.HCratio / 4.0)
                    * self.O2_molar_mass
                )

                CO2_exit_mass = (
                    CO2_in_mass
                    + self.CO2_molar_mass * fuel_moles
                )

                H2O_exit_mass = (
                    H2O_in_mass
                    + self.H2O_molar_mass * fuel_moles * self.HCratio / 2.0
                )

                Ar_exit_mass = AR_in_mass
                N2_exit_mass = N2_in_mass

                Yprod = np.zeros(self.system.gas.n_species)

                Yprod[self.system.i_O2]  = O2_exit_mass
                Yprod[self.system.i_CO2] = CO2_exit_mass
                Yprod[self.system.i_H2O] = H2O_exit_mass
                Yprod[self.system.i_AR]  = Ar_exit_mass
                Yprod[self.system.i_N2]  = N2_exit_mass

                Yprod /= Yprod.sum()
                # for debug:
                # print(type(product_composition_mass))
                # print(product_composition_mass)
                
                # use self.gas_out to get h_gas_in_ref before combustion (thanks Joao Cardoso Lopes!)                
                # so we can leave self.gas_in unchanged with the actual inlet composition, 
                # and use self.gas_out to get the reference enthalpy of the inlet gas composition 
                # at Tref and Pref, which is needed for the LHV-based calculation of the final enthalpy of the products after combustion
                m_gas = self.fs_in_q.gas_q.mass
                m_liq = self.fs_in_q.m_liq

                # self.fs_out.TPY = c.T_standard_ref, c.P_standard_ref, self.fs_in.gas_q.Y
                if self.scratch_quantity is None:
                    self.scratch_quantity = ct.Quantity(self.system.gas)
                self.scratch_quantity.TPY = c.T_standard_ref, c.P_standard_ref, self.fs_in_q.gas_q.Y
                h_gas_in_ref = self.scratch_quantity.enthalpy_mass

                # move to constants
                #  add liquid water:
                # w = ct.Water()
                # w = self.fs_out._scratch_water
                # w.TQ = c.T_standard_ref, 0.0          # saturated liquid water at Tref
                # h_liq_ref = w.enthalpy_mass

                H_in_ref = (
                    m_gas * h_gas_in_ref
                    + m_liq * c.h_liq_ref
                ) 

                # redefine gas_out for enthalpy of combustion products mixture at Pref and Tref of
                # assume all gas phase
                self.fs_out.gas_q.TPY = c.T_standard_ref, c.P_standard_ref, Yprod
                # make sure fuel mass flow added to the inlet gas flow (before working on total H !):
                # self.fs_out.W_gas = self.fs_in.mass + self.Wf
                self.fs_out.W = w_gas_in + self.Wf
                # H_prod_ref is the enthalpy of the products at the reference conditions, 
                # which is used as a baseline for calculating the final enthalpy of the products 
                # after combustion based on the specified LHV and the enthalpy of the inlet gas 
                # composition at the reference conditions. This allows us to account for the energy 
                # added by combustion while keeping track of the reference state for accurate energy balance calculations.
                H_prod_ref = self.fs_out.H_total  # get total H in J (enthalpy_mass * mass), for use in LHV calculation with Etades

                # now, calculate the final enthalpy of the products based on given LHV:
                # from equation for conservation of energy ()"in = out"):
                # w_fuel * LHV_kJ_kg*1000 + w_air * (h_air_initial - self.h_air_ref)  =   (w_air + w_fuel) * (h_prod_final - h_prod_ref)
                # assuming LHV defined at c.T_standard_ref, c.P_standard_ref,
                # 2.1 energy balance to calculate H_prod_final (final total enthalpy of the products after combustion)
                # based on the specified LHV and the enthalpy of the inlet gas composition at the reference conditions, 
                # and accounting for the efficiency (Etades) which represents heat loss during combustion:
                # assuming all water evaporated
                H_prod_final = self.Wf * self.LHV * 1000 * self.Etades + H_in_initial - H_in_ref  + H_prod_ref

                # now set exit gas_out H to h_prod_final, this will calculate gas_out.T
                self.fs_out.HP = H_prod_final, Pin

                if self.system.high_gas_fidelity or (Mode == 'DP'):
                    self.fs_out.equilibrate_combustor_mixture()

            else:                  # fuel specification based on FuelComposition and Tfuel
                #  1.4 test if fuel exists (DP may be virtual flow, and OD composition specified, so....)
                # if Mode == 'DP':
                if self.fuel is None:
                    # create separate fuel quantity for mixing with gas_in
                    self.fuel = ct.Quantity(self.system.gas)
                self.fuel.mass = self.Wf
                if self.Tfuel is None:      # assume Tfuel equal to T of air in
                    Tfuelin = self.fs_in_q.T
                else:                       # use user specified Tfuel
                    Tfuelin = self.Tfuel
                # v1.2 set P fuel to Pout, otherwise (using gas_in.P, which is before the pressure loss)
                #  the fuel pressure will increase the combustor pressure again with the TPY assignment
                # self.fuel.TPY = Tfuelin, self.gas_in.P, self.FuelComposition
                self.fuel.TPY = Tfuelin, Pin, self.FuelComposition
                # fuel.TPY = self.gas_in.T, self.gas_in.P, self.FuelComposition
                self.fs_out = self.fs_in_q + self.fuel

                # 1.3
                if self.Etades < 1.000:
                    # calculate enthalpy loss
                    # 1) Enthalpy of mixed, *unreacted* stream
                    h_in = self.fs_out.enthalpy_mass
                    # Save mixed, unreacted state
                    gas_out_phase_saved = self.fs_out.phase.state               # stores T, P, composition, etc.

                    # 3) Target enthalpy that includes heat loss via Etades
                    # self.gas_out.equilibrate("TP")                   # equilibrium at fixed T (mix temp) & P
                    self.fs_out.equilibrate_combustor_mixture()

                    dh_rxn_T = self.fs_out.enthalpy_mass - h_in     # this reflects reaction enthalpy at the mix T

                    # Apply efficiency (heat loss): scale the enthalpy release
                    h_target = h_in + (1-self.Etades) * dh_rxn_T

                    # Restore original mixed state
                    self.fs_out.phase.state = gas_out_phase_saved

                    # 4) Set target (H,P) and equilibrate to get final state with losses
                    self.fs_out.HP = h_target, Pin
                else:
                    # v1.2 reimpose pressure Pout to gas_out
                    self.fs_out.HP = self.fs_out.enthalpy_mass, Pin

                # 2.0
                # self.gas_out.equilibrate("HP")
                # fu.robust_combustor_equilibrate(self.fs_out)
                # self.fs_out.robust_equilibrate(self.fs_out.gas_q.gas)
                self.fs_out.equilibrate_quantity()

            # pressure loss
            if (self.A is None) or (self.A ==0):
                PRfund = 1
            else:
                # PRfund = 1- self.fundamental_pressure_loss_rayleigh(self.A, self.gas_out.mass)
                # PRfund = 1- self.apply_rayleigh_and_fund_loss(self.A, self.gas_out.mass)
                # PRfund = self.CalcFundamentalDp(self.A)
                # provisional:
                    # fundamental_pressure_loss_rayleigh is under test ************
                    # may want to have option  to specify exit Mach instead and calculate A
                PRfund = self.fundamental_pressure_loss_rayleigh(self.A)
            Pout = Pin * PRfund * self.PRdes
            self.fs_out.HP = self.fs_out.H_total, Pout

            # we redefined gas_out, so we must reassing self.gas_out to fsys.gaspath_conditions[self.station_out]
            self.system.gaspath_conditions[self.station_out] = self.fs_out
            return self.fs_out.T

        super().Run(Mode, PointTime)

        # self.GetLHV()

        # 2.1 assume no liquid water in combustor, 
        # so disable liquid model for the out gas, otherwise it may cause convergence issues when the water 
        # is close to saturation and the solver tries to add/remove liquid water to equilibrate
        self.fs_out.disable_liquid_model(collapse=True)
        # save initial fs_out.Y and w_gas for Texit iteration start 
        self.Y_out_0 = self.fs_out.gas_q.Y
        self.W_gas_in_0 = self.fs_out.gas_q.mass

        if Mode == 'DP':
            if self.Texitdes is not None: # calc Wf from Texit, use Wfdes as Wf first guess
                self.Texit = self.Texitdes  # now self.Wfdes is 1st guess for iteration to Text

            # 2.1
            elif self.FARdes is not None:
                # assuming incoming fluid is pure air (do not use for afterburner/reheat)
                self.Wf = self.FARdes * self.fs_in_q.mass
                self.Wfdes = self.Wf

            else:
                self.Wf = self.Wfdes
        else:
            # 2.1 : simplified, no OD control of Texit anymore inside TCombustor
            if self.control is not None:
                self.Wf = self.control.input_value
                if self.Wf < 0:
                    self.Wf = 0
            elif self.FAR is not None:
                self.Wf = self.FAR * self.fs_in_q.mass

        # this combustor has constant PR, no OD PR yet (use manual input in code here, or make PR map)
        self.PR = self.PRdes
        Sin = self.fs_in_q.gas_q.s
        Pin = self.fs_in_q.gas_q.P
        # Pout = self.gas_in.P*self.PRdes
        w_air = self.fs_in_q.gas_q.mass
        # h_gas_in_initial = self.gas_in.gas_q.enthalpy_mass
        H_in_initial = self.fs_in_q.H_total

        if (self.FuelComposition == '') or (self.FuelComposition == None):
            # fuel mole mass for the virtual fuel based on the specified H/C and O/C ratios (normalized to 1 mole of C)
            CHyOzMoleMass = self.C_atom_weight + self.H_atom_weight * self.HCratio + self.O_atom_weight * self.OCratio

        # 2.1
        # if (self.control is not None) and (self.control.OD_controlled_parameter_name is None) and  (self.Texit is not None): # calc Wf from Texit
        if Mode == 'DP':
            if  (self.Texit is not None):
                # initial guess for Wf
                Wf0 = self.Wfdes  # if Texit specified, Wfdes is initial guess
                self.Wf0_OD = None

                def equation(Wfiter):
                    # 1.6.0.5
                    # self.Wf=Wfiter[0]
                    self.Wf=float(Wfiter)
                    return CalcEndConditions(PointTime, Mode) - self.Texit
                solution = root_scalar(equation,

                                        method = 'secant',
                                        x0 = Wf0,  # Wf0 is guessed Wfdes here
                                        x1 = 1.02 * Wf0,
                                    xtol = 1e-6,
                                    maxiter = 100
                                    )
                if solution.converged:
                    self.Wf = solution.root
                    self.Wfdes = self.Wf
                else:
                    print(f"Wf for Combustor DP Texit value of {self.Texit:.0f} not found")
            else:
                CalcEndConditions(PointTime, Mode) # just calculate using self.Wf (= self.Wfdes)

        else: # OD off-design
            # if for off-design T4 input is needed: just do it using a TControl for T4
            # so the old method of version 2.0 is abandoned here
            CalcEndConditions(PointTime, Mode) # just calculate using self.Wf

        #  add fuel to system level total fuel flow
        self.system.WF = self.system.WF + self.Wf

        self.Add_Q_to_fs_out()

        return self.fs_out

    def PrintPerformance(self, Mode, PointTime):
        super().PrintPerformance(Mode, PointTime)
        print(f"\tFuel flow                 : {self.Wf:.4f} kg/s")
        print(f"\tCombustion End Temperature: {self.fs_out.T:.2f} K")

    # 2.0.0.0
    def get_outputs(self):
        out = super().get_outputs()
        out["Wf_"+self.name] = self.Wf
        return out
