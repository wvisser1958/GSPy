import matplotlib.pyplot as plt
from f_compressor import TCompressor
from f_turbine import TTurbine
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
    
    def GetMapData(self):
        pass
    
    def PlotOperatingCurve(self):
        pass
    
    def PlotDesignPoint(self):
        pass
    
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

    
class TurbineMapPlot(MapPlot):
    # constructor
    def __init__(self, mapname, turbineObject):
        super().__init__(mapname)
        # Turbine object containing map data
        self.turbineObject = turbineObject
        self.figTurbSplit = None
        self.figTurbContour = None
        self.turbNcArrayValues    = None
        self.turbBetaArrayValues  = None
        self.turbWcArrayValues    = None
        self.turbPRArrayValues    = None
        self.turbEtaArrayValues   = None
        
    # Methods
    # -------
    # Get map data arrays
    def GetMapData(self):
        super().GetMapData()
        (self.turbineObject).ReadMap((self.turbineObject).MapFileName)
        self.turbNcArrayValues   = (self.turbineObject).GetNcArray()     * (self.turbineObject).SFmap_Nc
        self.turbBetaArrayValues  = (self.turbineObject).GetBetaArray()
        self.turbWcArrayValues    = (self.turbineObject).GetWcValues()   * (self.turbineObject).SFmap_Wc
        self.turbPRArrayValues    = (self.turbineObject).GetPrValues()   * (self.turbineObject).SFmap_PR
        self.turbEtaArrayValues   = (self.turbineObject).GetEtaValues()  * (self.turbineObject).SFmap_Eta

    def ContourPlotMap(self):
        figTurbContour = plt.figure(num='Turbine map plot', figsize=(10,8))
        ax = figTurbContour.gca()
        self.figTurbContour = figTurbContour
        self.tAx = ax
        # Get the data arrays for plotting the map
        self.GetMapData()
        
        self.figTurbContour.suptitle((self.turbineObject).MapFileName)

        # Plot Wc-PR top subplot
        for index, NcValue in enumerate(self.turbNcArrayValues): 
            self.tAx.plot(self.turbPRArrayValues[index], self.turbWcArrayValues[index], linewidth=0.25, linestyle='dashed', color='black', label=str(NcValue))
        self.tAx.set_xlabel('Corected massflow')
        self.tAx.set_ylabel('Pressure Ratio')
        
        # Plot surge line
        # self.tAx.plot(self.turbSlWcArrayValues, self.turbSlPRArrayValues[0], linewidth=1.0, linestyle='solid', color='red', label='Surge Line')
        # self.ax.legend()
        
        # Contours
        PR_grid, Wc_grid, Eta_grid = self.CreateEtaTopology(self.turbWcArrayValues,self.turbPRArrayValues,self.turbEtaArrayValues,False)
        CS = self.tAx.contour(Wc_grid,PR_grid,np.transpose(Eta_grid),10,colors='slategrey',alpha=0.3,levels = np.linspace(0.64, 0.84, 11)) 
        self.tAx.clabel(CS, fontsize=7, inline=True)
        self.tAx.contourf(Wc_grid,PR_grid,np.transpose(Eta_grid), 14 ,cmap='RdYlGn',alpha=0.3)

    
