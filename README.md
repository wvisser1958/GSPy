<p align="center">
  <img src="docs/logos/GSPy_logo_final.png" width="140"/>
</p>

<h2 align="center">GSPy</h2>
<p align="center">Gas turbine system simulation in Python</p>

# GSPy
GSPy is a Python-based tool for modelling and simulating propulsion and power system performance. Developed by the creators of GSP, this implementation demonstrates how leveraging robust existing libraries can significantly reduce the need for writing large amounts of custom code.

### Authors:
- Wilfried Visser
- Oscar Kogenhop

### Contributors:
- Lucas Middendorp

--------------------------------------------------------------------------------
CONTENTS:
---------------------------------
1. License
2. Version history
3. Hints
4. Known issues
5. Other
6. GSPy Development Team
---------------------------------

********************************************************************************
## 1. LICENSE
********************************************************************************

This project is licensed under the Apache License 2.0
See the LICENSE file for details.

********************************************************************************
## 2. VERSION HISTORY
********************************************************************************
### GSPy v2.0.0.0                                                     14-04-2026
--------------------------------------------------------------------------------
### Improvements
--------------------------------------------------------------------------------
- Folder structure
  * It is assumed that models run from a project folder, where standard folder
    locations are assumed to find requested data, see the .\projects folder
    of the project. As an example, see the folder structure of the turbojet
    demo project:
      turbojet/
      ├── data/
      │   ├── fluid_props/
      │   │   ├── jetsurf.yaml
      │   │   └── jetsurf_noPAH.yaml
      │   └── maps/
      │       ├── compmap-scaled.map
      │       ├── compmap.map
      │       └── turbimap.map
      ├── input/
      │   ├── Turbojet_AMinput.csv
      ├── output/
      │   ├── Turbojet.csv
      │   ├── Turbojet_1.jpg
      │   ├── compressor1_map.jpg
      │   ├── compressor1_map_dual.jpg
      │   ├── turbine1_map.jpg
      │   └── turbine1_map_dual.jpg
      ├── turbojet.py
      ├── turbojet_AM.py
      ....
  * The yaml file with the gas properties data for Cantera must be located in the
    project/data/fluid_props/ sub folder. Per default, this is the jetsurf.yaml
    folder that mostly works for gas turbine and jet engine models. For backward
    compatibility, if not found there, GSPy will look for jetsurf.yaml in the
    \data\ folder in the GSPy root.
- Architecture
  * A GSPy model now is an object of class TSystem_Model. A project model script
    now must instantiate a TSystem_Model object and then call the
    methods simular to the earlier version main program functions for configuring
    and running the model.
  * The Ambient model object class now embedded in TSystem_Model. Default station
    number for ambient is 'a'. Change if using
    <system_model>.ambient.set_station_nr if desired (e.g. to comply to AS755).
  * Note that this means the inlet entry gas path station must now be different
    from the ambient station. Standard would be station 1 (or '010') and 2
    (or '020') for inlet gas path entry and exit.
  * Note that the "station number" does not have to be a number, ASCII strings
    composed of any combination of alphanumering characters are allowed.
    A string like '000' is perfectly valid as an AS755 station number.
    Also, for example 'a', 'thr', 'exit1' etc. all are allowed.
- Thermodynamic model
  * Combustor Cantera equilibrium calculations made more robust using auto, then
    'vcs' and 'gibbs' method if subsequently if auto fails to converge (e.g. like
    at high >2000 K temperatures)
- Many renamings and refactorings to more pythonic coding style.
- The class_hierarchy.md file in de \docs folder now show the object orientated
  architecture with the component model classes.
- Utility scripts
  In the projects\utils folder there are 2 utility scripts:
  * file_structure_to_text.py: for generating a file structure diagram of
    a folder path. This may be convenient for generating the folder
    structure of a project. In the script it is set to generate it for
    the turbojet project. The resulting 'tree_structure.md' file is
    created in the specific project folder.
  * class_diagram.py: for generating object class diagrams from a python
    source code folder. The script is per default configured to generate
    the class hierarchy diagram of the .\src\gspy\core folder.
    The resulting class_diagram.md file is created in the .\docs folder.
- Shaft component classes are introduced to model components producing or
  consuming power and/or torque, like electric motors, generators etc.
  Class hierarchy:
  TComponent
    └── TShaftComponent
        ├── TOneShaftComponent
        │   ├── TLoad
        │   └── TMotor
        │       └── TStarterGenerator
        └── TTwoShaftComponent
  TTwoShaftComponent is an abstract class to e.g. derive models for gearboxes,
  couplings, clutches etc.
  * A turbojet sample model (turbojet_PWofftakes.py) demonstrates the usage
    of power delivery and extraction enable the object in the model to test
    the usage.
  * A basic starter-generator component model demonstrates power delivery
    and power extraction modes, see comments and docstrings in the class for
    usage.

