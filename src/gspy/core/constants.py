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
# ----------------------------------------------------------------------
# Standard dry-air mole composition
#
# Columns:
#   mole fraction
# ----------------------------------------------------------------------
air_composition_moles_array = [
    ("CO2", 0.000412),
    ("O2",  0.209460),
    ("AR",  0.009340),
    ("N2",  0.7808409)]

# def _normalize(comp: dict[str, float]) -> dict[str, float]:
#     """Return a normalized copy of a composition dictionary."""
#     total = sum(comp.values())
#     return {sp: val / total for sp, val in comp.items()}

# # Mole fractions from the Air_composition table
# air_composition_moles = _normalize({
#     sp: x
#     for sp, y, x, xo2 in air_composition_moles_array
# })

# # Standard dry-air mass fractions
# air_composition_mass = _normalize({
#     sp: y
#     for sp, y, x, xo2 in Air_composition
# })

# # Standard dry-air mole fractions
# air_composition_moles = _normalize({
#     sp: x
#     for sp, y, x, xo2 in Air_composition
# })

# # Standard dry-air O2-normalized mole ratios
# air_composition_O2ratio = {
#     sp: xo2
#     for sp, y, x, xo2 in Air_composition
# }

# s_air_composition_moles = '' 
# s_air_composition_mass = '' 

# for species, massfraction, molefraction, O2_norm_molefraction in Air_composition:
#     # m_total = m_total + massfraction            should be 1.0 !
#     if s_air_composition_mass != '' :
#         s_air_composition_mass = s_air_composition_mass + ', '
#     s_air_composition_mass = s_air_composition_mass + species + ':' + str(massfraction)
#     if s_air_composition_moles != '' :
#         s_air_composition_moles = s_air_composition_moles + ', '
#     s_air_composition_moles = s_air_composition_moles + species + ':' + str(molefraction)

# # Accessing the tuple for 'O2' (finding the tuple by its first element)
# O2_tuple = next(item for item in Air_composition if item[0] == 'O2')
# CO2_tuple = next(item for item in Air_composition if item[0] == 'CO2')
# AR_tuple = next(item for item in Air_composition if item[0] == 'AR')
# N2_tuple = next(item for item in Air_composition if item[0] == 'N2')

# air_O2_fraction_mass = O2_tuple[1]
# air_O2_fraction_moles = O2_tuple[2]
# air_CO2_fraction_mass = CO2_tuple[1]
# air_Ar_fraction_mass = AR_tuple[1]
# air_N2_fraction_mass = N2_tuple[1]

LIQUID_WATER_INDEX = -1

# standard atmosphere sea level conditions
T_std = 288.15
P_std = 101325

# Standard temperature for chemical gas model calculations and for fuel LHV
T_standard_ref = 298.15 # (25°C)
P_standard_ref = ct.one_atm  # (1 atm)

T_WATER_TRIPLE = 273.16
T_WATER_CRITICAL = 647.096
MW_H2O = 18.01528e-3

C_StefanBoltzmann = 5.67e-8; # [W/m2/K4]

w = ct.Water()
w.TQ = T_standard_ref, 0.0          # saturated liquid water at Tref
h_liq_ref = w.enthalpy_mass