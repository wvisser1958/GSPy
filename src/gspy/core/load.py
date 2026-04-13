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
#   Oscar Kogenhop

from gspy.core.shaft_component import TOneShaftComponent


class TLoad(TOneShaftComponent):
    """
    Concrete shaft power consumer.

    Examples:
        - Generator (normal operation)
        - Hydraulic pump
        - Accessory gearbox parasitic load
    """

    def __init__(
        self,
        owner,                  # owning system model object
        name,                   # component name
        map_filename_or_dict,   # map file name or dict with power values for different demands
        control_component,      # optional control component, if None then no control component
                                # is used for this load, otherwise the control component must be
                                # defined before this load in the model file
        shaft_id,               # shaft number of the load, must be defined in the model file
                                # before this load, the shaft could also be created in the model
                                # file first
        power_kw_des,           # design power of the load, used to calculate the power demand
                                # of the load at design conditions, and to calculate the power
                                # demand at off-design conditions based on the power demand set
                                # by the control component
        ):
        super().__init__(owner, name, map_filename_or_dict, control_component, shaft_id)
        self.power_w_des = power_kw_des * 1000  # convert kW to W
        self.power_w = self.power_w_des

    def get_outputs(self):
        out = {}
        out["PW_" + self.name] = self.power_w / 1000  # convert W to kW for output

        return out

    def get_drive_shaft_power(self):
        # Power consumer, so negative sign: power absorbed from shaft
        return -self.power_w
