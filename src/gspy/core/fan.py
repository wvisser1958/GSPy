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
from gspy.core.flow_state import TFlowState
from gspy.core.turbo_component import TTurboComponent
from gspy.core.compressormap import TCompressorMap


class TFan(TTurboComponent):
    def __init__(self, 
                    *,     
                    map_filename_core, 
                    map_filename_duct, 
                    station_out_core, station_out_duct, 
                    BPRdes,                    
                    PRdes_core, Etades_core, Ncmapdes_core, Betamapdes_core, 
                    PRdes_duct, Etades_duct, Ncmapdes_duct, Betamapdes_duct, 
                    #  v1.6 Cf factor for off-design duct-core cross flow correction
                    # cf < 1 :  cross flow between duct/bypass and core sections (with different maps used for compression calculation)
                    #           for cf = 0 : cross flow between fan exit and splitter, we need to mix some of the core flow with bypass or
                    #           vice versa, so that the flow distribution is corresponding to the off-design bypass ratio
                    #           0 < cf < 1 : the cf factor determines the fraction of the cross flow actually compressed by the map
                    #           of 'the other side' (1-cf) * cross flow
                    # cf = 1 :  no cross flow between duct/bypass and core sections (with different maps used for compression calculation)
                    #           the flow distribution to core and duct/bypass maps remains corresponding to design BPR (BPRdes)
                    # default value for cf = 1 : most stable, assuming the duct-core dividing stream line remains the same as with BPRdes
                    # see image Fan_model_BPR_Cf_factor.png 
                    cf = 1,
                    **kwargs):

        # TTurboComponent parent class creator    no control link
        # 1.6 WV at this stage no variable geometry in this fan model, so VGparvaluedes = None and only a single map file for core and one for duct
        super().__init__( # map_filename, leave map_filename = None, because we have 2 maps now, one for core and one for duct
                         station_out = station_out_core, 
                         Etades = Etades_core, 
                         Ncmapdes = Ncmapdes_core, 
                         Betamapdes = Betamapdes_core,
                         **kwargs)
        self.station_out_duct = station_out_duct

        self.fs_out_duct = TFlowState.create_empty(self.system.gas, station_nr=self.station_out_duct)
        self.fs_crossflow = TFlowState.create_empty(self.system.gas, station_nr=self.station_out)

        self.BPRdes = BPRdes

        # core side map
        self.map_core = TCompressorMap(self, self.name + '_map_core', 
                                       map_filename_core, "Wc_core_"+self.name, "PR_core_"+self.name, self.shaft_id, 
                                       Ncmapdes_core, Betamapdes_core)
        self.PRdes_core = PRdes_core
        #  1.5 set self.Etades to None, use Etadec_core instead to avoid duplicate in output
        #      checking if self.Etades non None in TTurboComponent
        self.Etades_core = self.Etades
        self.Etades = None

        # duct side map
        self.map_duct = TCompressorMap(self, self.name + '_map_duct', 
                                       map_filename_duct, "Wc_duct_"+self.name, "PR_duct_"+self.name, self.shaft_id, 
                                       Ncmapdes_duct, Betamapdes_duct)
        self.PRdes_duct = PRdes_duct
        self.Etades_duct = Etades_duct

        # 1.6
        if not 0.0 <= cf <= 1.0:
            raise ValueError(f"cf factor must be between 0 and 1, got {cf}")
        self.cf = cf

    def GetSlWcValues(self):
        return self.sl_wc_array

    def GetSlPrValues(self):
        return self.sl_pr_array

    def Run(self, Mode, PointTime):
        super().Run(Mode, PointTime)

        if Mode == 'DP':
            self.BPR = self.BPRdes

            # # create fs_out_duct ct.Quantity here
            # self.fs_out_duct = ct.Quantity(self.fs_in.phase, mass = 1)
            # #  1.5
            # self.OD_crossFlow = ct.Quantity(self.fs_in.phase, mass = 1)

            # self.fs_out_duct = TFlowState.create_empty(self.system.gas, station_nr=self.station_out_duct)
            # self.fs_out_duct.copy_from(self.fs_in, self.station_in)
            # self.fs_crossflow = TFlowState.create_empty(self.system.gas, station_nr=self.station_out)
            # self.fs_crossflow.copy_from(self.fs_in, self.station_in)
        else:
            self.BPR = self.system.states[self.istate_BPR] * self.BPRdes

        # self.fs_out.copy_from(self.fs_in, self.station_in, scale_W = 1/(self.BPR + 1))
        # self.fs_out_duct.copy_from(self.fs_in, self.station_in, scale_W = self.BPR/(self.BPR + 1))

        # 1.5 bug fix !!!! 20-12-2025 W. Visser
        # W_core_in and W_duct_in are always the part corresponding to BPRdes  (design value!, we split the core and duct/bypass corresponding to BPRdes)
        # W_core_in and W_duct_in are used for the mass flow error equations at the end of this procedure
        # THIS IS EQUIVALENT TO CF = 0 om GSP
        # self.W_core_in = self.gas_in.mass               / (self.BPRdes + 1)
        # self.W_duct_in = self.gas_in.mass * self.BPRdes / (self.BPRdes + 1)

        # *********** Lucas Cf implementation ***********
        # design split (based on BPRdes !!!! ) / gas only ! W_liq not included Wc for compressor map
        self.W_gas_core_BPR_design = self.fs_in.W_gas / (self.BPRdes + 1.0)
        self.W_gas_duct_BPR_design = self.fs_in.W_gas - self.W_gas_core_BPR_design

        # cross-flow due to BPR change (eq. 3-20)
        if Mode == 'DP':
            self.W_crossflow = 0.0
        else:
            self.W_crossflow = self.fs_in.W * (self.BPR / (self.BPR + 1.0) - (self.BPRdes / (self.BPRdes + 1.0)))

        # effective inlet flows for maps (eq. 3-21, 3-22)
        # for cf = 1, the off-design flow distribution to core and duct/bypass maps will be corresponding to actual BPR (off-design BPR)
        #             so there is cross flow between duct/bypass and core sections BEFORE the fan rotor inlet
        #             if Cf<1, som of the cross flow will be compressed by the map of 'the other side' (1-cf) * cross flow   
        # for cf = 0, the off-design flow distribution to core and duct/bypass maps remains corresponding to design BPR (BPRdes)
        #             there is only cross flow after the end of the fan compression, to correspond to the off design BPR
        # for 0 < Cf < 1 at BPR deviation from BPRdes, a part of the cross flow is compressed by the map of 'the other side' (1-cf) * cross flow
        self.W_gas_core_in_for_map = self.W_gas_core_BPR_design - self.cf * self.W_crossflow
        # = self.fs_in.mass / (self.BPRdes + 1.0) - self.cf * self.fs_in.W * (self.BPR / (self.BPR + 1.0) - (self.BPRdes / (self.BPRdes + 1.0)))
        # self.W_core_in/self.fs_in.W = 1/(self.BPRdes + 1.0) - self.cf * (self.BPR / (self.BPR + 1.0) - (self.BPRdes / (self.BPRdes + 1.0)))
        self.W_gas_duct_in_for_map = self.W_gas_duct_BPR_design + self.cf * self.W_crossflow

        #  set exit flows for the maps, corresponding to the inlet flows for the maps, which are based on BPRdes and cf factor
        # self.fs_out.copy_from(self.fs_in, self.station_in, scale_W = 1/(self.BPR + 1))
        # self.fs_out_duct.copy_from(self.fs_in, self.station_in, scale_W = self.BPR/(self.BPR + 1))
