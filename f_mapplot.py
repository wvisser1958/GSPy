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
        NcArrayValues   = (self.compressorObject).GetNcArray()
        # BetaArrayValues = (self.compressorObject).GetBetaArray()
        WcArrayValues   = (self.compressorObject).GetWcValues()  * (self.compressorObject).SFmap_Wc
        PRArrayValues   = (self.compressorObject).GetPrValues()  * (self.compressorObject).SFmap_PR
        EtaArrayValues  = (self.compressorObject).GetEtaValues() * (self.compressorObject).SFmap_Eta
        
        fig, (ax1, ax2) = plt.subplots(2, 1)
        fig.suptitle('Compressor map')

        for index, NcValue in enumerate(NcArrayValues): 
            ax1.plot(WcArrayValues[index], EtaArrayValues[index], linewidth=0.5, linestyle='dashed', color='black', label=str(NcValue))
        ax1.set_ylabel('Efficiency')

        for index, NcValue in enumerate(NcArrayValues): 
            ax2.plot(WcArrayValues[index], PRArrayValues[index], linewidth=0.5, linestyle='dashed', color='black', label=str(NcValue))
        ax2.set_xlabel('Corected massflow')
        ax2.set_ylabel('Pressure Ratio')

    def ShowPlot(self):
        plt.show()
        pass
    
    def PlotOperatingCurve(self):
        # Pass operating data to plot in the map
        pass
        
# main program start
if __name__ == "__main__":
    aCompressor = TCompressor('compressor1', 'compmap.map',   1, 0.8, 1,   16540, 0.825, 6.92)
    compMap = CompressorMapPlot("compmap.map", aCompressor)
    compMap.PlotMap()
    compMap.PlotOperatingCurve()
    compMap.ShowPlot()
    pass