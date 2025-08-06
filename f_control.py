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
    def __init__(self, name, MapFileName, DP_inputvalue, OD_startvalue, OD_endvalue, OD_pointstepvalue, OD_controlledparname):
        super().__init__(name, MapFileName, '') # no control controlling a control (yet)
        self.DP_inputvalue = DP_inputvalue
        self.OD_startvalue = OD_startvalue
        self.OD_endvalue = OD_endvalue
        self.OD_pointstepvalue = OD_pointstepvalue
        self.OD_controlledparname = OD_controlledparname
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
            # 1.1 WV
            if self.OD_controlledparname == None:
                # just simple open loop control
                self.Inputvalue = self.OD_startvalue + self.OD_inputpoints[PointTime] * self.OD_pointstepvalue
            else:
                # input is coming from state, iterating toward value satisfying control equation
                self.Inputvalue = self.DP_inputvalue * fsys.states[self.istate_control]

    # 1.1 WV PostRun evaluates the equation for controlling parameter named OD_controlledparName to input
    def PostRun(self, Mode, PointTime):
        # super().PostRun(Mode, PointTime)
        if self.OD_controlledparname != None:
            if Mode == 'DP':
                fsys.states = np.append(fsys.states, 1)
                self.istate_control = fsys.states.size-1
                fsys.errors = np.append(fsys.errors, 0)
                self.ierror_control = fsys.errors.size-1
                #  get control parameter DP value
                self.DP_controlparvalue = fsys.output_dict[self.OD_controlledparname]
            else:
                # get control demanded (set point) parameter value from input
                controlpar_demand = self.OD_startvalue + self.OD_inputpoints[PointTime] * self.OD_pointstepvalue
                #  get control parameter current value
                lastrownumber = len(fsys.OutputTable)
                controlparvalue = fsys.output_dict[self.OD_controlledparname]
                fsys.errors[self.ierror_control] = (controlpar_demand - controlparvalue) / self.DP_controlparvalue

    def GetOutputTableColumnNames(self):
        return super().GetOutputTableColumnNames() + ["Control_input_"+self.name]

    #  1.1 WV
    def AddOutputToDict(self, Mode):
        fsys.output_dict["Control_input_"+self.name] = self.Inputvalue
