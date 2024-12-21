import numpy as np
import cantera as ct
import f_global as fg
import f_system as fsys
from f_gaspath import TGaspath as gaspath

class TInlet(gaspath):
    def __init__(self, name, MapFileName, stationin, stationout, Wdes, PRdes):    # Constructor of the class
        super().__init__(name, MapFileName, stationin, stationout)    
        self.Wdes = Wdes
        self.PRdes = PRdes        

    def Run(self, Mode, PointTime):       
        # self.GasIn = ct.Quantity(fsys.gaspath_conditions[self.stationin].phase, mass = self.Wdes) 
        if Mode == 'DP':
            fsys.gaspath_conditions[self.stationin].mass = self.Wdes
        super().Run(Mode, PointTime)
        self.GasIn.TP = self.GasIn.T, self.GasIn.P
        if Mode == 'DP':
            self.GasIn.mass = self.Wdes                     
            self.wcdes = self.GasIn.mass * fg.GetFlowCorrectionFactor(self.GasIn)
            self.wc = self.wcdes
            self.PR = self.PRdes  

            # add state for corrected inlet flow wc
            # question: why corrected? : more stable... state staying closer to 1 at high altitude
            fsys.states = np.append(fsys.states, 1)
            self.istate_wc = fsys.states.size-1           
        else:
            self.wc = fsys.states[self.istate_wc] * self.wcdes
            self.GasIn.mass = self.wc / fg.GetFlowCorrectionFactor(self.GasIn)                     
            self.GasOut.TP = self.GasIn.T, self.GasIn.P * self.PRdes  
            # this inlet has constant PR, no OD PR yet (use manual input in code here, or make PR, Ram recovery map)
            self.PR = self.PRdes  

        self.GasOut.TP = self.GasIn.T, self.GasIn.P * self.PR              
        self.GasOut.mass = self.GasIn.mass            
        self.RD = self.GasIn.mass * fsys.Ambient.V    
        # add ram drag to system level ram drag (note that multiple inlets may exist)
        fsys.RD = fsys.RD + self.RD        
        return self.GasOut