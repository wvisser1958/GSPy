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
from gspy.core.base_component import TComponent
from gspy.core.flow_state import TFlowState
import gspy.core.utils as fu
import gspy.core.constants as c

class TGaspath(TComponent):
    def __init__(self, 
                 *,
                 station_in, 
                 station_out,
                 fs_out_output_species = None,
                 enable_liquid_water = None,
                 **kwargs):    # Constructor of the class
        super().__init__(**kwargs)
        self.station_in = station_in
        self.station_out = station_out
        # set design properties to None, if still None in PrintPerformance,
        # then not assigned anywhere so no need to Print/output.
        self.fs_in = None
        self.fs_in_des = None
        self.fs_out = None
        # fs_in_q is a 'scratch' TFlowState for heat transfer between entry and start of process (e.g. compression, expansion)
        self.fs_in_q = None
        self.fs_in_des_q = None
        self.PRdes = 1
        self.PR = None
        # 1.6.0.5
            # self.W = None
            # self.Wgas = None
        # 2.0.0.2
        self.fs_out_output_species = list(fs_out_output_species or [])
        self.fs_out_output_species_indices = [
            c.LIQUID_WATER_INDEX if sp.upper() == "H2O_LIQ"
            else self.system.gas.species_index(sp)
            for sp in self.fs_out_output_species
        ]
        #  2.1
        if enable_liquid_water is None:
            self.enable_liquid_water = self.system.sys_enable_liquid_water
        else:
            self.enable_liquid_water = enable_liquid_water

        self.fs_in_des = TFlowState.create_empty(self.system.gas, 
                                                 station_nr=self.station_in,
                                                 enable_liquid_water=self.enable_liquid_water)
        self.fs_out = TFlowState.create_empty(self.system.gas, 
                                              station_nr=self.station_out, 
                                              enable_liquid_water=self.enable_liquid_water)

    def Run(self, Mode, PointTime):
        self.fs_in = self.system.gaspath_conditions[self.station_in]

        if Mode == 'DP':
            self.fs_in_des.copy_from(self.fs_in, self.station_in)

        self.fs_out.copy_from(self.fs_in, self.station_out, overrule_enable_liquid_water=self.enable_liquid_water)

        # if heathpaths, add Q
        self.Add_Q_to_fs_in_q(Mode)

        self.system.gaspath_conditions[self.station_out] = self.fs_out
        return self.fs_out

    def Add_Q_to_fs_in_q(self, Mode):
        # Heat transfer with heat sink components
        if self.fs_in_q is None:
            # create fs_in_q
            self.fs_in_q = TFlowState.create_empty(
                self.fs_in.gas,
                station_nr=self.fs_in.station_nr
            )
        # copy from fs_in
        self.fs_in_q.copy_from(
            self.fs_in,
            str(self.fs_in.station_nr) + '_hx',
        )
        if Mode == 'DP':
            if self.fs_in_des_q is None:
                # create fs_in_q
                self.fs_in_des_q = TFlowState.create_empty(
                    self.fs_in.gas,
                    station_nr=self.fs_in.station_nr
                )
            # copy from fs_in
            self.fs_in_des_q.copy_from(
                self.fs_in,
                str(self.fs_in.station_nr) + '_hx',
            )

        # if heathpaths, add Q
        if self.heatpaths:
            Qhs_in = self.CalculateHeatTransfer(self.fs_in, fu.HeatTransferLocation.INLET)
            self.fs_in_q.HP = (
                self.fs_in_q.H_total + Qhs_in,
                self.fs_in_q.P,
            )

    def Add_Q_to_fs_out(self):
        # if heathpaths, add Q
        if self.heatpaths:
            Qhs_out = self.CalculateHeatTransfer(self.fs_out, fu.HeatTransferLocation.OUTLET)
            self.fs_out.HP = (
                self.fs_out.H_total + Qhs_out,
                self.fs_out.P
            )

    def PrintPerformance(self, Mode, PointTime):
        super().PrintPerformance(Mode, PointTime)
        print(f"\tInlet conditions:")
        print(f"\t\tMass flow  : {self.fs_in.W:.2f} kg/s")
        print(f"\t\tTemperature: {self.fs_in.T:.1f} K")
        print(f"\t\tPressure   : {self.fs_in.P:.0f} Pa")
        if self.fs_in_des.Wc != None:
            print(f"\tDP Corr.Mass flow  : {self.fs_in_des.Wc:.2f} kg/s")
        if self.fs_in.Wc != None:
            print(f"\tCorr.Mass flow  : {self.fs_in.Wc:.2f} kg/s")
        if self.PRdes != None:
            print(f"\tDP Pressure ratio  : {self.PRdes:.4f}")
        if self.PR != None:
            print(f"\tPressure ratio  : {self.PR:.4f}")
        print(f"\tExit conditions:")
        print(f"\t\tTemperature: {self.fs_out.T:.1f} K")
        print(f"\t\tPressure   : {self.fs_out.P:.0f} Pa")

    # not used ?
    # def _get_species_outputs(self, gas_quantity, station, basis="mass", prefix=None):
    #     out = {}

    #     if gas_quantity is None:
    #         return out

    #     gas = gas_quantity.phase

    #     if basis == "mass":
    #         values = gas.Y
    #         names = gas.species_names
    #         key_prefix = "Y" if prefix is None else prefix
    #     elif basis == "mole":
    #         values = gas.X
    #         names = gas.species_names
    #         key_prefix = "X" if prefix is None else prefix
    #     else:
    #         raise ValueError("basis must be 'mass' or 'mole'")

    #     for species, value in zip(names, values):
    #         out[f"{key_prefix}_{species}_{station}"] = float(value)

    #     return out

    def get_flowstate_mass_fractions(self, out, fs : TFlowState, station_nr):
        #  mass fraction outputs for specified species in fs
        gas_q = fs.gas_q
        Y = gas_q.Y          # or gas_q.phase.Y if needed
        m_gas = gas_q.mass
        m_total = fs.W
        if m_total > 0.0:
            for sp, idx in zip(self.fs_out_output_species,
                            self.fs_out_output_species_indices):
                if idx == c.LIQUID_WATER_INDEX:
                    value = fs.m_liq / m_total
                else:
                    value = Y[idx] * m_gas / m_total
                out[f"Y{station_nr}_{sp}"] = value
        else:
            for sp in self.fs_out_output_species:
                out[f"Y{station_nr}_{sp}"] = 0.0

    def get_outputs(self):
        out = super().get_outputs()

        s_in = self.station_in

        # out[f"W{s_in}"] = fu.scalar(self.fs_in.mass)
        out[f"W{s_in}"] = self.fs_in.W
        out[f"T{s_in}"] = self.fs_in.T
        out[f"P{s_in}"] = self.fs_in.P
        out[f"Wc{s_in}"] = self.fs_in.Wc

        if self.PR is not None:
            out[f"PR{self.id}"] = self.PR

        # #  2.0.0.2 mass fraction outputs for specified species in fs_out
        # s_out = self.station_out
        # fs_out = self.fs_out
        # gas_q = fs_out.gas_q
        # Y = gas_q.Y          # or gas_q.phase.Y if needed
        # m_gas = gas_q.mass
        # m_total = fs_out.W
        # if m_total > 0.0:
        #     for sp, idx in zip(self.fs_out_output_species,
        #                     self.fs_out_output_species_indices):
        #         if idx == c.LIQUID_WATER_INDEX:
        #             value = fs_out.m_liq / m_total
        #         else:
        #             value = Y[idx] * m_gas / m_total
        #         out[f"Y{s_out}_{sp}"] = value
        # else:
        #     for sp in self.fs_out_output_species:
        #         out[f"Y{s_out}_{sp}"] = 0.0
        self.get_flowstate_mass_fractions(out, self.fs_out, self.station_out)

        return out



