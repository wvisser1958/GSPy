import numpy as np
from f_turbomap import TTurboMap

class TCompressorMap(TTurboMap):
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


