# gspy_arp4868 (minimal framework)

This package provides a **function-based** ARP4868-style API for GSPy with the **Python prefix** `py4868*`.

## Key design choice in this version

✅ **No parameter registry.** All `get*` calls retrieve values from the **last row** of the model's `OutputTable` (a pandas DataFrame). This matches your plan to **query parameters from output table results**.

## Expected model contract

Your model module should expose a factory function:

```python
def build_model(project_root=None):
    return TSystemModel(...)
```

The factory should **only configure** the model (components, connections, maps). It should **not**:
- call `run()`
- set ambient or other inputs

Inputs are provided via `py4868set*` / `py4868parseFile` / `py4868parseString` from the calling program.

## Calling program example

```python
from gspy_arp4868 import *

args = ["projects.turbojet.turbojet_api", "build_model", "./projects/turbojet"]
assert py4868initProg(len(args), args) == 0

py4868activateLog("stdOut")
py4868parseFile("./projects/turbojet/input/Turbojet_AMinput.csv")
py4868run()

Fn = [0.0]
py4868getD("Fn", Fn)
print("Fn", Fn[0])

py4868terminate()
```

## Notes

- `py4868set*` is implemented as **best-effort** without a registry:
  it tries common setter methods (`set`, `set_param`, ...), dot-path assignment (`ambient.Ts000`), `model.inputs[...]`, or direct attributes.
- `py4868getUnits` and `py4868getDescription` return empty strings by default (allowed by ARP4868).
- `py4868getDataType` is inferred from the OutputTable column dtype.

## Files

- `gspy_arp4868/session.py` : session state
- `gspy_arp4868/utils.py`   : OutputTable helpers, best-effort set/run, parseString
- `gspy_arp4868/functions.py`: `py4868*` functions
