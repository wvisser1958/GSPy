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
import numpy as np
from scipy.interpolate import RegularGridInterpolator
import cantera as ct
import gspy.core.sys_global as fg
import gspy.core.system as fsys
import gspy.core.utils as fu
from gspy.core.turbo_component import TTurboComponent
from gspy.core.compressormap import TCompressorMap

class TFan(TTurboComponent):
    def __init__(self, name, MapFileName_core, stationin, stationout_core, stationout_duct, ShaftNr,
                 Ndes_core, Etades_core,
                # in TFan, Etades paramater = Etades_core
                #          MapFileName = name of core map file
                 BPRdes,
                 Ncmapdes_core, Betamapdes_core, PRdes_core,
                 MapFileName_duct,
                 Ncmapdes_duct, Betamapdes_duct, PRdes_duct, Etades_duct):

        # TTurboComponent parent class creator    no control link
        super().__init__(name, MapFileName_core, '', stationin, stationout_core, ShaftNr, Ndes_core, Etades_core)

        self.stationout_duct = stationout_duct

        self.BPRdes = BPRdes

        # core side map
        self.map_core = TCompressorMap(self, name + '_map_core', MapFileName_core, "Wc_core_"+self.name, "PR_core_"+self.name, ShaftNr, Ncmapdes_core, Betamapdes_core)
        self.PRdes_core = PRdes_core

        #  1.5 set self.Etades to None, use Etadec_core instead to avoid duplicate in output
        #      checking if self.Etades non None in TTurboComponent
        self.Etades_core = self.Etades
        self.Etades = None

        # duct side map
        self.map_duct = TCompressorMap(self, name + '_map_duct', MapFileName_duct, "Wc_duct_"+self.name, "PR_duct_"+self.name, ShaftNr, Ncmapdes_duct, Betamapdes_duct)
        self.PRdes_duct = PRdes_duct
        self.Etades_duct = Etades_duct

    def GetSlWcValues(self):
        return self.sl_wc_array

    def GetSlPrValues(self):
        return self.sl_pr_array

    def Run(self, Mode, PointTime):
        super().Run(Mode, PointTime)

        if Mode == 'DP':
            self.BPR = self.BPRdes
            # create GasOut_duct ct.Quantity here
            self.GasOut_duct = ct.Quantity(self.GasIn.phase, mass = 1)
        else:
            self.BPR = fsys.states[self.istate_BPR] * self.BPRdes

        # 1.5 bug fix !!!! 20-12-2025 W. Visser
        # W_core_in and W_duct_in are always the part corresponding to BPRdes  (design value!, we split the core and duct/bypass corresponding to BPRdes)
        # W_core_in and W_duct_in are used for the mass flow error equations at the end of this procedure
                    # old self.W_core_in = self.GasIn.mass / (self.BPR + 1)
                    # old self.GasOut.mass = self.W_core_in
                    # self.W_duct_in = self.GasIn.mass - self.GasOut.mass
                    # self.GasOut_duct.mass = self.W_duct_in
        self.W_core_in = self.GasIn.mass               / (self.BPRdes + 1)
        self.W_duct_in = self.GasIn.mass * self.BPRdes / (self.BPRdes + 1)
        # actual GasOut mass flows are corresponding to actual BPR !
        self.GasOut.mass       = self.GasIn.mass            / (self.BPR + 1)
        self.GasOut_duct.mass  = self.GasIn.mass * self.BPR / (self.BPR + 1)

        # 1.5
        # W_duct_in is always the part corresponding to BPRdes  (design value!, we split the core and duct/bypass corresponding to BPRdes)

        if Mode == 'DP':
            # # correct mass flow
            self.Wdes_core_in = self.W_core_in
            self.Wcdes_core_in = self.Wdes_core_in * fg.GetFlowCorrectionFactor(self.GasIn)
            self.map_core.ReadMapAndSetScaling(self.Ncdes, self.Wcdes_core_in, self.PRdes_core, self.Etades_core)
            self.PW_core = fu.Compression(self.GasIn, self.GasOut, self.PRdes_core, self.Etades_core, self.Polytropic_Eta)

            # # add fan duct side compression
            # self.Wdes_duct = self.GasIn.mass - self.GasOut.mass
            self.Wdes_duct_in = self.W_duct_in
            self.Wcdes_duct_in = self.W_duct_in * fg.GetFlowCorrectionFactor(self.GasIn)
            self.map_duct.ReadMapAndSetScaling(self.Ncdes, self.Wcdes_duct_in, self.PRdes_duct, self.Etades_duct)
            self.PW_duct = fu.Compression(self.GasIn, self.GasOut_duct, self.PRdes_duct, self.Etades_duct, self.Polytropic_Eta)

            self.PW = self.PW_core + self.PW_duct
            self.shaft.PW_sum = self.shaft.PW_sum - self.PW

            # add states and errors
            #  rotor speed
            fsys.states = np.append(fsys.states, 1)
            self.istate_n = fsys.states.size-1
            self.shaft.istate = self.istate_n
            # state for bypass ratio BPR
            fsys.states = np.append(fsys.states, 1)
            self.istate_BPR = fsys.states.size-1
            #  map beta core
            fsys.states = np.append(fsys.states, 1)
            self.istate_beta_core = fsys.states.size-1
            # map beta duct
            fsys.states = np.append(fsys.states, 1)
            self.istate_beta_duct = fsys.states.size-1

            # error for equation GasIn.mass = W (W according to map operating point)
            fsys.errors = np.append(fsys.errors, 0)
            self.ierror_wc_core = fsys.errors.size-1
            fsys.errors = np.append(fsys.errors, 0)
            self.ierror_wc_duct = fsys.errors.size-1

            # calculate parameters for output
            self.PR_core  = self.PRdes_core
            self.PR_duct = self.PRdes_duct
            self.Wc_core = self.Wcdes_core_in
            self.Wc_duct = self.Wcdes_duct_in
            self.Eta_core = self.Etades_core
            self.Eta_duct = self.Etades_duct
        else:
            self.N = fsys.states[self.istate_n] * self.Ndes
            self.Nc = self.N / fg.GetRotorspeedCorrectionFactor(self.GasIn)

            self.Wc_core, self.PR_core, self.Eta_core = self.map_core.GetScaledMapPerformance(self.Nc, fsys.states[self.istate_beta_core])
            self.Wc_duct, self.PR_duct, self.Eta_duct = self.map_duct.GetScaledMapPerformance(self.Nc, fsys.states[self.istate_beta_duct])

            self.PW_core = fu.Compression(self.GasIn, self.GasOut, self.PR_core, self.Eta_core, self.Polytropic_Eta)
            self.PW_duct = fu.Compression(self.GasIn, self.GasOut_duct, self.PR_duct, self.Eta_duct, self.Polytropic_Eta)

            self.PW = self.PW_core + self.PW_duct

            self.shaft.PW_sum = self.shaft.PW_sum - self.PW

            self.W_core = self.Wc_core / fg.GetFlowCorrectionFactor(self.GasIn)
            fsys.errors[self.ierror_wc_core ] = (self.W_core - self.W_core_in) / self.Wdes
            self.W_duct = self.Wc_duct / fg.GetFlowCorrectionFactor(self.GasIn)
            fsys.errors[self.ierror_wc_duct ] = (self.W_duct - self.W_duct_in) / self.Wdes

            self.GasOut.mass = self.W_core  # self.GasOut = core flow = GasOut_core
            self.GasOut_duct.mass = self.W_duct

        # calculate parameters for output
        self.Wc = self.GasIn.mass * fg.GetFlowCorrectionFactor(self.GasIn)

        fsys.gaspath_conditions[self.stationout_duct] = self.GasOut_duct
        return self.GasOut, self.GasOut_duct

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

        print(f"\tEta des_core : {self.Etades_core:.4f}")
        print(f"\tEta core    : {self.Eta_core:.4f}")
        print(f"\tEta des_duct : {self.Etades_duct:.4f}")
        print(f"\tEta duct    : {self.Eta_duct:.4f}")

        print(f"\tPW : {self.PW:.1f}")

    def GetOutputTableColumnNames(self):
        # override the super.., delete unused PR..., Eta_is: now separate PR and Eta for core and duct
        column_list = super().GetOutputTableColumnNames()
        column_list.remove("PR_"+self.name)
        column_list.remove("Eta_is_"+self.name)
        column_list = column_list + ["BPR_"+self.name, "PR_core_"+self.name, "PR_duct_"+self.name,
                                     "Wc_core_"+self.name, "Wc_duct_"+self.name,
                                     "Eta_is_core_"+self.name, "Eta_is_duct_"+self.name]
        return column_list

    #  1.1 WV
    def AddOutputToDict(self, Mode):
        super().AddOutputToDict(Mode)
        fsys.output_dict["BPR_"+self.name] = self.BPR
        fsys.output_dict["PR_core_"+self.name] = self.PR_core
        fsys.output_dict["PR_duct_"+self.name] = self.PR_duct
        fsys.output_dict["Wc_core_"+self.name] = self.Wc_core
        fsys.output_dict["Wc_duct_"+self.name] = self.Wc_duct
        fsys.output_dict["Eta_is_core_"+self.name] = self.Eta_core
        fsys.output_dict["Eta_is_duct_"+self.name] = self.Eta_duct

    # override PlotMaps, to now plot the self.map_core and self.map_duct
    def PlotMaps(self): # Plot performance in map(s)
        if self.map_core != None:
            self.map_core.PlotMap()
            # 1.4
            # print(self.name + " core map with operating curve saved in " + self.map_core.map_figure_pathname)
            print(f"{self.name} map (dual) with operating curve saved in {self.map_core.map_figure_pathname}")

            # 1.5
            self.map_core.PlotDualMap('Eta_is_core_')
            print(f"{self.name} core map (dual) with operating curve saved in {self.map_core.map_figure_pathname}")

        if self.map_duct != None:
            self.map_duct.PlotMap()
            # 1.4
            # print(self.name + " duct map with operating curve saved in " + self.map_duct.map_figure_pathname)
            print(f"{self.name} map (dual) with operating curve saved in {self.map_duct.map_figure_pathname}")

            # 1.5
            self.map_duct.PlotDualMap('Eta_is_duct_')
            print(f"{self.name} duct map (dual) with operating curve saved in {self.map_duct.map_figure_pathname}")
