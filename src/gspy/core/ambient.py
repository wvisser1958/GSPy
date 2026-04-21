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
# import gspy.core.sys_global as fg
import gspy.core.constants as c

class TAmbient(TComponent):
    def __init__(self, owner, name, stationnr, Altitude, Macha, dTs, Psa, Tsa, RH=None):
        super().__init__(owner, name, '', None)
        self.station_nr = stationnr

        self.humidity_mode_des = None
        self.humidity_value_des = None
        self.humidity_mode = None
        self.humidity_value = None

        # create Cantera quantity object for Ambient (mass = 1 per default)
        # this quantity is then further copied along the gaspath in the system model
        self.Gas_Ambient = ct.Quantity(self.owner.gas)
        self.owner.gaspath_conditions[self.station_nr] = self.Gas_Ambient

        self.SetConditions('DP', Altitude, Macha, dTs, Psa, Tsa, RH=RH)

        owner.ambient = self

    def _get_ambient_mole_fractions_from_static_conditions(self):
        """
        Return humid ambient composition as mole fractions, based on
        static ambient conditions Tsa / Psa and the stored humidity spec.
        """

        # no humidity specified -> dry air
        if self.humidity_mode is None:
            return dict(c.s_air_composition_mole)

        # ----------------------------------------------------------
        # Relative humidity [%]
        # ----------------------------------------------------------
        if self.humidity_mode == "RH":
            water = ct.Water()
            water.TQ = self.Tsa, 1.0
            p_sat = water.P_sat

            p_h2o = (self.humidity_value / 100.0) * p_sat
            x_h2o = p_h2o / self.Psa

            if not (0.0 <= x_h2o < 1.0):
                raise ValueError(f"Invalid RH gives x_h2o={x_h2o:.6f}")

            X = {k: v * (1.0 - x_h2o) for k, v in c.s_air_composition_mole.items()}
            X["H2O"] = x_h2o
            return X

        # ----------------------------------------------------------
        # Water volume %
        # for ideal gases: vol% = mole%
        # ----------------------------------------------------------
        if self.humidity_mode == "H2O_vol_pct":
            x_h2o = self.humidity_value / 100.0

            if not (0.0 <= x_h2o < 1.0):
                raise ValueError(f"Invalid H2O_vol_pct gives x_h2o={x_h2o:.6f}")

            X = {k: v * (1.0 - x_h2o) for k, v in c.s_air_composition_mole.items()}
            X["H2O"] = x_h2o
            return X

        # ----------------------------------------------------------
        # Water mass %
        # convert mass fractions -> Cantera state -> mole fractions
        # ----------------------------------------------------------
        if self.humidity_mode == "H2O_mass_pct":
            y_h2o = self.humidity_value / 100.0

            if not (0.0 <= y_h2o < 1.0):
                raise ValueError(f"Invalid H2O_mass_pct gives y_h2o={y_h2o:.6f}")

            Y = {k: v * (1.0 - y_h2o) for k, v in c.s_air_composition_mass.items()}
            Y["H2O"] = y_h2o

            # temporary set state to convert Y -> X
            self.Gas_Ambient.TPY = self.Tsa, self.Psa, Y
            return dict(zip(self.Gas_Ambient.species_names, self.Gas_Ambient.X))

        raise ValueError(f"Unknown humidity_mode '{self.humidity_mode}'")


    def SetConditions(self, Mode, Altitude, Macha, dTs, Psa, Tsa,
                      *, RH=None, H2O_mass_pct=None, H2O_vol_pct=None):

        specified = [(k, v) for k, v in {
            'RH': RH,
            'H2O_mass_pct': H2O_mass_pct,
            'H2O_vol_pct': H2O_vol_pct
        }.items() if v is not None]

        if len(specified) > 1:
            raise ValueError(
                f"Specify only one humidity argument, got: "
                f"{', '.join(k for k, _ in specified)}"
            )

        hum_mode, hum_value = (specified[0] if specified else (None, None))

        if Mode == 'DP':
            self.Altitude_des = Altitude
            self.Macha_des = Macha
            self.dTs_des = dTs
            self.Psa_des = Psa
            self.Tsa_des = Tsa
            self.humidity_mode_des = hum_mode
            self.humidity_value_des = hum_value

        self.Altitude = Altitude
        self.Macha = Macha
        self.dTs = dTs
        self.Psa = Psa
        self.Tsa = Tsa
        self.humidity_mode = hum_mode
        self.humidity_value = hum_value

        if self.Tsa == None:
            # Tsa not defined, use standard atmosphere
            self.Tsa = ac.std_atm.alt2temp(self.Altitude, alt_units='m', temp_units='K')
            # for standard atmosphere, use dTs if defined
            if self.dTs != None:
                self.Tsa = self.Tsa + self.dTs
        if self.Psa == None:
            # Ps0 not defined, used standard atmosphere
            self.Psa = ac.std_atm.alt2press(self.Altitude, alt_units='m', press_units='pa')

        # 1) composition from static ambient humidity definition
        X = self._get_ambient_mole_fractions_from_static_conditions()

        # 2) static humid-air state
        self.Gas_Ambient.TPX = self.Tsa, self.Psa, X
        cp = self.Gas_Ambient.cp_mass
        cv = self.Gas_Ambient.cv_mass
        gamma = cp / cv

        # 3) static velocity
        a_s = self.Gas_Ambient.sound_speed
        self.V = self.Macha * a_s

        # 4) total conditions using humid-air gamma
        self.Tta = self.Tsa * (1.0 + 0.5 * (gamma - 1.0) * self.Macha**2)
        self.Pta = self.Psa * (self.Tta / self.Tsa)**(gamma / (gamma - 1.0))

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
            # this quantity is then further copied along the gaspath in the system model
            self.Gas_Ambient = ct.Quantity(self.owner.gas)
            self.owner.gaspath_conditions[self.station_nr] = self.Gas_Ambient
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

