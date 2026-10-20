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
from gspy.core.flow_state import TFlowState

class TCoolingFlow(TGaspath):
    def __init__(self,
                 *,
                 coolingflownumber, frombleednumber, fractiontakendes,
                 dPfraction, W_tur_eff_fraction, Rexit,
                 **kwargs) :    # Constructor of the class
        super().__init__(**kwargs)
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
        self.fs_injected = TFlowState.create_empty(self.system.gas, 
                                                   station_nr=self.station_out, 
                                                   enable_liquid_water=False)
                
    def Run(self, Mode, PointTime):
        super().Run(Mode, PointTime)
        if Mode == 'DP':
            self.fractiontaken = self.fractiontakendes
            # quantity of gas after injection: is a fraction of fs_in so cannot be the same as fs_in which is the out of the 
            # bleed flow, which must keep its total bleed flow mass flow rate
            # self.gas_injected = ct.Quantity(self.fs_in.phase, mass = self.fs_in.mass*self.fractiontaken)
            # self.gas_out = ct.Quantity(self.gas_injected.phase, mass = self.gas_injected.mass)
        # else:
            #  at this state, fraction taken still constant
            # self.fractiontaken = self.fractiontakendes
        self.fs_injected.copy_from(self.fs_in, 
                                   self.fractiontaken)
        # self.gas_injected.mass = self.fs_in.mass * self.fractiontaken
        # self.fs_injected.TPY = self.fs_in.TPY
        self.fs_out.copy_from(self.fs_injected)
        self.W = self.fs_out.W
        return self.fs_out

    def PrintPerformance(self, Mode, PointTime):
        super().PrintPerformance(Mode, PointTime)
        print(f"\tFraction from bleed nr {self.frombleednumber}: {self.fractiontaken:.2f}")
        print(f"\tInject conditions:")
        print(f"\t\tTemperature : {self.fs_injected.T:.1f} K")
        print(f"\t\tPressure    : {self.fs_injected.P:.0f} Pa")
        #  1.6 WV
        print(f"\tExit conditions:")
        print(f"\t\tMass flow : {self.fs_out.W:.1f} [kg/s]")
        print(f"\t\tTemperature : {self.fs_out.T:.1f} K")
        print(f"\t\tPressure    : {self.fs_out.P:.0f} Pa")

        if self.DHWpump != None:
            print(f"\t\tDHW rad pump : {self.DHWpump:.0f} kW")
        if self.DHWexp != None:
            print(f"\t\tDHW expansion: {self.DHWexp:.1f} kW")

    # 2.0.0.0
    def get_outputs(self):
        out = super().get_outputs()

        out[f"Fraction from bleed nr {self.frombleednumber}"]  = self.fractiontaken
        out[f"T{self.station_in}j"]  = self.fs_injected.T
        out[f"P{self.station_in}j"]  = self.fs_injected.P
        #  1.6 WV
        out[f"W{self.station_out}"]  = self.fs_out.mass
        out[f"T{self.station_out}"]  = self.fs_out.T
        out[f"P{self.station_out}"]  = self.fs_out.P

        if self.DHWpump != None:
            out[f"DHWpump{self.station_out}"]  = self.DHWpump
        if self.DHWexp != None:
            out[f"DHWexp{self.station_out}"]  = self.DHWexp

        return out

    def get_output_units(self):
        units = super().get_output_units()

        units[f"Fraction from bleed nr {self.frombleednumber}"]  = "[-]"
        units[f"T{self.station_in}j"]  = "[K]"
        units[f"P{self.station_in}j"]  = "[Pa]"

        #  1.6 WV
        units[f"W{self.station_out}"]  = "[kg/s]"
        units[f"T{self.station_out}"]  = "[K]"
        units[f"P{self.station_out}"]  = "[Pa]"

        if self.DHWpump != None:
            units[f"DHWpump{self.station_out}"]  = "[W]"
        if self.DHWexp != None:
            units[f"DHWexp{self.station_out}"]  = "[W]"

        return units