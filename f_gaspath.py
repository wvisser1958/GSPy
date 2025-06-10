import numpy as np
import cantera as ct
from f_base_component import TComponent
import f_global as fg
import f_system as fsys

class TGaspath(TComponent):
    def __init__(self, name, MapFileName, stationin, stationout):    # Constructor of the class
        super().__init__(name, MapFileName)
        self.stationin = stationin
        self.stationout = stationout
        # set design properties to None, if still None in PrintPerformance,
        # then not assigned anywhere so no need to Print/output.
        self.GasIn = None
        self.GasOut = None
        self.Wc = None
        self.PRdes = 1
        self.PR = None

    def Run(self, Mode, PointTime):
        self.GasIn = fsys.gaspath_conditions[self.stationin]

        if Mode == 'DP':
            # create GasInDes, GasOut cantera Quantity (GasIn already created)
            self.GasInDes = ct.Quantity(self.GasIn.phase, mass = self.GasIn.mass)
            self.GasOut = ct.Quantity(self.GasIn.phase, mass = self.GasIn.mass)
            self.Wdes = self.GasInDes.mass
            self.Wcdes = self.Wdes * fg.GetFlowCorrectionFactor(self.GasInDes)
            self.Wc = self.Wcdes
        else:
            self.GasOut.TPY = self.GasIn.TPY
            self.GasOut.mass = self.GasIn.mass

        fsys.gaspath_conditions[self.stationout] = self.GasOut
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

    def GetOutputTableColumnNames(self):
        return [f"W{self.stationin}", f"Wc{self.stationin}", f"T{self.stationin}", f"P{self.stationin}", "PR_"+self.name]

    def AddOutputToTable(self, Mode, rownr):
        for columnname in self.GetOutputTableColumnNames():
            # fg.OutputTable.loc[rownr, columnname] = getattr(self, columnname)
            fsys.OutputTable.loc[rownr, f"W{self.stationin}"]  = self.GasIn.mass
            fsys.OutputTable.loc[rownr, f"Wc{self.stationin}"] = self.Wc
            fsys.OutputTable.loc[rownr, f"T{self.stationin}"]  = self.GasIn.T
            fsys.OutputTable.loc[rownr, f"P{self.stationin}"]  = self.GasIn.P
            if self.PR != None:
                fsys.OutputTable.loc[rownr, "PR_"+self.name] = self.PR


