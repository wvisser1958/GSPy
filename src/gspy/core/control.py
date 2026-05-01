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
from gspy.core.base_component import TComponent

class TControl(TComponent):
    def __init__(self, owner, name, map_file_name,
                 DP_input_value,
                 OD_start_value, OD_end_value, OD_point_step_value,
                 OD_controlled_parameter_name):
        # note that, if OD_controlledparname != None:
        #    OD_startvalue, OD_endvalue, OD_pointstepvalue represent the values of the OD_controlledparname
        # else:
        #    they are the direct input values of the component using this control (like fuel flow for a combustor for example)
        # DP_inputvalue always is direct input values of the component using this control
        super().__init__(owner, name, map_file_name, None) # no control controlling a control (yet)
        # 2.1
        self.Re_init(map_file_name,
                    DP_input_value,
                    OD_start_value, OD_end_value, OD_point_step_value,
                    OD_controlled_parameter_name)

    # 2.1
    def Re_init(self, map_file_name,
                 DP_input_value,
                 OD_start_value, OD_end_value, OD_point_step_value,
                 OD_controlled_parameter_name):
        self.map_filename = map_file_name # for use in customized child classes, e.g. with lookup tables
        self.DP_input_value = DP_input_value
        self.OD_start_value = OD_start_value
        self.OD_end_value = OD_end_value
        self.OD_point_step_value = OD_point_step_value
        self.OD_controlled_parameter_name = OD_controlled_parameter_name
        self.control_parameter_demand = None
        if not ((OD_point_step_value == None) and (OD_end_value == None)): # single point input
            if (abs(OD_point_step_value) == 0) or ((OD_end_value - OD_start_value) * OD_point_step_value < 0):
                raise Exception("Invalid control variable begin, end and step values")

    # 2.1
    # def get_OD_input_points(self):
    def get_OD_input_points(self, start_point_time = 0):
        if (self.OD_end_value == None) or (self.OD_point_step_value == None):
            point_count = 1
        else:
            point_count = round(abs((self.OD_end_value - self.OD_start_value) / self.OD_point_step_value) + 1)


        point_times = start_point_time + np.arange(point_count)
        values = self.OD_start_value + np.arange(point_count) * self.OD_point_step_value

        # self.OD_input_points = np.arange(0, point_count, 1)
        self.OD_input_points = self.OD_input_points = np.column_stack((point_times, values))
        # return np.arange(0, point_count, 1)
        return self.OD_input_points

    def Run(self, Mode, PointTime):
        if Mode == 'DP':
            # in case of DP control
            self.input_value = self.DP_input_value
        else:
            # 2.1 WV
            point_time_input_value = self.owner.get_value_at_point_time(PointTime)
            if self.OD_controlled_parameter_name == None:
                # just simple open loop control
                # 2.0 OK Allow single value input of OD_start_value only
                # self.input_value = self.OD_start_value + self.OD_input_points[PointTime] * self.OD_point_step_value
                self.input_value = self.OD_start_value # basic value
                if not((self.OD_end_value == None) or (self.OD_point_step_value == None)):
                    # 2.1
                    # self.input_value = self.input_value + self.OD_input_points[PointTime] * self.OD_point_step_value
                    self.input_value = point_time_input_value
            else:
                # input is coming from state, iterating toward value satisfying control equation
                self.input_value = self.DP_input_value * self.owner.states[self.istate_control]
            # 2.0 OK Allow single value input of OD_start_value only
            # self.control_parameter_demand = self.OD_start_value + self.OD_input_points[PointTime] * self.OD_point_step_value
            self.control_parameter_demand = self.OD_start_value
            if not((self.OD_end_value == None) or (self.OD_point_step_value == None)):
                #  2.1
                # self.control_parameter_demand = self.control_parameter_demand + self.OD_input_points[PointTime] * self.OD_point_step_value
                self.control_parameter_demand = point_time_input_value

    # 1.1 WV PostRun evaluates the equation for controlling parameter named OD_controlledparName to input
    # note that anything calculated in PostRun will not end up in the output_dict !
    def PostRun(self, Mode, PointTime):
        # super().PostRun(Mode, PointTime)
        if self.OD_controlled_parameter_name != None:
            if Mode == 'DP':
                self.owner.states = np.append(self.owner.states, 1)
                self.istate_control = self.owner.states.size-1
                self.owner.errors = np.append(self.owner.errors, 0)
                self.ierror_control = self.owner.errors.size-1
                #  get control parameter DP value
                self.DP_control_parameter_value = self.owner.output_dict[self.OD_controlled_parameter_name]
            else:
                # get control demanded (set point) parameter value from input
                # self.controlpar_demand = self.OD_startvalue + self.OD_inputpoints[PointTime] * self.OD_pointstepvalue
                #  get control parameter current value
                # lastrownumber = len(self.owner.OutputTable)
                control_parameter_value = self.owner.output_dict[self.OD_controlled_parameter_name]
                self.owner.errors[self.ierror_control] = (self.control_parameter_demand - control_parameter_value) / self.DP_control_parameter_value

    # 2.0.0.0
    def get_outputs(self):
        out = super().get_outputs()
        if self.owner.mode == 'DP':
            out[self.name+"_setpoint"] = None
            out[self.name+"_input"] = None
        else:
            out[self.name+"_setpoint"] = self.control_parameter_demand
            out[self.name+"_input"] = self.input_value
        return out
