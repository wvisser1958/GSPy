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
#   Modified by Lucas Middendorp: weight factor and equation for alternative power setting parameter (other than Wf)

import numpy as np
import pandas as pd
from dataclasses import dataclass
from gspy.core.base_component import TComponent

@dataclass
class AMMeasurement:
    parameter_name: str
    weight: float = 1.0

@dataclass
class AMHealthParameter:
    component: object
    attribute_name: str
    reference_value: float = 1.0    # value of the map modifier factor at reference (e.g. heatlhy) condition, usually 1.
                                    # map scale factors usually are 1, but can be set to other values for example to represent 
                                    # a healthy condition at a different value than 1.0
    # bounds: tuple[float | None, float | None] = (None, None)

class TAMcontrol(TComponent):
        # Usage example:
        #  AMcontrol = TAMcontrol(<owner>,
        #                        'AMcontrol',
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

    def __init__(self, 
                 *,
                measdatafilename, 
                powersetting_comp_par, 
                ambient_parameters, 
                measurement_parameters, 
                health_parameters,
                **kwargs):
                        
        super().__init__(**kwargs)
        self.measdatafilename = measdatafilename
        self.powersetting_comp_par = powersetting_comp_par
        self.ambient_parameters = ambient_parameters
        self.measurement_parameters = measurement_parameters
        self.health_parameters = health_parameters
        self.measpardesvalues = np.array([])  # array to store the design values of the measured parameters, used to normalize the errors

    def Get_OD_inputpoints(self):
        # set the input  points as the input data file row numbers (must be Point, value pair, value here = None)
        return [(point, None) for point in self.am_input["Point"]]

    def Run(self, Mode, PointTime):
        if Mode == 'DP':
            # reset all map/health modifiers back to 1
            for hp in self.health_parameters:
                setattr(hp.component, hp.attribute_name, hp.reference_value)
            # read input (points to perform AM analysis on)
            self.am_input = pd.read_csv(self.system.input_dir_path / self.measdatafilename)
            self.am_input.set_index('Point')

            # by Lucas Middendorp ======================== AM Powersetting control ===========
            if self.powersetting_comp_par[1] is None:
                self.powersetting_comp_par = (self.powersetting_comp_par[0], 'Wf')

            if self.powersetting_comp_par[1] != 'Wf':
                self.system.states = np.append(self.system.states, 1)   
                self.istate_Wf = self.system.states.size - 1
                self.system.errors = np.append(self.system.errors, 0)
                self.ierror_powerset = self.system.errors.size - 1

            # reset design reference
            self.measpardesvalues = np.array([])  # array to store the design values of the measured parameters, used to normalize the errors

        else:
            # set ambient conditions
            for ambientcondpar in self.ambient_parameters:
                setattr(self.system.ambient, ambientcondpar, self.am_input.at[PointTime, ambientcondpar])

            # set power setting
            psetcomp, psetpar = self.powersetting_comp_par

            # ======================== AM Power setting control ========================
            # if self.powersettingcomppar[1] != 'Wf':
            if psetpar == 'Wf':
                setattr(psetcomp, psetpar, self.am_input.at[PointTime, psetpar])
            else:  # power setting determined by other parameter (see PostRun)
                Wf_meas = self.am_input.at[PointTime, 'Wf']  # Wfmeas from input table used to normalize state_Wf
                Wf_state = self.system.states[self.istate_Wf]
                setattr(psetcomp, 'Wf', Wf_meas * Wf_state)

            #  set map modifiers according to states
            for i, hp in enumerate(self.health_parameters, start=0):
                setattr(hp.component, hp.attribute_name, self.system.states[self.first_attribute_stateindex+i] * hp.reference_value)

    # note that anything calculated in PostRun will not end up in the output_dict !
    def PostRun(self, mode, PointTime):
        # super().PostRun(Mode, PointTime)
        if mode == 'DP':
            #  add states and errors at end of existing states and errors of system model
            #  save the 1st index
            self.first_attribute_stateindex = self.system.states.size
            for i, hp in enumerate(self.health_parameters, start=0):
                # set the map modifier factors backto hp.reference_value in case of multiple DP, OD calculations....
                setattr(hp.component, hp.attribute_name, hp.reference_value)
                self.system.states = np.append(self.system.states, 1)
                self.system.errors = np.append(self.system.errors, 0)
            for mp in self.measurement_parameters:
                self.measpardesvalues = np.append(self.measpardesvalues, self.system.output_dict[f"{mp.parameter_name}"])
        else:
            for i, mp in enumerate(self.measurement_parameters, start = 0):
                parname_measured = mp.parameter_name
                parvalue_measured =  self.am_input.at[PointTime, parname_measured]
                parvalue_calculated = self.system.output_dict[f"{parname_measured}"]
                weight_factor = mp.weight
                self.system.errors[self.first_attribute_stateindex+i] =  (   weight_factor 
                                                                          * (parvalue_calculated - parvalue_measured) 
                                                                          / self.measpardesvalues[i])

    def PrintPerformance(self, Mode, PointTime):
        if Mode == 'DP':
            pass
        else:
            for i, hp in enumerate(self.health_parameters, start=0):
                comp = hp.component
                attrib_name = hp.attribute_name
                print(f"\t{comp.name}_{attrib_name} {getattr(comp, attrib_name)}")

    # 2.0.0.0
    def get_outputs(self):
        out = super().get_outputs()
        for i, hp in enumerate(self.health_parameters, start=0):
            comp = hp.component
            attribute_name = hp.attribute_name
            out[comp.name+"_"+attribute_name] = getattr(comp, attribute_name)
        return out
