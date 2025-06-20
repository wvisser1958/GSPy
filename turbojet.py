# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#    http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from scipy.optimize import root

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
    # input or combustor exit temperature
    fsys.Control = TControl('Control', '', 0.38, 0.38, 0.06, -0.01)
    # combustor Texit input, with Wf 0.38 as first guess for 1200 K
    # combustor exit temperature
    # fsys.Control = TControl('Control', '', 0.38, 1200, 1000, -20)

    # Generic gas turbine components
    inlet1   = TInlet('Inlet1',      '',            0,2,   19.9, 1    )
    duct1    = TDuct('exhduct',      '',            5,7,   1.0        )
    exhaust1 = TExhaust('exhaust1',  '',            7,8,9, 1, 1, 1, 1 )
    # ***************** Combustor ******************************************************
    # fuel input
    combustor1 = TCombustor('combustor1', '', 3, 4, 0.38, None, 1, 1, None,      43031, 1.9167, 0, '')
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
    compressor1 = TCompressor('compressor1','compmap.map' , 2, 3, 1, 16540, 0.825, 1, 0.75   , 6.92, 'GG')
    turbine1 =    TTurbine(   'turbine1'   ,'turbimap.map', 4, 5, 1, 16540, 0.88 , 1, 0.50943, 0.99, 'GG')

    # for turboshaft, constant speed
    # TCompressor('compressor1','compmap.map', 2,3,   1,   16540, 0.825, 1, 0.8, 6.92, 'CS'),
    # for turboshaft
    # TTurbine('turbine1',      'turbimap.map',4,5,   1,   16540, 0.88,       1, 0.8, 0.99, 'PT'   ),

    # create a turbojet system model
    fsys.system_model = [inlet1,
                         compressor1,
                         combustor1,
                         turbine1,
                         duct1,
                         exhaust1]

    fsys.InitializeOutputTable()
    # # add Ambient (Flight / Ambient operating conditions) and Control compoenent output column names
    # fsys.OutputColumnNames = fsys.Ambient.GetOutputTableColumnNames() + fsys.Control.GetOutputTableColumnNames()
    # # add Component models
    # for comp in fsys.systemmodel:
    #     fsys.OutputColumnNames = fsys.OutputColumnNames + comp.GetOutputTableColumnNames()
    # # add system performance output
    # fsys.OutputColumnNames = fsys.OutputColumnNames + fsys.GetOutputTableColumnNames()
    # fsys.OutputTable = pd.DataFrame(columns = ['Point/Time', 'Mode'] + fsys.OutputColumnNames)

    # define the gas model in f_global
    fg.InitializeGas()

    # run the system model Design Point (DP) calculation
    Mode = 'DP'
    print("Design point (DP) results")
    print("=========================")
    # set DP ambient/flight conditions
    fsys.Ambient.SetConditions('DP', 0, 0, 0, None, None)
    # not using states and errors yet for DP, but do this for later when doing DP iterations
    fsys.reinit_states_and_errors()
    fsys.Do_Run(Mode, 0, fsys.states)    # in DP always fsys.states = [1, 1, 1, 1, .....]
    fsys.Do_Output(Mode, 0)

    # run the Off-Design (OD) simulation, using Newton-Raphson to find
    # the steady state operating point

    # return # uncomment for design point only

    Mode = 'OD'
    inputpoints = fsys.Control.Get_OD_inputpoints()
    # inputpoints = np.arange(0, 10, 1)
    print("\nOff-design (OD) results")
    print("=======================")
    # set OD ambient/flight conditions
    fsys.Ambient.SetConditions('OD', 0, 0, 0, None, None)

    def residuals(states):
        # residuals will return residuals of system conservation equations, schedules, limiters etc.
        # the residuals are the errors returned by Do_Run
        # test with GSP final performan with 0.3 kg/s fuel at ISA static
        # states = [+9.278E-01,  +9.438E-01,  +8.958E-01,  +1.008E+00]
        return fsys.Do_Run(Mode, inputpoints[ipoint], states)

    # for debug
    # savedstates = np.empty((0, fsys.states.size+2), dtype=float)

    try:
        # start with all states 1 and errors 0
        fsys.reinit_states_and_errors()
        maxiter=50
        for ipoint in inputpoints:
            # solution returns the residual errors after conversion (shoudl be within the tolerance 'tol')
            options = {
                # "xtol":1e-4           # this only avoids an initial warning,
                                        # leave it: only warning at initial step, but a bit faster
                                        # (with automatic min step size)
            }
            # solution = root(residuals, fsys.states, method='krylov', options = options) # leave tolerance at default: is fastest and error ususally < 0.00001
            # fsys.Do_Output(Mode, inputpoints[ipoint])
            solution = root(residuals, fsys.states, method='krylov', options={'maxiter': maxiter}) # leave tolerance at default: is fastest and error ususally < 0.00001
            if solution.success:
                fsys.Do_Output(Mode, inputpoints[ipoint])
            else:
                print(f"Could not find a solution for point {ipoint} with max {maxiter} iterations")
            # for debug
            # wf = fu.get_component_object_by_name(turbojet, 'combustor1').Wf
            # wfpoint = np.array([inputpoints[ipoint], wf], dtype=float)
            # point_wf_states_array = np.concatenate((wfpoint, fsys.states))
            # savedstates = np.vstack([savedstates, point_wf_states_array])
        # for debug
        # solution = root(residuals, [ 0.55198737,  0.71696654,  0.76224776,  0.85820746], method='krylov')
    except Exception as e:
        print(f"An error occurred: {e}")

    # Export to Excel
    output_directory = 'output'
    os.makedirs(output_directory, exist_ok=True)
    outputcsvfilename = os.path.join(output_directory, 'output.csv')
    fsys.OutputTable.to_csv(outputcsvfilename, index=False)
    print("output saved in "+outputcsvfilename)

     # Create plots with operating lines if available
    for comp in fsys.system_model:
        comp.PlotMaps()
        # if comp.map != None:
        #     print(comp.name + " map with operating curve saved in " + comp.map.map_figure_pathname)

    print("end of running turbojet simulation")

# main program start, calls main()
if __name__ == "__main__":
    main()
