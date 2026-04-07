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
from gspy.core.base_component import TComponent
# import gspy.core.sys_global as fg
import gspy.core.utils as fu

class TGaspath(TComponent):
    def __init__(self, owner, name, map_filename, control_component, station_in, station_out):    # Constructor of the class
        super().__init__(owner, name, map_filename, control_component)
        self.station_in = station_in
        self.station_out = station_out
        # set design properties to None, if still None in PrintPerformance,
        # then not assigned anywhere so no need to Print/output.
        self.gas_in = None
        self.gas_out = None
        self.Wc = None
        self.PRdes = 1
        self.PR = None
        # 1.6.0.5
        self.W = None

    def Run(self, Mode, PointTime):
        self.gas_in = self.owner.gaspath_conditions[self.station_in]

        if Mode == 'DP':
            # create gas_inDes, gas_out cantera Quantity (gas_in already created)
            self.gas_inDes = ct.Quantity(self.gas_in.phase, mass = self.gas_in.mass)
            self.gas_out = ct.Quantity(self.gas_in.phase, mass = self.gas_in.mass)
            self.Wdes = fu.scalar(self.gas_inDes.mass)
            self.Wcdes = self.Wdes * fu.GetFlowCorrectionFactor(self.gas_inDes)
            self.W = self.Wdes
            self.Wc = self.Wcdes
        else:
            # v1.2
            self.W = fu.scalar(self.gas_in.mass)
            self.Wc = self.W * fu.GetFlowCorrectionFactor(self.gas_in)

            self.gas_out.TPY = self.gas_in.TPY
            self.gas_out.mass = self.gas_in.mass

        self.owner.gaspath_conditions[self.station_out] = self.gas_out
        return self.gas_out

    def PrintPerformance(self, Mode, PointTime):
        super().PrintPerformance(Mode, PointTime)
        print(f"\tInlet conditions:")
        print(f"\t\tMass flow  : {self.W:.2f} kg/s")
        print(f"\t\tTemperature: {self.gas_in.T:.1f} K")
        print(f"\t\tPressure   : {self.gas_in.P:.0f} Pa")
        if self.Wcdes != None:
            print(f"\tDP Corr.Mass flow  : {self.Wcdes:.2f} kg/s")
        if self.Wc != None:
            print(f"\tCorr.Mass flow  : {self.Wc:.2f} kg/s")
        if self.PRdes != None:
            print(f"\tDP Pressure ratio  : {self.PRdes:.4f}")
        if self.PR != None:
            print(f"\tPressure ratio  : {self.PR:.4f}")
        print(f"\tExit conditions:")
        print(f"\t\tTemperature: {self.gas_out.T:.1f} K")
        print(f"\t\tPressure   : {self.gas_out.P:.0f} Pa")

    def _get_species_outputs(self, gas_quantity, station, basis="mass", prefix=None):
        out = {}

        if gas_quantity is None:
            return out

        gas = gas_quantity.phase

        if basis == "mass":
            values = gas.Y
            names = gas.species_names
            key_prefix = "Y" if prefix is None else prefix
        elif basis == "mole":
            values = gas.X
            names = gas.species_names
            key_prefix = "X" if prefix is None else prefix
        else:
            raise ValueError("basis must be 'mass' or 'mole'")

        for species, value in zip(names, values):
            out[f"{key_prefix}_{species}_{station}"] = float(value)

        return out

    # 2.0.0.0
    def get_outputs(self):
        out = super().get_outputs()

        s_in = self.station_in

        out[f"W{s_in}"] = fu.scalar(self.gas_in.mass)
        out[f"T{s_in}"] = self.gas_in.T
        out[f"P{s_in}"] = self.gas_in.P
        out[f"Wc{s_in}"] = self.Wc

        if self.PR is not None:
            out[f"PR_{self.name}"] = self.PR

        # out.update(self._get_species_outputs(self.gas_in, s_in, basis="mass"))

        return out



