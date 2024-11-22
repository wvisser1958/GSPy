import math 
import numpy as np
import cantera as ct

# Create a gas object for air and products using gri30.yaml (or another suitable mechanism)
gas = ct.Solution('gri30.yaml')

C_atom_weight = gas.atomic_weight(gas.element_index('C'))
O_atom_weight = gas.atomic_weight(gas.element_index('O'))
H_atom_weight = gas.atomic_weight(gas.element_index('H'))

O2_molar_mass = gas.molecular_weights[gas.species_index('O2')]
CO2_molar_mass = gas.molecular_weights[gas.species_index('CO2')]
H2O_molar_mass = gas.molecular_weights[gas.species_index('H2O')]

# Define the air composition species, mass fraction, mole fraction, molefraction normalized to O2
Air_composition = [
    ('CO2', 0.00048469, 0.000412, 0.0020 ),
    ('O2',  0.2314151,  0.20946,  1.0000 ),
    ('Ar',  0.0129159,  0.00934,  0.0446),
    ('N2',  0.75518431, 0.78084,  3.7279)
]
s_air_composition_mass = ''
# air_composition_moles = ''
for species, massfraction, molefraction, O2_norm_molefraction in Air_composition:
    # m_total = m_total + massfraction            should be 1.0 !
    if s_air_composition_mass != '' :
        s_air_composition_mass = s_air_composition_mass + ', '
    s_air_composition_mass = s_air_composition_mass + species + ':' + str(massfraction)    
    # if air_composition_moles != '' :
    #     air_composition_moles = air_composition_moles + ', '
    # air_composition_moles = air_composition_moles + species + ':' + str(O2_norm_molefraction)    
# Accessing the tuple for 'O2' (finding the tuple by its first element)
O2_tuple = next(item for item in Air_composition if item[0] == 'O2')
CO2_tuple = next(item for item in Air_composition if item[0] == 'CO2')
Ar_tuple = next(item for item in Air_composition if item[0] == 'Ar')
N2_tuple = next(item for item in Air_composition if item[0] == 'N2')

air_O2_fraction_mass = O2_tuple[1]
air_O2_fraction_moles = O2_tuple[2]
air_CO2_fraction_mass = CO2_tuple[1]
air_Ar_fraction_mass = Ar_tuple[1]
air_N2_fraction_mass = N2_tuple[1]

# standard atmosphere sea level conditions
T_std = 288.15
P_std = 101325 

# Standard temperature for chemical gas model calculations
T_standard_ref = 298.15 # (25°C)
P_standard_ref = ct.one_atm  # (1 atm)

h_air_ref = None
def InitializeGas(gas):
    gas.TPY = T_standard_ref, P_standard_ref, s_air_composition_mass
    global h_air_ref
    h_air_ref = gas.enthalpy_mass

shaft_list = []

states = np.array([], dtype=float)
errors = np.array([], dtype=float)

RD = None
FN = None 

def find_shaft_by_number(ShaftNr):
    for shaft in shaft_list:
        if shaft.ShaftNr == ShaftNr:
            return shaft
    return None  # Return None if no matching object is found

def reinit_all_shafts():
    for shaft in shaft_list:
        shaft.PW_sum = 0
    return None  # Return None if no matching object is found

def GetRotorspeedCorrectionFactor(gas: ct.Quantity):
    return math.sqrt(gas.T/T_std)
def GetFlowCorrectionFactor(gas: ct.Quantity):
    return math.sqrt(gas.T/T_std) / (gas.P/P_std)

def converged():
    for error in errors:
        if error > 0.001:
            return False
    return True

def jacobian(x, residuals_func, epsilon=1e-3):
    n = x.size
    J = np.zeros((n, n))
    f_x = residuals_func(x)
    
    for i in range(n):
        x_perturbed = x.copy()
        x_perturbed[i] -= epsilon
        f_x_perturbed = residuals_func(x_perturbed)
        J[:, i] = (f_x_perturbed - f_x) / epsilon  # Finite difference approximation
        
    return J

def newton_raphson(x0, residuals_func, tol=1e-5, max_iter=100):
    x = x0
    for iteration in range(max_iter):
        f_x = residuals_func(x)
        if np.linalg.norm(f_x) < tol:
            print(f"Converged after {iteration} iterations")
            return x  # Solution found

        J = jacobian(x, residuals_func)
        try:
            delta_x = np.linalg.solve(J, -f_x)
        except np.linalg.LinAlgError:
            print("Jacobian is singular; Newton-Raphson cannot proceed.")
            return None

        x = x + delta_x

    print("Newton-Raphson did not converge within the maximum number of iterations.")
    return None

def PrintPerformance(Mode):
    print(f"System performance")
    print(f"\tNet thrust: {FN:.2f} N")