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
    def __init__(self, owner, name, stationnr, Altitude, Macha, dTs, Psa, Tsa):
        super().__init__(owner, name, '', None)
        self.station_nr = stationnr

        # self.humidity_mode_des = None
        # self.humidity_value_des = None
        # self.humidity_mode = None
        # self.humidity_value = None

        self.Gas_Ambient = ct.Quantity(self.owner.gas)
        self.owner.gaspath_conditions[self.station_nr] = self.Gas_Ambient
        self.SetConditions('DP', Altitude, Macha, dTs, Psa, Tsa, RH=None, H2O_mass_pct=None, H2O_vol_pct=None)

        owner.ambient = self

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

        # hum_mode, hum_value = (specified[0] if specified else (None, None))

        if Mode == 'DP':
            self.Altitude_des = Altitude
            self.Macha_des = Macha
            self.dTs_des = dTs
            self.Psa_des = Psa
            self.Tsa_des = Tsa
            # self.humidity_mode_des = hum_mode
            # self.humidity_value_des = hum_value
            self.H2O_mass_pct_des = H2O_mass_pct
            self.H2O_vol_pct = H2O_vol_pct
        self.Altitude = Altitude
        self.Macha = Macha
        self.dTs = dTs
        if Tsa == None:
            # Tsa not defined, use standard atmosphere
            self.Tsa = ac.std_atm.alt2temp(self.Altitude, alt_units='m', temp_units='K')
            # for standard atmosphere, use dTs if defined
            if self.dTs != None:
                self.Tsa = self.Tsa + self.dTs
        else:
            self.Tsa = Tsa
        if Psa == None:
            # Ps0 not defined, used standard atmosphere
            self.Psa = ac.std_atm.alt2press(self.Altitude, alt_units='m', press_units='pa')
        else:
            self.Psa = Psa
        # self.humidity_mode = hum_mode
        # self.humidity_value = hum_value
        self.RH = RH
        self.H2O_mass_pct = H2O_mass_pct
        self.H2O_vol_pct = H2O_vol_pct

        self._set_gas_ambient_state()

        # for debug
        # for sp, y in zip(self.Gas_Ambient.phase.species_names, self.Gas_Ambient.phase.Y):
        #     if y > 1e-12:
        #         print(f"{sp:8s} {y:.8f}")        
        # return

    def _set_gas_ambient_state(self):
        """
        Set total ambient gas state including humidity.

        This is gas-only:
        - no separate liquid water
        - RH > 100 is clamped to saturation
        """

        X = self._get_ambient_mole_fractions_from_static_conditions(
            T_static=self.Tsa,
            P_static=self.Psa,
            RH=self.RH,
            H2O_vol_pct=self.H2O_vol_pct,
            H2O_mass_pct=self.H2O_mass_pct,
        )

        # Static state
        self.Gas_Ambient.TPX = self.Tsa, self.Psa, X

        cp = self.Gas_Ambient.cp_mass
        cv = self.Gas_Ambient.cv_mass
        gamma = cp / cv

        a_s = self.Gas_Ambient.sound_speed
        self.V = self.Macha * a_s

        self.Tta = self.Tsa * (1.0 + 0.5 * (gamma - 1.0) * self.Macha**2)
        self.Pta = self.Psa * (self.Tta / self.Tsa)**(gamma / (gamma - 1.0))

        # Total state, same composition
        self.Gas_Ambient.TPX = self.Tta, self.Pta, X

    def _get_ambient_mole_fractions_from_static_conditions(self,
                                                           *,
                                                           T_static,
                                                           P_static,
                                                           RH=None,
                                                           H2O_vol_pct=None,
                                                           H2O_mass_pct=None):
        """
        Return humid-air mole fractions based on static ambient T/P.
        """

        n_given = sum(v is not None for v in [RH, H2O_vol_pct, H2O_mass_pct])

        if n_given > 1:
            raise ValueError("Specify only one of RH, H2O_vol_pct, or H2O_mass_pct")

        # dry_X = {
        #     "CO2": 0.000412,
        #     "O2":  0.20946,
        #     "AR":  0.00934,
        #     "N2":  0.78084,
        # }
        dry_X = c.s_air_composition_mole

        if n_given == 0:
            return dry_X

        if RH is not None:
            x_H2O = self._x_H2O_from_RH(T_static, P_static, RH)

        elif H2O_vol_pct is not None:
            x_H2O = H2O_vol_pct / 100.0

        else:
            x_H2O = self._x_H2O_from_mass_pct(
                T_static,
                P_static,
                H2O_mass_pct,
                dry_X,
            )

        x_sat = self._x_H2O_saturation(T_static, P_static)

        # gas-only model: clamp oversaturation
        x_H2O = min(x_H2O, x_sat)

        X = {
            sp: x * (1.0 - x_H2O)
            for sp, x in dry_X.items()
        }
        X["H2O"] = x_H2O

        self.RH = 100.0 * x_H2O / x_sat if x_sat > 0 else 0.0

        return X

    def _x_H2O_from_RH(self, T, P, RH):
        if RH < 0.0:
            raise ValueError("RH must be >= 0")

        return (RH / 100.0) * self._x_H2O_saturation(T, P)

    def _x_H2O_from_mass_pct(self, T, P, H2O_mass_pct, dry_X):
        if not (0.0 <= H2O_mass_pct < 100.0):
            raise ValueError("H2O_mass_pct must be in [0, 100)")

        y_H2O = H2O_mass_pct / 100.0

        dry_Y = self._dry_X_to_Y(T, P, dry_X)

        Y = {
            sp: y * (1.0 - y_H2O)
            for sp, y in dry_Y.items()
        }
        Y["H2O"] = y_H2O

        self.Gas_Ambient.TPY = T, P, Y

        return self.Gas_Ambient.X[self.Gas_Ambient.species_index("H2O")]

    def _dry_X_to_Y(self, T, P, dry_X):
        self.Gas_Ambient.TPX = T, P, dry_X

        return {
            sp: self.Gas_Ambient.Y[self.Gas_Ambient.species_index(sp)]
            for sp in dry_X
        }

    def _x_H2O_saturation(self, T, P):
        """
        Saturation mole fraction of water vapor at static T/P.
        """

        if T <= 273.16:
            raise ValueError("Gas-only humidity model does not handle ice conditions")

        if T >= 647.096:
            return 1.0

        water = ct.Water()
        water.TQ = T, 1.0
        p_sat = water.P_sat

        if p_sat >= P:
            return 1.0

        return p_sat / P

    def Run(self, Mode, PointTime):
        # if Mode == 'DP':  # alway reset de DP conditions
        #     self.Altitude = self.Altitude_des
        #     self.Macha = self.Macha_des
        #     self.dTs = self.dTs_des
        #     self.Psa = self.Psa_des      # if None then this will override value from standard atmosphere Alt, Machm dTs
        #     self.Tsa = self.Tsa_des      # if None then this will override value from standard atmosphere Alt, Machm dTs
            # create separate Cantera phase object for Ambient, to be used by components if needed
            # self.Gas_Ambient = ct.Solution('jetsurf.yaml')
            # create Cantera quantity object for Ambient (mass = 1 per default)
            # this quantity is then further copied along the gaspath in the system model
            # self.Gas_Ambient = ct.Quantity(self.owner.gas)
            # self.owner.gaspath_conditions[self.station_nr] = self.Gas_Ambient

        # if self.Tsa == None:
        #     # Tsa not defined, use standard atmosphere
        #     self.Tsa = ac.std_atm.alt2temp(self.Altitude, alt_units='m', temp_units='K')
        #     # for standard atmosphere, use dTs if defined
        #     if self.dTs != None:
        #         self.Tsa = self.Tsa + self.dTs
        # if self.Psa == None:
        #     # Ps0 not defined, used standard atmosphere
        #     self.Psa = ac.std_atm.alt2press(self.Altitude, alt_units='m', press_units='pa')
        # self.Tta = self.Tsa * ( 1 + 0.2 * self.Macha**2)
        # self.Pta = self.Psa * ((self.Tta/self.Tsa)**3.5)
        # # set values in the Gas_Ambient phase object conditions
        # self.Gas_Ambient.TPY = self.Tta, self.Pta, c.s_air_composition_mass
        # self.V = self.Macha * ac.std_atm.temp2speed_of_sound(self.Tsa, speed_units = 'm/s', temp_units = 'K')

        H2O_in_mass = self.Gas_Ambient.phase["H2O"].Y[0]
        return

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
            f"RH{s}": self.RH
        }

    def get_station_nr(self):
        return self.station_nr

    def set_station_nr(self, station_nr):
        self.station_nr = station_nr
