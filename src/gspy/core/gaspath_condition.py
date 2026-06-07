from __future__ import annotations
import math
import cantera as ct
from scipy.optimize import root_scalar
from scipy.optimize import root

class TGaspathCondition:
    """
    Gas-path station condition with:
      - gas_q: Cantera Quantity containing the full GAS phase, including H2O vapor
      - m_total_water: total water inventory [kg] = vapor + liquid
      - m_dry: dry-gas mass [kg] = all gas species except H2O vapor

    Only LIQUID water is outside the Cantera gas phase.
    Water vapor always remains inside gas_q.
    """

    T_WATER_TRIPLE = 273.16
    T_WATER_CRITICAL = 647.096
    MW_H2O = 18.01528e-3

    LIQ_ABS_TOL = 1e-9
    LIQ_REL_TOL = 1e-4   # 0.01% of water inventory; adjust to e.g. 1e-3 or 1e-5 if needed
    RH_TOL = 1e-8    
    
    WATER_TOL = 1e-12

    # default liquid model settings: can be overridden in constructor or via methods
    # def_enable_liquid_model: bool = False
    # def_force_gas_only: bool = True
    def_enable_liquid_water : bool = True

    def_debug_flash: bool = False

    def __init__(self,
                 gas: ct.Solution,
                 gas_mass: float,
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
                 enable_liquid_water: bool = def_enable_liquid_water,

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
                self.mass * self._gas_h2o_mass_fraction()
                + float(m_liq)
            )
        else:
            self.m_total_water = float(m_total_water)

        # Final consistency check for gas-only mode
        if not self.enable_liquid_water:
            m_vap = self.mass * self._gas_h2o_mass_fraction()

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
    def mass(self):
        return self.gas_q.mass

    @mass.setter
    def mass(self, value):
        liq_old = self.m_liq
        self.gas_q.mass = float(value)
        self.m_dry = self.mass * (1.0 - self._gas_h2o_mass_fraction())
        self.m_total_water = self.m_vap + liq_old
        # if self.force_gas_only:
        if not self.enable_liquid_water:
            self.m_total_water = self.m_vap

    @property
    def m_vap(self):
        mv = self.mass * self._gas_h2o_mass_fraction()
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
            self.LIQ_REL_TOL * max(self.m_total_water, self.mass, 1e-30),
        )
        return 0.0 if m <= tol else m

    @property
    def has_condensed_water(self):
        return self.m_liq > self.LIQ_ABS_TOL

    @property
    def x_H2O_gas(self):
        return self.X.get("H2O", 0.0)

    @property
    def m_total(self):
        return self.mass + self.m_liq

    @property
    def h_gas(self):
        return self.gas_q.enthalpy_mass

    @property
    def s_gas(self):
        return self.gas_q.entropy_mass

    @property
    def H_total(self):
        if not self._use_liquid_model():
            return self.gas_q.enthalpy
        return self.gas_q.enthalpy + self.m_liq * self._sat_liquid_h(self.T)

    @property
    def S_total(self):
        if not self._use_liquid_model():
            return self.gas_q.entropy
        return self.gas_q.entropy + self.m_liq * self._sat_liquid_s(self.T)

    @property
    def p_saturation(self):
        if self.T >= self.T_WATER_CRITICAL:
            return self.P
        if self.T <= self.T_WATER_TRIPLE:
            raise ValueError(
                f"T={self.T:g} K is below the liquid-water triple point for this model."
            )
        w =self._water()
        w.TQ = self.T, 1.0
        return w.P_sat

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

    def _collapse_to_gas_only(self):
        self.m_total_water = self.m_vap

    def disable_liquid_model(self, collapse=True):
        # self.enable_liquid_model = False
        # self.force_gas_only = True
        self.enable_liquid_water = False
        if collapse:
            self._collapse_to_gas_only()

    def maybe_disable_liquid_model(self, T_threshold=700.0):
        if self.T >= T_threshold and self.m_liq <= self.LIQ_ABS_TOL:
            self.disable_liquid_model(collapse=True)

    # ------------------------------------------------------------------
    # constructors
    # ------------------------------------------------------------------
    @classmethod
    def create_empty(cls, gas):
        # gas = ct.Solution(mechanism)
        return cls(gas=gas, gas_mass=1.0)


    @classmethod
    def from_RH(cls, gas: ct.Solution, gas_mass: float, T: float, P: float,
                RH: float, dry_X: dict,
                # enable_liquid_model: bool = def_enable_liquid_model,
                # force_gas_only: bool = def_force_gas_only,
                enable_liquid_water: bool = def_enable_liquid_water,
                debug_flash: bool = def_debug_flash):
        obj = cls(
            gas=gas,
            gas_mass=gas_mass,
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
    def from_vol_pct(cls, gas: ct.Solution, gas_mass: float, T: float, P: float,
                     H2O_vol_pct: float, dry_X: dict,
                     enable_liquid_water: bool = def_enable_liquid_water,
                     debug_flash: bool = def_debug_flash):
        obj = cls(
            gas=gas,
            gas_mass=gas_mass,
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
    def from_mass_pct(cls, gas: ct.Solution, gas_mass: float, T: float, P: float,
                      H2O_mass_pct: float, dry_Y: dict,
                      enable_liquid_water: bool = def_enable_liquid_water,
                      debug_flash: bool = def_debug_flash):
        obj = cls(
            gas=gas,
            gas_mass=gas_mass,
            m_liq=0.0,
            enable_liquid_water=enable_liquid_water,
            debug_flash=debug_flash,
        )
        obj._initialize_humidity(
            mode="mass_pct",
            value=H2O_mass_pct,
            T=T,
            P=P,
            dry_comp=dry_Y,
            comp_basis="Y",
        )
        return obj

    def copy_from(self, other: "TGaspathCondition"):
        self.gas_q.TPX = other.gas_q.T, other.gas_q.P, other.gas_q.X
        self.gas_q.mass = other.gas_q.mass

        self.m_dry = other.m_dry
        self.m_total_water = other.m_total_water
        # self.enable_liquid_model = other.enable_liquid_model
        # self.force_gas_only = other.force_gas_only
        self.enable_liquid_water = other.enable_liquid_water
        self.Ts = other.Ts
        self.Ps = other.Ps
        self.Mach = other.Mach
        self.V = other.V
        self.A = other.A
        self.rhos = other.rhos
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
            self._collapse_to_gas_only()
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

            self.m_dry = self.mass * (1.0 - self._gas_h2o_mass_fraction())
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

            self.m_dry = self.mass * (1.0 - self._gas_h2o_mass_fraction())
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
        self._set_energy_state_with_composition("S", "X", s, P, X)

    @property
    def SPY(self):
        raise AttributeError("SPY is write-only")

    @SPY.setter
    def SPY(self, args):
        s, P, Y = args
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
            "vol_pct"
            "mass_pct"
        """

        if gas_mass is not None:
            self.gas_q.mass = gas_mass

        if humidity_mode == "dry":
            if dry_X is None:
                raise ValueError("dry_X required for dry gas")
            self.gas_q.TPX = T, P, self._normalize_without_h2o(dry_X)
            self.m_dry = self.mass
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

        elif humidity_mode == "mass_pct":
            if dry_Y is None:
                raise ValueError("dry_Y required for mass_pct")
            self._initialize_humidity(
                mode="mass_pct",
                value=humidity_value,
                T=T,
                P=P,
                dry_comp=dry_Y,
                comp_basis="Y",
            )

        else:
            raise ValueError("humidity_mode must be 'dry', 'RH', 'vol_pct', or 'mass_pct'")

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
            "mass": self.mass,
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


    def repartition_at_TP(self, T: float, P: float):
        """
        Repartition total water into gas vapor + external liquid at fixed T,P.
        Conserves m_dry and m_total_water.
        """
        if not self._has_water():
            self.gas_q.TP = T, P
            self.m_total_water = 0.0
            return self._quick_state_dict()

        if not self._use_liquid_model():
            self.gas_q.TP = T, P
            self._collapse_to_gas_only()
            return self._quick_state_dict()

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
            self.gas_q.HP = H_target / self.mass, P_target
            self.m_total_water = 0.0
            return self._quick_state_dict()

        if not self._use_liquid_model():
            self.gas_q.HP = H_target / self.mass, P_target
            self._collapse_to_gas_only()
            return self._quick_state_dict()

        if T_low is None:
            T_low = max(self.T, self.T_WATER_TRIPLE + 1.0)
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
            self.gas_q.SP = S_target / self.mass, P_target
            self.m_total_water = 0.0
            return self._quick_state_dict()

        if not self._use_liquid_model():
            self.gas_q.SP = S_target / self.mass, P_target
            self._collapse_to_gas_only()
            return self._quick_state_dict()

        if T_low is None:
            T_low = max(self.T, self.T_WATER_TRIPLE + 1.0)
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
        self.gas_q = ct.Quantity(phase, mass=self.mass)

        liq_old = self.m_liq
        self.m_dry = self.mass * (1.0 - self._gas_h2o_mass_fraction())
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

        self.m_dry = self.mass * (1.0 - self._gas_h2o_mass_fraction())
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
        self.gas_q = ct.Quantity(phase, mass=self.mass)

        self.m_dry = self.mass * (1.0 - self._gas_h2o_mass_fraction())
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

        self.m_dry = self.mass * (1.0 - self._gas_h2o_mass_fraction())
        self.m_total_water = self.m_vap + liq_old

        if not self.enable_liquid_water:
            self._collapse_to_gas_only()
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

        self.m_dry = self.mass * (1.0 - self._gas_h2o_mass_fraction())
        self.m_total_water = self.m_vap + liq_old

        if not self.enable_liquid_water:
            if mode == "H":
                self.gas_q.HP = value, P
            elif mode == "S":
                self.gas_q.SP = value, P
            else:
                raise ValueError("mode must be 'H' or 'S'")
            self._collapse_to_gas_only()
            return

        if mode == "H":
            target = self.mass * value + liq_old * self._sat_liquid_h(self.T)
            self.update_HP(H_target=target, P_target=P)
        elif mode == "S":
            target = self.mass * value + liq_old * self._sat_liquid_s(self.T)
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
        """
        Decide what to do if requested water exceeds vapor saturation.
        """

        oversaturated = x_req > x_sat + 1e-12

        if not oversaturated:
            return x_req

        if self.enable_liquid_water:
            return x_req

        if not self.enable_liquid_water:
            # gas-only model: clamp to saturation, discard excess intentionally
            return min(x_req, x_sat)

        raise ValueError(
            f"{mode}={value} gives oversaturated air, but enable_liquid_water=False. "
            "Enable liquid water model, reduce humidity, or set enable_liquid_water=True to "
            "explicitly clamp/discard excess water."
        )

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

        elif mode == "mass_pct":
            if comp_basis != "Y":
                raise ValueError("mass_pct requires dry mass fractions")

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
                self.m_dry = self.mass * (1.0 - self._gas_h2o_mass_fraction())

                # total water from original requested mass fraction
                self.m_total_water = self.mass * y_req

                if self.enable_liquid_water:
                    self.repartition_at_TP(T, P)

        else:
            raise ValueError("mode must be 'RH', 'vol_pct', or 'mass_pct'")

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
    #     self.m_total_water = n_h2o_total * self.MW_H2O
    #     if not self.enable_liquid_water:
    #         self._collapse_to_gas_only()
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
        self.m_dry = self.mass * (1.0 - self._gas_h2o_mass_fraction())

        mw_dry = self._mean_mw_of_composition(T, P, dry_basis_X)
        n_dry = self.m_dry / mw_dry
        n_h2o_total = x_req / max(1.0 - x_req, 1e-15) * n_dry
        self.m_total_water = n_h2o_total * self.MW_H2O

        # Clean up tiny artificial liquid at RH≈100%
        m_liq_raw = self.m_total_water - self.m_vap
        liq_tol = max(
            self.LIQ_ABS_TOL,
            self.LIQ_REL_TOL * max(self.m_total_water, self.mass, 1e-30),
        )

        # if m_liq_raw <= liq_tol:
        #     self.m_total_water = self.m_vap
        if (m_liq_raw <= liq_tol) or (not self.enable_liquid_water):
            self._collapse_to_gas_only()

    # ------------------------------------------------------------------
    # pure thermodynamic helpers
    # ------------------------------------------------------------------

    def _gas_h2o_mass_fraction(self):
        return self.Y.get("H2O", 0.0)

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

    def _sat_water_mole_fraction(self, T, P):
        if T <= self.T_WATER_TRIPLE:
            raise ValueError(
                f"T={T:g} K is below the liquid-water triple point for this model."
            )

        if T >= self.T_WATER_CRITICAL:
            return 1.0

        w =self._water()
        w.TQ = T, 1.0
        p_sat = w.P_sat

        if p_sat >= P:
            return 1.0

        return max(p_sat / P, 0.0)

    def _sat_liquid_h(self, T):
        if T <= self.T_WATER_TRIPLE:
            raise ValueError(
                f"T={T:g} K is below the liquid-water triple point for this model."
            )

        if T >= self.T_WATER_CRITICAL:
            return 0.0

        w =self._water()
        w.TQ = T, 0.0
        return w.enthalpy_mass

    def _sat_liquid_s(self, T):
        if T <= self.T_WATER_TRIPLE:
            raise ValueError(
                f"T={T:g} K is below the liquid-water triple point for this model."
            )

        if T >= self.T_WATER_CRITICAL:
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
            "m_gas": self.mass,
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
                m_vap_sat = n_vap_sat * self.MW_H2O
                m_vap = min(m_total_water, m_vap_sat)
                m_liq = max(0.0, m_total_water - m_vap)

            if m_liq <= self.LIQ_ABS_TOL:
                m_liq = 0.0
                m_vap = m_total_water

            n_vap = m_vap / self.MW_H2O
            x_h2o = n_vap / (n_dry + n_vap) if (n_dry + n_vap) > 0.0 else 0.0

            Xgas = {sp: xi * (1.0 - x_h2o) for sp, xi in dry_basis_X.items()}
            Xgas["H2O"] = x_h2o

            self.gas_q.TPX = T, P, Xgas

            h_gas = self.gas_q.enthalpy_mass
            s_gas = self.gas_q.entropy_mass
            m_gas = m_dry + m_vap

            h_liq = self._sat_liquid_h(T) if m_liq > 0.0 else 0.0
            s_liq = self._sat_liquid_s(T) if m_liq > 0.0 else 0.0

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

    def _flash_HP_or_SP(self, target, P_target, mode,
                        T_low, T_high, tol, maxiter):
        # _flash_HP_or_SP(...) is solving:
        # Given:
        #     H_target (or S_target)
        #     P_target
        #     m_dry
        #     m_total_water
        # Find:
        #     T
        # such that:
        # H_total(T,P) = H_target or S_total(T,P) = S_target
        # where:
        # H_total = H_gas(T,P,x_H2O) + H_liquid(T,m_liq)
        # and simultaneously: m_total_water = m_vap + m_liq
        # with vapor-liquid equilibrium enforced.

        if mode not in ("H", "S"):
            raise ValueError("mode must be 'H' or 'S'")

        dry_basis_X = self._current_dry_basis_X()
        m_dry = self.m_dry
        m_total_water = self.m_total_water
        T_min = self.T_WATER_TRIPLE + 1.0

        def residual(T):
            st = self._state_at_TP_with_split(
                T=T,
                P=P_target,
                dry_basis_X=dry_basis_X,
                m_dry=m_dry,
                m_total_water=m_total_water,
            )
            return (st["H_total"] if mode == "H" else st["S_total"]) - target

        f_low = residual(T_low)
        f_high = residual(T_high)

        if self.debug_flash:
            print(f"_flash {mode}: f({T_low})={f_low:.6e}, f({T_high})={f_high:.6e}")

        if abs(f_low) < tol:
            return self._state_at_TP_with_split(T_low, P_target, dry_basis_X, m_dry, m_total_water)
        if abs(f_high) < tol:
            return self._state_at_TP_with_split(T_high, P_target, dry_basis_X, m_dry, m_total_water)

        if f_low * f_high > 0.0:
            if f_low > 0.0 and f_high > 0.0:
                T2 = T_low
                for _ in range(20):
                    T_new = max(T_min, T2 - 0.5 * (T_high - T_low))
                    if T_new <= T_min + 1e-6:
                        break
                    f_new = residual(T_new)
                    if self.debug_flash:
                        print(f"  expand down: f({T_new})={f_new:.6e}")
                    if abs(f_new) < tol:
                        return self._state_at_TP_with_split(T_new, P_target, dry_basis_X, m_dry, m_total_water)
                    if f_new * f_high < 0.0:
                        T_low, f_low = T_new, f_new
                        break
                    T2 = T_new
                    T_high, f_high = T_low, f_low
            elif f_low < 0.0 and f_high < 0.0:
                T2 = T_high
                for _ in range(20):
                    T2 *= 1.5
                    f2 = residual(T2)
                    if self.debug_flash:
                        print(f"  expand up: f({T2})={f2:.6e}")
                    if abs(f2) < tol:
                        return self._state_at_TP_with_split(T2, P_target, dry_basis_X, m_dry, m_total_water)
                    if f_low * f2 < 0.0:
                        T_high, f_high = T2, f2
                        break
            else:
                raise ValueError("Unexpected bracketing state")

            if f_low * f_high > 0.0:
                raise ValueError(
                    f"Could not bracket flash root: "
                    f"f({T_low})={f_low:.6e}, f({T_high})={f_high:.6e}"
                )

        sol = root_scalar(
            residual,
            bracket=(T_low, T_high),
            method="toms748",
            xtol=tol,
            maxiter=maxiter,
        )

        if not sol.converged:
            raise RuntimeError(f"Flash solver did not converge: {sol.flag}")

        return self._state_at_TP_with_split(
            T=sol.root,
            P=P_target,
            dry_basis_X=dry_basis_X,
            m_dry=m_dry,
            m_total_water=m_total_water,
        )

    # ------------------------------------------------------------------
    # method to re ininitialize TGaspathCondition
    # ------------------------------------------------------------------
    def set_conditions_humidity(self, *, T, P, gas_mass=None,
                                humidity_mode=None, humidity_value=0.0,
                                dry_X=None, dry_Y=None):
        """
        Reinitialize this existing TGaspathCondition in-place.

        humidity_mode:
            None / "dry"
            "RH"
            "vol_pct"
            "mass_pct"
        """

        if gas_mass is not None:
            self.gas_q.mass = gas_mass

        if humidity_mode is None or humidity_mode == "dry":
            if dry_X is None:
                raise ValueError("dry_X required for dry initialization")
            dry_X = self._normalize_without_h2o(dry_X)
            self.gas_q.TPX = T, P, dry_X
            self.m_dry = self.mass
            self.m_total_water = 0.0
            self._set_static_equal_total()
            return self

        if humidity_mode == "RH":
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

        elif humidity_mode == "mass_pct":
            if dry_Y is None:
                raise ValueError("dry_Y required for mass_pct")
            self._initialize_humidity(
                mode="mass_pct",
                value=humidity_value,
                T=T,
                P=P,
                dry_comp=dry_Y,
                comp_basis="Y",
            )

        else:
            raise ValueError("humidity_mode must be None, 'dry', 'RH', 'vol_pct', or 'mass_pct'")

        self._set_static_equal_total()
        return self    

    # ------------------------------------------------------------------
    # convenience compressor helpers
    # ------------------------------------------------------------------
    def compress_isentropic(self, PR: float, out: "TGaspathCondition"):
        """
        Ideal compression:
        - total entropy gas + liquid conserved
        - target total pressure
        """
        out.copy_from(self)

        out.update_SP(
            S_target=self.S_total,
            P_target=PR * self.P,
        )

        out._set_static_equal_total()
        return out

    def compress_real_eta_isentropic(self, PR, out, eta_is):

        self.compress_isentropic(PR, out)

        H1 = self.H_total
        H2s = out.H_total

        H2_target = H1 + (H2s - H1) / eta_is

        out.update_HP(
            H_target=H2_target,
            P_target=PR * self.P,
        )

        out._set_static_equal_total()

    def compress_real_polytropic_eta_fast(self, PR: float,
                                out: "TGaspathCondition",
                                eta_poly: float):
        if PR <= 0.0:
            raise ValueError("PR must be > 0")
        if not (0.0 < eta_poly <= 1.0):
            raise ValueError("eta_poly must be in (0, 1]")

        out.copy_from(self)

        R = ct.gas_constant / self.gas_q.mean_molecular_weight
        Sout = self.gas_q.entropy_mass + R * math.log(PR) * (1.0 / eta_poly - 1.0)
        Pout = self.P * PR

        out.gas_q.SPX = Sout, Pout, self.X

        # gas-only bookkeeping
        out.m_dry = out.mass * (1.0 - out._gas_h2o_mass_fraction())
        out.m_total_water = out.m_vap

        out._set_static_equal_total()

    def compress_real_polytropic_eta(self, PR: float, out: "TGaspathCondition",
                            eta_poly: float, tmp: "TGaspathCondition" = None, n_steps: int = 20):

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
            out.m_dry = out.mass * (1.0 - out._gas_h2o_mass_fraction())

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
                      out: "TGaspathCondition",
                      eta: float,
                      Polytropic_Eta: bool = False,
                      tmp: "TGaspathCondition" = None,
                      n_steps: int = 20):

        if Polytropic_Eta:
            self.compress_real_polytropic_eta(
                PR=PR,
                out=out,
                eta_poly=eta,
                tmp=tmp,
                n_steps=n_steps,
            )
        else:
            self.compress_real_eta_isentropic(
                PR=PR,
                out=out,
                eta_is=eta,
            )

        PW = out.H_total - self.H_total
        return out, PW

    # ------------------------------------------------------------------
    # turbine expansion
    # ------------------------------------------------------------------

    def expand_real_eta_isentropic(self,
                                PR: float,
                                out: "TGaspathCondition",
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
                                out: "TGaspathCondition",
                                eta_poly: float,
                                tmp: "TGaspathCondition" = None,
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
                        out: "TGaspathCondition",
                        eta: float,
                        polytropic_eta: bool = False,
                        tmp: "TGaspathCondition" = None,
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
            raise ValueError("eta must be in (0, 1]")

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

    # try the fastest first.
    # For your case, a good practical order is auto → vcs → gibbs.
    # Do not assume the fastest successful one is always the best-conditioned one.
    # Log solver usage so you can see where robustness problems are coming from.

    @staticmethod
    def robust_equilibrate(gas,
                        mode="HP",
                        max_iter=2000):

        methods = [
            ("auto",  dict()),
            ("vcs",   dict(solver="vcs", max_iter=max_iter)),
            ("gibbs", dict(
                solver="gibbs",
                max_iter=max_iter,
                estimate_equil=-1,
            )),
        ]

        last_err = None

        for name, kwargs in methods:
            try:
                gas.equilibrate(mode, **kwargs)
                return name
            except Exception as err:
                last_err = err

        raise RuntimeError(
            f"All {mode} equilibrium solvers failed. "
            f"Last error: {last_err}"
        )

    def equilibrate_combustor_mixture(self, max_iter=2000, collapse_liquid=True):
        liq_old = self.m_liq
        m_gas = self.gas_q.mass

        phase = self.gas_q.phase
        solver_used = self.robust_equilibrate(phase, max_iter=max_iter)

        self.gas_q = ct.Quantity(phase, mass=m_gas)
        self.m_dry = self.mass * (1.0 - self._gas_h2o_mass_fraction())
        self.m_total_water = self.m_vap + liq_old

        if collapse_liquid:
            self.disable_liquid_model(collapse=True)
        elif self._use_liquid_model():
            self.repartition_at_TP(self.Ts, self.Ps)

        self._set_static_equal_total()

        return solver_used

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
            "m_gas": self.mass,
            "m_vap": self.m_vap,
            "m_liq": self.m_liq,
            "m_total_water": self.m_total_water,
            "RH_gas": self.RH_gas,
            "H_total": self.H_total,
            "S_total": self.S_total,
            "enable_liquid_water": self.enable_liquid_water
        }