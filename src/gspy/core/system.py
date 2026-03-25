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
#   Wilfried Visser
#   Oscar Kogenhop

from pathlib import Path
import numpy as np
import pandas as pd
import math
import os
import inspect
from scipy.optimize import root
import matplotlib.pyplot as plt
import gspy.core.sys_global as fg
from gspy.core.ambient import TAmbient
from gspy.core.gaspath import TGaspath

class TSystemModel:
    def __init__(self, model_name, model_root: Path | None = None):
        self.initialized = False
        if model_name is None:
            self.model_name = Path(inspect.stack()[1].filename).stem
        else:
            self.model_name = model_name
        self.params = {}

        # Default to this file's folder if caller doesn't provide a root
        if model_root is None:
            caller_file = inspect.stack()[1].filename
            default_root = Path(caller_file).resolve().parent
        else:
            default_root = model_root

        self.model_root = default_root

        # Paths relative to the chosen model root
        self.maps_dir_path = self.model_root / "maps"
        self.input_dir_path = self.model_root / "input"
        self.output_dir_path = self.model_root / "output"

        # Tell the core where to put outputs
        # 2.0 obsolete fg.output_dir_path = self.output_dir_path

        self.ambient = TAmbient(self, 'Ambient', 'a', 0, 0,   0,   None,   None)

        # use dictionary for gas path conditions oriented by gas path station number
        self.gaspath_conditions = {}

        # 1.1 WV dictionary for output during iteration (e.g. for control equations)
        self.output_dict = {}

        self.component_run_list = [self.ambient] # system model component list, always starting with ambient
        self.shaft_list = []

        self.inputpoints = np.array([], dtype=float)
        self.points_output_interval = 1

        self.states = np.array([], dtype=float)
        self.errors = np.array([], dtype=float)

        # system performance, in this case a gs turbine
        self.FG = 0.0
        self.FN = 0.0
        self.RD = 0.0
        self.WF = 0.0
        self.PW = 0.0

        self.reset_output()

        self.VERBOSE = True

        self.mode = None
        self.error_tolerance = 0.0001 # default error tolerance 0.1%, override if needed in main code

        # error code constants
        self.no_error = 0
        self.no_convergence_error = 1
        self.max_iterations_exceeded_error = 2
        self.false_convergence_error = 3
        self.exception_error = 4

        self.continue_next_OD_point_on_error = True

    def get_error_text(self, error_code):
        if error_code == self.no_convergence_error:
            return 'Not converged'
        elif error_code == self.max_iterations_exceeded_error:
            return 'Max. nr. of iterations exceeded'
        elif error_code == self.false_convergence_error:
            return 'False Krylov convergence'
        elif error_code == self.exception_error:
            return 'Exception error'
        else:
            return ''
        # Do print to console!
        self.VERBOSE = True

    def get_shaft(self, ShaftNr):
        for shaft in self.shaft_list:
            if shaft.ShaftNr == ShaftNr:
                return shaft
        return None  # Return None if no matching object is found

    # find system model component object by name
    def get_comp(self, component_name):
        for comp in self.component_run_list:
            if comp.name == component_name:
                return comp
        return None  # Return None if no matching object is found

    def get_component_object_by_name(self, aname):
        return next((obj for obj in self.component_run_list if obj.name == aname), None)

    def get_gaspathcomponent_object_inlet_stationnr(self, astationnr):
        return next((obj for obj in self.component_run_list if (isinstance(obj, TGaspath)) and (obj.station_in == astationnr)), None)

    def reinit_states_and_errors(self):
        # global states, errors
        for state in self.states:
            state = 1
        for error in self.errors:
            state = 0

    def reset_output(self):
        self._output_rows = []
        self.output_table = None

    def reinit_system(self):
        for shaft in self.shaft_list:
            shaft.PW_sum = 0
        # global FG, FN, RD, WF
        self.FG = 0.0    # Gross thrust kN
        self.FN = 0.0    # Net thrust kN
        self.RD = 0.0    # Ram drag kN
        self.WF = 0.0    # Total fuel
        self.PW = 0.0    # Total net output shaft power

    # method running component model simulations/calculations
    # from inlet(s) through exhaust(s)
    def Do_Run(self, mode, point_time, states_par):
        # global system_model, states, errors, Ambient, Control
        self.states = states_par.copy()
        self.reinit_system()
        # Ambient.Run(Mode, PointTime)
        # Ambient.AddOutputToDict(Mode)

        self.output_dict['Point/Time'] = point_time
        self.output_dict['Mode'] = mode

        # 1.6 new PreRun virtual method
        for comp in self.component_run_list:
            comp.PreRun(mode, point_time)

        # Run simulation code of all components in the system model
        for comp in self.component_run_list:
            comp.Run(mode, point_time)

            # comp.AddOutputToDict(aMode)
            self.output_dict.update(comp.get_outputs())

        # v1.3 moved to BEFORE PostRun calls
        # self.AddSystemOutputToDict(mode)
        self.output_dict.update(self.get_outputs())

        for comp in self.component_run_list:
            comp.PostRun(mode, point_time)
        return self.errors

    # 2.0.0.0
    # self.component_run_list, always starting with ambient
    def define_comp_run_list(self, *component_list):
        self.component_run_list = [self.ambient, *component_list]

    # 1.6.0.1.8 dictionary with design targets and variables
    # def Run_DP_simulation():
    def Run_DP_simulation(self, targets = None):
        try:
            self.reinit_states_and_errors()

            if targets is None:
                self.Do_Run('DP', 0, self.states)
            else:
                try:
                    var_values_ref = [0.0] * len(targets)

                    for i, (varobj, varattr, targetobj, targetattr, targetvalue) in enumerate(targets):
                        var_values_ref[i] = getattr(varobj, varattr)

                    def targetresiduals(dp_variables):
                        for i, (varobj, varattr, targetobj, targetattr, targetvalue) in enumerate(targets):
                            setattr(varobj, varattr, dp_variables[i] * var_values_ref[i])

                        self.Do_Run('DP', 0, self.states)

                        residuals = [0.0] * len(targets)
                        for i, (varobj, varattr, targetobj, targetattr, targetvalue) in enumerate(targets):
                            actual = getattr(targetobj, targetattr)
                            residuals[i] = (actual - targetvalue) / targetvalue

                        return residuals

                    dp_variables_init = [1.0] * len(targets)

                    solution = root(
                        targetresiduals,
                        dp_variables_init,
                        method='krylov',
                        # tol=self.error_tolerance,
                        # options={'maxiter': 100}
                         options={
                                'maxiter': 100,
                                'fatol': self.error_tolerance,     # absolute residual target
                                'xatol': 1e-12,                     # avoid premature "small step" success
                                }
                    )
                except Exception as e:
                    self.Do_Output(0, self.exception_error)
                    print(f"DP target iteration exception error: {e}")

            self.targets = targets # save target information for output

            self.Do_Output(0, self.no_error)      # 0 to indicated all Ok if we get to this line of code after Do_Run
        except Exception as e:
            self.Do_Output(0, self.exception_error)
            print(f"DP simulation: exception error: {e}")

    def print_DP_equation_solution(self):
        if self.targets != None:
            print(f"DP simulation equations solution:")
            for i, (varobj, varattr, targetobj, targetattr, targetvalue) in enumerate(self.targets):
                print(f"\t{f'{targetobj.name}.{targetattr}':<26} = {targetvalue:>10} (target)   at {f'{varobj.name}.{varattr}':<26} = {f'{getattr(varobj, varattr)}':>22}")

    def Run_OD_simulation(self):
        def residuals(states):
            # residuals will return residuals of system conservation equations, schedules, limiters etc.
            # the residuals are the errors returned by Do_Run
            return self.Do_Run('OD', self.inputpoints[ipoint], states)

        try:
            # start with all states 1 and errors 0
            self.print_states_and_errors()
            self.reinit_states_and_errors()
            maxiter=100
            successcount = 0
            failedcount = 0
            for ipoint in self.inputpoints:
                # solution returns the residual errors after conversion (shoudl be within the tolerance 'tol')
                # fsys.Do_Output(Mode, inputpoints[ipoint])
                try:
                    solution = root(residuals,
                                    self.states,
                                    method = 'krylov',
                                    # tol=self.error_tolerance,
                                    # options={'maxiter': maxiter})
                                        options={
                                                'maxiter': maxiter,
                                                'fatol': self.error_tolerance,     # absolute residual target
                                                'xatol': 1e-12,                     # avoid premature "small step" success
                                                }
                                    )
                                    # options={'maxiter': maxiter, 'xtol': 0.01})
                                    # options={'maxiter': maxiter, 'line_search': 'wolfe'})
                    # 2.0
                    r = residuals(solution.x)
                    rmax = np.max(np.abs(r))
                    if rmax > self.error_tolerance:
                        raise RuntimeError(f"{self.get_error_text(self.false_convergence_error)}: residual {rmax}")

                    if ipoint % self.points_output_interval == 0:
                        self.Do_Output(self.inputpoints[ipoint], self.no_error if solution.success else self.convergence_error)
                    if solution.success:
                        successcount = successcount + 1
                    else:
                        failedcount = failedcount + 1
                        print(f"Could not find a solution for point {ipoint} with max {maxiter} iterations")
                except Exception as e:
                    if rmax > self.error_tolerance:
                        error_index = self.false_convergence_error
                    else:
                        error_index = self.exception_error
                    self.Do_Output(self.inputpoints[ipoint], error_index)
                    failedcount = failedcount + 1
                    print(f"OD simulation: Error at point {ipoint}: {e}")
                    if not self.continue_next_OD_point_on_error:
                        break

        except Exception as e:
            self.Do_Output(self.inputpoints[ipoint], self.exception_error)
            failedcount = failedcount + 1
            print(f"OD simulation: exception error: {e}")

        print(f"{successcount} OD points calculated, {failedcount} failed")

        # v1.2 return number of succesfully calculated points
        return successcount

    def PrintPerformance(self, mode, PointTime):
        print(f"System performance ({mode}) Point/Time:{PointTime}")
        if (self.FG != 0) or (self.RD !=0):
            self.FN = self.FG - self.RD
            print(f"\tGross thrust: {self.FG:.2f} kN")
            print(f"\tRam drag    : {self.RD:.2f} kN")
            print(f"\tNet thrust  : {self.FN:.2f} kN")
        self.PW = 0
        for shaft in self.shaft_list:
            self.PW = self.PW + shaft.PW_sum
            print(f"\tPower offtake shaft {shaft.ShaftNr} : {shaft.PW_sum/1000:.2f} kW")
        if not math.isclose(self.PW, 0.0, abs_tol=1e-9):
            print(f"\tTotal power output : {self.PW/1000:.2f} kW")

    # 2.0.0.0
    def get_outputs(self):
        out = {}
        self.FN = self.FG - self.RD
        out["FG"] = self.FG
        out["FN"] = self.FN
        out["RD"] = self.RD
        out["WF"] = self.WF
        self.PW = 0
        for shaft in self.shaft_list:
            self.PW = self.PW + shaft.PW_sum
            out[f"PW{shaft.ShaftNr}"] = shaft.PW_sum/1000
        out["PW"] = self.PW/1000
        return out

    # v1.2
    # def Do_Output(PointTime, Solution):
    def Do_Output(self, PointTime, error_code):
        # output to terminal
        # global system_model,  OutputTable, Ambient

        if self.VERBOSE:
            # 1.4
            print(f"")
            print(f"Point {PointTime}:")

            for comp in self.component_run_list:
                comp.PrintPerformance(self.mode, PointTime)
            self.PrintPerformance(self.mode, PointTime)

        #  2.0
        self.output_dict['Comment'] = self.get_error_text(error_code)

        #  2.0
        # add output of this point (ouptut_dict) to output_rows dictionary
        self._output_rows.append(self.output_dict.copy())

        # add system performance
        # self.AddSystemOutputToDict(self.mode)

    def print_states_and_errors(self):
        print(f"Nr. of state variables: {len(self.states)}\nNr. of error equations: {len(self.errors)}")

    def prepare_output_table(self):
        #  collect output_rows in dataframe, for processing in OutputToCSV, Plot_X_nY_graph, PlotMaps etc.
        self.output_table = pd.DataFrame(self._output_rows)

    def OutputToCSV(self):
        # Export to Excel
        os.makedirs(self.output_dir_path, exist_ok=True)
        outputcsvfilename = os.path.join(self.output_dir_path, self.model_name + ".csv")
        self.output_table.to_csv(outputcsvfilename, index=False, float_format='%.6f')
        print("output saved in "+outputcsvfilename)

    def Plot_X_nY_graph(self, title, filename_suffix, xcol, ycollist, do_show = False):
        # Plot output_tableable data
        # Create n subplots stacked vertically, sharing the same X-axis
        fig, axes = plt.subplots(nrows=len(ycollist), ncols=1, sharex=True, figsize=(8, 10))
        for ax in axes:
            ax.grid(True, linestyle=':', linewidth=1.0, alpha=1.0)  # add

        # # Plot each variable
        yaxisnr = 0
        xname, xlabel = xcol

        # one-time mask for design points
        dp_mask = (self.output_table["Mode"] == "DP")

        for item in ycollist:
            col   = item[0]
            label = item[1] if len(item) > 1 else item[0]
            color = item[2] if len(item) > 2 else None

            ax = axes[yaxisnr]

            # main line
            ax.plot(self.output_table[xname], self.output_table[col], color=color, zorder=2)
            ax.set_ylabel(label)

            # screen-fixed squares at design points (only for rows where Mode == "DP")
            ax.scatter(
                self.output_table.loc[dp_mask, xname],
                self.output_table.loc[dp_mask, col],
                s=40,                    # points^2, screen-fixed size
                marker="s",
                facecolors="yellow",
                edgecolors="black",
                linewidths=0.8,
                zorder=1,
                label="Design point" if yaxisnr == 0 else None  # add legend label once
            )

            yaxisnr += 1

        axes[yaxisnr - 1].set_xlabel(xlabel)

        # optional: show a single legend (pull handles/labels from the first axes)
        handles, labels = axes[0].get_legend_handles_labels()
        if handles:
            axes[0].legend(handles, labels, loc="best")

        # Optional: improve layout
        fig.suptitle(title, fontsize=14)
        fig.tight_layout(rect=[0, 0, 1, 0.96])
        # 2.0.0.0
        if do_show:
            plt.show()
        # xyplotfilename = os.path.join(output_directory, os.path.splitext(os.path.basename(__file__))[0]) + ".jpg"
        # 2.0.0.0
        # jpg_filename = self.model_name + filename_suffix + ".jpg"
        jpg_filename = os.path.join(self.output_dir_path, self.model_name + filename_suffix + ".jpg")
        fig.savefig(jpg_filename)
        print("x-4y plot saved in " + jpg_filename)

    def PlotMaps(self):
        for comp in self.component_run_list:
           comp.PlotMaps()
