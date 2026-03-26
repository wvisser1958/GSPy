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
import gspy.core.sys_global as fg
from gspy.core.gaspath import TGaspath

class TInlet(TGaspath):
    def __init__(self, owner, name, MapFileName, ControlComponent, station_in, station_out, Wdes, PRdes):  # Constructor of the class
        super().__init__(owner, name, MapFileName, ControlComponent, station_in, station_out)
        self.Wdes = Wdes
        self.PRdes = PRdes

    def Run(self, Mode, PointTime):
        if Mode == 'DP':
            # Get the ambient conditions for the inlet gas_in conditions
            self.owner.gaspath_conditions[self.station_in] = self.owner.gaspath_conditions[self.owner.ambient.station_nr]
            self.owner.gaspath_conditions[self.station_in].mass = self.Wdes
        super().Run(Mode, PointTime)
        # self.gas_in.TP = self.gas_in.T, self.gas_in.P
        if Mode == 'DP':
            self.gas_in.mass = self.Wdes
            self.wcdes = self.gas_in.mass * fg.GetFlowCorrectionFactor(self.gas_in)
            self.wc = self.wcdes
            self.PR = self.PRdes
            self.owner.states = np.append(self.owner.states, 1)
            self.istate_wc = self.owner.states.size-1   # add state for corrected inlet flow wc more stable... state staying closer to 1 at high altitude
        else:
            self.wc = self.owner.states[self.istate_wc] * self.wcdes
            if self.wc < 0.001*self.wcdes:
                self.wc = 0.001*self.wcdes
            self.gas_in.mass = self.wc / fg.GetFlowCorrectionFactor(self.gas_in)
            self.gas_out.TP = self.gas_in.T, self.gas_in.P * self.PRdes
            # this inlet has constant PR, no OD PR yet (use manual input in code here, or make PR, Ram recovery map)
            self.PR = self.PRdes
        self.gas_out.TP = self.gas_in.T, self.gas_in.P * self.PR
        self.gas_out.mass = self.gas_in.mass
        self.RD = self.gas_in.mass * self.owner.ambient.V / 1000 # kN
        # add ram drag to system level ram drag (note that multiple inlets may exist)
        self.owner.RD = self.owner.RD + self.RD
        return self.gas_out