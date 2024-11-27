import numpy as np
import cantera as ct
import f_utils as fu
from scipy.optimize import root_scalar
# from scipy.optimize import root
from f_gaspath import TGaspath as gaspath
import f_global as fg

class TExhaust(gaspath):
    def __init__(self, name, MapFileName, stationin, stationout, CXdes, CVdes, CDdes):    # Constructor of the class
        super().__init__(name, MapFileName, stationin, stationout)    
        self.CXdes = CXdes
        self.CVdes = CVdes    
        self.CDdes = CDdes
    
    def Run(self, Mode, PointTime, GasIn: ct.Quantity, Ambient) -> ct.Quantity:    
        super().Run(Mode, PointTime, GasIn, Ambient)
        Sin = GasIn.entropy_mass
        Hin = GasIn.enthalpy_mass
        Pin = GasIn.P
        Pout = Ambient.Ps0
        if Mode == 'DP':                        
            Visentropic, Tisout = fu.calculate_exit_velocity(self.GasOut.phase, Pin/Pout)
            self.GasOut.TP = Tisout, Pout
            self.Mthroat = Visentropic / self.GasOut.phase.sound_speed 
            if self.Mthroat > 1:
                # Function to find the pressure for Mach 1
                def mach_number_difference(exit_pressure):
                    self.GasOut.SP = Sin, exit_pressure  # Set state at the given pressure
                    local_speed_of_sound = self.GasOut.sound_speed
                    velocity = (2 * (Hin - self.GasOut.enthalpy_mass))**0.5
                    mach_number = velocity / local_speed_of_sound
                    return mach_number - 1.0  # We want Mach number to be exactly 1
                # Use a numerical solver to find the exit pressure where Mach = 1
                rootresult = root_scalar(mach_number_difference, bracket=[0.1*Pout, Pin], method='brentq')
                self.Pthroat = rootresult.root
                self.Vthroat = self.GasOut.phase.sound_speed
            else:
                self.Pthroat = Pout
                self.Vthroat = Visentropic

            # exit flow error
            fg.errors = np.append(fg.errors, 0)
            self.ierror_w = fg.errors.size - 1 
            self.Athroat_des = self.GasOut.mass / self.GasOut.phase.density / self.Vthroat
            self.FG = self.GasOut.mass * self.Vthroat + self.Athroat_des*(self.Pthroat-Pout) 
            fg.FN = self.FG - fg.RD 
        else:
            self.Pthroat, self.Tthroat, self.Vthroat, massflow = fu.calculate_expansion_to_A(self.GasIn.phase, Pin/Pout, self.Athroat_des)
            self.GasOut.TP = self.Tthroat, self.Pthroat
            self.FG = self.GasOut.mass * self.Vthroat + self.Athroat_des*(self.Pthroat-Pout) 
            fg.FN = self.FG - fg.RD             
            fg.errors[self.ierror_w] = (self.GasIn.mass - massflow) / self.GasInDes.mass              
            pass    
        return self.GasOut
    
    def PrintPerformance(self, Mode, PointTime):
        super().PrintPerformance(Mode, PointTime)
        # Print and return the results
        print(f"\tExit velocity: {self.Vthroat:.2f} m/s")
        if Mode == 'DP':    
            print(f"\tThroat area (DP): {self.Athroat_des:.4f} m2")
        print(f"\tExit static temperature: {self.GasOut.T:.1f} K")
        print(f"\tThroat static pressure: {self.Pthroat:.0f} Pa")
        print(f"\tExit static pressure: {self.GasOut.P:.0f} Pa")
        print(f"\tGross thrust: {self.FG:.2f} N")