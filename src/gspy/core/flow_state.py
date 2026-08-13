from __future__ import annotations
import math
import cantera as ct
import gspy.core.constants as c
from scipy.optimize import root_scalar
from scipy.optimize import root
import gspy.core.utils as fu

class TFlowState:
    """
    Gas-path station condition with:
      - gas_q: Cantera Quantity containing the full GAS phase, including H2O vapor
      - m_total_water: total water inventory [kg] = vapor + liquid
      - m_dry: dry-gas mass [kg] = all gas species except H2O vapor

    Only LIQUID water is outside the Cantera gas phase.
    Water vapor always remains inside gas_q.
    """

    # T_WATER_TRIPLE = 273.16
    # T_WATER_CRITICAL = 647.096
    # MW_H2O = 18.01528e-3

    LIQ_ABS_TOL = 1e-9
    LIQ_REL_TOL = 1e-4   # 0.01% of water inventory; adjust to e.g. 1e-3 or 1e-5 if needed
    RH_TOL = 1e-8    
    
    WATER_TOL = 1e-12

    def_debug_flash: bool = False

    def __init__(self,
                 gas: ct.Solution,
                 gas_mass: float,
                 station_nr: str,

                # faster 2.11
                 *,
                #  i_H2O: int,

                 m_total_water: float | None = None,
                 m_liq: float = 0.0,

                # new single flag enable_liquid_water
                            #  enable_liquid_model: bool = def_enable_liquid_model,   # if True allow condensation / evaporation model
                            #  force_gas_only: bool = def_force_gas_only,             # if True: set m_total_water = m_vap, m_liq = 0   
                            # In practice, force_gas_only is the strongest 
                            # shortcut for gas turbines, as it allows skipping 
                            # all liquid model logic and just treating water 
                            # as a gas species that can be present up to saturation. 
                            # So it's recommended to set force_gas_only=True for 
                            # compressor and combustor conditions, and enable_liquid_model=True 
                            # but force_gas_only=False for ambient inlet conditions if you want to track humidity there.
                 enable_liquid_water: bool = False,

                 debug_flash: bool = def_debug_flash):
        # self.mechanism = mechanism

        # Recommended use of enable_liquid_model and force_gas_only for gas turbines:
        # At inlet (ambient)
        # enable_liquid_model = True
        # Downstream (compressor / combustor)
        # force_gas_only = True

        # self.enable_liquid_model = enable_liquid_model
        # self.force_gas_only = force_gas_only
        self.enable_liquid_water = enable_liquid_water
        self.debug_flash = debug_flash

        self.gas_q = ct.Quantity(gas, mass=gas_mass)

        # faster 2.11
        #        self.i_H2O = i_H2O
        self.i_H2O = int(self.gas_q.phase.species_index("H2O"))

        self.velocity = None

        self.station_nr = str(station_nr)

        # set Ps, Ts, Mach etc....
        self._set_static_equal_total()

        # scratch objects for fast residual evaluations
        # self._scratch_gas = ct.Solution(self.mechanism)
        # self._scratch_water = ct.Water()
        self._scratch_water = None   # create when needed only to save initialization time and memory  

        self.m_dry = gas_mass * (1.0 - self._gas_h2o_mass_fraction())

        # Cannot specify liquid water in gas-only mode
        if (not self.enable_liquid_water) and (m_liq > self.LIQ_ABS_TOL):
            raise ValueError(
                "Conflicting TGaspathCondition initialization: "
                "m_liq > 0 was specified while enable_liquid_water=False."
            )

        if m_total_water is None:
            self.m_total_water = (
                self.W_gas * self._gas_h2o_mass_fraction()
                + float(m_liq)
            )
        else:
            self.m_total_water = float(m_total_water)

        # Final consistency check for gas-only mode
        if not self.enable_liquid_water:
            m_vap = self.W_gas * self._gas_h2o_mass_fraction()

            if abs(self.m_total_water - m_vap) > self.LIQ_ABS_TOL:
                raise ValueError(
                    "Conflicting TGaspathCondition initialization: "
                    "enable_liquid_water=False but total water inventory "
                    "differs from gas-phase H2O inventory."
                )
                
    # ------------------------------------------------------------------
    # basic forwarding / compatibility
    # ------------------------------------------------------------------
    # forward all unknown attributes to gas_q, so that we can access things like .species_names, .mechanism, etc. directly on the TGaspathCondition object
    # note that getattr is slow so we should avoid accessing attributes that aren't on TGaspathCondition in performance-critical code paths
    def __getattr__(self, name):
        try:
            return getattr(self.gas_q, name)
        except AttributeError:
            raise AttributeError(
                f"{type(self).__name__!s} object has no attribute {name!r}"
            ) from None

    @property
    def gas(self):
        return self.gas_q.phase

    @property
    def T(self):
        return self.gas_q.T

    @property
    def P(self):
        return self.gas_q.P

    @property
    def X(self):
        return dict(zip(self.gas_q.species_names, self.gas_q.X))
        
    @property
    def Y(self):
        return dict(zip(self.gas_q.species_names, self.gas_q.Y))        

    @property
    def W_gas(self):
        return self.gas_q.mass
    
    @W_gas.setter
    def W_gas(self, value):
        liq_old = self.m_liq
        self.gas_q.mass = float(value)
        self.m_dry = self.W_gas * (1.0 - self._gas_h2o_mass_fraction())

        #  old code
        # self.m_total_water = self.m_vap + liq_old
        # # if self.force_gas_only:
        # if not self.enable_liquid_water:
        #     self.m_total_water = self.m_vap

        # more efficient:
        if self.enable_liquid_water:
            self.m_total_water = self.m_vap + liq_old
        else:
            self.m_total_water = self.m_vap


    @property
    def W(self):
        return self.W_gas + self.m_liq

    @W.setter
    def W(self, value):
        # this will set W_gas and m_liq, but not m_total_water, which is set in the W_gas setter
        self.W_gas = float(value) - self.m_liq

    @property
    def Wc(self):
        return self.W_gas * fu.GetFlowCorrectionFactor(self)

    @property
    def m_vap(self):
        mv = self.W_gas * self._gas_h2o_mass_fraction()
        if self.m_total_water - mv <= self.LIQ_ABS_TOL:
            return self.m_total_water
        return mv

    @property
    # m_liq error at RH=100 problem fix:
    # def m_liq(self):
    #     m = self.m_total_water - self.m_vap
    #     return 0.0 if m <= self.LIQ_ABS_TOL else m
    def m_liq(self):
        m = self.m_total_water - self.m_vap
        tol = max(
            self.LIQ_ABS_TOL,
            self.LIQ_REL_TOL * max(self.m_total_water, self.W_gas, 1e-30),
        )
        return 0.0 if m <= tol else m

    # for TInlet: scale mass up from 1 kg (TAmbient) to inlet gas mass flow
    def scale_mass(self, scale_value: float):
        f = float(scale_value)

        if f < 0.0:
            raise ValueError("scale_value must be >= 0")

        self.gas_q.mass *= f    # this sets W_gas, which is used to compute m_vap and m_liq
        self.m_dry *= f
        self.m_total_water *= f # now m_total_water = m_vap + m_liq, so this is consistent with the scaled W_gas and m_liq 
                                # m_vap is calculated from the H2O fraction in the W_gas (or gas_q.mass) 
                                # with m_total_water set, now m_liq is also defined

        # no need to scale W, since W is derived from W_gas and m_liq
        # self.W *= f    
        # self.W = f    

        return self

    @property
    def has_condensed_water(self):
        return self.m_liq > self.LIQ_ABS_TOL

    @property
    def x_H2O_gas(self):
        return self.X.get("H2O", 0.0)

    @property
    def h_gas(self):
        return self.gas_q.enthalpy_mass

    @property
    def s_gas(self):
        return self.gas_q.entropy_mass

    @property
    def H_total(self):
        if (not self._use_liquid_model()) or (self.m_liq < self.LIQ_ABS_TOL):
            return self.gas_q.enthalpy
        return self.gas_q.enthalpy + self.m_liq * self._sat_liquid_h(self.T)

    @property
    def S_total(self):
        if not self._use_liquid_model() or (self.m_liq < self.LIQ_ABS_TOL):
            return self.gas_q.entropy
        return self.gas_q.entropy + self.m_liq * self._sat_liquid_s(self.T)

    # not
    # @property
    # def p_saturation(self):
    #     if self.T >= c.T_WATER_CRITICAL:
    #         return self.P
    #     if self.T <= c.T_WATER_TRIPLE:
    #         raise ValueError(
    #             f"T={self.T:g} K is below the liquid-water triple point for this model."
    #         )
    #     w =self._water()
    #     w.TQ = self.T, 1.0
    #     return w.P_sat

    @property
    def RH_gas(self):
        if not self._has_water():
            return 0.0
        x_sat = self._sat_water_mole_fraction(self.T, self.P)
        if 0.0 < x_sat < 1.0:
            return 100.0 * self.x_H2O_gas / x_sat
        return 0.0

    # ------------------------------------------------------------------
    # fast-path logic
    # ------------------------------------------------------------------

    def _has_water(self):
        return self.m_total_water > self.WATER_TOL

    def _use_liquid_model(self):
        # return self.enable_liquid_model and (not self.force_gas_only) and self._has_water()
        return self.enable_liquid_water and self._has_water()


    def disable_liquid_model(self, collapse: bool = False):
        """
        Disable separate liquid-water tracking.

        After calling this method:

            enable_liquid_water = False

        and the object behaves as a gas-only thermodynamic state. No further
        condensation or evaporation calculations are performed, improving
        computational performance.

        Parameters
        ----------
        collapse : bool, default=False

            False
                Disable the liquid-water model only if no liquid water is
                currently present (m_liq <= LIQ_TOL).

                If liquid water is still present, a RuntimeError is raised.
                This is useful as a consistency check to detect unexpected
                liquid water in components where it should not exist.

            True
                Convert all remaining liquid water into gas-phase H2O,
                conserving total water mass and total flow mass, then disable
                the liquid-water model.

                This option should be used whenever the physics guarantees
                that any remaining liquid water will evaporate before further
                calculations are performed.

        Typical usage
        -------------
        Ambient / inlet with possible fog or rain:
            enable_liquid_water = True

        Compressor with wet compression:
            enable_liquid_water = True

        Combustor:
            disable_liquid_model(collapse=True)
            # Remaining liquid water is assumed to evaporate before or during
            # combustion.

        Turbine inlet:
            Liquid model already disabled.

        Turbine, ducts, nozzles:
            disable_liquid_model(collapse=False)
            # Simply disable liquid tracking for maximum performance.
            # Raises an exception if liquid water unexpectedly remains.

        Recuperator:
        compressor
        ↓
        combustor
        ↓
        turbine
        ↓
        recuperator

        You know the turbine exit is 900 K.
        Therefore: m_liq == 0 Always.
        So the recuperator can simply do:
        self.fs_in.disable_liquid_model(collapse=False)
        and from then on all subsequent property setters use the fast gas-only path.            

        Notes
        -----
        With collapse=True, the gas mass increases by the evaporated liquid
        mass and the gas composition is updated so that the liquid water is
        converted into gas-phase H2O. Mass is therefore conserved.

        With collapse=False, no thermodynamic state is modified; only liquid
        tracking is disabled. This is therefore only valid if no liquid water
        is present.
        """
        if collapse:
            m_liq_old = self.m_liq

            if m_liq_old > self.LIQ_ABS_TOL:
                # Add liquid water to gas phase as H2O vapor
                m_gas_old = self.gas_q.mass
                m_gas_new = m_gas_old + m_liq_old

                Y_old = self.gas_q.Y.copy()
                # faster 2.11
                # i_h2o = self.gas_q.species_index("H2O")

                Y_new = Y_old * (m_gas_old / m_gas_new)
                # faster 2.11
                # Y_new[i_h2o] += m_liq_old / m_gas_new
                Y_new[self.i_H2O] += m_liq_old / m_gas_new

                T = self.T
                P = self.P

                self.gas_q.TPY = T, P, Y_new
                self.gas_q.mass = m_gas_new

            self.enable_liquid_water = False
            self.m_total_water = self.gas_q.mass * self._gas_h2o_mass_fraction()

            if hasattr(self, "_m_vap"):
                self._m_vap = self.m_total_water
            if hasattr(self, "_m_liq"):
                self._m_liq = 0.0

        else:
            if self.m_liq > self.LIQ_ABS_TOL:
                raise RuntimeError(
                    f"Cannot disable liquid model while liquid water is present at station {self.station_nr}. "
                    "Use collapse=True to convert liquid water to gas-phase H2O."
                )

            self.enable_liquid_water = False

    def maybe_disable_liquid_model(self, T_threshold=700.0):
        if self.T >= T_threshold and self.m_liq <= self.LIQ_ABS_TOL:
            self.disable_liquid_model(collapse=True)

    # ------------------------------------------------------------------
    # constructors
    # ------------------------------------------------------------------
    @classmethod
    def create_empty(cls, gas, station_nr: str, 
                     *,
                     enable_liquid_water = False):
        # gas = ct.Solution(mechanism)
        return cls(gas=gas, gas_mass=1.0, station_nr=station_nr, enable_liquid_water = enable_liquid_water)

    @classmethod
    def from_RH(cls, gas: ct.Solution, gas_mass: float, station_nr: str, 
                *,
                T: float, P: float,
                RH: float, dry_X: dict,
                # enable_liquid_model: bool = def_enable_liquid_model,
                # force_gas_only: bool = def_force_gas_only,
                enable_liquid_water: bool = False,
                debug_flash: bool = def_debug_flash):
        obj = cls(
            gas=gas,
            gas_mass=gas_mass,
            station_nr=station_nr,
            # i_H2O=i_H2O,
            m_liq=0.0,
            # enable_liquid_model=enable_liquid_model,
            # force_gas_only=force_gas_only,
            enable_liquid_water=enable_liquid_water,
            debug_flash=debug_flash,
        )
        obj._initialize_humidity(
            mode="RH",
            value=RH,
            T=T,
            P=P,
            dry_comp=dry_X,
            comp_basis="X",
        )
        return obj

    @classmethod
    def from_vol_pct(cls, gas: ct.Solution, gas_mass: float, station_nr: str, 
                     *,
                     # i_H2O: int,
                     T: float, P: float,
                     H2O_vol_pct: float, dry_X: dict,
                     enable_liquid_water: bool = False,
                     debug_flash: bool = def_debug_flash):
        obj = cls(
            gas=gas,
            gas_mass=gas_mass,
            station_nr=station_nr,
            # i_H2O=i_H2O,
            m_liq=0.0,
            # enable_liquid_model=enable_liquid_model,
            # force_gas_only=force_gas_only,
            enable_liquid_water=enable_liquid_water,
            debug_flash=debug_flash,
        )
        obj._initialize_humidity(
            mode="vol_pct",
            value=H2O_vol_pct,
            T=T,
            P=P,
            dry_comp=dry_X,
            comp_basis="X",
        )
        return obj

    @classmethod
    def from_mass_pct(cls, gas: ct.Solution, gas_mass: float, station_nr: str, 
                      *,
                    #   i_H2O: int,  
                      T: float, P: float,
                      H2O_mass_pct: float, dry_Y: dict,
                      enable_liquid_water: bool = False,
                      debug_flash: bool = def_debug_flash):
        obj = cls(
            gas=gas,
            gas_mass=gas_mass,
            station_nr=station_nr,
            # i_H2O=i_H2O,
            m_liq=0.0,
            enable_liquid_water=enable_liquid_water,
            debug_flash=debug_flash,
        )
        obj._initialize_humidity(
            mode="H2O_mass_pct",
            value=H2O_mass_pct,
            T=T,
            P=P,
            dry_comp=dry_Y,
            comp_basis="Y",
        )
        return obj

    def copy_from(self, other: "TFlowState", new_station_nr: str = None, scale_W: float = 1.0,
                  overrule_enable_liquid_water = None) -> "TFlowState":
        self.gas_q.TPX = other.gas_q.T, other.gas_q.P, other.gas_q.X
        self.station_nr = new_station_nr if str(new_station_nr) is not None else str(other.station_nr)

        self.i_H2O=other.i_H2O
        if overrule_enable_liquid_water != None:
            self.enable_liquid_water = overrule_enable_liquid_water
        else:
            self.enable_liquid_water = other.enable_liquid_water

        # these 3 need to be set, the W, m_vap and m_liq properties are derived from them 
        self.gas_q.mass = other.gas_q.mass * scale_W    # this sets W_gas, which is used to compute m_vap and m_liq
        self.m_dry = other.m_dry * scale_W
        self.m_total_water = other.m_total_water * scale_W  # now m_total_water = m_vap + m_liq, so this is consistent with the scaled W_gas and m_liq 
                                                            # m_vap is calculated from the H2O fraction in the W_gas (or gas_q.mass) 
                                                            # with m_total_water set, now m_liq is also defined

        # self.enable_liquid_model = other.enable_liquid_model
        # self.force_gas_only = other.force_gas_only
        self.Ts = other.Ts
        self.Ps = other.Ps
        self.Mach = other.Mach
        self.V = other.V
        self.A = other.A
        self.rhos = other.rhos
        return self

    def mix_same_composition_gas_only(
        self,
        flow1: "TFlowState",
        flow2: "TFlowState",
        *,
        P_out: float,
    ) -> "TFlowState":
        """
        Fast adiabatic mixing of two gas-only streams with identical
        gas-species composition.
        """
        gas1 = flow1.gas_q
        gas2 = flow2.gas_q

        m1 = gas1.mass
        m2 = gas2.mass
        m_out = m1 + m2

        if m_out <= 0.0:
            raise ValueError("Combined gas mass must be positive.")

        H_out = gas1.enthalpy + gas2.enthalpy

        # Set composition only once from flow1.
        self.gas_q.TPY = flow1.T, float(P_out), gas1.phase.Y
        self.gas_q.mass = m_out
        self.gas_q.HP = H_out / m_out, float(P_out)

        self.enable_liquid_water = False
        self.m_dry = flow1.m_dry + flow2.m_dry
        self.m_total_water = flow1.m_total_water + flow2.m_total_water
        self._m_vap = self.m_total_water
        self._m_liq = 0.0

        self._set_static_equal_total()
        return self

    def mix_from(
        self,
        flow1: "TFlowState",
        flow2: "TFlowState",
        *,
        P_out: float | None = None,
        enable_liquid_water: bool | None = None,
    ) -> "TFlowState":
        """
        Mix two TFlowState streams into this TFlowState.

        Conserved quantities
        --------------------
        - Gas-species masses
        - Total water mass, including separately tracked liquid water
        - Total extensive enthalpy
        - Total stream mass

        Pressure
        --------
        Mixing does not determine the outlet pressure. If P_out is omitted,
        the lower inlet pressure is used. This corresponds to throttling the
        higher-pressure stream to the lower pressure before adiabatic mixing.

        Parameters
        ----------
        flow1, flow2
            Inlet flow states.

        P_out
            Outlet pressure [Pa]. Default is min(flow1.P, flow2.P).

        enable_liquid_water
            True:
                The outlet may contain separate liquid water and the final
                state is established with the vapor-liquid HP flash.

            False:
                All inlet water, including liquid water, is treated as
                gas-phase H2O at the outlet.

            None:
                Enable the liquid model if it is enabled for either inlet.

        Returns
        -------
        self
            The mixed outlet state.
        """
        if flow1.gas_q.phase.n_species != flow2.gas_q.phase.n_species:
            raise ValueError(
                "Cannot mix TFlowState objects with different species sets."
            )

        if flow1.gas_q.phase.species_names != flow2.gas_q.phase.species_names:
            raise ValueError(
                "Cannot mix TFlowState objects with different species ordering."
            )

        if P_out is None:
            P_out = min(flow1.P, flow2.P)

        P_out = float(P_out)

        if P_out <= 0.0:
            raise ValueError("P_out must be positive.")

        if enable_liquid_water is None:
            enable_liquid_water = (
                flow1.enable_liquid_water
                or flow2.enable_liquid_water
            )

        enable_liquid_water = bool(enable_liquid_water)

        # Cache all inlet quantities before modifying self. This also allows
        # self to be the same object as flow1 or flow2.
        Y1 = flow1.gas_q.phase.Y.copy()
        Y2 = flow2.gas_q.phase.Y.copy()

        m_gas1 = flow1.gas_q.mass
        m_gas2 = flow2.gas_q.mass

        m_liq1 = flow1.m_liq
        m_liq2 = flow2.m_liq

        m_dry_out = flow1.m_dry + flow2.m_dry
        m_water_out = flow1.m_total_water + flow2.m_total_water

        # The inlet total enthalpies include their liquid-water enthalpy.
        H_target = flow1.H_total + flow2.H_total

        # Gas-species mass vector before handling separately tracked liquid.
        species_masses = m_gas1 * Y1 + m_gas2 * Y2

        m_liq_in = m_liq1 + m_liq2

        if enable_liquid_water:
            # Keep inlet liquid separate initially. update_HP() will determine
            # the final equilibrium vapor-liquid split.
            m_gas_initial = m_gas1 + m_gas2

        else:
            # Gas-only outlet: convert all separate liquid into gas-phase H2O.
            species_masses[self.i_H2O] += m_liq_in
            m_gas_initial = m_gas1 + m_gas2 + m_liq_in

        if m_gas_initial <= 0.0:
            raise ValueError("The mixed gas mass must be positive.")

        Y_out = species_masses / m_gas_initial

        # Use the mass-weighted inlet temperature only as an initial state.
        # The final temperature is determined from H_target and P_out.
        T_guess = (
            m_gas1 * flow1.T
            + m_gas2 * flow2.T
        ) / (m_gas1 + m_gas2)

        self.enable_liquid_water = enable_liquid_water

        self.gas_q.TPY = T_guess, P_out, Y_out
        self.gas_q.mass = m_gas_initial

        self.m_dry = m_dry_out
        self.m_total_water = m_water_out

        if enable_liquid_water:
            # Establish final T and vapor-liquid split from conserved total
            # enthalpy and selected outlet pressure.
            self.update_HP(
                H_target=H_target,
                P_target=P_out,
            )
        else:
            # All water is now included in the gas composition.
            self.gas_q.HP = H_target / m_gas_initial, P_out

            self.m_total_water = (
                self.gas_q.mass
                * self.gas_q.phase.Y[self.i_H2O]
            )

            if hasattr(self, "_m_vap"):
                self._m_vap = self.m_total_water

            if hasattr(self, "_m_liq"):
                self._m_liq = 0.0

        self._set_static_equal_total()

        return self

    # ------------------------------------------------------------------
    # Cantera-like setter properties
    # ------------------------------------------------------------------
    @property
    def TP(self):
        raise AttributeError("TP is write-only")

    @TP.setter
    def TP(self, args):
        T, P = args

        # fastest path: pure gas-only
        if not self._use_liquid_model():
            self.gas_q.TP = T, P
            self.disable_liquid_model(collapse=True)
            self._set_static_equal_total()
            return

        # full water/liquid model
        self.repartition_at_TP(T, P)
        self._set_static_equal_total()

    @property
    def TPX(self):
        raise AttributeError("TPX is write-only")

    @TPX.setter
    def TPX(self, args):
        T, P, X = args

        # Fast path: no liquid model active
        if not self._use_liquid_model():
            self.gas_q.TPX = T, P, X

            self.m_dry = self.W_gas * (1.0 - self._gas_h2o_mass_fraction())
            self.m_total_water = self.m_vap

            self._set_static_equal_total()
            return

        # Full liquid model
        self._set_state_with_composition(
            basis="X",
            T=T,
            P=P,
            comp=X,
            repartition=True,
        )

    @property
    def TPY(self):
        raise AttributeError("TPY is write-only")

    @TPY.setter
    def TPY(self, args):
        T, P, Y = args

        # Fast path: no liquid model active
        if not self._use_liquid_model():
            self.gas_q.TPY = T, P, Y

            self.m_dry = self.W_gas * (1.0 - self._gas_h2o_mass_fraction())
            self.m_total_water = self.m_vap

            self._set_static_equal_total()
            return

        # Full liquid model
        self._set_state_with_composition(
            basis="Y",
            T=T,
            P=P,
            comp=Y,
            repartition=True,
        )

    # HP = (H_total [J], P [Pa])  H = total enthalpy = gas enthalpy + liquid enthalpy, 
    # so that HP flash conserves total enthalpy (h*mass + m_liq*sat_liq_h)
    @property
    def HP(self):
        raise AttributeError("HP is write-only")

    @HP.setter
    def HP(self, args):
        H, P = args

        self.update_HP(
            H_target=H,
            P_target=P,
        )

    @property
    def HPX(self):
        raise AttributeError("HPX is write-only")

    @HPX.setter
    def HPX(self, args):
        h, P, X = args
        self._set_energy_state_with_composition("H", "X", h, P, X)

    @property
    def HPY(self):
        raise AttributeError("HPY is write-only")

    @HPY.setter
    def HPY(self, args):
        h, P, Y = args
        self._set_energy_state_with_composition("H", "Y", h, P, Y)

    # SP = (S_total [J/K], P [Pa])  S = total entropy = gas entropy + liquid entropy, 
    # so that SP flash conserves total entropy (s*mass + m_liq*sat_liq_s)
    @property
    def SP(self):
        raise AttributeError("SP is write-only")

    @SP.setter
    def SP(self, args):
        S, P = args

        if P <= 0.0:
            raise ValueError(f"SP setter: P must be > 0, got {P} at station {self.station_nr}")

        self.update_SP(
            S_target=S,
            P_target=P,
        )

    @property
    def SPX(self):
        raise AttributeError("SPX is write-only")

    @SPX.setter
    def SPX(self, args):
        s, P, X = args
        if P <= 0.0:
            raise ValueError(f"SP setter: P must be > 0, got {P} at station {self.station_nr}")

        self._set_energy_state_with_composition("S", "X", s, P, X)

    @property
    def SPY(self):
        raise AttributeError("SPY is write-only")

    @SPY.setter
    def SPY(self, args):
        s, P, Y = args
        if P <= 0.0:
            raise ValueError(f"SP setter: P must be > 0, got {P} at station {self.station_nr}")
        self._set_energy_state_with_composition("S", "Y", s, P, Y)

    # ------------------------------------------------------------------
    # public methods
    # ------------------------------------------------------------------
    def set_conditions_humidity(self, *,
                                T: float,
                                P: float,
                                gas_mass: float | None = None,
                                humidity_mode: str = "dry",
                                humidity_value: float = 0.0,
                                dry_X: dict | None = None,
                                dry_Y: dict | None = None):
        """
        Public method to set T/P and humidity on an existing TGaspathCondition.

        humidity_mode:
            "dry"
            "RH"
            "H2O_vol_pct"
            "H2O_mass_pct"
        """

        if gas_mass is not None:
            self.gas_q.mass = gas_mass

        if humidity_mode == "dry":
            if dry_X is None:
                raise ValueError("dry_X required for dry gas")
            self.gas_q.TPX = T, P, self._normalize_without_h2o(dry_X)
            self.m_dry = self.W_gas
            self.m_total_water = 0.0

        elif humidity_mode == "RH":
            if dry_X is None:
                raise ValueError("dry_X required for RH")
            self._initialize_humidity(
                mode="RH",
                value=humidity_value,
                T=T,
                P=P,
                dry_comp=dry_X,
                comp_basis="X",
            )

        elif humidity_mode == "vol_pct":
            if dry_X is None:
                raise ValueError("dry_X required for vol_pct")
            self._initialize_humidity(
                mode="vol_pct",
                value=humidity_value,
                T=T,
                P=P,
                dry_comp=dry_X,
                comp_basis="X",
            )

        elif humidity_mode == "H2O_mass_pct":
            if dry_Y is None:
                raise ValueError("dry_Y required for H2O_mass_pct")
            self._initialize_humidity(
                mode="H2O_mass_pct",
                value=humidity_value,
                T=T,
                P=P,
                dry_comp=dry_Y,
                comp_basis="Y",
            )

        else:
            raise ValueError("humidity_mode must be 'dry', 'RH', 'H2O_vol_pct', or 'H2O_mass_pct'")

        self._set_static_equal_total()
        return self

    # ------------------------------------------------------------------
    # calculate static from total
    # ------------------------------------------------------------------
    def _save_gasq_state(self):
        return {
            "T": self.T,
            "P": self.P,
            "X": self.X,
            "mass": self.W_gas,
        }

    def _restore_gasq_state(self, state):
        self.gas_q.TPX = state["T"], state["P"], state["X"]
        self.gas_q.mass = state["mass"]

    def update_static(self, Mach=None, V=None, A=None, mdot=None):
        import math
        from scipy.optimize import root_scalar

        # default: static = total
        if Mach is None and V is None and A is None:
            self.Ts = self.T
            self.Ps = self.P
            self.Mach = 0.0
            self.V = 0.0
            self.A = None
            self.rhos = self.gas_q.density
            return

        if A is not None and mdot is None:
            raise ValueError("If A is specified, mdot must also be specified")

        if A is None and mdot is not None:
            raise ValueError("If mdot is specified, A must also be specified")

        n = sum([Mach is not None, V is not None, A is not None])
        if n != 1:
            raise ValueError("Specify exactly one of Mach, V, or A+mdot")

        saved = self._save_gasq_state()

        Pt = saved["P"]
        X = saved["X"]
        h_total = self.gas_q.enthalpy_mass
        s_total = self.gas_q.entropy_mass

        def eval_static(Ps):
            self.gas_q.SPX = s_total, Ps, X

            if Mach is not None:
                vel = Mach * self.gas_q.sound_speed
            elif V is not None:
                vel = V
            else:
                vel = mdot / (self.gas_q.density * A)

            res = self.gas_q.enthalpy_mass + 0.5 * vel * vel - h_total

            return (
                res,
                vel,
                self.gas_q.T,
                self.gas_q.P,
                self.gas_q.density,
                self.gas_q.sound_speed,
            )

        def f(logP):
            Ps = math.exp(logP)
            res, *_ = eval_static(Ps)
            return res

        try:
            P_hi = Pt * (1.0 - 1e-8)
            logP_hi = math.log(P_hi)
            f_hi = f(logP_hi)

            logP_low = None

            for fac in [0.99, 0.97, 0.95, 0.90, 0.85, 0.80,
                        0.75, 0.70, 0.65, 0.60, 0.55, 0.50,
                        0.45, 0.40, 0.35, 0.30]:
                try:
                    logP_try = math.log(Pt * fac)
                    f_try = f(logP_try)
                except Exception:
                    continue

                if f_try * f_hi < 0.0:
                    logP_low = logP_try
                    break

            if logP_low is None:
                raise RuntimeError("Could not bracket static state")

            sol = root_scalar(
                f,
                bracket=(logP_low, logP_hi),
                method="toms748",
                xtol=1e-6,
                maxiter=50,
            )

            if not sol.converged:
                raise RuntimeError(f"Static solve failed: {sol.flag}")

            Ps = math.exp(sol.root)
            _, vel, Ts, Ps, rho, a = eval_static(Ps)

            self.Ts = Ts
            self.Ps = Ps
            self.V = vel
            self.Mach = vel / a
            self.A = A
            self.rhos = rho

        finally:
            self._restore_gasq_state(saved)

    def _set_static_equal_total(self):
        self.Ts = self.T
        self.Ps = self.P
        self.Mach = 0.0
        self.V = 0.0
        self.A = None
        self.rhos = self.gas_q.density

    # for changing from ambient frame of reference to moving engine frame of reference in inlet
    def _set_total_equal_static(self):
        self.Ts = self.T
        self.Ps = self.P
        self.Mach = 0.0
        self.V = 0.0
        self.A = None
        self.rhos = self.gas_q.density

    def repartition_at_TP(self, T: float, P: float):
        """
        Repartition total water into gas vapor + external liquid at fixed T,P.
        Conserves m_dry and m_total_water.
        """
        if not self._has_water():
            self.gas_q.TP = T, P
            self.m_total_water = 0.0
