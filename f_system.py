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
import pandas as pd
from scipy.optimize import root

# use dictionary for gas path conditions oriented by gas path station number
gaspath_conditions = {}

# 1.1 WV dictionary for output during iteration (e.g. for control equations)
output_dict = {}

system_model = [] # system model component list
shaft_list = []

inputpoints = np.array([], dtype=float)

states = np.array([], dtype=float)
errors = np.array([], dtype=float)

FG = 0.0
FN = 0.0
RD = 0.0
WF = 0.0

OutputColumnNames = None
OutputTable = None
Ambient = None
# Control = None
Mode = None

def get_shaft(ShaftNr):
    for shaft in shaft_list:
        if shaft.ShaftNr == ShaftNr:
            return shaft
    return None  # Return None if no matching object is found

# find system model component object by name
def get_comp(component_name):
    for comp in system_model:
        if comp.name == component_name:
            return comp
    return None  # Return None if no matching object is found

def reinit_states_and_errors():
    global states, errors
    for state in states:
        state = 1
    for error in errors:
        state = 0

def reinit_system():
    for shaft in shaft_list:
        shaft.PW_sum = 0
    global FG, FN, RD, WF
    FG = 0.0
    FN = 0.0
    RD = 0.0
    WF = 0.0

# method running component model simulations/calculations
# from inlet(s) through exhaust(s)
def Do_Run(PointTime, states_par):
    global system_model, states, errors, Ambient, Control
    states = states_par.copy()
    reinit_system()
    # Ambient.Run(Mode, PointTime)
    # Ambient.AddOutputToDict(Mode)

    output_dict['Point/Time'] = PointTime
    output_dict['Mode'] = Mode

    # Control.Run(Mode, PointTime)
    # Control.AddOutputToDict(Mode)
    for comp in system_model:
        comp.Run(Mode, PointTime)
        comp.AddOutputToDict(Mode)
    AddSystemOutputToDict(Mode)
    for comp in system_model:
        comp.PostRun(Mode, PointTime)

    # 1.1 WV PostRun to evaluate equations
    # Control.PostRun(Mode, PointTime)
    return errors

def Run_DP_simulation():
    # not using states and errors yet for DP, but do this for later when doing DP iterations
    reinit_states_and_errors()
    Do_Run(0, states)    # in DP always fsys.states = [1, 1, 1, 1, .....]
    Do_Output(0, None)

def Run_OD_simulation():
    def residuals(states):
        # residuals will return residuals of system conservation equations, schedules, limiters etc.
        # the residuals are the errors returned by Do_Run
        return Do_Run(inputpoints[ipoint], states)
    try:
        # start with all states 1 and errors 0
        reinit_states_and_errors()
        maxiter=50
        failedcount = 0
        for ipoint in inputpoints:
            # solution returns the residual errors after conversion (shoudl be within the tolerance 'tol')
            options = {
                # "xtol":1e-4           # this only avoids an initial warning,
                                        # leave it: only warning at initial step, but a bit faster
                                        # (with automatic min step size)
            }
            # solution = root(residuals, fsys.states, method='krylov', options = options) # leave tolerance at default: is fastest and error ususally < 0.00001
            # fsys.Do_Output(Mode, inputpoints[ipoint])
            solution = root(residuals, states, method='krylov', options={'maxiter': maxiter}) # leave tolerance at default: is fastest and error ususally < 0.00001
            Do_Output(inputpoints[ipoint], solution)
            if not solution.success:
                failedcount = failedcount + 1
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

    print(f"{len(inputpoints) - 1 - failedcount} OD points calculated, {failedcount} failed")

def PrintPerformance(Mode, PointTime):
    print(f"System performance ({Mode}) Point/Time:{PointTime}")
    FN = FG - RD
    print(f"\tNet thrust: {FN:.2f} N")
    for shaft in shaft_list:
        print(f"\tPower shaft {shaft.ShaftNr} : {shaft.PW_sum/1000:.2f} kW")

def GetOutputTableColumnNames():
    colnames = ["FG", "FN", "RD", "WF"]
    for shaft in shaft_list:
        colnames = colnames + [f"PW{shaft.ShaftNr}"]
    return colnames

 #  1.1 WV
def AddSystemOutputToDict(Mode):
    FN = FG - RD
    output_dict["FG"] = FG
    output_dict["FN"] = FN
    output_dict["RD"] = RD
    output_dict["WF"] = WF
    for shaft in shaft_list:
        output_dict[f"PW{shaft.ShaftNr}"] = shaft.PW_sum/1000

def Do_Output(PointTime, Solution):
    # output to terminal
    global system_model,  OutputColumnNames, OutputTable, Ambient
    for comp in system_model:
        comp.PrintPerformance(Mode, PointTime)
    PrintPerformance(Mode, PointTime)

    # add system performance
    AddSystemOutputToDict(Mode)

    if (Solution != None) and (not Solution.success):
        output_dict['Comment'] = 'Not converged'

    # add output of this point (ouptut_dict) to OutputTable
    if OutputTable is None:
        OutputTable = pd.DataFrame([output_dict])
    else:
        OutputTable = pd.concat([OutputTable, pd.DataFrame([output_dict])], ignore_index=True)

def print_states_and_errors():
   	print(f"Nr. of states: {len(states)}\nNr. of errors: {len(errors)}")
