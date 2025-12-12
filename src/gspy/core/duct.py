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

class TDuct(TGaspath):
    def __init__(self, name, MapFileName, ControlComponent, stationin, stationout, PRdes):    # Constructor of the class
        super().__init__(name, MapFileName, ControlComponent, stationin, stationout)
        self.PRdes = PRdes

    def Run(self, Mode, PointTime):
        super().Run(Mode, PointTime)
        # v1.2 dprel proportional to Wc^2
        dprel = (1 - self.PRdes) * np.square(self.Wc/self.Wcdes)
        self.PR = 1 - dprel
        self.GasOut.TP = self.GasIn.T, self.GasIn.P*self.PR
        return self.GasOut