# no need, slows down            return self._quick_state_dict()
            return

        if not self._use_liquid_model():
            self.gas_q.TP = T, P
            self.disable_liquid_model(collapse=True)
# no need, slows down            return self._quick_state_dict()
            return

        dry_basis_X = self._current_dry_basis_X()
        st = self._state_at_TP_with_split(
            T=T,
            P=P,
            dry_basis_X=dry_basis_X,
            m_dry=self.m_dry,
            m_total_water=self.m_total_water,
        )
        self._apply_state(st)
        return st

    def update_HP(self, H_target: float, P_target: float,
                  T_low: float | None = None,
                  T_high: float | None = None,
                  tol: float = 1e-4,
                  maxiter: int = 100):
        """
        Total-H flash at target total enthalpy [J] and pressure [Pa].
        Conserves m_dry and m_total_water.
        """
        if not self._has_water():
            self.gas_q.HP = H_target / self.W_gas, P_target
            self.m_total_water = 0.0
# no need, slows down            return self._quick_state_dict()
            return

        if not self._use_liquid_model():
            self.gas_q.HP = H_target / self.W_gas, P_target
            self.disable_liquid_model(collapse=True)
# no need, slows down            return self._quick_state_dict()
            return

        if T_low is None:
            T_low = max(self.T, c.T_WATER_TRIPLE + 1.0)
        if T_high is None:
            T_high = max(2.0 * self.T, self.T + 400.0)

        st = self._flash_HP_or_SP(
            target=H_target,
            P_target=P_target,
            mode="H",
            T_low=T_low,
            T_high=T_high,
            tol=tol,
            maxiter=maxiter,
        )
        self._apply_state(st)
        return st

    def update_SP(self, S_target: float, P_target: float,
                  T_low: float | None = None,
                  T_high: float | None = None,
                  tol: float = 1e-4,
                  maxiter: int = 100):
        """
        Total-S flash at target total entropy [J/K] and pressure [Pa].
        Conserves m_dry and m_total_water.
        """
        if not self._has_water():
            self.gas_q.SP = S_target / self.W_gas, P_target
            self.m_total_water = 0.0
