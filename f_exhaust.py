import numpy as np
import cantera as ct
import f_utils as fu
from scipy.optimize import root_scalar
# from scipy.optimize import root
from f_gaspath import TGaspath as gaspath
import f_global as fg

class TExhaust(gaspath):
    def __init__(self, name, MapFileName, stationin, stationthroat, stationout, CXdes, CVdes, CDdes):    # Constructor of the class
        super().__init__(name, MapFileName, stationin, stationout) 
        self.stationthroat = stationthroat
        self.CXdes = CXdes
        self.CVdes = CVdes    
        self.CDdes = CDdes
    
    def Run(self, Mode, PointTime, GasIn: ct.Quantity, Ambient) -> ct.Quantity:    
        super().Run(Mode, PointTime, GasIn, Ambient)
        # add nozzle throat station
        self.GasThroat = ct.Quantity(GasIn.phase, mass = GasIn.mass) 
        Sin = GasIn.entropy_mass
        Hin = GasIn.enthalpy_mass
        Pin = GasIn.P
        Pout = Ambient.Pa
        self.PR = Pin/Pout
        if Mode == 'DP':                                        
            Vthroat_is, self.Tthroat = fu.calculate_exit_velocity(self.GasOut.phase, self.PR)
            # try full expansion to Pout
            self.GasThroat.TP = self.Tthroat, Pout
            self.Mthroat = Vthroat_is / self.GasThroat.phase.sound_speed 
            if self.Mthroat > 1: # cannot be, correct for Mthroat = 1
                self.Mthroat = 1
                # Function to find the pressure for Mach 1
                def mach_number_difference(exit_pressure):
                    self.GasThroat.SP = Sin, exit_pressure  # Set state at the given pressure
                    local_speed_of_sound = self.GasThroat.sound_speed
                    velocity = (2 * (Hin - self.GasThroat.enthalpy_mass))**0.5
                    mach_number = velocity / local_speed_of_sound
                    return mach_number - 1.0  # We want Mach number to be exactly 1
                # Use a numerical solver to find the exit pressure where Mach = 1
                rootresult = root_scalar(mach_number_difference, bracket=[0.1*Pout, Pin], method='brentq')
                self.Pthroat = rootresult.root
                self.Vthroat = self.GasThroat.phase.sound_speed * self.CVdes                
            else:
                self.Pthroat = Pout
                self.Vthroat = Vthroat_is * self.CVdes
            self.Tthroat = self.GasThroat.T
            # exit flow error
            fg.errors = np.append(fg.errors, 0)
            self.ierror_w = fg.errors.size - 1 
            self.Athroat_des = self.GasThroat.mass / self.GasThroat.phase.density / self.Vthroat
            self.Athroat = self.Athroat_des
        else:
            self.Athroat = self.Athroat_des # fixed nozzle are still here
            self.Pthroat, self.Tthroat, Vthroat_is, massflow = fu.calculate_expansion_to_A(self.GasIn.phase, Pin/Pout, self.Athroat)
            self.GasThroat.TP = self.Tthroat, self.Pthroat
            self.Vthroat = Vthroat_is * self.CVdes
            fg.errors[self.ierror_w] = (self.GasIn.mass - massflow) / self.GasInDes.mass   
            self.Mthroat = self.Vthroat / self.GasThroat.phase.sound_speed           
        # calculate parameters for output
        self.GasOut.TP = self.Tthroat, Pout # assume no further expansion
        self.Wc = self.GasIn.mass * fg.GetFlowCorrectionFactor(GasIn)            
        self.FG = self.CXdes * (self.GasOut.mass * self.Vthroat + self.Athroat*(self.Pthroat-Pout)) 
        fg.FN = self.FG - fg.RD     
        self.Athroat_geom = self.Athroat / self.CDdes
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

    def GetOutputTableColumns(self):
        return super().GetOutputTableColumns()                                                              \
            + [f"T{self.stationthroat}", f"P{self.stationthroat}", f"V{self.stationthroat}", f"Mach{self.stationthroat}", \
               f"T{self.stationout}", f"P{self.stationout}",                                                \
               "Athroat_"+self.name, "Athroat_geom_" + self.name, "FG_" + self.name]
         
    def AddOutputToTable(self, Mode, rownr):
        # fg.OutputTable.loc[rownr, columnname] = getattr(self, columnname) 
        super().AddOutputToTable(Mode, rownr)
        fg.OutputTable.loc[rownr, f"T{self.stationthroat}"]  = self.Tthroat
        fg.OutputTable.loc[rownr, f"P{self.stationthroat}"]  = self.Pthroat 
        fg.OutputTable.loc[rownr, f"V{self.stationthroat}"]  = self.Vthroat
        fg.OutputTable.loc[rownr, f"Mach{self.stationthroat}"]  = self.Mthroat
        fg.OutputTable.loc[rownr, f"T{self.stationout}"]  = self.GasOut.T 
        fg.OutputTable.loc[rownr, f"P{self.stationout}"]  = self.GasOut.P 
        fg.OutputTable.loc[rownr, "Athroat_"+self.name]  = self.Athroat
        fg.OutputTable.loc[rownr, "Athroat_geom_"+self.name]  = self.Athroat_geom
        fg.OutputTable.loc[rownr, "FG_"+self.name]  = self.FG
        