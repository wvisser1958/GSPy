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

import numpy as np
import cantera as ct
from gspy.core.duct import TDuct
from scipy.optimize import brentq
# from scipy.optimize import toms748

MW_H2O = 18.01528   # kg/kmol
T_TRIPLE = 273.16  # K
T_CRIT = 647.096  # K

# Wilfried Visser, 1 October2026
# water injection is modeled as a liquid phase that is injected into the gas flow.
# one can use the water injection to cool the gas flow by evaporative cooling. The maximum amount of water that can 
# evaporate is limited by the saturation pressure of water at the given gas temperature.
# only the portion of the injected water that can evaporate at the given gas temperature is added to the gas flow. 
# The rest of the water is discarded from the model.
# the discarded water can be saved to use in a customized water injection model that can handle the excess water, 
# e.g. at the end of the compressor for further evaporation or to be collected in a water tank. The discarded water mass is available in the output dictionary as "W_liq_discard_<component name>".

# In future GSPy version 3.0, liquid water is added to the fluid model as a separate phase and kept in the gas path for further modeling like evaporation downstream the compressor for example or during  compression

class TWaterInjector(TDuct):
    def __init__(self, owner, name, MapFileName, ControlComponent, station_in, station_out, PRdes,
                 *,
                 gas_out_output_species = None,
                 w_water_injection_des = 0.0,
                 percent_water_injection_des = 0.0,
                 T_water_injection_des = 300.0
                 ):
        super().__init__(owner,     name, MapFileName, ControlComponent, station_in, station_out, PRdes, gas_out_output_species = gas_out_output_species)
        if percent_water_injection_des != 0.0 and w_water_injection_des != 0.0:
            raise ValueError("Either percent_water_injection_des and/or w_water_injection_des must be nonzero")
        self.w_water_injection_des = w_water_injection_des
        self.percent_water_injection_des = percent_water_injection_des
        self.T_water_injection_des = T_water_injection_des
        self.w_water_injection = w_water_injection_des
        self.percent_water_injection = percent_water_injection_des
        self.T_water_injection = T_water_injection_des
        self.m_evap = 0.0
        self.m_discard = 0.0

    def Run(self, Mode, PointTime):
        if self.percent_water_injection_des != 0.0 and self.w_water_injection_des != 0.0:
            raise ValueError("Either percent_water_injection_des and/or w_water_injection_des must be nonzero")
            
        self.gas_out = super().Run(Mode, PointTime)
        if self.percent_water_injection > 0.0:
            self.w_water_injection = self.percent_water_injection/100.0 * self.gas_out.mass
        if self.w_water_injection > 0.0:
            self.percent_water_injection = 100.0 * self.w_water_injection / self.gas_out.mass
            self.gas_out = self.add_liquid_water_equilibrium(self.gas_out, self.w_water_injection, self.T_water_injection)

        return self.gas_out

    def add_liquid_water_equilibrium(self, gas_q, m_water, T_water):
        """
        Inject liquid water into a Cantera gas Quantity and evaporate
        as much water as possible while maintaining vapor equilibrium.

        Only the part of the injected water that evaporates is added
        to the gas Quantity. Any excess liquid water, including its
        enthalpy, is ignored.

        Parameters
        ----------
        gas_q : ct.Quantity
            Existing gas quantity. The gas mechanism must contain H2O.

        m_water : float
            Requested injected liquid-water mass [kg].

        T_water : float
            Temperature of the injected liquid water [K].

        Returns
        -------
        gas_q : ct.Quantity
            Modified gas quantity. Its mass increases only by the
            amount of injected water that actually evaporates.

        Notes
        -----
        The calculation assumes:
        - constant pressure;
        - adiabatic mixing/evaporation;
        - existing H2O in gas_q is vapor;
        - injected water enters as liquid;
        - excess liquid water is discarded from the model;
        - no ice phase is modeled.

        If the requested water injection exceeds the amount that can
        evaporate, a warning is printed.
        """

        if m_water <= 0.0:
            return gas_q

        gas = gas_q.phase

        # ----------------------------------------------------------
        # Save original gas state BEFORE helper functions modify
        # the underlying Cantera phase.
        # ----------------------------------------------------------

        P       = gas_q.P
        T_gas0  = gas_q.T
        m_gas0  = gas_q.mass
        Y0      = gas_q.Y.copy()
        H_gas0  = m_gas0 * gas_q.enthalpy_mass

        iH2O = gas.species_index("H2O")

        # Original species masses
        m_species0 = m_gas0 * Y0

        # Existing H2O vapor
        m_H2O_0 = m_species0[iH2O]

        # Dry species masses remain unchanged
        m_species_dry = m_species0.copy()
        m_species_dry[iH2O] = 0.0

        # Maximum possible H2O vapor mass if ALL injected water
        # were to evaporate
        m_H2O_max = m_H2O_0 + m_water

        # ----------------------------------------------------------
        # Number of kmol of dry gas
        #
        # Cantera molecular_weights: kg/kmol
        # ----------------------------------------------------------

        n_dry = 0.0

        for k in range(gas.n_species):
            if k != iH2O:
                n_dry += (
                    m_species_dry[k]
                    / gas.molecular_weights[k]
                )

        # ----------------------------------------------------------
        # Cantera liquid-water phase
        # ----------------------------------------------------------

        water = ct.Water()

        # ----------------------------------------------------------
        # Liquid-water enthalpy on the SAME reference basis as the
        # H2O species in the GSPy gas mechanism.
        #
        # ct.Water() is used only to obtain:
        #
        #       h_liquid - h_vapor
        #
        # so its absolute enthalpy reference cancels.
        # ----------------------------------------------------------

        def h_liq(T):

            T_w = max(T, T_TRIPLE)

            if T_w >= T_CRIT:
                raise ValueError(
                    f"Liquid water temperature {T:.2f} K is at or above "
                    f"the critical temperature ({T_CRIT:.3f} K)."
                )

            gas.TPY = T_w, P, {"H2O": 1.0}
            h_vap_gasref = gas.enthalpy_mass

            water.TQ = T_w, 0.0
            h_l = water.enthalpy_mass

            water.TQ = T_w, 1.0
            h_v = water.enthalpy_mass

            return h_vap_gasref + (h_l - h_v)
        
        # Enthalpy per kg of injected liquid water.
        #
        # Only the portion that actually evaporates will contribute
        # this enthalpy to the modeled gas flow.
        h_water_in = h_liq(T_water)

        # ----------------------------------------------------------
        # Maximum total H2O vapor mass allowed by saturation at T.
        #
        # This includes the H2O already present in the inlet gas.
        # ----------------------------------------------------------

        def vapor_mass_at_saturation(T):

            # Below triple point: use triple-point saturation condition
            T_w = max(T, T_TRIPLE)

            # Above critical temperature there is no liquid/vapor
            # equilibrium limitation: all available water can be vapor.
            if T_w >= T_CRIT:
                return m_H2O_max

            water.TQ = T_w, 0.0
            Psat = water.P

            # If saturation pressure exceeds the gas pressure,
            # all available water can exist as vapor.
            if Psat >= P:
                return m_H2O_max

            Xw = Psat / P

            n_w = Xw / (1.0 - Xw) * n_dry
            m_vap = n_w * MW_H2O

            return min(m_vap, m_H2O_max)

        # ----------------------------------------------------------
        # Determine how much of the INJECTED water can evaporate
        # at a given temperature.
        # ----------------------------------------------------------

        def evaporated_water_mass(T):

            m_H2O_sat = vapor_mass_at_saturation(T)

            # Existing inlet H2O is already vapor.
            # Only additional capacity is available for injected water.
            m_evap = m_H2O_sat - m_H2O_0

            m_evap = max(0.0, m_evap)
            m_evap = min(m_water, m_evap)

            return m_evap

        # ----------------------------------------------------------
        # Energy residual
        #
        # IMPORTANT:
        #
        # Only the injected water that actually evaporates enters
        # the modeled flow and contributes its inlet enthalpy.
        #
        # Excess liquid mass AND its enthalpy are discarded.
        # ----------------------------------------------------------

        def residual(T):

            m_evap = evaporated_water_mass(T)

            # Final H2O vapor consists of:
            #
            #   original vapor + evaporated injected water
            #
            m_H2O_vap = m_H2O_0 + m_evap

            # Construct gas species masses
            m_species = m_species_dry.copy()
            m_species[iH2O] = m_H2O_vap

            m_gas = m_species.sum()

            Y = m_species / m_gas

            # Final gas enthalpy
            gas.TPY = T, P, Y
            H_gas = m_gas * gas.enthalpy_mass

            # Target enthalpy:
            #
            # initial gas
            # +
            # inlet enthalpy of ONLY the water that evaporates
            #
            H_target = (
                H_gas0
                + m_evap * h_water_in
            )

            return H_gas - H_target

        # ----------------------------------------------------------
        # Solve final gas temperature
        #
        # We don't solve below the triple point because ice is not
        # represented in this simplified model.
        # ----------------------------------------------------------

        T_low = T_TRIPLE

        T_high = max(
            T_gas0,
            T_water,
            T_TRIPLE
        ) + 1000.0

        f_low  = residual(T_low)
        f_high = residual(T_high)

        # Expand upper bracket if necessary
        while f_low * f_high > 0.0:

            T_high += 1000.0
            f_high = residual(T_high)

            if T_high > 5000.0:
                raise RuntimeError(
                    "Could not bracket water-injection equilibrium "
                    "temperature."
                )

        T_final = brentq(
            residual,
            T_low,
            T_high,
            xtol=1.0e-8
        )

        # ----------------------------------------------------------
        # Final amount of injected water that actually evaporated
        # ----------------------------------------------------------

        self.m_evap = evaporated_water_mass(T_final)

        self.m_discard = max(
            0.0,
            m_water - self.m_evap
        )

        m_H2O_vap = m_H2O_0 + self.m_evap

        # ----------------------------------------------------------
        # Construct final gas Quantity
        #
        # ONLY evaporated water is added to gas_q.mass.
        # ----------------------------------------------------------

        m_species = m_species_dry.copy()
        m_species[iH2O] = m_H2O_vap

        m_gas = m_species.sum()
        Y_final = m_species / m_gas

        gas_q.mass = m_gas
        gas_q.TPY = T_final, P, Y_final

        # ----------------------------------------------------------
        # Warn if requested injection exceeds evaporation capacity.
        #
        # This is deliberately only a warning: requesting excessive
        # water is allowed and can be used to obtain the maximum
        # possible evaporative cooling.
        # ----------------------------------------------------------

        # if m_discard > 1.0e-9:

        #     print(
        #         f"Warning: {m_discard:.6g} kg of the requested "
        #         f"{m_water:.6g} kg water injection could not be "
        #         f"evaporated and is ignored. "
        #         f"Only {m_evap:.6g} kg was added to the gas."
        #     )

        return gas_q

    def PrintPerformance(self, Mode, PointTime):
        super().PrintPerformance(Mode, PointTime)
        print(f"\tPercent water injection   : {self.percent_water_injection:.2f} %")
        print(f"\tWater injection flow      : {self.w_water_injection:.4f} kg/s")
        if self.m_discard > 1.0e-9:
            print(
                f"Warning: {self.m_discard:.6g} kg of the requested "
                f"{self.w_water_injection:.4f} kg water injection could not be "
                f"evaporated and is ignored. "
                f"Only {self.m_evap:.6g} kg was added to the gas."
            )

    # 2.0.0.0
    def get_outputs(self):
        out = super().get_outputs()
        out["Perc_water_"+self.name] = self.percent_water_injection
        out["W_water_"+self.name] = self.w_water_injection
        out["W_vapor_"+self.name] = self.m_evap
        out["W_liq_discard_"+self.name] = self.m_discard
        return out