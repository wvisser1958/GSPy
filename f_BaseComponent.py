import numpy as np
import cantera as ct
# from scipy.interpolate import RegularGridInterpolator

class TComponent:
    def __init__(self, name, MapFileName):    # Constructor of the class
        self.name = name
        self.MapFileName = MapFileName
        self.mapfile = None
        self.maptype = None
        self.maptitle = None

    def ReadMap(self, filename):              # Abstract method, defined by convention only
        #    raise NotImplementedError("Subclass must implement abstract method")
        try:
            amapfile = open(filename, 'r')
            # Read the first line
            line = amapfile.readline()
            line_number = 1  # Initialize line number counter
            while not '99' in line:
                line = amapfile.readline()
            items = line.split()
            amaptype = items[0]
            amaptitle = rest_of_items = ' '.join(items[1:])            
            return amaptype, amaptitle, amapfile

        except FileNotFoundError:   
            print(f"Map file '{filename}' does not exist.")            
    
    def Run(self, Mode, PointTime, GasIn: ct.Quantity) -> ct.Quantity:    
        raise NotImplementedError("Subclass must implement Run abstract method")
    
    def PrintPerformance(self, Mode, PointTime):
        print(f"{self.name} ({Mode}) Point/Time:{PointTime}")

    def GetOutputTableColumnNames(self):
        # raise NotImplementedError("Subclass must implement InitOutputTable abstract method")
        return []
        
    def AddOutputToTable(self, Mode, rownr):
        raise NotImplementedError("Subclass must implement AddOutputToTable abstract method")

