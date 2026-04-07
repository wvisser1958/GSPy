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
import gspy.core.utils as fu
from gspy.core.turbo_component import TTurboComponent
from gspy.core.compressormap import TCompressorMap

class TFan(TTurboComponent):
    def __init__(self, owner, name, MapFileName_core, station_in, station_out_core, station_out_duct, ShaftNr,
                 Ndes_core, Etades_core,
                # in TFan, Etades paramater = Etades_core
                #          MapFileName = name of core map file
                 BPRdes,
                 Ncmapdes_core, Betamapdes_core, PRdes_core,
                 MapFileName_duct,
                 Ncmapdes_duct, Betamapdes_duct, PRdes_duct, Etades_duct,
                #  v1.6 Cf factor for off-design duct-core cross flow correction
                # cf < 1 :  cross flow between duct/bypass and core sections (with different maps used for compression calculation)
                #           for cf = 0 : cross flow between fan exit and splitter, we need to mix some of the core flow with bypass or
                #           vice versa, so that the flow distribution is corresponding to the off-design bypass ratio
                #           0 < cf < 1 : the cf factor determines the fraction of the cross flow actually compressed by the map
                #           of 'the other side' (1-cf) * cross flow
                # cf = 1 :  no cross flow between duct/bypass and core sections (with different maps used for compression calculation)
                #           the flow distribution to core and duct/bypass maps remains corresponding to design BPR (BPRdes)
                # default value for cf = 1 : most stable, assuming the duct-core dividing stream line remains the same as with BPRdes
                cf = 1):

        # TTurboComponent parent class creator    no control link
        # 1.6 WV at this stage no variable geometry in this fan model, so VGparvaluedes = None and only a single map file for core and one for duct
        super().__init__(owner, name, MapFileName_core, '', station_in, station_out_core, ShaftNr, Ndes_core, Etades_core, Ncmapdes_core, Betamapdes_core)

        self.station_out_duct = station_out_duct

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

        # 1.6
        self.cf = cf

    def GetSlWcValues(self):
        return self.sl_wc_array

    def GetSlPrValues(self):
        return self.sl_pr_array

    def Run(self, Mode, PointTime):
        super().Run(Mode, PointTime)

        if Mode == 'DP':
            self.BPR = self.BPRdes
            # create gas_out_duct ct.Quantity here
            self.gas_out_duct = ct.Quantity(self.gas_in.phase, mass = 1)
            #  1.5
            self.OD_crossFlow = ct.Quantity(self.gas_in.phase, mass = 1)
        else:
            self.BPR = self.owner.states[self.istate_BPR] * self.BPRdes

        # 1.5 bug fix !!!! 20-12-2025 W. Visser
        # W_core_in and W_duct_in are always the part corresponding to BPRdes  (design value!, we split the core and duct/bypass corresponding to BPRdes)
        # W_core_in and W_duct_in are used for the mass flow error equations at the end of this procedure
        # THIS IS EQUIVALENT TO CF = 0 om GSP
        # self.W_core_in = self.gas_in.mass               / (self.BPRdes + 1)
        # self.W_duct_in = self.gas_in.mass * self.BPRdes / (self.BPRdes + 1)


        # *********** Lucas Cf implementation ***********
        # design split (always based on BPRdes)
        self.W_core_BPRdes = self.gas_in.mass / (self.BPRdes + 1.0)
        self.W_duct_BPRdes = self.gas_in.mass * self.BPRdes / (self.BPRdes + 1.0)

        # cross-flow due to BPR change (eq. 3-20)
        self.crossflow = self.gas_in.mass * (self.BPR / (self.BPR + 1.0) - (self.BPRdes / (self.BPRdes + 1.0)))

        # effective inlet flows for maps (eq. 3-21, 3-22)
        self.W_core_in = self.W_core_BPRdes - self.cf * self.crossflow
        self.W_duct_in = self.W_duct_BPRdes + self.cf * self.crossflow

        #  set exit flows
        self.gas_out.mass       = self.W_core_in
        self.gas_out_duct.mass  = self.W_duct_in

        if Mode == 'DP':
            # correct mass flow
            self.Wdes_core_in = self.W_core_in
            self.Wcdes_core_in = self.Wdes_core_in * fu.GetFlowCorrectionFactor(self.gas_in)
            self.map_core.ReadMapAndGetScaling(self.Ncdes, self.Wcdes_core_in, self.PRdes_core, self.Etades_core)
            self.PW_core = fu.Compression(self.gas_in, self.gas_out, self.PRdes_core, self.Etades_core, self.Polytropic_Eta)

            # # add fan duct side compression
            # self.Wdes_duct = self.gas_in.mass - self.gas_out.mass
            self.Wdes_duct_in = self.W_duct_in
            self.Wcdes_duct_in = self.W_duct_in * fu.GetFlowCorrectionFactor(self.gas_in)
            self.map_duct.ReadMapAndGetScaling(self.Ncdes, self.Wcdes_duct_in, self.PRdes_duct, self.Etades_duct)
            self.PW_duct = fu.Compression(self.gas_in, self.gas_out_duct, self.PRdes_duct, self.Etades_duct, self.Polytropic_Eta)

            self.PW = self.PW_core + self.PW_duct
            self.shaft.PW_sum = self.shaft.PW_sum - self.PW

            # add states and errors
            #  rotor speed
            self.owner.states = np.append(self.owner.states, 1)
            self.istate_n = self.owner.states.size-1
            self.shaft.istate = self.istate_n
            # state for bypass ratio BPR
            self.owner.states = np.append(self.owner.states, 1)
            self.istate_BPR = self.owner.states.size-1
            #  map beta core
            self.owner.states = np.append(self.owner.states, 1)
            self.istate_beta_core = self.owner.states.size-1
            # map beta duct
            self.owner.states = np.append(self.owner.states, 1)
            self.istate_beta_duct = self.owner.states.size-1

            # error for equation gas_in.mass = W (W according to map operating point)
            self.owner.errors = np.append(self.owner.errors, 0)
            self.ierror_wc_core = self.owner.errors.size-1
            self.owner.errors = np.append(self.owner.errors, 0)
            self.ierror_wc_duct = self.owner.errors.size-1

            # calculate parameters for output
            self.PR_core  = self.PRdes_core
            self.PR_duct = self.PRdes_duct
            self.Wc_core = self.Wcdes_core_in
            self.Wc_duct = self.Wcdes_duct_in
            self.Eta_core = self.Etades_core
            self.Eta_duct = self.Etades_duct

        else:
            self.N = self.owner.states[self.istate_n] * self.Ndes
            self.Nc = self.N / fu.GetRotorspeedCorrectionFactor(self.gas_in)

            self.Wc_core, self.PR_core, self.Eta_core = self.map_core.GetScaledMapPerformance(self.Nc, self.owner.states[self.istate_beta_core])
            self.Wc_duct, self.PR_duct, self.Eta_duct = self.map_duct.GetScaledMapPerformance(self.Nc, self.owner.states[self.istate_beta_duct])

            self.PW_core = fu.Compression(self.gas_in, self.gas_out, self.PR_core, self.Eta_core, self.Polytropic_Eta)
            self.PW_duct = fu.Compression(self.gas_in, self.gas_out_duct, self.PR_duct, self.Eta_duct, self.Polytropic_Eta)

            self.PW = self.PW_core + self.PW_duct

            self.shaft.PW_sum = self.shaft.PW_sum - self.PW

            self.W_core = self.Wc_core / fu.GetFlowCorrectionFactor(self.gas_in)
            self.owner.errors[self.ierror_wc_core ] = (self.W_core - self.W_core_in) / self.Wdes
            self.W_duct = self.Wc_duct / fu.GetFlowCorrectionFactor(self.gas_in)
            self.owner.errors[self.ierror_wc_duct ] = (self.W_duct - self.W_duct_in) / self.Wdes

            # self.gas_out.mass = self.W_core  # self.gas_out = core flow = gas_out_core
            # self.gas_out_duct.mass = self.W_duct

            # 1.5   now correct the out flow W, and P and H with the
            #       crossover flow dw_to_duct, between fan exit and splitter,
            #       due to BPR changing from BPRdes
            #       when dw_to_duct > 0, flow from core to duct side
            # win = self.W_core + self.W_duct

            # wd_split = win * self.BPR/(self.BPR+1)
            # wc_split = win *        1/(self.BPR+1)
            # dw_to_duct1 = wd_split - self.W_duct

            # # self.dw_to_duct = self.gas_in.mass * (1/(self.BPRdes + 1) - 1/(self.BPR + 1))
            # self.dw_to_duct = win * (1/(self.BPRdes + 1) - 1/(self.BPR + 1))

            # ************ Lucas Cf implementation ***********
            crossflow_to_add = self.crossflow * (1-self.cf)

            if crossflow_to_add > 0:  # i.e. BPR > BPRdes
                # adjust duct flow properties with some of the core flow (flowing into the duct)
                self.gas_out.mass = self.gas_out.mass - crossflow_to_add
                self.OD_crossFlow.mass = crossflow_to_add
                self.OD_crossFlow.HP = fu.scalar(self.gas_out.enthalpy_mass), self.gas_out.P
                self.gas_out_duct = self.gas_out_duct + self.OD_crossFlow
                # 1.6.0.7 obsolete
                # self.gas_out_duct.equilibrate("HP")
            else:
                # adjust core flow properties with some of the duct flow (flowing into the core)
                self.gas_out_duct.mass = self.gas_out_duct.mass + crossflow_to_add
                self.OD_crossFlow.mass = - crossflow_to_add
                self.OD_crossFlow.HP = fu.scalar(self.gas_out_duct.enthalpy_mass), self.gas_out_duct.P
                self.gas_out = self.gas_out + self.OD_crossFlow
                # 1.6.0.7 obsolete
                # self.gas_out.equilibrate("HP")

        # calculate parameters for output
        self.Wc = fu.scalar(self.gas_in.mass) * fu.GetFlowCorrectionFactor(self.gas_in)

        # assigne gas_out_duct to gaspath_conditions dictionary, for the core flow already done in TGaspath parent class
        self.owner.gaspath_conditions[self.station_out_duct] = self.gas_out_duct
        return self.gas_out, self.gas_out_duct

    def PrintPerformance(self, mode, PointTime):
        super().PrintPerformance(mode, PointTime)
        print(f"\tRotor speed  : {self.N:.0f} rpm")
        print(f"\tCorr Rotor speed : {self.Nc:.0f} rpm")
        if self.map_core != None:
            print(f"\tCore Map:")
            self.print_map_data(self.map_core, mode)

        if self.map_duct != None:
            print(f"\tDuct Map:")
            self.print_map_data(self.map_duct, mode)

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
                                     "Eta_is_core_"+self.name, "Eta_is_duct_"+self.name,
                                     # test
                                     "dw_to_duct"]
        return column_list

    # 2.0.0.0
    def get_outputs(self):
        out = super().get_outputs()
        out["BPR_"+self.name] = self.BPR
        out["crossflow_"+self.name] = self.crossflow
        out["PR_core_"+self.name] = self.PR_core
        out["PR_duct_"+self.name] = self.PR_duct
        out["Wc_core_"+self.name] = self.Wc_core
        out["Wc_duct_"+self.name] = self.Wc_duct
        out["Eta_is_core_"+self.name] = self.Eta_core
        out["Eta_is_duct_"+self.name] = self.Eta_duct
        return out

    # override PlotMaps, to now plot the self.map_core and self.map_duct
    def PlotMaps(self): # Plot performance in map(s)
        if self.map_core != None:
            self.map_core.PlotMap()
            # 1.4
            # print(self.name + " core map with operating curve saved in " + self.map_core.map_figure_file_path)
            print(f"{self.name} map (dual) with operating curve saved in {self.map_core.map_figure_file_path}")

            # 1.5
            self.map_core.PlotDualMap('Eta_is_core_')
            print(f"{self.name} core map (dual) with operating curve saved in {self.map_core.map_figure_file_path}")

        if self.map_duct != None:
            self.map_duct.PlotMap()
            # 1.4
            # print(self.name + " duct map with operating curve saved in " + self.map_duct.map_figure_file_path)
            print(f"{self.name} map (dual) with operating curve saved in {self.map_duct.map_figure_file_path}")

            # 1.5
            self.map_duct.PlotDualMap('Eta_is_duct_')
            print(f"{self.name} duct map (dual) with operating curve saved in {self.map_duct.map_figure_file_path}")
