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
from gspy.core.map import TMap
from typing import Optional

class TComponent:
    def __init__(self, owner, name, map_filename, control_component):    # Constructor of the class
        self.owner = owner
        self.name = name
        self.map_filename = map_filename
        # assume in most cases single map in instantiable child classes
        # (add extra map if necessary, e.g. with f_fan)
        self.map: Optional[TMap] = None
        # 1.1 WV
        self.control = control_component

    # 1.6
    def PreRun(self, Mode, PointTime):
        # raise NotImplementedError("Subclass must implement Run abstract method")
        # if Mode == 'DP':
        #     pass
        # else:
        #     pass
        pass

    def Run(self, Mode, PointTime):
        raise NotImplementedError("Subclass must implement Run abstract method")

    # note that anything calculated in PostRun will not end up in the output_dict !
    def PostRun(self, Mode, PointTime):
        # raise NotImplementedError("Subclass must implement Run abstract method")
        pass

    def PrintPerformance(self, Mode, PointTime):
        print(f"{self.name} ({Mode}) Point/Time:{PointTime}")

    def PlotMaps(self): # Plot performance in map(s)
        if self.map != None:
            self.map.PlotMap()
            print(f"{self.name} map with operating curve saved in {self.map.map_figure_file_path}")

    def get_outputs(self):
        return {}

    def add_outputs_to_dict(self, mode):
        self.owner.output_dict.update(self.get_outputs())