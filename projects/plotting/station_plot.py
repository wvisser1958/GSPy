from __future__ import annotations
from pathlib import Path

import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os


def resolve_csv_path(
    csv_path: str | os.PathLike,
    *,
    base: str = "script",   # "script" or "cwd"
    must_exist: bool = True,
    search: bool = True,
) -> Path:
    """
    Resolve csv_path robustly.

    - If csv_path is absolute and exists -> return it
    - If relative:
        - base="script": resolve relative to this .py file directory
        - base="cwd": resolve relative to current working directory
    - If not found and search=True:
        - search a few common project locations
        - search recursively by filename (last resort)

    Returns a Path (existing if must_exist=True).
    """
    p = Path(csv_path)

    # 1) Absolute path
    if p.is_absolute():
        if (not must_exist) or p.exists():
            return p
        raise FileNotFoundError(f"Absolute path not found: {p}")

    # 2) Relative path, try base folder
    script_dir = Path(__file__).resolve().parent
    cwd_dir = Path.cwd()

    base_dir = script_dir if base.lower() == "script" else cwd_dir
    candidate = (base_dir / p).resolve()
    if (not must_exist) or candidate.exists():
        return candidate

    # 3) If requested, try a few likely roots / locations
    tried = [candidate]

    if search:
        # try relative to script_dir and cwd_dir explicitly
        for root in [script_dir, cwd_dir]:
            cand = (root / p).resolve()
            if cand not in tried:
                tried.append(cand)
            if cand.exists():
                return cand

        # try walking upward from script_dir (project root often above /projects/plotting/)
        for parent in [script_dir] + list(script_dir.parents):
            cand = (parent / p).resolve()
            if cand not in tried:
                tried.append(cand)
            if cand.exists():
                return cand

        # last resort: find by filename anywhere under script_dir parents (can be slow on huge repos)
        filename = Path(p).name
        for parent in [script_dir] + list(script_dir.parents):
            hits = list(parent.rglob(filename))
            # prefer exact suffix match (…/turbojet/output/turbojet.csv) if it exists
            for h in hits:
                if h.as_posix().endswith(Path(p).as_posix().replace("\\", "/")):
                    return h.resolve()
            if hits:
                return hits[0].resolve()

    # 4) Give a helpful error
    msg = [
        f"Could not find CSV: {csv_path!s}",
        f"Current working directory: {cwd_dir}",
        f"Script directory:          {script_dir}",
        "Tried:",
        *[f"  - {t}" for t in tried],
        "",
        "Tip: pass an absolute path or set base='cwd'/'script' as needed.",
    ]
    raise FileNotFoundError("\n".join(msg))


def read_gspy_csv(csv_path: str | os.PathLike, *, base: str = "script") -> pd.DataFrame:
    resolved = resolve_csv_path(csv_path, base=base, search=True)
    print(f"Reading CSV from: {resolved}")
    return pd.read_csv(resolved)


def station_location_sort_key(loc: str):
    # numeric sort by location
    return int(loc)


def parse_station_suffix(suffix: str):
    """
    Parse AS755-like station suffix into:
      stream: int
      location: str  (normalized, at least 3 digits, may be longer)
      aggregate: bool (suffix ends with 'A')

    Examples:
      030   -> stream=0,  loc='030', aggregate=False
      130   -> stream=1,  loc='030', aggregate=False
      1311  -> stream=1,  loc='311', aggregate=False
      13_11 -> stream=13, loc='011', aggregate=False
      010A  -> stream=0,  loc='010', aggregate=True
    """
    s = str(suffix).strip()

    aggregate = False
    if s.endswith("A"):
        aggregate = True
        s = s[:-1]

    if "_" in s:
        parts = s.split("_")
        if not parts[0].isdigit():
            raise ValueError(f"Invalid station suffix (stream not numeric): {suffix!r}")
        stream = int(parts[0])

        loc_digits = "".join(parts[1:])
        if loc_digits == "" or not loc_digits.isdigit():
            raise ValueError(f"Invalid station suffix (location not numeric): {suffix!r}")
    else:
        if not s.isdigit() or len(s) < 2:
            raise ValueError(f"Invalid station suffix: {suffix!r}")
        stream = int(s[0])   # by standard: single digit stream if no underscore
        loc_digits = s[1:]

    loc_norm = loc_digits.zfill(3) if len(loc_digits) < 3 else loc_digits
    return stream, loc_norm, aggregate


def station_order_key(station_suffix: str):
    """
    Sort key primarily by location along the engine, then by stream.
    Aggregate 'A' stations are placed after non-aggregate at same location.
    """
    stream, loc, aggregate = parse_station_suffix(station_suffix)
    return (int(loc), 1 if aggregate else 0, stream, station_suffix)


def _find_param_station_columns(columns, param_prefix: str):
    """
    Return dict: station_suffix -> full_column_name

    Matches param+station suffix where suffix is digits/underscores with optional trailing 'A'
    e.g.: P030, P130, P13_11, P1311, P010A
    """
    pat = re.compile(rf"^{re.escape(param_prefix)}([0-9_]+A?)$")

    mapping = {}
    for c in columns:
        m = pat.match(c)
        if not m:
            continue
        suffix = m.group(1)

        # Validate it actually follows our station parsing rules
        try:
            parse_station_suffix(suffix)
        except ValueError:
            continue

        mapping[suffix] = c

    return mapping