### GSPy v1.7.0.0                                                     17-03-2026
--------------------------------------------------------------------------------
### Release
--------------------------------------------------------------------------------
- Release and maintenance branch for 1.7.0

### GSPy v1.6.0.9                                                     13-03-2026
--------------------------------------------------------------------------------
### Improvements
--------------------------------------------------------------------------------
- Maps can now be plotted with the β-lines and labels, see the demo_plot*.py
  files in ./projects/map_viewer
- Nc label in map plot optionally displays the referred Nc or the actual RPM not
  referred to the design spool speed
- Created a basic test script for automatic testing of the results; now after each
  version update, the output data can be compared for validation

### GSPy v1.6.0.8                                                     12-03-2026
--------------------------------------------------------------------------------
### Improvements
--------------------------------------------------------------------------------
- Functionality added to specify targets and free variables for design point
  simulation (Run_DP_simulation method).
  See example project turbojet_DPeq.py.
- Code in turbine.py made more consistent: thermodynamic power = 'DHW',
  mechanical power (after mechanical losses / Etamech) = 'PW'.

### GSPy v1.6.0.7                                                     11-03-2026
--------------------------------------------------------------------------------
### Bug fixes
--------------------------------------------------------------------------------
- Bug in turbinemap.py call to contour functions fixed: self.EtaArrayValues
  must not be transposed.

--------------------------------------------------------------------------------
### Improvements
--------------------------------------------------------------------------------
- equilibrate not anymore used after mixing cross flow (causes Cantera to
  get stuck outside gas properties T range; and also does not have any effect
  at the relatively low temperatures typically in a turbofan exit).

### GSPy v1.6.0.6                                                     11-03-2026
--------------------------------------------------------------------------------
### New features
--------------------------------------------------------------------------------
- Added an ambient class in src/gspy/core to override standard ambient conditions
  class. This class extends the ambient conditions to use the SAE AS210 standard
  "Definition of Commonly Used Day Types (Atmospheric Ambient Temperature
  Characteristics Versus Pressure Altitude)".
- Model projects/turbojet/turbojet ambient_AS210.py demonstrates the usage of non-
  ISA atmospheric models.
- Additional project to plot output parameters versus station number
- Added gas turbine models incorporating SAE AS755 (Aircraft Propulsion System
  Performance Station Designation) and naming from AS5571 (Gas Turbine Engine
  Performance Presentation and Nomenclature For Object-Oriented Computer Programs).
- Plotting project to plot the T-S diagram of air.

--------------------------------------------------------------------------------
### Improvements
--------------------------------------------------------------------------------
- Speed parameter labels in map plots are now referred to the design speed, the
  speed line at design has value 1.0.

### GSPy v1.6.0.5                                                     10-02-2026
--------------------------------------------------------------------------------
### Improvements
--------------------------------------------------------------------------------
- numpy updated to version 2.4.2
- scipy updated to version 1.17.0
- code labeled 1.6.0.5 updated to comply to these newer versions, specifically
  statements requiring float scalars (needed conversion from 1-element NumPy
  arrays to scalars, mostly in Cantera tuple assignment statements).

### GSPy v1.6.0.4                                                     24-01-2026
--------------------------------------------------------------------------------
### Improvements
--------------------------------------------------------------------------------
- Plotting of the Nc values in the dual subplot off design map characteristics

### GSPy v1.6.0.3                                                     23-01-2026
--------------------------------------------------------------------------------
### Improvements
--------------------------------------------------------------------------------
- Improved map handing and small fixes

### GSPy v1.6.0.2                                                     23-01-2026
--------------------------------------------------------------------------------
### Improvements
--------------------------------------------------------------------------------
- Improved map_viewer project;
  - map_plotter.py
    - added docstrings describing the usage and class
  - map plotting demo files
    - added docstrings/comments describing the generated maps
    - implemented map_suffix example usage
  - updated the map classes to default use arguments with value False to prevent
    accidental setting of plot options to True (fixing a bug where the title
    displayed "(scaled to DP)" where in fact it was not scaled)

### GSPy v1.6.0.1                                                     23-01-2026
--------------------------------------------------------------------------------
### Bug fixes
--------------------------------------------------------------------------------
- Bug fix removes spurious accidental added text to graph

