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


class TShaftComponent(TComponent, ABC):
    """
    Abstract shaft-connected mechanical device.

    This class represents any non-gaspath component that exchanges
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


class TOneShaftComponent(TShaftComponent, ABC):
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


class TTwoShaftComponent(TShaftComponent, ABC):
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