# no need, slows down            return self._quick_state_dict()
            return

        if not self._use_liquid_model():
            self.gas_q.SP = S_target / self.W_gas, P_target
            self.disable_liquid_model(collapse=True)
# no need, slows down            return self._quick_state_dict()
            return

        if T_low is None:
            T_low = max(self.T, c.T_WATER_TRIPLE + 1.0)
        if T_high is None:
            T_high = max(2.0 * self.T, self.T + 400.0)

        st = self._flash_HP_or_SP(
            target=S_target,
            P_target=P_target,
            mode="S",
            T_low=T_low,
            T_high=T_high,
            tol=tol,
            maxiter=maxiter,
        )
        self._apply_state(st)
        return st

    def add_liquid_water(self, m_liq_add: float):
        if m_liq_add < 0.0:
            raise ValueError("m_liq_add must be >= 0")
        self.m_total_water += m_liq_add

    # def set_equivalence_ratio(self, phi, fuel, air, basis="mole", repartition=True):
    #     mix_gas = ct.Solution(self.mechanism)
    #     mix_gas.TP = self.T, self.P
    #     mix_gas.set_equivalence_ratio(phi, fuel=fuel, oxidizer=air, basis=basis)

    #     liq_old = self.m_liq
    #     self.gas_q = ct.Quantity(mix_gas, mass=self.mass)
    #     self.m_dry = self.mass * (1.0 - self._gas_h2o_mass_fraction())
    #     self.m_total_water = self.m_vap + liq_old

    #     if repartition:
    #         self.repartition_at_TP(self.T, self.P)

    def burn_at_equivalence_ratio(self, phi, fuel, air,
                                  basis="mole",
                                  equil_mode="HP",
                                  repartition=True):
        self.set_equivalence_ratio(phi, fuel, air, basis=basis, repartition=False)

        phase = self.gas_q.phase
        phase.equilibrate(equil_mode)
        self.gas_q = ct.Quantity(phase, mass=self.W_gas)

        liq_old = self.m_liq
        self.m_dry = self.W_gas * (1.0 - self._gas_h2o_mass_fraction())
        self.m_total_water = self.m_vap + liq_old

        # hot combustor: usually safe to disable liquid model
        self.maybe_disable_liquid_model(T_threshold=700.0)

        if repartition:
            self.repartition_at_TP(self.T, self.P)

    def add_combustion_products(self, prod_gas: ct.Solution, prod_gas_mass: float,
                                prod_liq: float = 0.0, repartition: bool = True):
        if prod_gas_mass < 0.0 or prod_liq < 0.0:
            raise ValueError("prod_gas_mass and prod_liq must be >= 0")

        if tuple(self.gas.species_names) != tuple(prod_gas.species_names):
            raise ValueError("prod_gas must use same species set/order as self.gas")

        liq_old = self.m_liq + prod_liq
        q_prod = ct.Quantity(prod_gas, mass=prod_gas_mass)
        self.gas_q += q_prod

        self.m_dry = self.W_gas * (1.0 - self._gas_h2o_mass_fraction())
        self.m_total_water = self.m_vap + liq_old

        self.maybe_disable_liquid_model(T_threshold=700.0)

        if repartition:
            self.repartition_at_TP(self.T, self.P)

    def add_fuel_and_equilibrate(self, fuel_X, fuel_mass: float,
                                 equil_mode: str = "HP",
                                 repartition: bool = True):
        if fuel_mass < 0.0:
            raise ValueError("fuel_mass must be >= 0")
        if fuel_mass == 0.0:
            return

        liq_old = self.m_liq

        fuel_gas = ct.Solution(self.mechanism)
        fuel_gas.TPX = self.T, self.P, fuel_X
        fuel_q = ct.Quantity(fuel_gas, mass=fuel_mass)

        self.gas_q += fuel_q

        phase = self.gas_q.phase
        phase.equilibrate(equil_mode)
        self.gas_q = ct.Quantity(phase, mass=self.W_gas)

        self.m_dry = self.W_gas * (1.0 - self._gas_h2o_mass_fraction())
        self.m_total_water = self.m_vap + liq_old

        self.maybe_disable_liquid_model(T_threshold=700.0)

        if repartition:
            self.repartition_at_TP(self.T, self.P)

    # ------------------------------------------------------------------
    # internal state-setting helpers
    # ------------------------------------------------------------------

    def _set_state_with_composition(self, basis: str, T, P, comp, repartition=True):
        liq_old = self.m_liq

        if basis == "X":
            self.gas_q.TPX = T, P, comp
        elif basis == "Y":
            self.gas_q.TPY = T, P, comp
        else:
            raise ValueError("basis must be 'X' or 'Y'")

        self.m_dry = self.W_gas * (1.0 - self._gas_h2o_mass_fraction())
        self.m_total_water = self.m_vap + liq_old

        if not self.enable_liquid_water:
            self.disable_liquid_model(collapse=True)
            return

        if repartition:
            self.repartition_at_TP(T, P)

    def _set_energy_state_with_composition(self, mode: str, basis: str, value, P, comp):
        liq_old = self.m_liq

        if basis == "X":
            self.gas_q.TPX = self.T, P, comp
        elif basis == "Y":
            self.gas_q.TPY = self.T, P, comp
        else:
            raise ValueError("basis must be 'X' or 'Y'")

        self.m_dry = self.W_gas * (1.0 - self._gas_h2o_mass_fraction())
        self.m_total_water = self.m_vap + liq_old

        if not self.enable_liquid_water:
            if mode == "H":
                self.gas_q.HP = value, P
            elif mode == "S":
                self.gas_q.SP = value, P
            else:
                raise ValueError("mode must be 'H' or 'S'")
            self.disable_liquid_model(collapse=True)
            return

        if mode == "H":            
            target = self.W_gas * value 
            if liq_old > self.LIQ_ABS_TOL:
                target += liq_old * self._sat_liquid_h(self.T)
            self.update_HP(H_target=target, P_target=P)
        elif mode == "S":
            target = self.W_gas * value 
            if liq_old > self.LIQ_ABS_TOL:
                target += liq_old * self._sat_liquid_s(self.T)
            self.update_SP(S_target=target, P_target=P)
        else:
            raise ValueError("mode must be 'H' or 'S'")

    # ------------------------------------------------------------------
    # humidity initialization
    # ------------------------------------------------------------------
    def _water(self):
        if self._scratch_water is None:
            self._scratch_water = ct.Water()
        return self._scratch_water

    def _handle_oversaturation_input(self, mode, value, x_req, x_sat):
        #  old code
        # """
        # Decide what to do if requested water exceeds vapor saturation.
        # """

        # oversaturated = x_req > x_sat + 1e-12

        # if not oversaturated:
        #     return x_req

        # if self.enable_liquid_water:
        #     return x_req

        # if not self.enable_liquid_water:
        #     # gas-only model: clamp to saturation, discard excess intentionally
        #     return min(x_req, x_sat)

        # raise ValueError(
        #     f"{mode}={value} gives oversaturated air, but enable_liquid_water=False. "
        #     "Enable liquid water model, reduce humidity, or set enable_liquid_water=True to "
        #     "explicitly clamp/discard excess water."
        # )
        """
        Validate or allow oversaturated humidity input.

        x_req:
            requested total H2O mole fraction implied by input

        x_sat:
            saturated H2O mole fraction at T,P
        """

        oversaturated = x_req > x_sat * (1.0 + self.RH_TOL)

        if oversaturated and not self.enable_liquid_water:
            raise ValueError(
                f"{mode}={value} implies supersaturated air at station {self.station_nr} "
                f"(RH={100.0 * x_req / x_sat:.3f}%), "
                "but enable_liquid_water=False. "
                "Set enable_liquid_water=True, or reduce the humidity input."
            )

        return x_req


    def _initialize_humidity(self, mode: str, value: float, T: float, P: float,
                            dry_comp: dict, comp_basis: str):
        if value < 0.0:
            raise ValueError(f"{mode} must be >= 0")

        dry_comp = self._normalize_without_h2o(dry_comp)

        if mode == "RH":
            if comp_basis != "X":
                raise ValueError("RH requires dry mole fractions")

            x_sat = self._sat_water_mole_fraction(T, P)
            x_req = (value / 100.0) * x_sat
            x_req = self._handle_oversaturation_input(mode, value, x_req, x_sat)

            self._initialize_from_requested_x(T, P, dry_comp, x_req)

        elif mode == "vol_pct":
            if comp_basis != "X":
                raise ValueError("vol_pct requires dry mole fractions")

            x_req = value / 100.0
            if x_req >= 1.0:
                raise ValueError("H2O_vol_pct must be < 100")

            x_sat = self._sat_water_mole_fraction(T, P)
            x_req = self._handle_oversaturation_input(mode, value, x_req, x_sat)

            self._initialize_from_requested_x(T, P, dry_comp, x_req)

        elif mode == "H2O_mass_pct":
            if comp_basis != "Y":
                raise ValueError("H2O_mass_pct requires dry mass fractions")

            y_req = value / 100.0
            if y_req >= 1.0:
                raise ValueError("H2O_mass_pct must be < 100")

            gas_Y = {sp: yi * (1.0 - y_req) for sp, yi in dry_comp.items()}
            gas_Y["H2O"] = y_req

            # Convert requested mass fraction to mole fraction
            self.gas_q.TPY = T, P, gas_Y
            x_req = self.x_H2O_gas

            x_sat = self._sat_water_mole_fraction(T, P)
            x_req_checked = self._handle_oversaturation_input(
                mode, value, x_req, x_sat
            )

            if x_req_checked < x_req:
                # gas-only clamped case
                dry_X = self._current_dry_basis_X()
                self._initialize_from_requested_x(T, P, dry_X, x_req_checked)
            else:
                # liquid model enabled or not oversaturated
                self.gas_q.TPY = T, P, gas_Y
                self.m_dry = self.W_gas * (1.0 - self._gas_h2o_mass_fraction())

                # total water from original requested mass fraction
                self.m_total_water = self.W_gas * y_req

                if self.enable_liquid_water:
                    self.repartition_at_TP(T, P)

        else:
            raise ValueError("mode must be 'RH', 'vol_pct', or 'H2O_mass_pct'")

    # m_liq error at RH=100 problem fix:
    # def _initialize_from_requested_x(self, T, P, dry_basis_X, x_req):
    #     x_sat = self._sat_water_mole_fraction(T, P)
    #     x_vap = min(x_req, x_sat)
    #     Xgas = {sp: xi * (1.0 - x_vap) for sp, xi in dry_basis_X.items()}
    #     Xgas["H2O"] = x_vap
    #     self.gas_q.TPX = T, P, Xgas
    #     self.m_dry = self.mass * (1.0 - self._gas_h2o_mass_fraction())
    #     mw_dry = self._mean_mw_of_composition(T, P, dry_basis_X)
    #     n_dry = self.m_dry / mw_dry
    #     n_h2o_total = x_req / max(1.0 - x_req, 1e-15) * n_dry
    #     self.m_total_water = n_h2o_total * c.MW_H2O
    #     if not self.enable_liquid_water:
    #         self.disable_liquid_model(collapse=True)
    def _initialize_from_requested_x(self, T, P, dry_basis_X, x_req):
        x_sat = self._sat_water_mole_fraction(T, P)

        # Treat very-near-saturation as exactly saturated
        if abs(x_req - x_sat) <= self.RH_TOL * max(x_sat, 1e-30):
            x_req = x_sat

        if self.enable_liquid_water:
            x_vap = min(x_req, x_sat)
        else:
            x_vap = x_req

        Xgas = {sp: xi * (1.0 - x_vap) for sp, xi in dry_basis_X.items()}
        Xgas["H2O"] = x_vap

        self.gas_q.TPX = T, P, Xgas
        self.m_dry = self.W_gas * (1.0 - self._gas_h2o_mass_fraction())

        mw_dry = self._mean_mw_of_composition(T, P, dry_basis_X)
        n_dry = self.m_dry / mw_dry
        n_h2o_total = x_req / max(1.0 - x_req, 1e-15) * n_dry
        self.m_total_water = n_h2o_total * c.MW_H2O

        # Clean up tiny artificial liquid at RH≈100%
        m_liq_raw = self.m_total_water - self.m_vap
        liq_tol = max(
            self.LIQ_ABS_TOL,
            self.LIQ_REL_TOL * max(self.m_total_water, self.W_gas, 1e-30),
        )

        # if m_liq_raw <= liq_tol:
        #     self.m_total_water = self.m_vap
        if (m_liq_raw <= liq_tol) or (not self.enable_liquid_water):
            self.disable_liquid_model(collapse=True)

    # ------------------------------------------------------------------
    # pure thermodynamic helpers
    # ------------------------------------------------------------------
    def _gas_h2o_mass_fraction(self):
        # return self.Y.get("H2O", 0.0)
        return float(self.gas_q.phase.Y[self.i_H2O])

    def _normalize_without_h2o(self, comp: dict):
        out = {k: v for k, v in comp.items() if k != "H2O"}
        s = sum(out.values())
        if s <= 0.0:
            raise ValueError("composition sum must be > 0")
        return {k: v / s for k, v in out.items()}

    def _current_dry_basis_X(self):
        X = self.X
        x_h2o = X.get("H2O", 0.0)
        scale = max(1.0 - x_h2o, 1e-15)
        dry = {sp: xi / scale for sp, xi in X.items() if sp != "H2O"}
        return self._normalize_without_h2o(dry)

    # def _sat_water_mole_fraction(self, T, P):
    #     if T <= c.T_WATER_TRIPLE:
    #         raise ValueError(
    #             f"T={T:g} K is below the liquid-water triple point for this model."
    #         )

    #     if T >= c.T_WATER_CRITICAL:
    #         return 1.0

    #     w =self._water()
    #     w.TQ = T, 1.0
    #     p_sat = w.P_sat

    #     if p_sat >= P:
    #         return 1.0

    #     return max(p_sat / P, 0.0)

    # def _sat_water_mole_fraction(self, T: float, P: float) -> float:
    #     """
    #     Saturation mole fraction of H2O at temperature T [K]
    #     and total pressure P [Pa].

    #     Above the water triple point:
    #         use Cantera liquid-vapor saturation pressure.

    #     Below the triple point:
    #         use saturation vapor pressure over ice
    #         (Murphy & Koop, 2005).

    #     Returns
    #     -------
    #     x_sat : float
    #         Saturated gas-phase H2O mole fraction.
    #     """
    #     if P <= 0.0:
    #         raise ValueError("Pressure must be > 0")

    #     p_sat = self.water_saturation_pressure(T)

    #     # At very low total pressure, saturation pressure could in principle
    #     # approach/exceed total pressure. Cap to a physically valid gas mole
    #     # fraction below 1.
    #     return min(p_sat / P, 1.0 - 1e-12)

    def _sat_water_mole_fraction(self, T: float, P: float) -> float:
        """
        Maximum gas-phase H2O mole fraction at T/P.

        Below the triple point:
            saturation vapor pressure over ice.

        Between triple and critical point:
            liquid-vapor saturation pressure from Cantera.

        At or above the critical temperature:
            no liquid-vapor phase boundary exists, so all water can
            remain in the gas/supercritical phase.
        """
        if P <= 0.0:
            raise ValueError("Pressure must be > 0")

        if T >= c.T_WATER_CRITICAL:
            return 1.0

        p_sat = self.water_saturation_pressure(T)

        if p_sat >= P:
            return 1.0

        return p_sat / P

    def _sat_liquid_h(self, T: float) -> float:
        if T < c.T_WATER_TRIPLE:
            raise ValueError(
                f"T={T:g} K is below the water triple point. "
                "Liquid-water enthalpy is not defined by this model."
            )

        if T >= c.T_WATER_CRITICAL:
            raise ValueError(
                f"T={T:g} K is at or above the water critical temperature. "
                "A saturated-liquid state does not exist."
            )

        w = self._water()
        w.TQ = T, 0.0
        return w.enthalpy_mass

    # def water_saturation_pressure(self, T: float) -> float:
    #     """
    #     Saturation vapor pressure [Pa].

    #     Above 273.15 K:
    #         use Cantera liquid-vapor saturation.

    #     Below 273.15 K:
    #         use saturation over ice (Murphy & Koop, 2005).
    #     """
    #     if T >= c.T_WATER_TRIPLE:
    #         water = ct.Water()
    #         water.TQ = T, 1.0
    #         return water.P_sat

    #     # Murphy & Koop (2005), saturation vapor pressure over ice
    #     ln_p = (
    #         9.550426
    #         - 5723.265 / T
    #         + 3.53068 * math.log(T)
    #         - 0.00728332 * T
    #     )

    #     return math.exp(ln_p)

    def water_saturation_pressure(self, T: float) -> float:
        """
        Saturation vapor pressure [Pa].

        T < triple point:
            saturation over ice (Murphy & Koop, 2005).

        triple point <= T < critical point:
            liquid-vapor saturation from Cantera.
        """
        if T >= c.T_WATER_CRITICAL:
            raise ValueError(
                f"Saturation pressure is not defined above the water "
                f"critical temperature ({c.T_WATER_CRITICAL:g} K)."
            )

        if T >= c.T_WATER_TRIPLE:
            water = self._water()
            water.TQ = T, 1.0
            return water.P_sat

        # Murphy & Koop (2005): saturation vapor pressure over ice
        ln_p = (
            9.550426
            - 5723.265 / T
            + 3.53068 * math.log(T)
            - 0.00728332 * T
        )

        return math.exp(ln_p)

    def _sat_liquid_s(self, T):
        if T <= c.T_WATER_TRIPLE:
            raise ValueError(
                f"T={T:g} K is below the liquid-water triple point for this model."
            )

        if T >= c.T_WATER_CRITICAL:
            return 0.0

        w =self._water()
        w.TQ = T, 0.0
        return w.entropy_mass

    def _mean_mw_of_composition(self, T, P, X):
        # gas = self._scratch_gas
        # gas.TPX = T, P, X
        return self.gas_q.mean_molecular_weight / 1000.0

    def _quick_state_dict(self):
        return {
            "T": self.T,
            "P": self.P,
            "X": self.X,
            "m_gas": self.W_gas,
            "m_vap": self.m_vap,
            "m_liq": self.m_liq,
            "x_h2o": self.x_H2O_gas,
            "RH_gas": self.RH_gas,
            "has_condensed_water": self.has_condensed_water,
            "H_total": self.H_total,
            "S_total": self.S_total,
        }

    def _state_at_TP_with_split(self, T=None, P=None, dry_basis_X=None,
                                m_dry=None, m_total_water=None):

        if T is None:
            T = self.Ts
        if P is None:
            P = self.Ps
        if dry_basis_X is None:
            dry_basis_X = self._current_dry_basis_X()
        if m_dry is None:
            m_dry = self.m_dry
        if m_total_water is None:
            m_total_water = self.m_total_water

        saved = self._save_gasq_state()

        try:
            self.gas_q.TPX = T, P, dry_basis_X
            mw_dry = self.gas_q.mean_molecular_weight / 1000.0

            n_dry = m_dry / mw_dry
            x_sat = self._sat_water_mole_fraction(T, P)

            if x_sat >= 1.0:
                m_vap = m_total_water
                m_liq = 0.0
            else:
                n_vap_sat = x_sat / max(1.0 - x_sat, 1e-15) * n_dry
                m_vap_sat = n_vap_sat * c.MW_H2O
                m_vap = min(m_total_water, m_vap_sat)
                m_liq = max(0.0, m_total_water - m_vap)

            if m_liq <= self.LIQ_ABS_TOL:
                m_liq = 0.0
                m_vap = m_total_water

            n_vap = m_vap / c.MW_H2O
            x_h2o = n_vap / (n_dry + n_vap) if (n_dry + n_vap) > 0.0 else 0.0

            Xgas = {sp: xi * (1.0 - x_h2o) for sp, xi in dry_basis_X.items()}
            Xgas["H2O"] = x_h2o

            self.gas_q.TPX = T, P, Xgas

            h_gas = self.gas_q.enthalpy_mass
            s_gas = self.gas_q.entropy_mass
            m_gas = m_dry + m_vap

            h_liq = self._sat_liquid_h(T) if m_liq > self.LIQ_ABS_TOL else 0.0
            s_liq = self._sat_liquid_s(T) if m_liq > self.LIQ_ABS_TOL else 0.0

            RH_gas = 100.0 * x_h2o / x_sat if (0.0 < x_sat < 1.0) else 0.0

            return {
                "T": T,
                "P": P,
                "X": Xgas,
                "m_gas": m_gas,
                "m_vap": m_vap,
                "m_liq": m_liq,
                "x_h2o": x_h2o,
                "RH_gas": RH_gas,
                "has_condensed_water": m_liq > self.LIQ_ABS_TOL,
                "H_total": m_gas * h_gas + m_liq * h_liq,
                "S_total": m_gas * s_gas + m_liq * s_liq,
            }

        finally:
            self._restore_gasq_state(saved)

    def _apply_state(self, st):
        self.gas_q.TPX = st["T"], st["P"], st["X"]
        self.gas_q.mass = st["m_gas"]
        self.m_dry = st["m_gas"] - st["m_vap"]
        self.m_total_water = st["m_vap"] + st["m_liq"]

    # def _flash_HP_or_SP(self, target, P_target, mode,
    #                     T_low, T_high, tol, maxiter):
    #     # _flash_HP_or_SP(...) is solving:
    #     # Given:
    #     #     H_target (or S_target)
    #     #     P_target
    #     #     m_dry
    #     #     m_total_water
    #     # Find:
    #     #     T
    #     # such that:
    #     # H_total(T,P) = H_target or S_total(T,P) = S_target
    #     # where:
    #     # H_total = H_gas(T,P,x_H2O) + H_liquid(T,m_liq)
    #     # and simultaneously: m_total_water = m_vap + m_liq
    #     # with vapor-liquid equilibrium enforced.

    #     if mode not in ("H", "S"):
    #         raise ValueError("mode must be 'H' or 'S'")

    #     dry_basis_X = self._current_dry_basis_X()
    #     m_dry = self.m_dry
    #     m_total_water = self.m_total_water
    #     T_min = c.T_WATER_TRIPLE + 1.0

    #     def residual(T):
    #         st = self._state_at_TP_with_split(
    #             T=T,
    #             P=P_target,
    #             dry_basis_X=dry_basis_X,
    #             m_dry=m_dry,
    #             m_total_water=m_total_water,
    #         )
    #         return (st["H_total"] if mode == "H" else st["S_total"]) - target

    #     f_low = residual(T_low)
    #     f_high = residual(T_high)

    #     if self.debug_flash:
    #         print(f"_flash {mode}: f({T_low})={f_low:.6e}, f({T_high})={f_high:.6e}")

    #     if abs(f_low) < tol:
    #         return self._state_at_TP_with_split(T_low, P_target, dry_basis_X, m_dry, m_total_water)
    #     if abs(f_high) < tol:
    #         return self._state_at_TP_with_split(T_high, P_target, dry_basis_X, m_dry, m_total_water)

    #     if f_low * f_high > 0.0:
    #         if f_low > 0.0 and f_high > 0.0:
    #             T2 = T_low
    #             for _ in range(20):
    #                 T_new = max(T_min, T2 - 0.5 * (T_high - T_low))
    #                 if T_new <= T_min + 1e-6:
    #                     break
    #                 f_new = residual(T_new)
    #                 if self.debug_flash:
    #                     print(f"  expand down: f({T_new})={f_new:.6e}")
    #                 if abs(f_new) < tol:
    #                     return self._state_at_TP_with_split(T_new, P_target, dry_basis_X, m_dry, m_total_water)
    #                 if f_new * f_high < 0.0:
    #                     T_low, f_low = T_new, f_new
    #                     break
    #                 T2 = T_new
    #                 T_high, f_high = T_low, f_low
    #         elif f_low < 0.0 and f_high < 0.0:
    #             T2 = T_high
    #             for _ in range(20):
    #                 T2 *= 1.5
    #                 f2 = residual(T2)
    #                 if self.debug_flash:
    #                     print(f"  expand up: f({T2})={f2:.6e}")
    #                 if abs(f2) < tol:
    #                     return self._state_at_TP_with_split(T2, P_target, dry_basis_X, m_dry, m_total_water)
    #                 if f_low * f2 < 0.0:
    #                     T_high, f_high = T2, f2
    #                     break
    #         else:
    #             raise ValueError("Unexpected bracketing state")

    #         if f_low * f_high > 0.0:
    #             raise ValueError(
    #                 f"Could not bracket flash root: "
    #                 f"f({T_low})={f_low:.6e}, f({T_high})={f_high:.6e}"
    #             )

    #     sol = root_scalar(
    #         residual,
    #         bracket=(T_low, T_high),
    #         method="toms748",
    #         xtol=tol,
    #         maxiter=maxiter,
    #     )

    #     if not sol.converged:
    #         raise RuntimeError(f"Flash solver did not converge: {sol.flag}")

    #     return self._state_at_TP_with_split(
    #         T=sol.root,
    #         P=P_target,
    #         dry_basis_X=dry_basis_X,
    #         m_dry=m_dry,
    #         m_total_water=m_total_water,
    #     )


    def _flash_HP_or_SP(
        self,
        target,
        P_target,
        mode,
        T_low,
        T_high,
        tol,
        maxiter,
    ):
        """
        Flash calculation at specified pressure.

        Solves for temperature T such that either:

            H_total(T, P_target) = target     mode == "H"

        or:

            S_total(T, P_target) = target     mode == "S"

        while conserving:
            - dry-gas mass
            - total water mass

        and enforcing vapor/liquid equilibrium.

        The current model does not support a condensed ice phase, so the
        search is not allowed below the water triple-point temperature.
        """

        if mode not in ("H", "S"):
            raise ValueError("mode must be 'H' or 'S'")

        dry_basis_X = self._current_dry_basis_X()
        m_dry = self.m_dry
        m_total_water = self.m_total_water

        # Do not allow the liquid-water flash to enter the ice region.
        T_min = c.T_WATER_TRIPLE + 1e-6

        T_low = max(float(T_low), T_min)
        T_high = max(float(T_high), T_low + 1.0)

        def residual(T):
            st = self._state_at_TP_with_split(
                T=T,
                P=P_target,
                dry_basis_X=dry_basis_X,
                m_dry=m_dry,
                m_total_water=m_total_water,
            )

            if mode == "H":
                return st["H_total"] - target
            else:
                return st["S_total"] - target

        # --------------------------------------------------------------
        # Initial bracket
        # --------------------------------------------------------------

        f_low = residual(T_low)
        f_high = residual(T_high)

        if self.debug_flash:
            print(
                f"_flash {mode}: "
                f"f({T_low:.6g})={f_low:.6e}, "
                f"f({T_high:.6g})={f_high:.6e}"
            )

        if abs(f_low) <= tol:
            return self._state_at_TP_with_split(
                T=T_low,
                P=P_target,
                dry_basis_X=dry_basis_X,
                m_dry=m_dry,
                m_total_water=m_total_water,
            )

        if abs(f_high) <= tol:
            return self._state_at_TP_with_split(
                T=T_high,
                P=P_target,
                dry_basis_X=dry_basis_X,
                m_dry=m_dry,
                m_total_water=m_total_water,
            )

        # --------------------------------------------------------------
        # Expand downward if both residuals are positive.
        #
        # Because H_total and S_total normally increase with T, this means
        # that the required state lies below the current bracket.
        # --------------------------------------------------------------

        if f_low > 0.0 and f_high > 0.0:

            if T_low > T_min:
                T_low = T_min
                f_low = residual(T_low)

                if self.debug_flash:
                    print(
                        f"  expand down: "
                        f"f({T_low:.6g})={f_low:.6e}"
                    )

                if abs(f_low) <= tol:
                    return self._state_at_TP_with_split(
                        T=T_low,
                        P=P_target,
                        dry_basis_X=dry_basis_X,
                        m_dry=m_dry,
                        m_total_water=m_total_water,
                    )

            # Still above target at the lowest supported temperature:
            # solution would require entering the ice region.
            if f_low > 0.0:
                raise ValueError(
                    f"{mode} flash requires T below the water triple point. "
                    f"At T_min={T_min:.6g} K, residual={f_low:.6e}. "
                    "Condensed ice is not supported by the current model."
                )

        # --------------------------------------------------------------
        # Expand upward if both residuals are negative.
        #
        # The required state lies above the current bracket.
        # --------------------------------------------------------------

        elif f_low < 0.0 and f_high < 0.0:

            for _ in range(20):

                # Increase upper temperature substantially each attempt.
                T_high *= 1.5
                f_high = residual(T_high)

                if self.debug_flash:
                    print(
                        f"  expand up: "
                        f"f({T_high:.6g})={f_high:.6e}"
                    )

                if abs(f_high) <= tol:
                    return self._state_at_TP_with_split(
                        T=T_high,
                        P=P_target,
                        dry_basis_X=dry_basis_X,
                        m_dry=m_dry,
                        m_total_water=m_total_water,
                    )

                if f_high > 0.0:
                    break

            if f_high < 0.0:
                raise ValueError(
                    f"Could not bracket {mode} flash root after expanding "
                    f"upper temperature to {T_high:.6g} K: "
                    f"f_low={f_low:.6e}, f_high={f_high:.6e}"
                )

        # --------------------------------------------------------------
        # We should now have a proper sign-changing bracket.
        # --------------------------------------------------------------

        if f_low * f_high > 0.0:
            raise ValueError(
                f"Could not bracket {mode} flash root: "
                f"f({T_low:.6g})={f_low:.6e}, "
                f"f({T_high:.6g})={f_high:.6e}"
            )

        # --------------------------------------------------------------
        # Scalar root solve
        # --------------------------------------------------------------

        sol = root_scalar(
            residual,
            bracket=(T_low, T_high),
            method="toms748",
            xtol=tol,
            maxiter=maxiter,
        )

        if not sol.converged:
            raise RuntimeError(
                f"{mode} flash did not converge after "
                f"{sol.iterations} iterations."
            )

        T_solution = sol.root

        if self.debug_flash:
            print(
                f"_flash {mode} converged: "
                f"T={T_solution:.9g} K, "
                f"iterations={sol.iterations}, "
                f"calls={sol.function_calls}"
            )

        return self._state_at_TP_with_split(
            T=T_solution,
            P=P_target,
            dry_basis_X=dry_basis_X,
            m_dry=m_dry,
            m_total_water=m_total_water,
        )

    # ------------------------------------------------------------------
    # method to re ininitialize TGaspathCondition
    # ------------------------------------------------------------------
    def set_conditions_humidity(self, 
                                *, 
                                T, 
                                P, 
                                total_mass=None,
                                humidity_mode=None, 
                                humidity_value=0.0,
                                dry_X_dict=None, 
                                dry_Y_dict=None):
        """
        Reinitialize this existing TGaspathCondition in-place.

        humidity_mode:
            None / "dry"
            "RH"
            "vol_pct"
            "H2O_mass_pct"
        """
        if total_mass is not None:
            self.gas_q.mass = total_mass

        if humidity_mode is None or humidity_mode == "dry":
            if dry_X_dict is None:
                raise ValueError("dry_X required for dry initialization")
            dry_X_dict = self._normalize_without_h2o(dry_X_dict)
            self.gas_q.TPX = T, P, dry_X_dict
            self.m_dry = self.W_gas
            self.m_total_water = 0.0
            self._set_static_equal_total()
            return self

        if humidity_mode == "RH":
            if dry_X_dict is None:
                raise ValueError("dry_X required for RH")
            self._initialize_humidity(
                mode="RH",
                value=humidity_value,
                T=T,
                P=P,
                dry_comp=dry_X_dict,
                comp_basis="X",
            )

        elif humidity_mode == "H2O_vol_pct":
            if dry_X_dict is None:
                raise ValueError("dry_X required for vol_pct")
            self._initialize_humidity(
                mode="vol_pct",
                value=humidity_value,
                T=T,
                P=P,
                dry_comp=dry_X_dict,
                comp_basis="X",
            )

        elif humidity_mode == "H2O_mass_pct":
            if dry_Y_dict is None:
                raise ValueError("dry_Y required for H2O_mass_pct")
            self._initialize_humidity(
                mode="H2O_mass_pct",
                value=humidity_value,
                T=T,
                P=P,
                dry_comp=dry_Y_dict,
                comp_basis="Y",
            )

        else:
            raise ValueError("humidity_mode must be None, 'dry', 'RH', 'H2O_vol_pct', or 'H2O_mass_pct'")

        self._set_static_equal_total()
        return self    

    # ------------------------------------------------------------------
    # convenience compressor helpers
    # ------------------------------------------------------------------
    def compress_isentropic(self, PR: float, out: "TFlowState", W_total = None):
        """
        Ideal compression:
        - total entropy gas + liquid conserved
        - target total pressure
        """
        out.copy_from(self)

        # in case mass is given (e.g., for a compressor with bleed, fan core or duct flow etc.), 
        # set the output mass by scaling from self
        Starget = float(self.S_total)
        if W_total is not None:
            out.scale_mass(W_total/self.W)
            Starget = Starget * W_total/self.W
        out.update_SP(
            S_target=Starget,
            P_target=PR * self.P,
        )

        out._set_static_equal_total()
        return out

    def compress_real_eta_isentropic(self, PR, out, eta_is, W_out = None):

        self.compress_isentropic(PR, out, W_total=W_out)

        H1 = self.H_total

        # in case mass is given (e.g., for a compressor with bleed, fan core or duct flow etc.), 
        # set the output mass by scaling from self
        if W_out is not None:
            H1 = H1 * W_out/self.W
        
        H2s = out.H_total

        H2_target = H1 + (H2s - H1) / eta_is

        out.update_HP(
            H_target=H2_target,
            P_target=PR * self.P,
        )

        out._set_static_equal_total()

    def compress_real_polytropic_eta_fast(self, PR: float,
                                out: "TFlowState",
                                eta_poly: float,
                                W_out = None):
        if PR <= 0.0:
            raise ValueError("PR must be > 0")
        if not (0.0 < eta_poly <= 1.0):
            raise ValueError("eta_poly must be in (0, 1]")

        out.copy_from(self)

        if W_out is not None:
            out.scale_mass(W_out/self.W)

        R = ct.gas_constant / self.gas_q.mean_molecular_weight
        Sout = self.gas_q.entropy_mass + R * math.log(PR) * (1.0 / eta_poly - 1.0)
        Pout = self.P * PR

        out.gas_q.SPX = Sout, Pout, self.X

        # gas-only bookkeeping
        out.m_dry = out.W_gas * (1.0 - out._gas_h2o_mass_fraction())
        out.m_total_water = out.m_vap

        out._set_static_equal_total()

    def compress_real_polytropic_eta(self, PR: float, out: "TFlowState",
                            eta_poly: float, tmp: "TFlowState" = None, n_steps: int = 20,
                            W_out = None):

        """
        Polytropic compressor model.

        Two modes are used:

        1) FAST GAS-ONLY MODE
        Used when no liquid-water physics is active.
        Uses the analytical entropy-rise relation:

            ds = R * ln(PR) * (1/eta_poly - 1)

        This is very fast and works well for ideal-gas mixtures
        with fixed composition.

        2) STEPWISE WET MODE
        Used when liquid water may evaporate/condense during compression.

        The compression is divided into many small pressure steps.
        For each step:

            a) compute ideal isentropic step
            b) determine ideal enthalpy rise
            c) scale enthalpy rise using eta_poly
            d) perform real HP flash

        This properly handles:
            - liquid evaporation
            - changing vapor fraction
            - real thermodynamic path effects

        Parameters
        ----------
        pressure_ratio : float
            Compressor pressure ratio Pout / Pin

        out : TGaspathCondition
            Output condition object

        eta_poly : float
            Polytropic efficiency (0 < eta_poly <= 1)

        tmp : TGaspathCondition
            Temporary working object used only for wet stepwise mode

        n_steps : int
            Number of pressure increments in wet mode
        """

        import math
        import cantera as ct

        # -------------------------------------------------------------
        # basic checks
        # -------------------------------------------------------------

        if PR <= 0.0:
            raise ValueError("PR must be > 0")

        if not (0.0 < eta_poly <= 1.0):
            raise ValueError("eta_poly must be in (0,1]")

        # -------------------------------------------------------------
        # FAST GAS-ONLY MODE
        # -------------------------------------------------------------
        #
        # Use analytical entropy relation:
        #
        #   s2 = s1 + R ln(PR) (1/eta_poly - 1)
        #
        # Then solve:
        #
        #   gas.SPX = s2, P2, X
        #
        # This is much faster than stepwise integration.
        #
        # Only valid if:
        #   - no active liquid phase
        #   - no significant composition changes
        #
        # -------------------------------------------------------------

        if (not self._use_liquid_model()) or (self.m_liq <= self.LIQ_ABS_TOL):

            # initialize output from inlet state
            out.copy_from(self)

            if W_out is not None:
                out.scale_mass(W_out/self.W)

            # gas constant of current mixture [J/kg/K]
            R = ct.gas_constant / self.gas_q.mean_molecular_weight

            # outlet pressure
            Pout = self.P * PR

            # entropy rise due to finite polytropic efficiency
            Sout = (
                self.gas_q.entropy_mass
                + R * math.log(PR) * (1.0 / eta_poly - 1.0)
            )

            # solve final gas state at:
            #   specified entropy
            #   specified pressure
            out.gas_q.SPX = Sout, Pout, self.X

            # recompute bookkeeping quantities
            out.m_dry = out.W_gas * (1.0 - out._gas_h2o_mass_fraction())

            # gas-only mode → all water remains vapor
            out.m_total_water = out.m_vap

            # by default static = total
            out._set_static_equal_total()

            return out

        # -------------------------------------------------------------
        # WET / LIQUID-ACTIVE MODE
        # -------------------------------------------------------------
        #
        # We cannot use the analytical entropy formula anymore because:
        #
        #   - evaporation/condensation changes entropy
        #   - latent heat effects appear
        #   - vapor fraction changes during compression
        #
        # Therefore:
        #
        #   Divide compression into many small pressure increments.
        #
        # For each increment:
        #
        #   1) compute ideal isentropic step
        #   2) compute ideal enthalpy rise
        #   3) scale enthalpy rise using eta_poly
        #   4) perform real HP flash
        #
        # -------------------------------------------------------------

        if tmp is None:
            raise ValueError(
                "tmp TGaspathCondition required for wet polytropic compression"
            )

        # initialize outlet from inlet
        out.copy_from(self)

        if W_out is not None:
            out.scale_mass(W_out/self.W)


        # inlet and outlet pressures
        P1 = self.P
        P2 = PR * P1

        # -------------------------------------------------------------
        # logarithmic pressure stepping
        #
        # logarithmic spacing is physically better because
        # compressors behave approximately exponentially in pressure
        # -------------------------------------------------------------

        for i in range(1, n_steps + 1):

            # target pressure for this increment
            Pout = P1 * (P2 / P1) ** (i / n_steps)

            # current real-state enthalpy and entropy
            H_in = out.H_total


            S_in = out.S_total

            # ---------------------------------------------------------
            # IDEAL SMALL STEP
            # ---------------------------------------------------------
            #
            # Compute ideal isentropic endpoint for this small step.
            #
            # tmp becomes:
            #
            #   same entropy
            #   slightly higher pressure
            #
            # ---------------------------------------------------------

            tmp.copy_from(out)

            tmp.update_SP(
                S_target=S_in,
                P_target=Pout,
            )

            # ideal enthalpy rise of this increment
            dH_is = tmp.H_total - H_in

            # ---------------------------------------------------------
            # REAL SMALL STEP
            # ---------------------------------------------------------
            #
            # Polytropic efficiency definition:
            #
            #   eta_poly = dH_is / dH_real
            #
            # therefore:
            #
            #   dH_real = dH_is / eta_poly
            #
            # ---------------------------------------------------------

            dH_real = dH_is / eta_poly

            # perform real thermodynamic flash
            out.update_HP(
                H_target=H_in + dH_real,
                P_target=Pout,
            )

        # default static = total
        out._set_static_equal_total()

        return out

    def compress_real_eta(self,
                      *,
                      PR: float,
                      out: "TFlowState",
                      eta: float,
                      Polytropic_Eta: bool = False,
                      tmp: "TFlowState" = None,
                      n_steps: int = 20,
                      W_out = None):

        H_total_0 = self.H_total
        if W_out is not None:
            H_total_0 = H_total_0 * W_out/self.W

        if Polytropic_Eta:
            self.compress_real_polytropic_eta(
                PR=PR,
                out=out,
                eta_poly=eta,
                tmp=tmp,
                n_steps=n_steps,
                W_out=W_out
            )
        else:
            self.compress_real_eta_isentropic(
                PR=PR,
                out=out,
                eta_is=eta,
                W_out=W_out
            )

        # PW = out.H_total - self.H_total
        PW = out.H_total - H_total_0
        return out, PW

    # ------------------------------------------------------------------
    # GSP-style wet isentropic compression
    # ------------------------------------------------------------------
    # Original TGasConditions method: equilibrium compression
    # vs.
    # GSP method                    : post-compression evaporation correction
    # 
    # The difference is fundamental:
    # In original TGasConditions you solve:
        # S_total(T,P,m_vap,m_liq) = constant
        # while simultaneously enforcing:
            # m_vap(T,P)
            # m_liq(T,P)
        # through saturation equilibrium.
    # Physically this means:
        # Compression
        # ↓
        # Temperature rises
        # ↓
        # Some liquid evaporates immediately
        # ↓
        # Evaporation cools the gas
        # ↓
        # Compression continues
        # ↓
        # More evaporation
        # ↓
        # ...
    # Evaporation occurs continuously during the compression process.
    # This gives the lowest outlet temperature.

    # GSP method, GSP effectively assumes:
    # Step 1:
        # Compress gas + initial vapor only
        # (no evaporation during compression)
    # Step 2:
        # At outlet T,P determine how much water can evaporate
    # Step 3:
        # Subtract evaporation energy
    # Step 4:
        # Recompute outlet temperature
        # Thus the gas is first compressed hotter.
        # Only afterwards does evaporation cool it down.
    # This yields:
        # T_GSP > T_equilibrium
        # which is exactly what you observe.
        # Thermodynamic analogy
        # This is similar to intercooling:
    # Equilibrium model : compress while cooling continuously
    # GSP model         : compress adiabatically then apply cooling afterwards
    # The latter always produces a higher outlet temperature.
    
    # Which is physically correct?
    # For infinitely small droplets with perfect mixing and infinitely fast evaporation TGasConditions equilibrium method is correct.
    # For larger droplets with finite evaporation times the GSP method may actually be closer to reality.
    # For Real engines it lies somewhere in between:
    # instantaneous equilibrium
    # <
    # real engine
    # <
    # post-compression evaporation
    # Why only 10 K difference?
    # My recommendation
    # Keep both:
    # wet_model = "equilibrium"     # current TGasConditions
    # wet_model = "gsp"             # legacy GSP approach
    # Then:
    # Validation against GSP → "gsp"
    # New simulations → "equilibrium"
    # This gives backwards compatibility while preserving the more rigorous model that Cantera makes possible.

    def _pure_h2o_gas_h(self, T: float, P: float) -> float:
        """
        Pure gas-phase H2O enthalpy [J/kg] using the current Cantera gas mechanism.
        """
        saved_T = self.T
        saved_P = self.P
        saved_X = self.gas_q.X
        saved_m = self.gas_q.mass

        try:
            self.gas_q.TPX = T, P, {"H2O": 1.0}
            return self.gas_q.enthalpy_mass
        finally:
            self.gas_q.TPX = saved_T, saved_P, saved_X
            self.gas_q.mass = saved_m

    #  Note that we can only use Cantera ct.water for Latent heat as the absolute enthalpy reference
    #  of the gas mchanisme will not match that of ct.water in Cantera
    def _water_latent_heat(self, T: float) -> float:
        """
        Latent heat of vaporization [J/kg] from ct.Water.
        """
        w = self._water()

        w.TQ = T, 0.0
        h_liq = w.enthalpy_mass

        w.TQ = T, 1.0
        h_vap = w.enthalpy_mass

        return h_vap - h_liq


    def _liquid_water_h_aligned(self, T: float, P: float) -> float:
        """
        Liquid-water enthalpy [J/kg], aligned to the gas-phase H2O
        reference enthalpy of the Cantera gas mechanism.
        """
        return self._pure_h2o_gas_h(T, P) - self._water_latent_heat(T)
   
    def compress_isentropic_gsp_wet(self,
                                    pressure_ratio: float,
                                    out: "TFlowState"):
        """
        GSP-compatible wet isentropic compression.

        Steps:
        1) Compress gas + existing vapor only isentropically.
        2) Determine how much liquid water evaporates at outlet P,T.
        3) Account for inlet liquid enthalpy on a Cantera-compatible basis.
        4) Recalculate final gas state at outlet pressure with extra vapor.
        """

        if pressure_ratio <= 0.0:
            raise ValueError("pressure_ratio must be > 0")

        out.copy_from(self)

        P2 = self.P * pressure_ratio

        # 1) Compress gas phase only isentropically
        s1_gas = self.gas_q.entropy_mass
        X1 = self.gas_q.X
        m_gas_old = self.gas_q.mass

        out.gas_q.SPX = s1_gas, P2, X1
        out.gas_q.mass = m_gas_old

        T2_gas = out.T
        H2_gas_before_evap = out.gas_q.enthalpy

        # 2) Determine vapor/liquid split at compressed gas T/P
        dry_basis_X = self._current_dry_basis_X()

        st_split = out._state_at_TP_with_split(
            T=T2_gas,
            P=P2,
            dry_basis_X=dry_basis_X,
            m_dry=self.m_dry,
            m_total_water=self.m_total_water,
        )

        m_vap_old = self.m_vap
        m_liq_old = self.m_liq

        m_vap_eq = st_split["m_vap"]

        m_evap = max(0.0, m_vap_eq - m_vap_old)
        m_evap = min(m_evap, m_liq_old)

        m_vap_new = m_vap_old + m_evap
        m_liq_new = m_liq_old - m_evap

        if m_liq_new <= self.LIQ_ABS_TOL:
            m_liq_new = 0.0

        m_gas_new = self.m_dry + m_vap_new

        # 3) Build gas composition after evaporation
        out.gas_q.TPX = T2_gas, P2, dry_basis_X
        mw_dry = out.gas_q.mean_molecular_weight / 1000.0

        n_dry = self.m_dry / mw_dry
        n_vap = m_vap_new / c.MW_H2O

        x_h2o = n_vap / (n_dry + n_vap) if (n_dry + n_vap) > 0.0 else 0.0

        X_new = {
            sp: xi * (1.0 - x_h2o)
            for sp, xi in dry_basis_X.items()
        }
        X_new["H2O"] = x_h2o

        # 4) Energy bookkeeping on aligned reference basis
        #
        # H2_gas_before_evap contains:
        #   compressed dry gas + old vapor
        #
        # The old liquid was not part of gas compression, so add its inlet
        # liquid enthalpy on a reference basis aligned with gas H2O.
        #
        # If liquid remains after evaporation, subtract its final liquid enthalpy.
        #
        # The remaining target is the final GAS enthalpy for:
        #   dry gas + old vapor + newly evaporated vapor
        #
        H_liq_in = m_liq_old * out._liquid_water_h_aligned(self.T, self.P)
        H_liq_out = m_liq_new * out._liquid_water_h_aligned(T2_gas, P2)

        H_target_gas = H2_gas_before_evap + H_liq_in - H_liq_out

        # 5) Final gas HP solve at outlet pressure and new composition
        out.gas_q.TPX = T2_gas, P2, X_new
        out.gas_q.mass = m_gas_new
        out.gas_q.HP = H_target_gas / m_gas_new, P2

        # 6) Update water bookkeeping
        out.m_dry = self.m_dry
        out.m_total_water = m_vap_new + m_liq_new

        if hasattr(out, "_m_vap"):
            out._m_vap = m_vap_new
        if hasattr(out, "_m_liq"):
            out._m_liq = m_liq_new

        out._set_static_equal_total()

        return out


    def compress_real_eta_gsp_wet(self,
                                pressure_ratio: float,
                                out: "TFlowState",
                                eta_c: float):

        if not (0.0 < eta_c <= 1.0):
            raise ValueError("eta_c must be in (0, 1]")

        # Ideal GSP-style wet compression first
        self.compress_isentropic_gsp_wet(pressure_ratio, out)

        H1 = self.H_total
        H2s = out.H_total

        H2_target = H1 + (H2s - H1) / eta_c

        # Use ideal result as initial guess, solve final total HP
        out.update_HP(
            H_target=H2_target,
            P_target=self.P * pressure_ratio,
        )

        out._set_static_equal_total()
        return out

    # ------------------------------------------------------------------
    # turbine expansion
    # ------------------------------------------------------------------

    def expand_real_eta_isentropic(self,
                                PR: float,
                                out: "TFlowState",
                                eta_is: float):
        """
        Real turbine expansion using isentropic efficiency.

        PR = Pin / Pout

        eta_t = (H1 - H2_real) / (H1 - H2s)
        """

        if PR <= 1.0:
            raise ValueError("PR must be > 1 for turbine expansion")

        if not (0.0 < eta_is <= 1.0):
            raise ValueError("eta_is must be in (0, 1]")

        Pout = self.P / PR

        # ideal isentropic outlet
        out.copy_from(self)
        out.update_SP(
            S_target=self.S_total,
            P_target=Pout,
        )

        H1 = self.H_total
        H2s = out.H_total

        # turbine efficiency:
        # actual enthalpy drop = eta * ideal enthalpy drop
        H2_target = H1 - eta_is * (H1 - H2s)

        # use ideal state as initial guess, then solve real HP outlet
        out.update_HP(
            H_target=H2_target,
            P_target=Pout,
        )

        out._set_static_equal_total()
        return out

    def expand_real_polytropic_eta(self,
                                PR: float,
                                out: "TFlowState",
                                eta_poly: float,
                                tmp: "TFlowState" = None,
                                n_steps: int = 20):
        """
        Polytropic turbine expansion.

        pressure_ratio = Pin / Pout

        For each small pressure step:
            1) compute ideal isentropic expansion
            2) ideal enthalpy drop = H_in - H_is
            3) real enthalpy drop = eta_poly * ideal drop
            4) solve real HP state
        """

        if PR <= 1.0:
            raise ValueError("pressure_ratio must be > 1 for turbine expansion")

        if not (0.0 < eta_poly <= 1.0):
            raise ValueError("eta_poly must be in (0, 1]")

        if tmp is None:
            raise ValueError("tmp TGaspathCondition required for polytropic expansion")

        out.copy_from(self)

        P1 = self.P
        P2 = P1 / PR

        for i in range(1, n_steps + 1):
            # logarithmic pressure decrease
            Pstep = P1 * (P2 / P1) ** (i / n_steps)

            H_in = out.H_total
            S_in = out.S_total

            # ideal small expansion step
            tmp.copy_from(out)
            tmp.update_SP(
                S_target=S_in,
                P_target=Pstep,
            )

            # ideal enthalpy drop
            dH_is_drop = H_in - tmp.H_total

            # actual turbine enthalpy drop
            dH_real_drop = eta_poly * dH_is_drop

            out.update_HP(
                H_target=H_in - dH_real_drop,
                P_target=Pstep,
            )

        out._set_static_equal_total()
        return out

    def expand_real_eta(self,
                        *,
                        PR: float,
                        out: "TFlowState",
                        eta: float,
                        polytropic_eta: bool = False,
                        tmp: "TFlowState" = None,
                        n_steps: int = 20):
        """
        Turbine expansion.

        PR = Pin / Pout
        eta = isentropic or polytropic turbine efficiency

        Returns:
            out : outlet state
            PW  : turbine power output on this mass basis [W if mass is kg/s, J if mass is kg]
        """

        if PR <= 1.0:
            raise ValueError("For turbine expansion, PR should be > 1, where PR = Pin / Pout")

        if not (0.0 < eta <= 1.0):
            raise ValueError(f"eta must be in (0, 1) in expand_real_eta at station {self.station_nr}")

        if polytropic_eta:
            self.expand_real_polytropic_eta(
                PR=PR,
                out=out,
                eta_poly=eta,
                tmp=tmp,
                n_steps=n_steps,
            )
        else:
            self.expand_real_eta_isentropic(
                PR=PR,
                out=out,
                eta_is=eta,
            )

        # turbine power output is positive
        PW = self.H_total - out.H_total
        return out, PW

    # ------------------------------------------------------------------
    # combustor mixture equilibration
    # ------------------------------------------------------------------

    def equilibrate_quantity(self) -> None:
        # Equilibrate the combustor mixture at constant enthalpy and pressure.
        # The underlying Cantera Solution is equilibrated first. Since changes
        # made directly to gas_q.phase are not automatically reflected in the
        # Quantity state, the equilibrated T, P, and Y are explicitly copied
        # back into gas_q

        gas_q = self.gas_q
        phase = gas_q.phase

        phase.equilibrate("HP", solver="auto", max_iter=2000)

        gas_q.TPY = phase.T, phase.P, phase.Y

    def equilibrate_combustor_mixture(
        self,
        collapse_liquid: bool = True,
    ) -> None:
        """
            Parameters
        ----------
        collapse_liquid : bool, default=True
            True:
                Convert any separately tracked liquid water into gas-phase H2O
                after equilibrium and disable liquid-water tracking.

            False:
                Retain liquid-water tracking and repartition vapor/liquid water
                at the equilibrated state.
        """

        liq_old = self.m_liq

        self.equilibrate_quantity()

        m_gas = self.gas_q.mass
        y_h2o = self.gas_q.Y[self.i_H2O]

        self.m_dry = m_gas * (1.0 - y_h2o)
        self.m_total_water = m_gas * y_h2o + liq_old

        if collapse_liquid:
            self.disable_liquid_model(collapse=True)
        elif self.enable_liquid_water:
            self.repartition_at_TP(self.T, self.P)

        self._set_static_equal_total()

    # ------------------------------------------------------------------
    # reporting
    # ------------------------------------------------------------------

    def summary(self):
        return {
            "T": self.T,
            "P": self.P,
            "Ts": self.Ts,
            "Ps": self.Ps,
            "Mach": self.Mach,
            "V": self.V,
            "A": self.A,
            "m_gas": self.W_gas,
            "m_vap": self.m_vap,
            "m_liq": self.m_liq,
            "m_total_water": self.m_total_water,
            "RH_gas": self.RH_gas,
            "H_total": self.H_total,
            "S_total": self.S_total,
            "enable_liquid_water": self.enable_liquid_water
        }