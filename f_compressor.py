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

import math
import numpy as np
from scipy.interpolate import RegularGridInterpolator
import cantera as ct
import f_global as fg
import f_system as fsys
import f_utils as fu
from f_turbo_component import TTurboComponent
from f_compressormap import TCompressorMap

class TCompressor(TTurboComponent):
    def __init__(self, name, MapFileName, ControlComponent,
                 stationin, stationout, ShaftNr,
                 Ndes, Etades, Ncmapdes, Betamapdes, PRdes,
                 SpeedOption,
                 Bleeds):    # Constructor of the class
        super().__init__(name, MapFileName, ControlComponent, stationin, stationout, ShaftNr, Ndes, Etades)
        # only call SetDPparameters in instantiable classes in init creator
        self.PRdes = PRdes
        self.SpeedOption = SpeedOption
        self.map = TCompressorMap(self, name + '_map', MapFileName, '', '', ShaftNr, Ncmapdes, Betamapdes)
        self.Bleeds = Bleeds

    def Run(self, Mode, PointTime):
        super().Run(Mode, PointTime)
        if Mode == 'DP':
            self.PW = fu.Compression(self.GasIn, self.GasOut, self.PRdes, self.Etades)

            self.map.ReadMapAndSetScaling(self.Ncdes, self.Wcdes, self.PRdes, self.Etades)

            # add states and errors
            if self.SpeedOption != 'CS':
                fsys.states = np.append(fsys.states, 1)
                self.istate_n = fsys.states.size-1
                self.shaft.istate = self.istate_n
            fsys.states = np.append(fsys.states, 1)
            self.istate_beta = fsys.states.size-1
            # error for equation GasIn.wc = wcmap
            fsys.errors = np.append(fsys.errors, 0)
            self.ierror_wc = fsys.errors.size-1
            # calculate parameters for output
            self.PR = self.PRdes
        else:
            if self.SpeedOption != 'CS':
                self.N = fsys.states[self.istate_n] * self.Ndes
            self.Nc = self.N / fg.GetRotorspeedCorrectionFactor(self.GasIn)

            self.Wc, self.PR, self.Eta = self.map.GetScaledMapPerformance(self.Nc, fsys.states[self.istate_beta])

            self.PW = fu.Compression(self.GasIn, self.GasOut, self.PR, self.Eta)

            self.W = self.Wc / fg.GetFlowCorrectionFactor(self.GasIn)
            fsys.errors[self.ierror_wc ] = (self.W - self.GasIn.mass) / self.Wdes

            # set out flow rate to W according to map
            # may deviate from self.GasIn.mass during iteration: this is to propagate the effect of mass flow error
            # to downstream components for more stable convergence in the solver (?)
            self.GasOut.mass = self.W

        # v1.2 correction for bleed flows
        dW = 0
        dHW_bleeds_total = 0
        dH = self.GasOut.enthalpy_mass - self.GasIn.enthalpy_mass
        dP = self.GasOut.P - self.GasIn.P
        if self.Bleeds != None:
            for bleed in self.Bleeds:
                Wbleed = bleed.bleedfraction * self.W
                dW = dW + Wbleed
                # dHW = dHW + (1 - bleed.dPfactor) * dH * Wbleed
                if bleed.GasIn == None:
                    #  define bleed inflow GasIn conditions
                    bleed.GasIn = ct.Quantity(self.GasIn.phase, Wbleed)
                else:
                    bleed.GasIn.TPY = self.GasIn.T, self.GasIn.P, self.GasIn.Y
                    bleed.GasIn.mass = Wbleed
                #  add to station conditions dictionary
                fsys.gaspath_conditions[bleed.stationin] = bleed.GasIn

                # Compress Wbleed to bleed point
                dHW1 = fu.Compression(self.GasIn, bleed.GasIn, (self.GasIn.P+dP*bleed.dPfactor)/self.GasIn.P, self.Eta)
                # now delta of compression power due to the bleed is
                dHW2 = dH * Wbleed  - dHW1
                dHW_bleeds_total = dHW_bleeds_total + dHW2
                # run the bleed flow run code (default is simply the TGasPath method, sets bleed.GasOut to bleed.GasIn)
                bleed.Run(Mode, PointTime)
            self.GasOut.mass = self.GasOut.mass - dW
            self.PW = self.PW - dHW_bleeds_total

        self.shaft.PW_sum = self.shaft.PW_sum - self.PW

        return self.GasOut

    # v1.2
    def PrintPerformance(self, Mode, PointTime):
        super().PrintPerformance(Mode, PointTime)
        if self.Bleeds != None:
            for bleed in self.Bleeds:
                bleed.PrintPerformance(Mode, PointTime)

    def AddOutputToDict(self, Mode):
        super().AddOutputToDict(Mode)
        if self.Bleeds != None:
            for bleed in self.Bleeds:
                bleed.AddOutputToDict(Mode)
