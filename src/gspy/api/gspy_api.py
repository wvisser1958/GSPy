# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""
GSPy API Interface

Provides a stable programmatic interface to run gas turbine performance models
and retrieve structured results for downstream consumers. Compatible with data
fields and behaviors described in ARP4868 for interoperability. This is an 
independent implementation not affiliated with independent implementation not 
affiliated with or endorsed by SAE or the ARP4868 committee.

"""
import os
import importlib
import importlib.util
import pandas as pd

from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Iterable, Union

from gspy.core import system as fsys

# Model variables
_current_model = None
_current_log_file = None

# -----------------------------------------------------------------------------
# API supporting functions
# -----------------------------------------------------------------------------
def _resolve_model_root(module_name: str, module_obj) -> Path | None:
    """
    Return the filesystem directory for the given module/package.
    Prefer module.__file__ when available; fall back to importlib spec.
    """
    # 1) Most common case
    f = getattr(module_obj, "__file__", None)
    if f:
        return Path(f).resolve().parent

    # 2) Fallback to spec (handles some namespace/pkg cases)
    spec = importlib.util.find_spec(module_name)
    if not spec:
        return None
    if spec.submodule_search_locations:
        # Package: choose first search location
        return Path(next(iter(spec.submodule_search_locations))).resolve()
    if spec.origin and spec.origin != "built-in":
        return Path(spec.origin).resolve().parent
    return None

def _is_model_initialized():
    """Returns True if a model has been initialized and is marked as such."""
    return _current_model is not None and getattr(_current_model, "initialized", False)

def _get_model_name():
    """Returns the name of the currently initialized model.

    Raises:
        RuntimeError: If the model is not initialized.
    """
    if _current_model is None or not getattr(_current_model, "initialized", False):
        raise RuntimeError("Model not initialized")
    return _current_model.model_name

def _get_model_components_list(verbose=False):
    """Retrieves a list of system model components with their properties.

    Args:
        verbose (bool): Currently unused.

    Returns:
        dict: A dict with a "components" list containing dictionaries with
              keys: type, name, station_in, station_out.
    """
    if _current_model is None:
        raise RuntimeError("Model is not initialized")

    if not fsys.system_model:
        raise RuntimeError("System model is not initialized or empty")

    components = []
    for comp in fsys.system_model:
        components.append({
            "type": comp.__class__.__name__,
            "name": getattr(comp, "name", "unknown"),
            "station_in": getattr(comp, "station_in", None),
            "station_out": getattr(comp, "station_out", None)
        })

    return {"components": components}


def _get_output_parameter_names(verbose=False) -> list:
    """Retrieves the list of output parameters

    Args:
        verbose (bool): Currently unused.

    Returns:
        list: A list containing all the model parameters from the OutputTable
    """
    param_names = fsys.OutputTable.columns.tolist()
    return param_names
    

def _get_parameter_value(df: pd.DataFrame, param_name: str) -> Dict[str, Any]:
    if df is None or not isinstance(df, pd.DataFrame):
        return {"status": "invalid", "value": None, "message": "Input is not a DataFrame."}
    if not isinstance(param_name, str) or not param_name.strip():
        return {"status": "invalid", "value": None, "message": "Parameter name must be a non-empty string."}
    if df.empty:
        return {"status": "empty", "value": None, "message": "OutputTable has no rows."}
    if param_name not in df.columns:
        return {"status": "not_found", "value": None, "message": f"Column '{param_name}' not found."}

    # Get value from the last row
    val = df.iloc[-1][param_name]

    # Normalize NA/NaT to None for consistency
    if pd.isna(val):
        val = None

    # Return the successful result
    return {"status": "ok", "value": val, "message": ""}


def _log_message(caller: str, message: str, severity: str = "INFO") -> str:
    """Logs a message to the active log file with timestamp and severity.

    Args:
        caller (str): Name of the calling function.
        message (str): Log message content.
        severity (str): One of "INFO", "WARNING", "ERROR".

    Returns:
        str: Log write confirmation or error if no log file is active.
    """
    global _current_log_file

    if not _current_log_file:
        return "Logging to file not activated!"

    # Normalize severity to uppercase
    severity = severity.upper()
    if severity not in {"INFO", "WARNING", "ERROR"}:
        severity = "INFO"

    timestamp = datetime.now().strftime("%Y-%m-%d,%H:%M:%S.%f")[:-3]
    log_entry = f"{timestamp},{severity},{caller},{message}\n"
    _current_log_file.write(log_entry)
    _current_log_file.flush()
    return "Log entry written"


def _parse_parameter_string(param_string: str) -> list[str]:
    """
    Parse a comma-separated string of parameter names into a clean list.
    - Strips whitespace
    - Drops empty entries
    - De-duplicates while preserving order
    """
    seen = set()
    result = []
    for raw in param_string.split(","):
        item = raw.strip()
        if not item:
            continue
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# GSPy API functions
# -----------------------------------------------------------------------------
def initProg(**kwargs):
    """
    Initialize the gas turbine model.

    Keyword Args:
        model (str): The model module path to import. Supports either:
            - full dotted path, e.g. "projects.turbojet_api.turbojet"
            - short name, e.g. "turbojet"  (will be expanded to "projects.turbojet_api.turbojet")
        mode (str, optional): Run mode for the model, "DP" (Design Point) or "OD" (Off-Design).
            Defaults to "DP" if not provided.

    Returns:
        str: Initialization status string from the model's initialize().

    Raises:
        RuntimeError: If a model is already initialized.
        ValueError:   If 'model' is missing or 'mode' is invalid.
        ImportError/AttributeError: If the module or class cannot be imported/resolved.
    """
    global _current_model

    if _current_model is not None:
        raise RuntimeError("Model is already initialized")

    model_name = kwargs.get("model")
    if not model_name:
        raise ValueError("Missing required parameter: model")

    # Validate/normalize the mode (default = "DP")
    mode = kwargs.get("mode", "DP")
    valid_modes = {"DP", "OD"}
    if mode not in valid_modes:
        raise ValueError(f"Invalid mode '{mode}'. Allowed values: {sorted(valid_modes)}")

    # import model module + class
    module_path = model_name  # e.g. "projects.turbojet_api.turbojet" (see Fix 2)
    model_module = importlib.import_module(module_path)
    # Class name: Turbojet, Turboshaft2spool, etc.
    class_name = model_name.split(".")[-1].capitalize()
    model_class = getattr(model_module, class_name)

    instance = model_class()

    # optional: push resolved root into instance before init
    root = _resolve_model_root(module_path, model_module)
    if root is not None and hasattr(instance, "set_model_root"):
        instance.set_model_root(root)

    _current_model = instance

    # *** CALL initialize() ***
    status = None
    status = _current_model.initialize(run_mode=mode)
    return status


# -----------------------------------------------------------------------------
# Functions for logging of API actions
# -----------------------------------------------------------------------------
def activateLog(**kwargs):
    """Activates logging to a file for the current model.

    Keyword Args:
        filename (str): Optional filename for the log file (default 'api_log.txt').
        mode (str): Write mode ('w' for overwrite, 'a' for append).

    Returns:
        str: Confirmation message including file path and mode.

    Raises:
        RuntimeError: If no model is initialized.
        ValueError: If an invalid mode is provided.
    """
    if not _is_model_initialized():
        raise RuntimeError("Model not initialized")

    global _current_log_file

    model_name = _get_model_name()
    filename = kwargs.get("filename", "api_log.txt")  # Default log file name
    mode = kwargs.get("mode", "w")                    # Default is write mode, use "a" to append

    # Validate mode early
    if mode not in ("a", "w"):
        _log_message(
            caller="activateLog",
            message="Invalid mode for logging. Use 'a' (append) or 'w' (overwrite)!",
            severity="INFO",
        )
        raise ValueError("Invalid mode for logging. Use 'a' (append) or 'w' (overwrite).")

    # Prefer the model instance's output_path; fall back to legacy location
    # NOTE: BaseGasTurbineModel sets output_path (and set_model_root() updates it).
    # If not present, we write to src/system_models/output/{model_name}
    output_dir = getattr(_current_model, "output_path", None)
    if output_dir is not None:
        base_dir = Path(output_dir)
    else:
        base_dir = Path(f"src/system_models/output/{model_name}")

    # Ensure directory exists
    base_dir.mkdir(parents=True, exist_ok=True)

    # Construct full path using pathlib (safer and clearer)
    log_path = (base_dir / filename).resolve()

    # Open and prime the log file
    _current_log_file = open(log_path, mode, encoding="utf-8")
    _current_log_file.write("=== API Logging Activated ===\n")
    _log_message(caller="activateLog", message=f"Logging started in '{mode}' mode", severity="INFO")

   
def closeLog(**kwargs):
    """Closes the currently active log file and writes closing info.
    Returns:
        str: Confirmation of log closure or note if no log was open.
    """
    global _current_log_file
    if _current_log_file:
        _log_message(caller="closeLog", message="API logging deactivated", severity="INFO")
        _current_log_file.write("=== API Logging Closed ===\n")
        _current_log_file.close()
        _current_log_file = None
        return "Log closed"
    else:
        return "No log was active"
# -----------------------------------------------------------------------------


def defineDataList(name: str, params: Union[str, Iterable[str]], **kwargs) -> dict:
    """
    Define a named list of parameters in the data model.

    Parameters
    ----------
    name : str
        The list/set name, e.g. 'temperatures'.
    params : str | Iterable[str]
        Either a comma-separated string (e.g., 'T0, T2, T3')
        or an iterable of strings (['T0','T2','T3']).
    **kwargs :
        Optional metadata (e.g., tags='APU', description='T-sensors')

    Returns
    -------
    dict
        Dispatch dictionary for 'defineDataList' with keyword arguments.
    """
    # Normalize params to a list of strings
    if isinstance(params, str):
        items = _parse_parameter_string(params)
    else:
        # Clean iterable: strip, drop empties, de-duplicate preserving order
        seen = set()
        items = []
        for p in params:
            s = str(p).strip()
            if s and s not in seen:
                seen.add(s)
                items.append(s)

    if not name or not name.strip():
        raise ValueError("List name must be a non-empty string.")
    if not items:
        raise ValueError("Parameter list cannot be empty.")

    payload = {
        "function": "defineDataList",
               "args": {
            "name": name.strip(),
            "parameters": items,
            **kwargs,  # carry any extra metadata you want
        },
    }
    
    return payload


def getArraySize1D(**kwargs):
    """Return the size of a 1D data array.

    Returns:
        dict: Dispatch dictionary for 'getArraySize1D' with keyword arguments.
    """
    return {'function': 'getArraySize1D', 'args': kwargs}


def getArraySize2D(**kwargs):
    """Return the size (shape) of a 2D data array.

    Returns:
        dict: Dispatch dictionary for 'getArraySize2D' with keyword arguments.
    """
    return {'function': 'getArraySize2D', 'args': kwargs}


def getArraySize3D(**kwargs):
    """Return the size (shape) of a 3D data array.

    Returns:
        dict: Dispatch dictionary for 'getArraySize3D' with keyword arguments.
    """
    return {'function': 'getArraySize3D', 'args': kwargs}


def getD(**kwargs):
    """Retrieve a double-precision scalar value for an output parameter.

    Returns:
        dict: Dispatch dictionary for 'getD' with keyword arguments.
    """
    parameter_name = kwargs.get("parameter")
    # For now only functions are allowed
    if not parameter_name:
        raise ValueError("Missing 'parameter' argument")
    else:
        result = _get_parameter_value(fsys.OutputTable, parameter_name)
    return {'function': 'getD', 'args': kwargs, 'result': result}


def getD1D(**kwargs):
    """Retrieve a 1D array of double-precision values.

    Returns:
        dict: Dispatch dictionary for 'getD1D' with keyword arguments.
    """
    return {'function': 'getD1D', 'args': kwargs}


def getD1Dentry(**kwargs):
    """Retrieve a single entry from a 1D array of double-precision values.

    Returns:
        dict: Dispatch dictionary for 'getD1Dentry' with keyword arguments.
    """
    return {'function': 'getD1Dentry', 'args': kwargs}


def getD2Dentry(**kwargs):
    """Retrieve a single entry from a 2D array of double-precision values.

    Returns:
        dict: Dispatch dictionary for 'getD2Dentry' with keyword arguments.
    """
    return {'function': 'getD2Dentry', 'args': kwargs}


def getD3Dentry(**kwargs):
    """Retrieve a single entry from a 3D array of double-precision values.

    Returns:
        dict: Dispatch dictionary for 'getD3Dentry' with keyword arguments.
    """
    return {'function': 'getD3Dentry', 'args': kwargs}


def getDataListD(**kwargs):
    """Retrieve a list of double-precision values.

    Returns:
        dict: Dispatch dictionary for 'getDataListD' with keyword arguments.
    """
    return {'function': 'getDataListD', 'args': kwargs}


def getDataListF(**kwargs):
    """Retrieve a list of float values.

    Returns:
        dict: Dispatch dictionary for 'getDataListF' with keyword arguments.
    """
    return {'function': 'getDataListF', 'args': kwargs}


def getDataListI(**kwargs):
    """Retrieve a list of integer values.

    Returns:
        dict: Dispatch dictionary for 'getDataListI' with keyword arguments.
    """
    return {'function': 'getDataListI', 'args': kwargs}


def getDataType(**kwargs):
    """Return the data type of a specified parameter.

    Returns:
        dict: Dispatch dictionary for 'getDataType' with keyword arguments.
    """
    return {'function': 'getDataType', 'args': kwargs}


def getDescription(**kwargs):
    """Return the description string for a given parameter.

    Returns:
        dict: Dispatch dictionary for 'getDescription' with keyword arguments.
    """
    return {'function': 'getDescription', 'args': kwargs}


def getErrorMsg(**kwargs):
    """Return the last error or status message from the model.

    Returns:
        dict: Dispatch dictionary for 'getErrorMsg' with keyword arguments.
    """
    return {'function': 'getErrorMsg', 'args': kwargs}


def getF(**kwargs):
    """Retrieve a float scalar value.

    Returns:
        dict: Dispatch dictionary for 'getF' with keyword arguments.
    """
    return {'function': 'getF', 'args': kwargs}


def getF1D(**kwargs):
    """Retrieve a 1D array of float values.

    Returns:
        dict: Dispatch dictionary for 'getF1D' with keyword arguments.
    """
    return {'function': 'getF1D', 'args': kwargs}


def getF1Dentry(**kwargs):
    """Retrieve a single entry from a 1D array of float values.

    Returns:
        dict: Dispatch dictionary for 'getF1Dentry' with keyword arguments.
    """
    return {'function': 'getF1Dentry', 'args': kwargs}


def getF2Dentry(**kwargs):
    """Retrieve a single entry from a 2D array of float values.

    Returns:
        dict: Dispatch dictionary for 'getF2Dentry' with keyword arguments.
    """
    return {'function': 'getF2Dentry', 'args': kwargs}


def getF3Dentry(**kwargs):
    """Retrieve a single entry from a 3D array of float values.

    Returns:
        dict: Dispatch dictionary for 'getF3Dentry' with keyword arguments.
    """
    return {'function': 'getF3Dentry', 'args': kwargs}


def getI(**kwargs):
    """Retrieve an integer scalar value.

    Returns:
        dict: Dispatch dictionary for 'getI' with keyword arguments.
    """
    return {'function': 'getI', 'args': kwargs}


def getI1D(**kwargs):
    """Retrieve a 1D array of integer values.

    Returns:
        dict: Dispatch dictionary for 'getI1D' with keyword arguments.
    """
    return {'function': 'getI1D', 'args': kwargs}


def getI1Dentry(**kwargs):
    """Retrieve a single entry from a 1D array of integer values.

    Returns:
        dict: Dispatch dictionary for 'getI1Dentry' with keyword arguments.
    """
    return {'function': 'getI1Dentry', 'args': kwargs}


def getI2Dentry(**kwargs):
    """Retrieve a single entry from a 2D array of integer values.

    Returns:
        dict: Dispatch dictionary for 'getI2Dentry' with keyword arguments.
    """
    return {'function': 'getI2Dentry', 'args': kwargs}


def getI3Dentry(**kwargs):
    """Retrieve a single entry from a 3D array of integer values.

    Returns:
        dict: Dispatch dictionary for 'getI3Dentry' with keyword arguments.
    """
    return {'function': 'getI3Dentry', 'args': kwargs}


def getS(**kwargs):
    """Retrieve a string scalar value.

    Returns:
        dict: Dispatch dictionary for 'getS' with keyword arguments.
    """
    return {'function': 'getS', 'args': kwargs}


def getS1Dentry(**kwargs):
    """Retrieve a single entry from a 1D array of string values.

    Returns:
        dict: Dispatch dictionary for 'getS1Dentry' with keyword arguments.
    """
    return {'function': 'getS1Dentry', 'args': kwargs}


def getS2Dentry(**kwargs):
    """Retrieve a single entry from a 2D array of string values.

    Returns:
        dict: Dispatch dictionary for 'getS2Dentry' with keyword arguments.
    """
    return {'function': 'getS2Dentry', 'args': kwargs}


def getS3Dentry(**kwargs):
    """Retrieve a single entry from a 3D array of string values.

    Returns:
        dict: Dispatch dictionary for 'getS3Dentry' with keyword arguments.
    """
    return {'function': 'getS3Dentry', 'args': kwargs}


def getSeverityMax(**kwargs):
    """Return the highest severity level reported by the model/session.

    Returns:
        dict: Dispatch dictionary for 'getSeverityMax' with keyword arguments.
    """
    return {'function': 'getSeverityMax', 'args': kwargs}


def getUnits(**kwargs):
    """Return the engineering units associated with a parameter.

    Returns:
        dict: Dispatch dictionary for 'getUnits' with keyword arguments.
    """
    return {'function': 'getUnits', 'args': kwargs}


def isValidParamName(**kwargs):
    """Check whether the provided name is a valid parameter identifier.

    Returns:
        dict: Dispatch dictionary for 'isValidParamName' with keyword arguments.
    """
    parameter_name = kwargs.get("parameter")
    # For now only functions are allowed
    if not parameter_name:
        raise ValueError("Missing 'parameter' argument")
    
    result = False
    # Get parameter names from system model
    output_parameter_names = _get_output_parameter_names()
    if parameter_name in output_parameter_names:
        result = True
    
    return {'function': 'isValidParamName', 'args': kwargs, 'result': result}


def parseEfile(**kwargs):
    """Parse an engine configuration file (efile).

    Returns:
        dict: Dispatch dictionary for 'parseEfile' with keyword arguments.
    """
    return {'function': 'parseEfile', 'args': kwargs}


def parseFile(**kwargs):
    """Parse a general input file for structured data.

    Returns:
        dict: Dispatch dictionary for 'parseFile' with keyword arguments.
    """
    return {'function': 'parseFile', 'args': kwargs}


# parseString could be a generic function that calls other functions by string name
def parseString(**kwargs):
    """Parse a function name from a string and dispatch the corresponding local function.

    Keyword Args:
        function (str): The name of the function to invoke.
        ...: All remaining keyword arguments are passed through to the target function.

    Returns:
        Any: Result of the dispatched function.

    Raises:
        ValueError: If function name is missing or does not resolve to a callable.
    """
    _log_message(caller="parseString",
                message="parseString called " + (', '.join(f"{k}={v}" for k, v in kwargs.items())),
                severity="INFO")

    function_name = kwargs.get("function")
    # For now only functions are allowed
    if not function_name:
        raise ValueError("Missing 'function' argument")

    # Get the function object by name from the current module (or a known module)
    local_functions = globals()  # Or use `vars(module)` for external ones

    func = local_functions.get('_'+function_name)
    if not callable(func):
        raise ValueError(f"Function '{function_name}' is not callable or doesn't exist")

    # Remove 'function' from kwargs
    call_args = {k: v for k, v in kwargs.items() if k != "function"}

    return func(**call_args)


def run(**kwargs):
    """Execute the current engine simulation run via the active model.

    Returns:
        Any: Result returned by the model's run() method.

    Raises:
        RuntimeError: If no model has been initialized.
    """
    _log_message(caller="run", message="Starting engine simulation", severity="INFO")
    if _current_model is None:
        _log_message(caller="run", message="Engine simulation aborted, no model initialized!", severity="ERROR")
        raise RuntimeError("No model initialized")
    return _current_model.run()


def setD(**kwargs):
    """Set a double-precision scalar value.

    Returns:
        dict: Dispatch dictionary for 'setD' with keyword arguments.
    """
    return {'function': 'setD', 'args': kwargs}


def setD1D(**kwargs):
    """Set a 1D array of double-precision values.

    Returns:
        dict: Dispatch dictionary for 'setD1D' with keyword arguments.
    """
    return {'function': 'setD1D', 'args': kwargs}


def setD1Dentry(**kwargs):
    """Set a single entry in a 1D array of double-precision values.

    Returns:
        dict: Dispatch dictionary for 'setD1Dentry' with keyword arguments.
    """
    return {'function': 'setD1Dentry', 'args': kwargs}


def setD2Dentry(**kwargs):
    """Set a single entry in a 2D array of double-precision values.

    Returns:
        dict: Dispatch dictionary for 'setD2Dentry' with keyword arguments.
    """
    return {'function': 'setD2Dentry', 'args': kwargs}


def setD3Dentry(**kwargs):
    """Set a single entry in a 3D array of double-precision values.

    Returns:
        dict: Dispatch dictionary for 'setD3Dentry' with keyword arguments.
    """
    return {'function': 'setD3Dentry', 'args': kwargs}


def setDataListD(**kwargs):
    """Set a list of double-precision values.

    Returns:
        dict: Dispatch dictionary for 'setDataListD' with keyword arguments.
    """
    return {'function': 'setDataListD', 'args': kwargs}


def setDataListF(**kwargs):
    """Set a list of float values.

    Returns:
        dict: Dispatch dictionary for 'setDataListF' with keyword arguments.
    """
    return {'function': 'setDataListF', 'args': kwargs}


def setDataListI(**kwargs):
    """Set a list of integer values.

    Returns:
        dict: Dispatch dictionary for 'setDataListI' with keyword arguments.
    """
    return {'function': 'setDataListI', 'args': kwargs}


def setF(**kwargs):
    """Set a float scalar value.

    Returns:
        dict: Dispatch dictionary for 'setF' with keyword arguments.
    """
    return {'function': 'setF', 'args': kwargs}


def setF1D(**kwargs):
    """Set a 1D array of float values.

    Returns:
        dict: Dispatch dictionary for 'setF1D' with keyword arguments.
    """
    return {'function': 'setF1D', 'args': kwargs}


def setF1Dentry(**kwargs):
    """Set a single entry in a 1D array of float values.

    Returns:
        dict: Dispatch dictionary for 'setF1Dentry' with keyword arguments.
    """
    return {'function': 'setF1Dentry', 'args': kwargs}


def setF2Dentry(**kwargs):
    """Set a single entry in a 2D array of float values.

    Returns:
        dict: Dispatch dictionary for 'setF2Dentry' with keyword arguments.
    """
    return {'function': 'setF2Dentry', 'args': kwargs}


def setF3Dentry(**kwargs):
    """Set a single entry in a 3D array of float values.

    Returns:
        dict: Dispatch dictionary for 'setF3Dentry' with keyword arguments.
    """
    return {'function': 'setF3Dentry', 'args': kwargs}


def setI(**kwargs):
    """Set an integer scalar value.

    Returns:
        dict: Dispatch dictionary for 'setI' with keyword arguments.
    """
    return {'function': 'setI', 'args': kwargs}


def setI1D(**kwargs):
    """Set a 1D array of integer values.

    Returns:
        dict: Dispatch dictionary for 'setI1D' with keyword arguments.
    """
    return {'function': 'setI1D', 'args': kwargs}


def setI1Dentry(**kwargs):
    """Set a single entry in a 1D array of integer values.

    Returns:
        dict: Dispatch dictionary for 'setI1Dentry' with keyword arguments.
    """
    return {'function': 'setI1Dentry', 'args': kwargs}


def setI2Dentry(**kwargs):
    """Set a single entry in a 2D array of integer values.

    Returns:
        dict: Dispatch dictionary for 'setI2Dentry' with keyword arguments.
    """
    return {'function': 'setI2Dentry', 'args': kwargs}


def setI3Dentry(**kwargs):
    """Set a single entry in a 3D array of integer values.

    Returns:
        dict: Dispatch dictionary for 'setI3Dentry' with keyword arguments.
    """
    return {'function': 'setI3Dentry', 'args': kwargs}


def setS(**kwargs):
    """Set a string scalar value.

    Returns:
        dict: Dispatch dictionary for 'setS' with keyword arguments.
    """
    return {'function': 'setS', 'args': kwargs}


def setS1Dentry(**kwargs):
    """Set a single entry in a 1D array of string values.

    Returns:
        dict: Dispatch dictionary for 'setS1Dentry' with keyword arguments.
    """
    return {'function': 'setS1Dentry', 'args': kwargs}


def setS2Dentry(**kwargs):
    """Set a single entry in a 2D array of string values.

    Returns:
        dict: Dispatch dictionary for 'setS2Dentry' with keyword arguments.
    """
    return {'function': 'setS2Dentry', 'args': kwargs}


def setS3Dentry(**kwargs):
    """Set a single entry in a 3D array of string values.

    Returns:
        dict: Dispatch dictionary for 'setS3Dentry' with keyword arguments.
    """
    return {'function': 'setS3Dentry', 'args': kwargs}


def terminate(**kwargs):
    """Terminate the currently active engine model and close the log file.

    Returns:
        dict | str: Termination confirmation, or notice if no model was active.
    """
    global _current_model, _current_log_file
    _log_message(caller="terminate", message="terminate called", severity="INFO")

    if _current_model is not None:
        model_name = _current_model.model_name if hasattr(_current_model, "model_name") else "unknown"
        _current_model = None
        _log_message(caller="terminate", message="Model correctly terminated", severity="INFO")
        result = {'function': 'terminate', 'args': kwargs, 'result': f"{model_name} terminated and cleaned up"}
    else:
        _log_message(caller="terminate", message="No model initialized!", severity="WARNING")
        result = "No model was initialized."

    # Now close the log file after logging is finished
    closeLog()
    return result