### GSPy v1.6.0.0                                                     22-01-2026
--------------------------------------------------------------------------------
### Improvements
--------------------------------------------------------------------------------
- Cf factor added to the fan model for off-design duct-core cross flow correction
  cf < 1 :  cross flow between duct/bypass and core sections (with different maps
            used for compression calculation)
            for cf = 0 : cross flow between fan exit and splitter, we need to mix
            some of the core flow with bypass or
            vice versa, so that the flow distribution is corresponding to the
            off-design bypass ratio
            0 < cf < 1 : the cf factor determines the fraction of the cross flow
            actually compressed by the map
            of 'the other side' (1-cf) * cross flow
  cf = 1 :  no cross flow between duct/bypass and core sections (with different
            maps used for compression calculation)
            the flow distribution to core and duct/bypass maps remains
            corresponding to design BPR (BPRdes)
  default value for cf = 1 : most stable, assuming the duct-core dividing stream
  line remains the same as with BPRdes
- Added multi-map functionality (for variable geometry turbomachinery):
  instead of a map file name, a structure with a design variable geometry
  parameter (vg_angle_des) and a dictionary with maps corresponding to different
  variable geometry control parameter values (vg_angle) are implemented in the
  abtract TTurboComponent class.
  This functionality has resulted in several changes in the map handling code,
  keeping the existing projects mostly backward compatible.
- A TVG_Control component class has been added.
- A demo project demonstrating the use of the variable geometry function will be
  provided later (waiting for compressor maps without publication restrictions).
- Map plotting code has been improved, expecially for the turbine map.
- PreRun virtual method added to TComponent base class to implement code running
  prior to calling all the Run methods in a system model component list.
- Map reading code made more robust (in case emtpy lines missing between cross
  table blocks in map text file).
- Provisional alternative TAMcontrol class added with separate control over the
  adaptation equation tolerances and matching penalty factors: in AMcontrol_LM.py
  (by Lucas Middendorp).
- Turbine cooling output extended with separate W, T and P at cooling flow
  Out stations.
- map_viewer app added to the projects folder for plotting individual maps, either
  unscaled or scaled using a design point (DP), results from an output csv file or
  manually scaled. An operating curve can also be plotted in the map using csv
  output data.

### GSPy v1.5.0.0                                                     17-12-2025
--------------------------------------------------------------------------------
### New features
--------------------------------------------------------------------------------
- This release introduces the API, a layer between gspy/core and the script is
  created to run models from a script that calls a specific API model based on a
  base model. Inheriting this base model allows for creating a model without the
  need to have knowledge about the gspy/core, other than which options need to be
  added to create a model.
- ./projects/turbojet_api contains a runable script run_api_model.py to
  demonstrate how this works.

### GSPy v1.4.0.0                                                         15-12-2025
- IMPORTANT: you need to update any project / engine model file to comply to the
  new folder structure and other changes. Look at sample model scripts like
  turboject.py!
--------------------------------------------------------------------------------
### New features
--------------------------------------------------------------------------------
- Entirely new folder structure more compliant to Python common practice.
  Changes is the import and other paths.
- file names of component model classes changed
- Option to treat DP and/or map turbomachinery efficiency eta as either isentropic
  (default so far) or polytropic (new) using turbomachinery component
  Polytropic_Eta flag. Set Polytropic_Eta to 1 to treat as polytropic.

### GSPy v1.3.0.1                                                         12-11-2025
--------------------------------------------------------------------------------
### Bug fixes
--------------------------------------------------------------------------------
- Exhaust nozzle model CV affected A throat and thus mass flow capacity of the
  nozzle. Although may be an model option (but requires more code and equations)
  CV is set to only affect thrust which in most cases is more consistent. It is
  advised to use CD instead to control flow capacity (effective vs. geometric
  A throat) which now is not yet implemented.

### GSPy v1.3.0.0                                                         01-11-2025
--------------------------------------------------------------------------------
### Improvements
--------------------------------------------------------------------------------
- Map modifier scaling factors "SF.." added to the TTurboMap class used in the
  TTurbo_Component model class, to modify the map output (Eta, Wc and/or PR).
