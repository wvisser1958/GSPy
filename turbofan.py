import numpy as np
import cantera as ct

# import matplotlib as mpl
import pandas as pd
from scipy.optimize import root

import f_global as fg
import f_system as fsys
import f_utils as fu

from f_control import TControl
from f_ambient import TAmbient

from f_shaft import TShaft

from f_inlet import TInlet
from f_compressor import TCompressor
from f_fan import TFan
from f_combustor import TCombustor
from f_turbine import TTurbine
from f_duct import TDuct
from f_exhaust import TExhaust
import os

def main():
    # create Ambient conditions object (to set ambient/inlet/flight conditions)
    #                              Altitude, Mach, dTs,    Ps0,    Ts0
    # None for Ps0 and Ts0 means values are calculated from standard atmosphere
    fsys.Ambient = TAmbient('Ambient', 0,   0, 0,   0,   None,   None)

    # create a control (controlling all inputs to the system model)
    # direct fuel flow input
    # fsys.Control = TControl('Control', '', 0.48, 0.48, 0.08, -0.01)
    # combustor Texit input, with Wf 0.48 as first guess for 1200 K combustor exit temperature
    fsys.Control = TControl('Control', '', 0.50, 1600, 1100, -50)

    # create a turbojet system model
    fsys.systemmodel = [TInlet('Inlet1',          '',            0,2,   100, .9    ),

                        # for turbofan, note that fan has 2 GasOut outputs
                        TFan('FAN_BST','bigfanc.map', 2, 25, 21,   1,   4400, 0.825, 5, 1, 0.8, 2,
                                       'bigfand.map', 1, 0.8, 1.3,            0.8),

                        # always start with the components following the 1st GasOut object
                        TCompressor('HPC','compmap.map', 25,3,   2,   16540, 0.825, 1, 0.8, 6.92, 'GG'),

                        # ***************** Combustor ******************************************************
                        # fuel input
                        # TCombustor('combustor1',  '',            3,4,   0.38, None,    1, 1,
                        # Texit input
                        TCombustor('combustor1',  '',            3,4,   0.5, 1600,    1, 1,

                                                    # fuel specification examples:
                                                    # fuel specified by LHV, HCratio, OCratio:
                                                        # None,      43031, 1.9167, 0, ''),

                                                    # fuel specified by Fuel composition (by mass)
                                                        # NC12H26 = Dodecane ~ jet fuel, CH4 for hydrogen
                                                    None,      None, None, None, 'NC12H26:1'),
                                                    # fuel specified by Fuel temperature and Fuel composition (by mass)
                                                        # 288.15,      None, None, None, 'CH4:1'),

                                                    # fuel mixtures
                                                    # fuel specified by Fuel temperature and Fuel composition (by mass)
                                                    # 288.15,      None, None, None, 'CH4:5, C2H6:1'),

                        TTurbine('HPT',      'turbimap.map',4,45,   2,   16540, 0.88,       1, 0.8, 1, 'GG'   ),

                        TTurbine('LPT',      'turbimap.map',45,5,   1,   4400, 0.88,       1, 0.8, 1, 'GG'   ),


                        TDuct('Exhduct_hot',      '',                5,7,   1.0                 ),
                        TExhaust('HotNozzle',      '',            7,8,9, 1, 1, 1, 1           ),

                        # now add the list with components following the 2nd fan GasOut (i.e. the bypass duct)
                        TDuct('Exhduct_cold',      '',                21,23,   1.0                 ),
                        TExhaust('ColdNozzle',      '',            23,18,19, 1, 1, 1, 1           )]


    # add Ambient (Flight / Ambient operating conditions) output column names
    fsys.OutputColumnNames = fsys.Ambient.GetOutputTableColumnNames() + fsys.Control.GetOutputTableColumnNames()
    # add Component models
    for comp in fsys.systemmodel:
        fsys.OutputColumnNames = fsys.OutputColumnNames + comp.GetOutputTableColumnNames()
    # add system performance output
    fsys.OutputColumnNames = fsys.OutputColumnNames + fsys.GetOutputTableColumnNames()
    fsys.OutputTable = pd.DataFrame(columns = ['Point/Time', 'Mode'] + fsys.OutputColumnNames)

    # define the gas model in f_global
    fg.InitializeGas()

    # method running component model simulations/calculations
    # from inlet(s) through exhaust(s)
    def Do_Run(Mode, PointTime, states):
        fsys.states = states.copy()
        fsys.reinit_system()
        fsys.Ambient.Run(Mode, PointTime)
        fsys.Control.Run(Mode, PointTime)
        for comp in fsys.systemmodel:
            # q_gas = comp.Run(Mode, PointTime, q_gas)
            comp.Run(Mode, PointTime)
        return fsys.errors

    def Do_Output(Mode, PointTime):
        fsys.Ambient.PrintPerformance(Mode, PointTime)
        fsys.Control.PrintPerformance(Mode, PointTime)
        for comp in fsys.systemmodel:
            comp.PrintPerformance(Mode, PointTime)
        fsys.PrintPerformance(Mode, PointTime)

        # table output
        newrownumber = len(fsys.OutputTable)
        fsys.OutputTable.loc[newrownumber, 'Point/Time'] = PointTime
        fsys.OutputTable.loc[newrownumber, 'Mode'] = Mode
        fsys.Ambient.AddOutputToTable(Mode, newrownumber)
        fsys.Control.AddOutputToTable(Mode, newrownumber)
        for comp in fsys.systemmodel:
            comp.AddOutputToTable(Mode, newrownumber)
        fsys.AddOutputToTable(Mode, newrownumber)

    # run the system model Design Point (DP) calculation
    Mode = 'DP'
    print("Design point (DP) results")
    print("=========================")
    # set DP ambient/flight conditions
    fsys.Ambient.SetConditions('DP', 0, 0, 0, None, None)
    # not using states and errors yet for DP, but do this for later when doing DP iterations
    fsys.reinit_states_and_errors()
    Do_Run(Mode, 0, fsys.states)    # in DP always fsys.states = [1, 1, 1, 1, .....]
    Do_Output(Mode, 0)

    # return # uncomment for design point only

    Mode = 'OD'
    inputpoints = fsys.Control.Get_OD_inputpoints()
    # inputpoints = np.arange(0, 10, 1)
    ipoint = 0
    print("\nOff-design (OD) results")
    print("=======================")
    # set OD ambient/flight conditions
    fsys.Ambient.SetConditions('OD', 0, 0, 0, None, None)

    def residuals(states):
        # residuals will return residuals of system conservation equations, schedules, limiters etc.
        # the residuals are the errors returned by Do_Run
        # test with GSP final performan with 0.3 kg/s fuel at ISA static
        # states = [+9.278E-01,  +9.438E-01,  +8.958E-01,  +1.008E+00]
        return Do_Run(Mode, inputpoints[ipoint], states)

    # for debug
    # savedstates = np.empty((0, fsys.states.size+2), dtype=float)

    try:
        # start with all states 1 and errors 0
        fsys.reinit_states_and_errors()
        # run the Off-Design (OD) simulation for all points, using root with 'krylov'
        for ipoint in inputpoints:
            # solution returns the residual errors after conversion (should be within the tolerance 'tol')
            options = {
                # "xtol":1e-4           # this only avoids an initial warning,
                                        # leave it: only warning at initial step, but a bit faster
                                        # (with automatic min step size)
            }
            solution = root(residuals, fsys.states, method='krylov', options=options) # leave tolerance at default: is fastest and error ususally < 0.00001
            Do_Output(Mode, inputpoints[ipoint])

            # for debug
            # wf = fu.get_component_object_by_name(turbojet, 'combustor1').Wf
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
    output_directory = 'output'
    os.makedirs(output_directory, exist_ok=True)
    fsys.OutputTable.to_csv(os.path.join(output_directory, 'output.csv'), index=False)

     # Create plots with operating lines if available
    for comp in fsys.systemmodel:
        comp.PlotMaps()

    print("end of running turbofan simulation")

# main program start, calls main()
if __name__ == "__main__":
    main()
