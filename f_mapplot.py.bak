import matplotlib.pyplot as plt
from f_compressor import TCompressor
import numpy as np

class MapPlot:
    # properties
    
    # constructor
    def __init__(self, mapname):
        self.name = mapname
    
    # methods
    def PlotMap(self):
        pass
    
    def ShowPlot(self):
        pass
    
class CompressorMapPlot(MapPlot):
    # properties
    
    # constructor
    def __init__(self, mapname, compressorObject):
        super().__init__(mapname)
        # Compressor object containing map data
        self.compressorObject = compressorObject
        fig, (ax1, ax2) = plt.subplots(2, 1)
        self.fig = fig
        self.ax1 = ax1
        self.ax2 = ax2
    
    # methods
    def PlotMap(self):
        super().PlotMap()
        # #Setup (Visual)
        # sns.set_context("notebook", font_scale=1.5, rc={"lines.linewidth": 1.5})
        # sns.set_style('whitegrid')

        # plt.rcParams["figure.figsize"] = (25,20)
        # plt.rcParams['figure.facecolor'] = 'white'
        # plt.rcParams['axes.grid'] = False
        
        # plt.figure(0)
        # # plt.contourf(X,Y,Z, 30 ,cmap='bwr',alpha=0.3,levels = np.linspace(etamin, etamax, 30))
        # plt.colorbar()
        # # plt.contour(X,Y,Z, 10 ,colors='slategrey',levels = np.linspace(etamin, etamax, 10)) 
        # plt.show()
        
        (self.compressorObject).ReadMap((self.compressorObject).MapFileName)
        NcArrayValues   = (self.compressorObject).GetNcArray()   * (self.compressorObject).SFmap_Nc
        # BetaArrayValues = (self.compressorObject).GetBetaArray()
        WcArrayValues   = (self.compressorObject).GetWcValues()  * (self.compressorObject).SFmap_Wc
        PRArrayValues   = (self.compressorObject).GetPrValues()  * (self.compressorObject).SFmap_PR
        EtaArrayValues  = (self.compressorObject).GetEtaValues() * (self.compressorObject).SFmap_Eta
        
        self.fig.suptitle('Compressor map')

        for index, NcValue in enumerate(NcArrayValues): 
            self.ax1.plot(WcArrayValues[index], EtaArrayValues[index], linewidth=0.5, linestyle='dashed', color='black', label=str(NcValue))
        self.ax1.set_ylabel('Efficiency')

        for index, NcValue in enumerate(NcArrayValues): 
            self.ax2.plot(WcArrayValues[index], PRArrayValues[index], linewidth=0.5, linestyle='dashed', color='black', label=str(NcValue))
        self.ax2.set_xlabel('Corected massflow')
        self.ax2.set_ylabel('Pressure Ratio')

    def ShowPlot(self):
        plt.show()
    
    def PlotOperatingCurve(self,wc_values, pr_values, eta_values):
        # Pass operating data to plot in the map
        self.ax1.plot(wc_values, eta_values, linewidth=1.5, linestyle='solid', color='navy')
        self.ax2.plot(wc_values, pr_values,  linewidth=1.5, linestyle='solid', color='navy')
        
    def PlotDesignPoint(self,wc_value, pr_value, eta_value):
        self.ax1.plot(wc_value, eta_value, markersize=6.0, linestyle='none', marker='s', markeredgewidth=0.75, markerfacecolor='yellow', markeredgecolor='black')
        self.ax2.plot(wc_value, pr_value,  markersize=6.0, linestyle='none', marker='s', markeredgewidth=0.75, markerfacecolor='yellow', markeredgecolor='black')
        
# main program start
if __name__ == "__main__":
    aCompressor = TCompressor('compressor1', 'compmap.map',   1, 0.8, 1,   16540, 0.825, 6.92)
    compMap = CompressorMapPlot("compmap.map", aCompressor)
    aCompressor.SFmap_Wc = 1.00151
    aCompressor.SFmap_Eta = 0.948276
    aCompressor.SFmap_PR = 1.051659
    aCompressor.SFmap_Nc = 16539.99909
    compMap.PlotMap()
    # Read performnace data of TJET
    import pandas as pd
    df = pd.read_csv('./data/TJET.csv')
    compMap.PlotDesignPoint(df['Wc'][0],df['PR'][0],df['Eta'][0])
    compMap.PlotOperatingCurve(df['Wc'],df['PR'],df['Eta'])
    compMap.ShowPlot()
