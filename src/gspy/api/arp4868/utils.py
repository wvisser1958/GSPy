from __future__ import annotations

import ast
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Tuple

import pandas as pd


INVALID_NUM = -999.0
INVALID_INT = -999


def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec='seconds') + 'Z'


def resolve_output_table(model: Any) -> pd.DataFrame | None:
    """Best-effort retrieval of a pandas DataFrame holding results.

    Expected (common) attribute names:
      - OutputTable
      - output_table
      - results

    Returns None if not found or not a DataFrame.
    """
    candidates = ['OutputTable', 'output_table', 'results', 'ResultsTable', 'output']
    for name in candidates:
        if hasattr(model, name):
            obj = getattr(model, name)
            if isinstance(obj, pd.DataFrame):
                return obj
    return None


def output_has_param(df: pd.DataFrame, param_name: str) -> bool:
    return isinstance(df, pd.DataFrame) and (param_name in df.columns)


def get_last_value(df: pd.DataFrame, param_name: str) -> Any:
    """Returns the last-row value for the given column name."""
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        raise KeyError('OutputTable is missing or empty')
    if param_name not in df.columns:
        raise KeyError(f"Column '{param_name}' not found")
    return df.iloc[-1][param_name]


def best_effort_run(model: Any) -> None:
    """Call a suitable run method on the model."""
    for name in ('run', 'Run', 'execute', 'Execute', 'simulate', 'Simulate'):
        if hasattr(model, name) and callable(getattr(model, name)):
            getattr(model, name)()
            return
    raise AttributeError('No runnable method found on model (expected run/execute/simulate)')


def best_effort_set(model: Any, param_name: str, value: Any) -> None:
    """Set input value on the model.

    Since we intentionally do not use a registry in this version, this function
    attempts multiple strategies:
      1) model.set(param_name, value)
      2) model.set_param(param_name, value)
      3) attribute path (dot-separated): e.g. 'ambient.Ts000'
      4) dict-like: model.inputs[param_name]

    If all fail, raises AttributeError.
    """
    # 1) explicit setter methods
    for name in ('set', 'set_param', 'setParam', 'set_value', 'setValue'):
        if hasattr(model, name) and callable(getattr(model, name)):
            try:
                getattr(model, name)(param_name, value)
                return
            except TypeError:
                # wrong signature; ignore
                pass

    # 2) attribute path
    if '.' in param_name:
        parts = param_name.split('.')
        obj = model
        for p in parts[:-1]:
            if not hasattr(obj, p):
                raise AttributeError(f"Cannot resolve '{param_name}': missing '{p}'")
            obj = getattr(obj, p)
        setattr(obj, parts[-1], value)
        return

    # 3) common dict containers
    for name in ('inputs', 'Inputs', 'params', 'Params', 'parameters'):
        if hasattr(model, name):
            d = getattr(model, name)
            if isinstance(d, dict):
                d[param_name] = value
                return

    # 4) last resort: direct attribute
    if hasattr(model, param_name):
        setattr(model, param_name, value)
        return

    raise AttributeError(f"Parameter '{param_name}' not settable by best-effort strategies")


def parse_assignments(text: str) -> list[tuple[str, str, str]]:
    """Parse a simple command string into (dtype, name, value).

    Supported forms (semicolon-separated):
      - setD NAME=VALUE
      - setF NAME=VALUE
      - setI NAME=VALUE
      - setS NAME=VALUE

    Returns list of (dtype, name, value_str)
    """
    items = []
    for stmt in [s.strip() for s in text.split(';') if s.strip()]:
        m = re.match(r'^(set[DFIS])\s+([^=\s]+)\s*=\s*(.+)$', stmt, flags=re.IGNORECASE)
        if not m:
            raise ValueError(f"Unsupported parseString statement: '{stmt}'")
        op = m.group(1).lower()
        dtype = op[-1].upper()  # D/F/I/S
        name = m.group(2).strip()
        value = m.group(3).strip()
        items.append((dtype, name, value))
    return items


def coerce(dtype: str, value_str: str) -> Any:
    """Coerce value string to the requested dtype."""
    dtype = dtype.upper()
    if dtype == 'S':
        # allow quoted strings; otherwise take raw
        try:
            v = ast.literal_eval(value_str)
            return str(v)
        except Exception:
            return value_str
    if dtype == 'I':
        return int(float(value_str))
    if dtype in ('F', 'D'):
        return float(value_str)
    raise ValueError(f"Unsupported dtype '{dtype}'")