# # 2.0.0.1
# if self.humidity_mode == "RH":
#     w = ct.Water()
#     w.TQ = self.Tsa, 1.0
#     p_sat = w.P_sat
#     x_h2o = (self.humidity_value / 100.0) * p_sat / self.Psa

#     X = {k: v * (1.0 - x_h2o) for k, v in c.s_air_composition_mole.items()}
#     X["H2O"] = x_h2o

#     self.Gas_Ambient.TPX = self.Tsa, self.Psa, X

# elif self.humidity_mode == "H2O_vol_pct":
#     x_h2o = self.humidity_value / 100.0

#     X = {k: v * (1.0 - x_h2o) for k, v in c.s_air_composition_mole.items()}
#     X["H2O"] = x_h2o

#     self.Gas_Ambient.TPX = self.Tta, self.Pta, X

# elif self.humidity_mode == "H2O_mass_pct":
#     y_h2o = self.humidity_value / 100.0

#     Y = {k: v * (1.0 - y_h2o) for k, v in c.s_air_composition_mass.items()}
#     Y["H2O"] = y_h2o

#     self.Gas_Ambient.TPY = self.Tta, self.Pta, Y

# else:
#     self.Gas_Ambient.TPY = self.Tta, self.Pta, c.s_air_composition_mass

        self.V = self.Macha * ac.std_atm.temp2speed_of_sound(self.Tsa, speed_units = 'm/s', temp_units = 'K')

     # 2.0.0.0
    def get_outputs(self):
        #  outputs = super().get_outputs()
        s = self.station_nr

        return {
            "Alt": self.Altitude,
            f"Ts{s}": self.Tsa,
            f"Ps{s}": self.Psa,
            f"Tt{s}": self.Tta,
            f"Pt{s}": self.Pta,
            f"Mach{s}": self.Macha,
        }

    def get_station_nr(self):
        return self.station_nr

    def set_station_nr(self, station_nr):
        self.station_nr = station_nr
