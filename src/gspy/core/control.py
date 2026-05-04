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
                 OD_controlled_parameter_name,
                 *,    # force optional parameters passing by name
                 point_time_value_array = None 
                 ):
        # note that, if OD_controlledparname != None:
        #    OD_startvalue, OD_endvalue, OD_pointstepvalue represent the values of the OD_controlledparname
        # else:
        #    they are the direct input values of the component using this control (like fuel flow for a combustor for example)
        # DP_inputvalue always is direct input values of the component using this control
        super().__init__(owner, name, map_file_name, None) # no control controlling a control (yet)
        # 2.1
        self.re_init_input(map_file_name,
                    DP_input_value,
                    OD_start_value, OD_end_value, OD_point_step_value,
                    OD_controlled_parameter_name,
                    point_time_value_array = point_time_value_array)

    # 2.1
    def re_init_input(self, map_file_name,
                            DP_input_value,
                            OD_start_value, OD_end_value, OD_point_step_value,
                            OD_controlled_parameter_name,
                            *,
                            # point_time_value_array: 
                            #   - either an array with control demand/input values 
                            #     (point_time incremented automaticall from OD_start_value)
                            #   - or an array with [point_time, value] pairs, like
                            #       point_values = np.array([
                            #                     [3.0, 11],
                            #                     [4.5, 10],
                            #                     [5.0, 9]
                            #                 ])
                            point_time_value_array = None):
        self.map_filename = map_file_name # for use in customized child classes, e.g. with lookup tables
        self.DP_input_value = DP_input_value
        if OD_start_value is None:
            self.OD_start_value = self.owner.point_time + 1
        else:    
            self.OD_start_value = OD_start_value
        self.OD_end_value = OD_end_value
        self.OD_point_step_value = OD_point_step_value
        self.OD_controlled_parameter_name = OD_controlled_parameter_name
        self.control_parameter_demand = None
        # if point_time_value_array is not None:
        #     self.point_time_value_array = np.asarray(point_time_value_array)
        # self.point_time_value_array = (
        #     None if point_time_value_array is None
        #     else np.asarray(point_time_value_array)
        if point_time_value_array is None:
            self.point_time_value_array = None
        else:
            arr = np.asarray(point_time_value_array, dtype=float)
            if arr.ndim == 1:
                # Input is only values: [1.2, 1.8, 2.5]
                values = arr
                point_times = self.OD_start_value + np.arange(len(values), dtype=float)

                return np.column_stack((point_times, values))

            elif arr.ndim == 2 and arr.shape[1] == 2:
                # Input is already [[time, value], ...]
                return arr

            else:
                raise ValueError("input_points must be either [values...] or [[time, value], ...]")            
        
        if not ((OD_point_step_value == None) and (OD_end_value == None)): # single point input
            if (abs(OD_point_step_value) == 0) or ((OD_end_value - OD_start_value) * OD_point_step_value < 0):
                raise Exception("Invalid control variable begin, end and step values")
        
        return self.get_OD_input_points() 

    # 2.1
    # def get_OD_input_points(self):
    def get_OD_input_points(self, start_point_time = 0):
        if self.point_time_value_array is not None:
            # point_time array with values already given in point_time_value_array
            return self.point_time_value_array
        else:
            # make a simple point_time values array using start, end and step size
            if (self.OD_end_value == None) or (self.OD_point_step_value == None):
                point_count = 1
            else:
                point_count = round(abs((self.OD_end_value - self.OD_start_value) / self.OD_point_step_value) + 1)

            self.start_point_time = start_point_time
            # default is using self.OD_start_value, self.OD_end_value, self.OD_point_step_value
            # to make a constant step size series of inputs
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

            # if not((self.OD_end_value == None) or (self.OD_point_step_value == None)):
                #  2.1
                # self.control_parameter_demand = self.control_parameter_demand + self.OD_input_points[PointTime] * self.OD_point_step_value
            self.control_parameter_demand = point_time_input_value

    # 1.1 WV PostRun evaluates the equation for controlling parameter named OD_controlledparName to input
    # note that anything calculated in PostRun will not end up in the output_dict !
    def PostRun(self, Mode, PointTime):
        # super().PostRun(Mode, PointTime)
        if self.OD_controlled_parameter_name is not None:
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
