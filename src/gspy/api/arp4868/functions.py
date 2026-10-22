from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path
from typing import Any, List

import pandas as pd

from .session import Session
from .utils import (
    INVALID_INT,
    INVALID_NUM,
    now_iso,
    resolve_output_table,
    output_has_param,
    get_last_value,
    best_effort_run,
    best_effort_set,
    parse_assignments,
    coerce,
)


_SESSION = Session()


# -------------------------
# Internal helpers
# -------------------------

def _ok() -> int:
    _SESSION.last_error_msg = ""
    _SESSION.last_funct_status = 0
    return 0


def _err(msg: str, code: int = 1) -> int:
    _SESSION.last_error_msg = msg
    _SESSION.last_funct_status = code
    _SESSION.write_log(f"[{now_iso()}] ERROR {msg}")
    return code


def _require_init(fname: str) -> int | None:
    if not _SESSION.initialized:
        _err(f"{fname}: called before py4868initProg")
        return 1
    return None


def _df_or_none() -> pd.DataFrame | None:
    if not _SESSION.model:
        return None
    return resolve_output_table(_SESSION.model)


# -------------------------
# ARP4868 core lifecycle
# -------------------------

def py4868initProg(numArgs: int, args: List[str]) -> int:
    """Initialize the Engine Program.

    Proposed Python-friendly convention:
      args[0] = model_module (e.g. 'projects.turbojet.turbojet_api')
      args[1] = factory_name (optional, default 'build_model')
      args[2] = project_root (optional)

    The model module should expose a factory that returns a configured TSystemModel.
    """
    if numArgs < 1 or not args or not str(args[0]).strip():
        return _err("initProg: model_module not provided")
    print(args[0] if numArgs >= 1 else None, args[1] if numArgs >= 2 else 'build_model', args[2] if numArgs >= 3 else None)
    model_module = str(args[0]).strip()
    factory_name = str(args[1]).strip() if numArgs >= 2 and args[1] else 'build_model'
    project_root = Path(args[2]).resolve() if numArgs >= 3 and args[2] else None

    try:
        mod = import_module(model_module)
    except Exception as e:
        return _err(f"initProg: cannot import '{model_module}': {e}")

    factory = getattr(mod, factory_name, None)
    if factory is None or not callable(factory):
        return _err(f"initProg: factory '{factory_name}' not found/callable in '{model_module}'")

    try:
        model = factory(project_root=project_root)
    except TypeError:
        # factory might not accept project_root
        try:
            model = factory()
        except Exception as e:
            return _err(f"initProg: factory '{factory_name}' failed: {e}")
    except Exception as e:
        return _err(f"initProg: factory '{factory_name}' failed: {e}")

    _SESSION.reset()
    _SESSION.model = model
    _SESSION.initialized = True
    _SESSION.severity_max = 0
    _SESSION.write_log(f"[{now_iso()}] INFO initProg loaded model '{model_module}:{factory_name}'")
    return _ok()


def py4868terminate() -> int:
    """Terminate the Engine Program session."""
    if _require_init('terminate') is not None:
        # per ARP4868, terminate should still exist; we keep it safe
        _SESSION.reset()
        return 1

    # best-effort model shutdown
    for name in ('terminate', 'Terminate', 'close', 'Close', 'shutdown', 'Shutdown'):
        if hasattr(_SESSION.model, name) and callable(getattr(_SESSION.model, name)):
            try:
                getattr(_SESSION.model, name)()
            except Exception:
                pass
            break

    _SESSION.write_log(f"[{now_iso()}] INFO terminate")
    _SESSION.reset()
    return _ok()


def py4868run() -> int:
    if _require_init('run') is not None:
        return 1
    try:
        best_effort_run(_SESSION.model)
        # best-effort severity: if model carries it
        sev = getattr(_SESSION.model, 'severity_max', None)
        if sev is None:
            sev = getattr(_SESSION.model, 'SeverityMax', None)
        _SESSION.severity_max = int(sev) if sev is not None else _SESSION.severity_max
        _SESSION.write_log(f"[{now_iso()}] INFO run")
        return _ok()
    except Exception as e:
        _SESSION.severity_max = 99
        return _err(f"run: model execution failed: {e}", code=2)


