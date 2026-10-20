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
    def __init__(self, 
                 *,
                 w_water_injection_des = 0.0,
                 percent_water_injection_des = 0.0,
                 T_water_injection_des = 300.0,
                 **kwargs
                 ):
        super().__init__(**kwargs)
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
            
        self.fs_out = super().Run(Mode, PointTime)
        #  override disabling of liquid water model in TDuct.Run() to keep the liquid water model enabled for further downstream modeling
        self.fs_out.enable_liquid_water = self.enable_liquid_water
        if self.percent_water_injection > 0.0:
            self.w_water_injection = self.percent_water_injection/100.0 * self.fs_out.W
        if self.w_water_injection > 0.0:
            self.percent_water_injection = 100.0 * self.w_water_injection / self.fs_out.W
            # self.gas_out = self.add_liquid_water_equilibrium(self.gas_out, self.w_water_injection, self.T_water_injection)
            self.fs_out.add_liquid_water(self.w_water_injection, self.T_water_injection)

        return self.fs_out

    # def add_liquid_water_equilibrium(self, flow_state, m_water, T_water):
    #     """
    #     Add liquid water to a TFlowState and establish vapor/liquid
    #     equilibrium at constant pressure and total enthalpy.

    #     Unlike the old gas_q-only implementation, any water that
    #     cannot evaporate is retained in flow_state.m_liq.

    #     Parameters
    #     ----------
    #     flow_state : TFlowState
    #         Existing flow state.

    #     m_water : float
    #         Liquid water mass to add [kg].

    #     T_water : float
    #         Temperature of added liquid water [K].
    #     """

    #     if m_water <= 0.0:
    #         return flow_state

    #     P = flow_state.P

    #     # ----------------------------------------------------------
    #     # Initial state
    #     # ----------------------------------------------------------

    #     H_initial = flow_state.H_total
    #     m_water_initial = flow_state.m_total_water

    #     # ----------------------------------------------------------
    #     # Enthalpy of added liquid water
    #     #
    #     # Use the TFlowState liquid-water enthalpy function here.
    #     # This must use the same enthalpy reference as gas-phase H2O.
    #     # ----------------------------------------------------------

    #     h_water = flow_state.h_liq(T_water)

    #     # ----------------------------------------------------------
    #     # Add water mass and its enthalpy
    #     # ----------------------------------------------------------

    #     flow_state.m_total_water = (
    #         m_water_initial + m_water
    #     )

    #     H_new = H_initial + m_water * h_water

    #     # ----------------------------------------------------------
    #     # Reflash at constant total enthalpy and pressure.
    #     #
    #     # update_HP() determines:
    #     #
    #     #   T
    #     #   m_vap
    #     #   m_liq
    #     #   gas composition
    #     #
    #     # while satisfying vapor/liquid equilibrium.
    #     # ----------------------------------------------------------

    #     flow_state.update_HP(H_new, P)

    #     return flow_state

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