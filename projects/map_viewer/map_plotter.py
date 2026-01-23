# map_plotter.py
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

"""
This module provides a high‑level wrapper around turbomachinery map classes
used in gas turbine performance simulation tools such as GSP, GSPy and GasTurb.

It enables convenient loading, scaling, visualization and comparison of
compressor and turbine performance maps stored in the standard text formats
commonly used in industry and research. These map files may originate from
measurement data, test cell campaigns, or CFD‑derived maps generated with
Smooth C (a GasTurb add‑on tool).

The MapPlotter class adds:
    • Robust path handling for absolute and relative file locations
    • Reading and plotting of compressor and turbine maps (single or dual view)
    • Optional scaling using design-point data from CSV files
    • Optional scaling from manually supplied design-point values
    • Per‑plot selection of single vs. dual map view
    • Optional legacy plotting mode for turbine PR-Wc maps
    • Automatic filename suffixing and figure title formatting
    • Safe DP/OD overlay handling (only when scaled)
    • Isolation of plot settings so they never "leak" between plots

Relevant references:
    • GasTurb: https://www.gasturb.com/
    • Smooth C (GasTurb Add‑On Tool)
    • Dr. Joachim Kurzke – Inventor of GasTurb:
      https://www.kurzke-consulting.de/

This module is intended to simplify the use of turbomachinery maps in 
simulation workflows and help engineers quickly inspect, scale and 
compare component performance characteristics.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import warnings
import numpy as np
import matplotlib.pyplot as plt

# --- Imports with a graceful fallback to local files ---------------------------------
try:
    # If your code is installed as a package
    from gspy.core.compressormap import TCompressorMap
    from gspy.core.turbinemap import TTurbineMap
    from gspy.core import sys_global as fg           # fg.output_path used by base TMap
    import gspy.core.system as fsys                  # fsys.OutputTable used by plots
    _USING_LOCAL_FALLBACK = False
except ImportError:
    # If your .py files live alongside this adapter
    from compressormap import TCompressorMap
    from turbinemap import TTurbineMap

    # Minimal shims
    class _FG: ...
    fg = _FG()
    fg.output_path = Path.cwd() / "output"

    class _FSys: ...
    fsys = _FSys()
    setattr(fsys, "OutputTable", None)

    _USING_LOCAL_FALLBACK = True
# -------------------------------------------------------------------------------------


class MapPlotter:


    """
    High-level interface for reading, scaling, and plotting turbomachinery
    compressor and turbine maps (single- and dual-panel), supporting both
    modern and legacy plotting modes, CSV-driven scaling, and manual
    design-point scaling.

    The class wraps TCompressorMap / TTurbineMap and adds convenient features:
    - automatic path normalization for absolute and relative file locations
    - optional scaling using:
        * design-point values from a CSV file (DP + OD rows)
        * manually supplied design-point parameters (Nc, Wc, PR, Eta)
    - per-plot selection of single vs. dual map views
    - per-plot legacy mode (turbine PlotMap only, never applied to dual views)
    - optional title and filename suffixing for generated figures
    - strict control over overlay behavior:
        * DP/OD overlays only appear when scaled=True
        * overlays are disabled automatically for unscaled plots

    Basic Usage:
        plotter = MapPlotter(
            map_type="compressor" | "turbine",
            map_file="path/to/mapfile.map",
            output_dir="path/to/output",
            component_name="compressor1",
            station_in=2,
            legacy_map=False,            # turbine single-panel legacy off by default
            nc_map_des=1.0,              # optional map-design Nc (for scaling only)
            beta_map_des=0.5,            # optional map-design Beta (for scaling only)
        )

        # Unscaled plot (no DP/OD overlays)
        plotter.plot(scaled=False, show=True)

        # Single-panel scaled plot with DP and OD overlays
        plotter.scale_from_csv_and_plot(
            csv_path="output/turbojet.csv",
            do_plot_design_point=True,
            do_plot_series=True,
            map_suffix="_DP_from_CSV"
        )

        # Manual scaling (no CSV)
        plotter.scale_from_values_and_plot(
            Nc_des=16540,
            Wc_des=19.9,
            PR_des=6.92,
            Eta_des=0.825,
            do_plot_design_point=True,
            do_plot_series=False,
            map_suffix="_manual_DP"
        )

        # Dual-panel plot (always modern, never legacy)
        plotter.plot(scaled=True, dual=True, show=True)

    Key Options:
        scaled (bool):
            If False → plot raw/unscaled map with no overlays.
            If True  → use previously computed scale factors.

        do_plot_design_point (bool):
            Plot the DP yellow square. Only valid when scaled=True.

        do_plot_series (bool):
            Plot OD series from CSV or manually provided series.

        map_suffix (str):
            Optional suffix for file output.
            Title uses spaces, filename uses underscores.

        legacy_map (bool, single-panel turbine only):
            Per-plot legacy turbine view. Restored automatically after each plot.

        dual (bool):
            If True, calls plot_dual() for this call, ignoring legacy_map.

    Notes:
        - CSV mode expects columns named based on component_name and station_in:
            Wc<station nr>, PR_<component name>, Eta_is_<component name>, 
            optionally Nc<station nr>; where <station nr> and <component name> are
            defined in the constructor
        - Path resolution is robust to VS Code's changing working directory.
        - No internal state leaks: legacy mode and suffixes are temporary per-plot.
    """

    # --------------------------------------------------------------------------
    # Path normalization (robust to VS Code CWD)
    # --------------------------------------------------------------------------
    def _normalize_path(self, p: str | Path) -> Path:
        """
        Resolve absolute or relative paths safely:
        - expand '~'
        - absolute: resolve normally
        - relative: resolve relative to the directory containing this file (map_plotter.py)
        """
        p = Path(p).expanduser()
        if p.is_absolute():
            return p.resolve(strict=False)
        base = Path(__file__).parent.resolve()
        return (base / p).resolve(strict=False)

    # --------------------------------------------------------------------------
    # Construction
    # --------------------------------------------------------------------------
    def __init__(
        self,
        map_type: str,
        map_file: str | Path,
        output_dir: str | Path,
        *,
        component_name: str,
        station_in: int,
        name: str | None = None,
        shaft_string: str = "LP",
        nc_map_des: float | None = None,
        beta_map_des: float | None = None,
        ol_xcol: str = "",
        ol_ycol: str = "",
        legacy_map: bool = False
    ) -> None:

        self.map_type = map_type.lower().strip()

        # remember the default legacy preference for turbine PlotMap calls
        self._legacy_default = bool(legacy_map)

        # Normalize map file & output dir first
        self.map_file = self._normalize_path(map_file)
        self.output_dir = self._normalize_path(output_dir)

        # Optional: make the display name fallback to stem if no explicit name given
        self.name = name or self.map_file.stem

        # identity for CSV/param naming
        self.component_name = component_name
        self.station_in = int(station_in)

        # optional map-design coordinates retained for later scaling
        self._user_nc_map_des = None if nc_map_des is None else float(nc_map_des)
        self._user_beta_map_des = None if beta_map_des is None else float(beta_map_des)

        # other options
        self.shaft_string = shaft_string
        self.ol_xcol = ol_xcol
        self.ol_ycol = ol_ycol

        # Validate after normalization
        if not self.map_file.is_file():
            raise FileNotFoundError(f"Map file not found: {self.map_file}")

        # Ensure output directory exists after normalization
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Point your base library to the output folder
        fg.output_path = self.output_dir

        # Host component stub for parameter naming inside your classes
        self.host_component = SimpleNamespace(name=self.component_name, stationin=self.station_in)

        # Provide safe defaults to underlying classes; actual values used only when scaling
        _nc_default = float(self._user_nc_map_des) if self._user_nc_map_des is not None else 1.0
        _beta_default = float(self._user_beta_map_des) if self._user_beta_map_des is not None else 0.5

        # Create the map object
        if self.map_type == "compressor":
            self._map = TCompressorMap(
                host_component=self.host_component,
                name=self.name,
                MapFileName=str(self.map_file),
                OL_xcol=self.ol_xcol,
                OL_Ycol=self.ol_ycol,
                ShaftString=self.shaft_string,
                Ncmapdes=_nc_default,
                Betamapdes=_beta_default,
            )
        elif self.map_type == "turbine":
            self._map = TTurbineMap(
                host_component=self.host_component,
                name=self.name,
                MapFileName=str(self.map_file),
                OL_xcol=self.ol_xcol,
                OL_Ycol=self.ol_ycol,
                ShaftString=self.shaft_string,
                Ncmapdes=_nc_default,
                Betamapdes=_beta_default,
            )
        else:
            raise ValueError("map_type must be 'compressor' or 'turbine'")

        # Parse the map once (builds interpolators & param names)
        self._map.ReadMap(str(self.map_file))

        if _USING_LOCAL_FALLBACK:
            warnings.warn(
                "Using local fallbacks for gspy.* imports. "
                f"fg.output_path -> {fg.output_path}, fsys.OutputTable is None",
                RuntimeWarning,
            )

    # --------------------------------------------------------------------------
    # Helper: temporarily apply a suffix to the map's name (and save path)
    # --------------------------------------------------------------------------
    @contextmanager
    def _temporary_name_suffix(self, map_suffix: str | None):
        """
        Temporarily apply a suffix for this plot call:
        - Figure title uses spaces (underscores → spaces)
        - Saved filename uses underscores (spaces → underscores)
        Restores the original map name and save path afterwards.
        """
        if not map_suffix:
            # No-op
            yield
            return

        # 1) Build display suffix for title (underscores -> spaces)
        display_suffix = map_suffix.replace("_", " ")

        # 2) Build disk-safe suffix for filename (spaces -> underscores)
        disk_suffix = display_suffix.replace(" ", "_")

        original_name = getattr(self._map, "name", None)
        original_path = getattr(self._map, "map_figure_pathname", None)

        # Create a display name for title, and a filename with underscores
        display_name = f"{original_name}{display_suffix}"              # for suptitle
        filename_stem = f"{original_name}{disk_suffix}"                # for save path

        # Apply the display name and the precomputed single-plot path
        self._map.name = display_name
        try:
            # Single plot path; dual plot path may be set by PlotDualMap internally
            self._map.map_figure_pathname = fg.output_path / (filename_stem + ".jpg")
        except Exception:
            pass

        try:
            yield
        finally:
            # Restore originals
            if original_name is not None:
                self._map.name = original_name
            if original_path is not None:
                self._map.map_figure_pathname = original_path

    @contextmanager
    def _temporary_turbine_legacy(self, legacy_flag: bool):
        """
        For turbine PlotMap only: temporarily set legacy flag for this plot call,
        then restore the original flag afterwards.
        """
        if self.map_type != "turbine":
            # Not a turbine: do nothing
            yield
            return

        # Read previous state in a defensive way
        prev = None
        if hasattr(self._map, "LegacyMap"):
            prev = bool(getattr(self._map, "LegacyMap"))
        else:
            # If attribute absent, try method that sets it; we still "restore" with same method.
            prev = None

        # Set requested state
        try:
            if hasattr(self._map, "setLegacyMap"):
                self._map.setLegacyMap(bool(legacy_flag))
            else:
                setattr(self._map, "LegacyMap", bool(legacy_flag))
            yield
        finally:
            # Restore previous state
            if prev is not None:
                if hasattr(self._map, "setLegacyMap"):
                    self._map.setLegacyMap(prev)
                else:
                    setattr(self._map, "LegacyMap", prev)


    # --------------------------------------------------------------------------
    # Helpers: infer Betamapdes from a given (Nc_map_des, Wc_map_des)
    # --------------------------------------------------------------------------
    def _infer_betamapdes_by_wc(self, nc_map_des: float, wc_map_des: float) -> float:
        """
        Given (Nc_map_des, Wc_map_des) on the map, find a Beta where
        Wc(Nc_map_des, Beta) ~= Wc_map_des by nearest match along beta.
        """
        betas = np.asarray(self._map.beta_values, dtype=float)
        Nc_line = np.full_like(betas, fill_value=float(nc_map_des), dtype=float)
        pts = np.column_stack([Nc_line, betas])  # shape (nBeta, 2)

        wc_vals = self._map.get_map_wc(pts)  # RegularGridInterpolator supports array input
        wc_vals = np.asarray(wc_vals, dtype=float)

        idx = int(np.nanargmin(np.abs(wc_vals - float(wc_map_des))))
        beta = float(betas[idx])

        if (wc_map_des < np.nanmin(wc_vals)) or (wc_map_des > np.nanmax(wc_vals)):
            warnings.warn(
                f"Requested wc_map_des={wc_map_des} is outside map Wc range at Nc={nc_map_des}. "
                f"Using nearest Beta={beta:.6f} (Wc={wc_vals[idx]:.6f}).",
                RuntimeWarning,
            )
        return beta

    # --------------------------------------------------------------------------
    # Plotting core (unscaled or using *already-computed* scale factors)
    # --------------------------------------------------------------------------
    def _guard_series_features(self, want_dp: bool, want_series: bool) -> tuple[bool, bool]:
        # disable overlays if no OutputTable present
        if (want_dp or want_series) and getattr(fsys, "OutputTable", None) is None:
            warnings.warn(
                "DP/OD plotting requested but fsys.OutputTable is not available. "
                "Plots will be generated without DP/series overlays.",
                RuntimeWarning,
            )
            return False, False
        return want_dp, want_series

    def plot(
        self,
        *,
        scaled: bool = False,
        do_plot_design_point: bool = False,
        do_plot_series: bool = False,
        show: bool = True,
        save: bool = True,
        eta_name: str = "Eta_is_",    # only used by plot_dual()
        map_suffix: str | None = None,
        legacy_map: bool | None = None,   # turbine PlotMap only, per-call
        dual: bool = False,               # per-call choice: single vs dual
    ) -> None:
        """
        Plot for this call.

        - dual=False (default): single-panel PlotMap.
        * legacy_map is applied **only for turbine** and restored immediately after.
        - dual=True: delegates to plot_dual(...) and **ignores** legacy_map (by design).
        - If scaled=False, DP/OD overlays are disabled (enforced).
        """
        # If caller asked for dual, delegate and return (legacy does not apply to dual)
        if dual:
            self.plot_dual(
                scaled=scaled,
                do_plot_design_point=do_plot_design_point,
                do_plot_series=do_plot_series,
                show=show,
                save=save,
                eta_name=eta_name,
                map_suffix=map_suffix,
            )
            return

        # ---- Single-panel PlotMap flow below ----
        if not scaled:
            # Enforce: no overlays when unscaled
            do_plot_design_point = False
            do_plot_series = False

        dp, series = self._guard_series_features(do_plot_design_point, do_plot_series)

        # Default legacy to False when omitted (per-plot)
        effective_legacy = bool(legacy_map) if legacy_map is not None else False

        with self._temporary_name_suffix(map_suffix), \
            self._temporary_turbine_legacy(effective_legacy):
            self._map.PlotMap(
                use_scaled_map=scaled,
                do_plot_design_point=dp,
                do_plot_series=series,
            )

            if show:
                plt.show()
            if not save:
                pass

    def plot_dual(
        self,
        *,
        scaled: bool = False,
        do_plot_design_point: bool = False,
        do_plot_series: bool = False,
        show: bool = True,
        save: bool = True,
        eta_name: str = "Eta_is_",
        map_suffix: str | None = None,
    ) -> None:
        """
        Plot the dual-subplot figure.
        If map_suffix is provided, it is applied to this call only:
          "<name><suffix>_dual.jpg"
        """
        if not scaled:
            do_plot_design_point = False
            do_plot_series = False

        dp, series = self._guard_series_features(do_plot_design_point, do_plot_series)

        with self._temporary_name_suffix(map_suffix):
            if self.map_type == "compressor":
                self._map.PlotDualMap(
                    eta_name=eta_name,
                    use_scaled_map=scaled,
                    do_plot_design_point=dp,
                    do_plot_series=series,
                )
            else:
                self._map.PlotDualMap(
                    use_scaled_map=scaled,
                    do_plot_design_point=dp,
                    do_plot_series=series,
                )

            if show:
                plt.show()
            if not save:
                pass

    # --------------------------------------------------------------------------
    # CSV-based scaling + plot (scaled is implicit when overlays are requested)
    # --------------------------------------------------------------------------
    def apply_scaling_from_csv(
        self,
        csv_path: str | Path,
        *,
        eta_prefix: str = "Eta_is_",
        mode_col: str = "Mode",
        # Optional overrides of the *map-design* location used for unscaled lookups:
        nc_map_des: float | None = None,
        beta_map_des: float | None = None,
        wc_map_des: float | None = None,
    ) -> None:
        """
        Load CSV, take the first DP row, set fsys.OutputTable,
        and compute scale factors via ReadMapAndGetScaling().

        You can override (nc_map_des, beta_map_des). If only wc_map_des is given,
        we infer beta_map_des at the specified Nc_map_des by nearest Wc.
        """
        import pandas as pd

        # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
        csv_path = self._normalize_path(csv_path)
        # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

        if not csv_path.is_file():
            raise FileNotFoundError(f"CSV not found: {csv_path}")

        df = pd.read_csv(csv_path)
        if mode_col not in df.columns:
            raise KeyError(f"CSV missing '{mode_col}' column.")

        # Expose the full table for DP/OD overlays
        fsys.OutputTable = df

        dp_rows = df[df[mode_col] == "DP"]
        if dp_rows.empty:
            raise ValueError("No DP row (Mode == 'DP') found in CSV.")
        dp = dp_rows.iloc[0]

        wc_col  = f"Wc{self.station_in}"
        pr_col  = f"PR_{self.component_name}"
        eta_col = f"{eta_prefix}{self.component_name}"
        nc_col  = f"Nc{self.station_in}"

        missing = [c for c in (wc_col, pr_col, eta_col) if c not in df.columns]
        if missing:
            raise KeyError(f"CSV missing required columns: {', '.join(missing)}")

        # Actual design (from CSV)
        Wcdes  = float(dp[wc_col])
        PRdes  = float(dp[pr_col])
        Etades = float(dp[eta_col])
        Ncdes  = float(dp[nc_col]) if nc_col in df.columns else float(self._user_nc_map_des or 1.0)

        # Determine the map-design location to use for *unscaled* lookups
        Nc_map = float(nc_map_des if nc_map_des is not None else (self._user_nc_map_des if self._user_nc_map_des is not None else 1.0))
        Beta_map: float | None = float(beta_map_des) if beta_map_des is not None else (
            float(self._user_beta_map_des) if self._user_beta_map_des is not None else None
        )
        if (wc_map_des is not None) and (Beta_map is None):
            Beta_map = self._infer_betamapdes_by_wc(Nc_map, float(wc_map_des))
        if Beta_map is None:
            Beta_map = 0.5

        # Apply chosen map-design point before scaling
        self._map.Ncmapdes = Nc_map
        self._map.Betamapdes = Beta_map

        # Compute and assign scale factors via your map API
        self._map.ReadMapAndGetScaling(Ncdes, Wcdes, PRdes, Etades)

    def scale_from_csv_and_plot(
        self,
        csv_path: str | Path,
        *,
        # plotting controls (scaled is implicit when DP/OD overlays are requested)
        do_plot_design_point: bool = True,
        do_plot_series: bool = True,
        show: bool = True,
        save: bool = True,
        dual: bool = False,
        # CSV & naming controls
        eta_prefix: str = "Eta_is_",
        mode_col: str = "Mode",
        # Optional overrides for the map-design location used in scaling
        nc_map_des: float | None = None,
        beta_map_des: float | None = None,
        wc_map_des: float | None = None,
        # NEW: optional suffix for saved filename(s)
        map_suffix: str | None = None,   # default applied below: "_DP_from_CSV"
        legacy_map: bool | None = None,
    ) -> None:
        """
        One-shot: read CSV, compute scale factors, then plot (scaled).
        Because you requested overlays by calling this method, we always scale first.
        If map_suffix is provided (or defaulted), it is applied only for this call:
          single: "<name><suffix>.jpg"
          dual:   "<name><suffix>_dual.jpg"
        """
        # Default suffix for CSV flow
        if map_suffix is None:
            map_suffix = "_DP_from_CSV"

        self.apply_scaling_from_csv(
            csv_path=csv_path,
            eta_prefix=eta_prefix,
            mode_col=mode_col,
            nc_map_des=nc_map_des,
            beta_map_des=beta_map_des,
            wc_map_des=wc_map_des,
        )

        if dual:
            # Legacy must NOT apply to PlotDualMap
            self.plot_dual(
                scaled=True,
                do_plot_design_point=do_plot_design_point,
                do_plot_series=do_plot_series,
                show=show,
                save=save,
                eta_name=eta_prefix,
                map_suffix=map_suffix,
            )
        else:
            # Legacy applies ONLY to PlotMap
            self.plot(
                scaled=True,
                do_plot_design_point=do_plot_design_point,
                do_plot_series=do_plot_series,
                show=show,
                save=save,
                map_suffix=map_suffix,
                legacy_map=legacy_map,
            )

    # --------------------------------------------------------------------------
    # Value-based scaling (no CSV) + plot
    # --------------------------------------------------------------------------
    def apply_scaling_from_values(
        self,
        *,
        Nc_des: float,
        Wc_des: float,
        PR_des: float,
        Eta_des: float,
        # Optional overrides of the *map-design* point for unscaled lookups
        nc_map_des: float | None = None,
        beta_map_des: float | None = None,
        wc_map_des: float | None = None,
    ) -> None:
        """
        Compute scale factors using explicit design values (no CSV).
        """
        # Decide which map-design location to use for unscaled lookups
        Nc_map = float(nc_map_des if nc_map_des is not None else (self._user_nc_map_des if self._user_nc_map_des is not None else 1.0))
        Beta_map: float | None = float(beta_map_des) if beta_map_des is not None else (
            float(self._user_beta_map_des) if self._user_beta_map_des is not None else None
        )
        if (wc_map_des is not None) and (Beta_map is None):
            Beta_map = self._infer_betamapdes_by_wc(Nc_map, float(wc_map_des))
        if Beta_map is None:
            Beta_map = 0.5

        # Apply chosen map-design point before scaling
        self._map.Ncmapdes = Nc_map
        self._map.Betamapdes = Beta_map

        # Compute and assign scale factors via your map API
        self._map.ReadMapAndGetScaling(float(Nc_des), float(Wc_des), float(PR_des), float(Eta_des))

    def scale_from_values_and_plot(
        self,
        *,
        Nc_des: float,
        Wc_des: float,
        PR_des: float,
        Eta_des: float,
        do_plot_design_point: bool = True,
        do_plot_series: bool = False,
        show: bool = True,
        save: bool = True,
        dual: bool = False,
        eta_prefix: str = "Eta_is_",
        # Optional OD points (list of dicts); if provided and do_plot_series=True we will plot them
        od_points: list[dict] | None = None,
        # Optional overrides for the map-design location used in scaling
        nc_map_des: float | None = None,
        beta_map_des: float | None = None,
        wc_map_des: float | None = None,
        # NEW: optional suffix for saved filename(s)
        map_suffix: str | None = None,   # default applied below: "_manual_DP"
    ) -> None:
        """
        Scale using explicit values (no CSV), optionally overlay a DP yellow square
        and (if provided) a small OD series. The saved filename(s) will include
        the optional suffix for this call only.
        """
        import pandas as pd

        # Default suffix for value-based flow
        if map_suffix is None:
            map_suffix = "_manual_DP"

        # 1) Compute scale factors
        self.apply_scaling_from_values(
            Nc_des=Nc_des, Wc_des=Wc_des, PR_des=PR_des, Eta_des=Eta_des,
            nc_map_des=nc_map_des, beta_map_des=beta_map_des, wc_map_des=wc_map_des,
        )

        # 2) Construct a minimal OutputTable so your plotters can draw DP/OD
        wc_col  = f"Wc{self.station_in}"
        pr_col  = f"PR_{self.component_name}"
        nc_col  = f"Nc{self.station_in}"
        eta_col = f"{eta_prefix}{self.component_name}"

        rows = [{
            "Mode": "DP",
            wc_col: float(Wc_des),
            pr_col: float(PR_des),
            nc_col: float(Nc_des),
            eta_col: float(Eta_des),
        }]

        if do_plot_series and od_points:
            for pt in od_points:
                # Accept flexible keys; map to required columns
                rows.append({
                    "Mode": "OD",
                    wc_col: float(pt.get("Wc", pt.get(wc_col))),
                    pr_col: float(pt.get("PR", pt.get(pr_col))),
                    nc_col: float(pt.get("Nc", pt.get(nc_col, Nc_des))),  # default Nc if not supplied
                    eta_col: float(pt.get("Eta", pt.get(eta_col, Eta_des))),
                })

        fsys.OutputTable = pd.DataFrame(rows)

        # 3) Plot (always scaled here) with a temporary name suffix
        if dual:
            self.plot_dual(
                scaled=True,
                do_plot_design_point=do_plot_design_point,
                do_plot_series=(do_plot_series and od_points is not None),
                show=show,
                save=save,
                eta_name=eta_prefix,
                map_suffix=map_suffix,
            )
        else:
            self.plot(
                scaled=True,
                do_plot_design_point=do_plot_design_point,
                do_plot_series=(do_plot_series and od_points is not None),
                show=show,
                save=save,
                map_suffix=map_suffix,
            )