# -------------------------
# API logging
# -------------------------

def py4868activateLog(fileName: str) -> int:
    if _require_init('activateLog') is not None:
        return 1

    target = (fileName or '').strip() or 'stdOut'
    try:
        if target == 'stdOut':
            _SESSION.log = sys.stdout
        elif target == 'stdErr':
            _SESSION.log = sys.stderr
        else:
            _SESSION.log = open(target, 'w', encoding='utf-8')
        _SESSION.write_log(f"=== API Logging Activated ({target}) ===")
        return _ok()
    except Exception as e:
        return _err(f"activateLog: cannot open '{fileName}': {e}")


def py4868closeLog() -> int:
    if _require_init('closeLog') is not None:
        return 1
    _SESSION.write_log("=== API Logging Closed ===")
    _SESSION.close_log()
    return _ok()


# -------------------------
# Error reporting and attributes
# -------------------------

def py4868getErrorMsg(message_out: List[str], buffSize: int) -> int:
    """Return the error message for the immediately prior API call."""
    if not _SESSION.initialized:
        # ARP: error if called before init
        msg = "getErrorMsg: called before py4868initProg"
        message_out[:] = [msg[:max(buffSize - 1, 0)]]
        return _err(msg)

    msg = (_SESSION.last_error_msg or '')[:max(buffSize - 1, 0)]
    message_out[:] = [msg]
    return _ok()


def py4868getSeverityMax(severity_out: List[int]) -> int:
    if _require_init('getSeverityMax') is not None:
        severity_out[:] = [999]
        return 1
    severity_out[:] = [int(_SESSION.severity_max)]
    return _ok()


def py4868getDataType(paramName: str, dataType_out: List[str], buffSize: int = 32) -> int:
    """Best-effort datatype from OutputTable column dtype.

    Returns 'UNDEF' if unknown/missing.
    """
    if _require_init('getDataType') is not None:
        dataType_out[:] = ['UNDEF']
        return 1

    df = _df_or_none()
    if df is None or not isinstance(df, pd.DataFrame) or paramName not in df.columns:
        dataType_out[:] = ['UNDEF']
        return _err(f"getDataType: parameter '{paramName}' not found in OutputTable")

    dt = df[paramName].dtype
    # Map pandas dtype to ARP4868 strings
    s = 'UNDEF'
    if pd.api.types.is_integer_dtype(dt):
        s = 'I'
    elif pd.api.types.is_float_dtype(dt):
        s = 'D'
    elif pd.api.types.is_string_dtype(dt) or dt == object:
        s = 'S'

    dataType_out[:] = [s[:max(buffSize - 1, 0)]]
    return _ok()


def py4868getUnits(paramName: str, units_out: List[str], buffSize: int = 64) -> int:
    """No registry: returns empty string by default."""
    if _require_init('getUnits') is not None:
        units_out[:] = ['']
        return 1
    units_out[:] = ['']
    return _ok()


def py4868getDescription(paramName: str, descr_out: List[str], buffSize: int = 256) -> int:
    """No registry: returns empty string by default."""
    if _require_init('getDescription') is not None:
        descr_out[:] = ['']
        return 1
    descr_out[:] = ['']
    return _ok()


def py4868isValidParamName(paramName: str, valid_out: List[int]) -> int:
    if _require_init('isValidParamName') is not None:
        valid_out[:] = [0]
        return 1

    df = _df_or_none()
    valid_out[:] = [1 if (df is not None and isinstance(df, pd.DataFrame) and paramName in df.columns) else 0]
    # Not an error if invalid; per ARP, invalid just returns FALSE
    return _ok()


# -------------------------
# Scalar get (from OutputTable)
# -------------------------

