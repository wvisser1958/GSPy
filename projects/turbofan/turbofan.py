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
from gspy.core.fan import TFan
from gspy.core.compressor import TCompressor
from gspy.core.combustor import TCombustor
from gspy.core.turbine import TTurbine
from gspy.core.duct import TDuct
from gspy.core.exhaustnozzle import TExhaustNozzle

# IMPORTANT NOTE TO THIS MODEL FILE
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# note that this model is only to serve as example and does not represent an actual gas turbine design,
# nor an optimized design. The component maps are just sample maps scaled to the model design point.
# The maps are entirely unrealistic and therefore result in unrealistic, unstable off design performance,
# stall margin exceedance etc.
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

def main():
    turbofan = TSystemModel('Turbofan', model_file = __file__,
                            sys_enable_liquid_water=True)

    # create a control (controlling all inputs to the system model)
    # combustor Texit input, with Wf 1.11 as first guess for 1600 K DP combustor exit temperature
    fuel_control = TControl(system=turbofan, 
                           name='Fcontrol', 
                           DP_input_value=1.11,                # design point (DP) input for combustor
                           OD_start_value=1600, 
                           OD_end_value=1100, 
                           OD_point_step_value=-50,             # off design (OD) input: starting value, end value and step value OR alternatively:
                           OD_controlled_parameter_name='T4'  # OD control parameter name: must be an output present in the output table
                                                    # if None: the component using it directly takes the value
                                                    # if specified with parameter name, an equation is added forcing the parameter to match the input values
                                                    # and the component using it makes it's input a free state variable
                                                    # e.g. specify 'N1' to control rotor speed, with the combustor turning the Wf into a free state variable
                                                    # alternative: EGT (T5) control example:
                                                    # FuelControl = TControl('EGTcontrol', '', 0.38, 1020, 820, -50, 'T5')
                                                    # note that for a gas turbine, this method may well become instable at lower power setting due to multiple solutions at same T5
                           )

    inlet = TInlet(system=turbofan,    # owning system model object
                   name='Inlet',    # component name
                   station_in  = 1,        # station nr in
                   station_out = 2,        # station nr out (station strings are also allowed, e.g. '010' and '020')
                   Wdes = 337,            # design inlet mass flow
                   PRdes = 1               # design pressure ratio (PR = 1 - Ploss_relative)                    
                   )

    # for turbofan, note that fan has 2 GasOut outputs
    fan = TFan(system=turbofan,        # owning system model object
               name='Fan_Bst',         # component name
               station_in=2, station_out_core=25, station_out_duct=21,       # station nr in, core out, bypass (duct side) out
               shaft_id=1,             # shaft nr
               Ndes=4880,              # design rpm
               BPRdes=5.3,             # design bypass ratio BPR
               PRdes_core=2.33, 
               Etades_core=0.8696, 
               Ncmapdes_core=0.95, 
               Betamapdes_core=0.7,
               PRdes_duct=1.65, 
               Etades_duct=0.8606, 
               Ncmapdes_duct=0.95, 
               Betamapdes_duct=0.7,
               map_filename='', # set tp '' intentionally, to avoid error message and avoid reading of a map file, because we have 2 maps for the fan, one for core and one for duct    
               map_filename_core='bigfanc.map',    
               map_filename_duct='bigfand.map',    
               cf=1                                # cross flow control factor (see fan.py code)
               )

    hpc = TCompressor(system=turbofan,               # owning system model object
                              name='HPC',           # component name
                              map_filename='compmap.map' ,  # map file name
                              station_in = 25,               # station nr in and out
                              station_out=3,                
                              shaft_id=2,                   # shaft id, strings are allowed as well (e.g. 'gg'), but for simplicity we use integers here
                              Ndes=14000,                   # design rpm
                              Etades=0.8433,                # design efficiency
                              Ncmapdes=1,                   # map design Nc (for scaling)
                              Betamapdes=0.8,               # map design Beta (for scaling)
                              PRdes=10.9,                   # design pressure ratio
                              SpeedOption='GG',             # speed option
       )

    # ***************** Combustor ******************************************************
    # fuel input
    # Texit input, Wf guess for 1500 K is 1.1 kg/s
    combustor = TCombustor(system=turbofan,                 # owning system model object
                            name='combustor',               # component name
                            control_component = fuel_control,# fuel control component    # fuel control component setting fuel flow depending on OD / PointTime point
                            station_in=3, 
                            station_out=4,                  # station nr in and out
                            Wfdes=1.1,                      # Design point (DP) fuel flow Wfdes
                            Texitdes=1500,                  # Texit design  - if specified (not None) Wfdes will be calculated from Texit,
                                                            # - Wfdes is then taken as starting value for iteration

                            PRdes=1,                # design pressure ratio, use to specify rel. pressure loss ploss (PR = (1 - ploss)/Pin)
                            Etades=1,               # design combustor efficiency
                            Tfueldes=None,          # Fuel temperature K           # If None, then Tfuel is assumed to be equal to temperature of entry air flow
                            LHVdes=43031,               # LHV, required if Fuelcomposition is None
                            HCratiodes=1.9167,          # HCratio
                            OCratiodes=0,               # OCratio
                            )

    hpt =    TTurbine(system=turbofan,              # owning system model object
                           name='HPT',                  # component name
                           map_filename='turbimap.map', # map file name
                           station_in=4, 
                           station_out=45,              # station nr in and out
                           shaft_id=2,                  # shaft nr
                           Ndes=14000,                  # design point (DP) rpm
                           Etades=0.8732,               # design point (DP) efficiency
                           Ncmapdes=1,                  # map design Nc (for scaling)
                           Betamapdes=0.65,             # map design Beta (for scaling)
                           Etamechdes=1.0,              # design mechanical efficiency (standard isentropic, Polytropic_Eta = 0)
                           TurbineType='GG',            # turbine type 'GG' = gas generator delivering all power required by the shaft
                                                        # 'PT' = free power turbine or turbine driving power output shaft
                           )

    lpt =    TTurbine(system=turbofan,              # owning system model object
                           name='LPT',                  # component name
                           map_filename='turbimap.map', # map file name
                           station_in=45, 
                           station_out=5,               # station nr in and out
                           shaft_id=1,                  # shaft nr
                           Ndes=4480,                   # design point (DP) rpm
                           Etades=0.8682,               # design point (DP) efficiency
                           Ncmapdes=1,                  # map design Nc (for scaling)
                           Betamapdes=0.7,              # map design Beta (for scaling)
                           Etamechdes=1.0,              # design mechanical efficiency (standard isentropic, Polytropic_Eta = 0)
                           TurbineType='GG',            # turbine type 'GG' = gas generator delivering all power required by the shaft
                                                        # 'PT' = free power turbine or turbine driving power output shaft
                           )

    hot_duct = TDuct(system = turbofan,  
                     name = 'Exhduct_hot',      # component name
                     station_in = 5,
                     station_out = 7,
                     PRdes = 1.0                 # design pressure ratio, use to specify rel. pressure loss ploss (PR = (1 - ploss)/Pin)
                                )

    hot_nozzle= TExhaustNozzle(system=turbofan,    
                               name='HotNozzle', # component name
                               station_in=7,
                               station_throat=8,
                               station_out=9,           
                               # con-di nozzle model still to be implemented
                               CXdes=             1,               # design CX thrust coefficient
                               CVdes=             1,               # design CV velocity coefficient
                               CDdes=             1                # design CD discharge coefficient
                               )

    # now add the list with components following the 2nd fan GasOut (i.e. the bypass duct)
    cold_duct = TDuct(system=turbofan, 
                      name='Exhduct_cold',     # component name
                      station_in=21,
                      station_out=23,
                      PRdes=1.0                 # design pressure ratio, use to specify rel. pressure loss ploss (PR = (1 - ploss)/Pin)
                      )

    cold_nozzle = TExhaustNozzle(system=turbofan, 
                                name='ColdNozzle',
                                station_in=23,
                                station_throat=18,
                                station_out=19,
                                CXdes=1,
                                CVdes=1,
                                CDdes=1
                                )
    # create a turbojet system model
    turbofan.define_comp_run_list(  fuel_control,
                                    inlet,
                                    fan,
                                    hpc,
                                    combustor,
                                    hpt,
                                    lpt,
                                    hot_duct,
                                    hot_nozzle,
                                    cold_duct,
                                    cold_nozzle)

    # run the system model Design Point (DP) calculation
    turbofan.mode = 'DP'
    print("Design point (DP) results")
    print("=========================")
    # set DP ambient/flight conditions
    turbofan.ambient.SetConditions('DP', 0, 0, 0, None, None)
    turbofan.Run_DP_simulation()

    Run_OD = True
    if Run_OD:
        # run the Off-Design (OD) simulation, to find the steady state operating points for all fsys.inputpoints
        turbofan.mode = 'OD'
        print("\nOff-design (OD) results")
        print("=======================")

        # # test OD simulation at Design conditions 
        # turbofan.ambient.SetConditions('OD', 0, 0.0, 0, None, None)
        # turbofan.input_points = fuel_control.re_init_input(None,
        #                                                         1.11,
        #                                                         1600, 1200, -50,
        #                                                         'T4')    
        # turbofan.Run_OD_simulation('Test step at 0m / Ma 0.0 Design conditions')

        # # intermediate step at design T4 to help iteration towards point far from DP
        # # set OD ambient/flight conditions; note that Ambient.SetConditions must be implemented inside RunODsimulation if a sweep of operating/inlet
        # # conditions is desired
        # turbofan.ambient.SetConditions('OD', 0, 0.0, 0, None, None)
        # turbofan.input_points = fuel_control.re_init_input(None,
        #                                                         0.7,
        #                                                         None, None, None,
        #                                                         'T4',
        #                                                         point_time_value_array = [combustor.Texitdes])    
        # turbofan.Run_OD_simulation('Intermediate step at 5000m / Ma 0.8')


        # # intermediate step at design T4 to help iteration towards point far from DP
        # # set OD ambient/flight conditions; note that Ambient.SetConditions must be implemented inside RunODsimulation if a sweep of operating/inlet
        # # conditions is desired
        turbofan.ambient.SetConditions('OD', 5000, 0.8, 0, None, None, RH=120)
        turbofan.input_points = fuel_control.re_init_input(None,
                                                                0.7,
                                                                1600, 1200, -50,
                                                                'T4')    
        turbofan.Run_OD_simulation('Intermediate step at 5000m / Ma 0.8')

        # # sweep T4 at typical cruise condition 10k / Ma 0.8:
        # turbofan.ambient.SetConditions('OD', 5000, 0.8, 0, None, None)
        # turbofan.input_points = fuel_control.re_init_input(None,
        #                                                         0.7,
        #                                                         1600, 1100, -50,
        #                                                         'T4')    
        # turbofan.Run_OD_simulation('Performance at 5000m / Ma 0.8')

        # turbofan.ambient.SetConditions('DP', 0, 0, 0, None, None)
        # turbofan.Run_DP_simulation()

        # # # sweep T4 at typical cruise condition 11k / Ma 0.8:
        # turbofan.ambient.SetConditions('OD', 11000, 0.8, 0, None, None)
        # turbofan.input_points = fuel_control.re_init_input(None,
        #                                                         0.5,
        #                                                         1600, 1100, -50,
        #                                                         'T4')    
        # turbofan.Run_OD_simulation('Performance at 11000m / Ma 0.8')

    # export OutputTable to CSV
    turbofan.OutputToCSV()

    # plot nY vs X parameter
    turbofan.Plot_X_nY_graph('Performance vs N1 [%] at Alt 10000m, Ma 0.8 (DP at ISA SL)',
                            "_1",
                            # common X parameter column name with label
                            ("N1%",           "Fan speed [%]"),
                            # 4 Y paramaeter column names with labels and color
                            [   ("T4",              "TIT [K]",                  "blue"),
                                ("T45",             "EGT [K]",                  "blue"),
                                ("W2",              "Inlet mass flow [kg/s]",   "blue"),
                                ("Wf_combustor",    "Fuel flow [kg/s]",         "blue"),
                                ("FN",              "Net thrust [kN]",          "blue")            ])

     # Create plots with operating lines if available
    turbofan.PlotMaps()

    print("end of running turbofan simulation")

# main program start, calls main()
if __name__ == "__main__":
    main()
