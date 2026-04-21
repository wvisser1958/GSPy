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
from gspy.core.turbo_component import TTurboComponent
from gspy.core.compressormap import TCompressorMap

class TCompressor(TTurboComponent):
    def __init__(self, owner, name,
                 MapFileName_or_dict,
                 ControlComponent,
                 station_in, station_out, shaft_id,
                 Ndes, Etades,
                 Ncmapdes, Betamapdes, PRdes,
                 SpeedOption,
                 Bleeds):    # Constructor of the class
        super().__init__(owner, name, MapFileName_or_dict, ControlComponent, station_in, station_out, shaft_id, Ndes, Etades, Ncmapdes, Betamapdes)
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
        if Mode == 'DP':
            self.PW = fu.Compression(self.gas_in, self.gas_out, self.PRdes, self.Etades, self.Polytropic_Eta)

            # 1.6 WV
            # self.map.ReadMapAndSetScaling(self.Ncdes, self.Wcdes, self.PRdes, self.Etades)
            self.ReadTurboMapAndSetScaling()

            # add states and errors
            if self.SpeedOption != 'CS':
                # 1.5
                if self.shaft.istate == None:
                    self.owner.states = np.append(self.owner.states, 1)
                    self.istate_n = self.owner.states.size-1
                    self.shaft.istate = self.istate_n
                else:
                    # already assigned (e.g. by fan or compressor upstream in the gas path)
                    self.istate_n = self.shaft.istate
            self.owner.states = np.append(self.owner.states, 1)
            self.istate_beta = self.owner.states.size-1
            # error for equation gas_in.wc = wcmap
            self.owner.errors = np.append(self.owner.errors, 0)
            self.ierror_wc = self.owner.errors.size-1
            # calculate parameters for output
            self.PR = self.PRdes
        else:
            if self.SpeedOption != 'CS':
                # self.N = self.owner.states[self.istate_n] * self.Ndes
                self.N = self.shaft.Nt
            self.Nc = self.N / fu.GetRotorspeedCorrectionFactor(self.gas_in)

            # 1.6 WV
            # self.Wc, self.PR, self.Eta = self.map.GetScaledMapPerformance(self.Nc, fsys.states[self.istate_beta])
            if self.control != None:
                  self.vg_angle = self.control.Get_outputvalue_from_schedule(self.Nc)
            self.Wc, self.PR, self.Eta = self.GetTurboMapPerformance(self.vg_angle, self.Nc, self.owner.states[self.istate_beta])

            self.PW = fu.Compression(self.gas_in, self.gas_out, self.PR, self.Eta, self.Polytropic_Eta)

            self.W = self.Wc / fu.GetFlowCorrectionFactor(self.gas_in)
            self.owner.errors[self.ierror_wc ] = (self.W - self.gas_in.mass) / self.Wdes

            # set out flow rate to W according to map
            # may deviate from self.gas_in.mass during iteration: this is to propagate the effect of mass flow error
            # to downstream components for more stable convergence in the solver (?)
            self.gas_out.mass = self.W

        # v1.2 correction for bleed flows
        dW = 0
        dHW_bleeds_total = 0
        dH = self.gas_out.enthalpy_mass - self.gas_in.enthalpy_mass
        dP = self.gas_out.P - self.gas_in.P
        if self.Bleeds != None:
            for bleed in self.Bleeds:
                Wbleed = bleed.bleedfraction * self.W
                dW = dW + Wbleed
                # dHW = dHW + (1 - bleed.dPfactor) * dH * Wbleed
                if bleed.gas_in == None:
                    #  define bleed inflow gas_in conditions
                    bleed.gas_in = ct.Quantity(self.gas_in.phase, Wbleed)
                else:
                    bleed.gas_in.TPY = self.gas_in.T, self.gas_in.P, self.gas_in.Y
                    bleed.gas_in.mass = Wbleed
                #  add to station conditions dictionary
                self.owner.gaspath_conditions[bleed.station_in] = bleed.gas_in

                # Compress Wbleed to bleed point
                dHW1 = fu.Compression(self.gas_in, bleed.gas_in, (self.gas_in.P+dP*bleed.dPfactor)/self.gas_in.P, self.Eta, self.Polytropic_Eta)
                # now delta of compression power due to the bleed is
                dHW2 = dH * Wbleed  - dHW1
                dHW_bleeds_total = dHW_bleeds_total + dHW2
                # run the bleed flow run code (default is simply the TGasPath method, sets bleed.gas_out to bleed.gas_in)
                bleed.Run(Mode, PointTime)
            self.gas_out.mass = self.gas_out.mass - dW
            self.PW = self.PW - dHW_bleeds_total

        self.shaft.PW_sum = self.shaft.PW_sum - self.PW
        return self.gas_out

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
