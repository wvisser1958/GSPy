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
from gspy.core.base_component import TComponent
from gspy.core.gaspath import TGaspath
import gspy.core.utils as fu
import gspy.core.constants as c
import sympy as sp
from gspy.core.flow_state import TFlowState

class THeatpath(TComponent):

    def __init__(self, 
                 *,
                 heatsink,      # heat sink component the path is connected to  
                 a_ht,          # heat transfer area (between flow and wall)
                 a_flow,        # flow cross area (to calculate convection properties from mass flow)
                 d_re,          # characteristic length for Reynolds nr
                 k_gas,         # conductivity of the gas
                 Nu,            # Nusselt expression
                 d_mat,          # material/wall thickness for conduction
                 k_mat,          # wall material conductivity
                 eps_rad,        # radiation emissivity
                 q_user,          # manual user specified total heat flux Q 
                                # (if not None, overriding all other parameter determined Q)
                 location_factor = 0.5,   # 0 = all Q from gas path component entry
                                        # 1 = all Q from gas path component exit
                                        # 0.5 (default is half / half)
                                        # 0.3 0.3 from entry, 0.7 from exit
                **kwargs                                        
                ):                
        if not isinstance(heatsink, TComponent):
            raise TypeError(
                f"heatsink must be a TComponent, got {type(heatsink).__name__}"
            )        
        super().__init__(**kwargs)
        self.heatsink = heatsink
        self.a_ht = a_ht
        self.a_flow = a_flow    
        self.d_re = d_re   
        self.k_gas = k_gas   
        self.Nu = Nu   
        self.d_mat = d_mat   
        self.k_mat = k_mat   
        self.eps_rad = eps_rad   
        self.q_user = q_user   
        self.location_factor = location_factor

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

    def Run(self, Mode, PointTime):
        if self.q_user is not None:
            Q_total = self.q_user
        else:
            # set the gas conditions at the heat path location (between entry and exit of the gas path component)
            if self.owner is TGaspath:
                T_hx = self.owner.fs_in.T + self.location_factor * (self.owner.fs_out.T - self.owner.fs_in.T)
                P_hx = self.owner.fs_in.P + self.location_factor * (self.owner.fs_out.P - self.owner.fs_in.P)
            if self.scratch_fs is None:
                self.scratch_fs = TFlowState.create_empty(self.owner.gas, station_nr=self.station_in+'_hs')
            self.scratch_fs.copy_from(self.fs_in, self.station_in+'_hs')
            # for now we are using the total gas T and P (as near/at the wal there there is stagnation temperature)
            self.scratch_fs.TPY = T_hx, P_hx, self.fs_in.gas_q.Y

            # calculate the heat transfer from the gas to the wall (convection) and through the wall (conduction)
            mu_hs = self.scratch_fs.gas_q.viscosity
            Rho_hs = self.scratch_fs.gas_q.density
            c_hs = self.scratch_fs.gas_q.mass/self.a_flow/Rho_hs
            Re = Rho_hs * c_hs * self.d_re / mu_hs
            Pr = mu_hs * self.scratch_fs.gas_q.cp / self.scratch_fs.gas_q.thermal_conductivity 
            Nu = self.Nu_func(Re, Pr)
            hs_convection = Nu * self.k_gas / self.d_re
            hs_conduction = self.k_mat / self.d_mat
            hs_total = 1 / (1/hs_convection + 1/hs_conduction)
            Q_conv_cond = hs_total * self.a_ht * (self.scratch_fs.T - self.heatsink.T)

            # now with the calculated Q_conv_cond, we can calculate the wall temperature Twall for radiation            
            if math.isclose(hs_conduction, 0.0, abs_tol=1e-12) or math.isclose(self.a_ht, 0.0, rel_tol=1e-12):
                Twall = self.heatsink.T
            else:
                Twall = self.heatsink.T - Q_conv_cond/self.a_ht/hs_conduction
           
            # radiation heat transfer (from wall to ambient) is not yet included in the Q calculation
            Q_rad = self.eps_rad * c.C_StefanBoltzmann * self.a_ht * (Twall**4-self.scratch_fs.T**4)  
            Q_total = Q_conv_cond + Q_rad
        return Q_total               

    def get_outputs(self):
        out = super().get_outputs()

        if self.a_ht is not None:
            out[f"a_ht{self.id}"] = self.a_ht
        if self.a_flow is not None:
            out[f"a_flow{self.id}"] = self.a_flow
        if self.d_re is not None:
            out[f"d_re{self.id}"] = self.d_re
        if self.k_gas is not None:
            out[f"k_gas{self.id}"] = self.k_gas
        if self.Nu is not None:
            out[f"Nu{self.id}"] = self.Nu
        if self.d_mat is not None:
            out[f"d_mat{self.id}"] = self.d_mat
        if self.k_mat is not None:
            out[f"k_mat{self.id}"] = self.k_mat
        if self.eps_rad is not None:
            out[f"eps_rad{self.id}"] = self.eps_rad
        if self.q_user is not None:
            out[f"q_user{self.id}"] = self.q_user

        return out
    
