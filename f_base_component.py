# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#    http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import numpy as np
import cantera as ct
from f_map import TMap
from typing import Optional

class TComponent:
    def __init__(self, name, MapFileName, ControlComponent):    # Constructor of the class
        self.name = name
        # assume in moste case single map in instantiable child classes (add extra map if necessary, e.g. with f_fan)
        self.map: Optional[TMap] = None
        # 1.1 WV
        self.Control = ControlComponent

    def Run(self, Mode, PointTime):
        raise NotImplementedError("Subclass must implement Run abstract method")

    def PostRun(self, Mode, PointTime):
        # raise NotImplementedError("Subclass must implement Run abstract method")
        pass

    def PrintPerformance(self, Mode, PointTime):
        print(f"{self.name} ({Mode}) Point/Time:{PointTime}")

    def PlotMaps(self): # Plot performance in map(s)
        if self.map != None:
            self.map.PlotMap()
            print(self.name + " map with operating curve saved in " + self.map.map_figure_pathname)

    #  1.1 WV
    def AddOutputToDict(self, Mode):
        raise NotImplementedError("Subclass must implement AddOutputToDict abstract method")


