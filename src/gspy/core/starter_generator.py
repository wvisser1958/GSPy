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

from gspy.core.motor import TMotor

class TStarterGenerator(TMotor):
    """
    Concrete starter-generator device where the power is defined in kVA and power factor.

    A starter-generator is a shaft-connected device that can operate as both a power
    consumer (starter motor) and a power producer (generator load) depending on the 
    operating mode. This class extends TMotor but overrides the applied drive shaft
    power sign to support both operating modes.
    
    This class uses a fixed power factor to convert between real power (kW) and apparent power (kVA),
    to allow modeling of the power conversion behavior of the device, the get_power_conversion() method 
    can be overridden to in derived classes from this class to retrieve the power factor for use with 
    other components such as from an electrical system model.
    """

    # Derivation from TMotor is chosen here because the default behavior of a
    # starter-generator is to produce power (generator mode), operating in starter mode
    # for example during engine start is a special simulation case

    def __init__(
        self,                   # instance reference
        owner,                  # owning system model object
        name,                   # component name
        map_filename_or_dict,   # map file name or dict with power values for different demands
        control_component,      # optional control component, if None then no control component
                                # is used for this load, otherwise the control component must be
                                # defined before this load in the model file
        shaft_id,               # shaft number of the load, must be defined in the model file
                                # before this load, the shaft could also be created in the model
                                # file first
        apparent_power,         # design power of the load in kVA, used to calculate the power demand
                                # of the load at design conditions, and to calculate the power
                                # demand at off-design conditions based on the power demand set
                                # by the control component
        power_factor=1.0,       # Power factor is assumed to be 1, so apparent power is equal to real power in this case e.g. for a starter motor power conversion is typically 0.5-0.8, for a generator it is typically 0.9-1.0
        power_mode='generator'  # options: ['starter', 'generator'], determines the power conversion behavior of the load
        ):
        self.power_sign = -1  # generator mode: power absorbed from shaft

        if power_mode not in ['starter', 'generator']:
            raise ValueError("Invalid power_mode. Expected 'starter' or 'generator'.")
        else:
            if power_mode == 'starter':
                self.power_sign = 1  # power delivered to shaft

        if power_factor <= 0 or power_factor > 1:
            raise ValueError("Power factor should be in the range [0, 1].")

        # calculate real power in kW based on apparent power and power factor
        self.apparent_power = apparent_power
        self.power_factor = power_factor
        power_kw_des = self.apparent_power /self.power_factor

        # Now call the parent constructor with the calculated real power
        super().__init__(owner, name, map_filename_or_dict, control_component, shaft_id, power_kw_des)
        self.power_w_des = power_kw_des * 1000  # convert kW to W
        self.power_w = self.power_w_des

    def get_outputs(self):
        out = {}
        out["PW_" + self.name] = self.power_w / 1000  # convert W to kW for output
        out["S_" + self.name] = self.apparent_power  # apparent power in kVA for output
        out["PF_" + self.name] = self.power_factor  # power factor for output
        return out

    def get_drive_shaft_power(self):
        # Sign depends on operating mode: starter delivers power to shaft,
        # generator absorbs power from shaft
        return self.power_w * self.power_sign

    def get_power_conversion(self):
        return self.power_factor