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
    turbofan = TSystemModel('Turbofan N1control', model_file = __file__)

    # create a control (controlling all inputs to the system model)
    # combustor Texit input, with Wf 1.11 as first guess for 1600 K DP combustor exit temperature
    N1_control = TControl(turbofan, 'N1_control', '', 1.11, 100, 40, -5, 'N1%')

    inlet = TInlet(turbofan, 'Inlet',          '', None,           1,2,   337, 1    )

    # for turbofan, note that fan has 2 GasOut outputs
    fan = TFan(turbofan, 'Fan_Bst', 'bigfanc.map', 2, 25, 21,   1,   4880, 0.8696, 5.3, 0.95, 0.7, 2.33,
                                    'bigfand.map', 0.95, 0.7, 1.65,            0.8606,
                                    # cf = 1
                                    1)

    # always start with the components following the 1st GasOut object
    hpc = TCompressor(turbofan, 'HPC', 'compmap.map', None, 25,3,   2,   14000, 0.8433, 1, 0.8, 10.9, 'GG', None)

    # ***************** Combustor ******************************************************
    # fuel input
    # Texit input, Wf guess for 1500 K is 1.1 kg/s
    combustor = TCombustor(turbofan, 'Combustor',  '',  N1_control,           3,4,   1.1 , 1500,    1, 1,
                                # fuel specification examples:
                                # fuel specified by LHV, HCratio, OCratio:
                                None,      43031, 1.9167, 0, '', None)

                                # fuel specified by Fuel composition (by mass)
                                    # NC12H26 = Dodecane ~ jet fuel, CH4 for hydrogen
                                # None,      None, None, None, 'NC12H26:1'),
                                # fuel specified by Fuel temperature and Fuel composition (by mass)
                                    # 288.15,      None, None, None, 'CH4:1', None),

                                # fuel mixtures
                                # fuel specified by Fuel temperature and Fuel composition (by mass)
                                # 288.15,      None, None, None, 'CH4:5, C2H6:1', None),

    hpt = TTurbine(turbofan, 'HPT', 'turbimap.map', None, 4,45,   2,   14000, 0.8732,       1, 0.65, 1, 'GG', None)

    lpt = TTurbine(turbofan, 'LPT', 'turbimap.map', None, 45,5,   1,   4480, 0.8682,       1, 0.7, 1, 'GG', None)


    hot_duct = TDuct(turbofan, 'Exhduct_hot',      '', None,               5,7,   1.0                 )
    hot_nozzle= TExhaustNozzle(turbofan, 'HotNozzle',     '', None,           7,8,9, 1, 1, 1)

    # now add the list with components following the 2nd fan GasOut (i.e. the bypass duct)
    cold_duct = TDuct(turbofan, 'Exhduct_cold',      '', None,               21,23,   1.0                 )
    cold_nozzle = TExhaustNozzle(turbofan, 'ColdNozzle',      '', None,           23,18,19, 1, 1, 1)

    # create a turbojet system model
    turbofan.define_comp_run_list(  N1_control,
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

    # # create a turbojet system model
    # fsys.system_model = [fsys.ambient,

    #                     FuelControl,

    #                     TInlet('Inlet1',          '', None,           0,2,   337, 1    ),

    #                     # for turbofan, note that fan has 2 GasOut outputs
    #                     TFan('FAN_BST',map_path / 'bigfanc.map', 2, 25, 21,   1,   4880, 0.8696, 5.3, 0.95, 0.7, 2.33,
    #                                    map_path / 'bigfand.map', 0.95, 0.7, 1.65,            0.8606,
    #                                    # cf = 1
    #                                    1),

    #                     # always start with the components following the 1st GasOut object
    #                     TCompressor('HPC',map_path / 'compmap.map', None, 25,3,   2,   14000, 0.8433, 1, 0.8, 10.9, 'GG', None),

    #                     # ***************** Combustor ******************************************************
    #                     # fuel input
    #                     # Texit input, Wf guess for 1500 K is 1.1 kg/s
    #                     TCombustor('combustor1',  '',  FuelControl,           3,4,   1.1 , 1500,    1, 1,
    #                                                 # fuel specification examples:
    #                                                 # fuel specified by LHV, HCratio, OCratio:
    #                                                 None,      43031, 1.9167, 0, '', None),

    #                                                 # fuel specified by Fuel composition (by mass)
    #                                                     # NC12H26 = Dodecane ~ jet fuel, CH4 for hydrogen
    #                                                 # None,      None, None, None, 'NC12H26:1'),
    #                                                 # fuel specified by Fuel temperature and Fuel composition (by mass)
    #                                                     # 288.15,      None, None, None, 'CH4:1', None),

    #                                                 # fuel mixtures
    #                                                 # fuel specified by Fuel temperature and Fuel composition (by mass)
    #                                                 # 288.15,      None, None, None, 'CH4:5, C2H6:1', None),

    #                     TTurbine('HPT', map_path / 'turbimap.map', None, 4,45,   2,   14000, 0.8732,       1, 0.65, 1, 'GG', None),

    #                     TTurbine('LPT', map_path / 'turbimap.map', None, 45,5,   1,   4480, 0.8682,       1, 0.7, 1, 'GG', None),


    #                     TDuct('Exhduct_hot',      '', None,               5,7,   1.0                 ),
    #                     TExhaustNozzle('HotNozzle',     '', None,           7,8,9, 1, 1, 1),

    #                     # now add the list with components following the 2nd fan GasOut (i.e. the bypass duct)
    #                     TDuct('Exhduct_cold',      '', None,               21,23,   1.0                 ),
    #                     TExhaustNozzle('ColdNozzle',      '', None,           23,18,19, 1, 1, 1)]

    # run the system model Design Point (DP) calculation
    turbofan.mode = 'DP'
    print("Design point (DP) results")
    print("=========================")
    # set DP ambient/flight conditions
    turbofan.ambient.SetConditions('DP', 0, 0, 0, None, None)
    turbofan.Run_DP_simulation()

    # run the Off-Design (OD) simulation, to find the steady state operating points for all fsys.inputpoints
    turbofan.mode = 'OD'
    turbofan.input_points = N1_control.get_OD_input_points()
    print("\nOff-design (OD) results")
    print("=======================")
    # set OD ambient/flight conditions; note that Ambient.SetConditions must be implemented inside RunODsimulation if a sweep of operating/inlet
    # conditions is desired
    # typical cruise conditions:
    turbofan.ambient.SetConditions('OD', 10000, 0.8, 0, None, None)
    # Run OD simulation
    turbofan.Run_OD_simulation()

    turbofan.prepare_output_table()

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
                                ("Wf_Combustor",    "Fuel flow [kg/s]",         "blue"),
                                ("FN",              "Net thrust [kN]",          "blue")            ])

     # Create plots with operating lines if available
    turbofan.PlotMaps()

    print("end of running turbofan simulation")

# main program start, calls main()
if __name__ == "__main__":
    main()
