import matplotlib.pyplot as plt
from f_compressor import TCompressor
import numpy as np
from scipy.interpolate import griddata
from scipy.ndimage import gaussian_filter


class MapPlot:
    # properties
    
    # constructor
    def __init__(self, mapname):
        self.name = mapname
    
    # methods
    def PlotMap(self):
        pass
    
    def ContourPlotMap(self):
        pass
    
    def ShowPlot(self):
        pass
    
class CompressorMapPlot(MapPlot):
    # properties
    # NcArrayValues   = None
    # WcArrayValues   = None
    # PRArrayValues   = None
    # EtaArrayValues  = None
    # slWcArrayValues = None
    # slPRArrayValues = None
    
    # constructor
    def __init__(self, mapname, compressorObject):
        super().__init__(mapname)
        # Compressor object containing map data
        self.compressorObject = compressorObject
        self.fig0 = None
        self.fig1 = None
        self.NcArrayValues    = None
        self.BetaArrayValues  = None
        self.WcArrayValues    = None
        self.PRArrayValues    = None
        self.EtaArrayValues   = None
        self.slWcArrayValues  = None
        self.slPRArrayValues  = None

        
    # methods
    # -------
    # Get map data arrays
    def GetMapData(self):
        # TODO, maybe better to load data in separate method
        (self.compressorObject).ReadMap((self.compressorObject).MapFileName)
        self.NcArrayValues   = (self.compressorObject).GetNcArray()     * (self.compressorObject).SFmap_Nc
        self.BetaArrayValues  = (self.compressorObject).GetBetaArray()
        self.WcArrayValues    = (self.compressorObject).GetWcValues()   * (self.compressorObject).SFmap_Wc
        self.PRArrayValues    = (self.compressorObject).GetPrValues()   * (self.compressorObject).SFmap_PR
        self.EtaArrayValues   = (self.compressorObject).GetEtaValues()  * (self.compressorObject).SFmap_Eta
        self.slWcArrayValues  = (self.compressorObject).GetSlWcValues() * (self.compressorObject).SFmap_Wc
        self.slPRArrayValues  = (self.compressorObject).GetSlPrValues() * (self.compressorObject).SFmap_PR
    
    def ContourPlotMap(self):
        plt.figure('Compressor map plot', figsize=(10,8))
        ax = plt.gca()
        self.ax = ax
        # Get the data arrays for plotting the map
        self.GetMapData()

        # Plot Wc-PR top subplot
        for index, NcValue in enumerate(self.NcArrayValues): 
            self.ax.plot(self.WcArrayValues[index], self.PRArrayValues[index], linewidth=0.25, linestyle='dashed', color='black', label=str(NcValue))
        self.ax.set_xlabel('Corected massflow')
        self.ax.set_ylabel('Pressure Ratio')
        
        # Plot surge line
        self.ax.plot(self.slWcArrayValues, self.slPRArrayValues[0], linewidth=1.0, linestyle='solid', color='red', label='Surge Line')
        # self.ax.legend()
        
        # Contours
        Wc_grid, PR_grid, Eta_grid = self.CreateEtaTopology(self.WcArrayValues,self.PRArrayValues,self.EtaArrayValues,False)
        CS = self.ax.contour(Wc_grid,PR_grid,Eta_grid,10,colors='slategrey',alpha=0.3,levels = np.linspace(0.64, 0.84, 11),linewidth=2.5, linestyle='dashed') 
        self.ax.clabel(CS, fontsize=7, inline=True)
        self.ax.contourf(Wc_grid,PR_grid,Eta_grid, 14 ,cmap='RdYlGn',alpha=0.3)
        
    def CreateEtaTopology(self,WcArrayValues,PRArrayValues,EtaArrayValues,doSmooth=True):
        # Flatten the data for interpolation
        Wc_flat = WcArrayValues.flatten()
        PR_flat = PRArrayValues.flatten()
        Eta_flat = EtaArrayValues.flatten()

        # Create a grid for corrected mass flow (Wc) and pressure ratio (PR)
        Wc_grid = np.linspace(WcArrayValues.min(), WcArrayValues.max(), 100)
        PR_grid = np.linspace(PRArrayValues.min(), PRArrayValues.max(), 100)
        Wc_mesh, PR_mesh = np.meshgrid(Wc_grid, PR_grid)

        # Interpolate efficiency data onto the grid
        Eta_grid = griddata(
            (Wc_flat, PR_flat),  # Original data points
            Eta_flat,            # Efficiency values
            (Wc_mesh, PR_mesh),  # Target grid
            method='linear'      # Interpolation method
        )
        # Apply Gaussian smoothing
        if doSmooth:
            Eta_grid = gaussian_filter(Eta_grid, sigma=0.8)  # Adjust sigma for more or less smoothing

        return Wc_grid, PR_grid, Eta_grid

    def PlotMap(self):
        super().PlotMap()
        plt.figure('Split compressor map plot')
        fig0, (ax1, ax2) = plt.subplots( 2, 1, figsize=(10,8))
        self.fig0 = fig0
        self.ax1 = ax1
        self.ax2 = ax2
                
        # Get the data arrays for plotting the map
        self.GetMapData()
       
        self.fig0.suptitle('Compressor map')
        
        # Plot Wc-Eta top subplot
        for index, NcValue in enumerate(self.NcArrayValues): 
            self.ax1.plot(self.WcArrayValues[index], self.EtaArrayValues[index], linewidth=0.5, linestyle='dashed', color='black', label=str(NcValue))
        self.ax1.set_ylabel('Efficiency')
        # self.ax1.legend()
                
        # Plot Wc-PR top subplot
        for index, NcValue in enumerate(self.NcArrayValues): 
            self.ax2.plot(self.WcArrayValues[index], self.PRArrayValues[index], linewidth=0.25, linestyle='dashed', color='black', label=str(NcValue))
        self.ax2.set_xlabel('Corected massflow')
        self.ax2.set_ylabel('Pressure Ratio')
        
        # Contours
        Wc_grid, PR_grid, Eta_grid = self.CreateEtaTopology(self.WcArrayValues,self.PRArrayValues,self.EtaArrayValues,False)
        CS = self.ax2.contour(Wc_grid,PR_grid,Eta_grid,10,colors='slategrey',alpha=0.3,levels = np.linspace(0.64, 0.84, 11),linewidth=2.5, linestyle='dashed') 
        self.ax2.clabel(CS, fontsize=7, inline=True)
        self.ax2.contourf(Wc_grid,PR_grid,Eta_grid, 14 ,cmap='RdYlGn',alpha=0.3)

        # Plot surge line
        self.ax2.plot(self.slWcArrayValues, self.slPRArrayValues[0], linewidth=1.0, linestyle='solid', color='red', label='Surge Line')
        # self.ax2.legend()

    def ShowPlot(self):
        plt.show()
    
    def PlotOperatingCurve(self,wc_values, pr_values, eta_values):
        # Pass operating data to plot in the map
        plt.figure('Compressor map plot')
        # self.ax1.plot(wc_values, eta_values, linewidth=1.5, linestyle='solid', color='navy')
        self.ax.plot(wc_values, pr_values,  linewidth=1.5, linestyle='solid', color='navy')
        
    def PlotDesignPoint(self,wc_value, pr_value, eta_value):
        plt.figure('Compressor map plot')
        # self.ax1.plot(wc_value, eta_value, markersize=6.0, linestyle='none', marker='s', markeredgewidth=0.75, markerfacecolor='yellow', markeredgecolor='black')
        self.ax.plot(wc_value, pr_value,  markersize=6.0, linestyle='none', marker='s', markeredgewidth=0.75, markerfacecolor='yellow', markeredgecolor='black')
        
        
# test program start
if __name__ == "__main__":
    # Create compressor object
    aCompressor = TCompressor('compressor1', 'compmap.map', 2, 3, 1, 0.8, 1, 16540, 0.825, 6.92)
    
    # Now set manually, but should be set in compressor class on run DP
    aCompressor.SFmap_Wc = 1.00151
    aCompressor.SFmap_Eta = 0.948276
    aCompressor.SFmap_PR = 1.051659
    aCompressor.SFmap_Nc = 16539.99909
    
    # Create a compressor map object
    compMap = CompressorMapPlot("compmap.map", aCompressor)

    # Plot the basic map curves
    compMap.PlotMap()
    
    # Plot contours
    compMap.ContourPlotMap()
    
    # Read performnace data of TJET to plot operating performance data
    import pandas as pd
    df = pd.read_csv('./data/TJET.csv')
    
    # Plot design point
    compMap.PlotDesignPoint(df['Wc'][0],df['PR'][0],df['Eta'][0])
    
    # Plot steady state series
    compMap.PlotOperatingCurve(df['Wc'],df['PR'],df['Eta'])
    
    # Finally, show created plot
    compMap.ShowPlot()