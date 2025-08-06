# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#    http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import f_global as fg
import f_system as fsys

from f_control import TControl
from f_ambient import TAmbient

from f_shaft import TShaft

from f_inlet import TInlet
from f_compressor import TCompressor
from f_combustor import TCombustor
from f_turbine import TTurbine
from f_duct import TDuct
from f_exhaust import TExhaust

import f_utils as fu
import os

def main():
    # create Ambient conditions object (to set ambient/inlet/flight conditions)
    #                               Altitude, Mach, dTs,    Ps0,    Ts0
    # None for Ps0 and Ts0 means values are calculated from standard atmosphere
    fsys.Ambient = TAmbient('Ambient', 0, 0, 0,   0,   None,   None)

    # create a control (controlling inputs to the system model)
    # components like the combustor retrieve inputs like fuel flow
    # input fuel flow (open loop control):
    # Control = TControl('Control', '', 0.38, 0.38, 0.06, -0.01, '')
    # or combustor Texit input, with Wf 0.38 as design point, and OD 1200 .. 1000 K combustor exit temperature:
    # fsys.Control = TControl('Control', '', 0.38, 1200, 1000, -20, '')
    # Specify control parameter N1% (this adds an equation with combustor fuel flow as free state)
    N1control = TControl('Control', '', 0.38, 100, 60, -5, 'N1%')

    inlet1   = TInlet('Inlet1',      '',    None,            0,2,   19.9, 1    )

    combustor1 = TCombustor('combustor1', '',    N1control, 3, 4, 0.38, None, 1, 1, None,      43031, 1.9167, 0, '')
    # Texit input
    # TCombustor('combustor1',  '',           3, 4, 0.38, 1200, 1, 1,
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

    # for turbojet
    compressor1 = TCompressor('compressor1','compmap.map' ,    None, 2, 3, 1, 16540, 0.825, 1, 0.75   , 6.92, 'GG')
    turbine1 =    TTurbine(   'turbine1'   ,'turbimap.map',    None, 4, 5, 1, 16540, 0.88 , 1, 0.50943, 0.99, 'GG')

    # for turboshaft, constant speed
    # TCompressor('compressor1','compmap.map', 2,3,   1,   16540, 0.825, 1, 0.8, 6.92, 'CS'),
    # for turboshaft
    # TTurbine('turbine1',      'turbimap.map',4,5,   1,   16540, 0.88,       1, 0.8, 0.99, 'PT'   ),

    duct1    = TDuct('exhduct',      '',    None,            5,7,   1.0        )
    exhaust1 = TExhaust('exhaust1',  '',    None,            7,8,9, 1, 1, 1, 1 )

    # create a turbojet system model
    fsys.system_model = [fsys.Ambient,
                         N1control,
                         inlet1,
                         compressor1,
                         combustor1,
                         turbine1,
                         duct1,
                         exhaust1]

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
    fsys.inputpoints = N1control.Get_OD_inputpoints()
    print("\nOff-design (OD) results")
    print("=======================")
    # set OD ambient/flight conditions
    fsys.Ambient.SetConditions('OD', 0, 0, 0, None, None)
    # Run OD simulation
    fsys.Run_OD_simulation()

    # Export to Excel
    output_directory = 'output'
    os.makedirs(output_directory, exist_ok=True)
    outputcsvfilename = os.path.join(output_directory, 'output.csv')
    fsys.OutputTable.to_csv(outputcsvfilename, index=False)
    print("output saved in "+outputcsvfilename)

     # Create plots with operating lines if available
    for comp in fsys.system_model:
        comp.PlotMaps()

    print("end of running turbojet simulation")

# main program start, calls main()
if __name__ == "__main__":
    main()
