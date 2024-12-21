import math
import numpy as np
from scipy.interpolate import RegularGridInterpolator
import cantera as ct
import f_global as fg
import f_system as fsys
import f_utils as fu
from f_TurboComponent import TTurboComponent 
from f_compressormap import TCompressorMap

class TFan(TTurboComponent):
    def __init__(self, name, MapFileName_core, stationin, stationout_core, stationout_duct, ShaftNr, Ndes_core, Etades_core,  
                # in TFan, Etades paramater = Etades_core
                #          MapFileName = name of core map file
                 BPRdes, 
                 Ncmapdes_core, Betamapdes_core, PRdes_core, 
                 MapFileName_duct, 
                 Ncmapdes_duct, Betamapdes_duct, PRdes_duct, Etades_duct):   

        # TTurboComponent parent class creator
        super().__init__(name, MapFileName_core, stationin, stationout_core, ShaftNr, Ndes_core, Etades_core) 
                
        self.stationout_duct = stationout_duct

        self.BPRdes = BPRdes

        self.map_core = TCompressorMap(self, name + '_map_core', MapFileName_core, Ncmapdes_core, Betamapdes_core)
        self.PRdes_core = PRdes_core
        # self.Etades = Etades duct, already in parent class

        # duct side map
        self.map_duct = TCompressorMap(self, name + '_map_duct', MapFileName_duct, Ncmapdes_duct, Betamapdes_duct)
        self.PRdes_duct = PRdes_duct
        self.Etades_duct = Etades_duct

        # # parameters for output
        # self.Wc_duct = None
        # # self.PR of TGasPathComponent = PR core here
        # self.PR_duct = None

    def GetSlWcValues(self):
        return self.sl_wc_array
    
    def GetSlPrValues(self):
        return self.sl_pr_array
      
    def Run(self, Mode, PointTime):      
        super().Run(Mode, PointTime)

        if Mode == 'DP':
            self.BPR = self.BPRdes
            # create GasOut_duct ct.Quantity here
            self.GasOut_duct = ct.Quantity(self.GasIn.phase, mass = 1) 
        else:
            self.BPR = fsys.states[self.istate_BPR] * self.BPRdes 

        # inherited compression is core side
        self.W_core_in = self.GasIn.mass / (self.BPR + 1)
        self.GasOut.mass = self.W_core_in

        # add fan duct side compression
        self.W_duct_in = self.GasIn.mass - self.GasOut.mass
        self.GasOut_duct.mass = self.W_duct_in 

        if Mode == 'DP':
            # # correct mass flow
            self.Wdes_core_in = self.W_core_in
            self.Wcdes_core_in = self.Wdes_core_in * fg.GetFlowCorrectionFactor(self.GasIn)
            self.map_core.ReadMapAndSetScaling(self.Ncdes, self.Wcdes_core_in, self.PRdes_core, self.Etades)   # self.Etades = same as Etades_core
            self.PW_core = fu.Compression(self.GasIn, self.GasOut, self.PRdes_core, self.Etades)                 # self.Etades = same as Etades_core

            # # add fan duct side compression
            # self.Wdes_duct = self.GasIn.mass - self.GasOut.mass
            self.Wdes_duct_in = self.W_duct_in
            self.Wcdes_duct_in = self.W_duct_in * fg.GetFlowCorrectionFactor(self.GasIn)
            self.map_duct.ReadMapAndSetScaling(self.Ncdes, self.Wcdes_duct_in, self.PRdes_duct, self.Etades_duct)
            self.PW_duct = fu.Compression(self.GasIn, self.GasOut_duct, self.PRdes_duct, self.Etades_duct)
            
            self.PW = self.PW_core + self.PW_duct
            shaft = fsys.find_shaft_by_number(self.ShaftNr)
            shaft.PW_sum = shaft.PW_sum - self.PW               

            # add states and errors 
            fsys.states = np.append(fsys.states, 1)
            self.istate_n = fsys.states.size-1
            shaft.istate = self.istate_n
            fsys.states = np.append(fsys.states, 1)
            self.istate_beta_core = fsys.states.size-1
            fsys.states = np.append(fsys.states, 1)
            self.istate_beta_duct = fsys.states.size-1
            # state for bypass ratio BPR
            fsys.states = np.append(fsys.states, 1)
            self.istate_BPR = fsys.states.size-1
            
            # error for equation GasIn.mass = W (W according to map operating point)
            fsys.errors = np.append(fsys.errors, 0)
            self.ierror_wc_core = fsys.errors.size-1                     
            fsys.errors = np.append(fsys.errors, 0)
            self.ierror_wc_duct = fsys.errors.size-1                     
            
            # calculate parameters for output
            self.PR_core  = self.PRdes_core
            self.PR_duct = self.PRdes_duct
            self.Wc_core = self.Wcdes_core_in
            self.Wc_duct = self.Wcdes_duct_in
            self.Eta_core = self.Etades
            self.Eta_duct = self.Etades_duct
        else:
            self.N = fsys.states[self.istate_n] * self.Ndes
            self.Nc = self.N / fg.GetRotorspeedCorrectionFactor(self.GasIn)

            # self.BPR = fsys.states[self.istate_BPR] * self.BPRdes

            self.Wc_core, self.PR_core, self.Eta_core = self.map_core.GetScaledMapPerformance(self.Nc, fsys.states[self.istate_beta_core])
            self.Wc_duct, self.PR_duct, self.Eta_duct = self.map_duct.GetScaledMapPerformance(self.Nc, fsys.states[self.istate_beta_duct])

            self.PW_core = fu.Compression(self.GasIn, self.GasOut, self.PR_core, self.Eta_core)                      # self.Etades = same as Etades_core
            self.PW_duct = fu.Compression(self.GasIn, self.GasOut_duct, self.PR_duct, self.Eta_duct)
            
            self.PW = self.PW_core + self.PW_duct

            shaft = fsys.find_shaft_by_number(self.ShaftNr)
            shaft.PW_sum = shaft.PW_sum - self.PW  

            self.W_core = self.Wc_core / fg.GetFlowCorrectionFactor(self.GasIn)
            fsys.errors[self.ierror_wc_core ] = (self.W_core - self.W_core_in) / self.Wdes 
            self.W_duct = self.Wc_duct / fg.GetFlowCorrectionFactor(self.GasIn)
            fsys.errors[self.ierror_wc_duct ] = (self.W_duct - self.W_duct_in) / self.Wdes 

            self.GasOut.mass = self.W_core  # self.GasOut = core flow = GasOut_core
            self.GasOut_duct.mass = self.W_duct

        # calculate parameters for output
        self.Wc = self.GasIn.mass * fg.GetFlowCorrectionFactor(self.GasIn)

        fsys.gaspath_conditions[self.stationout_duct] = self.GasOut_duct   
        return self.GasOut, self.GasOut_duct
    
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
        # override the super.., delete unused PR..., Eta_is: now separate PR and Eta for core and duct
        column_list = super().GetOutputTableColumnNames() 
        column_list.remove("PR_"+self.name) 
        column_list.remove("Eta_is_"+self.name) 
        column_list = column_list + ["BPR_"+self.name, "PR_core_"+self.name, "PR_duct_"+self.name, 
                                     "Wc_core_"+self.name, "Wc_duct_"+self.name,
                                     "Eta_is_core_"+self.name, "Eta_is_duct_"+self.name]
        
        return column_list
         
    def AddOutputToTable(self, Mode, rownr):
        super().AddOutputToTable(Mode, rownr)
        fsys.OutputTable.loc[rownr, "BPR_"+self.name] = self.BPR
        fsys.OutputTable.loc[rownr, "PR_core_"+self.name] = self.PR_core
        fsys.OutputTable.loc[rownr, "PR_duct_"+self.name] = self.PR_duct
        fsys.OutputTable.loc[rownr, "Wc_core_"+self.name] = self.Wc_core
        fsys.OutputTable.loc[rownr, "Wc_duct_"+self.name] = self.Wc_duct
        fsys.OutputTable.loc[rownr, "Eta_is_core_"+self.name] = self.Eta_core
        fsys.OutputTable.loc[rownr, "Eta_is_duct_"+self.name] = self.Eta_duct
