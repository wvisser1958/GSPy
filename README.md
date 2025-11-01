# gsppysim
GSPy Python propulsion and power system performance modelling and simulation tool

Authors
  Wilfried Visser
  Oscar Kogenhop

--------------------------------------------------------------------------------
CONTENTS:
---------------------------------
1. License
2. Version history
3. Hints
4. Known issues
5. Other
---------------------------------

********************************************************************************
1. LICENSE
********************************************************************************

This project is licensed under the Apache License 2.0
See the LICENSE file for details.

********************************************************************************
2. VERSION HISTORY
********************************************************************************
GSPy v1.3.0.0                                                         01-11-2025
--------------------------------------------------------------------------------
Improvements
--------------------------------------------------------------------------------
* Map modifier scaling factors "SF.." added to the TTurboMap class used in the
  TTurbo_Component model class, to modify the map output (Eta, Wc and/or PR).
* Adaptive modelling component class TAMcontrol (f_AMcontrol.py), inheriting
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
  ==========================================================================
  Note that for professional application, a lot of additional improvements
  considering measurement uncertainty, scatter, solver stability, parameter
  selection, numerical methods will be required.
  ==========================================================================
* The turbojet_AM.py model demonstrates the use of TAMcontrol determining
  all 4 turbomachinery scaling factors possible for adapting the model to
  P3, T3, T5 and N1% values at varying operating conditions (Alt, dTs, Mach
  and fuel flow Wf). Input file is Turbojet_AMinput.csv located on the
  input subfolder.
  Have fun :) with it!

GSPy v1.2.0.0                                                         18-10-2025
--------------------------------------------------------------------------------
Improvements
--------------------------------------------------------------------------------
* Instead of a generic TExhaust class, we now have a TExhaustNozzle class
  (f_exhaustnozzle.py) for propelling nozzles (jet engines and turboprops)
  and a TExhaustDiffuser class
  (f_exhaustdiffuser) for diffusers for turboshaft engines with a diffuser
  exhaust and a diffuser design pressure ratio (1 - rel. ploss) defined;
  off-design the pressure loss is scaled with (Wc/Wcdes)^2 (constant friction
  factor * 0.5*rho*v^2)
* provisions for turboshaft modelling  added
* FDuct component model class (f_duct.py) now scales off-design point
  pressure loss (1-PR) with (Wc/Wcdes)^2 relative to design pressure loss
  (1-PRdes)
* demo turbojet model added with rotor speed control ("turbojet_Ncontrol.py")
* demo turbofan model added ("turbofan.py"), OD simulation at cruise
  conditions
* demo turbofan model with N1 control added ("turbofan_N1control.py")
* demo 2-spool turboshaft engine model added (turboshaft_2spool.py)
* demo 2-spool turboshaft engine model with compressor bleeds and
  turbine cooling added (turboshaft_2spool_TurbineCooling.py)
* Compressor bleed class added, to be linked to compressor model. Bleed flows
  inherit from TGasPath and therby have there own unique entry and exit
  station numbers. Bleed flows are extracted from the gas path at user
  specified pressure level between inlet and exhaust. Conservation of mass
  and enthalpy is maintained.
* Turbine cooling flow class added, to be linked to turbine model and taking
  air from bleed flows by number and station numbers. Cooling flow
  inherit from TGasPath and therby have there own unique entry and exit
  station numbers. Entry into turbine is defined by a pressure factor (how
  much contributed to expansion work, consuming pumping power due to
  increase in kinetic energy when in rotating blades, also claiming effictive
  flow capacity in the turbine depending on W_tur_eff_fraction factor).
  Conservation of mass and enthalpy is maintained.
* Generic X-nY plot routine added in f_system to be called at end of simulation
  plotting n Y parameters to a single X axis parameter.
* Generic routine for exporting output table dataframe to CVS file.

GSPy v1.1.0.0                                                         14-07-2025
--------------------------------------------------------------------------------
Improvements
--------------------------------------------------------------------------------
* provisions for scheduling specific parameters during OD simulation
  via TControl component class (f_control.py) using extra equations. The
  equation component added to the component using the schedule and adding the
  equation (e.g. TCombustor). The parameter to be scheduled is specified in the
  TControl component instantiation (creation) call.

GSPy v1.0.0.0        (first release)                                  14-06-2025
--------------------------------------------------------------------------------
Fixed
--------------------------------------------------------------------------------
*

--------------------------------------------------------------------------------
Improvements
--------------------------------------------------------------------------------
*

GSPy Development Team
Wilfried Visser
wvisser@xs4all.nl
Faculty of Aerospace Engineering / Propulsion and Power
Delft University of Technology
Kluyverweg 1
2629 HS Delft
The Netherlands

Oscar Kogenhop
oscar.kogenhop@epcor.nl
EPCOR B.V.
Bellsingel 41
1119 NT Schiphol-Rijk
The Netherlands

