import numpy as np
import cantera as ct
import aerocalc as ac     # !!!! install with "pip install aero-calc", see https://www.kilohotel.com/python/aerocalc/html/ 
# from aerocalc3 import std_atm as ac
from f_BaseComponent import TComponent as component
import f_global as fg 

class TAmbient(component):
    def __init__(self, name, altitude, mach, dTs, Ps0, Ts0):    # Constructor of the class
        super().__init__(name, '')    
        self.SetConditions(altitude, mach, dTs, Ps0, Ts0)

    def SetConditions(self, altitude, Mach, dTs, Ps0, Ts0):
        self.altitude = altitude 
        self.Macha = Mach
        self.dTs = dTs
        self.Pa = Ps0      # if None then this will override value from standard atmosphere Alt, Machm dTs
        self.Ta = Ts0      # if None then this will override value from standard atmosphere Alt, Machm dTs

    def Run(self, Mode, PointTime, GasIn: ct.Quantity) -> ct.Quantity:  
        if Mode == 'DP':
            self.SetConditions( 0, 0, 0, None, None)   
        else:
            # add code to schedule condition as function of PointTime if desired        
            self.SetConditions( 0, 0, 0, None, None)   

        if self.Ta == None:
            # Ts0 not defined, use standard atmosphere
            self.Ta = ac.std_atm.alt2temp(self.altitude, alt_units='m', temp_units='K')
            # for standard atmosphere, use dTs if defined
            if self.dTs != None:
                self.Ta = self.Ta + self.dTs
        if self.Pa == None:            
            # Ps0 not defined, used standard atmosphere
            self.Pa = ac.std_atm.alt2press(self.altitude, alt_units='m', press_units='pa')
            # for test problem with aerocalc3 on iteration at Wf = 0.11:
                # self.Ps0 = 101325
                # self.Ps0 = 101324.891894  

        self.Tta = self.Ta * ( 1 + 0.2 * self.Macha**2)
        self.Pta = self.Pa * ((self.Tta/self.Ta)**3.5)
        # set values in the GasIn object conditions
        GasIn.TPY = self.Tta, self.Pta, fg.s_air_composition_mass
        self.V = self.Macha * ac.std_atm.temp2speed_of_sound(self.Ta, speed_units = 'm/s', temp_units = 'K')
    
    def GetOutputTableColumns(self):
        return super().GetOutputTableColumns() + ["Ta", "Pa", "Tta", "Pta", "Macha"]
         
    def AddOutputToTable(self, Mode, rownr):
        fg.OutputTable.loc[rownr, "Ta"] = self.Ta
        fg.OutputTable.loc[rownr, "Pa"] = self.Pa
        fg.OutputTable.loc[rownr, "Tta"] = self.Tta
        fg.OutputTable.loc[rownr, "Pta"] = self.Pta
        fg.OutputTable.loc[rownr, "Macha"] = self.Macha