import numpy as np
from scipy.optimize import root
import cantera as ct
from f_gaspath import TGaspath as gaspath
    
atomweightC = 12.010914 
molemassCO2 = 44.0098
atomweightO = 15.99940
molemassO2 = 31.9988
atomweightH = 1.0079832
atomweightN = 14
MM_NO2 = 46.00554

def set_enthalpy(gas, target_enthalpy):
    def equation(Titer):
        gas.TP = Titer, None
        return gas.enthalpy_mass - target_enthalpy 
    solution = root(equation, x0 = gas.T)
    if solution.success:
        return gas.T
    else:
        print("Root not found")

def pressure_ratio_for_enthalpy_drop(gas, initial_pressure, target_enthalpy_drop, eta_is) :
    # Set the initial state
    gas.TP = gas.T, initial_pressure
    initial_enthalpy = gas.enthalpy_mass
    initial_entropy = gas.entropy_mass  # Store initial entropy for isentropic condition

    # Define the function to find the root of
    def enthalpy_drop_difference(pressure_ratio):
        final_pressure = initial_pressure * pressure_ratio[0]
        gas.SP = initial_entropy, final_pressure  # Set entropy and pressure (isentropic condition)
        final_enthalpy_is = gas.enthalpy_mass
        final_enthalpy = initial_enthalpy - eta_is * (initial_enthalpy - final_enthalpy_is)
        gas.HP = final_enthalpy, final_pressure
        # Difference between current enthalpy drop and target enthalpy drop
        return initial_enthalpy - final_enthalpy - target_enthalpy_drop

    # Initial guess for pressure ratio
    initial_guess = [0.5]

    # Use scipy.optimize.root to find the pressure ratio
    solution = root(enthalpy_drop_difference, initial_guess)

    # Check if the solution converged
    if solution.success:
        return solution.x[0], gas.enthalpy_mass, gas.P  # The pressure ratio
    else:
        raise ValueError("Solution did not converge")     

def calculate_exit_velocity(gas, pressure_ratio):
    # Store the initial enthalpy for the stagnation state
    stagnation_enthalpy = gas.enthalpy_mass

    # Calculate exit state based on the pressure ratio
    exit_pressure = gas.P / pressure_ratio
    # keep entropy S constant
    gas.SP = gas.entropy_mass, exit_pressure  # Isentropic expansion to exit pressure
    exit_enthalpy = gas.enthalpy_mass

    # Calculate the exit velocity
    velocity = (2 * (stagnation_enthalpy - exit_enthalpy))**0.5

    return velocity, gas.T

def calculate_expansion_to_A(gas, pressure_ratio, A):
    # Store the initial enthalpy for the stagnation state
    stagnation_enthalpy = gas.enthalpy_mass
    stagnation_entropy = gas.entropy_mass

    # Calculate exit state based on the pressure ratio
    stagnation_pressure = gas.P 
    exit_pressure = gas.P / pressure_ratio
    # keep entropy S constant
    gas.SP = gas.entropy_mass, exit_pressure  # Isentropic expansion to exit pressure
    exit_enthalpy = gas.enthalpy_mass

    # Calculate the exit velocity
    dh = stagnation_enthalpy - exit_enthalpy
    if dh < 0:
        # allow backwards flow during iteration (avoiding complex number for velocity)
        velocity = -(2 * abs(dh))**0.5
    else:
        velocity = (2 * dh)**0.5
    Mout = velocity / gas.sound_speed 
    if Mout < 1:
        exit_enthalpy = gas.enthalpy_mass   
        massflow = A * velocity * gas.density 
        return exit_pressure, gas.T, velocity, massflow
    else:
        # exit_pressure = gas.P / pressure_ratio
        # keep entropy S constant
        def throat_H_error(Ps_throat):
            gas.SP = stagnation_entropy, Ps_throat  # Isentropic expansion to exit pressure
            dh = stagnation_enthalpy - gas.enthalpy_mass
            # allow backwards flow during iteration (avoiding complex number for velocity)
            if dh < 0:
                velocity = -(2 * abs(dh))**0.5
            else:
                velocity = (2 * dh)**0.5
            velocity1 = gas.sound_speed
            return velocity - velocity1
        initial_guess = [stagnation_pressure/1.9] # 1.0 approx. critical PR
        solution = root(throat_H_error, initial_guess)
        
        massflow = A * gas.sound_speed * gas.density        
        # Check if the solution converged
        if solution.success:
            return solution.x[0], gas.T, gas.sound_speed , massflow 
        else:
            raise ValueError("Solution throat P did not converge")  
   
def exit_T_and_enthalpy_for_pressure_ratio(gas, target_PR, eta_is) :
    # Set the initial state
    # gas.TP = gas.T, initial_pressure
    initial_enthalpy = gas.enthalpy_mass
    initial_entropy = gas.entropy_mass  # Store initial entropy for isentropic condition

    Pend = gas.P / target_PR
    gas.SP = initial_entropy, Pend  # Set entropy and pressure (isentropic condition)
    final_enthalpy_is = gas.enthalpy_mass
    # eta_is = (initial_enthalpy - final_enthalpy) / (initial_enthalpy - final_enthalpy_is)
    final_enthalpy = initial_enthalpy - (initial_enthalpy - final_enthalpy_is) * eta_is
    gas.HP = final_enthalpy, Pend
    return gas.T, gas.enthalpy_mass    

def get_component_object_by_name(component_objects, aname):
    return next((obj for obj in component_objects if obj.name == aname), None)

def get_gaspathcomponent_object_inlet_stationnr(component_objects, astationnr):
    return next((obj for obj in component_objects if (isinstance(obj, gaspath)) and (obj.stationin == astationnr)), None)

def Compression(GasIn: ct.Quantity, GasOut: ct.Quantity, PR, Etais):
    Sin = GasIn.s
    Pout = GasIn.P*PR
    GasOut.SP = Sin, Pout # get GasOut at constant s and higher P
    Hisout = GasOut.phase.enthalpy_mass # isentropic exit specific enthalpy
    Hout = GasIn.phase.enthalpy_mass + (Hisout - GasIn.phase.enthalpy_mass) / Etais
    GasOut.HP = Hout, Pout 
    PW = GasOut.H - GasIn.H
    return PW

def TurbineExpansion(GasIn: ct.Quantity, GasOut: ct.Quantity, PR, Etais):
    Pout = GasIn.P / PR 
    GasOut.SP = GasIn.entropy_mass, Pout
    final_enthalpy_is = GasOut.enthalpy_mass
    # eta_is = (initial_enthalpy - final_enthalpy) / (initial_enthalpy - final_enthalpy_is)
    final_enthalpy = GasIn.enthalpy_mass - (GasIn.enthalpy_mass - final_enthalpy_is) * Etais
    GasOut.HP = final_enthalpy, Pout 
    PW = GasIn.H - GasOut.H
    return PW