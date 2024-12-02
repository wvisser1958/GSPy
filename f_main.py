import numpy as np
import cantera as ct

# import matplotlib as mpl
import pandas as pd
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

global q_gas
    
def main():
    # create Ambient conditions object (to set ambient/inlet/flight conditions)
    #                              Altitude, Mach, dTs,    Ps0,    Ts0 
    # None for Ps0 and Ts0 means values are calculated from standard atmosphere
    Ambient = TAmbient('Ambient',     0, 0,   0,   None,   None)
    
    # create a control (controlling all inputs to the system model) 
    Control = TControl('Control', '')

    # create a turbojet system model
    turbojet = [TInlet('Inlet1',          '',            0,2,   19.9, 1    ),                           \
                TCompressor('compressor1','compmap.map', 2,3,   1, 0.8, 1,   16540, 0.825, 6.92),       \
                TCombustor('combustor1',  '',            3,4,   Control, 0.38, 0,    1, 1    ),         \
                TTurbine('turbine1',      'turbimap.map',4,5,   1, 0.8,       1,   16540, 0.88       ), \
                TDuct('exhduct',      '',                5,7,   1                 ),                    \
                TExhaust('exhaust1',      '',            7,8,9, 1, 1, 1           )]

    # add Ambient (Flight / Ambient operating conditions) output column names
    fsys.OutputColumnNames = Ambient.GetOutputTableColumnNames() + Control.GetOutputTableColumnNames()
    # add Component models
    for comp in turbojet:
        fsys.OutputColumnNames = fsys.OutputColumnNames + comp.GetOutputTableColumnNames()
    # add system performance output
    fsys.OutputColumnNames = fsys.OutputColumnNames + fsys.GetOutputTableColumnNames()
    fsys.OutputTable = pd.DataFrame(columns = ['Point/Time', 'Mode'] + fsys.OutputColumnNames)

    # define the gas model
    gas = ct.Solution('gri30.yaml')
    # gas = ct.Solution('jetsurf.yaml') 
    # start with air
    fg.InitializeGas(gas)
    # gas.TPY = fg.T_std, fg.P_std, fg.s_air_composition_mass
    global q_gas
    q_gas = ct.Quantity(gas, mass = 1) # initialize quantity

    # method running component model simulations/calculations
    # from inlet(s) through exhaust(s)
    def Do_Run(Mode, PointTime, q_gas, states):
        fsys.states = states.copy()
        fsys.reinit_system()
        Ambient.Run(Mode, PointTime, q_gas)     
        Control.Run(Mode, PointTime, q_gas, Ambient)
        for comp in turbojet:
            q_gas = comp.Run(Mode, PointTime, q_gas, Ambient)
        return fsys.errors

    def Do_Output(Mode, PointTime):
        Ambient.PrintPerformance(Mode, PointTime)     
        Control.PrintPerformance(Mode, PointTime) 
        for comp in turbojet:
            q_gas = comp.PrintPerformance(Mode, PointTime) 
        fsys.PrintPerformance(Mode, PointTime)   
        
        # table output
        newrownumber = len(fsys.OutputTable) 
        fsys.OutputTable.loc[newrownumber, 'Point/Time'] = PointTime
        fsys.OutputTable.loc[newrownumber, 'Mode'] = Mode
        Ambient.AddOutputToTable(Mode, newrownumber)
        Control.AddOutputToTable(Mode, newrownumber)
        for comp in turbojet:
            comp.AddOutputToTable(Mode, newrownumber)
        fsys.AddOutputToTable(Mode, newrownumber)            

    # run the system model Design Point (DP) calculation
    Mode = 'DP'
    print("Design point (DP) results")
    print("=========================")
    # set DP ambient/flight conditions
    Ambient.SetConditions('DP', 0, 0, 0, None, None)
    # not using states and errors yet for DP, but do this for later when doing DP iterations
    fsys.reinit_states_and_errors()
    Do_Run(Mode, 0, q_gas, fsys.states)    # in DP always fsys.states = [1, 1, 1, 1, .....]
    Do_Output(Mode, 0)

    # run the Off-Design (OD) simulation, using Newton-Raphson to find
    # the steady state operating point
    Mode = 'OD'
    inputpoints = np.arange(0, 44, 1)
    ipoint = 0
    print("\nOff-design (OD) results")
    print("=======================")
    # set OD ambient/flight conditions
    Ambient.SetConditions('OD', 0, 0, 0, None, None)
    
    def residuals(states):
        # residuals will return residuals of system conservation equations, schedules, limiters etc.
        # the residuals are the errors returned by Do_Run        
        # test with GSP final performan with 0.3 kg/s fuel at ISA static
        # states = [+9.278E-01,  +9.438E-01,  +8.958E-01,  +1.008E+00]
        return Do_Run(Mode, inputpoints[ipoint], q_gas, states) 
        
    # for debug
    # savedstates = np.empty((0, fsys.states.size+2), dtype=float)
    
    try:
        # start with all states 1 and errors 0
        fsys.reinit_states_and_errors() 
        for ipoint in inputpoints:
            # solution returns the residual errors after conversion (shoudl be within the tolerance 'tol')
            solution = root(residuals, fsys.states, method='krylov') # leave tolerance at default: is fastest and error ususally < 0.00001  
            Do_Output(Mode, inputpoints[ipoint])
            
            # for debug
            # wf = fu.get_component_object(turbojet, 'combustor1').Wf
            # wfpoint = np.array([inputpoints[ipoint], wf], dtype=float)
            # point_wf_states_array = np.concatenate((wfpoint, fsys.states))        
            # savedstates = np.vstack([savedstates, point_wf_states_array])          
        # for debug
        # solution = root(residuals, [ 0.55198737,  0.71696654,  0.76224776,  0.85820746], method='krylov')    
    except Exception as e:
        print(f"An error occurred: {e}")
    
    # print(savedstates)

    # print(fsys.OutputTable)

    # Export to Excel
    fsys.OutputTable.to_csv('output.csv', index=False)

    print("end of main program")

# main program start, calls main()
if __name__ == "__main__":
    main()   
