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
from abc import ABC, abstractmethod
from bisect import bisect_left
import cantera as ct
import gspy.core.sys_global as fg
import gspy.core.system as fsys
import gspy.core.shaft as fshaft
import gspy.core.turbomap as TMap
from gspy.core.gaspath import TGaspath
from pathlib import Path
from gspy.core.turbomap import TTurboMap

class TTurboComponent(TGaspath):
    def __init__(self, name, MapFileName_or_dict, ControlComponent, stationin, stationout, ShaftNr,
                 Ndes, Etades,
                 Ncmapdes, Betamapdes):
        super().__init__(name, MapFileName_or_dict, ControlComponent, stationin, stationout)

        self.GasIn = None
        self.GasOut = None
        self.ShaftNr = ShaftNr

        self.Ndes = Ndes
        self.N = Ndes
        self.Nc = None

        # 1.6
        self.Ncmapdes = Ncmapdes
        self.Betamapdes = Betamapdes
        self.map = None # to be assigned later
        self.maps_by_angle = None
        self.vg_angle_des = None
        self.vg_angle = None
        self.istate_beta = None

        self.W = None # W is mass flow of component, e.g. according to map

        self.Etades = Etades
        self.Eta = None
        # v1.4
        self.Polytropic_Eta = 0  # default eta is assumed isentropic, if self.Polytropic_Eta == 1, polytropic

        self.PW = None

        # 1.6 Wilfried Visser, to accomodate multi-map functionality for variable geometry
        # VGparvalue is set from outside (manually of via TControl component) determining the maps in the MapFileNames list to be used for interpolation
        # type-dependent behavior for MapFileNames (renamed here from 'MapFileName' in TGaspath)
        if isinstance(MapFileName_or_dict, dict):
            # MapFileName_or_dict holds VGparvaluedes in element 'design_angle' and a list of mapfilename, VGpasvalues in "maps"
            # MapFileNames is list of tuples : Map file path, VGparvalue (e.g. VSV / VIGV angle, VBV position)
            self.vg_angle_des = MapFileName_or_dict['design_angle']           # tuple[0] holds the VGpasvalue in the design point (for scaling map in DP calculation)
            self.vg_angle =self.vg_angle_des
            self.MapFileName = None

            self.maps_by_angle: dict[float, TTurboMap] = {}
            maps_dict = MapFileName_or_dict["maps"]
            for angle in sorted(maps_dict):
                fn = Path(maps_dict[angle])
                if not fn.exists():
                    raise FileNotFoundError(f"Map file for angle {angle} not found: {fn}")
                # You implement/own this constructor (or whatever you call it)
                self.maps_by_angle[angle] = self.CreateMap(fn, ShaftNr, Ncmapdes, Betamapdes)

                # VGparvaluedes must be one of the VGparvalue in the MapFileNameList (typically the value corresponding to the design point map),
                # so we can set scale factors, check if this is the case
                # check if this is the design map (for scaling)
                if math.isclose(angle, self.vg_angle_des, rel_tol=0.0, abs_tol=1e-6):
                    self.map = self.maps_by_angle[angle]    # map is design point map used for scaling
                    self.MapFileName = fn                   # mapfile used for scaling
            self.vg_angles = sorted(self.maps_by_angle)

            if self.MapFileName == None:
                raise TypeError(
                    "VGparvaluedes does not match any of the VGpasvalue's in the MapFileNames list")

        # single map from single map file path
        elif isinstance(MapFileName_or_dict, (str, Path)):
            # MapFileName_or_dict is just a single map file name/path
            # Normalize to Path internally (best practice)
            self.MapFileName = Path(MapFileName_or_dict)
            self.map = self.CreateMap(self.MapFileName, ShaftNr, Ncmapdes, Betamapdes)

        else:
            raise TypeError(
                "MapFileNames must be a str, pathlib.Path, or a tuple with 0) VGparvaluedesigm, and 1) list of (VGparvalue, MapFileName)"
            )

        if all(shaft.ShaftNr != ShaftNr for shaft in fsys.shaft_list):
            fsys.shaft_list.append(fshaft.TShaft(ShaftNr, name + ' shaft ' + str(ShaftNr)) )

    # 1.6 WV
    # @abstractmethod  not abstract: not implemented in TFan child class
    def CreateMap(self, MapFilePath, ShaftNr, Ncmapdes, Betamapdes):
        # raise NotImplementedError
        pass

    # 1.6 WV
    def ReadTurboMapAndSetScaling(self):
        if self.maps_by_angle == None:  # single map only in map object
            self.map.ReadMapAndGetScaling(self.Ncdes, self.Wcdes, self.PRdes, self.Etades)
        else:
            # scale the desig point map
            SFnc, SFwc, SFpr, SFeta = self.map.ReadMapAndGetScaling(self.Ncdes, self.Wcdes, self.PRdes, self.Etades)
            # now copy the scaling factors to the other maps

            for angle, tmap in self.maps_by_angle.items():
                # only scale the map (i.e. the design point map)
                if not (tmap is self.map):
                    tmap.ReadMap(tmap.MapFileName)
                    tmap.SetScaling(SFnc, SFwc, SFpr, SFeta)

    # 1.6 WV
    def GetTurboMapPerformance(self, vg_angle, Nc, Beta):
        if vg_angle == None:  # single map only in map object
            Wc, PR, Eta = self.map.GetScaledMapPerformance(Nc, Beta)
            return Wc, PR, Eta
        else:
            i = bisect_left(self.vg_angles, vg_angle)

            if i == 0:                  # take first map (also if angle beyond the range)
                Wc, PR, Eta = self.maps_by_angle[self.vg_angles[0]].GetScaledMapPerformance(Nc, Beta)
                return Wc, PR, Eta

            if i == len(self.vg_angles):   # take last map (also if angle beyond the range)
                Wc, PR, Eta = self.maps_by_angle[self.vg_angles[-1]].GetScaledMapPerformance(Nc, Beta)
                return Wc, PR, Eta

            a0, a1 = self.vg_angles[i - 1], self.vg_angles[i]
            Wc0, PR0, Eta0 = self.maps_by_angle[a0].GetScaledMapPerformance(Nc, Beta)
            Wc1, PR1, Eta1 = self.maps_by_angle[a1].GetScaledMapPerformance(Nc, Beta)

            w = (vg_angle - a0) / (a1 - a0)
            Wc = (1 - w) * Wc0 + w * Wc1
            PR = (1 - w) * PR0 + w * PR1
            Eta = (1 - w) * Eta0 + w * Eta1
            return Wc, PR, Eta

    def PlotMaps(self): # Plot performance in map(s) override to add dual plotting option
        super().PlotMaps()
        if self.map != None:
            self.map.PlotDualMap(use_scaled_map = True, do_plot_design_point = True, do_plot_series = True)
            # 1.4
            # print(self.name + " map (dual) with operating curve saved in " + self.map.map_figure_pathname)
            print(f"{self.name} map (dual) with operating curve saved in {self.map.map_figure_pathname}")

    def Run(self, Mode, PointTime):
        super().Run(Mode, PointTime)
        if Mode == 'DP':
            self.Ncdes = self.Ndes / fg.GetRotorspeedCorrectionFactor(self.GasIn)
            self.Nc = self.Ncdes
            self.Eta = self.Etades
            self.shaft = fsys.get_shaft(self.ShaftNr)
            self.vg_angle = self.vg_angle_des

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

        #  1.5
        if self.Etades != None:
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

        # 1.5
        if self.Eta != None:
            fsys.output_dict["Eta_is_"+self.name] = self.Eta
        # 1.6 WV
        if self.vg_angle_des !=None:
            fsys.output_dict["vg_angle_"+self.name] = self.vg_angle
        fsys.output_dict["PW_"+self.name] = self.PW
