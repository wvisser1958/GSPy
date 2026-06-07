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

from gspy.core.system import TSystemModel

from gspy.core.control import TControl
from gspy.core.inlet import TInlet
from gspy.core.compressor import TCompressor
from gspy.core.combustor import TCombustor
from gspy.core.turbine import TTurbine
from gspy.core.duct import TDuct
from gspy.core.exhaustnozzle import TExhaustNozzle

# IMPORTANT NOTE TO THIS MODEL FILE
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# note that this model is only to serve as example and does rougly  represent the GE J85
# note that low thrust off design performance is unrealistic due to the absence of variable bleed
# control to maintain low speed stall margin
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

def main():
    turbojet = TSystemModel('Turbojet HUM_test_21', model_file = __file__)

    # Uncomment control creation statement for either fuel flow ("Fcontrol"), N1% ("Ncontrol") or EGT aka T5 ("EGTcontrol"):
    # FuelControl for open loop direct control of fuel flow
    # fuelcontrol = TControl(turbojet, 'Fcontrol', '', 1.1, 1.1, 0.08, -0.01, None)

    # Uncomment control creation statement for either fuel flow ("Fcontrol"), N1% ("Ncontrol") or EGT aka T5 ("EGTcontrol"):
    # FuelControl for open loop direct control of fuel flow
    # fuelcontrol = TControl(turbojet, 'Fcontrol', '', 1.1, 1.1, 0.08, -0.01, None)
    fuelcontrol = TControl(owner = turbojet,            # owning system model object
                           name='Fcontrol',             # component name
                           DP_input_value=0.38,         # design point (DP) input
                           # off design control input ranging from 0.38 down to 0.8 with steps of -0.01
                           OD_start_value=0.38, 
                           OD_end_value=0.08, 
                           OD_point_step_value=-0.01,   # off design (OD) input: starting value, end value and step value OR alternatively:
                           # 1235.9, 835.9, -25,        # off design (OD) input: starting value, end value and step value OR alternatively:
                           # 0.30, None, None,          # off design (OD) input: single input value

                           OD_controlled_parameter_name=None                     
                            # OD control parameter name: must be an output present in the output table
                            # if None: the component using it directly takes the value
                            # if specified with parameter name, an equation is added forcing the parameter to match the input values
                            # and the component using it makes it's input a free state variable
                            # e.g. specify 'N1' to control rotor speed, with the combustor turning the Wf into a free state variable

                            # example for N1 rotor speed control:
                            # FuelControl = TControl('Ncontrol', '', 0.38, 100, 60, -5, 'N1%')

                            # TIT (T4) control example:
                            # FuelControl = TControl('EGTcontrol', '', 0.38, 1235.9, 835.9, -10, 'T4')
                            # note that for a gas turbine, this method may well become instable at lower power setting due to multiple solutions at same T5

                            # EGT (T5) control example:
                            # FuelControl = TControl('EGTcontrol', '', 0.38, 1020, 820, -50, 'T5')
                            # note that for a gas turbine, this method may well become instable at lower power setting due to multiple solutions at same T5
                           )

    # Generic gas turbine components
    inlet1   = TInlet(owner = turbojet,     # owning system model object
                    name = 'Inlet1',        # component name
                    station_in  = 1,        # station nr in
                    station_out = 2,        # station nr out (station strings are also allowed, e.g. '010' and '020')
                    Wdes = 19.9,            # design inlet mass flow
                    PRdes = 1,              # design pressure ratio (PR = 1 - Ploss_relative)
                    gas_out_output_species = ["CO2", "H2O", "O2", "H2O_LIQ"] )

    compressor1 = TCompressor(owner=turbojet,               # owning system model object
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
                              heatpaths = None,             # optional list of heat path links with heatsinks
                              gas_out_output_species = ["CO2", "H2O", "O2", "H2O_LIQ"] )

    combustor1 = TCombustor(owner=turbojet,                 # owning system model object
                            name='Combustor1',              # component name
                            map_filename = None,            # map file name             # for future use of a combustor efficiency map
                            # OD fuel input from FuelControl
                            control_component = fuelcontrol,# fuel control component    # fuel control component setting fuel flow depending on OD / PointTime point
                            station_in=3, 
                            station_out=4,                  # station nr in and out
                            Wfdes=0.38,                     # Design point (DP) fuel flow Wfdes
                            Texitdes=None,                  # Texit design  - if specified (not None) Wfdes will be calculated from Texit,
                            # example 1235.9,       # Texit design  - if specified (not None) Wfdes will be calculated from Texit,
                            #               - Wfdes is then taken as starting value for iteration
                            # note that using Texit as imput may be less stable in some cases

                            PRdes=1,                     # design pressure ratio, use to specify rel. pressure loss ploss (PR = (1 - ploss)/Pin)
                            Etades=1,                   # design combustor efficiency
                            Tfueldes=288.15,                # Fuel temperature K           # If None, then Tfuel is assumed to be equal to temperature of entry air flow

                            # For the fuel properties specification there are 2 options:
                            #     1:        virtual fuel with unknown composition:
                            #               specify LHV, H/C ratio, O/C ratio and Tfuel. GSPy will then do the species bookkeeping, determine the exit
                            #               gas composition based in inlet air/gas composition, H/C, O/C
                            #               and calculated the exit temperature from chemical equilibrium
                            #     2:        specify the fuel composition using Cantera composition string like
                            #                   'NC12H26:1' (dodecane),
                            #                   'CH4:9, N2:1' (mixture of CH4 and N2 in ratio 9:1 by mass)
                            #                   or 'CH4:5, C2H6:1' for example, and fuel temperature
                            LHVdes=43031,               # LHV, required if Fuelcomposition is None
                            HCratiodes=1.9167,          # HCratio
                            OCratiodes=0,               # OCratio
                            FuelCompositiondes=None,    # Fuelcomposition  alternative: take 'NC12H26:1' for a jet fuel surrogate for example
                            A=None,                     # Cross flow area to calculate fundamental pressue loss
                            gas_out_output_species = ["CO2", "H2O", "O2", "H2O_LIQ"] )
                            # example with Texit as design input:
                            # TCombustor(turbojet, 'combustor1',  '', None,           3, 4, 0.38, 1200, 1, 1,

                            # fuel specification examples:
                            # fuel specified by LHV, HCratio, OCratio, Tfuel = None means Tfuel equal to combustor entry temperature:
                            # None,      43031, 1.9167, 0, ''),

                            # fuel specified by Fuel composition (by mass)
                            # NC12H26 = Dodecane ~ jet fuel
                            # 300,      None, None, None, 'NC12H26:1'),

                            # fuel specified by Fuel temperature and pure H2 fuel
                            # 288.15,      None, None, None, 'H2:1'),

                            # fuel mixtures
                            # fuel specified by Fuel temperature and fuel mix composition (by mass)
                            #    288.15,      None, None, None, 'CH4:5, C2H6:1')

    turbine1 =    TTurbine(owner=turbojet,              # owning system model object
                           name='Turbine1',             # component name
                           map_filename='turbimap.map', # map file name
                           control_component=None,      # optional control component5
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
    duct1    = TDuct(owner=turbojet,                    # owning system model object
                     name='ExhDuct',                    # component name
                     station_in=5, 
                     station_out=7,                     # station nr in and out
                     PRdes=1.0                          # design pressure ratio, use to specify rel. pressure loss ploss (PR = (1 - ploss)/Pin)
                    )

    exhaustnozzle = TExhaustNozzle(owner=turbojet,      # owning system model object
                                   name='ExhaustNozzle',# component name
                                   station_in=7, 
                                   station_throat=8, 
                                   station_out=9,       # station nr of entry, throat and exit  (throat and exit only different fo con-di nozzle)
                                                        # con-di nozzle model still to be implemented
                                   CXdes=1,             # design CX thrust coefficient
                                   CVdes=1,             # design CV velocity coefficient
                                   CDdes=1              # design CD discharge coefficient
                                   )

    # create a turbojet system model
    turbojet.define_comp_run_list(  fuelcontrol,
                                    inlet1,
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
    turbojet.ambient.SetConditions('DP', 0, 0, 0, None, None, RH=0)
    turbojet.Run_DP_simulation(descr = 'Dry Air')

    turbojet.ambient.SetConditions('DP', 0, 0, 0, None, None, RH=100)
    turbojet.Run_DP_simulation(descr = 'RH=100')

    turbojet.ambient.SetConditions('DP', 0, 0, 0, None, None, RH=200)
    turbojet.Run_DP_simulation(descr = 'RH=200')

    run_OD = False

    if run_OD:
        # run the Off-Design (OD) simulation, to find the steady state operating points for all fsys.inputpoints
        turbojet.mode = 'OD'
        turbojet.input_points = fuelcontrol.get_OD_input_points()
        print("\nOff-design (OD) results")
        print("=======================")
        # set OD ambient/flight conditions; note that Ambient.SetConditions must be implemented inside RunODsimulation if a sweep of operating/inlet
        # conditions is desired
        turbojet.ambient.SetConditions('OD', 0, 0, 0, None, None, RH=100)
        # Run OD simulation
        # turbojet.VERBOSE = False # suppress OD output to terminal
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

    print("end of running turbojet simulation")

# main program start, calls main()
if __name__ == "__main__":
    main()
