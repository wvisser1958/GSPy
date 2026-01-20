# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#    http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Authors
#   Wilfried Visser

import numpy as np
import cantera as ct
from scipy.optimize import root
import gspy.core.sys_global as fg
import gspy.core.system as fsys
import gspy.core.utils as fu
from gspy.core.turbo_component import TTurboComponent
from gspy.core.turbinemap import TTurbineMap

class TTurbine(TTurboComponent):
    def __init__(self, name,
                 MapFileName_or_dict,
                 ControlComponent, stationin, stationout, ShaftNr,
                 Ndes, Etades, Ncmapdes, Betamapdes, Etamechdes,
                 TurbineType,
                 CoolingFlows):
        super().__init__(name, MapFileName_or_dict, ControlComponent, stationin, stationout, ShaftNr, Ndes, Etades, Ncmapdes, Betamapdes)
        self.Etamechdes = Etamechdes # spool mechanical efficiency
        self.TurbineType = TurbineType  # gas generator turbine providing all power required by compressor(s)
        # TurbineType = 'PT'  # heavy duty single spool or power turbine, providing power to external loads
        # only call SetDPparameters in instantiable classes in init creator
        self.map = TTurbineMap(self, name + '_map', self.MapFileName, '', '', ShaftNr, Ncmapdes, Betamapdes)
        self.CoolingFlows = CoolingFlows

    # 1.6 virtual method CreateMap will be called in ancestor TTurboComponent
    # for either single map or series of maps in case of variable geometry with multipe maps for example
    def CreateMap(self, MapFilePath, ShaftNr, Ncmapdes, Betamapdes):
        return TTurbineMap(self, self.name + '_map', MapFilePath, '', '', ShaftNr, Ncmapdes, Betamapdes)

    def GetTotalPRdesUntilAmbient(self):
        # always at least one gas path component downstream a turbine (if only one: exhaust)
        # this means Exhaust PRdes must be 1 or corresponding to some error loss (total-to-total)
        # (Exhast PR (off-design) actually is total to throat static PR)
        PRdesuntilAmbient = 1
        agaspathcomponent = fu.get_gaspathcomponent_object_inlet_stationnr(fsys.system_model, self.stationout)
        while agaspathcomponent != None:
            PRdesuntilAmbient = PRdesuntilAmbient * agaspathcomponent.PRdes
            agaspathcomponent = fu.get_gaspathcomponent_object_inlet_stationnr(fsys.system_model, agaspathcomponent.stationout)
        return PRdesuntilAmbient

    def Run(self, Mode, PointTime):

        super().Run(Mode, PointTime)
        Sin = self.GasIn.entropy_mass
        Pin = self.GasIn.P

        def CalcCoolingFlowEffects():
            self.PW_cl_pump = 0
            self.PW_cl_exp = 0
            self.W_cl_eff = 0
            Ekin_at_R1 = np.square(np.pi*self.N/60)
            for cf in self.CoolingFlows:
                cf.Run(Mode, PointTime)  # this calculates the bleed flow rate, set GasInjected to GasIn
                # pumping power for blade cooling
                if cf.Rexit > 0:
                    # power taken from shaft for accelerating the cooling flow in circumferential direction
                    dHradialpump = Ekin_at_R1 * np.square(cf.Rexit)
                    cf.PWpump =  dHradialpump * cf.W
                    self.PW_cl_pump = self.PW_cl_pump + cf.PWpump
                    # isentropic compression due to 'radial pump' action
                    # in the rotating frame dH increase is half of dHradialpump
                    dH_for_P = dHradialpump/2
                    TR_pump = (cf.GasIn.T + dH_for_P/cf.GasIn.cp_mass)/cf.GasIn.T
                    gamma = cf.GasIn.cp_mass/cf.GasIn.cv_mass
                    PR_pump = np.power(TR_pump, gamma/(gamma-1))
                    # now add full dHradialpump to enthalpy, and P increase to GasInjected
                    cf.GasInjected.HP = cf.GasIn.enthalpy_mass + dHradialpump, cf.GasIn.P * PR_pump
                else:
                    cf.PWpump = 0

                # expansion of cooling flow contribution to turbine power
                dPexp = (cf.GasInjected.P - self.GasOut.P) * cf.dPfraction
                if dPexp > 0:
                    PRexp = (self.GasOut.P + dPexp) / self.GasOut.P
                    cf.PWexp = fu.TurbineExpansion(cf.GasInjected, cf.GasOut, PRexp, self.Eta, cf.W, self.Polytropic_Eta)
                    self.PW_cl_exp = self.PW_cl_exp + cf.PWexp
                else:
                    cf.PWexp = 0

                # add fraction of flow to be included inlet mass flow conservation of mass error equation
                self.W_cl_eff = self.W_cl_eff + cf.W_tur_eff_fraction * cf.W

                # add to main exit flow
                Pout = self.GasOut.P
                self.GasOut = self.GasOut + cf.GasOut
                # Because Cantera assumes you are physically combining two finite quantities of gas,
                # so it recomputes the real thermodynamic result, not a mathematical average.
                # That means:
                # If the two gases weren’t identical species distribution + identical temperature,
                # the post-mix EOS solution will slightly shift pressure — even if both started at “same P”.
                #  so we must preserve pressure strictly
                self.GasOut.HP = self.GasOut.enthalpy_mass, Pout
            # return total cooling effects on turbine performance: PW delta and Wc delta
            return self.PW_cl_exp - self.PW_cl_pump, self.W_cl_eff

        def pressure_ratio_for_turbine_power(PR_iter):
            # Set the initial state
            # reset GasOut to GasIn (in case cooling flow added during previous iteration step)
            self.GasOut.TPY = self.GasIn.TPY
            self.GasOut.mass = self.GasIn.mass

            # power without cooling:
            PW_PR = fu.TurbineExpansion(self.GasIn, self.GasOut, PR_iter, self.Eta, None, self.Polytropic_Eta)

            # cooling flow effects
            if self.CoolingFlows != None:
                self.dPWcl, self.W_cl_eff = CalcCoolingFlowEffects()
                PW_PR = PW_PR + self.dPWcl
            else:
                self.dPWcl = 0
                self.W_cl_eff = 0

            return (PW_PR - self.PW)/self.PW

        if Mode == 'DP':
        # ******************** DP design mode *************************
            self.W_cl_eff = 0
            if self.TurbineType == 'GG':    # gas generator or fan lpt turbine, providing all power required by compressor(s) or fan
                # this turbine is providing all the power required by the shaft
                self.PW = -self.shaft.PW_sum /  self.Etamechdes

                # Define the function to find the root of
                initial_guess = [1.9]

                # Use scipy.optimize.root to find the pressure ratio
                solution = root(pressure_ratio_for_turbine_power, initial_guess)

                # Check if the solution converged
                if solution.success:
                    self.PRdes = solution.x[0]
                else:
                    raise ValueError(self.name + "DP PR iteration did not converge")

                # calculate parameters for output
                self.PR = self.PRdes
                self.shaft.PW_sum = 0
            else:
                PRdesuntilAmbient = self.GetTotalPRdesUntilAmbient()
                Pout = fsys.Ambient.Psa / PRdesuntilAmbient
                self.PRdes = self.GasIn.P/Pout
                self.PR = self.PRdes

                self.PW = fu.TurbineExpansion(self.GasIn, self.GasOut, self.PRdes, self.Etades, None, self.Polytropic_Eta)

                # v1.2
                # cooling flow effects
                if self.CoolingFlows != None:
                    self.dPWcl, self.W_cl_eff = CalcCoolingFlowEffects()
                    self.PW = self.PW + self.dPWcl

                self.shaft.PW_sum = self.shaft.PW_sum + self.PW * self.Etamechdes

            # reset GasOut to gaspath_conditions dictionary (because link broken by adding cooling flow to GasOut
            #                                                self.GasOut = self.GasOut + cf.GasOut)
            fsys.gaspath_conditions[self.stationout] = self.GasOut

            self.PWdes = self.PW

            # v1.2 recalculate self.Wcdes adding cooling flow
            self.Wcdes = (self.Wdes + self.W_cl_eff) * fg.GetFlowCorrectionFactor(self.GasInDes)

            # 1.6
            # self.map.ReadMapAndSetScaling(self.Ncdes, self.Wcdes, self.PRdes, self.Etades)
            self.ReadTurboMapAndSetScaling()

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
        # ******************** end DP design mode *************************

        # ******************** OD off design mode *************************
        else:
            if self.TurbineType == 'GG':
                self.N = fsys.states[self.shaft.istate] * self.Ndes
            self.Nc = self.N / fg.GetRotorspeedCorrectionFactor(self.GasIn)

            self.Wc, self.PR, self.Eta = self.map.GetScaledMapPerformance(self.Nc, fsys.states[self.istate_beta])
            self.W = self.Wc / fg.GetFlowCorrectionFactor(self.GasIn)
            # fsys.errors[self.ierror_wc ] = (self.W - self.GasOut.mass) / self.Wdes

            self.PW = fu.TurbineExpansion(self.GasIn, self.GasOut, self.PR, self.Eta, None, self.Polytropic_Eta)

            # v1.2
            if self.CoolingFlows != None:
                self.dPWcl, self.W_cl_eff = CalcCoolingFlowEffects()
                self.PW = self.PW + self.dPWcl
            fsys.errors[self.ierror_wc ] = (self.W - self.GasIn.mass - self.W_cl_eff) / self.Wdes

            self.shaft.PW_sum = self.shaft.PW_sum + self.PW * self.Etamechdes
            if self.TurbineType == 'GG':
                fsys.errors[self.ierror_shaftpw] = self.shaft.PW_sum / self.PWdes

            # reset GasOut to gaspath_conditions dictionary (because link broken by adding cooling flow to GasOut
            #                                                self.GasOut = self.GasOut + cf.GasOut)
            fsys.gaspath_conditions[self.stationout] = self.GasOut
        # ******************** end OD off design mode *************************

        return self.GasOut

    # v1.2
    def PrintPerformance(self, Mode, PointTime):
        super().PrintPerformance(Mode, PointTime)
        if self.CoolingFlows != None:
            for coolingflow in self.CoolingFlows:
                coolingflow.PrintPerformance(Mode, PointTime)

    def AddOutputToDict(self, Mode):
        super().AddOutputToDict(Mode)
        if self.CoolingFlows != None:
            for coolingflow in self.CoolingFlows:
                coolingflow.AddOutputToDict(Mode)