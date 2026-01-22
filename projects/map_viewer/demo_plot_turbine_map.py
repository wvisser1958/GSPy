
# demo_plot_turbine_scaled.py
from pathlib import Path
from map_plotter import MapPlotter

def main():
    turb_map = Path(r"C:\Users\oscar.kogenhop\OneDrive - EPCOR B.V\Documents\Projects\VSCode\GSPy\projects\turbojet\maps\turbimap.map")
    csv_file = Path(r"C:\Users\oscar.kogenhop\OneDrive - EPCOR B.V\Documents\Projects\VSCode\GSPy\projects\turbojet\output\turbojet.csv")
    output_dir = Path(r"C:\Users\oscar.kogenhop\OneDrive - EPCOR B.V\Documents\Projects\VSCode\GSPy\projects\map_viewer\output")

    plotter = MapPlotter(
        map_type="turbine",
        map_file=turb_map,
        output_dir=output_dir,
        component_name="turbine1",
        station_in=4,                       # per your request
        name="Turbojet turbine map",
        # Optional map-design location if planning to scale
        # nc_map_des=1.0,
        # beta_map_des=0.50943,
        legacy_map=False,
    )

    # (A.1) Unscaled map (no DP/OD overlays) Legacy map
    plotter.plot(scaled=False, legacy_map=True, show=True)
    # (A.2) Unscaled map (no DP/OD overlays) Dual graph map
    plotter.plot(scaled=False, legacy_map=True, dual=True, show=True)
    # (A.3) Unscaled map (no DP/OD overlays) Nc x Wc - PR
    plotter.plot(scaled=False, legacy_map=False, show=True)

    # (B) Scaled to CSV + DP + OD overlays
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
    )

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
    )


if __name__ == "__main__":
    main()
