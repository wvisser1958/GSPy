import numpy as np
from scipy.interpolate import RegularGridInterpolator

class TMap:
    def __init__(self, name, MapFileName):    # Constructor of the class
        self.name = name
        self.MapFileName = MapFileName
        self.mapfile = None
        self.maptype = None
        self.maptitle = None

        # mapxopoints = np.array([], dtype=float)
        # mapyopoints = np.array([], dtype=float)        

    def ReadMap(self, filename):              # Abstract method, defined by convention only
        #    raise NotImplementedError("Subclass must implement abstract method")
        try:
            self.mapfile = open(filename, 'r')
            # Read the first line
            line = self.mapfile.readline()
            line_number = 1  # Initialize line number counter
            while not '99' in line:
                line = self.mapfile.readline()
            items = line.split()
            self.maptype = items[0]
            self.maptitle = rest_of_items = ' '.join(items[1:])            
            return self.maptype, self.maptitle, self.mapfile

        except FileNotFoundError:   
            print(f"Map file '{filename}' does not exist.")            
   
