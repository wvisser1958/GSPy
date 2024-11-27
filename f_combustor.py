import numpy as np
import cantera as ct
import f_global as fg
from f_gaspath import TGaspath as gaspath

class TCombustor(gaspath):        
    def __init__(self, name, MapFileName, stationin, stationout, Control, Wfdes, Texitdes, PRdes, Etades):    # Constructor of the class
        super().__init__(name, MapFileName, stationin, stationout)    
        self.Wfdes = Wfdes
        self.Texitdes = Texitdes
        self.PRdes = PRdes
        self.Etades = Etades
        self.Control = Control
    
    def Run(self, Mode, PointTime, GasIn: ct.Quantity, Ambient) -> ct.Quantity:    
        super().Run(Mode, PointTime, GasIn, Ambient)
        if Mode == 'DP':
            self.Wf = self.Wfdes
        else:
            self.Wf = self.Control.Wf
        T_fuel = 288.15
        Sin = GasIn.s
        Pin = GasIn.P
        Pout = GasIn.P*self.PRdes

        # Given parameters for the virtual fuel
        LHV_kJ_kg = 43031  # Lower Heating Value in kJ/kg
        average_molar_mass_fuel = 167.31102  # Average molar mass in g/mol
        HC_ratio = 1.9167  # H/C ratio for the virtual fuel
        CHyOzMoleMass = fg.C_atom_weight + fg.H_atom_weight * HC_ratio # virtual fuel molecule with singe C atom

        w_air = self.GasIn.mass

        h_air_initial = GasIn.enthalpy_mass

        # Convert LHV from kJ/kg to J/mol
        LHV_J_mol = LHV_kJ_kg * 1000 * (average_molar_mass_fuel / 1000)

        # calculate compostion of combustion products mixed with excess air
        O2_exit_mass = w_air * fg.air_O2_fraction_mass - self.Wf/CHyOzMoleMass * (1+HC_ratio/4) * fg.O2_molar_mass 
        CO2_exit_mass = fg.CO2_molar_mass * self.Wf/CHyOzMoleMass + w_air*fg.air_CO2_fraction_mass   
        H2O_exit_mass = fg.H2O_molar_mass * self.Wf/CHyOzMoleMass * HC_ratio/2
        Ar_exit_mass = w_air * fg.air_Ar_fraction_mass
        N2_exit_mass = w_air * fg.air_N2_fraction_mass

        product_composition_mass = f'O2:{O2_exit_mass}, CO2:{CO2_exit_mass}, H2O:{H2O_exit_mass}, AR:{Ar_exit_mass}, N2:{N2_exit_mass}'
        self.GasOut.TPY = fg.T_standard_ref, fg.P_standard_ref, product_composition_mass

        h_prod_ref = self.GasOut.enthalpy_mass # get H in J/kg

        # now, from the equation (conservation of energy "in = out"):
        # w_fuel * LHV_kJ_kg*1000 + w_air * (h_air_initial - fg.h_air_ref)  =   (w_air + w_fuel) * (h_prod_final - h_prod_ref)
        h_prod_final = (self.Wf * LHV_kJ_kg * 1000 + w_air * (h_air_initial-fg.h_air_ref)) / (w_air + self.Wf) + h_prod_ref

        self.GasOut.HP = h_prod_final, Pout
        self.GasOut.mass = self.GasIn.mass + self.Wf
       
        return self.GasOut      
    
    def PrintPerformance(self, Mode, PointTime):
        super().PrintPerformance(Mode, PointTime)
        print(f"\tFuel flow                 : {self.Wf:.4f} kg/s")
        print(f"\tCombustion End Temperature: {self.GasOut.T:.2f} K")
