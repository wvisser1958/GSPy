import math
import numpy as np
from scipy.interpolate import RegularGridInterpolator
import cantera as ct
import f_global as fg
import f_shaft as fs
from f_TurboComponent import TTurboComponent as tc

class TCompressor(tc):
    def __init__(self, name, MapFileName, Ncmapdes, Betamapdes, ShaftNr, Ndes, Etades, PRdes):    # Constructor of the class
        super().__init__(name, MapFileName, Ncmapdes, Betamapdes, ShaftNr, Ndes, Etades)   
        # only call SetDPparameters in instantiable classes in init creator
        self.PRdes = PRdes

    def ReadMap(self, filename):              
        super().ReadMap(filename)
        self.nc_values, self.beta_values, self.wc_array = self.ReadNcBetaCrossTable(self.mapfile, 'MASS FLOW')
        self.nc_values, self.beta_values, self.eta_array = self.ReadNcBetaCrossTable(self.mapfile, 'EFFICIENCY')
        self.nc_values, self.beta_values, self.pr_array = self.ReadNcBetaCrossTable(self.mapfile, 'PRESSURE RATIO')   

        # define the interpolation functions allow extrapolation (i.e. fill value = None)
        self.get_map_wc = RegularGridInterpolator((self.nc_values, self.beta_values), self.wc_array, bounds_error=False, fill_value=None)
        self.get_map_eta = RegularGridInterpolator((self.nc_values, self.beta_values), self.eta_array, bounds_error=False, fill_value=None)
        self.get_map_pr = RegularGridInterpolator((self.nc_values, self.beta_values), self.pr_array, bounds_error=False, fill_value=None)
        # awc = get_map_wc((0.45, 0.0)) # wc value for (Nc, Beta)
        pass

    def Run(self, Mode, PointTime, GasIn: ct.Quantity, Ambient) -> ct.Quantity:    
        super().Run(Mode, PointTime, GasIn, Ambient)
        if Mode == 'DP':
            Sin = GasIn.s
            Pout = GasIn.P*self.PRdes
            self.GasOut.SP = Sin, Pout # get GasOut at constant s and higher P
            Hisout = self.GasOut.phase.enthalpy_mass # isentropic exit specific enthalpy
            Hout = GasIn.phase.enthalpy_mass + (Hisout - GasIn.phase.enthalpy_mass) / self.Etades
            self.GasOut.HP = Hout, Pout 
            shaft = fg.find_shaft_by_number(self.ShaftNr)
            # if shaft.assigned:
            self.PW = self.GasOut.H - self.GasIn.H
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
            fg.states = np.append(fg.states, 1)
            self.istate_n = fg.states.size-1
            shaft.istate = self.istate_n
            fg.states = np.append(fg.states, 1)
            self.istate_beta = fg.states.size-1
            # error for equation GasIn.wc = wcmap
            fg.errors = np.append(fg.errors, 0)
            self.ierror_wc = fg.errors.size-1                     
            pass
        else:
            self.N = fg.states[self.istate_n] * self.Ndes
            self.Nc = self.N / fg.GetRotorspeedCorrectionFactor(GasIn)
            self.Betamap = fg.states[self.istate_beta] * self.Betamapdes
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
            shaft = fg.find_shaft_by_number(self.ShaftNr)
            # if shaft.assigned:
            self.PW = self.GasOut.H - self.GasIn.H
            # self.PW = self.Wmap * (self.GasOut.enthalpy_mass - self.GasIn.enthalpy_mass)
            shaft.PW_sum = shaft.PW_sum - self.PW  
            self.Wc = self.GasIn.mass * fg.GetFlowCorrectionFactor(GasIn)
            # fg.errors[self.ierror_wc ] = (self.wcin - self.wc) / self.Wcdes 
            fg.errors[self.ierror_wc ] = (self.Wmap - self.GasIn.mass) / self.Wdes 
            self.GasOut.mass = self.Wmap
            self.N = self.Nc * fg.GetRotorspeedCorrectionFactor(GasIn)          
        return self.GasOut