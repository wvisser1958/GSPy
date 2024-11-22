class TFuel:
    def __init__(self, name):    # Constructor of the class
        self.name = name

    def Combustion(self, Wfdes, Texitdes, PRdes, Etades):
        self.Wfdes = Wfdes
        self.Texitdes = Texitdes
        self.PRdes = PRdes
        self.Etades = Etades


import cantera as ct
import f_utils as fu

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
air_composition_moles = ''
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


# Given parameters for the virtual fuel
LHV_kJ_kg = 43031  # Lower Heating Value in kJ/kg
average_molar_mass_fuel = 167.31102  # Average molar mass in g/mol
HC_ratio = 1.9167  # H/C ratio for the virtual fuel
CHyOzMoleMass = C_atom_weight + H_atom_weight * HC_ratio # virtual fuel molecule with singe C atom
T_standard_ref = 298.15  # Standard temperature (25°C)
P_standard_ref = ct.one_atm  # Standard pressure (1 atm)
w_fuel = 0.38
w_air = 19.9
T_fuel = 288.15

gas.TPY = T_standard_ref, P_standard_ref, s_air_composition_mass
h_air_ref = gas.enthalpy_mass

# combustor inlet conditions
T_initial = 542.32
P_initial = 7.01169

gas.TPY = T_initial, P_initial, s_air_composition_mass
h_air_initial = gas.enthalpy_mass

# Convert LHV from kJ/kg to J/mol
LHV_J_mol = LHV_kJ_kg * 1000 * (average_molar_mass_fuel / 1000)

# calculate compostion of combustion products mixed with excess air
O2_exit_mass = w_air * air_O2_fraction_mass - w_fuel/CHyOzMoleMass * (1+HC_ratio/4) * O2_molar_mass 
CO2_exit_mass = CO2_molar_mass * w_fuel/CHyOzMoleMass + w_air*air_CO2_fraction_mass   
H2O_exit_mass = H2O_molar_mass * w_fuel/CHyOzMoleMass * HC_ratio/2
Ar_exit_mass = w_air * air_Ar_fraction_mass
N2_exit_mass = w_air * air_N2_fraction_mass

product_composition_mass = f'O2:{O2_exit_mass}, CO2:{CO2_exit_mass}, H2O:{H2O_exit_mass}, AR:{Ar_exit_mass}, N2:{N2_exit_mass}'
gas.TPY = T_standard_ref, P_standard_ref, product_composition_mass

h_prod_ref = gas.enthalpy_mass # get H in J/kg

# now, from the equation (conservation of energy "in = out"):
# w_fuel * LHV_kJ_kg*1000 + w_air * (h_air_initial - h_air_ref)  =   (w_air + w_fuel) * (h_prod_final - h_prod_ref)
h_prod_final = (w_fuel * LHV_kJ_kg * 1000 + w_air * (h_air_initial-h_air_ref)) / (w_air + w_fuel) + h_prod_ref

gas.HP = h_prod_final, P_initial

combustion_end_temperature = gas.T

print(f"Combustion End Temperature: {combustion_end_temperature:.2f} K")


    
    def Run(self, Mode):  
        if Mode == 'DP':
            pass
        else:
            pass