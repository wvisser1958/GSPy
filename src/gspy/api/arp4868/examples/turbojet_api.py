"""
    Example configuration of a turbojet model file for use by an the GSPy API
"""

# Required system model import
from gspy.core.system import TSystemModel

# Optional model component imports used in (gas turbine) model
from gspy.core.inlet import TInlet
from gspy.core.compressor import TCompressor
from gspy.core.control import TControl
from gspy.core.turbine import TTurbine
from gspy.core.duct import TDuct
from gspy.core.combustor import TCombustor
from gspy.core.exhaustnozzle import TExhaustNozzle

def build_model(project_root=None):
    model = TSystemModel("Turbojet", model_file = __file__ if project_root is None else project_root)

    # Override ambient object station number to with new station string
    model.ambient.set_station_nr('000')
    
    fuelcontrol = TControl(model, 'Fcontrol', '',
                           0.38,                    # design point (DP) input

                           # off design control input ranging from 0.38 down to 0.8 with steps of -0.01
                           # 0.38, 0.08, -0.01,       # off design (OD) input Wf : starting value, end value and step value OR alternatively:
                           # 1235.9, 835.9, -25,      # off design (OD) input Tt4: starting value, end value and step value OR alternatively:
                           0.30, None, None,        # off design (OD) input: single input value

                           None                     # OD control parameter name: must be an output present in the output table
                                                    # if None: the component using it directly takes the value
                                                    # if specified with parameter name, an equation is added forcing the parameter to match the input values
                                                    # and the component using it makes it's input a free state variable
                                                    # e.g. specify 'N1' to control rotor speed, with the combustor turning the Wf into a free state variable

                                                    # example for N1 rotor speed control:
                                                    # FuelControl = TControl('Ncontrol', '', 0.38, 100, 60, -5, 'N1%')

                                                    # EGT (T5) control example:
                                                    # FuelControl = TControl('EGTcontrol', '', 0.38, 1020, 820, -50, 'T5')
                                                    # note that for a gas turbine, this method may well become instable at lower power setting due to multiple solutions at same T5
                           )

    # Generic gas turbine components
    inlet1   = TInlet(model,        # owning system model object
                      'Inlet1',     # component name
                      '',           # map file name
                      None,         # optional control component
                      '010', '020', # station nr in and out (station strings are also allowed, e.g. '010' and '020')
                      19.9,         # design inlet mass flow
                      1             # design pressure ratio (PR = 1 - Ploss_relative)
                      )

    compressor1 = TCompressor(model,            # owning system model object
                              'Compressor1',    # component name
                              'compmap.map' ,   # map file name
                              None,             # optional control component
                              '020', '030',     # station nr in and out
                              1,                # shaft id, strings are allowed as well (e.g. 'gg'), but for simplicity we use integers here
                              16540,            # design rpm
                              0.825,            # design efficiency
                              1,                # map design Nc (for scaling)
                              0.75,             # map design Beta (for scaling)
                              6.92,             # design pressure ratio
                              'GG',             # speed option
                              None              # option list of bleeds
                              )

    combustor1 = TCombustor(model,          # owning system model object
                            'Combustor1',   # component name
                            '',             # map file name             # for future use of a combustor efficiency map

                            # OD fuel input from FuelControl
                            fuelcontrol,    # fuel control component    # fuel control component setting fuel flow depending on OD / PointTime point

                            '030', '040',   # station nr in and out

                            0.38,           # Design point (DP) fuel flow Wfdes
                            None,           # Texit design  - if specified (not None) Wfdes will be calculated from Texit,
                            # 0.30,           # Design point (DP) fuel flow Wfdes
                            # 1235.9,         # Texit design  - if specified (not None) Wfdes will be calculated from Texit,
                                            #               - Wfdes is then taken as starting value for iteration

                            1,              # design pressure ratio, use to specify rel. pressure loss ploss (PR = (1 - ploss)/Pin)
                            1,              # design combustor efficiency
                            None,           # Fuel temperature K           # If None, then Tfuel is assumed to be equal to temperature of entry air flow

                            # For the fuel properties specification there are 2 options:
                            #     1:        virtual fuel with unknown composition:
                            #               specify LHV, H/C ratio, O/C ratio and Tfuel. GSPy will then do the species bookkeeping, determine the exit
                            #               gas composition based in inlet air/gas composition, H/C, O/C
                            #               and calculated the exit temperature from chemical equilibrium
                            #     2:        specify the fuel composition using Cantera composition string like
                            #                   'NC12H26:1' (dodecane),
                            #                   'CH4:9, N2:1' (mixture of CH4 and N2 in ratio 9:1 by mass)
                            #                   or 'CH4:5, C2H6:1' for example, and fuel temperature
                            43031,          # LHV, required if Fuelcomposition is None
                            1.9167,         # HCratio
                            0,              # OCratio
                            None,           # Fuelcomposition  alternative: take 'NC12H26:1' for a jet fuel surrogate for example
                            None            # Cross flow area to calculate fundamental pressue loss
                            )
                            # wxample with Texit as input:
                            # TCombustor(model, 'combustor1',  '', None,           3, 4, 0.38, 1200, 1, 1,

                            # fuel specification examples:
                            # fuel specified by LHV, HCratio, OCratio, Tfuel = None means Tfuel equal to combustor entry temperature:
                                # None,      43031, 1.9167, 0, ''),

                            # fuel specified by Fuel composition (by mass)
                                # NC12H26 = Dodecane ~ jet fuel
                                # 300,      None, None, None, 'NC12H26:1'),

                            # fuel specified by Fuel temperature and pure H2 fuel
                                # 288.15,      None, None, None, 'H2:1'),

                            # fuel mixtures
                            # fuel specified by Fuel temperature and fuel mix composition (by mass)
                            #    288.15,      None, None, None, 'CH4:5, C2H6:1')

    turbine1 =    TTurbine(model,           # owning system model object
                           'Turbine1',      # component name
                           'turbimap.map',  # map file name
                           None,            # optional control component
                           '040', '050',    # station nr in and out
                           1,               # shaft nr
                           16540,           # design point (DP) rpm
                           0.88,            # design point (DP) efficiency
                           1,               # map design Nc (for scaling)
                           0.50943,         # map design Beta (for scaling)
                           0.99,            # design mechanical efficiency (standard isentropic, Polytropic_Eta = 0)
                           'GG',            # turbine type 'GG' = gas generator delivering all power required by the shaft
                                            #              'PT' = free power turbine or turbine driving power output shaft
                           None             # optional cooling flows object list
                           )
    # option for working with polytropic efficiency: uncomment next line
    # turbine1.Polytropic_Eta = 1

    duct1    = TDuct(       model,          # owning system model object
                            'ExhDuct',      # component name
                            '',             # optional map file name
                            None,           # optional control component
                            '050', '070',   # station nr in and out
                            1.0             # design pressure ratio, use to specify rel. pressure loss ploss (PR = (1 - ploss)/Pin)
                            )

    exhaustnozzle = TExhaustNozzle(model,               # owning system model object
                                   'ExhaustNozzle',     # component name
                                   '',                  # option map file name
                                   None,                # optional control component
                                   '070', '080', '090', # station nr of entry, throat and exit  (throat and exit only different fo con-di nozzle)
                                                        # con-di nozzle model still to be implemented
                                   1,                   # design CX thrust coefficient
                                   1,                   # design CV velocity coefficient
                                   1                    # design CD discharge coefficient
                                   )

    # create a turbojet system model
    model.define_comp_run_list(  fuelcontrol,
                                 inlet1,
                                 compressor1,
                                 combustor1,
                                 turbine1,
                                 duct1,
                                 exhaustnozzle)

    # Return the model for use by the API
    return model