def _make_x_positions(stations, station_gaps=None):
    """
    stations: list of station strings in the order to plot
    station_gaps:
      - None -> default: [0, 1, 1, 1, ...]
      - list/np.array length N: gap[i] is distance from station i-1 to i (gap[0] ignored / treated as 0)
      - list/np.array length N-1: treated as gaps between consecutive stations, with a leading 0 inserted
    """
    n = len(stations)
    if n == 0:
        return np.array([])

    if station_gaps is None:
        gaps = np.array([0] + [1] * (n - 1), dtype=float)
    else:
        gaps = np.asarray(station_gaps, dtype=float)
        if len(gaps) == n - 1:
            gaps = np.concatenate(([0.0], gaps))
        elif len(gaps) != n:
            raise ValueError(
                f"station_gaps must have length {n} (or {n-1}). Got {len(gaps)}."
            )
        gaps[0] = 0.0

    x = np.cumsum(gaps)
    return x


def plot_station_parameters(
    csv_path: str,
    plot_parameters=("P", "T", "W"),
    units=None,
    scale=None,
    adder=None,
    row_index: int = 0,
    point_time=None,
    mode=None,
    station_gaps=None,
    title=None,
    include_aggregate_A: bool = True,  # plot e.g. 010A as P(A)
):
    """
    Plot up to 3 parameters vs station location (aligned across streams).

    - Multiple lines per parameter: one per stream (and optional aggregate A line).
    - Aligns e.g. 130 and 030 at same x location (= '030').
    - Legend: stream 0 -> 'P', stream n -> 'P(n)', aggregate -> 'P(A)'.

    units: list same length as plot_parameters[:3]
    scale: list same length as plot_parameters[:3], applied multiplicatively to y values
           e.g. Pa->bar: scale=1/100000, units='bar'
    station_gaps: optional spacing between LOCATIONS (not raw station suffixes)
                  length N or N-1 where N = number of unique locations
    """
    df = read_gspy_csv(csv_path, base="script")

    # Limit to max 3 parameters
    params = list(plot_parameters)[:3]

    # Validate / default units
    if units is not None:
        if len(units) != len(params):
            raise ValueError(
                f"'units' must have same length as plot_parameters ({len(params)}). "
                f"Got {len(units)}."
            )
    else:
        units = [None] * len(params)

    # Validate / default adder
    if adder is not None:
        if len(adder) != len(params):
            raise ValueError(
                f"'adder' must have same length as plot_parameters ({len(params)}). "
                f"Got {len(adder)}."
            )
        adder = [float(s) for s in adder]
    else:
        adder = [0.0] * len(params)

    # Validate / default scale
    if scale is not None:
        if len(scale) != len(params):
            raise ValueError(
                f"'scale' must have same length as plot_parameters ({len(params)}). "
                f"Got {len(scale)}."
            )
        scale = [float(s) for s in scale]
    else:
        scale = [1.0] * len(params)

    # ---- Select operating point ----
    if point_time is not None:
        if "Point/Time" not in df.columns:
            raise ValueError("CSV does not contain a 'Point/Time' column.")

        # robust compare: handles 3 vs "3", 3.0 vs "3", etc.
        pt_series = df["Point/Time"].astype(str).str.strip()
        target_pt = str(point_time).strip()
        sel = df[pt_series == target_pt]

        if mode is not None and "Mode" in df.columns:
            mode_series = df["Mode"].astype(str).str.strip()
            target_mode = str(mode).strip()
            sel = sel[mode_series.loc[sel.index] == target_mode]

        if sel.empty:
            raise ValueError(
                f"No rows match point_time={point_time!r}"
                + (f" and mode={mode!r}" if mode is not None else "")
                + "."
            )
        row = sel.iloc[0]
    else:
        if row_index < 0 or row_index >= len(df):
            raise IndexError(f"row_index out of range (0..{len(df)-1}).")
        row = df.iloc[row_index]

    columns = list(df.columns)

    # param_maps[p] : {station_suffix -> column_name}
    param_maps = {p: _find_param_station_columns(columns, p) for p in params}

    # Build a master list of LOCATIONS across all params, and a master set of streams
    locations_set = set()
    streams_set = set()
    aggregates_present = set()  # (p, loc) where A exists (stream implied in suffix rules)

    # For plotting: data[p][stream][loc] = value OR NaN
    data = {p: {} for p in params}

    for p in params:
        mapping = param_maps[p]
        for suffix, col in mapping.items():
            stream, loc, isA = parse_station_suffix(suffix)

            if isA and not include_aggregate_A:
                continue

            locations_set.add(loc)
            streams_set.add(stream)

            # store
            if isA:
                # Use a special stream key for aggregate so it plots as separate line
                stream_key = "A"
                aggregates_present.add((p, loc))
            else:
                stream_key = stream

            data[p].setdefault(stream_key, {})
            data[p][stream_key][loc] = row[col]

    if not locations_set:
        raise ValueError("No station-like columns found for the requested plot_parameters.")

    # Sort locations numerically (this is your x-axis)
    locations = sorted(locations_set, key=station_location_sort_key)

    # X positions based on locations
    x = _make_x_positions(locations, station_gaps=station_gaps)

    # ---- Create axes (one per parameter) ----
    fig, ax1 = plt.subplots(figsize=(12, 5))
    axes = [ax1]

    if len(params) >= 2:
        axes.append(ax1.twinx())

    if len(params) >= 3:
        ax3 = ax1.twinx()
        ax3.spines["right"].set_position(("axes", 1.15))
        axes.append(ax3)

    # Color selection: one base color per parameter axis; vary linestyle per stream
    base_colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    linestyles = ["-", "--", "-.", ":", (0, (3, 1, 1, 1))]  # repeat if many streams

    legend_lines = []
    legend_labels = []

    # Helper for legend formatting
    def series_label(param_name, stream_key):
        if stream_key == "A":
            return f"{param_name}(A)"
        if int(stream_key) == 0:
            return f"{param_name}"
        return f"{param_name}({int(stream_key)})"

    # Plot each parameter axis: multiple lines per stream
    for pi, (ax, p, unit, sc, addr) in enumerate(zip(axes, params, units, scale, adder)):
        base_color = base_colors[pi % len(base_colors)]

        # label the y-axis (parameter + unit)
        if unit:
            ax.set_ylabel(f"{p} {unit}", color=base_color)
        else:
            ax.set_ylabel(p, color=base_color)
        ax.tick_params(axis="y", colors=base_color)

        # decide which "streams" exist for this parameter (including "A")
        stream_keys = list(data[p].keys())

        # Sort stream keys: numeric streams ascending, then "A" last
        def _stream_sort(k):
            if k == "A":
                return (1, 10**9)
            return (0, int(k))
        stream_keys.sort(key=_stream_sort)

        for si, stream_key in enumerate(stream_keys):
            # Build y over all locations, NaN where missing
            y = (np.array([data[p][stream_key].get(loc, np.nan) for loc in locations], dtype=float) + addr) * sc

            # choose linestyle per stream, cycling
            ls = linestyles[si % len(linestyles)]

            line, = ax.plot(
                x, y,
                linewidth=2.0,
                linestyle=ls,
                marker="o",
                color=base_color,
                label=series_label(p, stream_key),
            )

            legend_lines.append(line)
            legend_labels.append(series_label(p, stream_key))

    # X axis shows LOCATION labels (aligned across streams)
    ax1.set_xticks(x)
    ax1.set_xticklabels(locations)
    ax1.set_xlabel("Station location")

    # Title
    if title is None:
        bits = []
        if point_time is not None:
            bits.append(f"Point/Time={point_time}")
        if mode is not None:
            bits.append(f"Mode={mode}")
        title = " | ".join(bits) if bits else "Station plot"
    ax1.set_title(title)

    # Legend (combined, unique labels)
    # Deduplicate while preserving order
    seen = set()
    uniq_lines = []
    uniq_labels = []
    for ln, lb in zip(legend_lines, legend_labels):
        if lb in seen:
            continue
        seen.add(lb)
        uniq_lines.append(ln)
        uniq_labels.append(lb)

    ax1.legend(uniq_lines, uniq_labels, loc="best")

    # Grid / layout
    ax1.grid(True, which="both", axis="both", linestyle="--", alpha=0.35)
    fig.tight_layout()
    plt.show()
    

