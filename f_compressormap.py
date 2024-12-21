import numpy as np
from f_turbomap import TTurboMap

class TCompressorMap(TTurboMap):
    def __init__(self, host_component, name, MapFileName, Ncmapdes, Betamapdes):
        super().__init__(host_component, name, MapFileName, Ncmapdes, Betamapdes)
    
    def ReadMap(self, filename):              # Abstract method, defined by convention only
        amaptype, amaptitle, amapfile = super().ReadMap(filename)  
        # tbd : read stall line
        return amaptype, amaptitle, amapfile
    
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
        # define the interpolation functions allow extrapolation (i.e. fill value = None)
        # self.get_map_wc = RegularGridInterpolator((self.nc_values, self.beta_values), self.wc_array, bounds_error=False, fill_value=None, method = 'cubic')
        # self.get_map_eta = RegularGridInterpolator((self.nc_values, self.beta_values), self.eta_array, bounds_error=False, fill_value=None, method = 'cubic')
        # self.get_map_pr = RegularGridInterpolator((self.nc_values, self.beta_values), self.pr_array, bounds_error=False, fill_value=None, method = 'cubic')
        self.DefineInterpolationFunctions()
        
    def PlotMap(self, use_scaled_map = False, do_plot_series = False):
        super().PlotMap(use_scaled_map, do_plot_series)
        
        if use_scaled_map:
            self.compSlWcArrayValues = self.sl_wc_array * self.SFmap_Wc
            self.compSlPRArrayValues = self.sl_pr_array * self.SFmap_PR
        else:
            self.compSlWcArrayValues = self.sl_wc_array
            self.compSlPRArrayValues = self.sl_pr_array

        # Plot Wc-PR top subplot
        for index, NcValue in enumerate(self.NcArrayValues): 
            self.main_plot_axis.plot(self.WcArrayValues[index], self.PRArrayValues[index], linewidth=0.25, linestyle='dashed', color='black', label=str(NcValue))
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
        
        self.map_figure.savefig('./output/comp_map.jpg')


