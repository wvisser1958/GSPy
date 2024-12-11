import numpy as np
import cantera as ct
import f_global as fg
import f_system as fsys
import f_shaft as fshaft
import f_turbomap as tmap
from f_gaspath import TGaspath as gaspath
        
class TTurboComponent(gaspath):
    def __init__(self, name, MapFileName, stationin, stationout, Ncmapdes, Betamapdes, ShaftNr, Ndes, Etades):    # Constructor of the class
        super().__init__(name, MapFileName, stationin, stationout)    
        self.GasIn = None
        self.GasOut = None
        self.ShaftNr = ShaftNr
        
        self.Ndes = Ndes  
        self.N = Ndes   
        self.Nc = None

        self.W = None # W is mass flow of component, e.g. according to map

        self.Etades = Etades
        self.Eta = None

        self.PW = None

        self.map = None

        if all(shaft.ShaftNr != ShaftNr for shaft in fsys.shaft_list):
            fsys.shaft_list.append(fshaft.TShaft(ShaftNr, name + ' shaft ' + str(ShaftNr)) )

    def Run(self, Mode, PointTime, GasIn: ct.Quantity) -> ct.Quantity:  
        super().Run(Mode, PointTime, GasIn)
        self.Ncdes = self.Ndes / fg.GetRotorspeedCorrectionFactor(GasIn) 
        self.Nc = self.Ncdes
        self.Wdes = self.GasIn.mass
        self.Wcdes = self.Wdes * fg.GetFlowCorrectionFactor(GasIn)
        self.Eta = self.Etades

    def PrintPerformance(self, Mode, PointTime):
        super().PrintPerformance(Mode, PointTime)
        print(f"\tRotor speed  : {self.N:.0f} rpm")
        print(f"\tCorr Rotor speed : {self.Nc:.0f} rpm")
        if self.map != None:
            if self.map.Ncmap!= None:
                print(f"\tMap Corr Rotor speed : {self.map.Ncmap:.4f} rpm")
            if self.map.Wcmapdes!= None:
                print(f"\tDP Map Corr mass flow : {self.map.Wcmapdes:.3f} kg/s")
            if self.map.Wcmap!= None:
                print(f"\tMap Corr mass flow : {self.map.Wcmap:.3f} kg/s")
            # if self.W!= None:
            #     print(f"\tMap mass flow : {self.W:.3f} kg/s")
            if self.map.PRmap!= None:
                print(f"\tPR map : {self.map.PRmap:.4f}")
            if self.map.Etamap!= None:
                print(f"\tEta map : {self.map.Etamap:.4f}")

        print(f"\tEta des : {self.Etades:.4f}")
        print(f"\tEta     : {self.Eta:.4f}")

        print(f"\tPW : {self.PW:.1f}")

    def GetOutputTableColumnNames(self):
        return super().GetOutputTableColumnNames() + ["N_"+self.name, "Nc_"+self.name, "Eta_is_"+self.name, "PW_"+self.name]
         
    def AddOutputToTable(self, Mode, rownr):
        super().AddOutputToTable(Mode, rownr)
        fsys.OutputTable.loc[rownr, "N_"+self.name] = self.N
        fsys.OutputTable.loc[rownr, "Nc_"+self.name] = self.Nc
        fsys.OutputTable.loc[rownr, "Eta_is_"+self.name] = self.Eta
        fsys.OutputTable.loc[rownr, "PW_"+self.name] = self.PW