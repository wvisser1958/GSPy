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
from gspy.core.base_component import TComponent
import gspy.core.utils as fu

class THeatsink(TComponent):

    def __init__(self, 
                 *,
                 mass,  # mass of the heatskink
                 cp,    # specific heat
                 T_trans_init = None,   # DP initial temperature for transient simulation
                 T_first_guess,         # DP iteration first guess temperature
                 Q_norm_factor,         # Q error normalization factor for iteration
                 connected_heatsinks = None,  # list of connected heatsinks and heat transfer coefficients for heatpaths between heatsinks
                 **kwargs): 
        super().__init__(**kwargs)
        self.mass = mass
        self.cp = cp    
        self.Q_balance = 0
        self.T_trans_init = T_trans_init
        self.T_first_guess = T_first_guess
        self.Q_norm_factor = Q_norm_factor 
        self.T = T_first_guess

    def PreRun(self, Mode, PointTime):
        if Mode == 'DP':
            self.Q_balance = 0
        elif Mode == 'OD':
            self.T = self.system.states[self.istate_T] * self.T_des

    def Run(self, Mode, PointTime):
        if Mode == 'DP':
            # define state and error for OD 
            self.system.states = np.append(self.system.states, 1)
            self.istate_T = self.system.states.size-1
            # error for equation fs_in.wc = wcmap
            self.system.errors = np.append(self.system.errors, 0)
            self.ierror_Q = self.system.errors.size-1
        if self.heatpaths:
            Qhs_out = self.CalculateHeatTransfer(None, fu.HeatTransferLocation.HEATSINK)
            self.Q_balance += Qhs_out
        return self.T
    
    def PostRun(self, Mode, PointTime):
        if Mode == 'DP':
            self.T_des = self.T            
        if Mode == 'OD':
            self.system.errors[self.ierror_Q] = self.Q_balance/self.Q_norm_factor
    
    def PrintPerformance(self, Mode, PointTime):
        super().PrintPerformance(Mode, PointTime)
        print(f"\t\tT        : {self.T:.1f} K")
        print(f"\t\tQ_balance: {self.Q_balance:.0f} W")

    def get_outputs(self):
        out = super().get_outputs()
        out[f"T{self.id}"] = self.T
        out[f"Q_balance{self.id}"] = self.Q_balance

        return out