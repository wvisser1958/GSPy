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
Demo script for plotting turbine performance maps using MapPlotter.

This example demonstrates:
    • Loading a turbine map file in the standard GSP / GasTurb text-map format
    • Generating unscaled (raw) map visualizations
    • Scaling the map using design-point and off-design data from a GSPy CSV 
      performace output data file
    • Using modern turbine plotting or optionally enabling legacy single-panel
      layout (legacy, simple PR-Wc plot, applies only to PlotMap and never to 
      dual-panel plots)
    • Per-plot selection of:
         - scaled vs. unscaled view
         - DP and OD overlays
         - file/title suffixing
         - single- vs. dual-panel (Eta and PR subplots) plotting

The turbine map file may originate from test-cell performance data,
CFD-derived maps, or Smooth C (GasTurb add-on) output.

This demo showcases practical usage patterns of MapPlotter for turbine
map evaluation and debugging. Update relative paths as needed based on
your directory structure.
"""
# demo_plot_turbine_map.py
from pathlib import Path
from map_plotter import MapPlotter

def main():
    turb_map = Path(r".\..\turbojet\maps\turbimap.map")
    csv_file = Path(r".\..\turbojet\output\turbojet.csv")
    output_dir = Path(r".\output")

    plotter = MapPlotter(
        map_type="turbine",
        map_file=turb_map,
        output_dir=output_dir,
        component_name="turbine1",
        station_in=4,                       # per your request
        name="Turbojet turbine map",
        # Optional map-design location if planning to scale
        # nc_map_des=1.0,        ┐
        # beta_map_des=0.50943,  │─› better to specify this in the function caller below!
        # legacy_map=False,      ┘
    )

    # Simple turbine plots, no scaling, plot data directly unscaled from map file
    # ---------------------------------------------------------------------------
    # "A.x" plots are overwritten, a suffix, e.g. suffix="A.1" is added to generate
    # a customized file name
    # (A.1) Unscaled map (no DP/OD overlays) Legacy map
    plotter.plot(scaled=False, legacy_map=True, map_suffix="_A.1", show=True)
    # (A.2) Unscaled map (no DP/OD overlays) Dual graph map
    # Note that dual=True overrides legacy_map=True
    plotter.plot(scaled=False, legacy_map=True, dual=True, map_suffix="_A.2", show=True)
    # (A.3) Unscaled map (no DP/OD overlays) Nc x Wc - PR
    plotter.plot(scaled=False, legacy_map=False, map_suffix="_A.3", show=True)

    # Plot scaled turbine maps based on CSV file with DP and OD performance data
    # ---------------------------------------------------------------------------
    # (B.1) Scaled to CSV + DP + OD overlays
    plotter.scale_from_csv_and_plot(
        csv_path=csv_file,
        do_plot_design_point=True,
        do_plot_series=True,
        show=True,
        save=True,
        dual=False,         # True -> dual subplot (PR–η and PR–Wc / Nc*Wc depending on your map impl)
        eta_prefix="Eta_is_",
        # Optional overrides for scaling:
        nc_map_des=1.0,
        beta_map_des=0.50943,
        # legacy_map=False,
        map_suffix="_B.1",
    )
    # (B.2) Scaled to CSV + DP + OD overlays, as legacy map
    plotter.scale_from_csv_and_plot(
        csv_path=csv_file,
        do_plot_design_point=True,
        do_plot_series=True,
        show=True,
        save=True,
        dual=False,         # True -> dual subplot (PR–η and PR–Wc / Nc*Wc depending on your map impl)
        eta_prefix="Eta_is_",
        # Optional overrides for scaling:
        nc_map_des=1.0,
        beta_map_des=0.50943,
        legacy_map=True,
        map_suffix="_B.2",
    )
    # (B.3) Scaled to CSV + DP + OD overlays in subplot graphs
    plotter.scale_from_csv_and_plot(
        csv_path=csv_file,
        do_plot_design_point=True,
        do_plot_series=True,
        show=True,
        save=True,
        dual=True,         # True -> dual subplot (PR–η and PR–Wc / Nc*Wc depending on your map impl)
        eta_prefix="Eta_is_",
        # Optional overrides for scaling:
        nc_map_des=1.0,
        beta_map_des=0.50943,
        # legacy_map=False,
        map_suffix="_B.3",
    )

    # Manually scaled turbine map to given design point data
    # ---------------------------------------------------------------------------
    # (C) Scaled to input values
    Nc_des = 7986.428190
    Wc_des = 6.069386
    PR_des = 2.493019
    Eta_des = 0.88
    plotter.scale_from_values_and_plot(
        Nc_des=Nc_des, Wc_des=Wc_des, PR_des=PR_des, Eta_des=Eta_des,
        do_plot_design_point=True,
        do_plot_series=False,
        # od_points=od_points,          # omit or pass [] if you don't want OD
        show=True,
        save=True,
        dual=False,
        eta_prefix="Eta_is_",
        # Optional overrides for the *map-design* location used in scaling:
        nc_map_des=1.0, beta_map_des=0.50943,
        # or infer beta from a map Wc: wc_map_des=8.0,
        map_suffix="_C.1",
    )


if __name__ == "__main__":
    main()
