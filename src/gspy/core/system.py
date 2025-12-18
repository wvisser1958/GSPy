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

import numpy as np
import pandas as pd
from scipy.optimize import root
import matplotlib.pyplot as plt
import os

VERBOSE = True
# 1.5 Declare a global registry in gspy/core/system.py
components = {}   # maps component name -> instance

# use dictionary for gas path conditions oriented by gas path station number
gaspath_conditions = {}

# 1.1 WV dictionary for output during iteration (e.g. for control equations)
output_dict = {}

system_model = [] # system model component list
shaft_list = []

inputpoints = np.array([], dtype=float)
points_output_interval = 1

states = np.array([], dtype=float)
errors = np.array([], dtype=float)

FG = 0.0
FN = 0.0
RD = 0.0
WF = 0.0

OutputTable = None
Ambient = None
# Control = None
Mode = None
ErrorTolerance = 0.0001 # default error tolerance 0.1%, override if needed in main code

# error code constants
NoError = 0
ConvergenceError = 1
ExceptionError = 2

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
    FG = 0.0    # Gross thrust kN
    FN = 0.0    # Net thrust kN
    RD = 0.0    # Ram drag kN
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
    # v1.3 moved to BEFORE PostRun calls
    AddSystemOutputToDict(Mode)
    for comp in system_model:
        comp.PostRun(Mode, PointTime)
    return errors

def Run_DP_simulation():
    # not using states and errors yet for DP, but do this for later when doing DP iterations
    try:
        reinit_states_and_errors()
        Do_Run(0, states)    # in DP always fsys.states = [1, 1, 1, 1, .....]
        Do_Output(0, NoError)      # 0 to indicated all Ok if we get to this line of code after Do_Run
    except Exception as e:
        Do_Output(0, ExceptionError)
        print(f"DP simulation: exception error: {e}")

def Run_OD_simulation():
    def residuals(states):
        # residuals will return residuals of system conservation equations, schedules, limiters etc.
        # the residuals are the errors returned by Do_Run
        return Do_Run(inputpoints[ipoint], states)

    try:
        # start with all states 1 and errors 0
        reinit_states_and_errors()
        maxiter=50
        successcount = 0
        failedcount = 0
        for ipoint in inputpoints:
            # solution returns the residual errors after conversion (shoudl be within the tolerance 'tol')
             # fsys.Do_Output(Mode, inputpoints[ipoint])
            solution = root(residuals,
                            states,
                            method = 'krylov',
                            tol=ErrorTolerance,
                            options={'maxiter': maxiter})
                            # options={'maxiter': maxiter, 'xtol': 0.01})
                            # options={'maxiter': maxiter, 'line_search': 'wolfe'})
            if ipoint % points_output_interval ==0:
                Do_Output(inputpoints[ipoint], NoError if solution.success else ConvergenceError)
            if solution.success:
                successcount = successcount + 1
            else:
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
        Do_Output(inputpoints[ipoint], ExceptionError)
        failedcount = failedcount + 1
        print(f"OD simulation: exception error: {e}")

    print(f"{successcount} OD points calculated, {failedcount} failed")

    # v1.2 return number of succesfully calculated points
    return successcount

def PrintPerformance(Mode, PointTime):
    print(f"System performance ({Mode}) Point/Time:{PointTime}")
    FN = FG - RD
    if (FG != 0) and (RD !=0):
        print(f"\tNet thrust: {FN:.2f} kN")
    for shaft in shaft_list:
        print(f"\tPower offtake shaft {shaft.ShaftNr} : {shaft.PW_sum/1000:.2f} kW")

 #  1.1 WV
def AddSystemOutputToDict(Mode):
    FN = FG - RD
    output_dict["FG"] = FG
    output_dict["FN"] = FN
    output_dict["RD"] = RD
    output_dict["WF"] = WF
    for shaft in shaft_list:
        output_dict[f"PW{shaft.ShaftNr}"] = shaft.PW_sum/1000

# v1.2
# def Do_Output(PointTime, Solution):
def Do_Output(PointTime, ErrorCode):
    # output to terminal
    global system_model,  OutputTable, Ambient

    if VERBOSE:
        # 1.4
        print(f"")
        print(f"Point {PointTime}:")

        for comp in system_model:
            comp.PrintPerformance(Mode, PointTime)
        PrintPerformance(Mode, PointTime)

    # add system performance
    AddSystemOutputToDict(Mode)

    #  v1.2
    if ErrorCode == 1:
        output_dict['Comment'] = 'Not converged'
    elif ErrorCode == 2:
        output_dict['Comment'] = 'Exception error'
    else:
        output_dict['Comment'] = ''

    # add output of this point (ouptut_dict) to OutputTable
    if OutputTable is None:  # add header + line 0
        OutputTable = pd.DataFrame([output_dict])
    else:
        OutputTable = pd.concat([OutputTable, pd.DataFrame([output_dict])], ignore_index=True)

def print_states_and_errors():
   	print(f"Nr. of states: {len(states)}\nNr. of errors: {len(errors)}")

def OutputToCSV(outputdir, outputcsvfilename):
    # Export to Excel
    os.makedirs(outputdir, exist_ok=True)
    outputcsvfilename = os.path.join(outputdir, outputcsvfilename)
    OutputTable.to_csv(outputcsvfilename, index=False, float_format='%.6f')
    print("output saved in "+outputcsvfilename)

def Plot_X_nY_graph(title, jpg_filename, xcol, ycollist):
    # Plot OutputTable data
    # Create n subplots stacked vertically, sharing the same X-axis
    fig, axes = plt.subplots(nrows=len(ycollist), ncols=1, sharex=True, figsize=(8, 10))
    for ax in axes:
        ax.grid(True, linestyle=':', linewidth=1.0, alpha=1.0)  # add

    # # Plot each variable
    yaxisnr = 0
    xname, xlabel = xcol

    # one-time mask for design points
    dp_mask = (OutputTable["Mode"] == "DP")

    for item in ycollist:
        col   = item[0]
        label = item[1] if len(item) > 1 else item[0]
        color = item[2] if len(item) > 2 else None

        ax = axes[yaxisnr]

        # main line
        ax.plot(OutputTable[xname], OutputTable[col], color=color, zorder=2)
        ax.set_ylabel(label)

        # screen-fixed squares at design points (only for rows where Mode == "DP")
        ax.scatter(
            OutputTable.loc[dp_mask, xname],
            OutputTable.loc[dp_mask, col],
            s=40,                    # points^2, screen-fixed size
            marker="s",
            facecolors="yellow",
            edgecolors="black",
            linewidths=0.8,
            zorder=1,
            label="Design point" if yaxisnr == 0 else None  # add legend label once
        )

        yaxisnr += 1

    axes[yaxisnr - 1].set_xlabel(xlabel)

    # optional: show a single legend (pull handles/labels from the first axes)
    handles, labels = axes[0].get_legend_handles_labels()
    if handles:
        axes[0].legend(handles, labels, loc="best")

    # Optional: improve layout
    modelfilename = os.path.splitext(os.path.basename(__file__))[0]
    fig.suptitle(title, fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    plt.show()
    # xyplotfilename = os.path.join(output_directory, os.path.splitext(os.path.basename(__file__))[0]) + ".jpg"
    fig.savefig(jpg_filename)
    print("x-4y plot saved in " + jpg_filename)
