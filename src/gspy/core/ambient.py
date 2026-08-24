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

from statistics import mode

import cantera as ct
import aerocalc as ac     # !!!! install with "pip install aero-calc", see https://www.kilohotel.com/python/aerocalc/html/
from gspy.core.base_component import TComponent
import gspy.core.utils as fu
import gspy.core.constants as c
from gspy.core.flow_state import TFlowState

class TAmbient(TComponent):
    def __init__(self, 
                 *,
                 station_nr, 
                 Altitude, 
                 Macha, 
                 dTs, 
                 Psa, 
                 Tsa, 
                 RH=None,
                #  RH=0,
                 ambient_output_species = None,
                 **kwargs):
        super().__init__(**kwargs)
        self.station_nr = station_nr

        self.humidity_mode_des = None
        self.humidity_value_des = None
        self.humidity_mode = None
        self.humidity_value = None

        # create Cantera quantity object for Ambient (mass = 1 per default)
        # this quantity is then further copied along the gaspath in the system model
        
        # GC
        # self.Gas_Ambient = ct.Quantity(self.owner.gas)
        self.fs_ambient = TFlowState.from_RH(self.system.gas, 1, station_nr,
                                            # i_H2O=self.system.i_H2O,
                                            T=288.15, 
                                            P=101325, 
                                            RH=RH, 
                                            dry_X=self.system.air_X)

        self.system.gaspath_conditions[self.station_nr] = self.fs_ambient

        self.fs_out_output_species = list(ambient_output_species or [])
        self.fs_out_output_species_indices = [
            c.LIQUID_WATER_INDEX if sp.upper() == "H2O_LIQ"
            else self.system.gas.species_index(sp)
            for sp in self.fs_out_output_species
        ]

        self.SetConditions('Init', Altitude, Macha, dTs, Psa, Tsa, RH=RH)

        self.system.ambient = self

    def _get_ambient_mole_fractions_from_static_conditions(self):
        """
        Return humid ambient composition as mole fractions, based on
        static ambient conditions Tsa / Psa and the stored humidity spec.
        """

        # no humidity specified -> dry air
        if self.humidity_mode is None:
            return dict(self.system.air_X)

        # ----------------------------------------------------------
        # Relative humidity [%]
        # ----------------------------------------------------------
        if self.humidity_mode == "RH":
            # water = ct.Water()
            # water.TQ = self.Tsa, 1.0
            # p_sat = water.P_sat
            p_sat = self.fs_ambient.water_saturation_pressure(self.Tsa)

            p_h2o = (self.humidity_value / 100.0) * p_sat
            x_h2o = p_h2o / self.Psa

            if not (0.0 <= x_h2o < 1.0):
                raise ValueError(f"Invalid RH gives x_h2o={x_h2o:.6f}")

            X = {k: v * (1.0 - x_h2o) for k, v in self.system.air_X.items()}
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

            X = {k: v * (1.0 - x_h2o) for k, v in self.system.air_X.items()}
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

            Y = {k: v * (1.0 - y_h2o) for k, v in self.system.air_Y.items()}
            Y["H2O"] = y_h2o

            # temporary set state to convert Y -> X
            self.fs_ambient.TPY = self.Tsa, self.Psa, Y
            # ????? return dict(zip(self.Gas_Ambient.species_names, self.Gas_Ambient.X))
            return self.fs_ambient.X

        raise ValueError(f"Unknown humidity_mode '{self.humidity_mode}'")


    def SetConditions(self, Mode, Altitude, Macha, dTs, Psa, Tsa,
                      *, 
                      RH=None, 
                      H2O_mass_pct=None, 
                      H2O_vol_pct=None,
                      enable_liquid_water = None):

        self.RH = RH

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

        #  2.1
        if enable_liquid_water is None:
            self.fs_ambient.enable_liquid_water = self.system.sys_enable_liquid_water
        else:
            self.fs_ambient.enable_liquid_water = enable_liquid_water

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
        self.fs_ambient.TPX = self.Tsa, self.Psa, X
        cp = self.fs_ambient.gas_q.cp_mass
        cv = self.fs_ambient.gas_q.cv_mass
        gamma = cp / cv

        # 3) static velocity
        a_s = self.fs_ambient.gas_q.sound_speed
        self.V = self.Macha * a_s

        # make V available in the TFlowState for convenience
        self.fs_ambient.velocity = self.V

        # 4) total conditions using humid-air gamma
        self.Tta = self.Tsa * (1.0 + 0.5 * (gamma - 1.0) * self.Macha**2)
        self.Pta = self.Psa * (self.Tta / self.Tsa)**(gamma / (gamma - 1.0))

        self.fs_ambient.set_conditions_humidity(
            T=self.Tsa,
            P=self.Psa,
            total_mass=1.0,
            humidity_mode=hum_mode,
            humidity_value=hum_value,
            dry_X_dict=self.system.air_X,
            dry_Y_dict=self.system.air_Y)   
        return     

    def Run(self, Mode, PointTime):
        Q_ambient = self.CalculateHeatTransfer(self.fs_ambient, fu.HeatTransferLocation.AMBIENT)

        # if Mode == 'DP':  # alway reset de DP conditions
        #     self.Altitude = self.Altitude_des
        #     self.Macha = self.Macha_des
        #     self.dTs = self.dTs_des
        #     self.Psa = self.Psa_des      # if None then this will override value from standard atmosphere Alt, Machm dTs
        #     self.Tsa = self.Tsa_des      # if None then this will override value from standard atmosphere Alt, Machm dTs
        #     # create separate Cantera phase object for Ambient, to be used by components if needed
        #     # self.Gas_Ambient = ct.Solution('jetsurf.yaml')
        #     # create Cantera quantity object for Ambient (mass = 1 per default)
        #     # this quantity is then further copied along the gaspath in the system model
        #     # 2.1 obsolete
        #     # self.Gas_Ambient = ct.Quantity(self.owner.gas)
        #     # self.owner.gaspath_conditions[self.station_nr] = self.Gas_Ambient
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

