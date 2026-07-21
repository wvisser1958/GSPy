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
from gspy.core.base_component import TComponent
from gspy.core.ambient import TAmbient
from gspy.core.gaspath import TGaspath
from gspy.core.heatsink import THeatsink
import gspy.core.utils as fu
import gspy.core.constants as c
import sympy as sp
from gspy.core.flow_state import TFlowState

@dataclass
class THeatTransferState:
    name: str = ""
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
                system,         # owning TSystemModel 
                component : TComponent = None,      # owning component is a TComponent (e.g. TGaspath, THeatsink, TAmbient) exchanging heat with the heatsink object
                                                    # component later assigned by
                name,                               # unique name of the heat path
                heatsink : THeatsink,               # heat sink component the heat path is connected to  
                a_ht,           # heat transfer area (between flow and wall)
                a_flow,         # flow cross area (to calculate convection properties from mass flow)
                d_re,           # characteristic length for Reynolds nr
                k_gas,          # conductivity of the gas
                Nu,             # Nusselt expression
                d_mat,          # material/wall thickness for conduction
                k_mat,          # wall material conductivity
                eps_rad = None, # radiation emissivity (if None, then no radiation heat transfer)
                h_user = None,  # manual user specified heat transfer coefficient h: 
                                # - optional for gaspath components, if not None, 
                                #   then overruling all above parameters (a_ht, a_flow, d_re, k_gas, Nu, d_mat, k_mat, eps_rad)                q_user,         # manual user specified total heat flux Q 
                Q_user = None,  # if not None, overriding all other parameters
                in_out_split_fraction = 0.5):   # factor for splitting heat transfer over start and end of compression, combustion etc.
                                                # 1 = all Q from gas path component entry
                                                # 0 = all Q from gas path component exit
                                                # 0.5 (default is half / half)
                                                # 0.3 0.3 from entry, 0.7 from exit
        # if not isinstance(heatsink, TComponent):
        #     raise TypeError(
        #         f"heatsink or ambient must be a TComponent, got {type(heatsink).__name__}"
        #     )       
        # if isinstance(owner, TGaspath):
        #     if not isinstance(heatsink, THeatsink): 
        #         raise TypeError(
        #             f"Gaspath component heat path must connect with THeatsink, got {type(heatsink).__name__}"
        #         )       
        # if isinstance(owner, THeatsink):
        #     if not isinstance(heatsink, TAmbient): 
        #         raise TypeError(
        #             f"Heatsink component heat path must connect with TAmbient, got {type(heatsink).__name__}"
        #         )      
             
        self.system = system
        self.component = component
        self.name = name

        self.hx_with = heatsink
        self.a_ht = a_ht
        self.a_flow = a_flow    
        self.d_re = d_re   
        self.k_gas = k_gas   
        self.Nu = Nu   
        self.d_mat = d_mat   
        self.k_mat = k_mat   
        self.eps_rad = eps_rad   

        self.h_user = h_user
        self.Q_user = Q_user   
        self.in_out_split_fraction = in_out_split_fraction

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

        self.ht = THeatPathStates(
            inlet=THeatTransferState(name = "inlet"),
            outlet=THeatTransferState(name = "outlet"),
        )
        # fixed split of heat transfer between inlet and outlet of connected (gaspathc) component
        self.ht.inlet.a = self.a_ht * self.in_out_split_fraction
        self.ht.outlet.a = self.a_ht * (1 - self.in_out_split_fraction)

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

    def calc_Q(self, fs_hx, inlet_or_outlet):
        if inlet_or_outlet == 'inlet':
            ht_state = self.ht.inlet
        else:
            ht_state = self.ht.outlet

        if self.Q_user:
            if inlet_or_outlet == 'inlet':
                ht_state.Q = self.Q_user * self.in_out_split_fraction
            else:
                ht_state.Q = self.Q_user * (1 - self.in_out_split_fraction)
        else:
            if self.h_user:
                # user given h_user overriding the rest....
                ht_state.Q = self.h_user * ht_state.a * (fs_hx.T - self.hx_with.T)
                ht_state.h_total = self.h_user                
            else:
                # calculate the heat transfer from the gas to the wall (convection) and through the wall (conduction)
                ht_state.mu = fs_hx.gas_q.viscosity
                ht_state.Rho = fs_hx.gas_q.density
                ht_state.c = fs_hx.gas_q.mass/self.a_flow/ht_state.Rho
                ht_state.Re = ht_state.Rho * ht_state.c * self.d_re / ht_state.mu
                ht_state.Pr = ht_state.mu * fs_hx.gas_q.cp / fs_hx.gas_q.thermal_conductivity 
                ht_state.Nu_value = self.Nu_func(ht_state.Re, ht_state.Pr)

                ht_state.h_conv = ht_state.Nu_value * self.k_gas / self.d_re
                ht_state.h_cond = self.k_mat / self.d_mat
                ht_state.h_total = 1 / (1/ht_state.h_conv + 1/ht_state.h_cond)
                
                # heat going into the gas is positive, so:
                ht_state.Q_conv_cond = ht_state.h_total * ht_state.a * (self.hx_with.T - fs_hx.T)

                # now with the calculated Q_conv_cond, we can calculate the wall temperature T_wall for radiation            
                # Q_conv_cond  = (T_heatsink-T_wall)*A*h__cond, so
                if math.isclose(ht_state.h_cond, 0.0, abs_tol=1e-12) or math.isclose(ht_state.a, 0.0, rel_tol=1e-12):
                    ht_state.T_wall = self.hx_with.T # assume temperature of heat sink
                else:
                    ht_state.T_wall = self.hx_with.T - ht_state.Q_conv_cond/ht_state.a/ht_state.h_cond
            
                # radiation heat transfer (from wall to ambient) is not yet included in the Q calculation
                ht_state.Q_rad = self.eps_rad * c.C_StefanBoltzmann * ht_state.a * (ht_state.T_wall**4-fs_hx.T**4)  
                ht_state.Q = ht_state.Q_conv_cond + ht_state.Q_rad

        # take fraction according to location_factor
        # if inlet_or_outlet == 'inlet':
        #     self.Q = Q_total * self.in_out_split_fraction
        # elif inlet_or_outlet == 'outlet':
        #     self.Q = Q_total * (1-self.in_out_split_fraction)
        self.hx_with.Q_balance += ht_state.Q
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
        self.Print_Inlet_or_Outlet_hx_performance(ht = self.ht.inlet)
        self.Print_Inlet_or_Outlet_hx_performance(ht = self.ht.outlet)

    def Get_Inlet_or_Outlet_Output(self, ht, out):
        out[f"a_{ht.name} {self.name}"] = ht.a
        out[f"Nu_{ht.name} {self.name}"] = ht.Nu_value
        out[f"hs_conv_{ht.name} {self.name}"] = ht.h_conv
        out[f"hs_cond_{ht.name} {self.name}"] = ht.h_cond
        out[f"T_wall_{ht.name} {self.name}"] = ht.T_wall
        out[f"Q_rad_{ht.name} {self.name}"] = ht.Q_rad
        out[f"Q_{ht.name} {self.name}"] = ht.Q

    def get_outputs(self):
        out = {}

        if self.hx_with is not None:
            out[f"hx_with_{self.name}"] = self.hx_with.name
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
        if self.h_user is not None:
            out[f"h_user_{self.name}"] = self.h_user
        if self.Q_user is not None:
            out[f"Q_user_{self.name}"] = self.Q_user

        self.Get_Inlet_or_Outlet_Output(self.ht.inlet, out)
        self.Get_Inlet_or_Outlet_Output(self.ht.outlet, out)

        return out
    
