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

class TCoolingFlow(TGaspath):
    def __init__(self, owner, name, map_filename, control_component, station_in, station_out,
                 coolingflownumber, frombleednumber, fractiontakendes,
                 dPfraction, W_tur_eff_fraction, Rexit) :    # Constructor of the class
        super().__init__(owner, name, map_filename, control_component, station_in, station_out)
        self.coolingflownumber = coolingflownumber
        self.frombleednumber = frombleednumber
        self.fractiontakendes = fractiontakendes
        self.fractiontaken = self.fractiontakendes
        self.dPfraction = dPfraction
        self.W_tur_eff_fraction = W_tur_eff_fraction
        self.Rexit = Rexit  # "pumping radius" / radius at point 'where cooling glow exits rotor blade cooling flow hole'
        self.gas_injected = None
        self.DHWexp = None
        self.DHWpump = None

    def Run(self, Mode, PointTime):
        super().Run(Mode, PointTime)
        if Mode == 'DP':
            self.fractiontaken = self.fractiontakendes
            # quantity of gas after injection
            self.gas_injected = ct.Quantity(self.gas_in.phase, mass = self.gas_in.mass*self.fractiontaken)
            self.gas_out = ct.Quantity(self.gas_injected.phase, mass = self.gas_injected.mass)
        else:
            #  at this state, fraction taken still constant
            self.fractiontaken = self.fractiontakendes
            self.gas_injected.mass = self.gas_in.mass * self.fractiontaken
            self.gas_injected.TPY = self.gas_in.TPY
        self.gas_out.mass = self.gas_injected.mass
        self.W = self.gas_out.mass
        return self.gas_out

    def PrintPerformance(self, Mode, PointTime):
        super().PrintPerformance(Mode, PointTime)
        print(f"\tFraction from bleed nr {self.frombleednumber}: {self.fractiontaken:.2f}")
        print(f"\tInject conditions:")
        print(f"\t\tTemperature : {self.gas_injected.T:.1f} K")
        print(f"\t\tPressure    : {self.gas_injected.P:.0f} Pa")
        #  1.6 WV
        print(f"\tExit conditions:")
        print(f"\t\tMass flow : {self.gas_out.mass:.1f} [kg/s]")
        print(f"\t\tTemperature : {self.gas_out.T:.1f} K")
        print(f"\t\tPressure    : {self.gas_out.P:.0f} Pa")

        if self.DHWpump != None:
            print(f"\t\tDHW rad pump : {self.DHWpump:.0f} kW")
        if self.DHWexp != None:
            print(f"\t\tDHW expansion: {self.DHWexp:.1f} kW")

    # #  1.1 WV
    # def AddOutputToDict(self, Mode):
    #     super().AddOutputToDict(Mode)
    #     fsys.output_dict[f"Fraction from bleed nr {self.frombleednumber}"]  = self.fractiontaken
    #     fsys.output_dict[f"T{self.station_in}j"]  = self.gas_injected.T
    #     fsys.output_dict[f"P{self.station_in}j"]  = self.gas_injected.P
    #     #  1.6 WV
    #     fsys.output_dict[f"W{self.station_out}"]  = self.gas_out.mass
    #     fsys.output_dict[f"T{self.station_out}"]  = self.gas_out.T
    #     fsys.output_dict[f"P{self.station_out}"]  = self.gas_out.P

    #     if self.DHWpump != None:
    #         fsys.output_dict[f"DHWpump{self.station_out}"]  = self.DHWpump
    #     if self.DHWexp != None:
    #         fsys.output_dict[f"DHWexp{self.station_out}"]  = self.DHWexp

    # 2.0.0.0
    def get_outputs(self):
        out = super().get_outputs()

        out[f"Fraction from bleed nr {self.frombleednumber}"]  = self.fractiontaken
        out[f"T{self.station_in}j"]  = self.gas_injected.T
        out[f"P{self.station_in}j"]  = self.gas_injected.P
        #  1.6 WV
        out[f"W{self.station_out}"]  = self.gas_out.mass
        out[f"T{self.station_out}"]  = self.gas_out.T
        out[f"P{self.station_out}"]  = self.gas_out.P

        if self.DHWpump != None:
            out[f"DHWpump{self.station_out}"]  = self.DHWpump
        if self.DHWexp != None:
            out[f"DHWexp{self.station_out}"]  = self.DHWexp

        return out