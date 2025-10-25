# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#    http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import numpy as np
import cantera as ct
import f_utils as fu
from scipy.optimize import root_scalar
from f_gaspath import TGaspath
import f_global as fg
import f_system as fsys

class TExhaustDiffuser(TGaspath):
    def __init__(self, name, MapFileName, ControlComponent, stationin, stationthroat, stationout, CXdes, CVdes, CDdes, PRdes):    # Constructor of the class
        # CXdes, CVdes, CDdes are for propelling nozzle
        # PRdes = diffuser pressure loss (Psout/Ptin) in case of a (divergent) exhaust diffuser
        # If PRdes <> None then a divergent diffuser expansion is calculated, with PRdes as the diffuser
        # pressure loss. PRdes must be < 1. Psout then determines the diffuser exit area A9.
        super().__init__(name, MapFileName, ControlComponent, stationin, stationout)
        self.PRdes = PRdes

    def Run(self, Mode, PointTime):
        super().Run(Mode, PointTime)
        # add nozzle throat station
        if Mode == 'DP':
            self.GasThroat = ct.Quantity(self.GasIn.phase, mass = self.GasIn.mass)
        else:
            self.GasThroat.TPY = self.GasIn.TPY
            self.GasThroat.mass = self.GasIn.mass
        Sin = self.GasIn.entropy_mass
        Hin = self.GasIn.enthalpy_mass
        Pin = self.GasIn.P
        Pout = fsys.Ambient.Psa
        # diffuser with pressure loss, diffusing flow.
        # 1 - PR is rel. pressure loss proportional to Wc^2
        # in derived version, maybe make PR loss map
        dprel = (1 - self.PRdes) * np.square(self.Wc/self.Wcdes)
        self.PR = 1 - dprel
        if Mode == 'DP':
            # diffuser
            # use GasThroat as exit here
            self.GasThroat.TP = self.GasIn.T, Pout
            fsys.errors = np.append(fsys.errors, 0)
            self.ierror_p = fsys.errors.size - 1
        else:
            # Off-design calculation
            # fsys.errors[self.ierror_p] = self.GasIn.P*self.PR / Pout
            fsys.errors[self.ierror_p] = (self.GasIn.P*self.PR - Pout) / Pout
        self.GasOut.TP = self.GasThroat.T, Pout
        return self.GasOut

    def PrintPerformance(self, Mode, PointTime):
        super().PrintPerformance(Mode, PointTime)
        # Print and return the results
        print(f"\t\tExit static temperature: {self.GasOut.T:.1f} K")
        print(f"\t\tExit static pressure: {self.GasOut.P:.0f} Pa")

    #  1.1 WV
    def AddOutputToDict(self, Mode):
        super().AddOutputToDict(Mode)
        fsys.output_dict[f"T{self.stationout}"]  = self.GasOut.T
        fsys.output_dict[f"P{self.stationout}"]  = self.GasOut.P

