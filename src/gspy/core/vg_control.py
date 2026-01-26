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
import gspy.core.system as fsys
from gspy.core.base_component import TComponent

class TVG_Control(TComponent):
    def __init__(self, name, MapFileName,
                 DP_inputvalue, DP_outputvalue):
        super().__init__(name, MapFileName, None) # no control controlling a control (yet)
        self.DP_inputvalue = DP_inputvalue
        self.DP_outputvalue = DP_outputvalue
        self.outputvalue = None
        self.inputvalue = None

    def Get_outputvalue_from_schedule(self, inputvalue):
        # inputvalue often Nc corrected rotor speed

        # the next line merely is an example schedule....
        # adapt to you own liking...
        self.outputvalue = (1 - inputvalue/self.DP_inputvalue) * 300

        self.inputvalue = inputvalue
        return self.outputvalue

    def Run(self, Mode, PointTime):
        if Mode == 'DP':
            # in case of DP control
            Return = self.DP_inputvalue
        else:
            pass

    #  1.1 WV
    def AddOutputToDict(self, Mode):
        if Mode == 'DP':
            fsys.output_dict["Control_input_"+self.name] = None
            fsys.output_dict["Control_output_"+self.name] = None
        else:
            fsys.output_dict["Control_input_"+self.name] = self.inputvalue
            fsys.output_dict["Control_output_"+self.name] = self.outputvalue
