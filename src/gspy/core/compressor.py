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
import gspy.core.utils as fu
from gspy.core.flow_state import TFlowState
from gspy.core.turbo_component import TTurboComponent
from gspy.core.compressormap import TCompressorMap


class TCompressor(TTurboComponent):
    def __init__(self, 
                 *,
                PRdes,
                 SpeedOption,
                 Bleeds=None,
                 **kwargs):    # Constructor of the class
        super().__init__(**kwargs)
        # only call SetDPparameters in instantiable classes in init creator
        self.PRdes = PRdes
        self.SpeedOption = SpeedOption
        self.Bleeds = Bleeds

    # 1.6 virtual method CreateMap will be called in ancestor TTurboComponent
    # for either single map or series of maps in case of variable geometry with multipe maps for example
    def CreateMap(self, MapFilePath, shaft_id, Ncmapdes, Betamapdes):
        return TCompressorMap(self, self.name + '_map', MapFilePath, '', '', shaft_id, Ncmapdes, Betamapdes)

    def Run(self, Mode, PointTime):
        super().Run(Mode, PointTime)
        # note that fs_in_q is the flow state with Q added, if any...

        if Mode == 'DP':
            self.fs_out, self.PW = self.fs_in_q.compress_real_eta(
                PR=self.PRdes,
                out=self.fs_out,
                eta=self.Etades,
                Polytropic_Eta=self.Polytropic_DP_eta
            )

            # 1.6 WV
            # self.map.ReadMapAndSetScaling(self.Ncdes, self.Wcdes, self.PRdes, self.Etades)
            self.ReadTurboMapAndSetScaling()

            # add states and errors
            if self.SpeedOption != 'CS':
                # 1.5
                if self.shaft.istate == None:
                    # self.system.states = np.append(self.system.states, 1)
                    # self.istate_n = self.system.states.size-1
                    self.istate_n = self.system.add_state(self.name + '_N', 1.0)
                    self.shaft.istate = self.istate_n
                else:
                    # already assigned (e.g. by fan or compressor upstream in the gas path)
                    self.istate_n = self.shaft.istate
            # self.system.states = np.append(self.system.states, 1)
            # self.istate_beta = self.system.states.size-1
            self.istate_beta = self.system.add_state(self.name + '_beta', 1.0)
            # error for equation fs_in.wc = wcmap
            # self.system.errors = np.append(self.system.errors, 0)
            # self.ierror_wc = self.system.errors.size-1
            self.ierror_wc = self.system.add_error(self.name + '_wc', 0.0)
            # calculate parameters for output
            self.PR = self.PRdes
        else:
            if self.SpeedOption != 'CS':
                # self.N = self.owner.states[self.istate_n] * self.Ndes
                self.N = self.shaft.Nt
            self.Nc = self.N / fu.GetRotorspeedCorrectionFactor(self.fs_in)

            # 1.6 WV
            # self.Wc, self.PR, self.Eta = self.map.GetScaledMapPerformance(self.Nc, fsys.states[self.istate_beta])
            if self.control != None:
                  self.vg_angle = self.control.Get_outputvalue_from_schedule(self.Nc)
            self.Wc_map, self.PR, self.Eta = self.GetTurboMapPerformance(self.vg_angle, self.Nc, self.system.states[self.istate_beta])

            self.fs_out, self.PW = self.fs_in_q.compress_real_eta(
                PR=self.PR,
                out=self.fs_out,
                eta=self.Eta,
                Polytropic_Eta=False  # OD eta always isentropic
            )

            self.W_map = self.Wc_map / fu.GetFlowCorrectionFactor(self.fs_in)
            self.system.errors[self.ierror_wc ] = (self.W_map - self.fs_in.W) / self.fs_in_des.W

            # set out flow rate to W according to map
            # may deviate from self.fs_in.mass during iteration: this is to propagate the effect of mass flow error
            # to downstream components for more stable convergence in the solver (?)
            self.fs_out.W_gas = self.W_map            

        # v1.2 correction for bleed flows
        dW = 0
        dHW_bleeds_total = 0
        # dH due to compression from fs_in_q
        dH = self.fs_out.gas_q.enthalpy_mass - self.fs_in_q.gas_q.enthalpy_mass
        dP = self.fs_out.gas_q.P - self.fs_in_q.gas_q.P
        if self.Bleeds != None:
            for bleed in self.Bleeds:
                Wbleed = bleed.bleedfraction * self.W
                dW = dW + Wbleed
                # dHW = dHW + (1 - bleed.dPfactor) * dH * Wbleed
                if bleed.fs_in == None:
                    #  define bleed inflow fs_in conditions
                    bleed.fs_in = ct.Quantity(self.fs_in_q.phase, Wbleed)
                else:
                    bleed.fs_in.TPY = self.fs_in_q.T, self.fs_in_q.P, self.fs_in_q.Y
                    bleed.fs_in.mass = Wbleed
                #  add to station conditions dictionary
                self.system.gaspath_conditions[bleed.station_in] = bleed.fs_in

                # Compress Wbleed to bleed point
                #  2.1
                # dHW1 = fu.Compression(self.fs_in, bleed.fs_in, (self.fs_in.P+dP*bleed.dPfactor)/self.fs_in.P, self.Eta, 
                #                       self.Polytropic_DP_eta if Mode=='DP' else 0)
                bleed.fs_in, dHW1 = self.fs_in_q.compress_real_eta(
                    PR=(self.fs_in_q.P+dP*bleed.dPfactor)/self.fs_in_q.P,
                    out=bleed.fs_in,
                    eta=self.Eta,
                    Polytropic_Eta=self.Polytropic_DP_eta if Mode=='DP' else False
                )

                # now delta of compression power due to the bleed is
                dHW2 = dH * Wbleed  - dHW1
                dHW_bleeds_total = dHW_bleeds_total + dHW2
                # run the bleed flow run code (default is simply the TGasPath method, sets bleed.fs_out to bleed.fs_in)
                bleed.Run(Mode, PointTime)
            self.fs_out.mass = self.fs_out.mass - dW
            self.PW = self.PW - dHW_bleeds_total

        self.shaft.PW_sum = self.shaft.PW_sum - self.PW

        self.Add_Q_to_fs_out()
        
        return self.fs_out

    # v1.2
    def PrintPerformance(self, Mode, PointTime):
        super().PrintPerformance(Mode, PointTime)
        if self.Bleeds != None:
            for bleed in self.Bleeds:
                bleed.PrintPerformance(Mode, PointTime)

    # 2.0.0.0
    def get_outputs(self):
        out = super().get_outputs()
        if self.Bleeds != None:
            for bleed in self.Bleeds:
                out.update(bleed.get_outputs())
        return out
