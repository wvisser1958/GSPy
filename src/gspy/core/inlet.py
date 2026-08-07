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
# import gspy.core.sys_global as fg
import gspy.core.utils as fu
from gspy.core.gaspath import TGaspath
from gspy.core.flow_state import TFlowState

class TInlet(TGaspath):
    def __init__(self, 
                 *,
                 Wdes, 
                 PRdes,
                 **kwargs):  # Constructor of the class
        super().__init__(**kwargs)
        self.Wdes = Wdes
        self.PRdes = PRdes

    def Run(self, Mode, PointTime):
        if Mode == 'DP':
            # 2.1 separate TGasCondition for fs_in (do not share with ambient gaspath_condition)
            # old Get the ambient conditions for the inlet fs_in conditions
            # old self.owner.gaspath_conditions[self.station_in] = self.owner.gaspath_conditions[self.owner.ambient.station_nr]
            self.fs_in = TFlowState.create_empty(self.system.gas, station_nr=self.station_in)
            self.system.gaspath_conditions[self.station_in] = self.fs_in

        self.fs_in.copy_from(self.system.gaspath_conditions[self.system.ambient.station_nr], self.system.ambient.station_nr)

        if Mode == 'DP':
            # now scale all masses (liquid and gas) from 1 (i.e. the mass of TAmbient) to Wdes
            # self.owner.gaspath_conditions[self.station_in].mass = self.Wdes
            self.fs_in.scale_mass(self.Wdes)

        # super (TGasPath) Run sets fs_in, fs_in_des and fs_out to self.owner.gaspath_conditions[self.station_in]
        # and in DP mode sets fs_in_des to fs_in
        super().Run(Mode, PointTime)

        # self.fs_in.TP = self.fs_in.T, self.fs_in.P
        if Mode == 'DP':
            # obsolete
            # self.fs_in.mass = self.Wdes
            
            # Wcdes is the design corrected flow, which is used to scale the inlet flow in OD mode using self.owner.states[self.istate_wc]
            self.Wcdes = self.fs_in.W_gas * fu.GetFlowCorrectionFactor(self.fs_in)
            
            self.PR = self.PRdes
            # self.system.states = np.append(self.system.states, 1)
            # self.istate_wc = self.system.states.size-1   # add state for corrected inlet flow wc more stable... state staying closer to 1 at high altitude
            self.istate_wc = self.system.add_state(self.name + '_wc', 1.0)  # add state for corrected inlet flow wc more stable... state staying closer to 1 at high altitude
        else:
            self.Wc = self.system.states[self.istate_wc] * self.Wcdes
            if self.Wc < 0.001*self.Wcdes:
                self.Wc = 0.001*self.Wcdes

            # use TGaspathCondition mass setter to maintain m_liq while setting the gas phase (m_dry + m_vap)
            # note that
            # self.fs_in.W_gas = self.Wc / fu.GetFlowCorrectionFactor(self.fs_in)
            W_gas = self.Wc / fu.GetFlowCorrectionFactor(self.fs_in)
            # scale fs_in H2O etc. now proportionally to the new W_gas, while keeping the same mass fractions (X, Y) and m_liq
            self.fs_in.scale_mass(W_gas/self.fs_in.W_gas)

            # self.fs_out.TP = self.fs_in.T, self.fs_in.P * self.PRdes
            # this inlet has constant PR, no OD PR yet (use manual input in code here, or make PR, Ram recovery map)
            self.PR = self.PRdes

        # self.W = self.fs_in.W

        # self.fs_in.set_conditions_humidity(
        #     T=self.owner.ambient.Tsa,
        #     P=self.owner.ambient.Psa,
        #     humidity_mode=self.owner.ambient.humidity_mode,
        #     humidity_value=self.owner.ambient.humidity_value,
        #     dry_X_dict=dict(self.fs_in.X),
        #     dry_Y_dict=dict(self.fs_in.Y)
        # )

        self.fs_out.copy_from(self.fs_in, self.station_out)
        self.fs_out.TP = self.fs_in.T, self.fs_in.P * self.PR
        # self.fs_out.mass = self.fs_in.mass
        self.RD = self.fs_in.W_gas * self.system.ambient.V / 1000 # kN
        # add ram drag to system level ram drag (note that multiple inlets may exist)
        self.system.RD = self.system.RD + self.RD
        return self.fs_out