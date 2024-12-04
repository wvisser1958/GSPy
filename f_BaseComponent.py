import numpy as np
import cantera as ct
# from scipy.interpolate import RegularGridInterpolator

class TComponent:
    def __init__(self, name, MapFileName):    # Constructor of the class
        self.name = name
        self.MapFileName = MapFileName
        self.mapfile = None

    def ReadMap(self, filename):              # Abstract method, defined by convention only
        #    raise NotImplementedError("Subclass must implement abstract method")
        try:
            self.mapfile = open(filename, 'r')
            self.ReadMapHeader(self.mapfile)
        except FileNotFoundError:   
            print(f"Map file '{filename}' does not exist.")            

    def ReadMapHeader(self, file): 
        # Read the first line
        line = file.readline()
        line_number = 1  # Initialize line number counter
        while not '99' in line:
            line = file.readline()

        items = line.split()
        maptype = items[0]
        maptitle = rest_of_items = ' '.join(items[1:])            
        return maptype, maptitle
    
    def ReadNcBetaCrossTable(self, file, keyword):
        line = file.readline()  
        while keyword not in line.upper():
            line = file.readline()  
        line = file.readline()  
        items = line.split()
        nccount1, betacount1  = divmod(float(items[0]),1)
        nccount = round(nccount1)-1
        betacount = round(betacount1*1000)-1

        beta_values = np.array(list(map(float, line.split()[1:])))
        nc_values = np.empty(nccount, dtype=float)
        fval_array = np.zeros((nccount, betacount), dtype=float)
        line = file.readline()  
        inc = 0
        while line.strip():
            items = line.split()
            nc_values[inc] = float(items[0])
            fval_array[inc] = list(map(float, line.split()[1:]))
            line = file.readline()  
            inc +=1        
        return nc_values, beta_values, fval_array      
    
    # def MapMassFlow(Nc, Beta):
    #     return RegularGridInterpolator()

    def Run(self, Mode, PointTime, GasIn: ct.Quantity) -> ct.Quantity:    
        raise NotImplementedError("Subclass must implement Run abstract method")
    
    def PrintPerformance(self, Mode, PointTime):
        print(f"{self.name} ({Mode}) Point/Time:{PointTime}")

    def GetOutputTableColumnNames(self):
        # raise NotImplementedError("Subclass must implement InitOutputTable abstract method")
        return []
        
    def AddOutputToTable(self, Mode, rownr):
        raise NotImplementedError("Subclass must implement AddOutputToTable abstract method")

