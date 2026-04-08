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

from gspy.core.AMcontrol import TAMcontrol

    # IMPORTANT NOTE TO THIS MODEL FILE
    # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    # note that this model is only to serve as example and does rougly  represent the GE J85
    # note that low thrust off design performance is unrealistic due to the absence of variable bleed
    # control to maintain low speed stall margin
    # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

def main():
    turbojet = TSystemModel('Turbojet AM',
                            model_file = __file__)

    inlet1   = TInlet(turbojet, 'Inlet1',      '', None,           1,2,   19.9, 1    )
    compressor1 = TCompressor(turbojet, 'compressor1', 'compmap.map' , None, 2, 3, 1, 16540, 0.825, 1, 0.75   , 6.92, 'GG', None)
    # no OD fuel input from FuelControl: constant fuel flow
    combustor1 = TCombustor(turbojet, 'combustor1', '',  None, 3, 4, 0.38, None, 1, 1, None,      43031, 1.9167, 0, '', None)
    turbine1 =    TTurbine(turbojet,    'turbine1'   , 'turbimap.map', None, 4, 5, 1, 16540, 0.88 , 1, 0.50943, 0.99, 'GG', None)
    duct1    = TDuct(turbojet, 'exhduct',      '', None,            5,7,   1.0        )
    exhaustnozzle = TExhaustNozzle(turbojet, 'exhaustnozzle',  '', None,            7,8,9, 1, 1, 1)
    amcontrol = TAMcontrol(turbojet, 'AMcontrol',
                        # input data file
                        "Turbojet_AMinput.csv",
                        (combustor1, "Wf"),
                        ['Alt', 'dTs', 'Macha'],
                        ['T3',
                         'P3',
                         'T5',
                         'N1%'],
                        [
                            (compressor1.map, "SF_eta_deter"),
                            (compressor1.map, "SF_wc_deter"),
                            (turbine1.map, "SF_eta_deter"),
                            (turbine1.map, "SF_wc_deter")
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
    turbojet.inputpoints = amcontrol.Get_OD_inputpoints()
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
                                ("Wf_combustor1",   "Fuel flow [kg/s]",         "blue"),
                                ("FN",              "Net thrust [kN]",          "blue")            ])

    # Create component map plots with operating lines if available
    turbojet.PlotMaps()

    print("end of running AM Adaptive modeling turbojet simulation")

# main program start, calls main()
if __name__ == "__main__":
    main()
