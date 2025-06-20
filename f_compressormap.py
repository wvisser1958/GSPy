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
from f_turbomap import TTurboMap
import f_system as fsys

class TCompressorMap(TTurboMap):
    def __init__(self, host_component, name, MapFileName, OL_xcol, OL_Ycol, ShaftString, Ncmapdes, Betamapdes):
        super().__init__(host_component, name, MapFileName, OL_xcol, OL_Ycol, ShaftString, Ncmapdes, Betamapdes)

    def GetSlWcValues(self):
        return self.sl_wc_array

    def GetSlPrValues(self):
        return self.sl_pr_array

    def ReadMap(self, filename):
        super().ReadMap(filename)
        self.nc_values, self.beta_values, self.wc_array = self.ReadNcBetaCrossTable(self.mapfile, 'MASS FLOW')
        self.nc_values, self.beta_values, self.eta_array = self.ReadNcBetaCrossTable(self.mapfile, 'EFFICIENCY')
        self.nc_values, self.beta_values, self.pr_array = self.ReadNcBetaCrossTable(self.mapfile, 'PRESSURE RATIO')
        dummy_value, self.sl_wc_array, self.sl_pr_array = self.ReadNcBetaCrossTable(self.mapfile, 'SURGE LINE')
        self.DefineInterpolationFunctions()

    def PlotMap(self, use_scaled_map = True, do_plot_design_point = True, do_plot_series = True):
        super().PlotMap(use_scaled_map, do_plot_series)

        if use_scaled_map:
            self.compSlWcArrayValues = self.sl_wc_array * self.SFmap_Wc
            # must scale around PR = 1
            # self.compSlPRArrayValues = self.sl_pr_array * self.SFmap_PR
            self.compSlPRArrayValues = (self.sl_pr_array - 1) * self.SFmap_PR + 1
        else:
            self.compSlWcArrayValues = self.sl_wc_array
            self.compSlPRArrayValues = self.sl_pr_array

        # Plot Wc-PR top subplot
        for index, NcValue in enumerate(self.NcArrayValues):
            x = self.WcArrayValues[index]
            y = self.PRArrayValues[index]
            self.main_plot_axis.plot(x, y, linewidth=0.25, linestyle='dashed', color='black', label=str(NcValue))
            # Add NcValue text at the last point of the curve
            ymin, ymax = self.main_plot_axis.get_ylim()
            # self.main_plot_axis.text(x[-1], y[-1], f'{NcValue:.1f}', fontsize=8, ha='left', va='center')
            if index == 0:
                text_label = f'Nc = {NcValue:.1f}'
            else:
                text_label = f'{NcValue:.1f}'
            self.main_plot_axis.text(
                x[0], y[0], text_label,
                fontsize=8, ha='left', va='center'
            )
        self.main_plot_axis.set_xlabel('Corected massflow')
        self.main_plot_axis.set_ylabel('Pressure Ratio')

        # Plot surge line
        self.main_plot_axis.plot(self.compSlWcArrayValues, self.compSlPRArrayValues[0], linewidth=1.0, linestyle='solid', color='red', label='Surge Line')
        # self.ax.legend()

        # Contours
        Wc_grid, PR_grid, Eta_grid = self.CalcMapEtaTopology(self.WcArrayValues,self.PRArrayValues,self.EtaArrayValues,False)
        CS = self.main_plot_axis.contour(Wc_grid,PR_grid,Eta_grid,10,colors='slategrey',alpha=0.3,levels = np.linspace(0.64, 0.84, 11))
        self.main_plot_axis.clabel(CS, fontsize=7, inline=True)
        self.main_plot_axis.contourf(Wc_grid, PR_grid, Eta_grid, 14 , cmap='RdYlGn', alpha=0.3)

        # Design point
        if do_plot_design_point:
            self.main_plot_axis.plot(fsys.OutputTable[(fsys.OutputTable['Mode'] == 'DP')][self.Wc_in_param].to_numpy(),
                                     fsys.OutputTable[(fsys.OutputTable['Mode'] == 'DP')][self.PR_comp_param].to_numpy(),
                                     markersize=6.0, linestyle='none', marker='s', markeredgewidth=0.75, markerfacecolor='yellow',
                                     markeredgecolor='black')

        # Operating line
        if do_plot_series:
            # Plotting Wc - PR
            self.main_plot_axis.plot(fsys.OutputTable[(fsys.OutputTable['Mode'] == 'OD')][self.Wc_in_param].to_numpy(),
                                     fsys.OutputTable[(fsys.OutputTable['Mode'] == 'OD')][self.PR_comp_param].to_numpy(),
                                     linewidth=1.5, linestyle='solid', color='navy')

        self.map_figure.savefig(self.map_figure_pathname)

    def PlotDualMap(self, use_scaled_map = True, do_plot_design_point = True, do_plot_series = True):
        super().PlotDualMap(use_scaled_map, do_plot_series)

        # Plot Wc-Eta top subplot
        for index, NcValue in enumerate(self.NcArrayValues):
            self.main_plot_axis.plot(self.WcArrayValues[index], self.EtaArrayValues[index], linewidth=0.25, linestyle='dashed', color='black', label=str(round(NcValue)))
            self.main_plot_axis.text(8, np.sin(8), "sin(x)", fontsize=12, color="blue")
        self.main_plot_axis.set_ylabel('Efficiency')
        # self.main_plot_axis.set_xlabel('Pressure Ratio')

        # Plot Pr-Eta bottom subplot
        for index, NcValue in enumerate(self.NcArrayValues):
            self.secondary_plot_axis.plot(self.WcArrayValues[index], self.PRArrayValues[index], linewidth=0.25, linestyle='dashed', color='black', label=str(round(NcValue)))
        self.secondary_plot_axis.set_ylabel('Pressure Ratio')
        self.secondary_plot_axis.set_xlabel('Corrected Mass Flow')

        # # Contours TODO
        # PR_grid, Wc_grid, Eta_grid = self.CalcMapEtaTopology(self.WcArrayValues,self.PRArrayValues,self.EtaArrayValues,False)
        # CS = self.main_plot_axis.contour(Wc_grid,PR_grid,np.transpose(Eta_grid),10,colors='slategrey',alpha=0.3,levels = np.linspace(0.64, 0.84, 11))
        # self.main_plot_axis.clabel(CS, fontsize=7, inline=True)
        # self.main_plot_axis.contourf(Wc_grid,PR_grid,np.transpose(Eta_grid), 14 ,cmap='RdYlGn',alpha=0.3)

        # Design point
        if do_plot_design_point:
            self.main_plot_axis.plot(fsys.OutputTable[(fsys.OutputTable['Mode'] == 'DP')][self.Wc_in_param].to_numpy(), fsys.OutputTable[(fsys.OutputTable['Mode'] == 'DP')]['Eta_is_' + str(self.host_component.name)].to_numpy(), markersize=6.0, linestyle='none', marker='s', markeredgewidth=0.75, markerfacecolor='yellow', markeredgecolor='black')
            self.secondary_plot_axis.plot(fsys.OutputTable[(fsys.OutputTable['Mode'] == 'DP')][self.Wc_in_param].to_numpy(), fsys.OutputTable[(fsys.OutputTable['Mode'] == 'DP')][self.PR_comp_param].to_numpy(), markersize=6.0, linestyle='none', marker='s', markeredgewidth=0.75, markerfacecolor='yellow', markeredgecolor='black')

        # Operating line
        if do_plot_series:
            # Plotting Wc - PR
            self.main_plot_axis.plot(fsys.OutputTable[(fsys.OutputTable['Mode'] == 'OD')][self.Wc_in_param].to_numpy(), fsys.OutputTable[(fsys.OutputTable['Mode'] == 'OD')]['Eta_is_' + str(self.host_component.name)].to_numpy(),  linewidth=1.5, linestyle='solid', color='navy')
            self.secondary_plot_axis.plot(fsys.OutputTable[(fsys.OutputTable['Mode'] == 'OD')][self.Wc_in_param].to_numpy(), fsys.OutputTable[(fsys.OutputTable['Mode'] == 'OD')][self.PR_comp_param].to_numpy(),  linewidth=1.5, linestyle='solid', color='navy')

        # self.dual_map_figure.tight_layout()
        self.dual_map_figure.savefig(self.map_figure_pathname)