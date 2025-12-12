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
from gspy.core.gaspath import TGaspath
import gspy.core.sys_global as fg
import gspy.core.system as fsys

class TCoolingFlow(TGaspath):
    def __init__(self, name, MapFileName, ControlComponent, stationin, stationout,
                 coolingflownumber, frombleednumber, fractiontakendes,
                 dPfraction, W_tur_eff_fraction, Rexit) :    # Constructor of the class
        super().__init__(name, MapFileName, ControlComponent, stationin, stationout)
        self.coolingflownumber = coolingflownumber
        self.frombleednumber = frombleednumber
        self.fractiontakendes = fractiontakendes
        self.fractiontaken = self.fractiontakendes
        self.dPfraction = dPfraction
        self.W_tur_eff_fraction = W_tur_eff_fraction
        self.Rexit = Rexit  # "pumping radius" / radius at point 'where cooling glow exits rotor blade cooling flow hole'
        self.GasInjected = None
        self.PWexp = None
        self.PWpump = None

    def Run(self, Mode, PointTime):
        super().Run(Mode, PointTime)
        if Mode == 'DP':
            self.fractiontaken = self.fractiontakendes
            # quantity of gas after injection
            self.GasInjected = ct.Quantity(self.GasIn.phase, mass = self.GasIn.mass*self.fractiontaken)
            self.GasOut = ct.Quantity(self.GasInjected.phase, mass = self.GasInjected.mass)
        else:
            #  at this state, fraction taken still constant
            self.fractiontaken = self.fractiontakendes
            self.GasInjected.mass = self.GasIn.mass * self.fractiontaken
            self.GasInjected.TPY = self.GasIn.TPY
        self.GasOut.mass = self.GasInjected.mass
        self.W = self.GasOut.mass
        return self.GasOut

    def PrintPerformance(self, Mode, PointTime):
        super().PrintPerformance(Mode, PointTime)
        print(f"\tFraction from bleed nr {self.frombleednumber}: {self.fractiontaken:.2f}")
        print(f"\tInject conditions:")
        print(f"\t\tTemperature : {self.GasInjected.T:.1f} K")
        print(f"\t\tPressure    : {self.GasInjected.P:.0f} Pa")
        if self.PWpump != None:
            print(f"\t\tPW rad pump : {self.PWpump:.0f} kW")
        if self.PWexp != None:
            print(f"\t\tPW expansion: {self.PWexp:.1f} kW")

    #  1.1 WV
    def AddOutputToDict(self, Mode):
        super().AddOutputToDict(Mode)
        fsys.output_dict[f"Fraction from bleed nr {self.frombleednumber}"]  = self.fractiontaken
        fsys.output_dict[f"T{self.stationin}j"]  = self.GasInjected.T
        fsys.output_dict[f"P{self.stationin}j"]  = self.GasInjected.P
        if self.PWpump != None:
            fsys.output_dict[f"PWpump{self.stationout}"]  = self.PWpump
        if self.PWexp != None:
            fsys.output_dict[f"PWexp{self.stationout}"]  = self.PWexp


