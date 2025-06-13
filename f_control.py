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
from f_base_component import TComponent

class TControl(TComponent):
    def __init__(self, name, MapFileName, DP_inputvalue, OD_startvalue, OD_endvalue, OD_pointstepvalue):
        super().__init__(name, MapFileName)
        self.DP_inputvalue = DP_inputvalue
        self.OD_startvalue = OD_startvalue
        self.OD_endvalue = OD_endvalue
        self.OD_pointstepvalue = OD_pointstepvalue
        if (abs(OD_pointstepvalue) == 0) or ((OD_endvalue - OD_startvalue) * OD_pointstepvalue < 0):
            raise Exception("Invalid control variable begin, end and step values")

    def Get_OD_inputpoints(self):
        pointcount = round(abs((self.OD_endvalue - self.OD_startvalue) / self.OD_pointstepvalue) + 1)
        self.OD_inputpoints = np.arange(0, pointcount, 1)
        return np.arange(0, pointcount, 1)

    def Run(self, Mode, PointTime):
        if Mode == 'DP':
            # in case of DP control
            self.Inputvalue = self.DP_inputvalue
        else:
            self.Inputvalue = self.OD_startvalue + self.OD_inputpoints[PointTime] * self.OD_pointstepvalue

    def GetOutputTableColumnNames(self):
        return super().GetOutputTableColumnNames() + ["Wf_"+self.name]

    def AddOutputToTable(self, Mode, rownr):
        fsys.OutputTable.loc[rownr, "Wf_"+self.name] = self.Inputvalue