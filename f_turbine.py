import numpy as np
import cantera as ct
from scipy.optimize import root
from scipy.interpolate import RegularGridInterpolator
import f_global as fg
import f_system as fsys
import f_utils as fu
from f_TurboComponent import TTurboComponent as tc

class TTurbine(tc):
    def __init__(self, name, MapFileName, stationin, stationout, Ncmapdes, Betamapdes, ShaftNr, Ndes, Etades, TurbineType):    # Constructor of the class
        super().__init__(name, MapFileName, stationin, stationout, Ncmapdes, Betamapdes, ShaftNr, Ndes, Etades)  
        self.TurbineType = TurbineType  # gas generator turbine providing all power required by compressor(s)
        # TurbineType = 'PT'  # heavy duty single spool or power turbine, providing power to external loads
        # only call SetDPparameters in instantiable classes in init creator

    def ReadPRlimits(self, mapfile, keyword):
        line = mapfile.readline()  
        while keyword not in line.upper():
            line = mapfile.readline()  
        line = mapfile.readline()  
        items = line.split()
        nccount1= float(items[0])%1
        nccount = round(nccount1*1000)-1
        nc_values = np.empty(nccount, dtype=float)
        line = mapfile.readline()  
        # items = line.split()
        prlimits_array = np.array(list(map(float, line.split()[1:])))
        return nc_values, prlimits_array      

    def ReadMap(self, filename):              # Abstract method, defined by convention only
        super().ReadMap(filename)

        # read PR min values
        self.nc_values, self.prmin_array = self.ReadPRlimits(self.mapfile, 'MIN PRESSURE RATIO')  
        self.nc_values, self.prmax_array = self.ReadPRlimits(self.mapfile, 'MAX PRESSURE RATIO')  

        self.nc_values, self.beta_values, self.wc_array = self.ReadNcBetaCrossTable(self.mapfile, 'MASS FLOW')
        self.nc_values, self.beta_values, self.eta_array = self.ReadNcBetaCrossTable(self.mapfile, 'EFFICIENCY')

        # now calculate PR_value table:
        # Unlike with the compressor, for the turbine PR values can be calculated
        self.pr_array = np.zeros((self.nc_values.size, self.beta_values.size), dtype=float)
        
        for irow in range(self.nc_values.size):
            for icol in range(self.beta_values.size):
                self.pr_array[irow, icol] = self.prmin_array[irow] + \
                    self.beta_values[icol] * (self.prmax_array[irow] - self.prmin_array[irow])

        # define the interpolation functions allow extrapolation (i.e. fill value = None)
        self.get_map_wc = RegularGridInterpolator((self.nc_values, self.beta_values), self.wc_array, bounds_error=False, fill_value=None)
        self.get_map_eta = RegularGridInterpolator((self.nc_values, self.beta_values), self.eta_array, bounds_error=False, fill_value=None)
        self.get_map_pr = RegularGridInterpolator((self.nc_values, self.beta_values), self.pr_array, bounds_error=False, fill_value=None)
        # aeta = get_map_eta((0.70, 0.75)) # wc value for (Nc, Beta)
        # apr = get_map_pr((0.70, 0.75)) # wc value for (Nc, Beta)
        pass

    def GetTotalPRdesUntilAmbient(self):
        # always at least one gas path component downstream a turbine (if only one: exhaust)
        # this means Exhaust PRdes must be 1 or corresponding to some error loss (total-to-total)
        # (Exhast PR (off-design) actually is total to throat static PR)
        PRdesuntilAmbient = 1
        agaspathcomponent = fu.get_gaspathcomponent_object_inlet_stationnr(fsys.systemmodel, self.stationout) 
        while agaspathcomponent != None:
            PRdesuntilAmbient = PRdesuntilAmbient * agaspathcomponent.PRdes
            agaspathcomponent = fu.get_gaspathcomponent_object_inlet_stationnr(fsys.systemmodel, agaspathcomponent.stationout)             
        return PRdesuntilAmbient 

    def Run(self, Mode, PointTime, GasIn: ct.Quantity) -> ct.Quantity:   
        super().Run(Mode, PointTime, GasIn)
        shaft = fsys.find_shaft_by_number(self.ShaftNr)
        Sin = GasIn.entropy_mass
        Pin = GasIn.P        
        if Mode == 'DP':
            if self.TurbineType == 'GG':    # gas generator turbine, providing all power required by compressor(s)
                # this turbine is providing all the power required by the shaft
                self.PW = -shaft.PW_sum
                self.PWdes = self.PW
                # start with guessed PR
                # pressure_ratio = t444.isentropic_pressure_ratio_for_enthalpy_drop(GasIn.phase, GasIn.P, self.PW / self.GasIn.mass)
                self.PRdes, Hout, Pout = fu.pressure_ratio_for_enthalpy_drop(self.GasOut.phase, self.GasIn.P, self.PW/self.GasIn.mass, self.Etades)
                # invert to Phigh/Plow
                self.PRdes = 1/self.PRdes
                self.GasOut.HP = Hout, Pout
            else:
                PRdesuntilAmbient = self.GetTotalPRdesUntilAmbient()
                Pout = fsys.Ambient.Psa / PRdesuntilAmbient  
                self.PRdes = GasIn.P/Pout
                self.GasOut.SP = self.GasIn.entropy_mass, Pout
                final_enthalpy_is = self.GasOut.enthalpy_mass
                # eta_is = (initial_enthalpy - final_enthalpy) / (initial_enthalpy - final_enthalpy_is)
                final_enthalpy = self.GasIn.enthalpy_mass - (self.GasIn.enthalpy_mass - final_enthalpy_is) * self.Etades
                self.GasOut.HP = final_enthalpy, Pout 
                self.PW = self.GasIn.H - self.GasOut.H
                shaft.PW_sum = shaft.PW_sum + self.PW 
                
            # Hout = (self.GasIn.H - self.PW)/self.GasIn.mass 
            # Tout = fu.set_enthalpy(self.GasOut.phase, Hout) 
            self.ReadMap(self.MapFileName)  
            self.Ncdes = self.Ndes / fg.GetRotorspeedCorrectionFactor(GasIn) 
            self.Nc = self.Ncdes
            self.Wdes = self.GasIn.mass
            self.Wcdes = self.Wdes * fg.GetFlowCorrectionFactor(GasIn)
            self.Eta = self.Etades
            if self.mapfile is not None:
                # get map scaling parameters
                # for Nc
                self.SFmap_Nc = self.Ncdes / self.Ncmapdes
                # for Wc
                self.Wcmapdes = self.get_map_wc((self.Ncmapdes, self.Betamapdes))
                self.SFmap_Wc = self.Wcdes / self.Wcmapdes
                # for PR
                self.PRmap = self.get_map_pr((self.Ncmapdes, self.Betamapdes))
                self.SFmap_PR = (self.PRdes - 1) / (self.PRmap - 1)
                # for Eta
                self.Etamap = self.get_map_eta((self.Ncmapdes, self.Betamapdes))
                self.SFmap_Eta = self.Etades / self.Etamap
                pass                      
            # add states and errors 
            # rotor speed state is same as compressor's
            fsys.states = np.append(fsys.states, 1)
            self.istate_beta = fsys.states.size-1
            # error for equation GasIn.wc = wcmap
            fsys.errors = np.append(fsys.errors, 0)
            self.ierror_wc = fsys.errors.size-1  
            # shaft power error
            if self.TurbineType == 'GG':
                fsys.errors = np.append(fsys.errors, 0)
                self.ierror_shaftpw = fsys.errors.size-1 
        else:
            self.Betamap = fsys.states[self.istate_beta] * self.Betamapdes
            if self.TurbineType == 'GG':
                self.N = fsys.states[shaft.istate] * self.Ndes
            self.Nc = self.N / fg.GetRotorspeedCorrectionFactor(GasIn)
            self.Ncmap = self.Nc / self.SFmap_Nc
            self.Wcmap = self.get_map_wc((self.Ncmap, self.Betamap))
            self.Wc = self.Wcmap * self.SFmap_Wc
            self.PRmap = self.get_map_pr((self.Ncmap, self.Betamap))
            self.PR = self.SFmap_PR * (self.PRmap - 1) + 1

            self.Wmap = self.Wc / fg.GetFlowCorrectionFactor(GasIn)
            # self.GasIn.mass * fg.GetFlowCorrectionFactor(GasIn)
            
            self.Etamap = self.get_map_eta((self.Ncmap, self.Betamap))
            self.Eta = self.SFmap_Eta * self.Etamap

            self.GasOut.mass = self.GasIn.mass
            # Tout, Hout = fu.exit_T_and_enthalpy_for_pressure_ratio(self.GasOut.phase, self.PR, self.Eta)

            # Hout = (GasIn.H - self.PW)/self.GasIn.mass
            Pout = self.GasIn.P / self.PR
            self.GasOut.SP = self.GasIn.entropy_mass, Pout
            final_enthalpy_is = self.GasOut.enthalpy_mass
            # eta_is = (initial_enthalpy - final_enthalpy) / (initial_enthalpy - final_enthalpy_is)
            final_enthalpy = self.GasIn.enthalpy_mass - (self.GasIn.enthalpy_mass - final_enthalpy_is) * self.Eta
            self.GasOut.HP = final_enthalpy, Pout            

            # self.wcin = self.GasIn.mass * fg.GetFlowCorrectionFactor(GasIn)
            # fg.errors[self.ierror_wc ] = (self.wcin - self.wc) / self.Wcdes             
            fsys.errors[self.ierror_wc ] = (self.Wmap - self.GasOut.mass) / self.Wdes             

            self.PW = self.GasIn.H - self.GasOut.H
            shaft.PW_sum = shaft.PW_sum + self.PW             
            
            if self.TurbineType == 'GG':
                fsys.errors[self.ierror_shaftpw] = shaft.PW_sum / self.PWdes 

            # set out flow rate to Wmap
            self.GasOut.mass = self.Wmap

        self.N = self.Nc * fg.GetRotorspeedCorrectionFactor(GasIn)   
        return self.GasOut    