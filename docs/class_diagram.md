# Class inheritance diagram
===========================
C:\Users\WilfriedVisser\Documents\Python\GSPy\src\gspy\core\base_component.py
└── TComponent  (external base: ABC)
    ├── methods
    │   ├── PreRun()
    │   ├── Run()
    │   ├── PostRun()
    │   ├── PrintPerformance()
    │   ├── PlotMaps()
    │   ├── get_outputs()
    │   └── add_outputs_to_dict()
    └── subclasses
        ├── TAMcontrol
        │   ├── methods
        │   │   ├── Get_OD_inputpoints()
        │   │   ├── Run()
        │   │   ├── PostRun()
        │   │   ├── PrintPerformance()
        │   │   └── get_outputs()
        ├── TDPequations_control
        │   ├── methods
        │   │   ├── Get_DP_inputpoints()
        │   │   ├── Initialize()
        │   │   ├── Run()
        │   │   ├── PostRun()
        │   │   ├── PrintPerformance()
        │   │   └── AddOutputToDict()
        ├── TSFControl
        │   ├── methods
        │   │   ├── Get_OD_inputpoints()
        │   │   ├── Run()
        │   │   ├── PostRun()
        │   │   ├── PrintPerformance()
        │   │   └── AddOutputToDict()
        ├── TAmbient
        │   ├── methods
        │   │   ├── SetConditions()
        │   │   ├── Run()
        │   │   ├── get_outputs()
        │   │   ├── get_station_nr()
        │   │   └── set_station_nr()
        ├── TControl
        │   ├── methods
        │   │   ├── get_OD_input_points()
        │   │   ├── Run()
        │   │   ├── PostRun()
        │   │   └── get_outputs()
        ├── TGaspath
        │   ├── methods
        │   │   ├── Run()
        │   │   ├── PrintPerformance()
        │   │   └── get_outputs()
        │   └── subclasses
        │       ├── TBleedFlow
        │       ├── TCombustor
        │       │   ├── methods
        │       │   │   ├── SetFuel()
        │       │   │   ├── GetLHV()
        │       │   │   ├── fundamental_pressure_loss_rayleigh()
        │       │   │   ├── Run()
        │       │   │   ├── PrintPerformance()
        │       │   │   └── get_outputs()
        │       ├── TCombustor
        │       │   ├── methods
        │       │   │   ├── SetFuel()
        │       │   │   ├── GetLHV()
        │       │   │   ├── fundamental_pressure_loss_rayleigh()
        │       │   │   ├── Run()
        │       │   │   ├── PrintPerformance()
        │       │   │   └── get_outputs()
        │       ├── TCombustor_AE4263
        │       │   ├── methods
        │       │   │   ├── SetFuel()
        │       │   │   ├── GetLHV()
        │       │   │   ├── fundamental_pressure_loss_rayleigh()
        │       │   │   ├── LiquefiedGasFuelQheatup()
        │       │   │   ├── Run()
        │       │   │   ├── PrintPerformance()
        │       │   │   └── get_outputs()
        │       ├── TCoolingFlow
        │       │   ├── methods
        │       │   │   ├── Run()
        │       │   │   ├── PrintPerformance()
        │       │   │   └── get_outputs()
        │       ├── TDuct
        │       │   ├── methods
        │       │   │   └── Run()
        │       ├── TExhaustDiffuser
        │       │   ├── methods
        │       │   │   ├── Run()
        │       │   │   ├── PrintPerformance()
        │       │   │   └── get_outputs()
        │       ├── TExhaustNozzle
        │       │   ├── methods
        │       │   │   ├── Run()
        │       │   │   ├── PrintPerformance()
        │       │   │   └── get_outputs()
        │       ├── TInlet
        │       │   ├── methods
        │       │   │   └── Run()
        │       └── TTurboComponent
        │           ├── methods
        │           │   ├── CreateMap()
        │           │   ├── ReadTurboMapAndSetScaling()
        │           │   ├── GetTurboMapPerformance()
        │           │   ├── PlotMaps()
        │           │   ├── Run()
        │           │   ├── print_map_data()
        │           │   ├── PrintPerformance()
        │           │   └── get_outputs()
        │           └── subclasses
        │               ├── TCompressor
        │               │   ├── methods
        │               │   │   ├── CreateMap()
        │               │   │   ├── Run()
        │               │   │   ├── PrintPerformance()
        │               │   │   └── get_outputs()
        │               ├── TFan
        │               │   ├── methods
        │               │   │   ├── GetSlWcValues()
        │               │   │   ├── GetSlPrValues()
        │               │   │   ├── Run()
        │               │   │   ├── PrintPerformance()
        │               │   │   ├── GetOutputTableColumnNames()
        │               │   │   ├── get_outputs()
        │               │   │   └── PlotMaps()
        │               └── TTurbine
        │                   ├── methods
        │                   │   ├── CreateMap()
        │                   │   ├── GetTotalPRdesUntilAmbient()
        │                   │   ├── Run()
        │                   │   ├── PrintPerformance()
        │                   │   └── get_outputs()
        ├── TShaftComponent  (external base: ABC)
        │   ├── methods
        │   │   ├── get_drive_shaft_power()
        │   │   └── get_outputs()
        │   └── subclasses
        │       ├── TOneShaftComponent  (external base: ABC)
        │       │   ├── methods
        │       │   │   ├── get_power_conversion()
        │       │   │   └── Run()
        │       │   └── subclasses
        │       │       ├── TLoad
        │       │       │   ├── methods
        │       │       │   │   ├── get_outputs()
        │       │       │   │   └── get_drive_shaft_power()
        │       │       └── TMotor
        │       │           ├── methods
        │       │           │   ├── get_outputs()
        │       │           │   └── get_drive_shaft_power()
        │       │           └── subclasses
        │       │               └── TStarterGenerator
        │       │                   ├── methods
        │       │                   │   ├── get_outputs()
        │       │                   │   ├── get_drive_shaft_power()
        │       │                   │   └── get_power_conversion()
        │       └── TTwoShaftComponent  (external base: ABC)
        │           ├── methods
        │           │   └── Run()
        └── TVG_Control
            ├── methods
            │   ├── Get_outputvalue_from_schedule()
            │   ├── Run()
            │   └── AddOutputToDict()

