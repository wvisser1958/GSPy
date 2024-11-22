import numpy as np
import f_global as fg
import f_shaft as fs
from f_gaspath import TGaspath as gaspath
        
class TTurboComponent(gaspath):
    def __init__(self, name, MapFileName, Ncmapdes, Betamapdes, ShaftNr, Ndes, Etades):    # Constructor of the class
        super().__init__(name, MapFileName)    
        self.GasIn = None
        self.GasOut = None
        self.ShaftNr = ShaftNr

        self.Betamapdes = Betamapdes 
        self.Betamap = None

        self.Ndes = Ndes  
        self.N = Ndes   
        self.Ncmapdes = Ncmapdes
        self.Nc = None
        self.Ncmap = None

        self.Etades = Etades
        self.Eta = None
        self.Etamap = None

        self.Wcmapdes = None
        self.Wcmap = None
        self.Wmap = None
        
        self.PRmap = None

        if all(shaft.ShaftNr != ShaftNr for shaft in fg.shaft_list):
            fg.shaft_list.append(fs.TShaft(ShaftNr, name + ' shaft ' + str(ShaftNr)) )
       
    def ReadMap(self, filename):              # Abstract method, defined by convention only
        super().ReadMap(filename)
        # with self.file:
        if self.mapfile is not None:
            line = self.mapfile.readline()     
            while 'REYNOLDS' not in line.upper():
                line = self.mapfile.readline()      
            RNI = np.empty(2, dtype=float)
            f_RNI = np.empty(2, dtype=float)
            items = line.split()
            RNI[0] = float(items[1].split("=", 1)[1]) 
            f_RNI[0] = float(items[2].split("=", 1)[1]) 
            RNI[1] = float(items[3].split("=", 1)[1]) 
            f_RNI[1] = float(items[4].split("=", 1)[1])             

    def PrintPerformance(self, Mode):
        super().PrintPerformance(Mode)
        print(f"\tRotor speed  : {self.N:.0f} rpm")
        print(f"\tCorr Rotor speed : {self.Nc:.0f} rpm")
        if self.Ncmap != None:
            print(f"\tMap Corr Rotor speed : {self.Ncmap:.4f} rpm")
        
        print(f"\tDP Map Corr mass flow : {self.Wcmapdes:.3f} kg/s")
        if self.Wcmap != None:
            print(f"\tMap Corr mass flow : {self.Wcmap:.3f} kg/s")
        if self.Wmap != None:
            print(f"\tMap mass flow : {self.Wmap:.3f} kg/s")

        print(f"\tPR map : {self.PRmap:.4f}")

        print(f"\tEta des : {self.Etades:.4f}")
        print(f"\tEta     : {self.Eta:.4f}")
        print(f"\tEta map : {self.Etamap:.4f}")

