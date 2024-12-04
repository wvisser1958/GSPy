import numpy as np
import cantera as ct
import f_global as fg
import f_system as fsys
from f_BaseComponent import TComponent as component

class TControl(component):
    def Run(self, Mode, PointTime, GasIn: ct.Quantity) -> ct.Quantity:    
        if Mode == 'DP':
            # in case of DP control
            self.Wfdes = 0.38
            self.Wf = self.Wfdes
        else:
            self.Wf = self.Wfdes - PointTime * (self.Wfdes-0.08)/40    
            # self.Wf = 0.11

    def GetOutputTableColumnNames(self):
        return super().GetOutputTableColumnNames() + ["Wf_"+self.name]
         
    def AddOutputToTable(self, Mode, rownr):
        fsys.OutputTable.loc[rownr, "Wf_"+self.name] = self.Wf        