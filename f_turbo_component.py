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
import f_global as fg
import f_system as fsys
import f_shaft as fshaft
import f_turbomap as TMap
from f_gaspath import TGaspath

class TTurboComponent(TGaspath):
    def __init__(self, name, MapFileName, ControlComponent, stationin, stationout, ShaftNr, Ndes, Etades):
        super().__init__(name, MapFileName, ControlComponent, stationin, stationout)
        self.GasIn = None
        self.GasOut = None
        self.ShaftNr = ShaftNr

        self.Ndes = Ndes
        self.N = Ndes
        self.Nc = None

        self.W = None # W is mass flow of component, e.g. according to map

        self.Etades = Etades
        self.Eta = None

        self.PW = None

        if all(shaft.ShaftNr != ShaftNr for shaft in fsys.shaft_list):
            fsys.shaft_list.append(fshaft.TShaft(ShaftNr, name + ' shaft ' + str(ShaftNr)) )

    def PlotMaps(self): # Plot performance in map(s) override to add dual plotting option
        super().PlotMaps()
        if self.map != None:
            self.map.PlotDualMap()
            print(self.name + " map (dual) with operating curve saved in " + self.map.map_figure_pathname)

    def Run(self, Mode, PointTime):
        super().Run(Mode, PointTime)
        if Mode == 'DP':
            self.Ncdes = self.Ndes / fg.GetRotorspeedCorrectionFactor(self.GasIn)
            self.Nc = self.Ncdes
            self.Eta = self.Etades
            self.shaft = fsys.get_shaft(self.ShaftNr)

    def PrintPerformance(self, Mode, PointTime):
        super().PrintPerformance(Mode, PointTime)
        print(f"\tRotor speed  : {self.N:.0f} rpm")
        print(f"\tCorr Rotor speed : {self.Nc:.0f} rpm")
        if self.map != None:
            if self.map.Ncmap!= None:
                print(f"\tMap Corr Rotor speed : {self.map.Ncmap:.4f} rpm")
            if self.map.Wcmapdes!= None:
                print(f"\tDP Map Corr mass flow : {self.map.Wcmapdes:.3f} kg/s")
            if self.map.Wcmap!= None:
                print(f"\tMap Corr mass flow : {self.map.Wcmap:.3f} kg/s")
            # if self.W!= None:
            #     print(f"\tMap mass flow : {self.W:.3f} kg/s")
            if self.map.PRmap!= None:
                print(f"\tPR map : {self.map.PRmap:.4f}")
            if self.map.Etamap!= None:
                print(f"\tEta map : {self.map.Etamap:.4f}")

        print(f"\tEta des : {self.Etades:.4f}")
        print(f"\tEta     : {self.Eta:.4f}")

        print(f"\tPW : {self.PW:.1f}")

    #  1.1 WV
    def AddOutputToDict(self, Mode):
        super().AddOutputToDict(Mode)
        fsys.output_dict[f"N{self.ShaftNr}"] = self.N
        fsys.output_dict[f"Nc{self.stationin}"] = self.Nc
        fsys.output_dict[f"N{self.ShaftNr}%"] = self.N/self.Ndes*100
        fsys.output_dict[f"Nc{self.stationin}%"] = self.Nc/self.Ncdes*100
        #  ??? why if here ???if "Eta_is_"+self.name in fsys.output_dict:
        fsys.output_dict["Eta_is_"+self.name] = self.Eta
        fsys.output_dict["PW_"+self.name] = self.PW
