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

import math
import numpy as np
import cantera as ct
import pandas as pd

# Create a gas object for air and products using the standardr gri30.yaml,
# or another suitable mechanism
# gas = ct.Solution('gri30.yaml')
# We are using jetsurf.yaml instead, which has kerosine subsitute
# species like PXC12H25, for user specified fuel composition
gas = ct.Solution('data/fluid_props/jetsurf.yaml')

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

# 1.4
output_path = None

h_air_ref = None
def InitializeGas():
    gas.TPY = T_standard_ref, P_standard_ref, s_air_composition_mass
    global h_air_ref
    h_air_ref = gas.enthalpy_mass

def GetRotorspeedCorrectionFactor(gas: ct.Quantity):
    return math.sqrt(gas.T/T_std)
def GetFlowCorrectionFactor(gas: ct.Quantity):
    return math.sqrt(gas.T/T_std) / (gas.P/P_std)
