import numpy as np
import cantera as ct
from f_map import TMap
from typing import Optional

class TComponent:
    def __init__(self, name, MapFileName):    # Constructor of the class
        self.name = name
        # assume in moste case single map in instantiable child classes (add extra map if necessary, e.g. with f_fan)
        self.map: Optional[TMap] = None

    def Run(self, Mode, PointTime):
        raise NotImplementedError("Subclass must implement Run abstract method")

    def PrintPerformance(self, Mode, PointTime):
        print(f"{self.name} ({Mode}) Point/Time:{PointTime}")

    def PlotMaps(self): # Plot performance in map(s)
        if self.map != None:
            self.map.PlotMap()

    def GetOutputTableColumnNames(self):
        # raise NotImplementedError("Subclass must implement InitOutputTable abstract method")
        return []

    def AddOutputToTable(self, Mode, rownr):
        raise NotImplementedError("Subclass must implement AddOutputToTable abstract method")

