import numpy as np
import cantera as ct
import f_global as fg
from f_gaspath import TGaspath as gaspath

class TInlet(gaspath):
    def __init__(self, name, MapFileName, Wdes, PRdes):    # Constructor of the class
        super().__init__(name, MapFileName)    
        self.Wdes = Wdes
        self.PRdes = PRdes        

    def Run(self, Mode, PointTime, GasIn: ct.Quantity, Ambient) -> ct.Quantity:    
        super().Run(Mode, PointTime, GasIn, Ambient)
        if Mode == 'DP':
            self.GasIn.TP = GasIn.T, GasIn.P
            self.GasIn.mass = self.Wdes                     
            self.GasOut.TP = GasIn.T, GasIn.P * self.PRdes  
            self.GasOut.mass = self.GasIn.mass
            fg.RD = self.GasIn.mass * Ambient.V
            self.wcdes = self.GasIn.mass * fg.GetFlowCorrectionFactor(self.GasIn)
            self.wc = self.wcdes

            # add state for corrected inlet flow wc
            # question: why corrected? : more stable... state staying closer to 1 at high altitude
            fg.states = np.append(fg.states, 1)
            self.istate_wc = fg.states.size-1
            pass
        else:
            self.wc = fg.states[self.istate_wc] * self.wcdes
            self.GasIn.TP = GasIn.T, GasIn.P
            self.GasIn.mass = self.wc / fg.GetFlowCorrectionFactor(self.GasIn)                     
            self.GasOut.TP = GasIn.T, GasIn.P * self.PRdes  
            self.GasOut.mass = self.GasIn.mass
            pass    
        return self.GasOut