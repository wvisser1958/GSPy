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

# v1.2 Propelling exhaust nozzle
import numpy as np
import cantera as ct
import f_utils as fu
from scipy.optimize import root_scalar
from f_gaspath import TGaspath
import f_global as fg
import f_system as fsys

class TExhaustNozzle(TGaspath):
    def __init__(self, name, MapFileName, ControlComponent, stationin, stationthroat, stationout, CXdes, CVdes, CDdes):    # Constructor of the class
        # CXdes, CVdes, CDdes are for propelling nozzle
        # PRdes = diffuser pressure loss (Psout/Ptin) in case of a (divergent) exhaust diffuser
        # If PRdes <> None then a divergent diffuser expansion is calculated, with PRdes as the diffuser
        # pressure loss. PRdes must be < 1. Psout then determines the diffuser exit area A9.
        super().__init__(name, MapFileName, ControlComponent, stationin, stationout)
        self.stationthroat = stationthroat
        self.CXdes = CXdes
        self.CVdes = CVdes
        self.CDdes = CDdes

    def Run(self, Mode, PointTime):
        super().Run(Mode, PointTime)
        # add nozzle throat station
        self.GasThroat = ct.Quantity(self.GasIn.phase, mass = self.GasIn.mass)
        Sin = self.GasIn.entropy_mass
        Hin = self.GasIn.enthalpy_mass
        Pin = self.GasIn.P
        Pout = fsys.Ambient.Psa
        # propelling nozzle, expansion flow
        # PR is nozzle PR Pout/Pin, only calculated (not given)
        # # v1.2
        # self.PR = Pin/Pout
        self.PR = Pin/Pout
        if Mode == 'DP':
            self.PRdes = self.PR
            # Vthroat_is, self.Tthroat = fu.calculate_exit_velocity(self.GasOut.phase, self.PR)
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
                # 1.301 bug fix do not multiply with CVdes here. CXV is not supposed to affect Athroat and mass flow
                # self.Vthroat = self.GasThroat.phase.sound_speed * self.CVdes
                self.Vthroat = self.GasThroat.phase.sound_speed
            else:
                self.Pthroat = Pout
                # 1.301
                # self.Vthroat = Vthroat_is * self.CVdes
                self.Vthroat = Vthroat_is
            self.Tthroat = self.GasThroat.T
            # exit flow error
            fsys.errors = np.append(fsys.errors, 0)
            self.ierror_w = fsys.errors.size - 1
            if self.Vthroat <= 0:
                self.Vthroat = 0.001  # always assume a minimal flow velocity: 0.001 will result in a theoretical
                                    # very large exhaust area
            self.Athroat_des = self.GasThroat.mass / self.GasThroat.phase.density / self.Vthroat
            self.Athroat = self.Athroat_des
            # 1.301 now apply CV
            self.Vthroat = self.Vthroat * self.CVdes
        else:
            # Off-design calculation
            self.Athroat = self.Athroat_des # fixed nozzle are still here
            self.Pthroat, self.Tthroat, Vthroat_is, massflow = fu.calculate_expansion_to_A(self.GasIn.phase, Pin/Pout, self.Athroat)
            self.GasThroat.TP = self.Tthroat, self.Pthroat
            self.Vthroat = Vthroat_is * self.CVdes
            fsys.errors[self.ierror_w] = (self.GasIn.mass - massflow) / self.GasInDes.mass
            # 1.301 use Vthroat_is for Mach number
            # self.Mthroat = self.Vthroat / self.GasThroat.phase.sound_speed
            self.Mthroat = Vthroat_is / self.GasThroat.phase.sound_speed
        self.GasOut.TP = self.Tthroat, Pout # assume no further expansion
        self.FG = self.CXdes * (self.GasOut.mass * self.Vthroat + self.Athroat*(self.Pthroat-Pout)) / 1000 # kN
        # add gross thrust to system level thrust (note that multiple propelling nozzles may exist)
        fsys.FG = fsys.FG + self.FG
        self.Athroat_geom = self.Athroat / self.CDdes
        fsys.gaspath_conditions[self.stationthroat] = self.GasThroat
        return self.GasOut


    def PrintPerformance(self, Mode, PointTime):
        super().PrintPerformance(Mode, PointTime)
        # Print and return the results
        print(f"\t\tExit static temperature: {self.GasOut.T:.1f} K")
        print(f"\t\tExit static pressure: {self.GasOut.P:.0f} Pa")
        print(f"\t\tExit velocity: {self.Vthroat:.2f} m/s")
        if Mode == 'DP':
            print(f"\t\tThroat area (DP): {self.Athroat_des:.4f} m2")
        print(f"\t\tAthroat: {self.Athroat:.4f} m2")
        print(f"\t\tThroat static pressure: {self.Pthroat:.0f} Pa")
        print(f"\tGross thrust: {self.FG:.2f} kN")

    #  1.1 WV
    def AddOutputToDict(self, Mode):
        super().AddOutputToDict(Mode)
        fsys.output_dict[f"T{self.stationthroat}"]  = self.Tthroat
        fsys.output_dict[f"P{self.stationthroat}"]  = self.Pthroat
        fsys.output_dict[f"V{self.stationthroat}"]  = self.Vthroat
        fsys.output_dict[f"Mach{self.stationthroat}"]  = self.Mthroat
        fsys.output_dict[f"T{self.stationout}"]  = self.GasOut.T
        fsys.output_dict[f"P{self.stationout}"]  = self.GasOut.P
        fsys.output_dict[f"A{self.stationthroat}"]  = self.Athroat
        fsys.output_dict[f"A{self.stationthroat}_geom"]  = self.Athroat_geom
        fsys.output_dict["FG_"+self.name]  = self.FG