- Adaptive modelling component class TAMcontrol (f_AMcontrol.py), inheriting
  from TControl. Allows the specification of measurement data with column
  names corresponding to GSPy output names and a number of map modifier scaling
  factors (SF...), the values of which are to be determined by solving the
  thermodynamic model equations together with the measurement value match
  equations. Note that careful attention much be given to the selection of
  measurement parameters and corresponding number of map modifiers as one
  easily creates a system for which there is no solution. multiple solution
  or severe instability problem arise.
  The Measurement data table also is used to set measured ambient conditions
  and power setting variable such as fuel flow Wf.
  Resulting factor are output in the outputdata table. SF.. values 1 mean no
  deviation. See code in TTurboMap for further details.
  Important:
  ___
  ***Note that for professional application, a lot of additional improvements
  considering measurement uncertainty, scatter, solver stability, parameter
  selection, numerical methods will be required.***
  ___

- The turbojet_AM.py model demonstrates the use of TAMcontrol determining
  all 4 turbomachinery scaling factors possible for adapting the model to
  P3, T3, T5 and N1% values at varying operating conditions (Alt, dTs, Mach
  and fuel flow Wf). Input file is Turbojet_AMinput.csv located on the
  input subfolder.
  Have fun :) with it!

### GSPy v1.2.0.0                                                         18-10-2025
--------------------------------------------------------------------------------
### Improvements
--------------------------------------------------------------------------------
- Instead of a generic TExhaust class, we now have a TExhaustNozzle class
  (f_exhaustnozzle.py) for propelling nozzles (jet engines and turboprops)
  and a TExhaustDiffuser class
  (f_exhaustdiffuser) for diffusers for turboshaft engines with a diffuser
  exhaust and a diffuser design pressure ratio (1 - rel. ploss) defined;
  off-design the pressure loss is scaled with (Wc/Wcdes)^2 (constant friction
  factor - 0.5*rho*v^2)
- provisions for turboshaft modelling  added
- FDuct component model class (f_duct.py) now scales off-design point
  pressure loss (1-PR) with (Wc/Wcdes)^2 relative to design pressure loss
  (1-PRdes)
- demo turbojet model added with rotor speed control ("turbojet_Ncontrol.py")
- demo turbofan model added ("turbofan.py"), OD simulation at cruise
  conditions
- demo turbofan model with N1 control added ("turbofan_N1control.py")
- demo 2-spool turboshaft engine model added (turboshaft_2spool.py)
- demo 2-spool turboshaft engine model with compressor bleeds and
  turbine cooling added (turboshaft_2spool_TurbineCooling.py)
- Compressor bleed class added, to be linked to compressor model. Bleed flows
  inherit from TGasPath and therby have there own unique entry and exit
  station numbers. Bleed flows are extracted from the gas path at user
  specified pressure level between inlet and exhaust. Conservation of mass
  and enthalpy is maintained.
- Turbine cooling flow class added, to be linked to turbine model and taking
  air from bleed flows by number and station numbers. Cooling flow
  inherit from TGasPath and therby have there own unique entry and exit
  station numbers. Entry into turbine is defined by a pressure factor (how
  much contributed to expansion work, consuming pumping power due to
  increase in kinetic energy when in rotating blades, also claiming effictive
  flow capacity in the turbine depending on W_tur_eff_fraction factor).
  Conservation of mass and enthalpy is maintained.
- Generic X-nY plot routine added in f_system to be called at end of simulation
  plotting n Y parameters to a single X axis parameter.
- Generic routine for exporting output table dataframe to CVS file.

### GSPy v1.1.0.0                                                         14-07-2025
--------------------------------------------------------------------------------
### Improvements
--------------------------------------------------------------------------------
- provisions for scheduling specific parameters during OD simulation
  via TControl component class (f_control.py) using extra equations. The
  equation component added to the component using the schedule and adding the
  equation (e.g. TCombustor). The parameter to be scheduled is specified in the
  TControl component instantiation (creation) call.

### GSPy v1.0.0.0        (first release)                                  14-06-2025
--------------------------------------------------------------------------------

********************************************************************************
## 3. HINTS
********************************************************************************

********************************************************************************
## 4. KNOWN ISSUES
********************************************************************************

********************************************************************************
## 5. OTHER
********************************************************************************

********************************************************************************
## 6. GSPy DEVELOPMENT TEAM
********************************************************************************

| Wilfried Visser | Oscar Kogenhop|
| ------ | ------ |
| wvisser@xs4all.nl<br>Faculty of Aerospace Engineering / Propulsion and Power<br>Delft University of Technology<br>Kluyverweg 1<br>2629 HS Delft<br>The Netherlands | oscar.kogenhop@epcor.nl<br><br>EPCOR B.V.<br>Bellsingel 41<br>1119 NT Schiphol-Rijk<br>The Netherlands |
