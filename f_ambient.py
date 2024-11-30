import numpy as np
import cantera as ct
import aerocalc as ac     # !!!! install with "pip install aero-calc", see https://www.kilohotel.com/python/aerocalc/html/ 
# from aerocalc3 import std_atm as ac
from f_BaseComponent import TComponent as component
import f_global as fg 
import f_system as fsys

class TAmbient(component):
    def __init__(self, name, Altitude, Macha, dTs, Psa, Tsa):    # Constructor of the class
        super().__init__(name, '')    
        self.SetConditions('DP', Altitude, Macha, dTs, Psa, Tsa)

    def SetConditions(self, Mode, Altitude, Macha, dTs, Psa, Tsa):
        if Mode == 'DP':
            self.Altitude_des = Altitude 
            self.Macha_des = Macha
            self.dTs_des = dTs
            self.Psa_des = Psa      # if None then this will override value from standard atmosphere Alt, Machm dTs
            self.Tsa_des = Tsa      # if None then this will override value from standard atmosphere Alt, Machm dTs
        else:            
            self.Altitude = Altitude 
            self.Macha = Macha
            self.dTs = dTs
            self.Psa = Psa      # if None then this will override value from standard atmosphere Alt, Machm dTs
            self.Tsa = Tsa      # if None then this will override value from standard atmosphere Alt, Machm dTs

    def Run(self, Mode, PointTime, GasIn: ct.Quantity) -> ct.Quantity:  
        if Mode == 'DP':  # alway reset de DP conditions
            self.Altitude = self.Altitude_des 
            self.Macha = self.Macha_des
            self.dTs = self.dTs_des
            self.Psa = self.Psa_des      # if None then this will override value from standard atmosphere Alt, Machm dTs
            self.Tsa = self.Tsa_des      # if None then this will override value from standard atmosphere Alt, Machm dTs

        if self.Tsa == None:
            # Tsa not defined, use standard atmosphere
            self.Tsa = ac.std_atm.alt2temp(self.Altitude, alt_units='m', temp_units='K')
            # for standard atmosphere, use dTs if defined
            if self.dTs != None:
                self.Tsa = self.Tsa + self.dTs
        if self.Psa == None:            
            # Ps0 not defined, used standard atmosphere
            self.Psa = ac.std_atm.alt2press(self.Altitude, alt_units='m', press_units='pa')
            # for test problem with aerocalc3 on iteration at Wf = 0.11:
                # self.Ps0 = 101325
                # self.Ps0 = 101324.891894  

        self.Tta = self.Tsa * ( 1 + 0.2 * self.Macha**2)
        self.Pta = self.Psa * ((self.Tta/self.Tsa)**3.5)
        # set values in the GasIn object conditions
        GasIn.TPY = self.Tta, self.Pta, fg.s_air_composition_mass
        self.V = self.Macha * ac.std_atm.temp2speed_of_sound(self.Tsa, speed_units = 'm/s', temp_units = 'K')
    
    def GetOutputTableColumnNames(self):
        return super().GetOutputTableColumnNames() + ["Tsa", "Psa", "Tta", "Pta", "Macha"]
         
    def AddOutputToTable(self, Mode, rownr):
        fsys.OutputTable.loc[rownr, "Tsa"] = self.Tsa
        fsys.OutputTable.loc[rownr, "Psa"] = self.Psa
        fsys.OutputTable.loc[rownr, "Tta"] = self.Tta
        fsys.OutputTable.loc[rownr, "Pta"] = self.Pta
        fsys.OutputTable.loc[rownr, "Macha"] = self.Macha