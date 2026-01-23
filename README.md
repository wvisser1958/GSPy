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
