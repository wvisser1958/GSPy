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

import cantera as ct

# constants
# Define the air composition species, mass fraction, mole fraction, molefraction normalized to O2
Air_composition = [
    ('CO2', 0.00048469, 0.000412, 0.0020 ),
    ('O2',  0.2314151,  0.20946,  1.0000 ),
    ('AR',  0.0129159,  0.00934,  0.0446),  # 2.0.0.1 changed from Ar to AR (compliant to Cantera)
    ('N2',  0.75518431, 0.78084,  3.7279)
]
# mole composition
s_air_composition_mole = {sp: x for sp, _, x, _ in Air_composition}
# mass composition
s_air_composition_mass = {sp: y for sp, y, _, _ in Air_composition}

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
AR_tuple = next(item for item in Air_composition if item[0] == 'AR')
N2_tuple = next(item for item in Air_composition if item[0] == 'N2')

air_O2_fraction_mass = O2_tuple[1]
air_O2_fraction_moles = O2_tuple[2]
air_CO2_fraction_mass = CO2_tuple[1]
air_Ar_fraction_mass = AR_tuple[1]
air_N2_fraction_mass = N2_tuple[1]

# standard atmosphere sea level conditions
T_std = 288.15
P_std = 101325

# Standard temperature for chemical gas model calculations
T_standard_ref = 298.15 # (25°C)
P_standard_ref = ct.one_atm  # (1 atm)