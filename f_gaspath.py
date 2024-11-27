import numpy as np
import cantera as ct
from f_BaseComponent import TComponent as component
import f_global as fg

class TGaspath(component):        
    def __init__(self, name, MapFileName, stationin, stationout):    # Constructor of the class
        super().__init__(name, MapFileName)   
        self.stationin = stationin
        self.stationout = stationout
        # set design properties to None, if still None in PrintPerformance,
        # then not assigned anywhere so no need to Print/output.         
        self.GasIn = None
        self.GasOut = None
        self.Wcdes = None
        self.Wc = None
        self.PRdes = None
        self.PR = None
            
    def Run(self, Mode, PointTime, GasIn: ct.Quantity, Ambient) -> ct.Quantity:  
        self.GasIn = ct.Quantity(GasIn.phase, mass = GasIn.mass) 
        self.GasOut = ct.Quantity(GasIn.phase, mass = GasIn.mass) 
        if Mode == 'DP':
            self.GasInDes = ct.Quantity(GasIn.phase, mass = GasIn.mass) 
        return self.GasOut    
    
    def PrintPerformance(self, Mode, PointTime):
        super().PrintPerformance(Mode, PointTime)
        print(f"\tInlet conditions:")
        print(f"\t\tMass flow  : {self.GasIn.mass:.2f} kg/s")
        print(f"\t\tTemperature: {self.GasIn.T:.1f} K")
        print(f"\t\tPressure   : {self.GasIn.P:.0f} Pa")
        print(f"\tExit conditions:")
        print(f"\t\tMass flow  : {self.GasOut.mass:.2f} kg/s")
        if self.Wcdes != None:
            print(f"\t\tDP Corr.Mass flow  : {self.Wcdes:.2f} kg/s")
        if self.Wc != None:
            print(f"\t\tCorr.Mass flow  : {self.Wc:.2f} kg/s")
        print(f"\t\tTemperature: {self.GasOut.T:.1f} K")
        print(f"\t\tPressure   : {self.GasOut.P:.0f} Pa")
        if self.PR != None:
            print(f"\t\tPressure ratio  : {self.PR:.4f}")
        if self.PRdes != None:
            print(f"\t\tDP Pressure ratio  : {self.PRdes:.4f}")

    def GetOutputTableColumns(self):
        return [f"W{self.stationin}", f"Wc{self.stationin}", f"T{self.stationin}", f"P{self.stationin}", "PR_"+self.name]
         
    def AddOutputToTable(self, Mode, rownr):
        for columnname in self.GetOutputTableColumns():
            # fg.OutputTable.loc[rownr, columnname] = getattr(self, columnname) 
            fg.OutputTable.loc[rownr, f"W{self.stationin}"]  = self.GasIn.mass 
            fg.OutputTable.loc[rownr, f"Wc{self.stationin}"] = self.Wc 
            fg.OutputTable.loc[rownr, f"T{self.stationin}"]  = self.GasIn.T 
            fg.OutputTable.loc[rownr, f"P{self.stationin}"]  = self.GasIn.P 
            fg.OutputTable.loc[rownr, "PR_"+self.name] = self.PR 
          
            
