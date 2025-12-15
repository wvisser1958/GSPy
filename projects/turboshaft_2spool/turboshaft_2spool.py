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

from gspy.core import sys_global as fg
from gspy.core import system as fsys
from gspy.core import utils as fu

from gspy.core.control import TControl
from gspy.core.ambient import TAmbient
from gspy.core.shaft import TShaft
from gspy.core.inlet import TInlet
from gspy.core.compressor import TCompressor
from gspy.core.combustor import TCombustor
from gspy.core.turbine import TTurbine
from gspy.core.duct import TDuct
from gspy.core.exhaustdiffuser import TExhaustDiffuser

import os
import matplotlib.pyplot as plt
from pathlib import Path

    # IMPORTANT NOTE TO THIS MODEL FILE
    # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    # note that this model is only to serve as example and does not represent an actual gas turbine design,
    # nor an optimized design. The component maps are just sample maps scaled to the model design point.
    # The maps are entirely unrealistic and therefore result in unrealistic, unstable off design performance,
    # stall margin exceedance etc.
    # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

def main():
    # Paths
    project_dir = Path(__file__).resolve().parent
    map_path = project_dir / "maps"
    fg.output_path = project_dir / "output"

    # create Ambient conditions object (to set ambient/inlet/flight conditions)
    #                               Altitude, Mach, dTs,    Ps0,    Ts0
    # None for Ps0 and Ts0 means values are calculated from standard atmosphere
    fsys.Ambient = TAmbient('Ambient', 0, 0, 0,   0,   None,   None)

    # create a control (controlling inputs to the system model)
    # components like the combustor retrieve inputs like fuel flow
    # input fuel flow or combustor exit temperature

    # create FuelControl for open loop direct control of fuel flow
    FuelControl = TControl('Control', '', 2.5, 2.5, 0.5, -0.1, None)

    inlet1   = TInlet('Inlet1',      '', None,           0,2,   100, 0.9901311    )

    # None = No bleeds
    compressor1 = TCompressor('compressor1',map_path / 'compmap.map' , None, 2, 3, '_gg', 4780, 0.915, 1, 0.8   , 20, 'GG', None)

    # OD fuel input from EGTFuelControl
    combustor1 = TCombustor('combustor1', '',  FuelControl, 3, 4, 2.5, None, 0.95, 0.9998, 458.15,      50025, 4, 0, 'CH4:1', None)
    # combustor1 = TCombustor('combustor1', '',  FuelControl, 3, 4, 2.5, None, 0.95, 0.9998, 298.15,      50025, 4, 0, None, None)

    turbine_gg      =  TTurbine(   'GGT'   ,map_path / 'turbimap.map', None, 4, 45, '_gg', 4780, 0.8 , 1, 0.50943, 0.99, 'GG', None)

    turbine_PT =    TTurbine(   'PT'   ,map_path / 'turbimap.map', None, 45, 5, '_pt', 3000, 0.91 , 1, 0.8, 0.99, 'PT', None)

    duct1    = TDuct('exhduct',      '', None,            5,7,   0.95        )

    exhaust1 = TExhaustDiffuser('exhaust1',  '', None,            7,8,9, 1, 1, 1, 0.95)

    # create a turbojet system model
    fsys.system_model = [fsys.Ambient,
                         FuelControl,
                         inlet1,
                         compressor1,
                         combustor1,
                         turbine_gg,
                         turbine_PT,
                         duct1,
                         exhaust1]

    # define the gas model in f_global
    fg.InitializeGas()
    fsys.ErrorTolerance = 0.001
    fsys.points_output_interval = 1  # only output EGT steps of 10 K (interation steps of EGT 1 K)

    # run the system model Design Point (DP) calculation
    fsys.Mode = 'DP'
    print("Design point (DP) results")
    print("=========================")
    # set DP ambient/flight conditions
    fsys.Ambient.SetConditions('DP', 0, 0, 0, None, None)
    fsys.Run_DP_simulation()

    # OD calculation flag, set 1 for OD, set 0 for DP only
    do_OD = 1

    if do_OD == 1:
        # run the Off-Design (OD) simulation, to find the steady state operating points for all fsys.inputpoints
        fsys.Mode = 'OD'
        fsys.inputpoints = FuelControl.Get_OD_inputpoints()
        print("\nOff-design (OD) results")
        print("=======================")
        # set OD ambient/flight conditions; note that Ambient.SetConditions must be implemented inside RunODsimulation if a sweep of operating/inlet
        # conditions is desired
        fsys.Ambient.SetConditions('OD', 0, 0, 0, None, None)
        # Run OD simulation
        ODpointscalculated = fsys.Run_OD_simulation()

    if do_OD == 1:
        outputbasename = os.path.splitext(os.path.basename(__file__))[0]

        # export OutputTable to CSV
        fsys.OutputToCSV(fg.output_path, outputbasename + ".csv")

        # plot nY vs X parameter
        fsys.Plot_X_nY_graph('Engine performance vs. N_gg [%]',
                                os.path.join(fg.output_path, outputbasename + "_1.jpg"),
                                # common X parameter column name with label
                                ("N_gg%",           "Gas generator speed [%]"),
                                # 4 Y paramaeter column names with labels and color
                                [   ("T45",             "EGT [K]",                  "blue"),
                                    ("W2",              "Inlet mass flow [kg/s]",   "blue"),
                                    ("Wf_combustor1",   "Fuel flow [kg/s]",         "blue"),
                                    ("PW_pt",           "Power output [kW]",        "blue")            ])

        # Create component map plots with operating lines if available
        if ODpointscalculated > 0:
            for comp in fsys.system_model:
                comp.PlotMaps()

    print("end of running turboshaft_2spool cooled turbine simulation")

# main program start, calls main()
if __name__ == "__main__":
    main()
