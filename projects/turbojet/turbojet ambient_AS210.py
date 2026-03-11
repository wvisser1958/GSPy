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

from gspy.core import sys_global as fg
from gspy.core import system as fsys
from gspy.core import utils as fu

from gspy.core.control import TControl
from gspy.core.ambient import TAmbient
from gspy.core.ambient_AS210 import TAmbient_AS210
from gspy.core.shaft import TShaft
from gspy.core.inlet import TInlet
from gspy.core.compressor import TCompressor
from gspy.core.combustor import TCombustor
from gspy.core.turbine import TTurbine
from gspy.core.duct import TDuct
from gspy.core.exhaustnozzle import TExhaustNozzle

import os
import matplotlib.pyplot as plt
from pathlib import Path

    # IMPORTANT NOTE TO THIS MODEL FILE
    # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    # note that this model is only to serve as example and does rougly  represent the GE J85
    # note that low thrust off design performance is unrealistic due to the absence of variable bleed
    # control to maintain low speed stall margin
    # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

def main():

    # Paths
    project_dir = Path(__file__).resolve().parent
    map_path = project_dir / "maps"
    fg.output_path = project_dir / "output"

    # create Ambient conditions object (to set ambient/inlet/flight conditions)
    #                               Altitude, Mach, dTs,    Ps0,    Ts0
    # None for Ps0 and Ts0 means values are calculated from standard atmosphere
    # fsys.Ambient = TAmbient('Ambient', '000', 0, 0,   0,   None,   None)
    fsys.Ambient = TAmbient_AS210('Amb', '000', 0, 0, 0, None, None)

    # create a control (controlling inputs to the system model)
    # components like the combustor retrieve inputs like fuel flow or combustor exit temperature

# Uncomment control creation statement for either fuel flow ("Fcontrol"), N1% ("Ncontrol") or EGT aka T5 ("EGTcontrol"):
    # FuelControl for open loop direct control of fuel flow
    FuelControl = TControl('CtrlF', '', 0.38, 0.38, 0.08, -0.01, None)

    # N1 rotor speed control
    # FuelControl = TControl('Ncontrol', '', 0.38, 100, 60, -5, 'N1%')

    # EGT (T5) control : instable at lower power setting due to multiple solutions at same T5
    # FuelControl = TControl('EGTcontrol', '', 0.38, 1020, 820, -50, 'T5')


    # Generic gas turbine components
    inlet1   = TInlet('In',      '', None,           '000','020',   19.9, 1    )

    compressor1 = TCompressor('Cmp',map_path / 'compmap.map' , None, '020', '030', 1, 16540, 0.825, 1, 0.75   , 6.92, 'GG', None)
    # option for polytropic efficiency, uncomment next line
    # compressor1.Polytropic_Eta = 1

    # OD fuel input from FuelControl
    combustor1 = TCombustor('Brn', '',  FuelControl, '030', '040', 0.38, None, 1, 1, None,      43031, 1.9167, 0, None, None)
    # Texit input
    # TCombustor('combustor1',  '', None,           3, 4, 0.38, 1200, 1, 1,
                # fuel specification examples:
                # fuel specified by LHV, HCratio, OCratio:
                    # None,      43031, 1.9167, 0, ''),

                # fuel specified by Fuel composition (by mass)
                    # NC12H26 = Dodecane ~ jet fuel, CH4 for hydrogen

                # None,      None, None, None, 'NC12H26:1'),
                # fuel specified by Fuel temperature and Fuel composition (by mass)
                    # 288.15,      None, None, None, 'CH4:1'),

                # fuel mixtures
                # fuel specified by Fuel temperature and Fuel composition (by mass)
                #    288.15,      None, None, None, 'CH4:5, C2H6:1')

    turbine1 =    TTurbine('Trb'   , map_path / 'turbimap.map', None, '040', '050', 1, 16540, 0.88 , 1, 0.50943, 0.99, 'GG', None)
    # option for polytropic efficiency, uncomment next line
    # turbine1.Polytropic_Eta = 1

    duct1    = TDuct('DH',      '', None,            '050','070',   1.0        )
    exhaustnozzle = TExhaustNozzle('Noz',  '', None,            '070','080','090', 1, 1, 1)

    # create a turbojet system model
    fsys.system_model = [fsys.Ambient,
                         FuelControl,
                         inlet1,
                         compressor1,
                         combustor1,
                         turbine1,
                         duct1,
                         exhaustnozzle]

    # define the gas model in f_global
    fg.InitializeGas()
    fsys.ErrorTolerance = 0.0001

    # run the system model Design Point (DP) calculation
    fsys.Mode = 'DP'
    print("Design point (DP) results")
    print("=========================")
    # set DP ambient/flight conditions
    Altitude = 0
    Mach = 0
    dTs = 0
    fsys.Ambient.SetConditionsAS210('STANDARD')
    fsys.Ambient.SetConditions('DP', Altitude, Mach, dTs, None, None)
    fsys.Run_DP_simulation()

    # run the Off-Design (OD) simulation, to find the steady state operating points for all fsys.inputpoints
    fsys.Mode = 'OD'
    fsys.inputpoints = FuelControl.Get_OD_inputpoints()
    print("\nOff-design (OD) results")
    print("=======================")
    # set OD ambient/flight conditions; note that Ambient.SetConditions must be implemented inside RunODsimulation if a sweep of operating/inlet
    # conditions is desired
    Altitude = 0
    Mach = 0.5
    dTs = 10
    fsys.Ambient.SetConditionsAS210('HOT')
    fsys.Ambient.SetConditions('OP', Altitude, Mach, dTs, None, None)
    # Run OD simulation
    fsys.Run_OD_simulation()

    outputbasename = os.path.splitext(os.path.basename(__file__))[0]

    # export OutputTable to CSV
    fsys.OutputToCSV(fg.output_path, outputbasename + ".csv")

    # plot nY vs X parameter
    fsys.Plot_X_nY_graph('Engine performance vs. N [%]',
                            os.path.join(fg.output_path, outputbasename + "_1.jpg"),
                            # common X parameter column name with label
                            ("N1%",           "Rotor speed [%]"),
                            # 4 Y paramaeter column names with labels and color
                            [   ("T040",              "TIT [K]",                  "blue"),
                                ("T050",              "EGT [K]",                  "blue"),
                                ("W020",              "Inlet mass flow [kg/s]",   "blue"),
                                ("Wf_Brn",            "Fuel flow [kg/s]",         "blue"),
                                ("FN",                "Net thrust [kN]",          "blue")            ])

     # Create component map plots with operating lines if available
    for comp in fsys.system_model:
        comp.PlotMaps()
        # if comp.map != None:
        #     print(comp.name + " map with operating curve saved in " + comp.map.map_figure_pathname)

    print("end of running turbojet simulation")

# main program start, calls main()
if __name__ == "__main__":
    main()
