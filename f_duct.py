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
from f_gaspath import TGaspath

class TDuct(TGaspath):
    def __init__(self, name, MapFileName, stationin, stationout, PRdes):    # Constructor of the class
        super().__init__(name, MapFileName, stationin, stationout)
        self.PRdes = PRdes

    def Run(self, Mode, PointTime):
        super().Run(Mode, PointTime)
        if Mode == 'DP':
            self.PR = self.PRdes
        else:
            # this duct has constant PR, no OD PR yet (use manual input in code here, or make PR map)
            self.PR = self.PRdes
        self.GasOut.TP = self.GasIn.T, self.GasIn.P*self.PR
        # calculate parameters for output
        self.Wc = self.GasIn.mass * fg.GetFlowCorrectionFactor(self.GasIn)
        return self.GasOut