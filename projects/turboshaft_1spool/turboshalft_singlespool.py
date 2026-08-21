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

from gspy.core.system import TSystemModel

from gspy.core.control import TControl
from gspy.core.inlet import TInlet
from gspy.core.compressor import TCompressor
from gspy.core.combustor import TCombustor
from gspy.core.turbine import TTurbine
from gspy.core.duct import TDuct
from gspy.core.exhaustdiffuser import TExhaustDiffuser
from gspy.core.load import TLoad
from gspy.core.bleedflow import TBleedFlow
from gspy.core.coolingflow import TCoolingFlow

# IMPORTANT NOTE TO THIS MODEL FILE
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# Single spool turboshaft APU model with bleed flows and cooling flows, using a radial compressor map
# and a standard turbine map. This is a simplified model for demonstration purposes, and does not
# represent a real APU. The model employs a generator power offtake only, and does not include any other
# shaft loads or accessories. The model excludes a load compressor, it produces electricity only. The
# model is not validated against any real data, and should not be used for any design or analysis
# purposes. The model is intended for educational purposes only, to demonstrate the use of GSPy for
# modeling a turboshaft APU with bleed flows and cooling flows.
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!


def main():
    turboshaft = TSystemModel("BLeedlessAPU", model_file=__file__)

    # Override ambient object station number to with new station string
    print("Ambinet station string: ", turboshaft.ambient.get_station_nr())
    turboshaft.ambient.set_station_nr("000")
    print("Ambinet station string: ", turboshaft.ambient.get_station_nr())

    # Uncomment control creation statement for either fuel flow ("Fcontrol"), N1% ("Ncontrol") or EGT aka T5 ("EGTcontrol"):
    # FuelControl for open loop direct control of fuel flow
    fuelcontrol = TControl(
        system=turboshaft,        # Owning system model object
        name="Fcontrol",          # Component name
        # map_filename = '',        # Optional map file name
        DP_input_value=0.060774,  # Design point (DP) input (Wf)
        OD_start_value=100,
        # OD_end_value = None,
        # OD_step_value = None,     # Off design (OD) input: single input value -> 100 % N1
        OD_controlled_parameter_name="Nc%_Compressor",
        # OD control parameter name: must be an output present in the output table
        # If None: the component using it directly takes the value
        # If specified with parameter name, an equation is added forcing the parameter to match the input values
        # and the component using it makes it's input a free state variable
        # e.g. specify 'N1' to control rotor speed, with the combustor turning the Wf into a free state variable
    )

    # Example for N1 rotor speed control:
    # fuelcontrol = TControl('Ncontrol', '', 0.38, 100, 60, -5, 'N1%')

    # EGT (T5) control example:
    # fuelcontrol = TControl('EGTcontrol', '', 0.38, 1020, 820, -50, 'T5')
    # Note that for a gas turbine, this method may well become instable at lower power setting due to multiple solutions at same T5

    # Generic gas turbine components
    inlet = TInlet(
        system=turboshaft,        # Owning system model object
        name="Inlet1",            # Component name
        # map_filename = '',        # Map file name
        # control = None,           # Optional control component
        station_in="000",         # Station nr in
        station_out="020",        # Station nr out
        Wdes=3.844,               # design inlet mass flow
        PRdes=0.9934,             # design pressure ratio (PR = 1 - Ploss_relative)
    )

    # compressor bleeds
    compressor_bleeds = [
        TBleedFlow(
            system=turboshaft,
            name="HPbleed",
            station_in="031",      # station in
            station_out="032",     # station out
            bleednumber=1,         # bleed number
            bleedfractiondes=0.05, # fraction of compressor inlet flow
            dPfactor=1.0,          # dP factor: bleed extraction pressure fraction: Pbleed = Pin + dP * dPtotal
            # this is an improvement over the GSP method where it was proportional to dH
            # dPfraction can be directly determined from the bleed pressure level requirement
        )
    ]

    compressor = TCompressor(
        system=turboshaft,         # Owning system model object
        name="Compressor",         # Component name
        map_filename="RadComp10-AIAA-79-1159.MAP",  # Map file name
        #  control = None,         # Optional control component
        station_in="020",          # Station nr in
        station_out="030",         # Station nr out
        shaft_id=1,                # Shaft nr
        Ndes=36000,                # Design rpm
        Etades=0.6787,             # Design efficiency
        Ncmapdes=1.0,              # Map design Nc (for scaling)
        Betamapdes=0.59714,        # Map design Beta (for scaling)
        PRdes=8.0677,              # Design pressure ratio
        SpeedOption="GG",          # Speed option
        Bleeds=compressor_bleeds,  # Optional bleed flows object list
        # heatpaths = None          # Optional list of heat path links with heatsinks)
    )

    combustor = TCombustor(
        system=turboshaft,         # Owning system model object
        name="Combustor",          # Component name
        # map_filename = '',        # Map file name; for future use of a combustor efficiency map
        # OD fuel input from FuelControl
        control_component=fuelcontrol, # Fuel control component; fuel control component setting fuel flow depending on OD / PointTime point
        station_in="030",          # Station nr in
        station_out="040",         # Station nr out
        Wfdes=0.0637,              # Design point (DP) fuel flow Wfdes
        Texitdes=1250,             # Texit design  - if specified (not None) Wfdes will be calculated from Texit,
        PRdes=0.96,                # Design pressure ratio, use to specify rel. pressure loss ploss (PR = (1 - ploss)/Pin)
        Etades=0.985,              # Design combustor efficiency
        Tfueldes=None,             # Fuel temperature K; if None, then Tfuel is assumed to be equal to temperature of entry air flow
        # For the fuel properties specification there are 2 options:
        #     1:        Virtual fuel with unknown composition:
        #                   specify LHV, H/C ratio, O/C ratio and Tfuel. GSPy will then do the species bookkeeping, determine the exit
        #                   gas composition based in inlet air/gas composition, H/C, O/C
        #                   and calculated the exit temperature from chemical equilibrium
        #     2:        Specify the fuel composition using Cantera composition string like
        #                   'NC12H26:1' (dodecane),
        #                   'CH4:9, N2:1' (mixture of CH4 and N2 in ratio 9:1 by mass)
        #                   or 'CH4:5, C2H6:1' for example, and fuel temperature
        LHVdes=43031,              # LHV, required if Fuelcomposition is None
        HCratiodes=1.9167,         # HCratio
        OCratiodes=0,              # OCratio
        FuelCompositiondes=None,   # Fuelcomposition  alternative: take 'NC12H26:1' for a jet fuel surrogate for example
        A=None,                    # Cross flow area to calculate fundamental pressue loss
    )

    # GGT cooling flows
    cooling_flows = [
        TCoolingFlow(
            system=turboshaft,
            name="turb_nozzle_cooling",
            station_in="032",
            station_out="041",
            coolingflownumber=1,
            frombleednumber=1,
            fractiontakendes=1.0,
            dPfraction=1.0,
            W_tur_eff_fraction=1.0,
            Rexit=0,  # pumpin radius (only > 0 for rotor blades)
        )
    ]

    turbine = TTurbine(
        system=turboshaft,           # Owning system model object
        name="Turbine1",             # Component name
        map_filename="turbimap.map", # Map file name
        control_component=None,      # Optional control component
        station_in="040",            # Station nr in
        station_out="050",           # Station nr out
        shaft_id=1,                  # Shaft nr
        Ndes=36000,                  # Design point (DP) rpm
        Etades=0.88,                 # Design point (DP) efficiency
        Ncmapdes=1,                  # Map design Nc (for scaling)
        Betamapdes=0.50943,          # Map design Beta (for scaling)
        Etamechdes=0.99,             # Design mechanical efficiency (standard isentropic, Polytropic_Eta = 0)
        #   TurbineType="GG",  # Turbine type 'GG' = gas generator delivering all power required by the shaft
        # A single spool APU does not use all power for the compressor as there might be power off-take for a
        # generator or other shaft load, so the turbine type is set to 'PT' = free power turbine
        TurbineType="PT",            # Turbine type 'PT' = free power turbine or turbine driving power output shaft
        CoolingFlows=cooling_flows,  # Optional cooling flows object list
        Polytropic_DP_eta=0,         # option for working with polytropic efficiency in DP set Polytropic_DP_Eta=1 (OD always isentropic)
    )

    duct = TDuct(
        system=turboshaft,    # Owning system model object
        name="ExhDuct",       # Component name
        #  map_filename = '',   # Optional map file name
        station_in="050",     # Station nr in
        station_out="070",    # Station nr out
        PRdes=1.0,            # Design pressure ratio, use to specify rel. pressure loss ploss (PR = (1 - ploss)/Pin)
    )

    exhaust_diffuser = TExhaustDiffuser(
        system=turboshaft,       # Owning system model object
        name="ExhaustDiffuser",  # Component name
        # map_filename = '',       # Optional map file name
        station_in="070",        # Station nr in
        station_out="090",       # Station nr out
        # PRdes=0.9724,            # Design diffuser pressure loss (Psout/Ptin) in case of a (divergent) exhaust diffuser
        PRdes=0.924,             # Design diffuser pressure loss (Psout/Ptin) in case of a (divergent) exhaust diffuser
    )

    generator_load = TLoad(
        system=turboshaft,       # Owning system model object
        name="GeneratorLoad",    # Component name
        drive_shaft_id=1,        # Shaft number of the load, must be defined in the model file before this load, the shaft could also be created in the model file first
        power_kw_des=450,        # Design power of the load in kW, used to calculate the power demand of the load at design conditions, and to calculate the power demand at off-design conditions based on the power demand set by the control component
    )

    # create a turbojet system model
    turboshaft.define_comp_run_list(
        fuelcontrol,
        inlet,
        compressor,
        combustor,
        turbine,
        duct,
        exhaust_diffuser,
        generator_load,
    )

    # turbojet.error_tolerance = 0.0001   # default iteration equation relative residual tolerance, adjust when needed

    print("--- Start of running APU turboshaft simulation ---")
    # Run the system model Design Point (DP) calculation
    turboshaft.mode = "DP"
    print("Design point (DP) results")
    print("=========================")
    # Set DP ambient/flight conditions
    turboshaft.ambient.SetConditions("DP", 0, 0, 0, None, None)
    turboshaft.Run_DP_simulation()

    # # Run the Off-Design (OD) simulation, to find the steady state operating points for all fsys.inputpoints
    # turboshaft.mode = 'OD'
    # turboshaft.inputpoints = fuelcontrol.get_OD_input_points()
    # print("\nOff-design (OD) results")
    # print("=======================")
    # # Set OD ambient/flight conditions; note that Ambient.SetConditions must be implemented inside RunODsimulation if a
    # # sweep of operating/inlet conditions is desired
    # turboshaft.ambient.SetConditions('OD', 0, 0, 0, None, None)
    # # Run OD simulation
    # turboshaft.Run_OD_simulation()

    # Export OutputTable to CSV
    turboshaft.OutputToCSV()

    # # Plot nY vs X parameter
    # turboshaft.Plot_X_nY_graph('Engine performance vs. N [%]',
    #                         # suffix for filename to keep multiple plot files apart
    #                         "_1",
    #                         # common X parameter column name with label
    #                         ("N1%", "Rotor speed [%]"),
    #                         # 4 Y paramaeter column names with labels and color
    #                         [   ("T4",              "TIT [K]",                  "blue"),
    #                             ("T5",              "EGT [K]",                  "blue"),
    #                             ("W2",              "Inlet mass flow [kg/s]",   "blue"),
    #                             ("Wf_Combustor",    "Fuel flow [kg/s]",         "blue"),
    #                             ("FN",              "Net thrust [kN]",          "blue")            ])

    #  # Create component map plots with operating lines if available
    # turboshaft.PlotMaps()

    print("---  End of running APU turboshaft simulation  ---")


# Main program start, calls main()
if __name__ == "__main__":
    main()
