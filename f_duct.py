import numpy as np
import cantera as ct
import f_global as fg
from f_gaspath import TGaspath

class TDuct(TGaspath):
    def __init__(self, name, MapFileName, stationin, stationout, PRdes):    # Constructor of the class
        super().__init__(name, MapFileName, stationin, stationout)
        self.PRdes = PRdes

    def Run(self, Mode, PointTime):
        super().Run(Mode, PointTime)
        if Mode == 'DP':
            self.PR = self.PRdes
        else:
            # this duct has constant PR, no OD PR yet (use manual input in code here, or make PR map)
            self.PR = self.PRdes
        self.GasOut.TP = self.GasIn.T, self.GasIn.P*self.PR
        # calculate parameters for output
        self.Wc = self.GasIn.mass * fg.GetFlowCorrectionFactor(self.GasIn)
        return self.GasOut