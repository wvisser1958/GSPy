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
#   Oscar Kogenhop

import numpy as np
from gspy.core.turbomap import TTurboMap
import gspy.core.system as fsys

class TTurbineMap(TTurboMap):
    def __init__(self, host_component, name, MapFileName, OL_xcol, OL_Ycol, ShaftString, Ncmapdes, Betamapdes):
        super().__init__(host_component, name, MapFileName, OL_xcol, OL_Ycol, ShaftString, Ncmapdes, Betamapdes)
        self.LegacyMap = False

    def setLegacyMap(self, LegacyMap):
        self.LegacyMap = LegacyMap

    def ReadMap(self, filename):              # Abstract method, defined by convention only
        amaptype, amaptitle, amapfile = super().ReadMap(filename)
        # tbd : read stall line
        return amaptype, amaptitle, amapfile

    # 1.6 WV obsolete now, see below
    # def ReadPRlimits(self, mapfile, keyword):
    #     line = mapfile.readline()
    #     while keyword not in line.upper():
    #         line = mapfile.readline()
    #     line = mapfile.readline()
    #     items = line.split()
    #     nccount1= float(items[0])%1
    #     nccount = round(nccount1*1000)-1
    #     nc_values = np.empty(nccount, dtype=float)
    #     line = mapfile.readline()
    #     # items = line.split()
    #     prlimits_array = np.array(list(map(float, line.split()[1:])))
    #     return nc_values, prlimits_array

    def ReadMap(self, filename):              # Abstract method, defined by convention only
        super().ReadMap(filename)

        # 1.6 WV use ReadNcBetaCrossTable instead... (like surge limit in compressor)
        # this way, a line break half way the prmin_array values does not cause problems
        # read PR min values
        # self.nc_values, self.prmin_array = self.ReadPRlimits(self.mapfile, 'MIN PRESSURE RATIO')
        # self.nc_values, self.prmax_array = self.ReadPRlimits(self.mapfile, 'MAX PRESSURE RATIO')
        dummy_value, self.nc_values, self.prmin_array = self.ReadNcBetaCrossTable(self.mapfile, 'MIN PRESSURE RATIO')
        dummy_value, self.nc_values, self.prmax_array = self.ReadNcBetaCrossTable(self.mapfile, 'MAX PRESSURE RATIO')
        # convert from 2-D array with 1 row to a 1-D array
        self.prmin_array = self.prmin_array[0]
        self.prmax_array = self.prmax_array[0]

        self.nc_values, self.beta_values, self.wc_array = self.ReadNcBetaCrossTable(self.mapfile, 'MASS FLOW')
        self.nc_values, self.beta_values, self.eta_array = self.ReadNcBetaCrossTable(self.mapfile, 'EFFICIENCY')

        # now calculate PR_value table:
        # Unlike with the compressor, for the turbine PR values can be calculated
        self.pr_array = np.zeros((self.nc_values.size, self.beta_values.size), dtype=float)

        for irow in range(self.nc_values.size):
            for icol in range(self.beta_values.size):
                self.pr_array[irow, icol] = self.prmin_array[irow] + \
                    self.beta_values[icol] * (self.prmax_array[irow] - self.prmin_array[irow])

        # define the interpolation functions allow extrapolation (i.e. fill value = None)
        # self.get_map_wc = RegularGridInterpolator((self.nc_values, self.beta_values), self.wc_array, bounds_error=False, fill_value=None)
        # self.get_map_eta = RegularGridInterpolator((self.nc_values, self.beta_values), self.eta_array, bounds_error=False, fill_value=None)
        # self.get_map_pr = RegularGridInterpolator((self.nc_values, self.beta_values), self.pr_array, bounds_error=False, fill_value=None)
        self.DefineInterpolationFunctions()

    def PlotMap(self, use_scaled_map = True, do_plot_design_point = True, do_plot_series = True):
        super().PlotMap(use_scaled_map, do_plot_design_point, do_plot_series)

        if self.LegacyMap:
            # Plot Wc-PR
            for index, NcValue in enumerate(self.NcArrayValues):
                self.main_plot_axis.plot(self.PRArrayValues[index], self.WcArrayValues[index], linewidth=0.25, linestyle='dashed', color='black', label=str(NcValue))
            self.main_plot_axis.set_ylabel('Corected massflow')
            self.main_plot_axis.set_xlabel('Pressure Ratio')

            # Contours
            self.main_plot_axis.contourf(self.PRArrayValues,self.WcArrayValues,np.transpose(self.EtaArrayValues), 14 ,cmap='RdYlGn',alpha=0.3)
            CS = self.main_plot_axis.contour(self.PRArrayValues,self.WcArrayValues,np.transpose(self.EtaArrayValues),10,colors='slategrey',alpha=0.3,levels = np.linspace(0.64, 0.84, 11))
            self.main_plot_axis.clabel(CS, fontsize=7, inline=True)

            # Design point
            if do_plot_design_point:
                self.main_plot_axis.plot(fsys.OutputTable[(fsys.OutputTable['Mode'] == 'DP')][self.PR_comp_param].to_numpy(), fsys.OutputTable[(fsys.OutputTable['Mode'] == 'DP')][self.Wc_in_param].to_numpy(), markersize=6.0, linestyle='none', marker='s', markeredgewidth=0.75, markerfacecolor='yellow', markeredgecolor='black')

            # Operating line
            if do_plot_series:
                # Plotting PR - Wc
                self.main_plot_axis.plot(fsys.OutputTable[(fsys.OutputTable['Mode'] == 'OD')][self.PR_comp_param].to_numpy(), fsys.OutputTable[(fsys.OutputTable['Mode'] == 'OD')][self.Wc_in_param].to_numpy(),  linewidth=1.5, linestyle='solid', color='navy')
        else:
            # Plot Nc*Wc - PR
            Nc_times_WcArrayValues = self.WcArrayValues.copy()
            for index, NcValue in enumerate(self.NcArrayValues):
                Nc_times_WcArrayValues[index] *= NcValue
                x = NcValue * self.WcArrayValues[index]
                y = self.PRArrayValues[index]
                self.main_plot_axis.plot(x, y, linewidth=0.25, linestyle='dashed', color='black', label=str(NcValue), zorder=3)
                # Add NcValue text at the last point of the curve
                ymin, ymax = self.main_plot_axis.get_ylim()
                # self.main_plot_axis.text(x[-1], y[-1], f'{NcValue:.1f}', fontsize=8, ha='left', va='center')
                if index == 0:
                    text_label = f'Nc = {NcValue:.1f}'
                else:
                    text_label = f'{NcValue:.1f}'
                self.main_plot_axis.text(
                    x[-1], y[-1]-((ymax-ymin)/8), text_label,
                    fontsize=8, ha='left', va='bottom', rotation=-90
                )
            self.main_plot_axis.set_xlabel('Corected mass flow * Corrected speed')
            self.main_plot_axis.set_ylabel('Pressure Ratio')

            # Contours
            self.main_plot_axis.contourf(Nc_times_WcArrayValues,self.PRArrayValues,np.transpose(self.EtaArrayValues), 14 ,cmap='RdYlGn',alpha=0.3)
            CS = self.main_plot_axis.contour(Nc_times_WcArrayValues,self.PRArrayValues,np.transpose(self.EtaArrayValues),10,colors='slategrey',alpha=0.3,levels = np.linspace(0.64, 0.84, 11))
            self.main_plot_axis.clabel(CS, fontsize=7, inline=True)

            # Design point
            if do_plot_design_point:
                self.main_plot_axis.plot(
                    np.multiply(fsys.OutputTable[(fsys.OutputTable['Mode'] == 'DP')][self.Wc_in_param].to_numpy(),
                                fsys.OutputTable[(fsys.OutputTable['Mode'] == 'DP')][self.Nc_comp_param].to_numpy()),
                    fsys.OutputTable[(fsys.OutputTable['Mode'] == 'DP')][self.PR_comp_param].to_numpy(),
                    markersize=6.0, linestyle='none', marker='s', markeredgewidth=0.75, markerfacecolor='yellow', markeredgecolor='black')

            # Operating line
            if do_plot_series:
                # Plot PR-Nc*Wc
                self.main_plot_axis.plot(
                    np.multiply(fsys.OutputTable[(fsys.OutputTable['Mode'] == 'OD')][self.Wc_in_param].to_numpy(),
                                fsys.OutputTable[(fsys.OutputTable['Mode'] == 'OD')][self.Nc_comp_param].to_numpy()),
                    fsys.OutputTable[(fsys.OutputTable['Mode'] == 'OD')][self.PR_comp_param].to_numpy(),
                    linewidth=1.5, linestyle='solid', color='navy')

        self.map_figure.savefig(self.map_figure_pathname)

    def PlotDualMap(self, use_scaled_map = False, do_plot_design_point = False, do_plot_series = False):
        super().PlotDualMap(use_scaled_map, do_plot_design_point, do_plot_series)

        # Plot Pr-Eta top subplot
        for index, NcValue in enumerate(self.NcArrayValues):
            self.main_plot_axis.plot(self.PRArrayValues[index], self.EtaArrayValues[index], linewidth=0.25, linestyle='dashed', color='black', label=str(round(NcValue)))
            # 1.6.0.1 self.main_plot_axis.text(8, np.sin(8), "sin(x)", fontsize=12, color="blue")
        self.main_plot_axis.set_ylabel('Efficiency')
        # self.main_plot_axis.set_xlabel('Pressure Ratio')

        # Plot Pr-Eta bottom subplot
        for index, NcValue in enumerate(self.NcArrayValues):
            self.secondary_plot_axis.plot(self.PRArrayValues[index], self.WcArrayValues[index], linewidth=0.25, linestyle='dashed', color='black', label=str(round(NcValue)))
        self.secondary_plot_axis.set_ylabel('Corected mass flow')
        self.secondary_plot_axis.set_xlabel('Pressure Ratio')

        # Design point
        if do_plot_design_point:
            self.main_plot_axis.plot(fsys.OutputTable[(fsys.OutputTable['Mode'] == 'DP')][self.PR_comp_param].to_numpy(), fsys.OutputTable[(fsys.OutputTable['Mode'] == 'DP')]['Eta_is_' + str(self.host_component.name)].to_numpy(), markersize=6.0, linestyle='none', marker='s', markeredgewidth=0.75, markerfacecolor='yellow', markeredgecolor='black')
            self.secondary_plot_axis.plot(fsys.OutputTable[(fsys.OutputTable['Mode'] == 'DP')][self.PR_comp_param].to_numpy(), fsys.OutputTable[(fsys.OutputTable['Mode'] == 'DP')][self.Wc_in_param].to_numpy(), markersize=6.0, linestyle='none', marker='s', markeredgewidth=0.75, markerfacecolor='yellow', markeredgecolor='black')

        # Operating line
        if do_plot_series:
            # Plotting PR - Wc
            self.main_plot_axis.plot(fsys.OutputTable[(fsys.OutputTable['Mode'] == 'OD')][self.PR_comp_param].to_numpy(), fsys.OutputTable[(fsys.OutputTable['Mode'] == 'OD')]['Eta_is_' + str(self.host_component.name)].to_numpy(),  linewidth=1.5, linestyle='solid', color='navy')
            self.secondary_plot_axis.plot(fsys.OutputTable[(fsys.OutputTable['Mode'] == 'OD')][self.PR_comp_param].to_numpy(), fsys.OutputTable[(fsys.OutputTable['Mode'] == 'OD')][self.Wc_in_param].to_numpy(),  linewidth=1.5, linestyle='solid', color='navy')

        # self.dual_map_figure.tight_layout()
        self.dual_map_figure.savefig(self.map_figure_pathname)
