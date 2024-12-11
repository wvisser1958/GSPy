import math
import numpy as np
from scipy.interpolate import RegularGridInterpolator
import cantera as ct
import f_global as fg
import f_system as fsys
import f_utils as fu
from f_compressor import TCompressor

class TFan(TCompressor):
    def __init__(self, name, MapFileName, stationin, stationout, Ncmapdes, Betamapdes, ShaftNr, Ndes, Etades, PRdes, SpeedOption, BPRdes, Etades_duct, PRdes_duct, MapFileName_duct, Ncmapdes_duct, Betamapdes_duct):    # Constructor of the class
        super().__init__(name, MapFileName, stationin, stationout, Ncmapdes, Betamapdes, ShaftNr, Ndes, Etades, PRdes, SpeedOption)   
        # only call SetDPparameters in instantiable classes in init creator
        self.BPRdes = BPRdes
        self.Etades_duct = Etades_duct
        self.PRdes_duct = PRdes_duct
        self.MapFileName_duct = MapFileName_duct
        self.mapfile_duct = None
        self.maptitle_duct = None
        self.Ncmapdes_duct = Ncmapdes_duct
        self.Betamapdes_duct = Betamapdes_duct
        self.Wcmapdes_duct = None
        self.Wcmap_duct = None
        self.Wmap_duct = None

        self.map_duct = tmap.TTurboMap(name + '_ductmap', MapFileName_duct, Ncmapdes_duct, Betamapdes_duct)

    def GetSlWcValues(self):
        return self.sl_wc_array
    
    def GetSlPrValues(self):
        return self.sl_pr_array

    def ReadMap_duct(self, filename):              
        self.maptype_duct, self.maptitle_duct, self.mapfile_duct = super().ReadMap(filename)  
        self.nc_values_duct, self.beta_values_duct, self.wc_array_duct = self.ReadNcBetaCrossTable(self.mapfile_duct, 'MASS FLOW')
        self.nc_values_duct, self.beta_values_duct, self.eta_array_duct = self.ReadNcBetaCrossTable(self.mapfile_duct, 'EFFICIENCY')
        self.nc_values_duct, self.beta_values_duct, self.pr_array_duct = self.ReadNcBetaCrossTable(self.mapfile_duct, 'PRESSURE RATIO')
        dummy_value, self.sl_wc_array_duct, self.sl_pr_array_duct = self.ReadNcBetaCrossTable(self.mapfile_duct, 'SURGE LINE')
        # define the interpolation functions allow extrapolation (i.e. fill value = None)
        self.get_map_wc_duct = RegularGridInterpolator((self.nc_values_duct, self.beta_values_duct), self.wc_array_duct, bounds_error=False, fill_value=None, method = 'cubic')
        self.get_map_eta_duct = RegularGridInterpolator((self.nc_values_duct, self.beta_values_duct), self.eta_array_duct, bounds_error=False, fill_value=None, method = 'cubic')
        self.get_map_pr_duct = RegularGridInterpolator((self.nc_values_duct, self.beta_values_duct), self.pr_array_duct, bounds_error=False, fill_value=None, method = 'cubic')

    def ReadMapsAndSetScaling(self):
        super().ReadMapsAndSetScaling()
        self.ReadMap_duct(self.MapFileName_duct)  
        if self.mapfile_duct is not None:
            # get map scaling parameters
            # for Nc
            self.SFmap_Nc_duct = self.Ncdes_duct / self.Ncmapdes_duct
            # for Wc
            self.Wcmapdes_duct = self.get_map_wc((self.Ncmapdes_duct, self.Betamapdes_duct))
            self.SFmap_Wc_duct = self.Wcdes_duct / self.Wcmapdes_duct
            # for PR
            self.PRmap_duct = self.get_map_pr((self.Ncmapdes_duct, self.Betamapdes_duct))
            self.SFmap_PR_duct = (self.PRdes - 1) / (self.PRmap_duct - 1)
            # for Eta
            self.Etamap_duct = self.get_map_eta((self.Ncmapdes_duct, self.Betamapdes_duct))
            self.SFmap_Eta_duct = self.Etades_duct / self.Etamap_duct
        
    def Run(self, Mode, PointTime, GasIn: ct.Quantity) -> ct.Quantity:    
        super().Run(Mode, PointTime, GasIn)
        if Mode == 'DP':
            # inherited compressio is core side
            # correct mass flow
            self.GasOut.mass = self.GasIn.mass / (self.BPRdes + 1)
            self.PW_core = fu.Compression(GasIn, self.GasOut, self.PRdes, self.Etades)
            # add fan duct side compression
            self.GasOut_duct = ct.Quantity(GasIn.phase, mass = GasIn.mass -self.GasOut.mass) 
            self.PW_duct = fu.Compression(GasIn, self.GasOut_duct, self.PRdes_duct, self.Etades_duct)
            
            self.PW = self.PW_core + self.PW_duct
            shaft = fsys.find_shaft_by_number(self.ShaftNr)
            shaft.PW_sum = shaft.PW_sum - self.PW               

            self.N = self.Ndes
            self.Ncdes = self.Ndes / fg.GetRotorspeedCorrectionFactor(GasIn) 
            self.Nc = self.Ncdes
            self.Eta = self.Etades

            self.ReadMap(self.MapFileName)  
            if self.mapfile is not None:
                # get map scaling parameters
                # for Nc
                self.SFmap_Nc = self.Ncdes / self.Ncmapdes
                # for Wc
                self.Wcmapdes = self.get_map_wc((self.Ncmapdes, self.Betamapdes))
                self.Wdes = self.GasIn.mass
                self.Wcdes = self.Wdes * fg.GetFlowCorrectionFactor(GasIn)
                self.SFmap_Wc = self.Wcdes / self.Wcmapdes
                # for PR
                self.PRmap = self.get_map_pr((self.Ncmapdes, self.Betamapdes))
                self.SFmap_PR = (self.PRdes - 1) / (self.PRmap - 1)
                # for Eta
                self.Etamap = self.get_map_eta((self.Ncmapdes, self.Betamapdes))
                self.SFmap_Eta = self.Etades / self.Etamap
                pass 
            # add states and errors 
            if self.SpeedOption != 'CS':
                fsys.states = np.append(fsys.states, 1)
                self.istate_n = fsys.states.size-1
                shaft.istate = self.istate_n
            fsys.states = np.append(fsys.states, 1)
            self.istate_beta = fsys.states.size-1
            # error for equation GasIn.wc = wcmap
            fsys.errors = np.append(fsys.errors, 0)
            self.ierror_wc = fsys.errors.size-1                     
            self.PR = self.PRdes
        else:
            if self.SpeedOption != 'CS':
                self.N = fsys.states[self.istate_n] * self.Ndes
            self.Nc = self.N / fg.GetRotorspeedCorrectionFactor(GasIn)
            self.Betamap = fsys.states[self.istate_beta] * self.Betamapdes
            self.Ncmap = self.Nc / self.SFmap_Nc 
            self.GasIn.TP = GasIn.T, GasIn.P
            self.GasIn.mass = GasIn.mass                     
            
            # for Wc
            self.Wcmap = self.get_map_wc((self.Ncmap, self.Betamap))
            self.Wc = self.SFmap_Wc * self.Wcmap
            # self.wc = 18.4385
            self.Wmap = self.Wc / fg.GetFlowCorrectionFactor(GasIn)
            # for PR
            self.PRmap = self.get_map_pr((self.Ncmap, self.Betamap))
            # self.SFmap_PR = (self.PRdes - 1) / (PRmap - 1)
            self.PR = self.SFmap_PR * (self.PRmap - 1) + 1
            # for Eta
            self.Etamap = self.get_map_eta((self.Ncmap, self.Betamap))
            self.Eta = self.SFmap_Eta * self.Etamap
            # self.Eta = 0.8374

            Sin = GasIn.entropy_mass
            Pout = GasIn.P*self.PR
            self.GasOut.SP = Sin, Pout # get GasOut at constant s and higher P
            Hisout = self.GasOut.phase.enthalpy_mass # isentropic exit specific enthalpy
            Hout = GasIn.phase.enthalpy_mass + (Hisout - GasIn.phase.enthalpy_mass) / self.Eta
            self.GasOut.HP = Hout, Pout 
            shaft = fsys.find_shaft_by_number(self.ShaftNr)
            # if shaft.assigned:
            self.PW = self.GasOut.H - self.GasIn.H
            # self.PW = self.Wmap * (self.GasOut.enthalpy_mass - self.GasIn.enthalpy_mass)
            shaft.PW_sum = shaft.PW_sum - self.PW  
            # fg.errors[self.ierror_wc ] = (self.wcin - self.wc) / self.Wcdes 
            fsys.errors[self.ierror_wc ] = (self.Wmap - self.GasIn.mass) / self.Wdes 
            self.GasOut.mass = self.Wmap
            self.N = self.Nc * fg.GetRotorspeedCorrectionFactor(GasIn)          

        # calculate parameters for output
        self.Wc = self.GasIn.mass * fg.GetFlowCorrectionFactor(GasIn)

        return self.GasOut