# self.fs_out.copy_from(self.fs_in, self.station_in, scale_W = self.W_gas_core_in_for_map/self.fs_in.W_gas)
# self.fs_out_duct.copy_from(self.fs_in, self.station_in, scale_W = self.W_gas_duct_in_for_map/self.fs_in.W_gas)

        if Mode == 'DP':
            # correct mass flow
            self.Wcdes_core_in = self.W_gas_core_in_for_map * fu.GetFlowCorrectionFactor(self.fs_in)
            self.map_core.ReadMapAndGetScaling(self.Ncdes, self.Wcdes_core_in, self.PRdes_core, self.Etades_core)
            # PW_core_old = fu.Compression(self.fs_in, self.fs_out, self.PRdes_core, self.Etades_core, self.Polytropic_DP_eta)
# self.fs_out, self.PW_core = self.fs_out.compress_real_eta(
            self.fs_out, self.PW_core = self.fs_in.compress_real_eta(
                PR=self.PRdes_core,
                out=self.fs_out,
                eta=self.Etades_core,
                Polytropic_Eta=self.Polytropic_DP_eta,
                W_out = self.W_gas_core_in_for_map
            )

            # # add fan duct side compression
            self.Wcdes_duct_in = self.W_gas_duct_in_for_map * fu.GetFlowCorrectionFactor(self.fs_in)
            self.map_duct.ReadMapAndGetScaling(self.Ncdes, self.Wcdes_duct_in, self.PRdes_duct, self.Etades_duct)

            # PW_duct_old = fu.Compression(self.fs_in, self.fs_out_duct, self.PRdes_duct, self.Etades_duct, self.Polytropic_DP_eta)