class CompressorMapPlot(MapPlot):
    # constructor
    def __init__(self, mapname, compressorObject):
        super().__init__(mapname)
        # Compressor object containing map data
        self.compressorObject = compressorObject
        self.figCompSplit = None
        self.figCompContour = None
        self.compNcArrayValues    = None
        self.compBetaArrayValues  = None
        self.compWcArrayValues    = None
        self.compPRArrayValues    = None
        self.compEtaArrayValues   = None
        self.compSlWcArrayValues  = None
        self.compSlPRArrayValues  = None

    # Methods
    # -------
    # Get map data arrays
    def GetMapData(self):
        super().GetMapData()
        (self.compressorObject).ReadMap((self.compressorObject).MapFileName)
        self.compNcArrayValues   = (self.compressorObject).GetNcArray()     * (self.compressorObject).SFmap_Nc
        self.compBetaArrayValues  = (self.compressorObject).GetBetaArray()
        self.compWcArrayValues    = (self.compressorObject).GetWcValues()   * (self.compressorObject).SFmap_Wc
        self.compPRArrayValues    = (self.compressorObject).GetPrValues()   * (self.compressorObject).SFmap_PR
        self.compEtaArrayValues   = (self.compressorObject).GetEtaValues()  * (self.compressorObject).SFmap_Eta
        self.compSlWcArrayValues  = (self.compressorObject).GetSlWcValues() * (self.compressorObject).SFmap_Wc
        self.compSlPRArrayValues  = (self.compressorObject).GetSlPrValues() * (self.compressorObject).SFmap_PR
    
    def ContourPlotMap(self):
        figCompContour = plt.figure(num='Compressor map plot', figsize=(10,8))
        ax = figCompContour.gca()
        self.figCompContour = figCompContour
        self.ax = ax
        # Get the data arrays for plotting the map
        self.GetMapData()
        
        self.figCompContour.suptitle((self.compressorObject).MapFileName)

        # Plot Wc-PR top subplot
        for index, NcValue in enumerate(self.compNcArrayValues): 
            self.ax.plot(self.compWcArrayValues[index], self.compPRArrayValues[index], linewidth=0.25, linestyle='dashed', color='black', label=str(NcValue))
        self.ax.set_xlabel('Corected massflow')
        self.ax.set_ylabel('Pressure Ratio')
        
        # Plot surge line
        self.ax.plot(self.compSlWcArrayValues, self.compSlPRArrayValues[0], linewidth=1.0, linestyle='solid', color='red', label='Surge Line')
        # self.ax.legend()
        
        # Contours
        Wc_grid, PR_grid, Eta_grid = self.CreateEtaTopology(self.compWcArrayValues,self.compPRArrayValues,self.compEtaArrayValues,False)
        CS = self.ax.contour(Wc_grid,PR_grid,Eta_grid,10,colors='slategrey',alpha=0.3,levels = np.linspace(0.64, 0.84, 11)) 
        self.ax.clabel(CS, fontsize=7, inline=True)
        self.ax.contourf(Wc_grid,PR_grid,Eta_grid, 14 ,cmap='RdYlGn',alpha=0.3)
        
    def PlotMap(self):
        super().PlotMap()
        # Create a figure with the name "testplot"
        figCompContour = plt.figure(num="Split compressor map plot", figsize=(10,8))
        # Add two subplots to the figure
        ax1 = figCompContour.add_subplot(2, 1, 1)  # First subplot (2 rows, 1 column, position 1)
        ax2 = figCompContour.add_subplot(2, 1, 2)  # Second subplot (2 rows, 1 column, position 2)
        self.figCompSplit = figCompContour
        self.cAxSplitTop = ax1
        self.cAxSplitBottom = ax2
                
        # Get the data arrays for plotting the map
        self.GetMapData()
       
        self.figCompSplit.suptitle((self.compressorObject).MapFileName)
        
        # Plot Wc-Eta top subplot
        for index, NcValue in enumerate(self.compNcArrayValues): 
            self.cAxSplitTop.plot(self.compWcArrayValues[index], self.compEtaArrayValues[index], linewidth=0.5, linestyle='dashed', color='black', label=str(NcValue))
        self.cAxSplitTop.set_ylabel('Efficiency')
        # self.ax1.legend()
                
        # Plot Wc-PR top subplot
        for index, NcValue in enumerate(self.compNcArrayValues): 
            self.cAxSplitBottom.plot(self.compWcArrayValues[index], self.compPRArrayValues[index], linewidth=0.25, linestyle='dashed', color='black', label=str(NcValue))
        self.cAxSplitBottom.set_xlabel('Corected massflow')
        self.cAxSplitBottom.set_ylabel('Pressure Ratio')
        
        # Contours
        Wc_grid, PR_grid, Eta_grid = self.CreateEtaTopology(self.compWcArrayValues,self.compPRArrayValues,self.compEtaArrayValues,False)
        CS = self.cAxSplitBottom.contour(Wc_grid,PR_grid,Eta_grid,10,colors='slategrey',alpha=0.3,levels = np.linspace(0.64, 0.84, 11)) 
        self.cAxSplitBottom.clabel(CS, fontsize=7, inline=True)
        self.cAxSplitBottom.contourf(Wc_grid,PR_grid,Eta_grid, 14 ,cmap='RdYlGn',alpha=0.3)

        # Plot surge line
        self.cAxSplitBottom.plot(self.compSlWcArrayValues, self.compSlPRArrayValues[0], linewidth=1.0, linestyle='solid', color='red', label='Surge Line')
        # self.ax2.legend()

    def ShowPlot(self):
        plt.show()
    
    def PlotOperatingCurve(self,wc_values, pr_values, eta_values):
        # Pass operating data to plot in the map
        if self.figCompSplit is not None:
            plt.figure('Split compressor map plot')
            self.cAxSplitTop.plot(wc_values, eta_values, linewidth=1.5, linestyle='solid', color='navy')
            self.cAxSplitBottom.plot(wc_values, pr_values, linewidth=1.5, linestyle='solid', color='navy')
        if self.figCompContour is not None:
            plt.figure('Compressor map plot')
            self.ax.plot(wc_values, pr_values,  linewidth=1.5, linestyle='solid', color='navy')
        
        
    def PlotDesignPoint(self,wc_value, pr_value, eta_value):
        if self.figCompSplit is not None:
            plt.figure('Split compressor map plot')
            self.cAxSplitTop.plot(wc_value, eta_value, markersize=6.0, linestyle='none', marker='s', markeredgewidth=0.75, markerfacecolor='yellow', markeredgecolor='black')
            self.cAxSplitBottom.plot(wc_value, pr_value, markersize=6.0, linestyle='none', marker='s', markeredgewidth=0.75, markerfacecolor='yellow', markeredgecolor='black')
        if self.figCompContour is not None:
            plt.figure('Compressor map plot')
            self.ax.plot(wc_value, pr_value,  markersize=6.0, linestyle='none', marker='s', markeredgewidth=0.75, markerfacecolor='yellow', markeredgecolor='black')
        
        