# # 2.0.0.1
# if self.humidity_mode == "RH":
#     w = ct.Water()
#     w.TQ = self.Tsa, 1.0
#     p_sat = w.P_sat
#     x_h2o = (self.humidity_value / 100.0) * p_sat / self.Psa

#     X = {k: v * (1.0 - x_h2o) for k, v in c.air_composition_moles.items()}
#     X["H2O"] = x_h2o

#     self.Gas_Ambient.TPX = self.Tsa, self.Psa, X

# elif self.humidity_mode == "H2O_vol_pct":
#     x_h2o = self.humidity_value / 100.0

#     X = {k: v * (1.0 - x_h2o) for k, v in c.air_composition_moles.items()}
#     X["H2O"] = x_h2o

#     self.Gas_Ambient.TPX = self.Tta, self.Pta, X

# elif self.humidity_mode == "H2O_mass_pct":
#     y_h2o = self.humidity_value / 100.0

#     Y = {k: v * (1.0 - y_h2o) for k, v in c.s_air_composition_mass.items()}
#     Y["H2O"] = y_h2o

#     self.Gas_Ambient.TPY = self.Tta, self.Pta, Y

# else:
#     self.Gas_Ambient.TPY = self.Tta, self.Pta, c.s_air_composition_mass

        # self.V = self.Macha * ac.std_atm.temp2speed_of_sound(self.Tsa, speed_units = 'm/s', temp_units = 'K')
        return

     # 2.0.0.0
    def get_outputs(self):
        out = super().get_outputs()
        s = self.station_nr

        out[f"Alt"] = self.Altitude
        out[f"Ts{s}"] = self.Tsa
        out[f"Ps{s}"] = self.Psa
        out[f"Tt{s}"] = self.Tta
        out[f"Pt{s}"] = self.Pta
        out[f"dTs{s}"] = self.dTs
        out[f"Mach{s}"] = self.Macha
        out[f"RH{s}"] = self.RH

        for sp, idx in zip(self.fs_out_output_species,
                        self.fs_out_output_species_indices):
            if idx == c.LIQUID_WATER_INDEX:
                value = self.fs_ambient.m_liq
            else:
                # correct gas mass fractions (gas_q.Y) to total mass fractions (including liquid water) by dividing by total mass
                value = self.fs_ambient.gas_q.Y[idx] * self.fs_ambient.gas_q.mass / self.fs_ambient.W
            out[f"Y{s}_{sp}"] = value
        return out  

    def get_output_units(self):
        units = super().get_output_units()

        s = self.station_nr

        units[f"Alt"] = "[m]"
        units[f"Ts{s}"] = "[K]"
        units[f"Ps{s}"] = "[Pa]"
        units[f"Tt{s}"] = "[K]"
        units[f"Pt{s}"] = "[Pa]"
        units[f"dTs{s}"] = "[K]"
        units[f"Mach{s}"] = "[-]"
        units[f"RH{s}"] = "[%]"

        for sp in self.fs_out_output_species:
            units[f"Y{s}_{sp}"] = "[-]"
        return units      

    # obsolete
    # def get_station_nr(self):
    #     return self.station_nr

    # def set_station_nr(self, station_nr):
    #     self.station_nr = station_nr
