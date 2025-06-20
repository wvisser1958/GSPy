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

# use dictionary for gas path conditions oriented by gas path station number
gaspath_conditions = {}

system_model = [] # system model component list
shaft_list = []

states = np.array([], dtype=float)
errors = np.array([], dtype=float)

FG = 0.0
FN = 0.0
RD = 0.0
WF = 0.0

OutputColumnNames = None
OutputTable = None
Ambient = None
Control = None

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

def AddOutputToTable(Mode, rownr):
    FN = FG - RD
    OutputTable.loc[rownr, "FG"] = FG
    OutputTable.loc[rownr, "FN"] = FN
    OutputTable.loc[rownr, "RD"] = RD
    OutputTable.loc[rownr, "WF"] = WF
    for shaft in shaft_list:
        OutputTable.loc[rownr, f"PW{shaft.ShaftNr}"] = shaft.PW_sum/1000

def InitializeOutputTable():
    global system_model,  OutputColumnNames, OutputTable, Ambient, Control
    # add Ambient (Flight / Ambient operating conditions) and Control compoenent output column names
    OutputColumnNames = Ambient.GetOutputTableColumnNames() + Control.GetOutputTableColumnNames()
    # add Component models
    for comp in system_model:
        OutputColumnNames = OutputColumnNames + comp.GetOutputTableColumnNames()
    # add system performance output
    OutputColumnNames = OutputColumnNames + GetOutputTableColumnNames()
    # Now remove duplicate columns, like "N1", "Nc1", etc.
    UniqueOutputColumnNames = list(dict.fromkeys(OutputColumnNames))
    OutputTable = pd.DataFrame(columns = ['Point/Time', 'Mode'] + UniqueOutputColumnNames)

# method running component model simulations/calculations
# from inlet(s) through exhaust(s)
def Do_Run(Mode, PointTime, states_par):
    global system_model, states, errors, Ambient, Control
    states = states_par.copy()
    reinit_system()
    Ambient.Run(Mode, PointTime)
    Control.Run(Mode, PointTime)
    for comp in system_model:
        comp.Run(Mode, PointTime)
    return errors

def Do_Output(Mode, PointTime):
    # output to terminal
    global system_model,  OutputColumnNames, OutputTable, Ambient, Control
    Ambient.PrintPerformance(Mode, PointTime)
    Control.PrintPerformance(Mode, PointTime)
    for comp in system_model:
        comp.PrintPerformance(Mode, PointTime)
    PrintPerformance(Mode, PointTime)

    # table output
    newrownumber = len(OutputTable)
    OutputTable.loc[newrownumber, 'Point/Time'] = PointTime
    OutputTable.loc[newrownumber, 'Mode'] = Mode
    Ambient.AddOutputToTable(Mode, newrownumber)
    Control.AddOutputToTable(Mode, newrownumber)
    for comp in system_model:
        comp.AddOutputToTable(Mode, newrownumber)
    AddOutputToTable(Mode, newrownumber)

def print_states_and_errors():
    print(f"Nr. of states: {len(states)}\nNr. of errors: {len(errors)}")