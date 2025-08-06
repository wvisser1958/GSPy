# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#    http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
from f_exhaust import TExhaust
import os

def main():
    # create Ambient conditions object (to set ambient/inlet/flight conditions)
    #                              Altitude, Mach, dTs,    Ps0,    Ts0
    # None for Ps0 and Ts0 means values are calculated from standard atmosphere
    fsys.Ambient = TAmbient('Ambient', 0,   0, 0,   0,   None,   None)

    # create a control (controlling all inputs to the system model)
    # direct fuel flow input
    # fsys.Control = TControl('Control', '', 0.48, 0.48, 0.08, -0.01)
    # combustor Texit input, with Wf 0.48 as first guess for 1200 K combustor exit temperature
    FuelControl = TControl('Control', '', 0.30, 1600, 1100, -50, None)
    # fsys.Control = TControl('Control', '', 0.36, 0.31, 0.04, -0.025)

    # create a turbojet system model
    fsys.system_model = [fsys.Ambient,

                         FuelControl,

                         TInlet('Inlet1',          '', None,           0,2,   337, 1    ),

                        # for turbofan, note that fan has 2 GasOut outputs
                        TFan('FAN_BST','bigfanc.map', 2, 25, 21,   1,   4880, 0.8696, 5.3, 0.95, 0.7, 2.33,
                                       'bigfand.map', 0.95, 0.7, 1.65,            0.8606),

                        # always start with the components following the 1st GasOut object
                        TCompressor('HPC','compmap.map', None, 25,3,   2,   14000, 0.8433, 1, 0.8, 10.9, 'GG'),

                        # ***************** Combustor ******************************************************
                        # fuel input
                        # TCombustor('combustor1',  '',            3,4,   0.36, None,    1, 1,
                        # Texit input
                        TCombustor('combustor1',  '',  FuelControl,           3,4,   0.3, 1500,    1, 1,
                                                    # fuel specification examples:
                                                    # fuel specified by LHV, HCratio, OCratio:
                                                    None,      43031, 1.9167, 0, ''),

                                                    # fuel specified by Fuel composition (by mass)
                                                        # NC12H26 = Dodecane ~ jet fuel, CH4 for hydrogen
                                                    # None,      None, None, None, 'NC12H26:1'),
                                                    # fuel specified by Fuel temperature and Fuel composition (by mass)
                                                        # 288.15,      None, None, None, 'CH4:1'),

                                                    # fuel mixtures
                                                    # fuel specified by Fuel temperature and Fuel composition (by mass)
                                                    # 288.15,      None, None, None, 'CH4:5, C2H6:1'),

                        TTurbine('HPT',      'turbimap.map', None, 4,45,   2,   14000, 0.8732,       1, 0.65, 1, 'GG'   ),

                        TTurbine('LPT',      'turbimap.map', None, 45,5,   1,   4480, 0.8682,       1, 0.7, 1, 'GG'   ),


                        TDuct('Exhduct_hot',      '', None,               5,7,   1.0                 ),
                        TExhaust('HotNozzle',     '', None,           7,8,9, 1, 1, 1, 1           ),

                        # now add the list with components following the 2nd fan GasOut (i.e. the bypass duct)
                        TDuct('Exhduct_cold',      '', None,               21,23,   1.0                 ),
                        TExhaust('ColdNozzle',      '', None,           23,18,19, 1, 1, 1, 1           )]

    # define the gas model in f_global
    fg.InitializeGas()

    # run the system model Design Point (DP) calculation
    fsys.Mode = 'DP'
    print("Design point (DP) results")
    print("=========================")
    # set DP ambient/flight conditions
    fsys.Ambient.SetConditions('DP', 0, 0, 0, None, None)
    fsys.Run_DP_simulation()

    # run the Off-Design (OD) simulation, to find the steady state operating points for all fsys.inputpoints
    fsys.Mode = 'OD'
    fsys.inputpoints = FuelControl.Get_OD_inputpoints()
    print("\nOff-design (OD) results")
    print("=======================")
    # set OD ambient/flight conditions; note that Ambient.SetConditions must be implemented inside RunODsimulation if a sweep of operating/inlet
    # conditions is desired
    # typical cruise conditions:
    fsys.Ambient.SetConditions('OD', 10000, 0.8, 0, None, None)
    # Run OD simulation
    fsys.Run_OD_simulation()
    # Export to Excel
    output_directory = 'output'
    os.makedirs(output_directory, exist_ok=True)
    fsys.OutputTable.to_csv(os.path.join(output_directory, 'output.csv'), index=False)

     # Create plots with operating lines if available
    for comp in fsys.system_model:
        comp.PlotMaps()

    print("end of running turbofan simulation")

# main program start, calls main()
if __name__ == "__main__":
    main()
