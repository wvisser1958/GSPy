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
from gspy.core.gaspath import TGaspath

class TDuct(TGaspath):
    def __init__(self, 
                 *,
                 PRdes,
                 Qdes = None,
                 **kwargs):   
        super().__init__(**kwargs)
        self.PRdes = PRdes
        # 2.1
        self.Qdes = Qdes
        self.Q = Qdes

    def Run(self, Mode, PointTime):
        super().Run(Mode, PointTime)
        # v1.2 dprel proportional to Wc^2
        # dprel = (1 - self.PRdes) * np.square(self.Wc/self.Wcdes)
        
        # assume PRloss is determined by flowstate after inlet side heat transfer from heatpath, so
        dprel = (1 - self.PRdes) * np.square(self.fs_in_q.Wc/self.fs_in_des_q.Wc)
        self.PR = 1 - dprel        
        # 2.1
        p_out = self.fs_in_q.P*self.PR
        # user specified Q
        if self.Q is None:
            self.fs_out.TP = self.fs_in_q.T, p_out
        else:
            self.fs_out.HP = (self.fs_in_q.H + self.Q) / self.fs_in_q.mass, p_out

        # now add Q heatpath
        self.Add_Q_to_fs_out()
        
        return self.fs_out
    
    def get_outputs(self):
        out = super().get_outputs()
        if self.Q is not None:
            out[f"Q{self.id}"] = self.Q / 1000  # kW
        return out