def py4868getD(paramName: str, value_out: List[float]) -> int:
    if _require_init('getD') is not None:
        value_out[:] = [INVALID_NUM]
        return 1
    df = _df_or_none()
    try:
        v = float(get_last_value(df, paramName))
        value_out[:] = [v]
        return _ok()
    except Exception as e:
        value_out[:] = [INVALID_NUM]
        return _err(f"getD: {e}")


def py4868getF(paramName: str, value_out: List[float]) -> int:
    # float32 in ARP; Python float is double, but caller can cast
    return py4868getD(paramName, value_out)


def py4868getI(paramName: str, value_out: List[int]) -> int:
    if _require_init('getI') is not None:
        value_out[:] = [INVALID_INT]
        return 1
    df = _df_or_none()
    try:
        v = int(float(get_last_value(df, paramName)))
        value_out[:] = [v]
        return _ok()
    except Exception as e:
        value_out[:] = [INVALID_INT]
        return _err(f"getI: {e}")


def py4868getS(paramName: str, value_out: List[str], buffSize: int = 1024) -> int:
    if _require_init('getS') is not None:
        value_out[:] = ['']
        return 1
    df = _df_or_none()
    try:
        v = str(get_last_value(df, paramName))
        v = v[:max(buffSize - 1, 0)]
        value_out[:] = [v]
        return _ok()
    except Exception as e:
        value_out[:] = ['']
        return _err(f"getS: {e}")


# -------------------------
# Scalar set (best-effort)
# -------------------------

def py4868setD(paramName: str, value: float) -> int:
    if _require_init('setD') is not None:
        return 1
    try:
        best_effort_set(_SESSION.model, paramName, float(value))
        return _ok()
    except Exception as e:
        return _err(f"setD: {e}")


def py4868setF(paramName: str, value: float) -> int:
    return py4868setD(paramName, float(value))


def py4868setI(paramName: str, value: int) -> int:
    if _require_init('setI') is not None:
        return 1
    try:
        best_effort_set(_SESSION.model, paramName, int(value))
        return _ok()
    except Exception as e:
        return _err(f"setI: {e}")


def py4868setS(paramName: str, value: str) -> int:
    if _require_init('setS') is not None:
        return 1
    try:
        best_effort_set(_SESSION.model, paramName, str(value))
        return _ok()
    except Exception as e:
        return _err(f"setS: {e}")


# -------------------------
# 1D arrays (minimal)
# -------------------------

def py4868getArraySize1D(paramName: str, numX_out: List[int]) -> int:
    """If OutputTable column holds list/tuple/np array, return len()."""
    if _require_init('getArraySize1D') is not None:
        numX_out[:] = [INVALID_INT]
        return 1
    df = _df_or_none()
    try:
        v = get_last_value(df, paramName)
        numX_out[:] = [len(v)]
        return _ok()
    except Exception as e:
        numX_out[:] = [INVALID_INT]
        return _err(f"getArraySize1D: {e}")


def py4868getArraySize2D(paramName: str, numX_out: List[int], numY_out: List[int]) -> int:
    if _require_init('getArraySize2D') is not None:
        numX_out[:] = [INVALID_INT]
        numY_out[:] = [INVALID_INT]
        return 1
    df = _df_or_none()
    try:
        v = get_last_value(df, paramName)
        numX_out[:] = [len(v)]
        numY_out[:] = [len(v[0])]
        return _ok()
    except Exception as e:
        numX_out[:] = [INVALID_INT]
        numY_out[:] = [INVALID_INT]
        return _err(f"getArraySize2D: {e}")


def py4868getArraySize3D(paramName: str, numX_out: List[int], numY_out: List[int], numZ_out: List[int]) -> int:
    if _require_init('getArraySize3D') is not None:
        numX_out[:] = [INVALID_INT]
        numY_out[:] = [INVALID_INT]
        numZ_out[:] = [INVALID_INT]
        return 1
    df = _df_or_none()
    try:
        v = get_last_value(df, paramName)
        numX_out[:] = [len(v)]
        numY_out[:] = [len(v[0])]
        numZ_out[:] = [len(v[0][0])]
        return _ok()
    except Exception as e:
        numX_out[:] = [INVALID_INT]
        numY_out[:] = [INVALID_INT]
        numZ_out[:] = [INVALID_INT]
        return _err(f"getArraySize3D: {e}")