C:\Users\WilfriedVisser\Documents\Python\GSPy\src\gspy\core\map.py
└── TMap
    ├── methods
    │   ├── simresultstable() [property]
    │   ├── ReadMap()
    │   └── PlotMap()
    └── subclasses
        └── TTurboMap
            ├── methods
            │   ├── ReadMap()
            │   ├── ReadNcBetaCrossTable()
            │   ├── ReadMapAndGetScaling()
            │   ├── SetScaling()
            │   ├── DefineInterpolationFunctions()
            │   ├── GetScaledMapPerformance()
            │   ├── set_scaled_arrays()
            │   ├── PlotMap()
            │   └── PlotDualMap()
            └── subclasses
                ├── TCompressorMap
                │   ├── methods
                │   │   ├── GetSlWcValues()
                │   │   ├── GetSlPrValues()
                │   │   ├── ReadMap()
                │   │   ├── PlotMap()
                │   │   └── PlotDualMap()
                └── TTurbineMap
                    ├── methods
                    │   ├── setLegacyMap()
                    │   ├── ReadMap()
                    │   ├── ReadMap()
                    │   ├── PlotMap()
                    │   └── PlotDualMap()

C:\Users\WilfriedVisser\Documents\Python\GSPy\src\gspy\core\shaft.py
└── TShaft

C:\Users\WilfriedVisser\Documents\Python\GSPy\src\gspy\core\system - Copy.py
└── TSystemModel
    ├── methods
    │   ├── get_shaft()
    │   ├── get_comp()
    │   ├── reinit_states_and_errors()
    │   ├── reset_output()
    │   ├── reinit_system()
    │   ├── Do_Run()
    │   ├── define_comp_run_list()
    │   ├── Run_DP_simulation()
    │   ├── Run_OD_simulation()
    │   ├── PrintPerformance()
    │   ├── AddSystemOutputToDict()
    │   ├── Do_Output()
    │   ├── print_states_and_errors()
    │   ├── prepare_output_table()
    │   ├── OutputToCSV()
    │   ├── Plot_X_nY_graph()
    │   └── PlotMaps()

C:\Users\WilfriedVisser\Documents\Python\GSPy\src\gspy\core\system.py
└── TSystemModel
    ├── methods
    │   ├── vprint()
    │   ├── get_error_text()
    │   ├── get_shaft()
    │   ├── get_comp()
    │   ├── get_component_object_by_name()
    │   ├── get_gaspathcomponent_object_inlet_stationnr()
    │   ├── reinit_states_and_errors()
    │   ├── reset_output()
    │   ├── reinit_system()
    │   ├── Do_Run()
    │   ├── define_comp_run_list()
    │   ├── Run_DP_simulation()
    │   ├── print_DP_equation_solution()
    │   ├── Run_OD_simulation()
    │   ├── PrintPerformance()
    │   ├── get_outputs()
    │   ├── Do_Output()
    │   ├── print_states_and_errors()
    │   ├── prepare_output_table()
    │   ├── OutputToCSV()
    │   ├── Plot_X_nY_graph()
    │   └── PlotMaps()