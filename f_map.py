# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#    http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import RegularGridInterpolator
from scipy.interpolate import griddata
from scipy.ndimage import gaussian_filter
import os

class TMap:
    def __init__(self, host_component, name, MapFileName, OL_xcol, OL_ycol):    # Constructor of the class
        self.name = name
        self.MapFileName = MapFileName
        self.mapfile = None
        self.maptype = None
        self.maptitle = None
        # This is the link to the object which created the map
        self.host_component = host_component
        # The map figure object
        self.map_figure = None
        # Map size controlled from a paramter to create identical map sizes
        self.map_size = (10, 8)
        # Axis of the plot
        self.main_plot_axis = None

        # output par names for map operating line
        self.OL_xcol = OL_xcol
        self.OL_ycol = OL_ycol

        # Output folder
        output_dir = './output/'

        # Mapnaming, override or extend in child classes
        self.map_figure_pathname = output_dir + self.name + '.jpg'

        # Create the directory if it doesn't exist
        if not os.path.isdir(output_dir):
            os.makedirs(output_dir)

    def ReadMap(self, filename):              # Abstract method, defined by convention only
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

    # Map plotting routine
    def PlotMap(self):
        # Note; images are plotted in an output folder, if you use Windows, mind that a Windows Explorer feature treats this folder
        #       as a pictures folder, this means is doesnt update the cahnged date when images are overwritten!
        #       https://stackoverflow.com/questions/49039581/matplotlib-savefig-will-not-overwrite-old-files
        self.map_figure = plt.figure(num=self.name, figsize = self.map_size)
        self.main_plot_axis = self.map_figure.gca()

    def CalcMapEtaTopology(self, WcArrayValues, PRArrayValues, EtaArrayValues, doSmooth=True):
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

