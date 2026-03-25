# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#    http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Authors
#   Oscar Kogenhop

import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import RegularGridInterpolator
from scipy.interpolate import griddata
from scipy.interpolate import SmoothBivariateSpline
from scipy.ndimage import gaussian_filter
import os
from gspy.core import sys_global as fg

class TMap:
    def __init__(self, host_component, name, map_filename, OL_xcol, OL_ycol):    # Constructor of the class
        # This is the link to the object which created the map
        self.host_component = host_component
        self.name = name

        # the filename of the map as located in TSystem_Model.maps_dir_path
        self.map_filename = map_filename

        # 2.0 standard map directory (default 'maps' subdirectory under project file)
        self.map_dir_path = self.host_component.owner.maps_dir_path

        # the textIOwrapper into which the map file data are read
        self.map_file = None

        self.map_type = None
        self.map_title = None

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
        # # output_dir = './output/'
        # output_dir = self.owner.output_dir_path

        # # Mapnaming, override or extend in child classes
        # # 1.4
        # # self.map_figure_file_path = output_dir + self.name + '.jpg'
        self.map_figure_dir_path = self.host_component.owner.output_dir_path
        self.map_figure_file_path = self.host_component.owner.output_dir_path / (self.name + ".jpg")
        # # Create the directory if it doesn't exist
        # if not os.path.isdir(output_dir):
        #     os.makedirs(output_dir)

    @property
    def simresultstable(self):
        return self.host_component.owner.output_table

    def ReadMap(self, filename):              # Abstract method, defined by convention only
        try:
            # self.map_file = open(filename, 'r')
            self.map_file = open(self.map_dir_path / filename, 'r')
            # Read the first line
            line = self.map_file.readline()
            line_number = 1  # Initialize line number counter
            while not '99' in line:
                line = self.map_file.readline()
            items = line.split()
            self.map_type = items[0]
            self.map_title = rest_of_items = ' '.join(items[1:])
            return self.map_type, self.map_title, self.map_file

        except FileNotFoundError:
            print(f"Map file '{self.map_dir_path / filename}' does not exist.")

    # Map plotting routine
    def PlotMap(self):
        # Note; images are plotted in an output folder, if you use Windows, mind that a Windows Explorer feature treats this folder
        #       as a pictures folder, this means is doesnt update the cahnged date when images are overwritten!
        #       https://stackoverflow.com/questions/49039581/matplotlib-savefig-will-not-overwrite-old-files
        self.map_figure = plt.figure(num=self.name, figsize = self.map_size)
        self.main_plot_axis = self.map_figure.gca()
