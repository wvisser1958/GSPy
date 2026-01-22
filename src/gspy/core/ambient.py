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

import cantera as ct
import aerocalc as ac     # !!!! install with "pip install aero-calc", see https://www.kilohotel.com/python/aerocalc/html/
from gspy.core.base_component import TComponent
import gspy.core.sys_global as fg
import gspy.core.system as fsys

class TAmbient(TComponent):
    def __init__(self, name, stationnr, Altitude, Macha, dTs, Psa, Tsa):    # Constructor of the class
        super().__init__(name, '', None)
        self.stationnr = stationnr
        self.SetConditions('DP', Altitude, Macha, dTs, Psa, Tsa)

    def SetConditions(self, Mode, Altitude, Macha, dTs, Psa, Tsa):
        if Mode == 'DP':
            self.Altitude_des = Altitude
            self.Macha_des = Macha
            self.dTs_des = dTs
            self.Psa_des = Psa      # if None then this will override value from standard atmosphere Alt, Machm dTs
            self.Tsa_des = Tsa      # if None then this will override value from standard atmosphere Alt, Machm dTs
        else:
            self.Altitude = Altitude
            self.Macha = Macha
            self.dTs = dTs
            self.Psa = Psa      # if None then this will override value from standard atmosphere Alt, Machm dTs
            self.Tsa = Tsa      # if None then this will override value from standard atmosphere Alt, Machm dTs

    def Run(self, Mode, PointTime):
        if Mode == 'DP':  # alway reset de DP conditions
            self.Altitude = self.Altitude_des
            self.Macha = self.Macha_des
            self.dTs = self.dTs_des
            self.Psa = self.Psa_des      # if None then this will override value from standard atmosphere Alt, Machm dTs
            self.Tsa = self.Tsa_des      # if None then this will override value from standard atmosphere Alt, Machm dTs
            # create separate Cantera phase object for Ambient, to be used by components if needed
            # self.Gas_Ambient = ct.Solution('jetsurf.yaml')
            # create Cantera quantity object for Ambient (mass = 1 per default)
            self.Gas_Ambient = ct.Quantity(fg.gas)
            fsys.gaspath_conditions[self.stationnr] = self.Gas_Ambient
        if self.Tsa == None:
            # Tsa not defined, use standard atmosphere
            self.Tsa = ac.std_atm.alt2temp(self.Altitude, alt_units='m', temp_units='K')
            # for standard atmosphere, use dTs if defined
            if self.dTs != None:
                self.Tsa = self.Tsa + self.dTs
        if self.Psa == None:
            # Ps0 not defined, used standard atmosphere
            self.Psa = ac.std_atm.alt2press(self.Altitude, alt_units='m', press_units='pa')
        self.Tta = self.Tsa * ( 1 + 0.2 * self.Macha**2)
        self.Pta = self.Psa * ((self.Tta/self.Tsa)**3.5)
        # set values in the Gas_Ambient phase object conditions
        self.Gas_Ambient.TPY = self.Tta, self.Pta, fg.s_air_composition_mass
        self.V = self.Macha * ac.std_atm.temp2speed_of_sound(self.Tsa, speed_units = 'm/s', temp_units = 'K')

    #  1.1 WV
    def AddOutputToDict(self, Mode):
        fsys.output_dict["Alt"] = self.Altitude
        fsys.output_dict["Tsa"] = self.Tsa
        fsys.output_dict["Psa"] = self.Psa
        fsys.output_dict["Tta"] = self.Tta
        fsys.output_dict["Pta"] = self.Pta
        fsys.output_dict["Macha"] = self.Macha