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
from f_base_component import TComponent
import f_global as fg
import f_system as fsys

class TGaspath(TComponent):
    def __init__(self, name, MapFileName, ControlComponent, stationin, stationout):    # Constructor of the class
        super().__init__(name, MapFileName, ControlComponent)
        self.stationin = stationin
        self.stationout = stationout
        # set design properties to None, if still None in PrintPerformance,
        # then not assigned anywhere so no need to Print/output.
        self.GasIn = None
        self.GasOut = None
        self.Wc = None
        self.PRdes = 1
        self.PR = None

    def Run(self, Mode, PointTime):
        self.GasIn = fsys.gaspath_conditions[self.stationin]

        if Mode == 'DP':
            # create GasInDes, GasOut cantera Quantity (GasIn already created)
            self.GasInDes = ct.Quantity(self.GasIn.phase, mass = self.GasIn.mass)
            self.GasOut = ct.Quantity(self.GasIn.phase, mass = self.GasIn.mass)
            self.Wdes = self.GasInDes.mass
            self.Wcdes = self.Wdes * fg.GetFlowCorrectionFactor(self.GasInDes)
            self.W = self.Wdes
            self.Wc = self.Wcdes
        else:
            # v1.2
            self.W = self.GasIn.mass
            self.Wc = self.W * fg.GetFlowCorrectionFactor(self.GasIn)

            self.GasOut.TPY = self.GasIn.TPY
            self.GasOut.mass = self.GasIn.mass

        fsys.gaspath_conditions[self.stationout] = self.GasOut
        return self.GasOut

    def PrintPerformance(self, Mode, PointTime):
        super().PrintPerformance(Mode, PointTime)
        print(f"\tInlet conditions:")
        print(f"\t\tMass flow  : {self.W:.2f} kg/s")
        print(f"\t\tTemperature: {self.GasIn.T:.1f} K")
        print(f"\t\tPressure   : {self.GasIn.P:.0f} Pa")
        if self.Wcdes != None:
            print(f"\tDP Corr.Mass flow  : {self.Wcdes:.2f} kg/s")
        if self.Wc != None:
            print(f"\tCorr.Mass flow  : {self.Wc:.2f} kg/s")
        if self.PRdes != None:
            print(f"\tDP Pressure ratio  : {self.PRdes:.4f}")
        if self.PR != None:
            print(f"\tPressure ratio  : {self.PR:.4f}")
        print(f"\tExit conditions:")
        print(f"\t\tTemperature: {self.GasOut.T:.1f} K")
        print(f"\t\tPressure   : {self.GasOut.P:.0f} Pa")

    #  1.1 WV
    def AddOutputToDict(self, Mode):
        fsys.output_dict[f"W{self.stationin}"]  = self.GasIn.mass
        fsys.output_dict[f"Wc{self.stationin}"] = self.Wc
        fsys.output_dict[f"T{self.stationin}"]  = self.GasIn.T
        fsys.output_dict[f"P{self.stationin}"]  = self.GasIn.P
        if self.PR != None:
            fsys.output_dict["PR_"+self.name] = self.PR


