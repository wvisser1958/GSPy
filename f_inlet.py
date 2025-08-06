# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#    http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import numpy as np
import cantera as ct
import f_global as fg
import f_system as fsys
from f_gaspath import TGaspath

class TInlet(TGaspath):
    def __init__(self, name, MapFileName, ControlComponent, stationin, stationout, Wdes, PRdes):  # Constructor of the class
        super().__init__(name, MapFileName, ControlComponent, stationin, stationout)
        self.Wdes = Wdes
        self.PRdes = PRdes

    def Run(self, Mode, PointTime):
        if Mode == 'DP':
            fsys.gaspath_conditions[self.stationin].mass = self.Wdes
        super().Run(Mode, PointTime)
        self.GasIn.TP = self.GasIn.T, self.GasIn.P
        if Mode == 'DP':
            self.GasIn.mass = self.Wdes
            self.wcdes = self.GasIn.mass * fg.GetFlowCorrectionFactor(self.GasIn)
            self.wc = self.wcdes
            self.PR = self.PRdes
            fsys.states = np.append(fsys.states, 1)
            self.istate_wc = fsys.states.size-1   # add state for corrected inlet flow wc more stable... state staying closer to 1 at high altitude
        else:
            self.wc = fsys.states[self.istate_wc] * self.wcdes
            self.GasIn.mass = self.wc / fg.GetFlowCorrectionFactor(self.GasIn)
            self.GasOut.TP = self.GasIn.T, self.GasIn.P * self.PRdes
            # this inlet has constant PR, no OD PR yet (use manual input in code here, or make PR, Ram recovery map)
            self.PR = self.PRdes
        self.GasOut.TP = self.GasIn.T, self.GasIn.P * self.PR
        self.GasOut.mass = self.GasIn.mass
        self.RD = self.GasIn.mass * fsys.Ambient.V
        # add ram drag to system level ram drag (note that multiple inlets may exist)
        fsys.RD = fsys.RD + self.RD
        return self.GasOut