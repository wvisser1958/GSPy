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

    def __init__(self,
                *,
                power_kw_des,           # design power of the load, used to calculate the power demand
                                        # of the load at design conditions, and to calculate the power
                                        # demand at off-design conditions based on the power demand set
                                        # by the control component
                **kwargs):
        super().__init__(**kwargs)
        self.power_w_des = power_kw_des * 1000  # convert kW to W
        self.power_w = self.power_w_des

    def get_outputs(self):
        out = {}
        out["PW_" + self.name] = self.power_w / 1000  # convert W to kW for output

        return out

    def get_drive_shaft_power(self):
        # Power consumer, so negative sign: power absorbed from shaft
        return -self.power_w

    def set_OD_power_demand(self, power_kw):
        """
        Set the off-design power demand of the load in kW.

        Args:
            power_kw (float): Power demand in kW.
        """
        self.power_w = power_kw * 1000  # convert kW to W
