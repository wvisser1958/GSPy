# demo_plot_compressor_scaled.py
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
        # nc_map_des=1.0,
        # beta_map_des=0.75,
         # map_suffix="_A",
   )

    # (A.1) Unscaled map (no DP/OD overlays)
    plotter.plot(scaled=False, show=True)
    # (A.2) Unscaled map (no DP/OD overlays) Dual subplot graph map
    plotter.plot(scaled=False, dual=True, show=True)

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
        # map_suffix="_B",
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
        # map_suffix="_B",
    )

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
        # map_suffix="_C",
    )

if __name__ == "__main__":
    main()
