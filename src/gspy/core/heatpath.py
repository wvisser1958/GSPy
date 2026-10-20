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
import cantera as ct
from abc import ABC, abstractmethod
from dataclasses import dataclass
from gspy.core.system import TSystemModel
from gspy.core.base_component import TComponent
from gspy.core.ambient import TAmbient
from gspy.core.gaspath import TGaspath
from gspy.core.heatsink import THeatsink
from gspy.core.utils import HeatTransferLocation
import gspy.core.constants as c
import sympy as sp
from gspy.core.flow_state import TFlowState

#  'sentinel' for validating consistent input
_NOT_SET = object()

@dataclass
class THeatTransferState:
    ht_loc: HeatTransferLocation = None
    a: float = 0.0

    mu: float = 0.0
    Rho: float = 0.0
    c: float = 0.0
    Re: float = 0.0
    Pr: float = 0.0
    Nu_value: float = 0.0

    h_conv: float = 0.0
    h_cond: float = 0.0
    h_total: float = 0.0
    Q_conv_cond: float = 0.0
    Q_rad: float = 0.0
    T_wall: float = 0.0
    Q: float = 0.0

@dataclass
class THeatPathStates:
    inlet: THeatTransferState
    outlet: THeatTransferState    

class THeatpath(ABC):

    def __init__(self, 
                *,
                system: TSystemModel,                   # owning TSystemModel 
                component : TComponent | None = None,   # owning component is a TComponent (e.g. TGaspath, THeatsink, TAmbient) exchanging heat with the heatsink object
                                                        # component later assigned by
                name: str,                              # unique name of the heat path
            heatsink : THeatsink,                       # heat sink component the heat path is connected to  
                a_ht=_NOT_SET,          # heat transfer area (between flow and wall)
                a_flow=_NOT_SET,        # flow cross area (to calculate convection properties from mass flow)
                d_re=_NOT_SET,          # characteristic length for Reynolds nr
                k_gas=_NOT_SET,         # conductivity of the gas
                Nu=_NOT_SET,            # Nusselt expression
                d_mat=_NOT_SET,         # material/wall thickness for conduction
                k_mat=_NOT_SET,         # wall material conductivity
                eps_rad:float = 0.0,    # radiation emissivity (if None, then no radiation heat transfer)
                u_user = _NOT_SET,      # manual user specified overall heat transfer coefficient u: 
                                        # - optional for gaspath components, if not None, 
                                        #   then overruling all above parameters (a_ht, a_flow, d_re, k_gas, Nu, d_mat, k_mat, eps_rad)                q_user,         # manual user specified total heat flux Q 
                Q_user=_NOT_SET,        # if not None, overriding all other parameters
                in_out_split_fraction=None) -> None: 
                                        # factor for splitting heat transfer over start and end of compression, combustion etc.
                                        # 1 = all Q from gas path component entry
                                        # 0 = all Q from gas path component exit
                                        # 0.5 (default is half / half)
                                        # 0.3 0.3 from entry, 0.7 from exit
             
        self.system = system
        self.component = component
        self.name = name
        self.with_heatsink = heatsink

        if (a_ht is not _NOT_SET) and (a_ht <= 0.0):
            raise ValueError(
                f"Heat path {name!r}: a_ht must be greater than zero."
            )

        if not 0.0 <= eps_rad <= 1.0:
            raise ValueError(
                f"Heat path {name!r}: eps_rad must be between 0 and 1."
            )
        
        self._validate_heat_transfer_inputs(
            a_ht=a_ht,
            a_flow=a_flow,
            d_re=d_re,
            k_gas=k_gas,
            Nu=Nu,
            d_mat=d_mat,
            k_mat=k_mat,
            u_user=u_user,
            Q_user=Q_user,
            in_out_split_fraction=in_out_split_fraction
        )

        self.a_ht = None if a_ht is _NOT_SET else a_ht
        self.a_flow = None if a_flow is _NOT_SET else a_flow
        self.d_re = None if d_re is _NOT_SET else d_re
        self.k_gas = None if k_gas is _NOT_SET else k_gas
        self.Nu = None if Nu is _NOT_SET else Nu
        self.d_mat = None if d_mat is _NOT_SET else d_mat
        self.k_mat = None if k_mat is _NOT_SET else k_mat
        self.u_user = None if u_user is _NOT_SET else float(u_user)
        self.Q_user = None if Q_user is _NOT_SET else float(Q_user)
        self.in_out_split_fraction = in_out_split_fraction

        self.eps_rad = float(eps_rad)

        if self.Nu is not None:
            self.Re, self.Pr, self.Ra = sp.symbols("Re Pr Ra")

            self.allowed_symbols = {
                "Re": self.Re,
                "Pr": self.Pr,
                "Ra": self.Ra,
            }

            self.Nu_expr, self.Nu_func = self.compile_nusselt_correlation(self.Nu)
                # example for Nu parameter: "Nu = 0.023 * Re**0.8 * Pr**0.4"
                # now self.Nu_func can be used to calculate Nu like
                # self.Nu_func(4, 5)

    def _validate_heat_transfer_inputs(
        self,
        *,
        a_ht,
        a_flow,
        d_re,
        k_gas,
        Nu,
        d_mat,
        k_mat,
        u_user,
        Q_user,
        in_out_split_fraction,
    ) -> None:

        calculated_u_parameters = {
            "a_flow": a_flow,
            "d_re": d_re,
            "k_gas": k_gas,
            "Nu": Nu,
            "d_mat": d_mat,
            "k_mat": k_mat,
        }

        #  for Q_user, a_ht also superfluous
        calculated_Q_parameters = {
            "a_ht": a_ht,
            **calculated_u_parameters,
        }

        # Q_user overrides all other heat-transfer calculations.
        if Q_user is not _NOT_SET:
            conflicting = [
                name
                for name, value in {
                    **calculated_Q_parameters,
                    "u_user": u_user,
                }.items()
                if value is not _NOT_SET
            ]

            if conflicting:
                raise ValueError(
                    f"Heat path {self.name!r}: Q_user overrides the complete "
                    "heat-transfer calculation. Do not also provide: "
                    f"{', '.join(conflicting)}."
                )

            if not isinstance(Q_user, (int, float)):
                raise TypeError(
                    f"Heat path {self.name!r}: Q_user must be numeric."
                )

        # u_user overrides calculated convection and conduction.
        elif u_user is not _NOT_SET:
            conflicting = [
                name
                for name, value in calculated_u_parameters.items()
                if value is not _NOT_SET
            ]

            if conflicting:
                raise ValueError(
                    f"Heat path {self.name!r}: u_user overrides the calculated "
                    "convection and conduction model. Do not also provide: "
                    f"{', '.join(conflicting)}."
                )

            if not isinstance(u_user, (int, float)):
                raise TypeError(
                    f"Heat path {self.name!r}: u_user must be numeric."
                )

            if u_user < 0.0:
                raise ValueError(
                    f"Heat path {self.name!r}: u_user cannot be negative."
                )

        # Validate the split value itself, if the user supplied it.
        # Whether it is allowed is checked after component connection.
        if in_out_split_fraction is not None:
            if not isinstance(in_out_split_fraction, (int, float)):
                raise TypeError(
                    f"Heat path {self.name!r}: in_out_split_fraction "
                    "must be numeric."
                )

            if not 0.0 <= in_out_split_fraction <= 1.0:
                raise ValueError(
                    f"Heat path {self.name!r}: in_out_split_fraction "
                    "must be between 0 and 1."
                )

    # def _validate_required_inputs_for_component(self) -> None:
    #     # A prescribed total Q or overall U needs no calculated U inputs.
    #     if self.Q_user is not None or self.u_user is not None:
    #         return

    #     if isinstance(self.component, TGaspath):
    #         required = {
    #             "a_flow": self.a_flow,
    #             "d_re": self.d_re,
    #             "k_gas": self.k_gas,
    #             "Nu": self.Nu,
    #             "d_mat": self.d_mat,
    #             "k_mat": self.k_mat,
    #             "in_out_split_fraction": self.in_out_split_fraction
    #         }

    #     elif isinstance(self.component, THeatsink):
    #         required = {
    #             "d_mat": self.d_mat,
    #             "k_mat": self.k_mat,
    #         }

    #     elif isinstance(self.component, TAmbient):
    #         required = {
    #             "a_flow": self.a_flow,
    #             "d_re": self.d_re,
    #             "k_gas": self.k_gas,
    #             "Nu": self.Nu,
    #             "d_mat": self.d_mat,
    #             "k_mat": self.k_mat,
    #         }

    #     else:
    #         return

    #     missing = [
    #         name
    #         for name, value in required.items()
    #         if value is None
    #     ]

    #     if missing:
    #         raise ValueError(
    #             f"Heat path {self.name!r}, connected to "
    #             f"{self.component.name!r}, requires: {', '.join(missing)}."
    #         )
        
    def init_heattransferstates(self, component):
        self.component = component
        if isinstance(component, TGaspath):
            if self.in_out_split_fraction is None:
                raise ValueError(
                    f"Heat path {self.name!r}: in_out_split_fraction not specified")
            self.ht = THeatPathStates(
                inlet=THeatTransferState(ht_loc = HeatTransferLocation.INLET),
                outlet=THeatTransferState(ht_loc = HeatTransferLocation.OUTLET),
            )
            # fixed split of heat transfer between inlet and outlet of connected (gaspathc) component
            self.ht.inlet.a = self.a_ht * self.in_out_split_fraction
            self.ht.outlet.a = self.a_ht * (1 - self.in_out_split_fraction)
        elif isinstance(component, TAmbient):
            if (component.fs_ambient.velocity<0.1) and (self.u_user is None) and (self.Q_user is None):
                raise ValueError(
                    f"Heat path {self.name!r} to Ambient must specify Q_user or u_user if ambient velocity = 0\n(No natural convection model implemented yet)")                
            self.in_out_split_fraction = 1
            self.ht = THeatTransferState(ht_loc = HeatTransferLocation.AMBIENT)
            self.ht.a = self.a_ht
        elif isinstance(component, THeatsink):
            self.in_out_split_fraction = 1
            self.ht = THeatTransferState(ht_loc = HeatTransferLocation.HEATSINK)
            self.ht.a = self.a_ht
            self.hs_comp = component
        else:
            raise ValueError(f'Component in heatpath {self.name} must be either TGasPath, TAmbient or THeatsink')

    def compile_nusselt_correlation(self, equation: str):
        # Allow both "Nu = ..." and plain expression
        if "=" in equation:
            lhs, rhs = equation.split("=", 1)
            if lhs.strip() != "Nu":
                raise ValueError("Left-hand side must be Nu")
            equation = rhs

        expr = sp.sympify(equation, locals = self.allowed_symbols)

        unknowns = expr.free_symbols - {self.Re, self.Pr, self.Ra}
        if unknowns:
            raise ValueError(f"Unknown variables: {unknowns}")

        f = sp.lambdify((self.Re, self.Pr), expr, "math")
        return expr, f

    def calc_Q(self, fs_hx, hx_location: HeatTransferLocation):
        if hx_location == HeatTransferLocation.INLET:
            ht_state = self.ht.inlet
            T_self_hx = fs_hx.T
        elif hx_location == HeatTransferLocation.OUTLET:
            ht_state = self.ht.outlet
            T_self_hx = fs_hx.T
        elif hx_location == HeatTransferLocation.AMBIENT:
            ht_state = self.ht
            T_self_hx = fs_hx.T
        elif hx_location == HeatTransferLocation.HEATSINK:
            ht_state = self.ht
            T_self_hx = self.hs_comp.T
        else:
            raise ValueError("Invalid HeatTransferLocation in HeatPath calc_C") 

        if self.Q_user:
            # total Q for hx to component given: must split in case of inlet / outlet here:
            if hx_location == HeatTransferLocation.INLET:
                ht_state.Q = self.Q_user * self.in_out_split_fraction
            elif hx_location == HeatTransferLocation.OUTLET:
                ht_state.Q = self.Q_user * (1 - self.in_out_split_fraction)
            else:     
                ht_state.Q = self.Q_user
        else:
            if self.u_user:
                # user given u_user overriding the rest....
                ht_state.Q = self.u_user * ht_state.a * (self.with_heatsink.T - T_self_hx)
                ht_state.h_total = self.u_user                
            else:
                # calculate the heat transfer from the gas to the wall (convection) and through the wall (conduction)
                ht_state.mu = fs_hx.gas_q.viscosity
                ht_state.Rho = fs_hx.gas_q.density
                if hx_location == HeatTransferLocation.AMBIENT:
                    ht_state.c = ht_state.c = fs_hx.velocity
                else:        
                    ht_state.c = fs_hx.gas_q.mass/self.a_flow/ht_state.Rho
                ht_state.Re = ht_state.Rho * ht_state.c * self.d_re / ht_state.mu
                ht_state.Pr = ht_state.mu * fs_hx.gas_q.cp / fs_hx.gas_q.thermal_conductivity 
                ht_state.Nu_value = self.Nu_func(ht_state.Re, ht_state.Pr)

                ht_state.h_conv = ht_state.Nu_value * self.k_gas / self.d_re
                ht_state.h_cond = self.k_mat / self.d_mat
                ht_state.h_total = 1 / (1/ht_state.h_conv + 1/ht_state.h_cond)
                
                # heat going into the gas is positive, so:
                ht_state.Q_conv_cond = ht_state.h_total * ht_state.a * (self.with_heatsink.T - T_self_hx)

                # now with the calculated Q_conv_cond, we can calculate the wall temperature T_wall for radiation            
                # Q_conv_cond  = (T_heatsink-T_wall)*A*h__cond, so
                if math.isclose(ht_state.h_cond, 0.0, abs_tol=1e-12) or math.isclose(ht_state.a, 0.0, rel_tol=1e-12):
                    ht_state.T_wall = self.with_heatsink.T # assume temperature of heat sink
                else:
                    ht_state.T_wall = self.with_heatsink.T - ht_state.Q_conv_cond/ht_state.a/ht_state.h_cond
            
                # radiation heat transfer (from wall to ambient) is not yet included in the Q calculation
                ht_state.Q_rad = self.eps_rad * c.C_StefanBoltzmann * ht_state.a * (ht_state.T_wall**4-T_self_hx**4)  
                ht_state.Q = ht_state.Q_conv_cond + ht_state.Q_rad

        self.with_heatsink.Q_balance -= ht_state.Q
        return ht_state.Q

    def Print_Inlet_or_Outlet_hx_performance(self, ht):
        print(f"Heat path {ht.name} {self.name}:")
        print(f"a: {ht.a}")
        print(f"Nu: {ht.Nu_value}")
        print(f"h_conv: {ht.h_conv}")
        print(f"h_cond: {ht.h_cond}")
        print(f"Q_conv_cond: {ht.Q_conv_cond}")
        print(f"T_wall: {ht.T_wall}")
        print(f"Q_rad: {ht.Q_rad}")

    def PrintPerformance(self):
        if isinstance(self.ht, THeatPathStates):
            print(f"\t\tQ inlet : {self.ht.inlet.Q:.0f} W")
            print(f"\t\tQ outlet: {self.ht.outlet.Q:.0f} W")
            print(f"\t\tQ total : {self.ht.inlet.Q + self.ht.outlet.Q:.0f} W")
        else:   # ht is a single THeatTransferState 
            print(f"\t\tQ  : {self.ht.Q:.0f} W")
        if self.system.debug_output:
            if isinstance(self.ht, THeatPathStates):
                self.Print_Inlet_or_Outlet_hx_performance(ht = self.ht.inlet)
                self.Print_Inlet_or_Outlet_hx_performance(ht = self.ht.outlet)
            else:
                self.Print_Inlet_or_Outlet_hx_performance(ht = self.ht)

    def Get_Inlet_or_Outlet_Output(self, ht, out):
        loc_value = ht.ht_loc.value
        if self.system.debug_output:
            out[f"a_{loc_value} {self.name}"] = ht.a
            out[f"Nu_{loc_value}"] = ht.Nu_value
            out[f"hs_conv_{loc_value} {self.name}"] = ht.h_conv
            out[f"hs_cond_{loc_value} {self.name}"] = ht.h_cond
            out[f"T_wall_{loc_value} {self.name}"] = ht.T_wall
            out[f"Q_rad_{loc_value} {self.name}"] = ht.Q_rad
        out[f"Q_{loc_value} {self.name}"] = ht.Q

    def get_outputs(self):
        out = {}

        if self.system.debug_output:
            if self.with_heatsink is not None:
                out[f"hx_with_{self.name}"] = self.with_heatsink.name
            if self.a_ht is not None:
                out[f"a_ht_{self.name}"] = self.a_ht
            if self.a_flow is not None:
                out[f"a_flow_{self.name}"] = self.a_flow
            if self.d_re is not None:
                out[f"d_re_{self.name}"] = self.d_re
            if self.k_gas is not None:
                out[f"k_gas_{self.name}"] = self.k_gas
            if self.Nu is not None:
                out[f"Nu_{self.name}"] = self.Nu
            if self.d_mat is not None:
                out[f"d_mat_{self.name}"] = self.d_mat
            if self.k_mat is not None:
                out[f"k_mat_{self.name}"] = self.k_mat
            if self.eps_rad is not None:
                out[f"eps_rad_{self.name}"] = self.eps_rad
            if self.u_user is not None:
                out[f"u_user_{self.name}"] = self.u_user
            if self.Q_user is not None:
                out[f"Q_user_{self.name}"] = self.Q_user

        if isinstance(self.ht, THeatPathStates):
            self.Get_Inlet_or_Outlet_Output(self.ht.inlet, out)
            self.Get_Inlet_or_Outlet_Output(self.ht.outlet, out)
            out[f"Q_total {self.name}"] = self.ht.inlet.Q + self.ht.outlet.Q
        else:
            self.Get_Inlet_or_Outlet_Output(self.ht, out)

        return out

    def Get_Inlet_or_Outlet_Output_units(self, ht, units):
        loc_value = ht.ht_loc.value
        if self.system.debug_output:
            units[f"a_{loc_value} {self.name}"] = "[m2]"
            units[f"Nu_{loc_value}"] = "[-]"
            units[f"hs_conv_{loc_value} {self.name}"] = "[W/m2/K]"
            units[f"hs_cond_{loc_value} {self.name}"] = "[W/m2/K]"
            units[f"T_wall_{loc_value} {self.name}"] = "[K]"
            units[f"Q_rad_{loc_value} {self.name}"] = "[W]"
        units[f"Q_{loc_value} {self.name}"] = "[W]"
    
    def get_output_units(self):
        units = {}

        if self.system.debug_output:
            if self.a_ht is not None:
                units[f"a_ht_{self.name}"] = "[m2]"
            if self.a_flow is not None:
                units[f"a_flow_{self.name}"] = "[m2]"
            if self.d_re is not None:
                units[f"d_re_{self.name}"] = "[m]"
            if self.k_gas is not None:
                units[f"k_gas_{self.name}"] = "[W/m/K]"
            if self.Nu is not None:
                units[f"Nu_{self.name}"] = "[-]"
            if self.d_mat is not None:
                units[f"d_mat_{self.name}"] = "[m]"
            if self.k_mat is not None:
                units[f"k_mat_{self.name}"] = "[W/m/K]"
            if self.eps_rad is not None:
                units[f"eps_rad_{self.name}"] = "[-]"
            if self.u_user is not None:
                units[f"u_user_{self.name}"] = "[W/m2/K]"
            if self.Q_user is not None:
                units[f"Q_user_{self.name}"] = "[kW]"

        if isinstance(self.ht, THeatPathStates):
            self.Get_Inlet_or_Outlet_Output_units(self.ht.inlet, units)
            self.Get_Inlet_or_Outlet_Output_units(self.ht.outlet, units)
            units[f"Q_total {self.name}"] = "[W]"
        else:
            self.Get_Inlet_or_Outlet_Output_units(self.ht, units)

        return units