if __name__ == "__main__":
    # Example usage:
    # - Plot P, T, W for the first row in the file
    plot_station_parameters(
        # csv_path=r"./projects/turbojet/output/turbojet.csv",
        csv_path=r"./projects/turbojet/output/Turbojet_AS210.csv",
        # plot_parameters=("P", "T", "W"),
        plot_parameters=("P", "T"),
        row_index=0,
        # units=["[bar]", "[K]", "[kg/s]"],
        # units=["[bar]", "[°C]", "[kg/s]"],
        units=["[bar]", "[°C]"],
        # adder=[0,-273.15,0],
        adder=[0,-273.15],
        # station_gaps=[0.5, 1, 3, 1, 1, 1, 1],  # default equidistant [1, 1, 1, 1, 1, 1, 1, 1]
        # station_gaps=[1, 1, 1, 1, 1, 1, 1],  # default equidistant [1, 1, 1, 1, 1, 1, 1, 1]
        # scale=[1/100000, 1, 1],
        scale=[1/100000, 1],
        point_time=0,
        mode="DP",
        title="Gas properties"
    )

    # Example with custom station spacing (gaps):
    # stations get spaced by cumulative sum of gaps, where 0 means "same x as previous"
    # plot_station_parameters(
    #     csv_path="turbojet.csv",
    #     plot_parameters=("P", "T", "W"),
    #     row_index=0,
    #     station_gaps=[0, 1, 1, 0, 2, 1, 1, 1],  # length must match number of stations (or be N-1)
    # )