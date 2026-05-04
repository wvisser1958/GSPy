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

from gspy.core.base_component import TComponent
import math
import numpy as np

class TEquation(TComponent):
    def __init__(self, owner, name, map_filename, control_component,
                *,
                obj_with_free_variable,
                free_var_attr_name,
                free_var_norm_factor):    # Constructor of the class
        super().__init__(owner,     name, map_filename, control_component)
        self.obj_with_free_variable = obj_with_free_variable
        self.free_var_attr_name = free_var_attr_name
        self.free_var_norm_factor = free_var_norm_factor
        self.free_var_des_value = None
        self.active = False

    def get_free_var_value(self):
        return getattr(self.obj_with_free_variable, self.free_var_attr_name)

    def set_free_var_value(self, value):
        setattr(self.obj_with_free_variable, self.free_var_attr_name, value)

    def PreRun(self, Mode, PointTime):
        # super().PostRun(Mode, PointTime)
        if Mode != 'DP':
            self.free_var_value = self.free_var_norm_factor * self.owner.states[self.istate_equation]
            if self.active:
                self.set_free_var_value(-self.free_var_value * 1000) # from W to kW

    def Run(self, Mode, PointTime):
        pass

    # note that anything calculated in PostRun will not end up in the output_dict !
    def PostRun(self, Mode, PointTime):
        # super().PostRun(Mode, PointTime)
        if Mode == 'DP':
            self.owner.states = np.append(self.owner.states, 1)
            self.istate_equation = self.owner.states.size-1
            self.owner.errors = np.append(self.owner.errors, 0)
            self.ierror_equation = self.owner.errors.size-1
            self.free_var_des_value = self.get_free_var_value()
            if self.free_var_norm_factor is None:
                self.free_var_norm_factor = self.free_var_des_value    
            # if nearly 0, set it to 1
            if math.isclose(self.free_var_norm_factor, 0.0, abs_tol=1e-3):
                self.free_var_norm_factor = 1
        else:
            # this is custom code for specific application, using the output table columns
            Qfuel_conditioning = self.owner.output_dict["Q_fuel_cond kW"]
            Qduct = self.free_var_value 
            self.owner.errors[self.ierror_equation] = (Qfuel_conditioning - Qduct) / self.free_var_norm_factor

    def PrintPerformance(self, Mode, PointTime):
        pass

    def get_outputs(self):
        out = super().get_outputs()
        return out
