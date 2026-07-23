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

from abc import ABC, abstractmethod
from gspy.core.map import TMap
from typing import Optional

class TComponent(ABC):
    def __init__(self, 
                 *,
                 system, 
                 name, 
                 map_filename = None, 
                 control_component = None, 
                 heatpaths = None,
                 **kwargs):    # Constructor of the class
        if kwargs:
            raise TypeError(f"Unexpected keyword arguments: {list(kwargs)}")
        self.system = system
        self.name = name
        self.map_filename = map_filename
        # assume in most cases single map in instantiable child classes
        # (add extra map if necessary, e.g. with f_fan)
        self.map: Optional[TMap] = None
        # 1.1 WV
        self.control = control_component
        self.heatpaths = heatpaths

        self.init_heatpaths()

    def init_heatpaths(self):
        if self.heatpaths is not None:
            for heatpath in self.heatpaths:
                # heatpath.owner = self
                heatpath.init_heattransferstates(self)

    # # backward compatibility
    # @property
    # def owner(self):
    #     return self.system

    # @owner.setter
    # def owner(self, value):
    #     self.system = value

    # 2.1
    @property
    def id(self):
        return f"_{self.name}"

    # 1.6
    def PreRun(self, Mode, PointTime):
        # raise NotImplementedError("Subclass must implement Run abstract method")
        # if Mode == 'DP':
        #     pass
        # else:
        #     pass
        pass

    @abstractmethod
    def Run(self, Mode, PointTime):
        raise NotImplementedError("Subclass must implement Run abstract method")

    # note that anything calculated in PostRun will not end up in the output_dict !
    def PostRun(self, Mode, PointTime):
        # raise NotImplementedError("Subclass must implement Run abstract method")
        pass

    def PlotMaps(self): # Plot performance in map(s)
        if self.map != None:
            self.map.PlotMap()
            print(f"{self.name} map with operating curve saved in {self.map.map_figure_file_path}")

    def CalculateHeatTransfer(self, fs_hx, inlet_or_outlet):
        Q = 0
        if self.heatpaths:
            for heatpath in self.heatpaths:
                Q += heatpath.calc_Q(fs_hx, inlet_or_outlet)
        return Q

    def PrintPerformance(self, Mode, PointTime):
        print(f"{self.name} ({Mode}) Point/Time:{PointTime}")
        if self.heatpaths:
            for heatpath in self.heatpaths:
                heatpath.PrintPerformance()

    def get_outputs(self):
        out = {}
        if self.heatpaths:
            for heatpath in self.heatpaths:
                out.update(heatpath.get_outputs())
                
        return out
    