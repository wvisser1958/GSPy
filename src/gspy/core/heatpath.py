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
from gspy.core.base_component import TComponent
from gspy.core.gaspath import TGaspath
import gspy.core.utils as fu
import sympy as sp

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
        if self.owner is TGaspath:
            T_hx = self.owner.gas_in.T + self.location_factor * (self.owner.gas_out.T - self.owner.gas_in.T)

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
    
