import numpy as np
import cantera as ct
from f_BaseComponent import TComponent as component

class TControl(component):
    def Run(self, Mode, PointTime, GasIn: ct.Quantity, Ambient) -> ct.Quantity:    
        if Mode == 'DP':
            # in case of DP control
            self.Wfdes = 0.38
        else:
            self.Wf = self.Wfdes - PointTime * (self.Wfdes-0.08)/40    