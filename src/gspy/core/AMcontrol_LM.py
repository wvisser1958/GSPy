# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#    http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Author
#   Wilfried Visser
#   Modified by Lucas Middendorp

import numpy as np
import pandas as pd
import cantera as ct
import gspy.core.sys_global as fg
import gspy.core.system as fsys
from gspy.core.base_component import TComponent

class TAMcontrol(TComponent):
        # Usage example:
        #  AMcontrol = TAMcontrol('AMcontrol',
        #                         # input data file
        #                        "input/Turbojet_AMinput.csv",
        #                         (combustor1, "Wf"),
        #                         ['T3',
        #                         'P3',
        #                         'T5,'
        #                         'N1%'],
        #                         [
        #                             (compressor1.map, "SF_eta_deter"),
        #                             (compressor1.map, "SF_wc_deter"),
        #                             (turbine1.map, "SF_eta_deter"),
        #                             (turbine1.map, "SF_wc_deter")
        #                         ])

    def __init__(self, name, measdatafilename, powersettingcomppar, ambientparnamelist, measparnametuple, bounds_penalty, mapmod_comps_pars_tuple):
        super().__init__(name, None, None) # no control controlling a control (yet)
        self.measdatafilename = measdatafilename
        self.powersettingcomppar = powersettingcomppar
        self.ambientparnamelist = ambientparnamelist

        self.measparnamelist = [x[0] for x in measparnametuple]
        self.tolerance = [float(x[1]) for x in measparnametuple]
        self.measpardesvalues = []
        self.bounds_penalty = bounds_penalty[0]
        self.mapmod_comps_pars_list = [x[0] for x in mapmod_comps_pars_tuple]
        self.mapmod_bounds = [x[1] for x in mapmod_comps_pars_tuple]

    def Get_OD_inputpoints(self):
        # set the input  points as the input data file row numbers
        return self.am_input.index.to_numpy()

    def Run(self, Mode, PointTime):
        if Mode == 'DP':
            # reset all map modifiers back to 1
            for compmap, SFpar in self.mapmod_comps_pars_list:
                setattr(compmap, SFpar, 1)
                # fsys.states = np.append(fsys.states, 1)
                # fsys.errors = np.append(fsys.errors, 0)
            # read input (points to perform AM analysis on)
            self.am_input = pd.read_csv(self.measdatafilename)
            self.am_input.set_index('Point', inplace=True)

            # ======================== AM Powersetting control ========================
            if self.powersettingcomppar[1] is None:
                self.powersettingcomppar = (self.powersettingcomppar[0], 'Wf')

            if self.powersettingcomppar[1] != 'Wf':
                self.istate_Wf = fsys.states.size
                fsys.states = np.append(fsys.states, 1.0)   # Wf scale factor
                fsys.errors = np.append(fsys.errors, 0.0)
                self.ierror_powerset = fsys.errors.size - 1
        else:
            # set ambient conditions
            for ambientcondpar in self.ambientparnamelist:
                # fsys.Ambient.__setattr__(ambientcondpar, self.am_input.at[PointTime, ambientcondpar])
                setattr(fsys.Ambient, ambientcondpar, self.am_input.at[PointTime, ambientcondpar])

            # set power setting
            psetcomp, psetpar = self.powersettingcomppar

            # ======================== AM input control ========================
            if self.powersettingcomppar[1] != 'Wf':
                Wf_meas = self.am_input.at[PointTime, 'Wf']
                SF_Wf = fsys.states[self.istate_Wf]
                setattr(psetcomp, 'Wf', Wf_meas * SF_Wf)
            else:
                setattr(psetcomp, psetpar, self.am_input.at[PointTime, psetpar])

            #  set map modifiers according to states
            # setattr(compmap, SFpar, fsys.states[self.first_map_mod_stateindex+i])
            for i, (compmap, SFpar) in enumerate(self.mapmod_comps_pars_list, start=0):
                setattr(compmap, SFpar, fsys.states[self.first_map_mod_stateindex+i])

    def PostRun(self, Mode, PointTime):
        # super().PostRun(Mode, PointTime)
        if Mode == 'DP':
            #  add states and errors at end of existing states and errors of system model
            #  save the 1st index
            self.first_map_mod_stateindex = fsys.states.size
            for compmap, SFpar in self.mapmod_comps_pars_list:
                # set the map modifier factors to 1 in case of multiple DP, OD calculations....
                setattr(compmap, SFpar, 1)
                fsys.states = np.append(fsys.states, 1)
                fsys.errors = np.append(fsys.errors, 0)
            for parname in self.measparnamelist:
                self.measpardesvalues = np.append(self.measpardesvalues, fsys.output_dict[f"{parname}"])

            # ======================== AM Powersetting control ========================
            if self.powersettingcomppar[1] != 'Wf':
                self.powerset_DP = fsys.output_dict[f"{self.powersettingcomppar[1]}"]

        else:
            # ===================== AM Errors with Tolerance =====================
            # Determine start index for mapmod states in the error vector
            mapmod_start = len(fsys.states) - len(self.mapmod_bounds)

            for i, parname in enumerate(self.measparnamelist):
                # Retrieve measurement and model value for each parameter
                par_value_measured = self.am_input.at[PointTime, parname]
                error_idx = mapmod_start + i
                # Apply tolerance to the error calculation
                fsys.errors[error_idx] = (
                    self.tolerance[i] * (fsys.output_dict[parname] - par_value_measured) / self.measpardesvalues[i]
                )

             # ==================== Bounds Enforcement with Penalty ====================
            for i, (compmap, SFpar) in enumerate(self.mapmod_comps_pars_list):
                state_idx = mapmod_start + i
                state_value = fsys.states[state_idx]
                lower_bound_perc, upper_bound_perc = self.mapmod_bounds[i]

                # Apply lower bound penalty if defined
                if lower_bound_perc is not None:
                    lower_bound = lower_bound_perc / 100 + 1
                    if state_value < lower_bound:
                        fsys.errors[:] += (lower_bound - state_value) ** 2 * self.bounds_penalty
                        # print(f'Penalty: {state_value} below lower bound {lower_bound} for {compmap.name}_{SFpar}')
                        continue

                # Apply upper bound penalty if defined
                if upper_bound_perc is not None:
                    upper_bound = upper_bound_perc / 100 + 1
                    if state_value > upper_bound:
                        fsys.errors[:] += (state_value - upper_bound) ** 2 * self.bounds_penalty
                        # print(f'Penalty: {state_value} above upper bound {upper_bound} for {compmap.name}_{SFpar}')
                        continue

            # ======================= AM Powersetting control =======================
            if self.powersettingcomppar[1] != 'Wf':
                # Get measured and modeled power setting
                powerset_meas = self.am_input.at[PointTime, self.powersettingcomppar[1]]
                powerset_model = fsys.output_dict[self.powersettingcomppar[1]]

                # Set normalization reference if not already set
                if not hasattr(self, 'powerset_DP'):
                    self.powerset_DP = powerset_model

                # Add normalized power setting error to the error vector
                fsys.errors[self.ierror_powerset] = (powerset_meas - powerset_model) / self.powerset_DP


    def PrintPerformance(self, Mode, PointTime):
        if Mode == 'DP':
            pass
        else:
            for i, (compmap, SFpar) in enumerate(self.mapmod_comps_pars_list, start=0):
                print(f"\t{compmap.name}_{SFpar} {getattr(compmap, SFpar)}")

    #  1.1 WV
    def AddOutputToDict(self, Mode):
        for i, (compmap, SFpar) in enumerate(self.mapmod_comps_pars_list, start=0):
            fsys.output_dict[compmap.name+"_"+SFpar] = getattr(compmap, SFpar)