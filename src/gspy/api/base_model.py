import os
from pathlib import Path

from ..core.system import TSystemModel
from gspy.api.components import resolve_component_class


class BaseGasTurbineModel:
    def __init__(self, model_name, model_root: Path | None = None):
        self.initialized = False
        self.model_name = model_name
        self.params = {}
        self.system_model_obj = None
        self.components = []
        self.components_by_name = {}

        default_root = Path(__file__).resolve().parent
        self._model_root: Path = Path(model_root).resolve() if model_root else default_root

    def set_model_root(self, root: Path):
        self._model_root = Path(root).resolve()

    @property
    def model_file(self) -> Path:
        return self._model_root / f"{self.model_name}.py"

    @property
    def map_path(self) -> Path:
        if self.system_model_obj is not None:
            return self.system_model_obj.maps_dir_path
        return self._model_root / "data" / "maps"

    @property
    def input_path(self) -> Path:
        if self.system_model_obj is not None:
            return self.system_model_obj.input_dir_path
        return self._model_root / "input"

    @property
    def output_path(self) -> Path:
        if self.system_model_obj is not None:
            return self.system_model_obj.output_dir_path
        return self._model_root / "output"

    def initialize(self, run_mode="DP"):
        self.system_model_obj = TSystemModel(
            self.model_name,
            model_file=str(self.model_file),
            verbose=False,
        )

        model_comps = self.build_model()
        components = []
        components_by_name = {}
        
        self.system_model_obj.VERBOSE = False

        for model_comp in model_comps:
            comp_class = resolve_component_class(model_comp["type"])
            args = model_comp.get("args", [])
            kwargs = model_comp.get("kwargs", {})
            comp = comp_class(self.system_model_obj, model_comp["name"], *args, **kwargs)
            components.append(comp)
            components_by_name[model_comp["name"]] = comp

        self.components = components
        self.components_by_name = components_by_name

        # Required by the new core for resolving inter-component references by name,
        # for example combustor control references like "Fuel Controller".
        self.system_model_obj.components = components_by_name

        # Optional aliases in case other core code expects list-based access.
        self.system_model_obj.component_list = components
        self.system_model_obj.component_run_list_user = components

        # Register execution order; TSystemModel already prepends its own ambient.
        self.system_model_obj.define_comp_run_list(*components)


        self.initialized = True
        self.run_mode = run_mode
        return f"{self.model_name} initialized"

    def build_model(self):
        raise NotImplementedError("build_model() must be implemented")

    def set_param(self, name, value):
        raise NotImplementedError("set_param() must be implemented")

    def run(self):
        if not self.initialized or self.system_model_obj is None:
            raise RuntimeError("Model not initialized")

        if self.run_mode == "DP":
            return self.system_model_obj.Run_DP_simulation()
        elif self.run_mode == "OD":
            return self.system_model_obj.Run_OD_simulation()
        else:
            raise ValueError(f"Invalid input string value: run mode ({self.run_mode})")

    def save_output_csv(self, filename: str = "output.csv") -> str:
        if self.system_model_obj is None:
            raise RuntimeError("Model not initialized")

        os.makedirs(self.output_path, exist_ok=True)
        csv_file_path = os.path.join(self.output_path, filename)

        self.system_model_obj.prepare_output_table()
        if (
            self.system_model_obj.output_table is not None
            and not self.system_model_obj.output_table.empty
        ):
            self.system_model_obj.output_table.to_csv(csv_file_path, index=False)

        return csv_file_path

    @property
    def run_mode(self) -> str | None:
        if self.system_model_obj is not None:
            return self.system_model_obj.mode
        return None

    @run_mode.setter
    def run_mode(self, value: str):
        run_mode_options = ["DP", "OD"]
        if value in run_mode_options:
            if self.system_model_obj is None:
                raise RuntimeError("System model object not initialized")
            self.system_model_obj.mode = value
        else:
            raise ValueError(
                f"Invalid input string value: run mode ({value}), allowed: {run_mode_options}"
            )
