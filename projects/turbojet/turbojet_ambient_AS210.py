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
from gspy.extensions.ambient.AS210 import TAmbient_AS210
from gspy.core.inlet import TInlet
from gspy.core.compressor import TCompressor
from gspy.core.combustor import TCombustor
from gspy.core.turbine import TTurbine
from gspy.core.duct import TDuct
from gspy.core.exhaustnozzle import TExhaustNozzle

# IMPORTANT NOTE TO THIS MODEL FILE
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# - Note that this model is only to serve as example and does rougly  represent the GE J85
# - Note that low thrust off design performance is unrealistic due to the absence of variable bleed
#   control to maintain low speed stall margin
# - This demo file is to demonstrate the use of a different Ambient object, one that implements the 
#   SAE AS210 atmospheric models
# - It furthermore uses AS755 standard 3-digit station naming and AS5571 component modle naming
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

def main():
    turbojet = TSystemModel('Turbojet_AS210',
                            model_file = __file__)
    # Override ambient conditions object (to set ambient/inlet/flight conditions)
    # The ambient conditions object is an embedded object inside the system model class,
    # we now have to override the system model ambient
    turbojet.ambient = TAmbient_AS210(
        turbojet, 'Amb', '000',
        alt_in=0.0,
        MN_in=0.0,
        dTs_in=0.0,
        switchDay='STANDARD',
        switchHum='RH',
        switchMode='ALDTMN',
    )
    # No component output to terminal:
    turbojet.VERBOSE = False # If set to True, each simulation step will output data to screen, however, 
                             # False makes the simulation much faster, the output is stored in a csv table.

    # Uncomment control creation statement for either fuel flow ("Fcontrol"), N1% ("Ncontrol") or EGT aka T5 ("EGTcontrol"):
    # fuelcontrol for open loop direct control of fuel flow
    fuelcontrol = TControl(turbojet, 'CtrlF', '', 0.38, 0.38, 0.08, -0.01, None)

    # N1 rotor speed control
    # fuelcontrol = TControl('Ncontrol', '', 0.38, 100, 60, -5, 'N1%')

    # EGT (T5) control : instable at lower power setting due to multiple solutions at same T5
    # fuelcontrol = TControl('EGTcontrol', '', 0.38, 1020, 820, -50, 'T5')

    # Generic gas turbine components
    inlet1   = TInlet(turbojet, 'In', '', None, '000','020', 19.9, 1    )

    compressor1 = TCompressor(turbojet, 'Cmp', turbojet.maps_dir_path / 'compmap.map' , None, '020', '030', 1, 16540, 0.825, 1, 0.75   , 6.92, 'GG', None)
    # option for polytropic efficiency, uncomment next line
    # compressor1.Polytropic_Eta = 1

    # OD fuel input from fuelcontrol
    combustor1 = TCombustor(turbojet, 'Brn', '',  fuelcontrol, '030', '040', 0.38, None, 1, 1, None,      43031, 1.9167, 0, None, None)
    # Texit input
    # TCombustor('combustor1', '', None, 3, 4, 0.38, 1200, 1, 1,
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

    turbine1 =    TTurbine(turbojet, 'Trb', turbojet.maps_dir_path / 'turbimap.map', None, '040', '050', 1, 16540, 0.88 , 1, 0.50943, 0.99, 'GG', None)
    # option for polytropic efficiency, uncomment next line
    # turbine1.Polytropic_Eta = 1

    duct1    = TDuct(turbojet, 'DH', '', None, '050','070', 1.0)
    exhaustnozzle = TExhaustNozzle(turbojet, 'Noz', '', None, '070','080','090', 1, 1, 1)

    # create a turbojet system model
    turbojet.define_comp_run_list(  fuelcontrol,
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
    Altitude_val = 0
    Mach_val = 0
    dTs_val = 0
    # turbojet.ambient.SetConditionsAS210(switchDay='STANDARD', switchHum='RH', switchMode='ALDTMN')
    # turbojet.ambient.SetConditions('DP', alt_in=Altitude_val, MN_in=Mach_val, dTs_in=dTs_val)
    turbojet.ambient.SetConditionsAS210('DP', alt_in=Altitude_val, MN_in=Mach_val, dTs_in=dTs_val, switchDay='STANDARD', switchHum='RH', switchMode='ALDTMN')
    turbojet.Run_DP_simulation()

    # run the Off-Design (OD) simulation, to find the steady state operating points for all fsys.inputpoints
    turbojet.Mode = 'OD'
    turbojet.inputpoints = fuelcontrol.get_OD_input_points()
    print("\nOff-design (OD) results")
    print("=======================")
    # set OD ambient/flight conditions; note that Ambient.SetConditions must be implemented inside RunODsimulation if a sweep of operating/inlet
    # conditions is desired
    Altitude_val = 0
    Mach_val = 0.5
    dTs_val = 10
    ambient_option = 'STANDARD_PSTSTT' # or 
    # ambient_option = 'STANDARD_ALDTMN' # or 
    # ambient_option = 'STANDARD_ALDTVT' # or 
    # ambient_option = 'STANDARD_ALDTVE' # or 
    # ambient_option = 'STANDARD_ALDTVC' # or 
    # ambient_option = 'HOT_ALDTMN'
    if ambient_option == 'STANDARD_PSTSTT':
        # Standard ambient conditions, PSTSTT switchmode
        turbojet.ambient.SetConditionsAS210(switchDay='STANDARD', switchHum='RH', switchMode='PSTSTT')
        turbojet.ambient.SetConditions('OD', Ps_in=101325.0, Ts_in=298.150000, Tt_in=313.057500, humRel_in=0.5)
    elif ambient_option == 'STANDARD_ALDTMN':
        # Standard ambient conditions, ALDTMN switchmode
        turbojet.ambient.SetConditionsAS210(switchDay='STANDARD', switchHum='RH', switchMode='ALDTMN')
        turbojet.ambient.SetConditions('OD', alt_in=Altitude_val, MN_in=Mach_val, dTs_in=dTs_val, humRel_in=0.5)
    elif ambient_option == 'STANDARD_ALDTVT':
        # Standard ambient conditions, ALDTVT switchmode
        turbojet.ambient.SetConditionsAS210(switchDay='STANDARD', switchHum='RH', switchMode='ALDTVT')
        turbojet.ambient.SetConditions('OD', alt_in=Altitude_val, VTAS_in=173.074277, dTs_in=dTs_val, humRel_in=0.5)
    elif ambient_option == 'STANDARD_ALDTVE':
        # Standard ambient conditions, ALDTVE switchmode
        turbojet.ambient.SetConditionsAS210(switchDay='STANDARD', switchHum='RH', switchMode='ALDTVE')
        turbojet.ambient.SetConditions('OD', alt_in=Altitude_val, VEAS_in=170.147054, dTs_in=dTs_val, humRel_in=0.5)
    elif ambient_option == 'STANDARD_ALDTVC':
        # Standard ambient conditions, ALDTVC switchmode
        turbojet.ambient.SetConditionsAS210(switchDay='STANDARD', switchHum='RH', switchMode='ALDTVC')
        turbojet.ambient.SetConditions('OD', alt_in=Altitude_val, VCAS_in=170.147053, dTs_in=dTs_val, humRel_in=0.5)
    elif ambient_option == 'HOT_ALDTMN':
        # Hot ambient conditions, ALDTMN switchmode
        turbojet.ambient.SetConditionsAS210(switchDay='HOT', switchHum='RH', switchMode='ALDTMN')
        turbojet.ambient.SetConditions('OD', alt_in=Altitude_val, MN_in=Mach_val, dTs_in=dTs_val, humRel_in=0.5)
    # Run OD simulation
    if turbojet.Run_OD_simulation() < 1:
        return

    # export OutputTable to CSV
    turbojet.prepare_output_table()
    turbojet.OutputToCSV()

    # plot nY vs X parameter
    turbojet.Plot_X_nY_graph('Engine performance vs. N [%]',
                            # suffix for filename to keep multiple plot files apart
                            "",
                            # common X parameter column name with label
                            ("N1%",           "Rotor speed [%]"),
                            # 4 Y paramaeter column names with labels and color
                            [   ("T040",              "TIT [K]",                  "blue"),
                                ("T050",              "EGT [K]",                  "blue"),
                                ("W020",              "Inlet mass flow [kg/s]",   "blue"),
                                ("Wf_Brn",            "Fuel flow [kg/s]",         "blue"),
                                ("FN",                "Net thrust [kN]",          "blue")
                            ],
                            False # do_show
                            )

     # Create component map plots with operating lines if available
    turbojet.PlotMaps()

    print("end of running turbojet simulation")

# main program start, calls main()
if __name__ == "__main__":
    main()