# test program start
if __name__ == "__main__":
    # Create turbo component objects
    aCompressor = TCompressor('compressor1', 'compmap.map',  2, 3, 1, 0.8, 1, 16540, 0.825, 6.92)
    aTurbine    = TTurbine('turbine1'      , 'turbimap.map', 4, 5, 1, 0.8, 1, 16540, 0.88)
    
    # Now set manually, but should be set in compressor class on run DP
    aCompressor.SFmap_Wc = 1.00151
    aCompressor.SFmap_Eta = 0.948276
    aCompressor.SFmap_PR = 1.051659
    aCompressor.SFmap_Nc = 16539.99909
    aTurbine.SFmap_Wc = 0.30258720860030913
    aTurbine.SFmap_Eta = 0.9658696778385591
    aTurbine.SFmap_PR = 0.6465586472480385
    aTurbine.SFmap_Nc = 7986.39865810925
    
    # Create turbo map objects
    compMap = CompressorMapPlot("compmap.map", aCompressor)
    turbMap = TurbineMapPlot("turbimap.map", aTurbine)

    # Plot the basic map curves
    compMap.PlotMap()
    
    # Plot contours
    compMap.ContourPlotMap()
    turbMap.ContourPlotMap()
    
    # Read performnace data of TJET to plot operating performance data
    import pandas as pd
    df = pd.read_csv('./data/TJET.csv')
    
    # Plot design point
    compMap.PlotDesignPoint(df['Wc'][0],df['PR'][0],df['Eta'][0])
    
    # Plot steady state series
    compMap.PlotOperatingCurve(df['Wc'],df['PR'],df['Eta'])
    
    # Finally, show created plot
    compMap.ShowPlot()
    turbMap.ShowPlot()