def py4868getD1D(paramName: str, array_out: List[float], numGet: int) -> int:
    if _require_init('getD1D') is not None:
        array_out[:] = [INVALID_NUM] * max(numGet, 0)
        return 1
    df = _df_or_none()
    try:
        v = list(get_last_value(df, paramName))
        out = [float(x) for x in v[:numGet]]
        if len(out) < numGet:
            out += [INVALID_NUM] * (numGet - len(out))
        array_out[:] = out
        return _ok()
    except Exception as e:
        array_out[:] = [INVALID_NUM] * max(numGet, 0)
        return _err(f"getD1D: {e}")


def py4868getF1D(paramName: str, array_out: List[float], numGet: int) -> int:
    return py4868getD1D(paramName, array_out, numGet)


def py4868getI1D(paramName: str, array_out: List[int], numGet: int) -> int:
    if _require_init('getI1D') is not None:
        array_out[:] = [INVALID_INT] * max(numGet, 0)
        return 1
    df = _df_or_none()
    try:
        v = list(get_last_value(df, paramName))
        out = [int(float(x)) for x in v[:numGet]]
        if len(out) < numGet:
            out += [INVALID_INT] * (numGet - len(out))
        array_out[:] = out
        return _ok()
    except Exception as e:
        array_out[:] = [INVALID_INT] * max(numGet, 0)
        return _err(f"getI1D: {e}")


def py4868setD1D(paramName: str, array: List[float], numSet: int) -> int:
    if _require_init('setD1D') is not None:
        return 1
    try:
        best_effort_set(_SESSION.model, paramName, [float(x) for x in array[:numSet]])
        return _ok()
    except Exception as e:
        return _err(f"setD1D: {e}")


def py4868setF1D(paramName: str, array: List[float], numSet: int) -> int:
    return py4868setD1D(paramName, array, numSet)


def py4868setI1D(paramName: str, array: List[int], numSet: int) -> int:
    if _require_init('setI1D') is not None:
        return 1
    try:
        best_effort_set(_SESSION.model, paramName, [int(x) for x in array[:numSet]])
        return _ok()
    except Exception as e:
        return _err(f"setI1D: {e}")


# -------------------------
# DataList functions (minimal)
# -------------------------

def py4868defineDataList(paramList: List[str], size: int, dataType: str, listID_out: List[int]) -> int:
    if _require_init('defineDataList') is not None:
        listID_out[:] = [-1]
        return 1
    if size != len(paramList):
        listID_out[:] = [-1]
        return _err('defineDataList: size mismatch with paramList')

    list_id = _SESSION.next_list_id()
    _SESSION.data_lists[list_id] = (str(dataType).strip().upper(), list(paramList))
    listID_out[:] = [list_id]
    return _ok()


def _get_list(listID: int, expect: str) -> tuple[str, List[str]] | None:
    entry = _SESSION.data_lists.get(int(listID))
    if not entry:
        _err(f"{expect}: invalid listID {listID}")
        return None
    return entry


def py4868getDataListD(listID: int, array_out: List[float], size: int) -> int:
    if _require_init('getDataListD') is not None:
        array_out[:] = [INVALID_NUM] * max(size, 0)
        return 1
    entry = _get_list(listID, 'getDataListD')
    if entry is None:
        array_out[:] = [INVALID_NUM] * max(size, 0)
        return 1
    dtype, names = entry
    if size != len(names):
        array_out[:] = [INVALID_NUM] * max(size, 0)
        return _err('getDataListD: size mismatch with defined list')

    df = _df_or_none()
    out = []
    for n in names:
        try:
            out.append(float(get_last_value(df, n)))
        except Exception:
            out.append(INVALID_NUM)
    array_out[:] = out
    return _ok()


def py4868getDataListF(listID: int, array_out: List[float], size: int) -> int:
    return py4868getDataListD(listID, array_out, size)


