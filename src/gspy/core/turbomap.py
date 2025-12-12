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
import matplotlib.pyplot as plt
from gspy.core.map import TMap
from scipy.interpolate import RegularGridInterpolator

class TTurboMap(TMap):
    def __init__(self, host_component, name, MapFileName, OL_xcol, OL_Ycol, ShaftString, Ncmapdes, Betamapdes):    # Constructor of the class
        super().__init__(host_component, name, MapFileName, OL_xcol, OL_Ycol)
        self.Ncmapdes = Ncmapdes
        self.Betamapdes = Betamapdes
        self.Betamap = None
        self.Ncmap = None
        self.Etamap = None
        self.Wcmapdes = None
        self.Wcmap = None
        self.PRmap = None
        self.ShaftString = ShaftString

        # Map scaling
        self.SFmap_Nc  = 1
        self.SFmap_Wc  = 1
        self.SFmap_PR  = 1
        self.SFmap_Eta = 1

        # v1.3 deterioration effects
        self.SF_wc_deter = 1
        self.SF_eta_deter = 1
        self.SF_pr_deter = 1

        # Dual plot axis
        self.secondary_plot_axis = None
        # The map figure object
        self.dual_map_figure = None

        # Map paramter naming
        # 1.1 WV bug fix
        # self.Nc_comp_param = f"Nc{self.ShaftString}"
        self.Nc_comp_param = f"Nc{self.host_component.stationin}"
        if self.OL_xcol != '':
            self.Wc_in_param = self.OL_xcol
        else:
            self.Wc_in_param = 'Wc' + str(self.host_component.stationin)
        if self.OL_ycol != '':
            self.PR_comp_param = self.OL_ycol
        else:
            self.PR_comp_param = 'PR_' + str(self.host_component.name)

    def ReadMap(self, filename):              # Abstract method, defined by convention only
        amaptype, amaptitle, amapfile = super().ReadMap(filename)
        # with self.file:
        if self.mapfile is not None:
            line = self.mapfile.readline()
            while 'REYNOLDS' not in line.upper():
                line = self.mapfile.readline()
            RNI = np.empty(2, dtype=float)
            f_RNI = np.empty(2, dtype=float)
            items = line.split()
            RNI[0] = float(items[1].split("=", 1)[1])
            f_RNI[0] = float(items[2].split("=", 1)[1])
            RNI[1] = float(items[3].split("=", 1)[1])
            f_RNI[1] = float(items[4].split("=", 1)[1])
        return amaptype, amaptitle, amapfile

    def ReadNcBetaCrossTable(self, file, keyword):
        line = file.readline()
        while keyword not in line.upper():
            line = file.readline()
        line = file.readline()
        items = line.split()
        nccount1, betacount1  = divmod(float(items[0]),1)
        nccount = round(nccount1)-1
        betacount = round(betacount1*1000)-1

        beta_values = np.array(list(map(float, line.split()[1:])))
        # read any beta values from subsequent lines until all added
        while len(beta_values) < betacount:
            line = file.readline()
            beta_values = np.append(beta_values, np.array(list(map(float, line.split()[0:]))))

        nc_values = np.empty(nccount, dtype=float)
        fval_array = np.zeros((nccount, betacount), dtype=float)
        line = file.readline()
        inc = 0
        while line.strip():
            items = line.split()
            nc_values[inc] = float(items[0])
            # get a list of items from 1 or multiple lines
            line_value_items = items[1:]
            # read any items from subsequent lines for the same Nc until values for all Beta values added
            while len(line_value_items) < betacount:
                line = file.readline()
                line_value_items = line_value_items + line.split()
            # now assign all betacount items to the fval_array
            fval_array[inc] = list(map(float, line_value_items))

            line = file.readline()
            inc +=1
        return nc_values, beta_values, fval_array

    def ReadMapAndSetScaling(self, Ncdes, Wcdes, PRdes, Etades):
        self.ReadMap(self.MapFileName)
        if self.mapfile is not None:
            # get map scaling parameters
            # for Nc
            self.SFmap_Nc = Ncdes / self.Ncmapdes
            # for Wc
            self.Wcmapdes = self.get_map_wc((self.Ncmapdes, self.Betamapdes))
            self.SFmap_Wc = Wcdes / self.Wcmapdes
            # for PR
            self.PRmap = self.get_map_pr((self.Ncmapdes, self.Betamapdes))
            self.SFmap_PR = (PRdes - 1) / (self.PRmap - 1)
            # for Eta
            self.Etamap = self.get_map_eta((self.Ncmapdes, self.Betamapdes))
            self.SFmap_Eta = Etades / self.Etamap

    def DefineInterpolationFunctions(self):
        self.get_map_wc = RegularGridInterpolator((self.nc_values, self.beta_values), self.wc_array, bounds_error=False, fill_value=None, method = 'cubic')
        self.get_map_eta = RegularGridInterpolator((self.nc_values, self.beta_values), self.eta_array, bounds_error=False, fill_value=None, method = 'cubic')
        self.get_map_pr = RegularGridInterpolator((self.nc_values, self.beta_values), self.pr_array, bounds_error=False, fill_value=None, method = 'cubic')

    def GetScaledMapPerformance(self, Nc, Beta_state):
        self.Ncmap = Nc / self.SFmap_Nc
        self.Betamap = Beta_state * self.Betamapdes
        wcmap = self.get_map_wc((self.Ncmap, self.Betamap))
        etamap = self.get_map_eta((self.Ncmap, self.Betamap))
        prmap = self.get_map_pr((self.Ncmap, self.Betamap))
        # v1.3 add % deltas for deterioration
        Wc = self.SFmap_Wc * wcmap          * self.SF_wc_deter
        Eta = self.SFmap_Eta * etamap       * self.SF_eta_deter
        PR = self.SFmap_PR * (prmap - 1)    * self.SF_pr_deter + 1
        return Wc, PR, Eta

    # Determine plot arrays, scaled or not
    def set_scaled_arrays(self, do_use_scaled_map = False):
        if do_use_scaled_map:
            self.NcArrayValues = self.nc_values * self.SFmap_Nc
            self.WcArrayValues = self.wc_array * self.SFmap_Wc
            # must scale around PR = 1
            self.PRArrayValues = (self.pr_array - 1) * self.SFmap_PR + 1
            self.EtaArrayValues = self.eta_array * self.SFmap_Eta
        else:
            self.NcArrayValues = self.nc_values
            self.WcArrayValues = self.wc_array
            self.PRArrayValues = self.pr_array
            self.EtaArrayValues = self.eta_array

    # Map plotting routine
    def PlotMap(self, use_scaled_map = True, do_plot_design_point = True, do_plot_series = True):
        super().PlotMap()
        # Set map title
        map_title = self.MapFileName

        if do_plot_series or do_plot_design_point:
            use_scaled_map = True

        if use_scaled_map:
            map_title = map_title + ' (scaled to DP)'

        self.map_figure.suptitle(map_title)

        self.set_scaled_arrays(use_scaled_map)

    # This plot consists of two subplots
    def PlotDualMap(self, use_scaled_map = True, do_plot_design_point = True, do_plot_series = True):
        # Store plot under a different name, override map file name
        # reuse the map_figure_pathname and map size class parameters
        self.map_figure_pathname = './output/' + self.name + '_dual' + '.jpg'

        # Create the subplot graph for a split turbomachinary plot
        self.dual_map_figure, (self.main_plot_axis, self.secondary_plot_axis) = plt.subplots(
            2, 1,                # two rows, one column
            sharex=True,         # both panels share the same x-ticks
            figsize = self.map_size
        )

        # Set map title
        map_title = self.MapFileName

        if do_plot_series or do_plot_design_point:
            use_scaled_map = True

        if use_scaled_map:
            map_title = map_title + ' (scaled to DP)'

        self.dual_map_figure.suptitle(map_title)

        self.set_scaled_arrays(use_scaled_map)


