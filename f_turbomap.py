import numpy as np
from f_map import TMap
from scipy.interpolate import RegularGridInterpolator

class TTurboMap(TMap):
    def __init__(self, host_component, name, MapFileName, Ncmapdes, Betamapdes):    # Constructor of the class
        super().__init__(host_component, name, MapFileName)
        self.Ncmapdes = Ncmapdes
        self.Betamapdes = Betamapdes
        self.Betamap = None
        self.Ncmap = None
        self.Etamap = None
        self.Wcmapdes = None
        self.Wcmap = None
        self.PRmap = None

        # Oscar
        self.SFmap_Nc  = 1
        self.SFmap_Wc  = 1
        self.SFmap_PR  = 1
        self.SFmap_Eta = 1

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
        Wc = self.SFmap_Wc * wcmap
        PR = self.SFmap_PR * (prmap - 1) + 1
        Eta = self.SFmap_Eta * etamap
        return Wc, PR, Eta

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
        self.map_figure_pathname = './output/' + self.host_component.name + '_map.jpg'

        # Map paramter naming
        self.Wc_in_param = 'Wc' + str(self.host_component.stationin)
        self.PR_comp_param = 'PR_' + str(self.host_component.name)

        if use_scaled_map:
            self.NcArrayValues = self.nc_values * self.SFmap_Nc
            self.WcArrayValues = self.wc_array * self.SFmap_Wc
            self.PRArrayValues = self.pr_array * self.SFmap_PR
            self.EtaArrayValues = self.eta_array * self.SFmap_Eta
        else:
            self.NcArrayValues = self.nc_values
            self.WcArrayValues = self.wc_array
            self.PRArrayValues = self.pr_array
            self.EtaArrayValues = self.eta_array