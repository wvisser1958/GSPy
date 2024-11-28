import numpy as np
import cantera as ct

# import matplotlib as mpl
import pandas as pd
from scipy.optimize import root

import f_global as fg

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
    # create a control (controlling all inputs to the system model) 
    Control = TControl('Control', '')
   
    # create Ambient conditions object (to set ambient/inlet/flight conditions)
    #                              Altitude, Mach, dTs,    Ps0,    Ts0 
    # None for Ps0 and Ts0 means values are calculated from standard atmosphere
    Ambient = TAmbient('Ambient',     0, 0,   0,   None,   None)
    
    # create a turbojet system model
    turbojet = [TInlet('Inlet1',          '',            0,2,   19.9, 1    ),                           \
                TCompressor('compressor1','compmap.map', 2,3,   1, 0.8, 1,   16540, 0.825, 6.92),       \
                TCombustor('combustor1',  '',            3,4,   Control, 0.38, 0,    1, 1    ),                  \
                TTurbine('turbine1',      'turbimap.map',4,5,   1, 0.8,       1,   16540, 0.88       ), \
                TDuct('exhaustduct',      '',            5,6,   1                 ),                    \
                TExhaust('exhaust1',      '',            6,8,   1, 1, 1           )]

    OutputColumns = []
    for comp in turbojet:
        OutputColumns = OutputColumns + comp.GetOutputTableColumns()
    fg.OutputTable = pd.DataFrame(columns = ['Point/Time', 'Mode'] + OutputColumns)

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
    def Do_Run(Mode, PointTime, q_gas):
        fg.reinit_all_shafts()
        Ambient.Run(Mode, PointTime, q_gas)     
        Control.Run(Mode, PointTime, q_gas, Ambient)
        for comp in turbojet:
            q_gas = comp.Run(Mode, PointTime, q_gas, Ambient)

    def Do_Output(Mode, PointTime):
        Ambient.PrintPerformance(Mode, PointTime)     
        Control.PrintPerformance(Mode, PointTime) 
        for comp in turbojet:
            q_gas = comp.PrintPerformance(Mode, PointTime) 
        fg.PrintPerformance(Mode, PointTime)   
        
        # table output
        newrownumber = len(fg.OutputTable) 
        fg.OutputTable.loc[newrownumber, 'Point/Time'] = PointTime
        fg.OutputTable.loc[newrownumber, 'Mode'] = Mode
        for comp in turbojet:
            comp.AddOutputToTable(Mode, newrownumber)

    # run the system model Design Point (DP) calculation
    Mode = 'DP'
    print("Design point (DP) results")
    print("=========================")
    # set DP ambient/flight conditions
    # Ambient.SetConditions( 0, 0, 0, None, None)
    Do_Run(Mode, 0, q_gas)    
    Do_Output(Mode, 0)

    # return

    # run the Off-Design (OD) simulation, using Newton-Raphson to find
    # the steady state operating point
    Mode = 'OD'
    inputpoints = np.arange(0, 44, 1)
    ipoint = 0
    print("\nOff-design (OD) results")
    print("=======================")
    # set OD ambient/flight conditions
    # Ambient.SetConditions( 0, 0, 0, None, None)

    def residuals(states):
        fg.states = states.copy()
        # test with GSP final performan with 0.3 kg/s fuel at ISA static
        # fg.states = [+9.278E-01,  +9.438E-01,  +8.958E-01,  +1.008E+00]
        Do_Run(Mode, inputpoints[ipoint], q_gas)
        return fg.errors.copy()     
    # solution = fg.newton_raphson(fg.states, residuals)

    # for debug
    savedstates = np.empty((0, fg.states.size+2), dtype=float)
    
    try:
        for ipoint in inputpoints:
            solution = root(residuals, fg.states, method='krylov')    
            Do_Output(Mode, inputpoints[ipoint])
            
            # for debug
            wf = fu.get_component_object(turbojet, 'combustor1').Wf
            wfpoint = np.array([inputpoints[ipoint], wf], dtype=float)
            point_wf_states_array = np.concatenate((wfpoint, fg.states))        
            savedstates = np.vstack([savedstates, point_wf_states_array])          
        # solution = root(residuals, [ 0.55198737,  0.71696654,  0.76224776,  0.85820746], method='krylov')    
    except Exception as e:
        print(f"An error occurred: {e}")
    
    print(savedstates)

    print(fg.OutputTable)

    # Export to Excel
    fg.OutputTable.to_csv('output.csv', index=False)

    print("end of main program")

# main program start, calls main()
if __name__ == "__main__":
    main()   
