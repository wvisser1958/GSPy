# --- Component class registry (eager imports) ---
from gspy.core.ambient import TAmbient
from gspy.core.AMcontrol import TAMcontrol
from gspy.core.bleedflow import TBleedFlow
from gspy.core.combustor import TCombustor
from gspy.core.compressor import TCompressor
from gspy.core.control import TControl
from gspy.core.coolingflow import TCoolingFlow
from gspy.core.duct import TDuct
from gspy.core.exhaustdiffuser import TExhaustDiffuser
from gspy.core.exhaustnozzle import TExhaustNozzle
from gspy.core.fan import TFan
from gspy.core.inlet import TInlet
from gspy.core.shaft import TShaft
from gspy.core.turbine import TTurbine

COMPONENT_CLASS_MAP: dict[str, type] = {
    "Ambient": TAmbient,
    "Adapt.Model.Ctrl": TAMcontrol,
    "BleedFlow": TBleedFlow,
    "Combustor": TCombustor,
    "Compressor": TCompressor,
    "Control": TControl,
    "CoolingFlow": TCoolingFlow,
    "Duct": TDuct,
    "ExhaustDiffuser": TExhaustDiffuser,
    "ExhaustNozzle": TExhaustNozzle,
    "Fan": TFan,
    "Inlet": TInlet,
    "Shaft": TShaft,
    "Turbine": TTurbine
}

COMPONENT_ALIASES: dict[str, str] = {
    "Nozzle": "ExhaustNozzle",
    "Exhaust": "ExhaustNozzle",
    "Burner": "Combustor",
    "JetPipe": "Duct",
}

def register_component(name: str, cls: type) -> None:
    if not isinstance(name, str) or not name:
        raise ValueError("Component name must be a non-empty string")
    if not isinstance(cls, type):
        raise TypeError("cls must be a class/type")
    COMPONENT_CLASS_MAP[name] = cls

def resolve_component_class(type_name: str) -> type:
    if not isinstance(type_name, str) or not type_name:
        raise KeyError("Component type must be a non-empty string")
    tn = type_name.strip()
    canonical = COMPONENT_ALIASES.get(tn, tn)
    try:
               return COMPONENT_CLASS_MAP[canonical]
    except KeyError as exc:
        known = ", ".join(sorted(COMPONENT_CLASS_MAP.keys()))
        aliases = ", ".join(f"{a}->{b}" for a, b in sorted(COMPONENT_ALIASES.items()))
        raise KeyError(
            f"Unknown component type '{type_name}'. "
            f"Known types: [{known}] ; Aliases: [{aliases}]"
        )
