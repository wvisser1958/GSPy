import numpy as np
import cantera as ct
from scipy.optimize import root
import f_global as fg
import f_system as fsys
import f_utils as fu
from f_TurboComponent import TTurboComponent
from f_turbinemap import TTurbineMap

class TTurbine(TTurboComponent):
    def __init__(self, name, MapFileName, stationin, stationout, ShaftNr, Ndes, Etades, Ncmapdes, Betamapdes, Etamechdes, TurbineType):    # Constructor of the class
        super().__init__(name, MapFileName, stationin, stationout, ShaftNr, Ndes, Etades)
        self.Etamechdes = Etamechdes # spool mechanical efficiency
        self.TurbineType = TurbineType  # gas generator turbine providing all power required by compressor(s)
        # TurbineType = 'PT'  # heavy duty single spool or power turbine, providing power to external loads
        # only call SetDPparameters in instantiable classes in init creator
        self.map = TTurbineMap(self, name + '_map', MapFileName, Ncmapdes, Betamapdes)

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

    def Run(self, Mode, PointTime):
        super().Run(Mode, PointTime)
        shaft = fsys.find_shaft_by_number(self.ShaftNr)
        Sin = self.GasIn.entropy_mass
        Pin = self.GasIn.P
        if Mode == 'DP':
            if self.TurbineType == 'GG':    # gas generator turbine, providing all power required by compressor(s)
                # this turbine is providing all the power required by the shaft
                self.PW = -shaft.PW_sum /  self.Etamechdes
                shaft.PW_sum = 0
                # start with guessed PR
                # pressure_ratio = t444.isentropic_pressure_ratio_for_enthalpy_drop(GasIn.phase, GasIn.P, self.PW / self.GasIn.mass)
                self.PRdes, Hout, Pout = fu.pressure_ratio_for_enthalpy_drop(self.GasOut.phase, self.GasIn.P, self.PW/self.GasIn.mass, self.Etades)
                # invert to Phigh/Plow
                self.PRdes = 1/self.PRdes
                self.GasOut.HP = Hout, Pout
            else:
                PRdesuntilAmbient = self.GetTotalPRdesUntilAmbient()
                Pout = fsys.Ambient.Psa / PRdesuntilAmbient
                self.PRdes = self.GasIn.P/Pout

                self.PW = fu.TurbineExpansion(self.GasIn, self.GasOut, self.PRdes, self.Etades)
                shaft.PW_sum = shaft.PW_sum + self.PW * self.Etamechdes

            self.PWdes = self.PW

            self.map.ReadMapAndSetScaling(self.Ncdes, self.Wcdes, self.PRdes, self.Etades)

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
            # calculate parameters for output
            self.N = self.Nc * fg.GetRotorspeedCorrectionFactor(self.GasIn)
        else:
            if self.TurbineType == 'GG':
                self.N = fsys.states[shaft.istate] * self.Ndes
            self.Nc = self.N / fg.GetRotorspeedCorrectionFactor(self.GasIn)

            self.Wc, self.PR, self.Eta = self.map.GetScaledMapPerformance(self.Nc, fsys.states[self.istate_beta])
            self.W = self.Wc / fg.GetFlowCorrectionFactor(self.GasIn)
            fsys.errors[self.ierror_wc ] = (self.W - self.GasOut.mass) / self.Wdes

            self.PW = fu.TurbineExpansion(self.GasIn, self.GasOut, self.PR, self.Eta)
            shaft.PW_sum = shaft.PW_sum + self.PW * self.Etamechdes
            if self.TurbineType == 'GG':
                fsys.errors[self.ierror_shaftpw] = shaft.PW_sum / self.PWdes

            # set out flow rate to W according to map
            # may deviate from self.GasIn.mass during iteration: this is to propagate the effect of mass flow error
            # to downstream components for more stable convergence in the solver (?)
            self.GasOut.mass = self.W

        return self.GasOut