
import numpy as np

# use dictionary for gas path conditions oriented by gas path station number
gaspath_conditions = {}

shaft_list = []

states = np.array([], dtype=float)
errors = np.array([], dtype=float)

FG = 0.0
FN = 0.0
RD = 0.0
WF = 0.0

OutputColumnNames = None
OutputTable = None

def find_shaft_by_number(ShaftNr):
    for shaft in shaft_list:
        if shaft.ShaftNr == ShaftNr:
            return shaft
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