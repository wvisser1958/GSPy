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
from math import pi

# precalc sqr(2*Pi/60) for TShaf.PWaccel
sqr2Pi_60 = (2*pi/60) ** 2

class TShaft:
    def __init__(self, owner, shaft_id, name, Ntdes, I):  # Constructor of the class
        self.owner = owner
        self.shaft_id = shaft_id
        self.name = name
        self.I = I # moment of inertia [kg.m2]
        self.Ivariable = 0 # variable moment of inertia [kg.m2]

        self.PW_sum = 0
        # 1.5
        self.istate = None

        # 2.1
        self.Ntdes = Ntdes
        self.Nt = None
        self.Ntprev = None
        self.Ntprev2 = None
        self.Ndot = None

    # 2.1
    def Run(self, Mode, PointTime):
        if Mode == 'DP':
            self.Nt = self.Ntdes
        else:
            self.Nt = self.owner.states[self.istate] * self.Ntdes

    def PWaccel(self, dt):
        self.Ndot = (self.Nt - self.Ntprev)/dt
        return sqr2Pi_60*(self.I + self.Ivariable) * self.Nt * self.Ndot

    # 2.1
    def set_steady_state(self):
        self.Ntprev = self.Nt
        self.Ndot = 0

    # 2.1
    def step_time(self, dt):
        self.Ntprev2 = self.Ntprev
        self.Ntprev = self.Nt

    # 2.1
    def step_back_time(self):
        self.Nt = self.Ntprev
        self.Ntprev = self.Ntprev2
