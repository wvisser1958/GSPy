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

class TExhaust(TGaspath):
    def __init__(self, name, MapFileName, stationin, stationthroat, stationout, CXdes, CVdes, CDdes, PRdes):    # Constructor of the class
        # CXdes, CVdes, CDdes are for propelling nozzle
        # PRdes = diffuser pressure loss (Psout/Ptin) in case of a (divergent) exhaust diffuser
        # If PRdes <> None then a divergent diffuser expansion is calculated, with PRdes as the diffuser
        # pressure loss. PRdes must be < 1. Psout then determines the diffuser exit area A9.
        super().__init__(name, MapFileName, stationin, stationout)
        self.stationthroat = stationthroat
        self.CXdes = CXdes
        self.CVdes = CVdes
        self.CDdes = CDdes
        self.PRdes = PRdes

    def Run(self, Mode, PointTime):
        super().Run(Mode, PointTime)
        # add nozzle throat station
        self.GasThroat = ct.Quantity(self.GasIn.phase, mass = self.GasIn.mass)
        Sin = self.GasIn.entropy_mass
        Hin = self.GasIn.enthalpy_mass
        Pin = self.GasIn.P
        Pout = fsys.Ambient.Psa
        self.PR = Pin/Pout
        if Mode == 'DP':
            Vthroat_is, self.Tthroat = fu.calculate_exit_velocity(self.GasOut.phase, self.PR)
            # try full expansion to Pout
            self.GasThroat.TP = self.Tthroat, Pout
            self.Mthroat = Vthroat_is / self.GasThroat.phase.sound_speed
            if self.Mthroat > 1: # cannot be, correct for Mthroat = 1
                self.Mthroat = 1

                # Function to find the pressure for Mach 1
                def mach_number_difference(exit_pressure):
                    self.GasThroat.SP = Sin, float(exit_pressure)  # Set state at the given pressure
                    local_speed_of_sound = self.GasThroat.sound_speed
                    velocity = (2 * (Hin - self.GasThroat.enthalpy_mass))**0.5
                    mach_number = velocity / local_speed_of_sound
                    return mach_number - 1.0  # We want Mach number to be exactly 1
                # Use a numerical solver to find the exit pressure where Mach = 1
                # rootresult = root_scalar(mach_number_difference, bracket=[0.1*Pout, Pin], method='brentq')
                # use newton with 1.9 as guess for PR critical/choke to calculate initial exit_pressure
                P0 = Pin/1.9
                rootresult = root_scalar(mach_number_difference, x0=P0, method='newton')

                self.Pthroat = rootresult.root
                self.Vthroat = self.GasThroat.phase.sound_speed * self.CVdes
            else:
                self.Pthroat = Pout
                self.Vthroat = Vthroat_is * self.CVdes
            self.Tthroat = self.GasThroat.T
            # exit flow error
            fsys.errors = np.append(fsys.errors, 0)
            self.ierror_w = fsys.errors.size - 1
            if self.Vthroat <= 0:
                self.Vthroat = 0.001  # always assume a minimal flow velocity: 0.001 will result in a theoretical
                                      # very large exhaust area
            self.Athroat_des = self.GasThroat.mass / self.GasThroat.phase.density / self.Vthroat
            self.Athroat = self.Athroat_des
        else:
            self.Athroat = self.Athroat_des # fixed nozzle are still here
            self.Pthroat, self.Tthroat, Vthroat_is, massflow = fu.calculate_expansion_to_A(self.GasIn.phase, Pin/Pout, self.Athroat)
            self.GasThroat.TP = self.Tthroat, self.Pthroat
            self.Vthroat = Vthroat_is * self.CVdes
            fsys.errors[self.ierror_w] = (self.GasIn.mass - massflow) / self.GasInDes.mass
            self.Mthroat = self.Vthroat / self.GasThroat.phase.sound_speed
        # calculate parameters for output
        self.GasOut.TP = self.Tthroat, Pout # assume no further expansion
        self.Wc = self.GasIn.mass * fg.GetFlowCorrectionFactor(self.GasIn)
        self.FG = self.CXdes * (self.GasOut.mass * self.Vthroat + self.Athroat*(self.Pthroat-Pout))
        # add gross thrust to system level thrust (note that multiple propelling nozzles may exist)
        fsys.FG = fsys.FG + self.FG
        self.Athroat_geom = self.Athroat / self.CDdes
        fsys.gaspath_conditions[self.stationthroat] = self.GasThroat
        return self.GasOut

    def Aexitname(self):
        if self.PRdes == None:
            return 'Athroat'
        else:
            return 'Aexit'

    def PrintPerformance(self, Mode, PointTime):
        super().PrintPerformance(Mode, PointTime)
        # Print and return the results
        print(f"\tExit velocity: {self.Vthroat:.2f} m/s")
        if Mode == 'DP':
            print(f"\tThroat area (DP): {self.Athroat_des:.4f} m2")
        print(f"\tExit static temperature: {self.GasOut.T:.1f} K")
        print(f"\tThroat static pressure: {self.Pthroat:.0f} Pa")
        print(f"\tExit static pressure: {self.GasOut.P:.0f} Pa")
        print(f"\tGross thrust: {self.FG:.2f} N")
        print(f"\t{self.Aexitname()}: {self.Athroat:.4f} m2")

    def GetOutputTableColumnNames(self):
        return super().GetOutputTableColumnNames()                                                              \
            + [f"T{self.stationthroat}", f"P{self.stationthroat}", f"V{self.stationthroat}", f"Mach{self.stationthroat}", \
               f"T{self.stationout}", f"P{self.stationout}",                                                \
               f"{self.Aexitname()}_"+self.name, f"{self.Aexitname()}_geom_" + self.name, "FG_" + self.name]

    def AddOutputToTable(self, Mode, rownr):
        # fg.OutputTable.loc[rownr, columnname] = getattr(self, columnname)
        super().AddOutputToTable(Mode, rownr)
        fsys.OutputTable.loc[rownr, f"T{self.stationthroat}"]  = self.Tthroat
        fsys.OutputTable.loc[rownr, f"P{self.stationthroat}"]  = self.Pthroat
        fsys.OutputTable.loc[rownr, f"V{self.stationthroat}"]  = self.Vthroat
        fsys.OutputTable.loc[rownr, f"Mach{self.stationthroat}"]  = self.Mthroat
        fsys.OutputTable.loc[rownr, f"T{self.stationout}"]  = self.GasOut.T
        fsys.OutputTable.loc[rownr, f"P{self.stationout}"]  = self.GasOut.P
        fsys.OutputTable.loc[rownr, f"{self.Aexitname()}_"+self.name]  = self.Athroat
        fsys.OutputTable.loc[rownr, f"{self.Aexitname()}_"+self.name]  = self.Athroat_geom
        fsys.OutputTable.loc[rownr, "FG_"+self.name]  = self.FG

