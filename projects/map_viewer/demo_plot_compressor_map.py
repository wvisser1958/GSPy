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
Demo script for plotting compressor performance maps using MapPlotter.

This example file demonstrates how to:
    • Load a compressor map from a standard text-based component map file
    • Optionally plot the map unscaled (raw map view)
    • Scale the map using design-point and off-design data from a CSV file
    • Apply per-plot options such as:
         - DP and OD overlays
         - title/filename suffixing
         - single plot vs. dual-panel (Eta and PR subplots) plotting

The compressor map file format follows the conventions used in GSP and GasTurb
and may originate from measurement data, CFD-generated maps, or Smooth C
(GasTurb add‑on tool) post-processing.

This demo illustrates typical usage of:
    - MapPlotter.plot(...)
    - MapPlotter.scale_from_csv_and_plot(...)
    - MapPlotter.scale_from_values_and_plot(...)

Adjust file paths and component names as needed for your project layout.
"""
# demo_plot_compressor_map.py
from pathlib import Path
from map_plotter import MapPlotter

def main():
    comp_map = Path(r".\..\turbojet\maps\compmap.map")
    csv_file = Path(r".\..\turbojet\output\turbojet.csv")
    output_dir = Path(r".\output")

    # Provide model identity and (optionally) a map-design location
    plotter = MapPlotter(
        map_type="compressor",
        map_file=comp_map,
        output_dir=output_dir,
        component_name="compressor1",
        station_in=2,
        name="Turbojet compressor map",
        # Optional map-design point if you plan to scale later
        # nc_map_des=1.0,      ┐
        # beta_map_des=0.75,   │─› better to specify this in the function caller below!
        # map_suffix="_A",     ┘
   )

    # Simple compressor plots, no scaling, plot data directly unscaled from map file
    # ------------------------------------------------------------------------------
   # (A.1) Unscaled map (no DP/OD overlays)
    plotter.plot(scaled=False, map_suffix="_A.1", show=True)
    # (A.2) Unscaled map (no DP/OD overlays) Dual subplot graph map
    plotter.plot(scaled=False, dual=True, map_suffix="_A.2", show=True)

    # Plot scaled compressor maps based on CSV file with DP and OD performance data
    # -----------------------------------------------------------------------------
    # (B.1) Scaled to CSV + DP (yellow square) + OD series overlays
    plotter.scale_from_csv_and_plot(
        csv_path=csv_file,
        do_plot_design_point=True,
        do_plot_series=True,
        show=True,
        save=True,
        dual=False,          # set True for the dual-subplot variant
        eta_prefix="Eta_is_",
        # Optionally override the map-design location used during scaling:
        nc_map_des=1.0,
        beta_map_des=0.75,
        # or supply wc_map_des=... to infer Beta at the chosen Nc
        map_suffix="_B.1",
    )
    # (B.2) Scaled to CSV + DP (yellow square) + OD series overlays, dual subplot map graph
    plotter.scale_from_csv_and_plot(
        csv_path=csv_file,
        do_plot_design_point=True,
        do_plot_series=True,
        show=True,
        save=True,
        dual=True,          # set True for the dual-subplot variant
        eta_prefix="Eta_is_",
        # Optionally override the map-design location used during scaling:
        nc_map_des=1.0,
        beta_map_des=0.75,
        # or supply wc_map_des=... to infer Beta at the chosen Nc
        map_suffix="_B.2",
    )

    # Manually scaled compressor map to given design point data
    # ---------------------------------------------------------------------------
    # (C) Scaled to input values
    Nc_des = 16540
    Wc_des = 19.9
    PR_des = 6.92
    Eta_des = 0.825
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
        nc_map_des=1.0, beta_map_des=0.75,
        # or infer beta from a map Wc: wc_map_des=8.0,
        map_suffix="_C",
    )

if __name__ == "__main__":
    main()
