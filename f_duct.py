import numpy as np
import cantera as ct
import f_global as fg
from f_gaspath import TGaspath as gaspath

class TDuct(gaspath):
    def __init__(self, name, MapFileName, stationin, stationout, PRdes):    # Constructor of the class
        super().__init__(name, MapFileName, stationin, stationout)    
        self.PRdes = PRdes
        
    def Run(self, Mode, PointTime, GasIn: ct.Quantity) -> ct.Quantity:  
        super().Run(Mode, PointTime, GasIn)
        if Mode == 'DP':
            self.PR = self.PRdes
        else:
            # this duct has constant PR, no OD PR yet (use manual input in code here, or make PR map)
            self.PR = self.PRdes
        self.GasOut.TP = GasIn.T, GasIn.P*self.PR
        # calculate parameters for output
        self.Wc = self.GasIn.mass * fg.GetFlowCorrectionFactor(GasIn)
        return self.GasOut   