#            self.fs_out_duct, self.PW_duct = self.fs_out_duct.compress_real_eta(
            self.fs_out_duct, self.PW_duct = self.fs_in.compress_real_eta(
                PR=self.PRdes_duct,
                out=self.fs_out_duct,
                eta=self.Etades_duct,
                Polytropic_Eta=self.Polytropic_DP_eta,
                W_out = self.W_gas_duct_in_for_map
            )

            # add states and errors
            #  rotor speed
            # self.system.states = np.append(self.system.states, 1)
            # self.istate_n = self.system.states.size-1
            self.istate_n = self.system.add_state(self.name + '_N', 1.0)
            self.shaft.istate = self.istate_n

            # state for bypass ratio BPR            
            # self.system.states = np.append(self.system.states, 1)
            # self.istate_BPR = self.system.states.size-1
            self.istate_BPR = self.system.add_state(self.name + '_BPR', 1.0)

            #  map beta core
            # self.system.states = np.append(self.system.states, 1)
            # self.istate_beta_core = self.system.states.size-1
            self.istate_beta_core = self.system.add_state(self.name + '_beta_core', 1.0)

            # map beta duct
            # self.system.states = np.append(self.system.states, 1)
            # self.istate_beta_duct = self.system.states.size-1
            self.istate_beta_duct = self.system.add_state(self.name + '_beta_duct', 1.0)

            # error for equation gas_in.mass = W (W according to map operating point)
            # self.system.errors = np.append(self.system.errors, 0)
            # self.ierror_wc_core = self.system.errors.size-1
            self.ierror_wc_core = self.system.add_error(self.name + '_Wc_core', 0.0)

            # self.system.errors = np.append(self.system.errors, 0)
            # self.ierror_wc_duct = self.system.errors.size-1
            self.ierror_wc_duct = self.system.add_error(self.name + '_Wc_duct', 0.0)

            # calculate parameters for output
            self.PR_core  = self.PRdes_core
            self.PR_duct = self.PRdes_duct
            self.Wc_core = self.Wcdes_core_in
            self.Wc_duct = self.Wcdes_duct_in
            self.Eta_core = self.Etades_core
            self.Eta_duct = self.Etades_duct

        else:
            self.N = self.system.states[self.istate_n] * self.Ndes
            self.Nc = self.N / fu.GetRotorspeedCorrectionFactor(self.fs_in)

            self.Wc_core, self.PR_core, self.Eta_core = self.map_core.GetScaledMapPerformance(self.Nc, self.system.states[self.istate_beta_core])
            self.Wc_duct, self.PR_duct, self.Eta_duct = self.map_duct.GetScaledMapPerformance(self.Nc, self.system.states[self.istate_beta_duct])

            # self.PW_core = fu.Compression(self.fs_in, self.fs_out, self.PR_core, self.Eta_core, 0)
            # self.PW_duct = fu.Compression(self.fs_in, self.fs_out_duct, self.PR_duct, self.Eta_duct, 0)
            self.fs_out, self.PW_core = self.fs_in.compress_real_eta(
                PR=self.PR_core,
                out=self.fs_out,
                eta=self.Eta_core,
                Polytropic_Eta=False,  # OD eta always isentropic
                W_out = self.W_gas_core_in_for_map
            )
            self.fs_out_duct, self.PW_duct = self.fs_in.compress_real_eta(
                PR=self.PR_duct,
                out=self.fs_out_duct,
                eta=self.Eta_duct,
                Polytropic_Eta=False,  # OD eta always isentropic
                W_out = self.W_gas_duct_in_for_map
            )

            self.W_core = self.Wc_core / fu.GetFlowCorrectionFactor(self.fs_in)
            self.system.errors[self.ierror_wc_core ] = (self.W_core - self.W_gas_core_in_for_map) / self.fs_in_des.W_gas
            self.W_duct = self.Wc_duct / fu.GetFlowCorrectionFactor(self.fs_in)
            self.system.errors[self.ierror_wc_duct ] = (self.W_duct - self.W_gas_duct_in_for_map) / self.fs_in_des.W_gas

            # self.fs_out.mass = self.W_core  # self.fs_out = core flow = fs_out_core
            # self.fs_out_duct.mass = self.W_duct

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
            # now we need to correct the out flow W, and P and H with the crossover flow dw_to_duct, between fan exit and splitter,
            # due to BPR changing from BPRdes, and the cf factor for cross flow
            crossflow_to_add = self.W_crossflow * (1-self.cf)

            cf_tolerance = 1e-4
            if self.cf < 1-cf_tolerance: # only add crossflow if cf significantly < 1 (crossflow_to_add significant)
                if crossflow_to_add > 0:  # i.e. BPR > BPRdes
                    # adjust duct flow properties with some of the core flow (flowing into the duct)
                    # reduce core flow mass:
                    self.fs_out.scale_mass((self.fs_out.W - crossflow_to_add)/self.fs_out.W)
                    # add W_crossflow to duct flow mass:
                    # assign crossflow flowstate properties to the crossflow flowstate, for adding to the duct flow
                    self.fs_crossflow.copy_from(self.fs_out, self.station_out, scale_W = crossflow_to_add/self.fs_out.W)
                    # interpolate the pressure of the mixed flow, based on the mass flow weighted average of the pressures of the two flows
                    P_out_mixed = (self.fs_out_duct.P*self.fs_out_duct.W + self.fs_crossflow.P*self.fs_crossflow.W)/(self.fs_out_duct.W + self.fs_crossflow.W)
                    self.fs_out_duct.mix_same_composition_gas_only(self.fs_out_duct, self.fs_crossflow, P_out=P_out_mixed)
                else:
                    # adjust core flow properties with some of the duct flow (flowing into the core)
                    # reduce duct flow mass:
                    self.fs_out_duct.scale_mass((self.fs_out_duct.W + crossflow_to_add)/self.fs_out_duct.W)
                    # add W_crossflow to core flow mass:
                    # assign crossflow flowstate properties to the crossflow flowstate, for adding to the core flow
                    self.fs_crossflow.copy_from(self.fs_out_duct, self.station_out, scale_W = -crossflow_to_add/self.fs_out_duct.W)
                    # interpolate the pressure of the mixed flow, based on the mass flow weighted average of the pressures of the two flows
                    P_out_mixed = (self.fs_out.P*self.fs_out.W + self.fs_crossflow.P*self.fs_crossflow.W)/(self.fs_out.W + self.fs_crossflow.W)
                    self.fs_out.mix_same_composition_gas_only(self.fs_out, self.fs_crossflow, P_out=P_out_mixed)

        # total power and shaft power balance
        self.PW = self.PW_core + self.PW_duct
        self.shaft.PW_sum = self.shaft.PW_sum - self.PW

        # calculate parameters for output
        self.Wc = fu.scalar(self.fs_in.mass) * fu.GetFlowCorrectionFactor(self.fs_in)

        # assigne fs_out_duct to gaspath_conditions dictionary, for the core flow already done in TGaspath parent class
        self.system.gaspath_conditions[self.station_out_duct] = self.fs_out_duct
        return self.fs_out, self.fs_out_duct

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
        out["BPR"+self.id] = self.BPR
        out["crossflow"+self.id] = self.W_crossflow
        out["PR_core"+self.id] = self.PR_core
        out["PR_duct"+self.id] = self.PR_duct
        out["Wc_core"+self.id] = self.Wc_core
        out["Wc_duct"+self.id] = self.Wc_duct
        out["Eta_is_core"+self.id] = self.Eta_core
        out["Eta_is_duct"+self.id] = self.Eta_duct
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
