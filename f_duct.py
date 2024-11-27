import numpy as np
import cantera as ct
from f_gaspath import TGaspath as gaspath

class TDuct(gaspath):
    def __init__(self, name, MapFileName, stationin, stationout, PRdes):    # Constructor of the class
        super().__init__(name, MapFileName, stationin, stationout)    
        self.PRdes = PRdes
        
    def Run(self, Mode, PointTime, GasIn: ct.Quantity, Ambient) -> ct.Quantity:  
        super().Run(Mode, PointTime, GasIn, Ambient)
        if Mode == 'DP':
            GasIn.TP = GasIn.T, GasIn.P*self.PRdes
        else:
            pass    
        return self.GasOut   