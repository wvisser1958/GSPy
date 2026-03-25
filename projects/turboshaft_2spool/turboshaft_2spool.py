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

from gspy.core.system import TSystemModel

from gspy.core.control import TControl
from gspy.core.inlet import TInlet
from gspy.core.compressor import TCompressor
from gspy.core.combustor import TCombustor
from gspy.core.turbine import TTurbine
from gspy.core.duct import TDuct
from gspy.core.exhaustdiffuser import TExhaustDiffuser

    # IMPORTANT NOTE TO THIS MODEL FILE
    # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    # note that this model is only to serve as example and does not represent an actual gas turbine design,
    # nor an optimized design. The component maps are just sample maps scaled to the model design point.
    # The maps are unrealistic and therefore result in unrealistic, unstable off design performance,
    # stall margin exceedance etc.
    # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

def main():
    turboshaft_2sp = TSystemModel('Turboshaft-2sp')
    # create a control (controlling inputs to the system model)
    # components like the combustor retrieve inputs like fuel flow
    # input fuel flow or combustor exit temperature

    # create FuelControl for open loop direct control of fuel flow
    fuel_control = TControl(turboshaft_2sp, 'Control', '', 2.5, 2.5, 0.5, -0.1, None)

    inlet1   = TInlet(turboshaft_2sp, 'Inlet1',      '', None,           0,2,   100, 0.9901311    )

    # None = No bleeds
    compressor1 = TCompressor(turboshaft_2sp, 'compressor1', turboshaft_2sp.maps_dir_path / 'compmap.map' , None, 2, 3, '_gg', 4780, 0.915, 1, 0.8   , 20, 'GG', None)

    # OD fuel input from EGTFuelControl
    combustor1 = TCombustor(turboshaft_2sp, 'combustor1', '',  fuel_control, 3, 4, 2.5, None, 0.95, 0.9998, 458.15,      50025, 4, 0, 'CH4:1', None)
    # combustor1 = TCombustor('combustor1', '',  FuelControl, 3, 4, 2.5, None, 0.95, 0.9998, 298.15,      50025, 4, 0, None, None)

    turbine_gg      =  TTurbine(turboshaft_2sp,    'GGT'   , turboshaft_2sp.maps_dir_path / 'turbimap.map', None, 4, 45, '_gg', 4780, 0.8 , 1, 0.50943, 0.99, 'GG', None)

    turbine_PT =    TTurbine(turboshaft_2sp,    'PT'   , turboshaft_2sp.maps_dir_path / 'turbimap.map', None, 45, 5, '_pt', 3000, 0.91 , 1, 0.8, 0.99, 'PT', None)

    duct1    = TDuct(turboshaft_2sp, 'exhduct',      '', None,            5,7,   0.95        )

    exhaust1 = TExhaustDiffuser(turboshaft_2sp, 'exhaust1',  '', None,            7,9, 0.95)

    # create a turbojet system model
    turboshaft_2sp.define_comp_run_list(fuel_control,
                                        inlet1,
                                        compressor1,
                                        combustor1,
                                        turbine_gg,
                                        turbine_PT,
                                        duct1,
                                        exhaust1)


    turboshaft_2sp.ErrorTolerance = 0.001

    # run the system model Design Point (DP) calculation
    turboshaft_2sp.mode = 'DP'
    print("Design point (DP) results")
    print("=========================")
    # set DP ambient/flight conditions
    turboshaft_2sp.ambient.SetConditions('DP', 0, 0, 0, None, None)
    turboshaft_2sp.Run_DP_simulation()

    # run the Off-Design (OD) simulation, to find the steady state operating points for all fsys.inputpoints
    turboshaft_2sp.mode = 'OD'
    turboshaft_2sp.inputpoints = fuel_control.Get_OD_inputpoints()
    print("\nOff-design (OD) results")
    print("=======================")
    # set OD ambient/flight conditions; note that Ambient.SetConditions must be implemented inside RunODsimulation if a sweep of operating/inlet
    # conditions is desired
    turboshaft_2sp.ambient.SetConditions('OD', 0, 0, 0, None, None)
    # Run OD simulation
    turboshaft_2sp.Run_OD_simulation()

    turboshaft_2sp.prepare_output_table()

    # export OutputTable to CSV
    turboshaft_2sp.OutputToCSV()

    # plot nY vs X parameter
    turboshaft_2sp.Plot_X_nY_graph('Engine performance vs. Ngg [%]',
                            # suffix for filename to keep multiple plot files apart
                            "_1",
                            # common X parameter column name with label
                            ("N_gg%",           "Rotor speed [%]"),
                            # 4 Y paramaeter column names with labels and color
                            [   ("T4",              "TIT [K]",                  "blue"),
                                ("T5",              "EGT [K]",                  "blue"),
                                ("W2",              "Inlet mass flow [kg/s]",   "blue"),
                                ("Wf_combustor1",   "Fuel flow [kg/s]",         "blue"),
                                ("FN",              "Net thrust [kN]",          "blue")            ])

     # Create component map plots with operating lines if available
    turboshaft_2sp.PlotMaps()
    print("end of running turboshaft_2spool turbine simulation")

# main program start, calls main()
if __name__ == "__main__":
    main()
