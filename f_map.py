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
from scipy.interpolate import SmoothBivariateSpline
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

    def CalcMapEtaTopology(self, XArrayValues, YArrayValues, FArrayValues, doSmooth=True):
        """
        Interpolates efficiency data onto a regular grid for contour plotting.

        Parameters:
        ----------
        XArrayValues : ndarray
            X-axis data (e.g., corrected mass flow, Wc) — can be scaled if needed.
        YArrayValues : ndarray
            Y-axis data (e.g., pressure ratio, PR).
        FArrayValues : ndarray
            Function values (e.g., efficiency or Eta).
        doSmooth : bool, optional
            If True, applies Gaussian smoothing to the result.

        Returns:
        -------
        X_mesh : ndarray
            2D meshgrid for X-axis (shape: [n_points, n_points]).
        Y_mesh : ndarray
            2D meshgrid for Y-axis (shape: [n_points, n_points]).
        F_grid : ndarray
            Interpolated F-values (shape: [n_points, n_points]).
        """

        # Flatten input arrays for interpolation
        x_flat = XArrayValues.flatten()
        y_flat = YArrayValues.flatten()
        f_flat = FArrayValues.flatten()

        # Create uniform grid in X and Y
        x_lin = np.linspace(XArrayValues.min(), XArrayValues.max(), 100)
        y_lin = np.linspace(YArrayValues.min(), YArrayValues.max(), 100)
        X_mesh, Y_mesh = np.meshgrid(x_lin, y_lin)

        # Interpolate F-values onto the grid
        F_grid = griddata(
            (x_flat, y_flat),   # Known data points
            f_flat,             # Function values at data points
            (X_mesh, Y_mesh),   # Target grid
            method='linear'     # Interpolation method
        )

        # Optionally smooth the interpolated surface
        if doSmooth:
            # F_grid = gaussian_filter(F_grid, sigma=0.8)
                # Fit smooth spline to the data
            spline = SmoothBivariateSpline(x_flat, y_flat, f_flat, s=0.001)  # s controls smoothing

            # Evaluate spline on grid
            F_grid = spline.ev(X_mesh.ravel(), Y_mesh.ravel()).reshape(X_mesh.shape)

        return X_mesh, Y_mesh, F_grid