def py4868getDataListI(listID: int, array_out: List[int], size: int) -> int:
    if _require_init('getDataListI') is not None:
        array_out[:] = [INVALID_INT] * max(size, 0)
        return 1
    entry = _get_list(listID, 'getDataListI')
    if entry is None:
        array_out[:] = [INVALID_INT] * max(size, 0)
        return 1
    dtype, names = entry
    if size != len(names):
        array_out[:] = [INVALID_INT] * max(size, 0)
        return _err('getDataListI: size mismatch with defined list')

    df = _df_or_none()
    out = []
    for n in names:
        try:
            out.append(int(float(get_last_value(df, n))))
        except Exception:
            out.append(INVALID_INT)
    array_out[:] = out
    return _ok()


def py4868setDataListD(listID: int, array: List[float], size: int) -> int:
    if _require_init('setDataListD') is not None:
        return 1
    entry = _get_list(listID, 'setDataListD')
    if entry is None:
        return 1
    _, names = entry
    if size != len(names):
        return _err('setDataListD: size mismatch with defined list')
    for n, v in zip(names, array[:size]):
        st = py4868setD(n, float(v))
        if st != 0:
            # keep going (ARP: retain position, do nothing for invalid)
            continue
    return _ok()


def py4868setDataListF(listID: int, array: List[float], size: int) -> int:
    return py4868setDataListD(listID, array, size)


def py4868setDataListI(listID: int, array: List[int], size: int) -> int:
    if _require_init('setDataListI') is not None:
        return 1
    entry = _get_list(listID, 'setDataListI')
    if entry is None:
        return 1
    _, names = entry
    if size != len(names):
        return _err('setDataListI: size mismatch with defined list')
    for n, v in zip(names, array[:size]):
        st = py4868setI(n, int(v))
        if st != 0:
            continue
    return _ok()


# -------------------------
# Parse functions
# -------------------------

def py4868parseFile(filename: str) -> int:
    """Parse a plain text input file.

    Minimal supported formats:
      1) CSV with columns: name,value[,type]

    This function simply calls the relevant py4868set* for each row.
    """
    if _require_init('parseFile') is not None:
        return 1

    path = Path(filename)
    if not path.exists():
        return _err(f"parseFile: file not found '{filename}'")

    try:
        df = pd.read_csv(path)
        if 'name' not in df.columns or 'value' not in df.columns:
            return _err("parseFile: CSV must contain 'name' and 'value' columns")

        for _, row in df.iterrows():
            name = str(row['name']).strip()
            dtype = str(row.get('type', 'D')).strip().upper() or 'D'
            val = row['value']

            if dtype == 'D':
                py4868setD(name, float(val))
            elif dtype == 'F':
                py4868setF(name, float(val))
            elif dtype == 'I':
                py4868setI(name, int(float(val)))
            elif dtype == 'S':
                py4868setS(name, str(val))
            else:
                return _err(f"parseFile: unsupported type '{dtype}' for '{name}'")

        return _ok()
    except Exception as e:
        return _err(f"parseFile: failed to parse '{filename}': {e}")


def py4868parseEfile(filename: str) -> int:
    """Encrypted file parsing is not supported in this minimal implementation."""
    if _require_init('parseEfile') is not None:
        return 1
    return _err('parseEfile: not supported in this implementation')


def py4868parseString(text: str) -> int:
    """Parse a semicolon-separated command string.

    Supported statements:
      setD NAME=VALUE; setI NAME=VALUE; setS NAME=VALUE

    This is intentionally small and safe; it does NOT eval arbitrary Python.
    """
    if _require_init('parseString') is not None:
        return 1

    try:
        assignments = parse_assignments(text)
        for dtype, name, value_str in assignments:
            value = coerce(dtype, value_str)
            if dtype == 'D':
                py4868setD(name, float(value))
            elif dtype == 'F':
                py4868setF(name, float(value))
            elif dtype == 'I':
                py4868setI(name, int(value))
            elif dtype == 'S':
                py4868setS(name, str(value))
        return _ok()
    except Exception as e:
        return _err(f"parseString: {e}")
