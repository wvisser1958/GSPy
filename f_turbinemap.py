import numpy as np
from f_turbomap import TTurboMap
import f_system as fsys

class TTurbineMap(TTurboMap):
    def __init__(self, host_component, name, MapFileName, Ncmapdes, Betamapdes):
        super().__init__(host_component, name, MapFileName, Ncmapdes, Betamapdes)
    
    def ReadMap(self, filename):              # Abstract method, defined by convention only
        amaptype, amaptitle, amapfile = super().ReadMap(filename)  
        # tbd : read stall line
        return amaptype, amaptitle, amapfile
    
    def ReadPRlimits(self, mapfile, keyword):
        line = mapfile.readline()  
        while keyword not in line.upper():
            line = mapfile.readline()  
        line = mapfile.readline()  
        items = line.split()
        nccount1= float(items[0])%1
        nccount = round(nccount1*1000)-1
        nc_values = np.empty(nccount, dtype=float)
        line = mapfile.readline()  
        # items = line.split()
        prlimits_array = np.array(list(map(float, line.split()[1:])))
        return nc_values, prlimits_array      

    def ReadMap(self, filename):              # Abstract method, defined by convention only
        super().ReadMap(filename)

        # read PR min values
        self.nc_values, self.prmin_array = self.ReadPRlimits(self.mapfile, 'MIN PRESSURE RATIO')  
        self.nc_values, self.prmax_array = self.ReadPRlimits(self.mapfile, 'MAX PRESSURE RATIO')  

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
    
    def PlotMap(self, use_scaled_map = False, do_plot_series = False):
        super().PlotMap(use_scaled_map, do_plot_series)

        # Plot Wc-PR top subplot
        for index, NcValue in enumerate(self.NcArrayValues): 
            self.main_plot_axis.plot(self.PRArrayValues[index], self.WcArrayValues[index], linewidth=0.25, linestyle='dashed', color='black', label=str(NcValue))
        self.main_plot_axis.set_ylabel('Corected massflow')
        self.main_plot_axis.set_xlabel('Pressure Ratio')
        
        # Contours
        PR_grid, Wc_grid, Eta_grid = self.CalcMapEtaTopology(self.WcArrayValues,self.PRArrayValues,self.EtaArrayValues,False)
        CS = self.main_plot_axis.contour(Wc_grid,PR_grid,np.transpose(Eta_grid),10,colors='slategrey',alpha=0.3,levels = np.linspace(0.64, 0.84, 11)) 
        self.main_plot_axis.clabel(CS, fontsize=7, inline=True)
        self.main_plot_axis.contourf(Wc_grid,PR_grid,np.transpose(Eta_grid), 14 ,cmap='RdYlGn',alpha=0.3)

        if do_plot_series:
            # Plot the operating line
            # -----------------------
            # Plotting Wc - PR
            self.main_plot_axis.plot(fsys.OutputTable[(fsys.OutputTable['Mode'] == 'OD')][self.PR_comp_param].to_numpy(), fsys.OutputTable[(fsys.OutputTable['Mode'] == 'OD')][self.Wc_in_param].to_numpy(),  linewidth=1.5, linestyle='solid', color='navy')

        self.map_figure.savefig(self.map_figure_pathname)