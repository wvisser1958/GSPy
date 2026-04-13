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

from abc import ABC, abstractmethod
from gspy.core.base_component import TComponent
import gspy.core.shaft as fshaft


class TShaftDevice(TComponent, ABC):
    """
    Abstract shaft-connected mechanical device.

    This class represents any non-turbomachinery device that exchanges
    mechanical power with a shaft. It provides the common control handling
    and power demand calculation shared by one-shaft and two-shaft devices.

    The base class stores the drive-side shaft id, because every shaft device
    has at least one primary shaft connection. Subclasses define whether
    additional shaft connections are required and how shaft power is applied.

    Sign convention (enforced by subclasses):
        + power : delivered to shaft
        - power : absorbed from shaft
    """

    def __init__(self, owner, name, map_filename_or_dict, control_component, shaft_id):
        super().__init__(owner, name, map_filename_or_dict, control_component)
        self.shaft_id = shaft_id
        self.drive_shaft = None  # to be assigned later in Run()

    @abstractmethod
    def get_drive_shaft_power(self) -> float:
        """
        Return the power contribution applied to the drive shaft.

        The sign convention and exact meaning depend on the subclass.
        For example, a power consumer returns negative power, while
        a power producer returns positive power.
        """
        raise NotImplementedError

    def _resolve_control(self):
        """
        Resolve the control reference if it is stored as a component name.
        """
        if isinstance(self.control, str):
            try:
                self.control = self.owner.components[self.control]
            except Exception as e:
                raise ValueError(
                    f"ShaftDevice '{self.name}': Control '{self.control}' "
                    f"cannot be resolved to an object. ({e})"
                )

    def get_outputs(self):
        """
        Default outputs for shaft-connected devices.

        Loads and shaft devices are algebraic components and therefore
        do not contribute standard gas-path outputs by default.
        Concrete subclasses may extend this.
        """
        return {}


class TOneShaftDevice(TShaftDevice, ABC):
    """
    Abstract shaft device connected to a single shaft.

    This class provides the one-shaft execution logic and is intended as the
    base class for concrete shaft devices that act on only one shaft, which is
    the most common case. If the referenced shaft does not yet exist, it is
    created automatically.
    """

    def __init__(self, owner, name, map_filename_or_dict, control_component, shaft_id):
        super().__init__(owner, name, map_filename_or_dict, control_component, shaft_id)
        self.power_w_des = None
        self.power_w = None

        # Ensure shaft exists even if load is defined before turbomachinery
        if all(shaft.shaft_id != shaft_id for shaft in owner.shaft_list):
            owner.shaft_list.append(
                fshaft.TShaft(shaft_id, name + " shaft " + str(shaft_id))
            )

    def get_power_conversion(self) -> float:
        """
        Return the conversion factor between the control input and shaft power.

        The default implementation assumes a direct conversion. Subclasses
        may override this, for example to include a power factor or other
        conversion relationship.
        """
        return 1.0

    def _calculate_power_demand(self, mode):
        """
        Determine the device power demand from design data or control input.

        Power is stored internally in W.
        """
        if mode == "DP":
            # Design point: fix the design demand
            self.power_w = self.power_w_des
            if self.control is not None and self.control.input_value is not None:
                # This overrides the design power of the ShaftDevice to the controller value
                # Get the design control value (e.g. from a control component instance),
                # the controller sets the "input_value" in design from "DP_input_value"
                self.power_w = self.get_power_conversion() * self.control.input_value * 1000  # convert kW to W
        else:
            # Off-Design
            if self.control is not None:
                # Get the control value (e.g. from a control component instance)
                if self.control.OD_controlled_parameter_name is None:
                    self.power_w = self.get_power_conversion() * self.control.input_value * 1000  # convert kW to W
                else:
                    # TODO
                    raise NotImplementedError(
                        "Control of shaft devices based on state variables is not implemented yet."
                    )
            else:  # use power demand from component design specification
                self.power_w = self.power_w_des

    def Run(self, mode, point_time):
        # Get shaft by shaft_id
        self.drive_shaft = self.owner.get_shaft(self.shaft_id)

        # Resolve control component
        self._resolve_control()

        # Determine the power demand from the control component if applicable
        self._calculate_power_demand(mode)

        # Apply the shaft power contribution to the connected shaft
        self.drive_shaft.PW_sum = self.drive_shaft.PW_sum + self.get_drive_shaft_power()

        return


class TTwoShaftDevice(TShaftDevice, ABC):
    """
    Abstract shaft device connected to two shafts.

    This class is intended to be a base class for concrete shaft devices that
    are connected to two shafts, such as gearboxes or clutches. It defines the
    second shaft connection and validates that both required shafts already
    exist in the model before the component is created.
    """

    def __init__(
        self,
        owner,
        name,
        map_filename_or_dict,
        control_component,
        drive_shaft_id,
        driven_shaft_id,
    ):
        super().__init__(owner, name, map_filename_or_dict, control_component, drive_shaft_id)

        # For a two-shaft device, we need to define a second shaft connection and
        # corresponding attributes
        self.driven_shaft_id = driven_shaft_id
        self.driven_shaft = None  # to be assigned later in Run()

        # Ensure shafts exist, for a 2 shaft device both shafts need to exist before
        # this component model is created. This is because the interaction between
        # the two shafts is a core part of the device behavior, and it is not
        # possible to define the device without both shafts being defined first.
        # For example, for a gearbox the drive and driven shaft speeds are related
        # by the gear ratio, so both shafts need to be defined before the gearbox
        # can be defined.
        required_shaft_ids = {drive_shaft_id, driven_shaft_id}
        existing_shaft_ids = {shaft.shaft_id for shaft in owner.shaft_list}

        missing_ids = required_shaft_ids - existing_shaft_ids

        if missing_ids:
            if drive_shaft_id in missing_ids:
                raise ValueError(
                    f"Drive shaft with id '{drive_shaft_id}' for two-shaft device "
                    f"'{name}' is not defined in the model file. Please define the drive shaft first."
                )
            if driven_shaft_id in missing_ids:
                raise ValueError(
                    f"Driven shaft with id '{driven_shaft_id}' for two-shaft device "
                    f"'{name}' is not defined in the model file. Please define the driven shaft first."
                )

    def Run(self, mode, point_time):
        """
        Base execution for two-shaft devices.

        This resolves both shaft references, but does not yet apply shaft power
        to either shaft. Concrete subclasses must implement that behavior
        because the relationship between drive-side power, driven-side power,
        losses, and shaft speed depends on the specific device type.
        """
        self.drive_shaft = self.owner.get_shaft(self.shaft_id)
        self.driven_shaft = self.owner.get_shaft(self.driven_shaft_id)

        self._resolve_control()

        raise NotImplementedError(
            "TTwoShaftDevice.Run() must be implemented by a concrete two-shaft device subclass."
        )


class TPowerConsumer(TOneShaftDevice):
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


class TPowerProducer(TOneShaftDevice):
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

    def get_drive_shaft_power(self):
        # Power producer, so positive sign: power delivered to shaft
        return self.power_w


class TStarterGenerator(TPowerProducer):
    """
    Concrete starter-generator device where the power is defined in kVA and power factor.

    A starter-generator is a shaft-connected device that can operate as both a power
    consumer (starter) and a power producer (generator) depending on the operating
    mode. This class extends TPowerProducer but overrides the applied drive shaft
    power sign to support both operating modes.
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

    def get_drive_shaft_power(self):
        # Sign depends on operating mode: starter delivers power to shaft,
        # generator absorbs power from shaft
        return self.power_w * self.power_sign

    def get_power_conversion(self):
        return self.power_factor