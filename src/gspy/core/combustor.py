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

import numpy as np
from scipy.optimize import root, root_scalar
import cantera as ct
import f_global as fg
import f_system as fsys
from f_gaspath import TGaspath
import f_utils as fu

class TCombustor(TGaspath):
    def __init__(self, name, MapFileName, ControlComponent, stationin, stationout, Wfdes, Texitdes, PRdes, Etades,
                 Tfueldes, LHVdes, HCratiodes, OCratiodes, FuelCompositiondes, A):
        super().__init__(name, MapFileName, ControlComponent, stationin, stationout)
        self.Wfdes = Wfdes
        self.Wf = Wfdes
        # Texitdes: set as None, use None or not None to determine input type : Wf or Texit
        self.Texitdes = Texitdes
        self.Texit = None
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

        print(f"LHV of CH4 (H2O vapor): {LHV:.2f} kJ/kg")

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
        q_in, q_out = self.GasIn, self.GasOut

        # velocities from continuity (A_in = A_out = A), mass flow mass = out mass flow for both in and out
        # because also the fuel flow must be accelerated during combustion
        V_in  = float(q_out.mass) / (q_in.density  * float(A))
        V_out = float(q_out.mass) / (q_out.density * float(A))

        p0_in  = fu.stagnation_pressure_from_quantity(q_in,  V_in)   # same helper as before
        p0_out = fu.stagnation_pressure_from_quantity(q_out, V_out)

        #  p0_out is now the "virtual" exit stagnation pressure as if there is no fundamental pressure loss,
        #  the loss is the difference between p0_out en p0_in, so

        # loss = 1.0 - (p0_out / p0_in)
        return p0_in / p0_out

    #    ********** under development ***************
    # def apply_rayleigh_and_fund_loss(self, A, mdot, iterate=False, iters=3):
    #     q1, q2 = self.GasIn, self.GasOut   # q2 after your Etades equilibrium

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
    # def GasOut_total_pressure_from_static(self, T_static, P_static, T_total):
    #     """
    #     Compute total (stagnation) pressure p0 given static T,P and total temperature T0.
    #     Uses isentropic constraint (s = const) for a real mixture.
    #     """
    #     # Make a working copy
    #     # self.GasOut.TP = T_static, P_static
    #     # gas = self.GasOut.phase.clone()
    #     gas = ct.Solution(self.GasOut.phase.source)
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
    #         q_in = self.GasIn
    #         q_out = self.GasOut
    #         w_out = self.GasOut.mass
    #         Ts_in, Ps_in, V_in, M_in = fu.static_from_total(q_in, A)
    #         Fin = Ps_in *A * (1+self.GasIn.phase.cp/self.GasIn.phase.cv * M_in * M_in)
    #         # // Force at exit station: (account for lower Cout.Pt due to normal pressure loss
    #         # //                         already calculated
    #         # //                         without normal pressure loss, of course Fout=Fin)
    #         Fout = Fin - A * (q_in.P- q_out.P)
    #         # starting value for M_out
    #         M_out = M_in
    #         Ts_out = Ts_in
    #         Ps_out = None
    #         Pt_out_no_loss = self.GasOut.P
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

    #         self.GasOut.P = self.GasOut_total_pressure_from_static(Ts_out, Ps_out, self.GasOut.T)
    #         return (Pt_out_no_loss - self.GasOut.P) / Pt_out_no_loss
    #     except Exception as e:
    #         print(f"Exception error {e} in {self.name} Fund. Press. Loss calculation, Hint: increase (burner) duct cross area.")

    def Run(self, Mode, PointTime):
        def CalcEndConditions(PointTime):
            # self.GetLHV()
            if (self.FuelComposition == '') or (self.FuelComposition == None):  # fuel specification based on LHV, HC and OC mole ratio
                # combustion product mass fractions, assuming complete combustion and air/fuel equivalence ratio >= 1
                O2_exit_mass = w_air * fg.air_O2_fraction_mass + self.Wf/CHyOzMoleMass * (self.OCratio/2 - 1 - self.HCratio/4) * fg.O2_molar_mass
                CO2_exit_mass = fg.CO2_molar_mass * self.Wf/CHyOzMoleMass + w_air*fg.air_CO2_fraction_mass
                H2O_exit_mass = fg.H2O_molar_mass * self.Wf/CHyOzMoleMass * self.HCratio/2
                Ar_exit_mass = w_air * fg.air_Ar_fraction_mass
                N2_exit_mass = w_air * fg.air_N2_fraction_mass
                # compose the composition string
                product_composition_mass = f'O2:{O2_exit_mass}, CO2:{CO2_exit_mass}, H2O:{H2O_exit_mass}, AR:{Ar_exit_mass}, N2:{N2_exit_mass}'

                # define enthalpy of combustion products mixture at Pref and Tref of
                self.GasOut.TPY = fg.T_standard_ref, fg.P_standard_ref, product_composition_mass
                h_prod_ref = self.GasOut.enthalpy_mass # get H in J/kg

                # now, calculate the final enthalpy of the products based on given LHV:
                # from equation for conservation of energy ()"in = out"):
                # w_fuel * LHV_kJ_kg*1000 + w_air * (h_air_initial - fg.h_air_ref)  =   (w_air + w_fuel) * (h_prod_final - h_prod_ref)
                # v1.3  bug fix: Etades was not accounted for
                # h_prod_final = (self.Wf * self.LHV * 1000 + w_air * (h_air_initial-fg.h_air_ref)) / (w_air + self.Wf) + h_prod_ref
                h_prod_final = (self.Wf * self.LHV * 1000 * self.Etades + w_air * (h_air_initial-fg.h_air_ref)) / (w_air + self.Wf) + h_prod_ref

                # now set exit GasOut H to h_prod_final, this will calculate GasOut.T
                self.GasOut.HP = h_prod_final, Pin

                # make sure fuel mass flow added to the inlet flow:
                self.GasOut.mass = self.GasIn.mass + self.Wf

                # v 1.2 go to chemical equilibrium
                self.GasOut.equilibrate('HP')
            else:                  # fuel specification based on FuelComposition and Tfuel
                #  1.4 test if fuel exists (DP may be virtual flow, and OD composition specified, so....)
                # if Mode == 'DP':
                if self.fuel == None:
                    # create separate fuel quantity for mixing with GasIn
                    self.fuel = ct.Quantity(fg.gas)
                self.fuel.mass = self.Wf
                if self.Tfuel == None:      # assume Tfuel equal to T of air in
                    Tfuelin = self.GasIn.T
                else:                       # use user specified Tfuel
                    Tfuelin = self.Tfuel
                # v1.2 set P fuel to Pout, otherwise (using GasIn.P, which is before the pressure loss)
                #  the fuel pressure will increase the combustor pressure again with the TPY assignment
                # self.fuel.TPY = Tfuelin, self.GasIn.P, self.FuelComposition
                self.fuel.TPY = Tfuelin, Pin, self.FuelComposition
                # fuel.TPY = self.GasIn.T, self.GasIn.P, self.FuelComposition
                self.GasOut = self.GasIn + self.fuel

                # 1.3
                if self.Etades < 1.000:
                    # calculate enthalpy loss
                    # 1) Enthalpy of mixed, *unreacted* stream
                    h_in = self.GasOut.enthalpy_mass
                    # Save mixed, unreacted state
                    GasOut_phase_saved = self.GasOut.phase.state               # stores T, P, composition, etc.

                    # 3) Target enthalpy that includes heat loss via Etades
                    self.GasOut.equilibrate("TP")                   # equilibrium at fixed T (mix temp) & P
                    dh_rxn_T = self.GasOut.enthalpy_mass - h_in     # this reflects reaction enthalpy at the mix T

                    # Apply efficiency (heat loss): scale the enthalpy release
                    h_target = h_in + (1-self.Etades) * dh_rxn_T

                    # Restore original mixed state
                    self.GasOut.phase.state = GasOut_phase_saved

                    # 4) Set target (H,P) and equilibrate to get final state with losses
                    self.GasOut.HP = h_target, Pin
                else:
                    # v1.2 reimpose pressure Pout to GasOut
                    self.GasOut.HP = self.GasOut.enthalpy_mass, Pin

                self.GasOut.equilibrate("HP")

            # pressure loss
            if (self.A == None) or (self.A ==0):
                PRfund = 1
            else:
                # PRfund = 1- self.fundamental_pressure_loss_rayleigh(self.A, self.GasOut.mass)
                # PRfund = 1- self.apply_rayleigh_and_fund_loss(self.A, self.GasOut.mass)
                # PRfund = self.CalcFundamentalDp(self.A)
                # provisional:
                    # fundamental_pressure_loss_rayleigh is under test ************
                    # may want to have option  to specify exit Mach instead and calculate A
                PRfund = self.fundamental_pressure_loss_rayleigh(self.A)
            Pout = Pin * PRfund * self.PRdes
            self.GasOut.HP = self.GasOut.enthalpy_mass, Pout

            # we redefined GasOut, so we must reassing self.GasOut to fsys.gaspath_conditions[self.stationout]
            fsys.gaspath_conditions[self.stationout] = self.GasOut
            return self.GasOut.T

        super().Run(Mode, PointTime)

        # self.GetLHV()

        if Mode == 'DP':
            if self.Texitdes  != None: # calc Wf from Texit, use Wfdes as Wf first guess
                self.Texit = self.Texitdes  # now self.Wfdes is 1st guess for iteration to Text
            else:
                self.Wf = self.Wfdes
        else:
            # v1.3
            if self.Control != None:
                # 1.4
                # if self.Texit != None: # calc Wf from Texit
                if (self.Control.OD_controlledparname == None) and  (self.Texit != None): # calc Wf from Texit
                    self.Texit =  self.Control.Inputvalue
                else:
                    self.Wf = self.Control.Inputvalue
                    if self.Wf < 0:
                        self.Wf = 0
            #  else Wf or Texit determined from outside by Control SetAttr

        # this combustor has constant PR, no OD PR yet (use manual input in code here, or make PR map)
        self.PR = self.PRdes
        Sin = self.GasIn.s
        Pin = self.GasIn.P
        # Pout = self.GasIn.P*self.PRdes
        Pin = self.GasIn.P
        w_air = self.GasIn.mass
        h_air_initial = self.GasIn.enthalpy_mass

        # 1.4 use separate routine, for allowing change of fuel for OD simulation cases
        # # Given parameters for the virtual fuel
        # # virtual fuel molecule with singe C atom
        # self.Tfuel = self.Tfueldes
        # self.LHV = self.LHVdes          # Lower Heating Value in kJ/kg
        # self.HCratio = self.HCratiodes  # H/C ratio for the virtual fuel
        # self.OCratio = self.OCratiodes  # O/C ratio for the virtual fuel
        # self.FuelComposition = self.FuelCompositiondes

        if (self.FuelComposition == '') or (self.FuelComposition == None):
            CHyOzMoleMass = fg.C_atom_weight + fg.H_atom_weight * self.HCratio + fg.O_atom_weight * self.OCratio

        Wf0 = self.Wf
        #  1.4
        # if self.Texit != None:
        if (self.Control.OD_controlledparname == None) and  (self.Texit != None): # calc Wf from Texit
            #  calculate Wf for given Texit, using scipy root function
            def equation(Wfiter):
                self.Wf=Wfiter[0]
                return CalcEndConditions(PointTime) - self.Texit
            solution = root(equation, x0 = Wf0)
            if solution.success:
                self.Wf = solution.x[0]
            else:
                print(f"Wf for Combustor Texit value of {self.Texit:.0f} not found")
        else: # just calculate Texit from Wf
            CalcEndConditions(PointTime)

        #  add fuel to system level total fuel flow
        fsys.WF = fsys.WF + self.Wf

        return self.GasOut

    def PrintPerformance(self, Mode, PointTime):
        super().PrintPerformance(Mode, PointTime)
        print(f"\tFuel flow                 : {self.Wf:.4f} kg/s")
        print(f"\tCombustion End Temperature: {self.GasOut.T:.2f} K")

    #  1.1 WV
    def AddOutputToDict(self, Mode):
        super().AddOutputToDict(Mode)
        fsys.output_dict["Wf_"+self.name] = self.Wf
