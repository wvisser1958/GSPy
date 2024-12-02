import matplotlib.pyplot as plt
from f_compressor import TCompressor
from f_turbine import TTurbine
import numpy as np
from scipy.interpolate import griddata
from scipy.ndimage import gaussian_filter
# from PIL import Image

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
        self.tAx.set_ylabel('Corected massflow')
        self.tAx.set_xlabel('Pressure Ratio')
        
        # Contours
        PR_grid, Wc_grid, Eta_grid = self.CreateEtaTopology(self.turbWcArrayValues,self.turbPRArrayValues,self.turbEtaArrayValues,False)
        CS = self.tAx.contour(Wc_grid,PR_grid,np.transpose(Eta_grid),10,colors='slategrey',alpha=0.3,levels = np.linspace(0.64, 0.84, 11)) 
        self.tAx.clabel(CS, fontsize=7, inline=True)
        self.tAx.contourf(Wc_grid,PR_grid,np.transpose(Eta_grid), 14 ,cmap='RdYlGn',alpha=0.3)
        
    def PlotOperatingCurve(self,wc_values, pr_values, eta_values):
        # Pass operating data to plot in the map
        if self.figTurbSplit is not None:
            plt.figure('Split turbine map plot')
            self.tAxSplitTop.plot(pr_values, eta_values, linewidth=1.5, linestyle='solid', color='navy')
            self.tAxSplitBottom.plot(pr_values, wc_values, linewidth=1.5, linestyle='solid', color='navy')
        if self.figTurbContour is not None:
            plt.figure('Turbine map plot')
            self.tAx.plot(pr_values, wc_values,  linewidth=1.5, linestyle='solid', color='navy')
        
    def PlotDesignPoint(self,wc_value, pr_value, eta_value):
        if self.figTurbContour is not None:
            plt.figure('Turbine map plot')
            self.tAx.plot(pr_value, wc_value,  markersize=6.0, linestyle='none', marker='s', markeredgewidth=0.75, markerfacecolor='yellow', markeredgecolor='black')
            
    def PlotMap(self):
        super().PlotMap()
        # Create a figure with the name "testplot"
        figTurbSplit = plt.figure(num="Split turbine map plot", figsize=(10,8))
        # Add two subplots to the figure
        ax1 = figTurbSplit.add_subplot(2, 1, 1)  # First subplot (2 rows, 1 column, position 1)
        ax2 = figTurbSplit.add_subplot(2, 1, 2)  # Second subplot (2 rows, 1 column, position 2)
        self.figTurbSplit = figTurbSplit
        self.tAxSplitTop = ax1
        self.tAxSplitBottom = ax2
                
        # Get the data arrays for plotting the map
        self.GetMapData()
       
        self.figTurbSplit.suptitle((self.turbineObject).MapFileName)
        
        # Plot PR-Eta top subplot
        for index, NcValue in enumerate(self.turbNcArrayValues): 
            # self.tAxSplitTop.plot(self.turbWcArrayValues[index], self.turbEtaArrayValues[index], linewidth=0.5, linestyle='dashed', color='black', label=str(NcValue))
            self.tAxSplitTop.plot(self.turbPRArrayValues[index], self.turbEtaArrayValues[index], linewidth=0.5, linestyle='dashed', color='black', label=str(NcValue))
        self.tAxSplitTop.set_ylabel('Efficiency')
                
        # Plot Wc-PR top subplot
        # for index, NcValue in enumerate(self.turbNcArrayValues): 
        #     # self.cAxSplitBottom.plot(self.compWcArrayValues[index], self.compPRArrayValues[index], linewidth=0.25, linestyle='dashed', color='black', label=str(NcValue))
        #     self.tAxSplitBottom.plot(self.turbPRArrayValues[index], self.turbWcArrayValues[index], linewidth=0.25, linestyle='dashed', color='black', label=str(NcValue))
        self.tAxSplitBottom.set_ylabel('Corected massflow')
        self.tAxSplitBottom.set_xlabel('Pressure Ratio')
        
        # Contours
        PR_grid, Wc_grid, Eta_grid = self.CreateEtaTopology(self.turbWcArrayValues,self.turbPRArrayValues,self.turbEtaArrayValues,False)
        CS = self.tAxSplitBottom.contour(Wc_grid,PR_grid,np.transpose(Eta_grid),10,colors='slategrey',alpha=0.3,levels = np.linspace(0.64, 0.84, 11)) 
        self.tAxSplitBottom.clabel(CS, fontsize=7, inline=True)
        self.tAxSplitBottom.contourf(Wc_grid,PR_grid,np.transpose(Eta_grid), 14 ,cmap='RdYlGn',alpha=0.3)

    def ShowPlot(self):
        if self.figTurbSplit is not None:
            # self.figTurbSplit.show
            self.figTurbSplit.savefig('./data/turbSplit.jpg')
            # # Load an image
            # imgTurbSplit = Image.open('./data/turbSplit.jpg')
            # # Display the image
            # imgTurbSplit.show()
        if self.figTurbContour is not None:
            # self.figTurbContour.show
            self.figTurbContour.savefig('./data/turbContour.jpg')
            #  # Load an image
            # imgTurbContour = Image.open('./data/turbContour.jpg')
            # # Display the image
            # imgTurbContour.show()
    
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
        self.cAx = ax
        # Get the data arrays for plotting the map
        self.GetMapData()
        
        self.figCompContour.suptitle((self.compressorObject).MapFileName)

        # Plot Wc-PR top subplot
        for index, NcValue in enumerate(self.compNcArrayValues): 
            self.cAx.plot(self.compWcArrayValues[index], self.compPRArrayValues[index], linewidth=0.25, linestyle='dashed', color='black', label=str(NcValue))
        self.cAx.set_xlabel('Corected massflow')
        self.cAx.set_ylabel('Pressure Ratio')
        
        # Plot surge line
        self.cAx.plot(self.compSlWcArrayValues, self.compSlPRArrayValues[0], linewidth=1.0, linestyle='solid', color='red', label='Surge Line')
        # self.ax.legend()
        
        # Contours
        Wc_grid, PR_grid, Eta_grid = self.CreateEtaTopology(self.compWcArrayValues,self.compPRArrayValues,self.compEtaArrayValues,False)
        CS = self.cAx.contour(Wc_grid,PR_grid,Eta_grid,10,colors='slategrey',alpha=0.3,levels = np.linspace(0.64, 0.84, 11)) 
        self.cAx.clabel(CS, fontsize=7, inline=True)
        self.cAx.contourf(Wc_grid,PR_grid,Eta_grid, 14 ,cmap='RdYlGn',alpha=0.3)
        
    def PlotMap(self):
        super().PlotMap()
        # Create a figure with the name "testplot"
        figCompSplit = plt.figure(num="Split compressor map plot", figsize=(10,8))
        # Add two subplots to the figure
        ax1 = figCompSplit.add_subplot(2, 1, 1)  # First subplot (2 rows, 1 column, position 1)
        ax2 = figCompSplit.add_subplot(2, 1, 2)  # Second subplot (2 rows, 1 column, position 2)
        self.figCompSplit = figCompSplit
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
        # plt.show()
        if self.figCompSplit is not None:
            # self.figCompSplit.show()
            self.figCompSplit.savefig('./data/compSplit.jpg')
            # # Load an image
            # imgCompSplit = Image.open('./data/compSplit.jpg')
            # # Display the image
            # imgCompSplit.show()
        if self.figCompContour is not None:
            # self.figCompContour.show() 
            self.figCompContour.savefig('./data/compContour.jpg')
            #  # Load an image
            # imgCompContour = Image.open('./data/compContour.jpg')
            # # Display the image
            # imgCompContour.show()
               
    def PlotOperatingCurve(self,wc_values, pr_values, eta_values):
        # Pass operating data to plot in the map
        if self.figCompSplit is not None:
            plt.figure('Split compressor map plot')
            self.cAxSplitTop.plot(wc_values, eta_values, linewidth=1.5, linestyle='solid', color='navy')
            self.cAxSplitBottom.plot(wc_values, pr_values, linewidth=1.5, linestyle='solid', color='navy')
        if self.figCompContour is not None:
            plt.figure('Compressor map plot')
            self.cAx.plot(wc_values, pr_values,  linewidth=1.5, linestyle='solid', color='navy')
        
    def PlotDesignPoint(self,wc_value, pr_value, eta_value):
        if self.figCompSplit is not None:
            plt.figure('Split compressor map plot')
            self.cAxSplitTop.plot(wc_value, eta_value, markersize=6.0, linestyle='none', marker='s', markeredgewidth=0.75, markerfacecolor='yellow', markeredgecolor='black')
            self.cAxSplitBottom.plot(wc_value, pr_value, markersize=6.0, linestyle='none', marker='s', markeredgewidth=0.75, markerfacecolor='yellow', markeredgecolor='black')
        if self.figCompContour is not None:
            plt.figure('Compressor map plot')
            self.cAx.plot(wc_value, pr_value,  markersize=6.0, linestyle='none', marker='s', markeredgewidth=0.75, markerfacecolor='yellow', markeredgecolor='black')
        
        
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
    
    aTurbine.SFmap_Wc = 0.329704
    aTurbine.SFmap_Eta = 0.944733
    aTurbine.SFmap_PR = 1.000753
    aTurbine.SFmap_Nc = 8276.062745
    
    # Create turbo map objects
    compMap = CompressorMapPlot("compmap.map", aCompressor)
    turbMap = TurbineMapPlot("turbimap.map", aTurbine)

    # Plot the basic map curves
    compMap.PlotMap()
    turbMap.PlotMap()
    
    # Plot contours
    compMap.ContourPlotMap()
    turbMap.ContourPlotMap()
    
    # Read performnace data of TJET to plot operating performance data
    import pandas as pd
    df = pd.read_csv('./data/TJET.csv')
    
    # Plot design point
    # Compressor data: Wc2 [kg/s],PR_c [-],Nc_c [%],Eta_c [-]
    compMap.PlotDesignPoint(df['Wc2 [kg/s]'][0],df['PR_c [-]'][0],df['Eta_c [-]'][0])
    turbMap.PlotDesignPoint(df['Wc4 [kg/s]'][0],df['PR_t [-]'][0],df['Eta_t [-]'][0])
    
    # Plot steady state series
    compMap.PlotOperatingCurve(df['Wc2 [kg/s]'],df['PR_c [-]'],df['Eta_c [-]'])
    turbMap.PlotOperatingCurve(df['Wc4 [kg/s]'],df['PR_t [-]'],df['Eta_t [-]'])
    
    # Finally, show created plot
    compMap.ShowPlot()
    turbMap.ShowPlot()