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
#   Wilfried Visser
#   Oscar Kogenhop

import numpy as np
from gspy.core.system import TSystemModel

from gspy.core.control import TControl
from gspy.core.inlet import TInlet
from gspy.core.compressor import TCompressor
from gspy.core.combustor import TCombustor
from gspy.core.turbine import TTurbine
from gspy.core.duct import TDuct
from gspy.core.exhaustnozzle import TExhaustNozzle
from gspy.core.waterinjector import TWaterInjector

# IMPORTANT NOTE TO THIS MODEL FILE
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# note that this model is only to serve as example and does rougly  represent the GE J85
# note that low thrust off design performance is unrealistic due to the absence of variable bleed
# control to maintain low speed stall margin
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

def main():
    turbojet = TSystemModel('Turbojet_wi', model_file = __file__, sys_enable_liquid_water=True)

    fuelcontrol = TControl(system = turbojet,            # owning system model object
                           name='Fcontrol',             # component name
                           DP_input_value=0.38,         # design point (DP) input
                           # off design control input ranging from 0.38 down to 0.8 with steps of -0.01
                           OD_start_value=1235.9, 
                           OD_end_value=None,
                           OD_point_step_value=None, 
                           OD_controlled_parameter_name='T4'                     
                           )
    
    inlet1   = TInlet(system = turbojet,     # owning system model object
                    name = 'Inlet1',        # component name
                    station_in  = 1,        # station nr in
                    station_out = 2,        # station nr out (station strings are also allowed, e.g. '010' and '020')
                    Wdes = 19.9,            # design inlet mass flow
                    PRdes = 1,               # design pressure ratio (PR = 1 - Ploss_relative)
                    enable_liquid_water = True
                    )

    waterinj = TWaterInjector(  system = turbojet,      # owning system model object
                                name = 'waterinj',        # component name
                                station_in  = 2,        # station nr in
                                station_out = 21,       # station nr out (station strings are also allowed, e.g. '010' and '020')
                                PRdes = 1,              # design pressure ratio (PR = 1 - Ploss_relative)  w_water_injection_des = 0.0,
                                percent_water_injection_des = 0.0,
                                T_water_injection_des = 300.0,
                                enable_liquid_water = True
                                )

    compressor1 = TCompressor(system=turbojet,               # owning system model object
                              name='Compressor1',           # component name
                              map_filename='compmap.map' ,  # map file name
                              station_in = 21,              # station nr in and out
                              station_out=3,                
                              shaft_id=1,                   # shaft id, strings are allowed as well (e.g. 'gg'), but for simplicity we use integers here
                              Ndes=16540,                   # design rpm
                              Etades=0.825,                 # design efficiency
                              Ncmapdes=1,                   # map design Nc (for scaling)
                              Betamapdes=0.75,              # map design Beta (for scaling)
                              PRdes=6.92,                   # design pressure ratio
                              SpeedOption='GG',             # speed option
                              Bleeds=None,                  # optional list of bleeds
                              heatpaths = None,
                              enable_liquid_water = True
                              )             # optional list of heat path links with heatsinks

    combustor1 = TCombustor(system=turbojet,                 # owning system model object
                            name='Combustor1',              # component name
                            map_filename = None,            # map file name             # for future use of a combustor efficiency map
                            # OD fuel input from FuelControl
                            control_component = fuelcontrol,# fuel control component    # fuel control component setting fuel flow depending on OD / PointTime point
                            station_in=3, 
                            station_out=4,                  # station nr in and out
                            Wfdes=0.38,                     # Design point (DP) fuel flow Wfdes
                            Texitdes=None,                  # Texit design  - if specified (not None) Wfdes will be calculated from Texit,
                            PRdes=1,                # design pressure ratio, use to specify rel. pressure loss ploss (PR = (1 - ploss)/Pin)
                            Etades=1.0,             # design combustor efficiency
                            Tfueldes=298.15,        # Fuel temperature K           # If None, then Tfuel is assumed to be equal to temperature of entry air flow
                            LHVdes=43031,               # LHV [kJ/kg] at T_standard_ref = 298.15 # (25°C), required if Fuelcomposition is None
                            Cp_fuel_des=2093,           # optional specific heat of the fuel for LVH, H/C and O/C ratio specification, in J/kg-K
                            HCratiodes=1.9167,          # HCratio
                            OCratiodes=0,               # OCratio
                            A=None                      # Cross flow area to calculate fundamental pressue loss
                            )

    turbine1 =    TTurbine(system=turbojet,              # owning system model object
                           name='Turbine1',             # component name
                           map_filename='turbimap.map', # map file name
                           control_component=None,      # optional control component
                           station_in=4, 
                           station_out=5,               # station nr in and out
                           shaft_id=1,                  # shaft nr
                           Ndes=16540,                  # design point (DP) rpm
                           Etades=0.88,                 # design point (DP) efficiency
                           Ncmapdes=1,                  # map design Nc (for scaling)
                           Betamapdes=0.50943,          # map design Beta (for scaling)
                           Etamechdes=0.99,             # design mechanical efficiency (standard isentropic, Polytropic_Eta = 0)
                           TurbineType='GG',            # turbine type 'GG' = gas generator delivering all power required by the shaft
                                                        # 'PT' = free power turbine or turbine driving power output shaft
                           CoolingFlows=None,           # optional cooling flows object list
                           Polytropic_DP_eta=0          # option for working with polytropic efficiency in DP set Polytropic_DP_Eta=1 (OD always isentropic)
                           )
                        
                        
    duct1    = TDuct(system=turbojet,                    # owning system model object
                     name='ExhDuct',                    # component name
                     station_in=5, 
                     station_out=7,                     # station nr in and out
                     PRdes=1.0                          # design pressure ratio, use to specify rel. pressure loss ploss (PR = (1 - ploss)/Pin)
                    )

    exhaustnozzle = TExhaustNozzle(system=turbojet,      # owning system model object
                                   name='ExhaustNozzle',# component name
                                   station_in=7, 
                                   station_throat=8, 
                                   station_out=9,       # station nr of entry, throat and exit  (throat and exit only different fo con-di nozzle)
                                                        # con-di nozzle model still to be implemented
                                   CXdes=1,             # design CX thrust coefficient
                                   CVdes=1,             # design CV velocity coefficient
                                   CDdes=1              # design CD discharge coefficient
                                   )
    
    # create a turbojet system model configuration
    turbojet.define_comp_run_list(  fuelcontrol,
                                    inlet1,
                                    waterinj,
                                    compressor1,
                                    combustor1,
                                    turbine1,
                                    duct1,
                                    exhaustnozzle)

    # turbojet.error_tolerance = 0.0001   # default iteration equation relative residual tolerance, adjust when needed

    # run the system model Design Point (DP) calculation
    turbojet.mode = 'DP'
    print("Design point (DP) results")
    print("=========================")
    # set DP ambient/flight conditions
    turbojet.ambient.SetConditions('DP', 0, 0, 0, None, None, enable_liquid_water = True)
    turbojet.Run_DP_simulation(descr = 'DP ISA SL')

    # run the Off-Design (OD) simulation, to find the steady state operating points for all fsys.inputpoints
    turbojet.mode = 'OD'
    turbojet.input_points = fuelcontrol.get_OD_input_points()
    print("\nOff-design (OD) results")
    print("=======================")
    # set OD ambient/flight conditions; note that Ambient.SetConditions must be implemented inside RunODsimulation if a sweep of operating/inlet
    # conditions is desired

    # effect of water injection at ISA + 30 !, from 0 to mass 2% water injection in steps of 0.5% (0, 0.5, 1.0, 1.5, 2.0)
    turbojet.ambient.SetConditions('OD', 0, 0, 30, None, None)

    for percwater in np.arange(0, 2.1, 0.5): 
        # Run OD simulation
        # turbojet.VERBOSE = False # suppress OD output to terminal
        waterinj.percent_water_injection = percwater
        turbojet.Run_OD_simulation(descr = f"\tSL ISA OD {percwater:.1f}% water injection")
    # export OutputTable to CSV
    turbojet.OutputToCSV()

    # plot nY vs X parameter
    turbojet.Plot_X_nY_graph('Engine performance vs. % Water injection at ISA SL, TIT = 1235.9 K',
                            # suffix for filename to keep multiple plot files apart
                            "_1",
                            # common X parameter column name with label
                            ("Perc_water_waterinj",           "Water injection [%]"),
                            # 4 Y paramaeter column names with labels and color
                            [   ("T21",             "T2 [K]",                   "blue"),
                                ("N1%",             "N1 [%]",                   "blue"),
                                ("T5",              "EGT [K]",                  "blue"),
                                ("W2",              "W2 (air)  [kg/s]",         "blue"),
                                ("Wf_Combustor1",   "Fuel flow [kg/s]",         "blue"),
                                ("FN",              "Net thrust [kN]",          "blue"),
                                ("TSFC",            "TSFC [kg/s/kN]",           "blue")            ])

     # Create component map plots with operating lines if available
    turbojet.PlotMaps()

    print("end of running turbojet simulation")

# main program start, calls main()
if __name__ == "__main__":
    main()
