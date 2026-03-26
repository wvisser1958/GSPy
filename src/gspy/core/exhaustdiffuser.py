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
import gspy.core.utils as fu
from scipy.optimize import root_scalar
from gspy.core.gaspath import TGaspath


class TExhaustDiffuser(TGaspath):
    def __init__(self, owner, name, MapFileName, ControlComponent, station_in, station_out, PRdes):    # Constructor of the class
        # CXdes, CVdes, CDdes are for propelling nozzle
        # PRdes = diffuser pressure loss (Psout/Ptin) in case of a (divergent) exhaust diffuser
        # If PRdes <> None then a divergent diffuser expansion is calculated, with PRdes as the diffuser
        # pressure loss. PRdes must be < 1. Psout then determines the diffuser exit area A9.
        super().__init__(owner, name, MapFileName, ControlComponent, station_in, station_out)
        self.PRdes = PRdes

    def Run(self, Mode, PointTime):
        super().Run(Mode, PointTime)
        # add nozzle throat station
        if Mode == 'DP':
            self.GasThroat = ct.Quantity(self.gas_in.phase, mass = self.gas_in.mass)
        else:
            self.GasThroat.TPY = self.gas_in.TPY
            self.GasThroat.mass = self.gas_in.mass
        Sin = self.gas_in.entropy_mass
        Hin = self.gas_in.enthalpy_mass
        Pin = self.gas_in.P
        Pout = self.owner.ambient.Psa
        # diffuser with pressure loss, diffusing flow.
        # 1 - PR is rel. pressure loss proportional to Wc^2
        # in derived version, maybe make PR loss map
        dprel = (1 - self.PRdes) * np.square(self.Wc/self.Wcdes)
        self.PR = 1 - dprel
        if Mode == 'DP':
            # diffuser
            # use GasThroat as exit here
            self.GasThroat.TP = self.gas_in.T, Pout
            self.owner.errors = np.append(self.owner.errors, 0)
            self.ierror_p = self.owner.errors.size - 1
        else:
            # Off-design calculation
            # fsys.errors[self.ierror_p] = self.gas_in.P*self.PR / Pout
            self.owner.errors[self.ierror_p] = (self.gas_in.P*self.PR - Pout) / Pout
        self.gas_out.TP = self.GasThroat.T, Pout
        return self.gas_out

    def PrintPerformance(self, Mode, PointTime):
        super().PrintPerformance(Mode, PointTime)
        # Print and return the results
        print(f"\t\tExit static temperature: {self.gas_out.T:.1f} K")
        print(f"\t\tExit static pressure: {self.gas_out.P:.0f} Pa")

    def get_outputs(self):
        out = super().get_outputs()
        sout = self.station_out
        out[f"T{sout}"]  = self.gas_out.T
        out[f"P{sout}"]  = self.gas_out.P

        return out