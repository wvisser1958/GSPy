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

    def SetConditions(self, altitude, mach, dTs, Ps0, Ts0):
        self.altitude = altitude 
        self.mach = mach
        self.dTs = dTs
        self.Ps0 = Ps0      # if None then this will override value from standard atmosphere Alt, Machm dTs
        self.Ts0 = Ts0      # if None then this will override value from standard atmosphere Alt, Machm dTs

    def Run(self, Mode, PointTime, GasIn: ct.Quantity) -> ct.Quantity:  
        if Mode == 'DP':
            self.SetConditions( 0, 0, 0, None, None)   
        else:
            # add code to schedule condition as function of PointTime if desired        
            self.SetConditions( 0, 0, 0, None, None)   

        if self.Ts0 == None:
            # Ts0 not defined, use standard atmosphere
            self.Ts0 = ac.std_atm.alt2temp(self.altitude, alt_units='m', temp_units='K')
            # for standard atmosphere, use dTs if defined
            if self.dTs != None:
                self.Ts0 = self.Ts0 + self.dTs
        if self.Ps0 == None:
            # Ps0 not defined, used standard atmosphere
            self.Ps0 = ac.std_atm.alt2press(self.altitude, alt_units='m', press_units='pa')
        self.Tt0 = self.Ts0 * ( 1 + 0.2 * self.mach**2)
        self.Pt0 = self.Ps0 * ((self.Tt0/self.Ts0)**3.5)
        # set values in the GasIn object conditions
        GasIn.TPY = self.Tt0, self.Pt0, fg.s_air_composition_mass
        self.V = self.mach * ac.std_atm.temp2speed_of_sound(self.Ts0, speed_units = 'm/s', temp_units = 'K')
        pass