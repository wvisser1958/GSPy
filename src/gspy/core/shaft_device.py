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

import numpy as np
from abc import ABC, abstractmethod
from gspy.core.base_component import TComponent
import gspy.core.shaft as fshaft


class TShaftDevice(TComponent, ABC):
    """
    Abstract shaft-connected mechanical device.

    This class represents *any* non-turbomachinery device that exchanges
    mechanical power with a shaft. Direction of power (consume vs produce)
    is intentionally NOT defined here.

    Sign convention (enforced by subclasses):
        + power : delivered to shaft
        - power : absorbed from shaft
    """

    def __init__(self, owner, name, map_filename_or_dict, control_component, shaft_id):
        super().__init__(owner, name, map_filename_or_dict, control_component)
        self.control_component = control_component
        self.shaft_id = shaft_id
        self.shaft = None  # to be assigned later in Run
        self.power_w_des = None
        self.power_w = self.power_w_des

        # Ensure shaft exists even if load is defined before turbomachinery
        if all(shaft.shaft_id != shaft_id for shaft in owner.shaft_list):
            owner.shaft_list.append(
                fshaft.TShaft(shaft_id, name + " shaft " + str(shaft_id))
            )

    @abstractmethod
    def get_shaft_power(self) -> float:
        """
        Return the shaft power using the sign convention defined by the subclass.

        This base method is abstract because the sign convention and exact
        implementation depend on the concrete component type.
        """
        raise NotImplementedError

    def get_power_conversion(self) -> float:
        # Empty implementation here, as power conversion is enforced by subclasses
        # This is per definition not an abstract method, as not all shaft devices 
        # need to implement power conversion, but it can be overridden by subclasses 
        # that do require power conversion (e.g. starter-generator)
        return 1

    def Run(self, mode, point_time):
        # Get shaft by shaft_id
        self.shaft = self.owner.get_shaft(self.shaft_id)

        # Resolve control component
        if isinstance(self.control, str):
            try:
                self.control = self.owner.components[self.control]   # resolve by name -> object
            except Exception as e:
                raise ValueError(
                    f"Combustor '{self.name}': Control '{self.control}' cannot be resolved to an object. ({e})"
                )

        # Determine the power demand from the control component if applicable
        if mode == "DP":
            # Design point: fix the design demand
            self.power_w = self.power_w_des
            if self.control != None and self.control.input_value != None: 
                # This overrides the design power of the ShaftDevice to the controller value
                # Get the design control value (e.g. from a control component instance),
                # the controller sets the "input_value" in design from "DP_input_value"
                self.power_w = self.get_power_conversion() * self.control.input_value * 1000 # convert kW to W
        else:
            # Off-Design
            if self.control != None:
                # Get the control value (e.g. from a control component instance)
                if (self.control.OD_controlled_parameter_name == None): 
                    self.power_w = self.get_power_conversion() * self.control.input_value * 1000 # convert kW to W
                else:
                    # TODO
                    raise NotImplementedError("Control of shaft devices based on state variables is not implemented yet.")
            else: # use power demand from componennt design specification
                self.power_w = self.power_w_des

        # self.shaft.PW_sum = self.shaft.PW_sum - self.power_w # Negative sign: power absorbed from shaft
        self.shaft.PW_sum = self.shaft.PW_sum + self.get_shaft_power()

        return

    def get_outputs(self):
        """
        Default outputs for shaft-connected devices.

        Loads and shaft devices are algebraic components and therefore
        do not contribute standard gas-path outputs by default.
        Concrete subclasses may extend this.
        """
        return {}


class TPowerConsumer(TShaftDevice):
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

    def get_outputs(self):
        out = {}
        out["PW_" + self.name] = self.power_w / 1000  # convert W to kW for output

        return out

    def get_shaft_power(self):
        # Power consumer, so negative sign: power absorbed from shaft
        return -self.power_w
    
    def Run(self, mode, point_time):
        super().Run(mode, point_time)

class TPowerProducer(TShaftDevice):
    """
    Concrete shaft power producer.

    Examples:
        - Starter motor
        - External drive rig
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

    def get_shaft_power(self):
        # Power producer, so positive sign: power delivered to shaft
        return self.power_w

    def Run(self, mode, point_time):
        super().Run(mode, point_time)

class TStarterGenerator(TPowerProducer):
    """
    Concrete starter-generator device where the power is defined in kVA and power factor.
    
    A starter-generator is a shaft-connected device that can operate as both a power 
    consumer (starter) and a power producer (generator) depending on the operating 
    mode. This class extends TPowerProducer but overrides the Run method to determine 
    the power demand based on the control component and operating mode. 
    """
    # Derivation from TPowerProducer is chosen here because the default behavior of a 
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
        self.power_sign = -1     # defaults to generator behavior (power absorbed from shaft, negative sign)
        
        if power_mode not in ['starter', 'generator']:
            raise ValueError("Invalid power_mode. Expected 'starter' or 'generator'.")
        else:
            if power_mode == 'starter':
                self.power_sign = 1     # power delivered to shaft
                
        if power_factor <= 0 or power_factor > 1:
            raise ValueError("Power factor should be in the range [0, 1].")
        
        # calculate real power in kW based on apparent power and power factor
        self.apparent_power = apparent_power
        self.power_factor = power_factor
        power_kw_des = self.apparent_power * self.power_factor

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

    def get_shaft_power(self):
        # Positive sign: power delivered to shaft
        return self.power_w * self.power_sign

    def get_power_conversion(self):
        return self.power_factor

    def Run(self, mode, point_time):
        super().Run(mode, point_time)
