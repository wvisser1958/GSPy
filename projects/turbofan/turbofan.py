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
    turbofan = TSystemModel('Turbofan', model_file = __file__)

    # create a control (controlling all inputs to the system model)
    # combustor Texit input, with Wf 1.11 as first guess for 1600 K DP combustor exit temperature
    # Note that using a control to specify T4 instead of Wf significantly slows down the simulation
    fuel_control = TControl(turbofan, 'Control', '', 1.11, 1600, 1100, -50, None)

    inlet = TInlet(turbofan,    # owning system model object
                    'Inlet',    # component name
                    '',         # map file name
                    None,       # optional control component
                    1,2,        # station nr in and out
                    337,        # design inlet mass flow
                    1           # design pressure ratio (PR = 1 - Ploss_relative)
                    )

    # for turbofan, note that fan has 2 GasOut outputs
    fan = TFan(turbofan,        # owning system model object
               'Fan_Bst',       # component name
               'bigfanc.map',   # core flow map file name
               2, 25, 21,       # station nr in, core out, bypass (duct side) out
               1,               # shaft nr
               4880,            # design rpm
               0.8696,          # core flow design efficiency
               5.3,             # design bypass ratio BPR
               0.95,            # core map design Nc (for scaling)
               0.7,             # core map design Beta (for scaling)
               2.33,            # core flow design PR

              # bypass flow map data
              'bigfand.map',    # bypass flow map file name
               0.95,            # bypass (duct side) map design Nc (for scaling)
               0.7,             # bypass map design Beta (for scaling)
               1.65,            # bypass flow design PR
               0.8606,          # bypass flow design efficiency

               1                # cross flow control factor (see fan.py code)
               )

    hpc = TCompressor(turbofan,
                                'HPC',    # component name
                                'compmap.map' ,   # map file name
                                None,             # optional control component
                                25, 3,            # station nr in and out
                                2,                # shaft nr
                                14000,            # design rpm
                                0.8433,           # design efficiency
                                1,                # map design Nc (for scaling)
                                0.8,              # map design Beta (for scaling)
                                10.9,             # design pressure ratio
                                'GG',             # speed option
                                None              # option list of bleeds
                                )

    # ***************** Combustor ******************************************************
    # fuel input
    # Texit input, Wf guess for 1500 K is 1.1 kg/s
    combustor = TCombustor(turbofan,
                            'combustor',    # component name
                            '',             # map file name             # for future use of a combustor efficiency map

                            # OD fuel input from FuelControl
                            fuel_control,    # fuel control component    # fuel control component setting fuel flow depending on OD / PointTime point

                            3, 4,           # station nr in and out

                            1.1,            # Design point (DP) fuel flow Wfdes
                            1500,           # Texit design  - if specified (not None) Wfdes will be calculated from Texit,
                                            #               - Wfdes is then taken as starting value for iteration

                            1,              # design pressure ratio, use to specify rel. pressure loss ploss (PR = (1 - ploss)/Pin)
                            1,              # design combustor efficiency
                            None,           # Fuel temperature K           # If None, then Tfuel is assumed to be equal to temperature of entry air flow

                            # For the fuel properties specification there are 2 options:
                            #     1:        virtual fuel with unknown composition:
                            #               specify LHV, H/C ratio, O/C ratio and Tfuel. GSPy will then do the species bookkeeping, determine the exit
                            #               gas composition based in inlet air/gas composition, H/C, O/C
                            #               and calculated the exit temperature from chemical equilibrium
                            #     2:        specify the fuel composition using Cantera composition string like
                            #                   'NC12H26:1' (dodecane),
                            #                   'CH4:9, N2:1' (mixture of CH4 and N2 in ratio 9:1 by mass)
                            #                   or 'CH4:5, C2H6:1' for example, and fuel temperature
                            43031,          # LHV, required if Fuelcomposition is None
                            1.9167,         # HCratio
                            0,              # OCratio
                            None,           # Fuelcomposition  alternative: take 'NC12H26:1' for a jet fuel surrogate for example
                            None            # Cross flow area to calculate fundamental pressue loss
                            )

    hpt = TTurbine(turbofan,'HPT',           # component name
                            'turbimap.map',  # map file name
                            None,            # optional control component
                            4, 45,           # station nr in and out
                            2,               # shaft nr
                            14000,           # design point (DP) rpm
                            0.8732,          # design point (DP) efficiency
                            1,               # map design Nc (for scaling)
                            0.65,            # map design Beta (for scaling)
                            1.0,             # design mechanical efficiency (standard isentropic, Polytropic_Eta = 0)
                            'GG',            # turbine type 'GG' = gas generator delivering all power required by the shaft
                                             #              'PT' = free power turbine or turbine driving power output shaft
                            None             # optional cooling flows object list
                            )
                            # option for working with polytropic efficiency: uncomment next line
                            # turbine1.Polytropic_Eta = 1

    lpt = TTurbine(turbofan,'LPT',
                            'turbimap.map',  # map file name
                            None,            # optional control component
                            45, 5,           # station nr in and out
                            1,               # shaft nr
                            4480,            # design point (DP) rpm
                            0.8682,          # design point (DP) efficiency
                            1,               # map design Nc (for scaling)
                            0.7,             # map design Beta (for scaling)
                            1.0,             # design mechanical efficiency (standard isentropic, Polytropic_Eta = 0)
                            'GG',            # turbine type 'GG' = gas generator delivering all power required by the shaft
                                             #              'PT' = free power turbine or turbine driving power output shaft
                            None             # optional cooling flows object list
                            )
                            # option for working with polytropic efficiency: uncomment next line
                            # turbine1.Polytropic_Eta = 1


    hot_duct = TDuct(turbofan,  'Exhduct_hot',      # component name
                                '',                 # optional map file name
                                None,               # optional control component
                                5,7,                # station nr in and out
                                1.0                 # design pressure ratio, use to specify rel. pressure loss ploss (PR = (1 - ploss)/Pin)
                                )

    hot_nozzle= TExhaustNozzle(turbofan,    'HotNozzle', # component name
                                            '',              # option map file name
                                            None,            # optional control component
                                            7,8,9,           # station nr of entry, throat and exit  (throat and exit only different fo con-di nozzle)
                                                             # con-di nozzle model still to be implemented
                                            1,               # design CX thrust coefficient
                                            1,               # design CV velocity coefficient
                                            1                # design CD discharge coefficient
                                            )

    # now add the list with components following the 2nd fan GasOut (i.e. the bypass duct)
    cold_duct = TDuct(turbofan, 'Exhduct_cold',     # component name
                                '',                 # optional map file name
                                None,               # optional control component
                                21,23,              # station nr in and out
                                1.0                 # design pressure ratio, use to specify rel. pressure loss ploss (PR = (1 - ploss)/Pin)
                                )

    cold_nozzle = TExhaustNozzle(turbofan, 'ColdNozzle',
                                            '',              # option map file name
                                            None,            # optional control component
                                            23,18,19,        # station nr of entry, throat and exit  (throat and exit only different fo con-di nozzle)
                                                             # con-di nozzle model still to be implemented
                                            1,               # design CX thrust coefficient
                                            1,               # design CV velocity coefficient
                                            1                # design CD discharge coefficient
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

    # run the Off-Design (OD) simulation, to find the steady state operating points for all fsys.inputpoints
    turbofan.mode = 'OD'
    turbofan.input_points = fuel_control.get_OD_input_points()
    print("\nOff-design (OD) results")
    print("=======================")
    # set OD ambient/flight conditions; note that Ambient.SetConditions must be implemented inside RunODsimulation if a sweep of operating/inlet
    # conditions is desired
    # typical cruise conditions:
    turbofan.ambient.SetConditions('OD', 10000, 0.8, 0, None, None)
    # Run OD simulation
    turbofan.Run_OD_simulation()

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
