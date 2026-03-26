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
import gspy.core.utils as fu
from gspy.core.turbo_component import TTurboComponent
from gspy.core.turbinemap import TTurbineMap

class TTurbine(TTurboComponent):
    def __init__(self, owner, name,
                 MapFileName_or_dict,
                 ControlComponent, station_in, station_out, ShaftNr,
                 Ndes, Etades, Ncmapdes, Betamapdes, Etamechdes,
                 TurbineType,
                 CoolingFlows):
        super().__init__(owner, name, MapFileName_or_dict, ControlComponent, station_in, station_out, ShaftNr, Ndes, Etades, Ncmapdes, Betamapdes)
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
        agaspathcomponent = self.owner.get_gaspathcomponent_object_inlet_stationnr(self.station_out)
        while agaspathcomponent != None:
            PRdesuntilAmbient = PRdesuntilAmbient * agaspathcomponent.PRdes
            agaspathcomponent = self.owner.get_gaspathcomponent_object_inlet_stationnr(agaspathcomponent.station_out)
        return PRdesuntilAmbient

    def Run(self, Mode, PointTime):

        super().Run(Mode, PointTime)
        Sin = self.gas_in.entropy_mass
        Pin = self.gas_in.P

        def CalcCoolingFlowEffects():
            self.DHW_cl_pump = 0
            self.DHW_cl_exp = 0
            self.W_cl_eff = 0
            Ekin_at_R1 = np.square(np.pi*self.N/60)
            for cf in self.CoolingFlows:
                cf.Run(Mode, PointTime)  # this calculates the bleed flow rate, set gas_injected to gas_in
                # pumping power for blade cooling
                if cf.Rexit > 0:
                    # power taken from shaft for accelerating the cooling flow in circumferential direction
                    dHradialpump = Ekin_at_R1 * np.square(cf.Rexit)
                    cf.DHWpump =  dHradialpump * cf.W
                    self.DHW_cl_pump = self.DHW_cl_pump + cf.DHWpump
                    # isentropic compression due to 'radial pump' action
                    # in the rotating frame dH increase is half of dHradialpump
                    dH_for_P = dHradialpump/2
                    TR_pump = (cf.gas_in.T + dH_for_P/cf.gas_in.cp_mass)/cf.gas_in.T
                    gamma = cf.gas_in.cp_mass/cf.gas_in.cv_mass
                    PR_pump = np.power(TR_pump, gamma/(gamma-1))
                    # now add full dHradialpump to enthalpy, and P increase to gas_injected
                    cf.gas_injected.HP = cf.gas_in.enthalpy_mass + dHradialpump, cf.gas_in.P * PR_pump
                else:
                    cf.DHWpump = 0

                # expansion of cooling flow contribution to turbine power
                dPexp = (cf.gas_injected.P - self.gas_out.P) * cf.dPfraction
                if dPexp > 0:
                    PRexp = (self.gas_out.P + dPexp) / self.gas_out.P
                    cf.DHWexp = fu.TurbineExpansion(cf.gas_injected, cf.gas_out, PRexp, self.Eta, cf.W, self.Polytropic_Eta)
                    self.DHW_cl_exp = self.DHW_cl_exp + cf.DHWexp
                else:
                    cf.DHWexp = 0

                # add fraction of flow to be included inlet mass flow conservation of mass error equation
                self.W_cl_eff = self.W_cl_eff + cf.W_tur_eff_fraction * cf.W

                # add to main exit flow
                Pout = self.gas_out.P
                self.gas_out = self.gas_out + cf.gas_out
                # Because Cantera assumes you are physically combining two finite quantities of gas,
                # so it recomputes the real thermodynamic result, not a mathematical average.
                # That means:
                # If the two gases weren’t identical species distribution + identical temperature,
                # the post-mix EOS solution will slightly shift pressure — even if both started at “same P”.
                #  so we must preserve pressure strictly
                self.gas_out.HP = self.gas_out.enthalpy_mass, Pout
            # return total cooling effects on turbine performance: PW delta and Wc delta
            return self.DHW_cl_exp - self.DHW_cl_pump, self.W_cl_eff

        def pressure_ratio_for_turbine_power(PR_iter):
            # Set the initial state
            # reset gas_out to gas_in (in case cooling flow added during previous iteration step)
            self.gas_out.TPY = self.gas_in.TPY
            self.gas_out.mass = self.gas_in.mass

            # power without cooling:
            # 1.6.0.8 renaming: gross power excl. mech. losses = DHW, mechanical power output = PW
            # PW_PR = fu.TurbineExpansion(self.gas_in, self.gas_out, PR_iter, self.Eta, None, self.Polytropic_Eta)
            DHW_PR = fu.TurbineExpansion(self.gas_in, self.gas_out, PR_iter, self.Eta, None, self.Polytropic_Eta)

            # cooling flow effects
            if self.CoolingFlows != None:
                self.dDHWcl, self.W_cl_eff = CalcCoolingFlowEffects()
                DHW_PR = DHW_PR + self.dDHWcl
            else:
                self.dDHWcl = 0
                self.W_cl_eff = 0

            PW_PR = DHW_PR * self.Etamechdes

            return (PW_PR - self.PW)/self.PW

        if Mode == 'DP':
        # ******************** DP design mode *************************
            self.W_cl_eff = 0
            if self.TurbineType == 'GG':    # gas generator or fan lpt turbine, providing all power required by compressor(s) or fan
                # this turbine is providing all the power required by the shaft

                # 1.6.0.8 adding thermodynamic power excl. mech. losses = DHW, mechanical power output = PW
                # self.PW = -self.shaft.PW_sum /  self.Etamechdes
                self.PW = -self.shaft.PW_sum
                self.DHW = self.PW / self.Etamechdes

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
                Pout = self.owner.ambient.Psa / PRdesuntilAmbient
                self.PRdes = self.gas_in.P/Pout
                self.PR = self.PRdes

                # 1.6.0.8 adding thermodynamic power excl. mech. losses = DHW, mechanical power output = PW
                # self.PW = fu.TurbineExpansion(self.gas_in, self.gas_out, self.PRdes, self.Etades, None, self.Polytropic_Eta)
                self.DHW = fu.TurbineExpansion(self.gas_in, self.gas_out, self.PRdes, self.Etades, None, self.Polytropic_Eta)
                # v1.2
                # cooling flow effects
                if self.CoolingFlows != None:
                    self.dDHWcl, self.W_cl_eff = CalcCoolingFlowEffects()
                    self.DHW = self.DHW + self.dDHWcl

                self.PW = self.DHW * self.Etamechdes

                # 1.6.0.8 adding thermodynamic power excl. mech. losses = DHW, mechanical power output = PW
                # self.shaft.PW_sum = self.shaft.PW_sum + self.PW * self.Etamechdes
                self.shaft.PW_sum = self.shaft.PW_sum + self.PW

            # reset gas_out to gaspath_conditions dictionary (because link broken by adding cooling flow to gas_out
            #                                                self.gas_out = self.gas_out + cf.gas_out)
            self.owner.gaspath_conditions[self.station_out] = self.gas_out

            self.PWdes = self.PW

            # v1.2 recalculate self.Wcdes adding cooling flow
            self.Wcdes = (self.Wdes + self.W_cl_eff) * fg.GetFlowCorrectionFactor(self.gas_inDes)

            # 1.6
            # self.map.ReadMapAndSetScaling(self.Ncdes, self.Wcdes, self.PRdes, self.Etades)
            self.ReadTurboMapAndSetScaling()

            # add states and errors
            # rotor speed state is same as compressor's
            self.owner.states = np.append(self.owner.states, 1)
            self.istate_beta = self.owner.states.size-1
            # error for equation gas_in.wc = wcmap
            self.owner.errors = np.append(self.owner.errors, 0)
            self.ierror_wc = self.owner.errors.size-1
            # shaft power error
            if self.TurbineType == 'GG':
                self.owner.errors = np.append(self.owner.errors, 0)
                self.ierror_shaftpw = self.owner.errors.size-1
            # calculate parameters for output
            self.N = self.Nc * fg.GetRotorspeedCorrectionFactor(self.gas_in)
        # ******************** end DP design mode *************************

        # ******************** OD off design mode *************************
        else:
            if self.TurbineType == 'GG':
                self.N = self.owner.states[self.shaft.istate] * self.Ndes
            self.Nc = self.N / fg.GetRotorspeedCorrectionFactor(self.gas_in)

            self.Wc, self.PR, self.Eta = self.map.GetScaledMapPerformance(self.Nc, self.owner.states[self.istate_beta])
            self.W = self.Wc / fg.GetFlowCorrectionFactor(self.gas_in)

            # 1.6.0.8 renaming: gross power excl. mech. losses = DHW (added), mechanical power output = PW
            # self.PW = fu.TurbineExpansion(self.gas_in, self.gas_out, self.PR, self.Eta, None, self.Polytropic_Eta)
            self.DHW = fu.TurbineExpansion(self.gas_in, self.gas_out, self.PR, self.Eta, None, self.Polytropic_Eta)

            # v1.2
            if self.CoolingFlows != None:
                self.dDHWcl, self.W_cl_eff = CalcCoolingFlowEffects()
                # 1.6.0.8 renaming: gross power excl. mech. losses = DHW (added), mechanical power output = PW
                # self.PW = self.PW + self.dPWcl
                self.DHW = self.DHW + self.dDHWcl
            self.owner.errors[self.ierror_wc ] = (self.W - fu.scalar(self.gas_in.mass) - self.W_cl_eff) / self.Wdes

            # 1.6.0.8 renaming: gross power excl. mech. losses = DHW (added), mechanical power output = PW
            self.PW = self.DHW * self.Etamechdes

            # 1.6.0.8
            # self.shaft.PW_sum = self.shaft.PW_sum + self.PW * self.Etamechdes
            self.shaft.PW_sum = self.shaft.PW_sum + self.PW
            if self.TurbineType == 'GG':
                self.owner.errors[self.ierror_shaftpw] = self.shaft.PW_sum / self.PWdes

            # reset gas_out to gaspath_conditions dictionary (because link broken by adding cooling flow to gas_out
            #                                                self.gas_out = self.gas_out + cf.gas_out)
            self.owner.gaspath_conditions[self.station_out] = self.gas_out
        # ******************** end OD off design mode *************************

        return self.gas_out

    # v1.2
    def PrintPerformance(self, Mode, PointTime):
        super().PrintPerformance(Mode, PointTime)
        if self.CoolingFlows != None:
            for coolingflow in self.CoolingFlows:
                coolingflow.PrintPerformance(Mode, PointTime)

    # 2.0.0.0
    def get_outputs(self):
        out = super().get_outputs()

        if self.CoolingFlows != None:
            for coolingflow in self.CoolingFlows:
                out.update(coolingflow.get_outputs())

        return out