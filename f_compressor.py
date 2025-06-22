# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#    http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import math
import numpy as np
from scipy.interpolate import RegularGridInterpolator
import cantera as ct
import f_global as fg
import f_system as fsys
import f_utils as fu
from f_turbo_component import TTurboComponent
from f_compressormap import TCompressorMap

class TCompressor(TTurboComponent):
    def __init__(self, name, MapFileName, stationin, stationout, ShaftNr, Ndes, Etades, Ncmapdes, Betamapdes, PRdes, SpeedOption):    # Constructor of the class
        super().__init__(name, MapFileName, stationin, stationout, ShaftNr, Ndes, Etades)
        # only call SetDPparameters in instantiable classes in init creator
        self.PRdes = PRdes
        self.SpeedOption = SpeedOption
        self.map = TCompressorMap(self, name + '_map', MapFileName, '', '', ShaftNr, Ncmapdes, Betamapdes)

    def Run(self, Mode, PointTime):
        super().Run(Mode, PointTime)
        if Mode == 'DP':
            self.PW = fu.Compression(self.GasIn, self.GasOut, self.PRdes, self.Etades)
            self.shaft.PW_sum = self.shaft.PW_sum - self.PW

            self.map.ReadMapAndSetScaling(self.Ncdes, self.Wcdes, self.PRdes, self.Etades)

            # add states and errors
            if self.SpeedOption != 'CS':
                fsys.states = np.append(fsys.states, 1)
                self.istate_n = fsys.states.size-1
                self.shaft.istate = self.istate_n
            fsys.states = np.append(fsys.states, 1)
            self.istate_beta = fsys.states.size-1
            # error for equation GasIn.wc = wcmap
            fsys.errors = np.append(fsys.errors, 0)
            self.ierror_wc = fsys.errors.size-1
            # calculate parameters for output
            self.PR = self.PRdes
        else:
            if self.SpeedOption != 'CS':
                self.N = fsys.states[self.istate_n] * self.Ndes
            self.Nc = self.N / fg.GetRotorspeedCorrectionFactor(self.GasIn)

            self.Wc, self.PR, self.Eta = self.map.GetScaledMapPerformance(self.Nc, fsys.states[self.istate_beta])

            self.PW = fu.Compression(self.GasIn, self.GasOut, self.PR, self.Eta)

            self.shaft.PW_sum = self.shaft.PW_sum - self.PW
            self.W = self.Wc / fg.GetFlowCorrectionFactor(self.GasIn)
            fsys.errors[self.ierror_wc ] = (self.W - self.GasIn.mass) / self.Wdes

            # set out flow rate to W according to map
            # may deviate from self.GasIn.mass during iteration: this is to propagate the effect of mass flow error
            # to downstream components for more stable convergence in the solver (?)
            self.GasOut.mass = self.W

        return self.GasOut