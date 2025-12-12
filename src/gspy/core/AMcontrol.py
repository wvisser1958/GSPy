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

    def __init__(self, name, measdatafilename, powersettingcomppar, ambientparnamelist, measparnamelist, mapmod_comps_pars_list):
        super().__init__(name, '', '') # no control controlling a control (yet)
        self.measdatafilename = measdatafilename
        self.powersettingcomppar = powersettingcomppar
        self.ambientparnamelist = ambientparnamelist
        self.measparnamelist = measparnamelist
        self.measpardesvalues = []
        self.mapmod_comps_pars_list = mapmod_comps_pars_list

    def Get_OD_inputpoints(self):
        # set the input  points as the input data file row numbers
        return self.am_input['Point'].to_numpy()

    def Run(self, Mode, PointTime):
        if Mode == 'DP':
            # reset all map modifiers back to 1
            for compmap, SFpar in self.mapmod_comps_pars_list:
                setattr(compmap, SFpar, 1)
                # fsys.states = np.append(fsys.states, 1)
                # fsys.errors = np.append(fsys.errors, 0)
            # read input (points to perform AM analysis on)
            self.am_input = pd.read_csv(self.measdatafilename)
            self.am_input.set_index('Point')
        else:
            # set ambient conditions
            for ambientcondpar in self.ambientparnamelist:
                # fsys.Ambient.__setattr__(ambientcondpar, self.am_input.at[PointTime, ambientcondpar])
                setattr(fsys.Ambient, ambientcondpar, self.am_input.at[PointTime, ambientcondpar])

            # set power setting
            psetcomp, psetpar = self.powersettingcomppar
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
        else:
            for i, parname in enumerate(self.measparnamelist, start = 0):
                parvalue =  self.am_input.at[PointTime, parname]
                fsys.errors[self.first_map_mod_stateindex+i] = (fsys.output_dict[f"{parname}"] - parvalue) / self.measpardesvalues[i]

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