
import os
from pathlib import Path
from ..core import sys_global as global_sys
from ..core import system as sys
from gspy.api.components import resolve_component_class  # <-- import your registry resolver

class BaseGasTurbineModel:
    def __init__(self, model_name, model_root: Path | None = None):
        self.initialized = False
        self.model_name = model_name
        self.params = {}

        # Default to this file's folder if caller doesn't provide a root
        default_root = Path(__file__).resolve().parent
        self._model_root: Path = model_root or default_root

        # Paths relative to the chosen model root
        self.map_path = self._model_root / "maps"
        self.input_path = self._model_root / "input"
        self.output_path = self._model_root / "output"

        # Tell the core where to put outputs
        global_sys.output_path = self.output_path
        # Do not print to console!
        sys.VERBOSE = False

    def set_model_root(self, root: Path):
        self._model_root = Path(root).resolve()
        self.map_path = self._model_root / "maps"
        self.input_path = self._model_root / "input"
        self.output_path = self._model_root / "output"
        global_sys.output_path = self.output_path  # keep core in sync

    def initialize(self, run_mode="DP"):
        # Declarative: build_model returns a list of dicts
        model_comps = self.build_model()
        components = []
        for model_comp in model_comps:
            comp_class = resolve_component_class(model_comp["type"])
            args = [model_comp["name"]] + model_comp.get("args", [])
            kwargs = model_comp.get("kwargs", {})
            comp = comp_class(*args, **kwargs)
            components.append(comp)

        # Wire into core system
        sys.system_model = components

        # Optionally expose ambient in the legacy global if your core expects it
        # (If you have multiple ambient types, adjust this check)
        from gspy.core.ambient import TAmbient
        ambient = next((component for component in components if isinstance(component, TAmbient)), None)
        if ambient is not None:
            sys.Ambient = ambient

        global_sys.InitializeGas()
        sys.ErrorTolerance = 0.0001
        self.initialized = True
        self.run_mode = run_mode  # Use property setter
        return f"{self.model_name} initialized"

    def build_model(self):
        raise NotImplementedError("build_model() must be implemented")

    def set_param(self, name, value):
        raise NotImplementedError("set_param() must be implemented")

    def run(self):
        if not self.initialized:
            raise RuntimeError("Model not initialized")

        if self.run_mode == 'DP':
            sys.Run_DP_simulation()
        elif self.run_mode == 'OD':
            sys.Run_OD_simulation()
        else:
            raise ValueError(f"Invalid input string value: run mode ({self.run_mode})")

    def save_output_csv(self, filename: str = 'output.csv') -> str:
        if not hasattr(self, "output_path"):
            raise AttributeError(f"Model class must define an output path!")

        os.makedirs(self.output_path, exist_ok=True)
        csv_file_path = os.path.join(self.output_path, filename)
        if sys.OutputTable is not None and not sys.OutputTable.empty:
            sys.OutputTable.to_csv(csv_file_path, index=False)
        return csv_file_path

    @property
    def run_mode(self) -> str | None:
        """Get the current run mode ('DP' or 'OD')."""
        run_mode_options = ["DP", "OD"]
        if hasattr(sys, "Mode") and sys.Mode in run_mode_options:
            return sys.Mode
        return None

    @run_mode.setter
    def run_mode(self, value: str):
        """Set the model run mode ('DP' or 'OD')."""
        run_mode_options = ["DP", "OD"]
        if value in run_mode_options:
            sys.Mode = value
        else:
            raise ValueError(
                f"Invalid input string value: run mode ({value}), allowed: {run_mode_options}"
            )