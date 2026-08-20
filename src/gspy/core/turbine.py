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
from scipy.optimize import root_scalar

import gspy.core.utils as fu
from gspy.core.turbo_component import TTurboComponent
from gspy.core.turbinemap import TTurbineMap

class TTurbine(TTurboComponent):
    def __init__(self, 
                 *,
                 Etamechdes,
                 TurbineType,
                 CoolingFlows=None,
                 **kwargs):
        super().__init__(**kwargs)
        self.Etamechdes = Etamechdes # spool mechanical efficiency
        self.TurbineType = TurbineType  # gas generator turbine providing all power required by compressor(s)
        # TurbineType = 'PT'  # heavy duty single spool or power turbine, providing power to external loads
        # only call SetDPparameters in instantiable classes in init creator
        self.map = TTurbineMap(self, self.name + '_map', self.MapFileName, '', '', self.shaft_id, self.Ncmapdes, self.Betamapdes)
        self.CoolingFlows = CoolingFlows

    # 1.6 virtual method CreateMap will be called in ancestor TTurboComponent
    # for either single map or series of maps in case of variable geometry with multipe maps for example
    def CreateMap(self, MapFilePath, shaft_id, Ncmapdes, Betamapdes):
        return TTurbineMap(self, self.name + '_map', MapFilePath, '', '', shaft_id, Ncmapdes, Betamapdes)

    def GetTotalPRdesUntilAmbient(self):
        # always at least one gas path component downstream a turbine (if only one: exhaust)
        # this means Exhaust PRdes must be 1 or corresponding to some error loss (total-to-total)
        # (Exhast PR (off-design) actually is total to throat static PR)
        PRdesuntilAmbient = 1
        agaspathcomponent = self.system.get_gaspathcomponent_object_inlet_stationnr(self.station_out)
        while agaspathcomponent != None:
            PRdesuntilAmbient = PRdesuntilAmbient * agaspathcomponent.PRdes
            agaspathcomponent = self.system.get_gaspathcomponent_object_inlet_stationnr(agaspathcomponent.station_out)
        return PRdesuntilAmbient

    def Run(self, Mode, PointTime):

        super().Run(Mode, PointTime)
        Sin = self.fs_in.gas_q.entropy_mass
        Pin = self.fs_in.gas_q.P

        def CalcCoolingFlowEffects():
            self.DHW_cl_pump = 0
            self.DHW_cl_exp = 0
            self.W_cl_eff = 0
            Ekin_at_R1 = np.square(np.pi*self.N/60)
            # we are assuming not liquid water in the bleed flows, so also not in the cooling flows
            for cf in self.CoolingFlows:
                cf.Run(Mode, PointTime)  # this calculates the bleed flow rate, set fs_injected to fs_in
                # pumping power for blade cooling
                if cf.Rexit > 0:
                    # power taken from shaft for accelerating the cooling flow in circumferential direction
                    dhradialpump = Ekin_at_R1 * np.square(cf.Rexit)
                    cf.DHWpump =  dhradialpump * cf.W
                    self.DHW_cl_pump += cf.DHWpump
                    # isentropic compression due to 'radial pump' action
                    # in the rotating frame dH increase is half of dHradialpump
                    dH_for_P = dhradialpump/2
                    TR_pump = (cf.fs_in.T + dH_for_P/cf.fs_in.gas_q.cp_mass)/cf.fs_in.T
                    gamma = cf.fs_in.gas_q.cp_mass/cf.fs_in.gas_q.cv_mass
                    PR_pump = np.power(TR_pump, gamma/(gamma-1))
                    # now add full dHradialpump to enthalpy, and P increase to fs_injected
                    cf.fs_injected.HP = cf.fs_in.gas_q.enthalpy_mass + dhradialpump, cf.fs_in.P * PR_pump
                else:
                    cf.DHWpump = 0

                # expansion of cooling flow contribution to turbine power
                dPexp = (cf.fs_injected.P - self.fs_out.P) * cf.dPfraction
                if dPexp > 0:
                    PRexp = (self.fs_out.P + dPexp) / self.fs_out.P
                    # 2.1
                    # cf.DHWexp = fu.TurbineExpansion(cf.fs_injected, cf.fs_out, PRexp, self.Eta, cf.W, 
                    #                                 self.Polytropic_DP_eta if Mode == 'DP' else 0)
                    cf.fs_out, cf.DHWexp = cf.fs_injected.expand_real_eta(
                        PR=PRexp,
                        out=cf.fs_out,
                        eta=self.Eta,
                        polytropic_eta=self.Polytropic_DP_eta if Mode == 'DP' else False
                    )                    

                    self.DHW_cl_exp += cf.DHWexp
                else:
                    cf.DHWexp = 0

                # add fraction of flow to be included inlet mass flow conservation of mass error equation
                self.W_cl_eff += cf.W_tur_eff_fraction * cf.W

                # add to main exit flow
                Pout = self.fs_out.P
                # self.fs_out = self.fs_out + cf.fs_out
                # Because Cantera assumes you are physically combining two finite quantities of gas,
                # so it recomputes the real thermodynamic result, not a mathematical average.
                # That means:
                # If the two gases weren’t identical species distribution + identical temperature,
                # the post-mix EOS solution will slightly shift pressure — even if both started at “same P”.
                #  so we must preserve pressure strictly
                # self.fs_out.HP = self.fs_out.enthalpy_mass, Pout
                self.fs_out.mix_from(self.fs_out, cf.fs_out, P_out=Pout)

            # return total cooling effects on turbine performance: PW delta and Wc delta
            return self.DHW_cl_exp - self.DHW_cl_pump, self.W_cl_eff

        def pressure_ratio_for_turbine_power(PR_iter):
            # Set the initial state
            # reset fs_out to fs_in (in case cooling flow added during previous iteration step)
            self.fs_out.gas_q.TPY = self.fs_in.gas_q.TPY
            self.fs_out.gas_q.mass = self.fs_in.gas_q.mass

            # 2.1
            # power without cooling:
            # 1.6.0.8 renaming: gross power excl. mech. losses = DHW, mechanical power output = PW
            # PW_PR = fu.TurbineExpansion(self.fs_in, self.fs_out, PR_iter, self.Eta, None, self.Polytropic_Eta)
            # DHW_PR = fu.TurbineExpansion(self.fs_in, self.fs_out, PR_iter, self.Eta, None, 
            #                              self.Polytropic_DP_eta if Mode == 'DP' else 0)
            self.fs_out, DHW_PR = self.fs_in.expand_real_eta(
                PR=PR_iter,
                out=self.fs_out,
                eta=self.Eta,
                polytropic_eta=self.Polytropic_DP_eta if Mode == 'DP' else False
            )

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
                initial_guess = 1.9

                # Use scipy.optimize.root to find the pressure ratio
                # solution = root(pressure_ratio_for_turbine_power, initial_guess)
                solution = root_scalar(
                    pressure_ratio_for_turbine_power,
                    x0=1.9,
                    x1=2.0,      # secant method
                    method='secant'
                )

                # Check if the solution converged
                if solution.converged:
                    self.PRdes = solution.root
                else:
                    raise ValueError(self.name + "DP PR iteration did not converge")

                # calculate parameters for output
                self.PR = self.PRdes
                self.shaft.PW_sum = 0
            else:
                PRdesuntilAmbient = self.GetTotalPRdesUntilAmbient()
                Pout = self.system.ambient.Psa / PRdesuntilAmbient
                self.PRdes = self.fs_in.P/Pout
                self.PR = self.PRdes

                # 1.6.0.8 adding thermodynamic power excl. mech. losses = DHW, mechanical power output = PW
                # self.PW = fu.TurbineExpansion(self.fs_in, self.fs_out, self.PRdes, self.Etades, None, self.Polytropic_Eta)
                # self.DHW = fu.TurbineExpansion(self.fs_in, self.fs_out, self.PRdes, self.Etades, None, 
                #                                self.Polytropic_DP_eta)
                self.fs_out, self.DHW = self.fs_in.expand_real_eta(
                    PR=self.PRdes,
                    out=self.fs_out,
                    eta=self.Etades,
                    polytropic_eta=self.Polytropic_DP_eta if Mode == 'DP' else False
                )

                # v1.2
                # cooling flow effects
                if self.CoolingFlows != None:
                    self.dDHWcl, self.W_cl_eff = CalcCoolingFlowEffects()
                    self.DHW = self.DHW + self.dDHWcl

                self.PW = self.DHW * self.Etamechdes

                # 1.6.0.8 adding thermodynamic power excl. mech. losses = DHW, mechanical power output = PW
                # self.shaft.PW_sum = self.shaft.PW_sum + self.PW * self.Etamechdes
                self.shaft.PW_sum = self.shaft.PW_sum + self.PW

            # reset fs_out to gaspath_conditions dictionary (because link broken by adding cooling flow to fs_out
            #                                                self.fs_out = self.fs_out + cf.fs_out)
            self.system.gaspath_conditions[self.station_out] = self.fs_out

            self.PWdes = self.PW

            # v1.2 recalculate self.Wcdes adding cooling flow
            # self.Wcdes = (self.Wdes + self.W_cl_eff) * fu.GetFlowCorrectionFactor(self.fs_in_des)
            self.Wcdes = (self.fs_in_des.W + self.W_cl_eff) * fu.GetFlowCorrectionFactor(self.fs_in_des)
    
            # 1.6
            # self.map.ReadMapAndSetScaling(self.Ncdes, self.Wcdes, self.PRdes, self.Etades)
            self.ReadTurboMapAndSetScaling()

            # add states and errors
            # rotor speed state is same as compressor's
            # self.system.states = np.append(self.system.states, 1)
            # self.istate_beta = self.system.states.size-1
            self.istate_beta = self.system.add_state(self.name + '_beta', 1.0)
            # error for equation fs_in.wc = wcmap
            # self.system.errors = np.append(self.system.errors, 0)
            # self.ierror_wc = self.system.errors.size-1
            self.ierror_wc = self.system.add_error(self.name + '_wc', 0.0)
            # shaft power error
            if self.TurbineType == 'GG':
                # self.system.errors = np.append(self.system.errors, 0)
                # self.ierror_shaftpw = self.system.errors.size-1
                self.ierror_shaftpw = self.system.add_error(self.name + '_shaftpw', 0.0)
            # calculate parameters for output
            self.N = self.Nc * fu.GetRotorspeedCorrectionFactor(self.fs_in)
        # ******************** end DP design mode *************************

        # ******************** OD off design mode *************************
        else:
            if self.TurbineType == 'GG':
                self.N = self.system.states[self.shaft.istate] * self.Ndes
            self.Nc = self.N / fu.GetRotorspeedCorrectionFactor(self.fs_in)

            self.Wc, self.PR, self.Eta = self.map.GetScaledMapPerformance(self.Nc, self.system.states[self.istate_beta])
            self.W = self.Wc / fu.GetFlowCorrectionFactor(self.fs_in)

            # 2.1
            # 1.6.0.8 renaming: gross power excl. mech. losses = DHW (added), mechanical power output = PW
            # self.PW = fu.TurbineExpansion(self.fs_in, self.fs_out, self.PR, self.Eta, None, self.Polytropic_Eta)
            # self.DHW = fu.TurbineExpansion(self.fs_in, self.fs_out, self.PR, self.Eta, None, 0)
            self.fs_out, self.DHW = self.fs_in.expand_real_eta(
                PR=self.PR,
                out=self.fs_out,
                eta=self.Eta,
                polytropic_eta = False # OD always False
            )
            
            # v1.2
            if self.CoolingFlows != None:
                self.dDHWcl, self.W_cl_eff = CalcCoolingFlowEffects()
                # 1.6.0.8 renaming: gross power excl. mech. losses = DHW (added), mechanical power output = PW
                # self.PW = self.PW + self.dPWcl
                self.DHW = self.DHW + self.dDHWcl
            self.system.errors[self.ierror_wc ] = (self.W - fu.scalar(self.fs_in.mass) - self.W_cl_eff) / self.fs_in_des.W

            # 1.6.0.8 renaming: gross power excl. mech. losses = DHW (added), mechanical power output = PW
            self.PW = self.DHW * self.Etamechdes

            # 1.6.0.8
            # self.shaft.PW_sum = self.shaft.PW_sum + self.PW * self.Etamechdes
            self.shaft.PW_sum = self.shaft.PW_sum + self.PW
            if self.TurbineType == 'GG':
                self.system.errors[self.ierror_shaftpw] = self.shaft.PW_sum / self.PWdes

            # reset fs_out to gaspath_conditions dictionary (because link broken by adding cooling flow to fs_out
            #                                                self.fs_out = self.fs_out + cf.fs_out)
            self.system.gaspath_conditions[self.station_out] = self.fs_out
        # ******************** end OD off design mode *************************

        self.Add_Q_to_fs_out()

        return self.fs_out

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