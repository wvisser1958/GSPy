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
import cantera as ct

# import matplotlib as mpl
import pandas as pd

import f_global as fg
import f_system as fsys
import f_utils as fu

from f_control import TControl
from f_ambient import TAmbient

from f_shaft import TShaft

from f_inlet import TInlet
from f_compressor import TCompressor
from f_fan import TFan
from f_combustor import TCombustor
from f_turbine import TTurbine
from f_duct import TDuct
from f_exhaustnozzle import TExhaustNozzle
import os

def main():
    # create Ambient conditions object (to set ambient/inlet/flight conditions)
    #                              Altitude, Mach, dTs,    Ps0,    Ts0
    # None for Ps0 and Ts0 means values are calculated from standard atmosphere
    fsys.Ambient = TAmbient('Ambient', 0,   0, 0,   0,   None,   None)

    # create a control (controlling all inputs to the system model)
    # direct fuel flow input
    N1_control = TControl('N1_control', '', 1.11, 100, 40, -5, 'N1%')

    # create a turbojet system model
    fsys.system_model = [fsys.Ambient,

                         N1_control,

                         TInlet('Inlet1',          '', None,           0,2,   337, 1    ),

                        # for turbofan, note that fan has 2 GasOut outputs
                        TFan('FAN_BST','bigfanc.map', 2, 25, 21,   1,   4880, 0.8696, 5.3, 0.95, 0.7, 2.33,
                                       'bigfand.map', 0.95, 0.7, 1.65,            0.8606),

                        # always start with the components following the 1st GasOut object
                        TCompressor('HPC','compmap.map', None, 25,3,   2,   14000, 0.8433, 1, 0.8, 10.9, 'GG', None),

                        # ***************** Combustor ******************************************************
                        # fuel input
                        # TCombustor('combustor1',  '',            3,4,   0.36, None,    1, 1,
                        # Wf_des = 1.11 kg/s
                        TCombustor('combustor1',  '',  N1_control,           3,4,   1.11, None,    1, 1,
                                                    # fuel specification examples:
                                                    # fuel specified by LHV, HCratio, OCratio:
                                                    None,      43031, 1.9167, 0, '', None),

                                                    # fuel specified by Fuel composition (by mass)
                                                        # NC12H26 = Dodecane ~ jet fuel, CH4 for hydrogen
                                                    # None,      None, None, None, 'NC12H26:1', None),
                                                    # fuel specified by Fuel temperature and Fuel composition (by mass)
                                                        # 288.15,      None, None, None, 'CH4:1', None),

                                                    # fuel mixtures
                                                    # fuel specified by Fuel temperature and Fuel composition (by mass)
                                                    # 288.15,      None, None, None, 'CH4:5, C2H6:1', None),

                        TTurbine('HPT',      'turbimap.map', None, 4,45,   2,   14000, 0.8732,       1, 0.65, 1, 'GG', None   ),

                        TTurbine('LPT',      'turbimap.map', None, 45,5,   1,   4480, 0.8682,       1, 0.7, 1, 'GG', None   ),


                        TDuct('Exhduct_hot',      '', None,               5,7,   1.0                 ),
                        TExhaustNozzle('HotNozzle',     '', None,           7,8,9, 1, 1, 1),

                        # now add the list with components following the 2nd fan GasOut (i.e. the bypass duct)
                        TDuct('Exhduct_cold',      '', None,               21,23,   1.0                 ),
                        TExhaustNozzle('ColdNozzle',      '', None,           23,18,19, 1, 1, 1)]


    # define the gas model in f_global
    fg.InitializeGas()
    fsys.ErrorTolerance = 0.0001

    # run the system model Design Point (DP) calculation
    fsys.Mode = 'DP'
    print("Design point (DP) results")
    print("=========================")
    # set DP ambient/flight conditions
    fsys.Ambient.SetConditions('DP', 0, 0, 0, None, None)
    fsys.Run_DP_simulation()

    # run the Off-Design (OD) simulation, to find the steady state operating points for all fsys.inputpoints
    fsys.Mode = 'OD'
    fsys.inputpoints = N1_control.Get_OD_inputpoints()
    print("\nOff-design (OD) results")
    print("=======================")
    # set OD ambient/flight conditions; note that Ambient.SetConditions must be implemented inside RunODsimulation if a sweep of operating/inlet
    # conditions is desired
    # typical cruise conditions:
    fsys.Ambient.SetConditions('OD', 0, 0.0, 0, None, None)
    # Run OD simulation
    fsys.Run_OD_simulation()

    #  output results
    outputbasename = os.path.splitext(os.path.basename(__file__))[0]
    # export OutputTable to CSV
    fsys.OutputToCSV('output', outputbasename + ".csv")

    # plot nY vs X parameter
    fsys.Plot_X_nY_graph('Performance vs N1 [%] at ISA SL',
                            os.path.join('output', outputbasename + "_1.jpg"),
                            # common X parameter column name with label
                            ("N1%",           "Fan speed [%]"),
                            # 4 Y paramaeter column names with labels and color
                            [   ("T4",              "TIT [K]",                  "blue"),
                                ("T45",             "EGT [K]",                  "blue"),
                                ("W2",              "Inlet mass flow [kg/s]",   "blue"),
                                ("Wf_combustor1",   "Fuel flow [kg/s]",         "blue"),
                                ("FN",              "Net thrust [kN]",          "blue")            ])

     # Create plots with operating lines if available
    for comp in fsys.system_model:
        comp.PlotMaps()

    print("end of running turbofan N1 control simulation")

# main program start, calls main()
if __name__ == "__main__":
    main()
