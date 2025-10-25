# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#    http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import numpy as np
from scipy.optimize import root
import cantera as ct
import f_global as fg
import f_system as fsys
from f_gaspath import TGaspath

class TCombustor(TGaspath):
    def __init__(self, name, MapFileName, ControlComponent, stationin, stationout, Wfdes, Texitdes, PRdes, Etades,
                 Tfueldes, LHVdes, HCratiodes, OCratiodes, FuelCompositiondes):
        super().__init__(name, MapFileName, ControlComponent, stationin, stationout)
        self.Wfdes = Wfdes
        self.Wf = Wfdes
        # Texitdes: set as None, use None or not None to determine input type : Wf or Texit
        self.Texitdes = Texitdes
        self.Texit = None
        self.PRdes = PRdes
        self.Etades = Etades
        self.Tfueldes = Tfueldes
        self.LHVdes = LHVdes
        self.HCratiodes = HCratiodes
        self.OCratiodes = OCratiodes
        # fuel composition string, e.g. 'NC12H26:1', or a mixture like 'NC12H26:5, C2H6:1'
        # with 'NC12H26:5, C2H6:1' mole ratio if 5:1 if TPX is used, mass ratio if TPY is used, see Cantera documentation
        self.FuelCompositiondes = FuelCompositiondes

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
                h_prod_final = (self.Wf * self.LHV * 1000 + w_air * (h_air_initial-fg.h_air_ref)) / (w_air + self.Wf) + h_prod_ref

                # now set exit GasOut H to h_prod_final, this will calculate GasOut.T
                self.GasOut.HP = h_prod_final, Pout

                # make sure fuel mass flow added to the inlet flow:
                self.GasOut.mass = self.GasIn.mass + self.Wf

                # v 1.2 go to chemical equilibrium
                self.GasOut.equilibrate('HP')
            else:                  # fuel specification based on FuelComposition and Tfuel
                if Mode == 'DP':
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
                self.fuel.TPY = Tfuelin, Pout, self.FuelComposition
                # fuel.TPY = self.GasIn.T, self.GasIn.P, self.FuelComposition
                self.GasOut = self.GasIn + self.fuel

                # v1.2
                self.GasOut.HP = self.GasOut.enthalpy_mass, Pout

                self.GasOut.equilibrate('HP')
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
            if self.Texit != None: # calc Wf from Texit
                self.Texit =  self.Control.Inputvalue
            else:
                self.Wf = self.Control.Inputvalue
                if self.Wf < 0:
                    self.Wf = 0

        # this combustor has constant PR, no OD PR yet (use manual input in code here, or make PR map)
        self.PR = self.PRdes
        Sin = self.GasIn.s
        Pin = self.GasIn.P
        Pout = self.GasIn.P*self.PRdes
        w_air = self.GasIn.mass
        h_air_initial = self.GasIn.enthalpy_mass

        # Given parameters for the virtual fuel
        # virtual fuel molecule with singe C atom
        self.Tfuel = self.Tfueldes
        self.LHV = self.LHVdes          # Lower Heating Value in kJ/kg
        self.HCratio = self.HCratiodes  # H/C ratio for the virtual fuel
        self.OCratio = self.OCratiodes  # O/C ratio for the virtual fuel
        self.FuelComposition = self.FuelCompositiondes
        if (self.FuelComposition == '') or (self.FuelComposition == None):
            CHyOzMoleMass = fg.C_atom_weight + fg.H_atom_weight * self.HCratio + fg.O_atom_weight * self.OCratio

        Wf0 = self.Wf
        if self.Texit != None:
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
