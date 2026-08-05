# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#    http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Author: Wilfried Visser 1-11-2025

# from gspy.core import sys_global as fg
from gspy.core.system import TSystemModel

from gspy.core.control import TControl
from gspy.core.inlet import TInlet
from gspy.core.compressor import TCompressor
from gspy.core.combustor import TCombustor
from gspy.core.turbine import TTurbine
from gspy.core.duct import TDuct
from gspy.core.exhaustnozzle import TExhaustNozzle

from gspy.core.AMcontrol import TAMcontrol, AMHealthParameter, AMMeasurement

    # IMPORTANT NOTE TO THIS MODEL FILE
    # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    # note that this model is only to serve as example and does rougly  represent the GE J85
    # note that low thrust off design performance is unrealistic due to the absence of variable bleed
    # control to maintain low speed stall margin
    # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

def main():
    turbojet = TSystemModel('Turbojet AM',
                            model_file = __file__)

    inlet1   = TInlet(system = turbojet,     # owning system model object
                    name = 'Inlet1',        # component name
                    station_in  = 1,        # station nr in
                    station_out = 2,        # station nr out (station strings are also allowed, e.g. '010' and '020')
                    Wdes = 19.9,            # design inlet mass flow
                    PRdes = 1               # design pressure ratio (PR = 1 - Ploss_relative)
                    )

    compressor1 = TCompressor(system=turbojet,               # owning system model object
                              name='Compressor1',           # component name
                              map_filename='compmap.map' ,  # map file name
                              station_in = 2,               # station nr in and out
                              station_out=3,                
                              shaft_id=1,                   # shaft id, strings are allowed as well (e.g. 'gg'), but for simplicity we use integers here
                              Ndes=16540,                   # design rpm
                              Etades=0.825,                 # design efficiency
                              Ncmapdes=1,                   # map design Nc (for scaling)
                              Betamapdes=0.75,              # map design Beta (for scaling)
                              PRdes=6.92,                   # design pressure ratio
                              SpeedOption='GG',             # speed option
                              Bleeds=None,                  # optional list of bleeds
                              heatpaths = None)             # optional list of heat path links with heatsinks
    # no OD fuel input from FuelControl: constant fuel flow
    combustor1 = TCombustor(system=turbojet,                 # owning system model object
                            name='Combustor1',              # component name
                            map_filename = None,            # map file name             # for future use of a combustor efficiency map
                            # OD fuel input from FuelControl
                            station_in=3, 
                            station_out=4,                  # station nr in and out
                            Wfdes=0.38,                     # Design point (DP) fuel flow Wfdes
                            Texitdes=None,                  # Texit design  - if specified (not None) Wfdes will be calculated from Texit,
                            PRdes=1,                # design pressure ratio, use to specify rel. pressure loss ploss (PR = (1 - ploss)/Pin)
                            Etades=1,               # design combustor efficiency
                            Tfueldes=None,          # Fuel temperature K           # If None, then Tfuel is assumed to be equal to temperature of entry air flow
                            LHVdes=43031,               # LHV, required if Fuelcomposition is None
                            HCratiodes=1.9167,          # HCratio
                            OCratiodes=0,               # OCratio
                            FuelCompositiondes=None,    # Fuelcomposition  alternative: take 'NC12H26:1' for a jet fuel surrogate for example
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
    exhaustnozzle = TExhaustNozzle(system=turbojet,     # owning system model object
                                   name='ExhaustNozzle',# component name
                                   station_in=7, 
                                   station_throat=8, 
                                   station_out=9,       # station nr of entry, throat and exit  (throat and exit only different fo con-di nozzle)
                                                        # con-di nozzle model still to be implemented
                                   CXdes=1,             # design CX thrust coefficient
                                   CVdes=1,             # design CV velocity coefficient
                                   CDdes=1              # design CD discharge coefficient
                                   )
    amcontrol = TAMcontrol( system = turbojet, 
                            name = 'AMcontrol',                        
                            measdatafilename = "Turbojet_AMinput.csv",  # input data file
                            powersetting_comp_par = (combustor1, "Wf"),
                            ambient_parameters = ['Alt', 'dTs', 'Macha'],
                            measurement_parameters =  [
                                            AMMeasurement("T5", 1.0),
                                            AMMeasurement("P3", 1.0),
                                            AMMeasurement("T3", 1.0),
                                            AMMeasurement("N1%", 1.0),
                                        ],
                            health_parameters=[
                                            AMHealthParameter(compressor1.map, "SF_eta_deter", 1.0),
                                            AMHealthParameter(compressor1.map, "SF_wc_deter", 1.0),
                                            AMHealthParameter(turbine1.map, "SF_eta_deter", 1.0),
                                            AMHealthParameter(turbine1.map, "SF_wc_deter", 1.0),
                                        ])

    # create a turbojet system model
    turbojet.define_comp_run_list(  amcontrol,
                                    inlet1,
                                    compressor1,
                                    combustor1,
                                    turbine1,
                                    duct1,
                                    exhaustnozzle)

    turbojet.error_tolerance = 0.0001

    # run the system model Design Point (DP) calculation
    turbojet.mode = 'DP'
    print("Design point (DP) results")
    print("=========================")
    # set DP ambient/flight conditions
    turbojet.ambient.SetConditions('DP', 0, 0, 0, None, None)
    turbojet.Run_DP_simulation()

    # run the Off-Design (OD) simulation, to find the steady state operating points for all fsys.inputpoints
    turbojet.mode = 'OD'
    turbojet.input_points = amcontrol.Get_OD_inputpoints()
    print("\nOff-design (OD) results")
    print("=======================")
    # set OD ambient/flight conditions; note that Ambient.SetConditions must be implemented inside RunODsimulation if a sweep of operating/inlet
    # conditions is desired
    turbojet.ambient.SetConditions('OD', 0, 0, 0, None, None)
    # Run OD simulation
    turbojet.Run_OD_simulation()

    # export OutputTable to CSV
    turbojet.OutputToCSV()

    # plot nY vs X parameter
    turbojet.Plot_X_nY_graph('Engine performance vs. N [%]',
                            # suffix for filename to keep multiple plot files apart
                            "_1",
                            # common X parameter column name with label
                            ("N1%",           "Rotor speed [%]"),
                            # 4 Y paramaeter column names with labels and color
                            [   ("T4",              "TIT [K]",                  "blue"),
                                ("T5",              "EGT [K]",                  "blue"),
                                ("W2",              "Inlet mass flow [kg/s]",   "blue"),
                                ("Wf_Combustor1",   "Fuel flow [kg/s]",         "blue"),
                                ("FN",              "Net thrust [kN]",          "blue")            ])

    # Create component map plots with operating lines if available
    turbojet.PlotMaps()

    print("end of running AM Adaptive modeling turbojet simulation")

# main program start, calls main()
if __name__ == "__main__":
    main()
