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
from f_gaspath import TGaspath
import f_global as fg
import f_system as fsys

class TBleedFlow(TGaspath):
    def __init__(self, name, MapFileName, ControlComponent, stationin, stationout, bleednumber, bleedfractiondes, dPfactor):    # Constructor of the class
        super().__init__(name, MapFileName, ControlComponent, stationin, stationout)
        self.bleednumber = bleednumber
        self.bleedfractiondes = bleedfractiondes
        self.bleedfraction = bleedfractiondes
        self.dPfactor = dPfactor
