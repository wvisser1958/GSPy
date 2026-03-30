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

# Ambient model with SAE AS210 non-standard atmospheres and ISA support

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
import math
import warnings
import numpy as np

DO_WARN = False

try:
    import cantera as ct
except Exception:  # optional at import-time
    ct = None

try:
    import aerocalc as ac
except Exception:
    ac = None

# ---- Constants ----
GAMMA = 1.4
R_D = 287.05287  # J/(kg*K)
P0 = 101_325.0   # Pa, ISA MSL
T0 = 288.15      # K, ISA MSL
RHO0 = 1.225     # kg/m^3, ISA MSL

def scale_composition_string(comp: str, factor: float) -> dict[str, float]:
    out: dict[str, float] = {}
    for part in comp.split(","):
        part = part.strip()
        if not part:
            continue
        name, value = part.split(":", 1)
        out[name.strip()] = float(value.strip()) * factor
    return out

# =============================================================================
# Embedded AS210 JSON tables
# =============================================================================
AS210_TABLES = {
  "10PCTCOLD": {
    "alt": [
      -610.0,
      1000.0,
      2000.0,
      4000.0,
      6000.0,
      8000.0,
      10000.0,
      12000.0,
      14000.0,
      16000.0,
      18000.0,
      20000.0,
      22000.0,
      24000.0,
      26000.0,
      28000.0,
      30000.0
    ],
    "temp": [
      219.15,
      219.15,
      220.15,
      237.15,
      234.15,
      222.15,
      212.15,
      207.15,
      206.15,
      198.15,
      189.15,
      193.15,
      192.15,
      190.15,
      190.15,
      190.15,
      191.15
    ]
  },
  "10PCTHOT": {
    "alt": [
      -610.0,
      1000.0,
      2000.0,
      4000.0,
      6000.0,
      8000.0,
      10000.0,
      12000.0,
      14000.0,
      16000.0,
      18000.0,
      20000.0,
      22000.0,
      24000.0,
      26000.0,
      28000.0,
      30000.0
    ],
    "temp": [
      318.15,
      318.15,
      310.15,
      299.15,
      284.15,
      272.15,
      260.15,
      248.15,
      240.15,
      235.15,
      234.15,
      234.15,
      234.15,
      234.15,
      235.15,
      236.15,
      239.15
    ]
  },
  "1PCTCOLD": {
    "alt": [
      -610.0,
      1000.0,
      2000.0,
      4000.0,
      6000.0,
      8000.0,
      10000.0,
      12000.0,
      14000.0,
      16000.0,
      18000.0,
      20000.0,
      22000.0,
      24000.0,
      26000.0,
      28000.0,
      30000.0
    ],
    "temp": [
      212.15,
      212.15,
      218.15,
      231.15,
      227.15,
      218.15,
      209.15,
      202.15,
      201.15,
      196.15,
      187.15,
      188.15,
      190.15,
      188.15,
      188.15,
      188.15,
      188.15
    ]
  },
  "1PCTHOT": {
    "alt": [
      -610.0,
      1000.0,
      2000.0,
      4000.0,
      6000.0,
      8000.0,
      10000.0,
      12000.0,
      14000.0,
      16000.0,
      18000.0,
      20000.0,
      22000.0,
      24000.0,
      26000.0,
      28000.0,
      30000.0
    ],
    "temp": [
      322.15,
      322.15,
      312.15,
      302.15,
      289.15,
      277.15,
      266.15,
      255.15,
      246.15,
      239.15,
      236.15,
      235.15,
      236.15,
      236.15,
      237.15,
      239.15,
      243.15
    ]
  },
  "20PCTCOLD": {
    "alt": [
      -610.0,
      1000.0,
      2000.0,
      4000.0,
      6000.0,
      8000.0,
      10000.0,
      12000.0,
      14000.0,
      16000.0,
      18000.0,
      20000.0,
      22000.0,
      24000.0,
      26000.0,
      28000.0,
      30000.0
    ],
    "temp": [
      222.15,
      222.15,
      221.15,
      240.15,
      236.15,
      225.15,
      214.15,
      209.15,
      208.15,
      200.15,
      190.15,
      194.15,
      196.15,
      194.15,
      191.15,
      191.15,
      192.15
    ]
  },
  "20PCTHOT": {
    "alt": [
      -610.0,
      1000.0,
      2000.0,
      4000.0,
      6000.0,
      8000.0,
      10000.0,
      12000.0,
      14000.0,
      16000.0,
      18000.0,
      20000.0,
      22000.0,
      24000.0,
      26000.0,
      28000.0,
      30000.0
    ],
    "temp": [
      316.15,
      316.15,
      307.15,
      298.15,
      283.15,
      271.15,
      259.15,
      247.15,
      236.15,
      233.15,
      233.15,
      233.15,
      233.15,
      233.15,
      234.15,
      236.15,
      238.15
    ]
  },
  "5PCTCOLD": {
    "alt": [
      -610.0,
      1000.0,
      2000.0,
      4000.0,
      6000.0,
      8000.0,
      10000.0,
      12000.0,
      14000.0,
      16000.0,
      18000.0,
      20000.0,
      22000.0,
      24000.0,
      26000.0,
      28000.0,
      30000.0
    ],
    "temp": [
      216.15,
      216.15,
      219.15,
      235.15,
      230.15,
      221.15,
      212.15,
      204.15,
      203.15,
      197.15,
      188.15,
      191.15,
      191.15,
      189.15,
      189.15,
      189.15,
      190.15
    ]
  },
  "5PCTHOT": {
    "alt": [
      -610.0,
      1000.0,
      2000.0,
      4000.0,
      6000.0,
      8000.0,
      10000.0,
      12000.0,
      14000.0,
      16000.0,
      18000.0,
      20000.0,
      22000.0,
      24000.0,
      26000.0,
      28000.0,
      30000.0
    ],
    "temp": [
      319.15,
      319.15,
      311.15,
      300.15,
      286.15,
      274.15,
      262.15,
      250.15,
      241.15,
      236.15,
      234.15,
      234.15,
      234.15,
      235.15,
      235.15,
      237.15,
      239.15
    ]
  },
  "COLD": {
    "alt": [
      -610.0,
      1009.0,
      3275.0,
      4572.0,
      6096.0,
      7620.0,
      9362.0,
      12917.0,
      13716.0,
      14783.0,
      15240.0,
      15418.0,
      18619.0,
      19812.0,
      20574.0,
      21336.0,
      22267.0,
      22860.0,
      24384.0,
      25908.0,
      27432.0,
      28956.0,
      30480.0
    ],
    "temp": [
      222.05,
      247.05,
      247.05,
      239.25,
      229.75,
      219.85,
      208.15,
      208.15,
      200.55,
      190.25,
      187.05,
      185.95,
      185.95,
      192.45,
      196.25,
      199.55,
      203.15,
      202.85,
      202.05,
      201.05,
      199.95,
      198.85,
      197.65
    ]
  },
  "HOT": {
    "alt": [
      -610.0,
      1524.0,
      3048.0,
      4572.0,
      6096.0,
      7620.0,
      9144.0,
      9906.0,
      10668.0,
      12009.0,
      13716.0,
      14478.0,
      14783.0,
      15240.0,
      15362.0,
      19812.0,
      20239.0,
      21336.0,
      22860.0,
      24384.0,
      25908.0,
      27432.0,
      28956.0,
      30480.0
    ],
    "temp": [
      312.55,
      312.55,
      301.85,
      290.85,
      280.35,
      269.55,
      259.15,
      248.55,
      243.55,
      238.65,
      230.35,
      231.65,
      232.35,
      232.65,
      233.05,
      233.15,
      234.75,
      234.85,
      236.05,
      238.05,
      240.05,
      242.15,
      244.35,
      246.55
    ]
  },
  "MAXREC": {
    "alt": [
      -610.0,
      1000.0,
      2000.0,
      4000.0,
      6000.0,
      8000.0,
      10000.0,
      12000.0,
      14000.0,
      16000.0,
      18000.0,
      20000.0,
      22000.0,
      24000.0,
      26000.0,
      28000.0,
      30000.0
    ],
    "temp": [
      331.15,
      331.15,
      313.15,
      304.15,
      292.15,
      279.15,
      269.15,
      255.15,
      246.15,
      239.15,
      238.15,
      239.15,
      242.15,
      242.15,
      242.15,
      246.15,
      251.15
    ]
  },
  "MINREC": {
    "alt": [
      -610.0,
      1000.0,
      2000.0,
      4000.0,
      6000.0,
      8000.0,
      10000.0,
      12000.0,
      14000.0,
      16000.0,
      18000.0,
      20000.0,
      22000.0,
      24000.0,
      26000.0,
      28000.0,
      30000.0
    ],
    "temp": [
      205.15,
      205.15,
      217.15,
      226.15,
      222.15,
      213.15,
      209.15,
      200.15,
      196.15,
      195.15,
      186.15,
      188.15,
      190.15,
      188.15,
      188.15,
      188.15,
      188.15
    ]
  },
  "POLAR": {
    "alt": [
      -610.0,
      -97.0,
      988.0,
      3012.0,
      6096.0,
      9164.0,
      26241.0,
      30480.0
    ],
    "temp": [
      246.15,
      246.15,
      246.65,
      252.15,
      250.15,
      234.25,
      218.15,
      210.15
    ]
  },
  "TROPICAL": {
    "alt": [
      -610.0,
      6096.0,
      10668.0,
      12192.0,
      13716.0,
      15240.0,
      16336.0,
      18288.0,
      21220.0,
      30480.0
    ],
    "temp": [
      305.25,
      305.25,
      262.25,
      230.05,
      219.45,
      209.35,
      199.75,
      193.15,
      200.95,
      213.15
    ]
  }
}

# Convert to NumPy arrays on import
AS210_PROFILES: Dict[str, Dict[str, np.ndarray]] = {}
for name, tab in AS210_TABLES.items():
    AS210_PROFILES[name.upper()] = {
        "alt": np.asarray(tab["alt"], dtype=float),
        "temp": np.asarray(tab["temp"], dtype=float),
    }

# ---- Helpers ----

def _isa_temp(alt_m: float) -> float:
    """
       ISA temperature at geometric altitude (approx) using aerocalc if available.
       Fallback is only valid up to 32 km.
    """
    if ac is not None:
        try:
            return ac.std_atm.alt2temp(alt_m, alt_units="m", temp_units="K")
        except ValueError:
            # "Proper" behavior: altitude invalid/out-of-range etc.
            # Do NOT silently fall back to a weaker model.
            raise
        except Exception:
            # Any unexpected aerocalc failure -> try our fallback (best-effort)
            pass
        
    # Fallback to piecewise ISA up to 32 km (sufficient for this use)
    # Layers: 0–11 km (L=-6.5 K/km); 11–20 km (isothermal 216.65 K); 20–32 km (+1.0 K/km)
    h = float(alt_m)
    if h <= 11_000.0:
        return T0 - 0.0065 * h
    elif h <= 20_000.0:
        return 216.65
    elif h <= 32_000:
        return 216.65 + 0.001 * (h - 20_000.0)
    else:
        raise ValueError("ISA fallback implemented only up to 32 km.")


def _interp(x: float, xs: np.ndarray, ys: np.ndarray) -> float:
    """1D linear interpolation with clamping to the end values for out-of-range x."""
    if x <= xs[0]:
        return float(ys[0])
    if x >= xs[-1]:
        return float(ys[-1])
    i = int(np.searchsorted(xs, x) - 1)  # xs[i] <= x < xs[i+1]
    x0, x1 = xs[i], xs[i+1]
    y0, y1 = ys[i], ys[i+1]
    w = (x - x0) / (x1 - x0)
    return float(y0 * (1 - w) + y1 * w)


def profile_temp(profile: str, alt_m: float) -> float:
    """Temperature for a given AS210 profile at altitude (m).
    Returns ISA if profile is 'STANDARD' or 'ISA'."""
    p = profile.upper()
    if p in ('STANDARD', 'ISA', 'STD'):
        return _isa_temp(alt_m)
    if p not in AS210_PROFILES:
        raise KeyError(f"Unknown AS210 profile '{profile}'. Available: {sorted(AS210_PROFILES)}")
    tab = AS210_PROFILES[p]
    return _interp(alt_m, tab['alt'], tab['temp'])

# ---- Humidity ----

def saturation_vapor_pressure_pa(T: float) -> float:
    """Saturation vapor pressure over liquid water/ice (Buck, 1981 style approximation)."""
    Tc = T - 273.15
    if T >= 273.15:
        # over water
        es_hPa = 6.1121 * math.exp((18.678 - Tc/234.5) * (Tc/(257.14 + Tc)))
    else:
        # over ice
        es_hPa = 6.1115 * math.exp((23.036 - Tc/333.7) * (Tc/(279.82 + Tc)))
    return es_hPa * 100.0


def q_from_rh_P_T(RH: float, P: float, T: float) -> float:
    RH = max(0.0, min(1.0, float(RH)))
    es = saturation_vapor_pressure_pa(T)
    e = min(RH * es, 0.99*P)  # avoid singularities
    w = 0.622 * e / (P - e)
    return w / (1.0 + w)


def rh_from_q_P_T(q: float, P: float, T: float) -> float:
    q = max(0.0, float(q))
    e = (q * P) / (0.622 + q)
    es = saturation_vapor_pressure_pa(T)
    return max(0.0, min(1.0, e / es))

# ---- Airspeed & Thermo ----

def speed_of_sound(T: float) -> float:
    if ac is not None:
        try:
            return ac.std_atm.temp2speed_of_sound(T, speed_units='m/s', temp_units='K')
        except Exception:
            pass
    return math.sqrt(GAMMA * R_D * T)


def total_T_from_M(Ts: float, M: float) -> float:
    return Ts * (1.0 + 0.5*(GAMMA-1.0)*M*M)


def total_P_from_M(Ps: float, M: float) -> float:
    return Ps * (1.0 + 0.5*(GAMMA-1.0)*M*M) ** (GAMMA/(GAMMA-1.0))


def M_from_total_T(Ts: float, Tt: float) -> float:
    r = max(Tt/Ts - 1.0, 0.0)
    return math.sqrt(2.0*r/(GAMMA-1.0))


def M_from_total_P(Ps: float, Pt: float) -> float:
    r = max((Pt/Ps) ** ((GAMMA-1.0)/GAMMA) - 1.0, 0.0)
    return math.sqrt(2.0*r/(GAMMA-1.0))


def qc_from_M(Ps: float, M: float) -> float:
    return total_P_from_M(Ps, M) - Ps


def vcas_from_qc(qc: float) -> float:
    # Compressible sea-level mapping
    return speed_of_sound(T0) * math.sqrt(5.0 * (((qc/P0) + 1.0) ** (2.0/7.0) - 1.0))


def vcas_from_M(Ps: float, M: float) -> float:
    qc = qc_from_M(Ps, M)
    return vcas_from_qc(qc)


def rho_from_P_T(P: float, T: float) -> float:
    # Dry-air approximation (adequate for flight mechanics)
    return P / (R_D * T)


def veas_from_vtas_rho(vtas: float, rho: float) -> float:
    return vtas * math.sqrt(rho / RHO0)


def vtas_from_veas_rho(veas: float, rho: float) -> float:
    return veas / math.sqrt(rho / RHO0)


def M_from_vcas(Ps: float, VCAS: float) -> float:
    # Invert by bisection on M in [0, 2.0]
    target = VCAS
    lo, hi = 0.0, 2.0
    for _ in range(60):
        mid = 0.5*(lo+hi)
        vmid = vcas_from_M(Ps, mid)
        if vmid < target:
            lo = mid
        else:
            hi = mid
    return 0.5*(lo+hi)


def M_from_veas(Ps: float, Ts: float, VEAS: float) -> float:
    rho = rho_from_P_T(Ps, Ts)
    VTAS = vtas_from_veas_rho(VEAS, rho)
    a = speed_of_sound(Ts)
    return max(0.0, VTAS / a)

# ---- API ----
@dataclass
class AmbientInputs:
    alt_in: Optional[float] = None
    dTs_in: Optional[float] = None
    humRel_in: Optional[float] = None  # 0..1
    humSp_in: Optional[float] = None   # kg/kg
    MN_in: Optional[float] = None
    Ps_in: Optional[float] = None
    Pt_in: Optional[float] = None
    Ts_in: Optional[float] = None
    Tt_in: Optional[float] = None
    VEAS_in: Optional[float] = None
    VCAS_in: Optional[float] = None
    VTAS_in: Optional[float] = None
    # selectors (single profile only; no blending)
    switchDay: Optional[str] = 'STANDARD'  # e.g. 'STANDARD' | 'HOT' | 'COLD' | '5PCTHOT' | ...
    switchHum: str = 'RH'                  # 'RH' -> use humRel_in, 'SH' -> use humSp_in, '-' -> dry
    switchMode: str = 'ALDTMN'             # AS210 6-character mode, e.g. 'ALDTMN'

@dataclass
class AmbientOutputs:
    alt: Optional[float]
    dTs: float
    dTsStd: float
    humRel: float
    humSp: float
    MN: float
    Ps: float
    Pt: float
    Ts: float
    Tt: float
    TsDay: float
    VEAS: float
    VCAS: float
    VTAS: float

class Ambient_AS210:
    """Ambient model with AS210 non-standard atmospheres + ISA.

    - Temperature day profiles from AS210 (HOT, COLD, POLAR, TROPICAL, MINREC, MAXREC,
      1/5/10/20PCTHOT/-COLD). Standard atmosphere pressure is always used for Ps vs pressure altitude.
    - Humidity handled by switchHum: 'RH' (use humRel_in), 'SH' (use humSp_in), '-' (dry).
    - Flight condition selection via switchMode
    
    The AS210 switchMode is interpreted as three 2-character selectors:
      - chars 1-2: pressure/altitude input ('AL' or 'PS')
      - chars 3-4: temperature input ('DT', 'TS', 'TT')
      - chars 5-6: speed input ('MN', 'VC', 'VT', 'VE')

    Supported combinations implemented here:
      - ALDTMN (commonly used option)
      - ALDTVC
      - ALDTVT
      - ALDTVE
      - ALTSMN
      - ALTSVE
      - PSTSMN
      - PSTSVE
      - PSTSTT

    For pressure-based modes ('PS....'), no altitude is applied and switchDay is
    ignored because it has no physical meaning without altitude.
    """

    VALID_SWITCH_MODES = {
        'ALDTMN', 'ALDTVC', 'ALDTVT', 'ALDTVE', 'ALTSMN', 'ALTSVE', 'PSTSMN', 'PSTSVE', 'PSTSTT'
    }
    NONSTANDARD_DAY_SWITCH_MODES = {
        'ALDTMN', 'ALDTVC', 'ALDTVT'
    }

    def __init__(self):
        self.outputs: Optional[AmbientOutputs] = None

    def _parse_switch_mode(self, switch_mode: Optional[str]) -> Tuple[str, str, str]:
        mode = (switch_mode or 'ALDTMN').strip().upper()
        if len(mode) != 6:
            raise ValueError(
                f"switchMode must be a 6-character AS210 code, got {switch_mode!r}."
            )
        if mode not in self.VALID_SWITCH_MODES:
            raise ValueError(
                f"Unsupported AS210 switchMode {mode!r}. Supported: {sorted(self.VALID_SWITCH_MODES)}"
            )
        return mode[:2], mode[2:4], mode[4:6]


    def _normalize_switch_day(self, switch_day: Optional[str]) -> str:
        return (switch_day or 'STANDARD').strip().upper()

    def _is_standard_day(self, switch_day: Optional[str]) -> bool:
        return self._normalize_switch_day(switch_day) in {'STANDARD', 'ISA', 'STD'}

    def _validate_switch_day_mode(self, I: AmbientInputs, press_sel: str, temp_sel: str, speed_sel: str) -> None:
        mode = (I.switchMode or 'ALDTMN').strip().upper()
        day = self._normalize_switch_day(I.switchDay)

        if self._is_standard_day(day):
            return

        if mode not in self.NONSTANDARD_DAY_SWITCH_MODES:
            raise ValueError(
                f"switchDay {day!r} only supports switchMode values {sorted(self.NONSTANDARD_DAY_SWITCH_MODES)}; got {mode!r}."
            )

        if press_sel != 'AL' or temp_sel != 'DT' or speed_sel not in {'MN', 'VC', 'VT', 'VE'}:
            raise ValueError(
                f"switchDay {day!r} requires an altitude + delta-static-temperature mode (ALDTMN/ALDTVC/ALDTVT/ALDTVE); got {mode!r}."
            )

    def _resolve_pressure_altitude(self, I: AmbientInputs, press_sel: str) -> Tuple[Optional[float], float, Optional[float], Optional[float]]:
        """Return (alt, Ps, TsDay, TsStd)."""
        if press_sel == 'AL':
            if I.alt_in is None:
                raise ValueError(
                    'switchMode requires altitude input (AL), but alt_in is None.'
                )
            alt = float(I.alt_in)
            Ps = float(I.Ps_in) if I.Ps_in is not None else self._isa_pressure(alt)
            day = self._normalize_switch_day(I.switchDay)
            TsDay = profile_temp(day, alt)
            TsStd = _isa_temp(alt)
            return alt, Ps, TsDay, TsStd

        if press_sel == 'PS':
            if I.Ps_in is None:
                raise ValueError(
                    'switchMode requires static pressure input (PS), but Ps_in is None.'
                )
            Ps = float(I.Ps_in)
            if not self._is_standard_day(I.switchDay):
                raise ValueError(
                    f"switchDay {self._normalize_switch_day(I.switchDay)!r} cannot be used with pressure-based switchMode {str(I.switchMode or 'ALDTMN').upper()!r}; use ALDTMN, ALDTVC or ALDTVT."
                )
            # No altitude/day interpretation for PS-based modes.
            return None, Ps, None, None

        raise ValueError(f'Unsupported pressure/altitude selector {press_sel!r}.')

    def _resolve_static_temperature(
        self,
        I: AmbientInputs,
        temp_sel: str,
        alt: Optional[float],
        TsDay: Optional[float],
    ) -> Tuple[float, float, float]:
        """Return (Ts, dTs, dTsStd)."""
        if temp_sel == 'DT':
            if TsDay is None:
                raise ValueError(
                    'DT temperature selector requires altitude/day profile; it cannot be used with PS-based modes.'
                )
            Ts = TsDay + (I.dTs_in or 0.0)
            dTs = Ts - TsDay
            TsStd = _isa_temp(float(alt))
            dTsStd = Ts - TsStd
            return Ts, dTs, dTsStd

        if temp_sel == 'TS':
            if I.Ts_in is None:
                raise ValueError(
                    'switchMode requires static temperature input (TS), but Ts_in is None.'
                )
            Ts = float(I.Ts_in)
            if TsDay is not None:
                dTs = Ts - TsDay
                TsStd = _isa_temp(float(alt))
                dTsStd = Ts - TsStd
            else:
                dTs = 0.0
                dTsStd = 0.0
            return Ts, dTs, dTsStd

        if temp_sel == 'TT':
            if I.Tt_in is None:
                raise ValueError(
                    'switchMode requires total temperature input (TT), but Tt_in is None.'
                )
            # Ts will be finalized after Mach is known.
            return math.nan, 0.0, 0.0

        raise ValueError(f'Unsupported temperature selector {temp_sel!r}.')

    def _resolve_mach(
        self,
        I: AmbientInputs,
        speed_sel: str,
        Ps: float,
        Ts: float,
        temp_sel: str,
    ) -> float:
        a = speed_of_sound(Ts)

        if speed_sel == 'MN':
            if I.MN_in is None:
                raise ValueError(
                    'switchMode requires Mach input (MN), but MN_in is None.'
                )
            return max(0.0, float(I.MN_in))

        if speed_sel == 'VC':
            if I.VCAS_in is None:
                raise ValueError(
                    'switchMode requires calibrated airspeed input (VC), but VCAS_in is None.'
                )
            return M_from_vcas(Ps, float(I.VCAS_in))

        if speed_sel == 'VT':
            if I.VTAS_in is None:
                raise ValueError(
                    'switchMode requires true airspeed input (VT), but VTAS_in is None.'
                )
            return max(0.0, float(I.VTAS_in) / a)

        if speed_sel == 'VE':
            if I.VEAS_in is None:
                raise ValueError(
                    'switchMode requires equivalent airspeed input (VE), but VEAS_in is None.'
                )
            return M_from_veas(Ps, Ts, float(I.VEAS_in))

        if temp_sel == 'TT':
            if I.Tt_in is None:
                raise ValueError(
                    'switchMode requires total temperature input (TT), but Tt_in is None.'
                )
            return M_from_total_T(Ts, float(I.Tt_in))

        raise ValueError(f'Unsupported speed selector {speed_sel!r}.')

    def _finalize_static_temperature_for_tt(
        self,
        I: AmbientInputs,
        alt: Optional[float],
        TsDay: Optional[float],
        MN: float,
    ) -> Tuple[float, float, float]:
        if I.Tt_in is None:
            raise ValueError('Tt_in is required to derive Ts from TT-based switchMode.')
        denom = 1.0 + 0.5 * (GAMMA - 1.0) * MN * MN
        Ts = float(I.Tt_in) / denom
        if TsDay is not None:
            dTs = Ts - TsDay
            TsStd = _isa_temp(float(alt))
            dTsStd = Ts - TsStd
        else:
            dTs = 0.0
            dTsStd = 0.0
        return Ts, dTs, dTsStd

    def _used_input_names(self, press_sel: str, temp_sel: str, speed_sel: str) -> set[str]:
        used = {'switchMode', 'switchHum'}

        if press_sel == 'AL':
            used.add('alt_in')
            used.add('switchDay')
        elif press_sel == 'PS':
            used.add('Ps_in')

        if temp_sel == 'DT':
            used.add('dTs_in')
        elif temp_sel == 'TS':
            used.add('Ts_in')
        elif temp_sel == 'TT':
            used.add('Tt_in')

        if speed_sel == 'MN':
            used.add('MN_in')
        elif speed_sel == 'VC':
            used.add('VCAS_in')
        elif speed_sel == 'VT':
            used.add('VTAS_in')
        elif speed_sel == 'VE':
            used.add('VEAS_in')
        elif speed_sel == 'TT':
            used.add('Tt_in')

        return used

    def _provided_input_names(self, I: AmbientInputs) -> set[str]:
        candidates = {
            'alt_in': I.alt_in,
            'dTs_in': I.dTs_in,
            'humRel_in': I.humRel_in,
            'humSp_in': I.humSp_in,
            'MN_in': I.MN_in,
            'Ps_in': I.Ps_in,
            'Pt_in': I.Pt_in,
            'Ts_in': I.Ts_in,
            'Tt_in': I.Tt_in,
            'VEAS_in': I.VEAS_in,
            'VCAS_in': I.VCAS_in,
            'VTAS_in': I.VTAS_in,
            'switchDay': I.switchDay,
        }
        provided = set()
        for name, value in candidates.items():
            if value is None:
                continue
            if name == 'switchDay' and str(value).upper() in ('STANDARD', 'ISA', 'STD'):
                continue
            provided.add(name)
        return provided

    def _required_input_names(self, press_sel: str, temp_sel: str, speed_sel: str) -> set[str]:
        required = set()

        if press_sel == 'AL':
            required.add('alt_in')
        elif press_sel == 'PS':
            required.add('Ps_in')

        if temp_sel == 'DT':
            required.add('dTs_in')
        elif temp_sel == 'TS':
            required.add('Ts_in')
        elif temp_sel == 'TT':
            required.add('Tt_in')

        if speed_sel == 'MN':
            required.add('MN_in')
        elif speed_sel == 'VC':
            required.add('VCAS_in')
        elif speed_sel == 'VT':
            required.add('VTAS_in')
        elif speed_sel == 'VE':
            required.add('VEAS_in')
        elif speed_sel == 'TT':
            required.add('Tt_in')

        return required

    def _validate_mode_inputs(self, I: AmbientInputs, press_sel: str, temp_sel: str, speed_sel: str, *, require_all: bool = True) -> None:
        used = self._used_input_names(press_sel, temp_sel, speed_sel)

        humidity_sel = (I.switchHum or 'RH').upper()
        if humidity_sel == 'RH':
            used.add('humRel_in')
        elif humidity_sel == 'SH':
            used.add('humSp_in')

        provided = self._provided_input_names(I)
        required = self._required_input_names(press_sel, temp_sel, speed_sel)

        missing = sorted(name for name in required if name not in provided)
        extras = sorted(name for name in provided if name not in used)

        if require_all and missing:
            mode = (I.switchMode or 'ALDTMN').upper()
            raise ValueError(
                f"switchMode {mode!r}: incorrect input parameters, required: "
                f"{', '.join(missing)}, supplied: {', '.join(sorted(provided)) or 'none'}."
            )

        if extras:
            raise ValueError(
                f"switchMode {(I.switchMode or 'ALDTMN').upper()!r}: non-applicable input parameters supplied: "
                f"{', '.join(extras)}."
            )

    # ---- Core compute ----
    def run(self, I: AmbientInputs) -> AmbientOutputs:
        press_sel, temp_sel, speed_sel = self._parse_switch_mode(I.switchMode)
        self._validate_switch_day_mode(I, press_sel, temp_sel, speed_sel)
        self._validate_mode_inputs(I, press_sel, temp_sel, speed_sel)

        alt, Ps, TsDay, TsStd = self._resolve_pressure_altitude(I, press_sel)
        Ts, dTs, dTsStd = self._resolve_static_temperature(I, temp_sel, alt, TsDay)

        if speed_sel == 'TT':
            # For PSTSTT, solve M from Ps + Ts + Tt.
            if press_sel != 'PS' or temp_sel != 'TS':
                raise ValueError(
                    f'Unsupported TT-based AS210 combination {I.switchMode!r}.'
                )
            if I.Ts_in is None or I.Tt_in is None:
                raise ValueError(
                    'PSTSTT requires both Ts_in and Tt_in.'
                )
            Ts = float(I.Ts_in)
            MN = M_from_total_T(Ts, float(I.Tt_in))
            dTs, dTsStd = (0.0, 0.0) if TsDay is None else (Ts - TsDay, Ts - TsStd)
        else:
            MN = self._resolve_mach(I, speed_sel, Ps, Ts, temp_sel)

        # Totals
        if temp_sel == 'TT' or speed_sel == 'TT':
            Tt = float(I.Tt_in)
        else:
            Tt = total_T_from_M(Ts, MN)
        Pt = total_P_from_M(Ps, MN)

        # Humidity
        if (I.switchHum or 'RH').upper() == 'SH' and I.humSp_in is not None:
            humSp = max(0.0, float(I.humSp_in))
            humRel = rh_from_q_P_T(humSp, Ps, Ts)
        elif (I.switchHum or 'RH').upper() == 'RH' and I.humRel_in is not None:
            humRel = max(0.0, min(1.0, float(I.humRel_in)))
            humSp = q_from_rh_P_T(humRel, Ps, Ts)
        else:
            humRel = 0.0
            humSp = 0.0

        # Speeds
        a = speed_of_sound(Ts)
        rho = rho_from_P_T(Ps, Ts)
        VTAS = float(I.VTAS_in) if speed_sel == 'VT' and I.VTAS_in is not None else vtas_from_veas_rho(float(I.VEAS_in), rho) if speed_sel == 'VE' and I.VEAS_in is not None else MN * a
        VEAS = float(I.VEAS_in) if speed_sel == 'VE' and I.VEAS_in is not None else veas_from_vtas_rho(VTAS, rho)
        VCAS = float(I.VCAS_in) if speed_sel == 'VC' and I.VCAS_in is not None else vcas_from_M(Ps, MN)

        self.outputs = AmbientOutputs(
            alt=alt,
            dTs=dTs,
            dTsStd=dTsStd,
            humRel=humRel,
            humSp=humSp,
            MN=MN,
            Ps=Ps,
            Pt=Pt,
            Ts=Ts,
            Tt=Tt,
            TsDay=TsDay if TsDay is not None else Ts,
            VEAS=VEAS,
            VCAS=VCAS,
            VTAS=VTAS,
        )
        return self.outputs

    # ---- ISA pressure (from aerocalc if available; otherwise a simple model) ----
    def _isa_pressure(self, alt_m: float) -> float:
        if ac is not None:
            try:
                return ac.std_atm.alt2press(alt_m, alt_units='m', press_units='pa')
            except Exception:
                pass
        # Piecewise ISA up to 32 km (sufficient)
        h = float(alt_m)
        if h <= 11_000.0:
            T = T0 - 0.0065*h
            # exponent ~ 5.25588 ; compute explicitly to avoid importing g
            return P0 * (T/T0) ** 5.25588
        elif h <= 20_000.0:
            T = 216.65
            P11 = 22632.06
            return P11 * math.exp(-(h-11_000.0) * 9.80665 / (R_D * T))
        else:
            T = 216.65 + 0.001*(h-20_000.0)
            P20 = 5474.889
            return P20 * (T/216.65) ** (-9.80665/(0.001*R_D))

# ---- GSPy adapter (AS210) -----------------------------------------
try:
    from gspy.core.base_component import TComponent
    import gspy.core.sys_global as fg
except Exception:
    TComponent = None


if TComponent is not None:
    class TAmbient_AS210(TComponent):
        """
        Drop-in replacement for gspy.core.ambient.TAmbient,
        but using the AS210 non-standard temperature profiles.

        Constructor signature:
            TAmbient_AS210(
                owner, name, station_nr, *,
                alt_in=None, dTs_in=None, humRel_in=None, humSp_in=None,
                MN_in=None, Ps_in=None, Pt_in=None, Ts_in=None, Tt_in=None,
                VEAS_in=None, VCAS_in=None, VTAS_in=None,
                switchMode='ALDTMN', switchDay='STANDARD', switchHum='RH'
            )
        """

        def __init__(
            self,
            owner,
            name,
            station_nr,
            *,
            alt_in=None,
            dTs_in=None,
            humRel_in=None,
            humSp_in=None,
            MN_in=None,
            Ps_in=None,
            Pt_in=None,
            Ts_in=None,
            Tt_in=None,
            VEAS_in=None,
            VCAS_in=None,
            VTAS_in=None,
            switchMode='ALDTMN',
            switchDay='STANDARD',
            switchHum='RH',
        ):
            super().__init__(owner, name, '', None)
            self.station_nr = station_nr

            if owner is not None:
                owner.ambient = self

            self.outputs = None
            self.last_inputs: Optional[AmbientInputs] = None
            self.Gas_Ambient = None

            for suffix in ('', '_des'):
                setattr(self, f'alt_in{suffix}', None)
                setattr(self, f'dTs_in{suffix}', None)
                setattr(self, f'humRel_in{suffix}', None)
                setattr(self, f'humSp_in{suffix}', None)
                setattr(self, f'MN_in{suffix}', None)
                setattr(self, f'Ps_in{suffix}', None)
                setattr(self, f'Pt_in{suffix}', None)
                setattr(self, f'Ts_in{suffix}', None)
                setattr(self, f'Tt_in{suffix}', None)
                setattr(self, f'VEAS_in{suffix}', None)
                setattr(self, f'VCAS_in{suffix}', None)
                setattr(self, f'VTAS_in{suffix}', None)
                setattr(self, f'switchDay{suffix}', 'STANDARD')
                setattr(self, f'switchHum{suffix}', 'RH')
                setattr(self, f'switchMode{suffix}', 'ALDTMN')

            self.SetConditionsAS210(
                'DP',
                alt_in=alt_in,
                dTs_in=dTs_in,
                humRel_in=humRel_in,
                humSp_in=humSp_in,
                MN_in=MN_in,
                Ps_in=Ps_in,
                Pt_in=Pt_in,
                Ts_in=Ts_in,
                Tt_in=Tt_in,
                VEAS_in=VEAS_in,
                VCAS_in=VCAS_in,
                VTAS_in=VTAS_in,
                switchDay=switchDay,
                switchHum=switchHum,
                switchMode=switchMode,
            )

        def print_ambient_composition(self, threshold: float = 0.0, basis: str = "mass") -> None:
            if self.Gas_Ambient is None:
                print("No Cantera ambient object available.")
                return

            gas = self.Gas_Ambient.phase  # underlying ct.Solution

            if basis == "mass":
                comp = gas.mass_fraction_dict(threshold=threshold)
                label = "Mass fraction"
            elif basis == "mole":
                comp = gas.mole_fraction_dict(threshold=threshold)
                label = "Mole fraction"
            else:
                raise ValueError("basis must be 'mass' or 'mole'")

            print(f"Ambient composition ({basis} basis)")
            for species, value in comp.items():
                print(f"{species:>8s} : {value:.8f}")

        # ------------------------------------------------------------------
        # User-facing configuration of AS210 day type and humidity handling
        # ------------------------------------------------------------------
        def SetConditionsAS210(
            self,
            Mode='OD',
            *,
            alt_in=None,
            dTs_in=None,
            humRel_in=None,
            humSp_in=None,
            MN_in=None,
            Ps_in=None,
            Pt_in=None,
            Ts_in=None,
            Tt_in=None,
            VEAS_in=None,
            VCAS_in=None,
            VTAS_in=None,
            switchDay='STANDARD',
            switchHum='RH',
            switchMode='ALDTMN',
        ):
            """
            Explicit AS210 ambient condition setter.

            This mirrors the AmbientInputs fields with GSPy-style attribute names,
            so any switchMode-required input can be provided directly by name.

            Parameters
            ----------
            switchDay : str
                Day profile, for example 'STANDARD', 'HOT', 'COLD', 'MAXREC', ...
            switchHum : str
                'RH' -> use humRel_in
                'SH' -> use humSp_in
                '-'  -> dry
            humRel_in : float | None
                Relative humidity [0..1]
            humSp_in : float | None
                Specific humidity [kg/kg]

            Examples
            --------
            self.SetConditionsAS210('OD', alt_in=3000.0, dTs_in=10.0, MN_in=0.4)
            self.SetConditionsAS210('OD', alt_in=3000.0, dTs_in=10.0, VCAS_in=120.0,
                                    switchMode='ALDTVC')
            """
            self.SetConditions(
                Mode,
                alt_in=alt_in,
                dTs_in=dTs_in,
                humRel_in=humRel_in,
                humSp_in=humSp_in,
                MN_in=MN_in,
                Ps_in=Ps_in,
                Pt_in=Pt_in,
                Ts_in=Ts_in,
                Tt_in=Tt_in,
                VEAS_in=VEAS_in,
                VCAS_in=VCAS_in,
                VTAS_in=VTAS_in,
                switchDay=switchDay,
                switchHum=switchHum,
                switchMode=switchMode,
            )

        def _clear_mode_specific_inputs(self, target=''):
            for name in (
                'alt_in', 'dTs_in', 'MN_in', 'Ps_in', 'Pt_in',
                'Ts_in', 'Tt_in', 'VEAS_in', 'VCAS_in', 'VTAS_in',
            ):
                setattr(self, f'{name}{target}', None)


        def _check_switchday_mode_compatibility(self, switchDay, switchMode):
            engine = Ambient_AS210()
            mode = (switchMode or 'ALDTMN').strip().upper()
            day = engine._normalize_switch_day(switchDay)
            press_sel, temp_sel, speed_sel = engine._parse_switch_mode(mode)
            engine._validate_switch_day_mode(
                AmbientInputs(switchDay=day, switchMode=mode),
                press_sel,
                temp_sel,
                speed_sel,
            )

        def _check_switchmode_inputs(
            self,
            target='',
            *,
            alt_in=None,
            dTs_in=None,
            humRel_in=None,
            humSp_in=None,
            MN_in=None,
            Ps_in=None,
            Pt_in=None,
            Ts_in=None,
            Tt_in=None,
            VEAS_in=None,
            VCAS_in=None,
            VTAS_in=None,
            switchDay=None,
            switchHum=None,
            switchMode=None,
        ):
            engine = Ambient_AS210()
            effective_switch_mode = switchMode if switchMode is not None else getattr(self, f'switchMode{target}', 'ALDTMN')
            effective_switch_day = switchDay if switchDay is not None else getattr(self, f'switchDay{target}', 'STANDARD')
            effective_switch_hum = switchHum if switchHum is not None else getattr(self, f'switchHum{target}', 'RH')

            inputs = AmbientInputs(
                alt_in=alt_in if alt_in is not None else getattr(self, f'alt_in{target}'),
                dTs_in=dTs_in if dTs_in is not None else getattr(self, f'dTs_in{target}'),
                humRel_in=humRel_in if humRel_in is not None else getattr(self, f'humRel_in{target}'),
                humSp_in=humSp_in if humSp_in is not None else getattr(self, f'humSp_in{target}'),
                MN_in=MN_in if MN_in is not None else getattr(self, f'MN_in{target}'),
                Ps_in=Ps_in if Ps_in is not None else getattr(self, f'Ps_in{target}'),
                Pt_in=Pt_in if Pt_in is not None else getattr(self, f'Pt_in{target}'),
                Ts_in=Ts_in if Ts_in is not None else getattr(self, f'Ts_in{target}'),
                Tt_in=Tt_in if Tt_in is not None else getattr(self, f'Tt_in{target}'),
                VEAS_in=VEAS_in if VEAS_in is not None else getattr(self, f'VEAS_in{target}'),
                VCAS_in=VCAS_in if VCAS_in is not None else getattr(self, f'VCAS_in{target}'),
                VTAS_in=VTAS_in if VTAS_in is not None else getattr(self, f'VTAS_in{target}'),
                switchDay=effective_switch_day,
                switchHum=effective_switch_hum,
                switchMode=effective_switch_mode,
            )
            press_sel, temp_sel, speed_sel = engine._parse_switch_mode(inputs.switchMode)
            engine._validate_mode_inputs(inputs, press_sel, temp_sel, speed_sel, require_all=False)

        # ------------------------------------------------------------------
        # Store DP or OD conditions for later use
        # ------------------------------------------------------------------
        def SetConditions(
            self,
            Mode,
            alt_in=None,
            MN_in=None,
            dTs_in=None,
            Ps_in=None,
            Ts_in=None,
            *,
            humRel_in=None,
            humSp_in=None,
            Pt_in=None,
            Tt_in=None,
            VEAS_in=None,
            VCAS_in=None,
            VTAS_in=None,
            switchDay=None,
            switchHum=None,
            switchMode=None,
        ):
            target = '_des' if Mode == 'DP' else ''

            effective_switch_mode = switchMode if switchMode is not None else getattr(self, f'switchMode{target}', 'ALDTMN')
            effective_switch_day = switchDay if switchDay is not None else getattr(self, f'switchDay{target}', 'STANDARD')
            self._check_switchday_mode_compatibility(effective_switch_day, effective_switch_mode)

            if switchMode is not None:
                current_mode = getattr(self, f'switchMode{target}', None)
                new_mode = str(switchMode).upper()
                if current_mode is None or str(current_mode).upper() != new_mode:
                    self._clear_mode_specific_inputs(target)

            self._check_switchmode_inputs(
                target,
                alt_in=alt_in,
                dTs_in=dTs_in,
                humRel_in=humRel_in,
                humSp_in=humSp_in,
                MN_in=MN_in,
                Ps_in=Ps_in,
                Pt_in=Pt_in,
                Ts_in=Ts_in,
                Tt_in=Tt_in,
                VEAS_in=VEAS_in,
                VCAS_in=VCAS_in,
                VTAS_in=VTAS_in,
                switchDay=switchDay,
                switchHum=switchHum,
                switchMode=switchMode,
            )

            updates = {
                'alt_in': alt_in,
                'dTs_in': dTs_in,
                'humRel_in': humRel_in,
                'humSp_in': humSp_in,
                'MN_in': MN_in,
                'Ps_in': Ps_in,
                'Pt_in': Pt_in,
                'Ts_in': Ts_in,
                'Tt_in': Tt_in,
                'VEAS_in': VEAS_in,
                'VCAS_in': VCAS_in,
                'VTAS_in': VTAS_in,
                'switchDay': switchDay,
                'switchHum': switchHum,
                'switchMode': switchMode,
            }

            for name, value in updates.items():
                if value is not None:
                    setattr(self, f'{name}{target}', value)

        # ------------------------------------------------------------------
        # Core of the adapter — executed every DP or OD simulation step
        # ------------------------------------------------------------------
        def Run(self, Mode, PointTime):

            # Apply DP conditions if needed (GSPy convention)
            if Mode == 'DP':
                for name in (
                    'alt_in', 'dTs_in', 'humRel_in', 'humSp_in', 'MN_in', 'Ps_in', 'Pt_in',
                    'Ts_in', 'Tt_in', 'VEAS_in', 'VCAS_in', 'VTAS_in',
                    'switchDay', 'switchHum', 'switchMode',
                ):
                    setattr(self, name, getattr(self, f'{name}_des'))

            # Build the input object for the AS210 computational model
            inputs = AmbientInputs(
                alt_in=self.alt_in,
                dTs_in=self.dTs_in,
                humRel_in=self.humRel_in,
                humSp_in=self.humSp_in,
                MN_in=self.MN_in,
                Ps_in=self.Ps_in,
                Pt_in=self.Pt_in,
                Ts_in=self.Ts_in,
                Tt_in=self.Tt_in,
                VEAS_in=self.VEAS_in,
                VCAS_in=self.VCAS_in,
                VTAS_in=self.VTAS_in,
                # switchDay=self.switchDay if self.Altitude is not None else None,
                switchDay=self.switchDay,
                switchHum=self.switchHum,
                switchMode=self.switchMode
            )

            self.last_inputs = inputs

            # Execute the AS210 physics model
            engine = Ambient_AS210()
            O = engine.run(inputs)
            self.outputs = O

            # --------------------------------------------------------------
            # Publish **all mandatory GSPy-compatible attributes**
            # --------------------------------------------------------------
            # Static
            self.Tsa   = O.Ts
            self.Psa   = O.Ps
            # Totals
            self.Tta   = O.Tt
            self.Pta   = O.Pt
            # Flight
            self.Macha = O.MN
            self.V = O.VTAS   # GSPy uses "V" = VTAS
            # AS210-specific outputs
            self.TsDay = O.TsDay
            self.dTs = O.dTs
            self.dTsStd = O.dTsStd
            self.humRel = O.humRel
            self.humSp = O.humSp
            self.VEAS = O.VEAS
            self.VCAS = O.VCAS
            self.VTAS = O.VTAS

            # --------------------------------------------------------------
            # Set the inlet state in Cantera (if available)
            # --------------------------------------------------------------
            if ct is not None and self.owner is not None:
                gas = fg.gas
                self.Gas_Ambient = ct.Quantity(gas)
                self.owner.gaspath_conditions[self.station_nr] = self.Gas_Ambient

                dry_comp = str(fg.s_air_composition_mass).strip()

                if O.humSp > 0.0:
                    if "H2O" not in gas.species_names:
                        raise ValueError(
                            "Humidity requested but H2O is not present in the Cantera gas model."
                        )

                    y_h2o = float(O.humSp)
                    y_dry = 1.0 - y_h2o

                    if y_dry < 0.0 or y_h2o > 1.0:
                        raise ValueError(
                            f"Invalid specific humidity for Cantera composition: humSp={O.humSp}"
                        )

                    Y = scale_composition_string(dry_comp, y_dry)
                    Y["H2O"] = y_h2o

                    # normalize for safety
                    y_sum = sum(Y.values())
                    if y_sum <= 0.0:
                        raise ValueError("Invalid composition: mass fractions sum to zero.")
                    Y = {k: v / y_sum for k, v in Y.items()}

                    comp = ", ".join(f"{k}:{v:.12g}" for k, v in Y.items())
                else:
                    comp = dry_comp

                self.Gas_Ambient.TPY = O.Tt, O.Pt, comp
            else:
                self.Gas_Ambient = None

            # self.print_ambient_composition(threshold=1e-12, basis="mass")

        def _active_input_values(self):
            I = self.last_inputs
            if I is None:
                return {}

            engine = Ambient_AS210()
            press_sel, temp_sel, speed_sel = engine._parse_switch_mode(I.switchMode)

            inputs = {
                'alt_in': None,
                'dTs_in': None,
                'humRel_in': None,
                'humSp_in': None,
                'MN_in': None,
                'Ps_in': None,
                'Pt_in': None,
                'Ts_in': None,
                'Tt_in': None,
                'VEAS_in': None,
                'VCAS_in': None,
                'VTAS_in': None,
                'switchDay': I.switchDay,
                'switchHum': I.switchHum,
                'switchMode': I.switchMode,
            }

            if press_sel == 'AL':
                inputs['alt_in'] = I.alt_in
            elif press_sel == 'PS':
                inputs['Ps_in'] = I.Ps_in

            if temp_sel == 'DT':
                inputs['dTs_in'] = I.dTs_in
            elif temp_sel == 'TS':
                inputs['Ts_in'] = I.Ts_in
            elif temp_sel == 'TT':
                inputs['Tt_in'] = I.Tt_in

            if speed_sel == 'MN':
                inputs['MN_in'] = I.MN_in
            elif speed_sel == 'VC':
                inputs['VCAS_in'] = I.VCAS_in
            elif speed_sel == 'VE':
                inputs['VEAS_in'] = I.VEAS_in
            elif speed_sel == 'VT':
                inputs['VTAS_in'] = I.VTAS_in

            humidity_sel = (I.switchHum or 'RH').upper()
            if humidity_sel == 'RH':
                inputs['humRel_in'] = I.humRel_in
            elif humidity_sel == 'SH':
                inputs['humSp_in'] = I.humSp_in

            return inputs

        def get_outputs(self):
            s = self.station_nr
            active_inputs = self._active_input_values()
            O = self.outputs

            outputs = {
                # Explicitly selected ambient inputs (options have no _in suffix)
                'alt_in': active_inputs.get('alt_in'),
                'dTs_in': active_inputs.get('dTs_in'),
                'humRel_in': active_inputs.get('humRel_in'),
                'humSp_in': active_inputs.get('humSp_in'),
                'MN_in': active_inputs.get('MN_in'),
                'Ps_in': active_inputs.get('Ps_in'),
                'Pt_in': active_inputs.get('Pt_in'),
                'Ts_in': active_inputs.get('Ts_in'),
                'Tt_in': active_inputs.get('Tt_in'),
                'VEAS_in': active_inputs.get('VEAS_in'),
                'VCAS_in': active_inputs.get('VCAS_in'),
                'VTAS_in': active_inputs.get('VTAS_in'),
                'switchDay': active_inputs.get('switchDay'),
                'switchHum': active_inputs.get('switchHum'),
                'switchMode': active_inputs.get('switchMode'),

                # Structured ambient/station outputs
                f'TsDay': getattr(O, 'TsDay', None) if O else None,
                f'dTsStd': getattr(O, 'dTsStd', None) if O else None,
                f'alt': getattr(O, 'alt', None) if O else None,
                f'dTs': getattr(O, 'dTs', None) if O else None,
                f'humRel': getattr(O, 'humRel', None) if O else None,
                f'humSp': getattr(O, 'humSp', None) if O else None,
                f'MN{s}': getattr(O, 'MN', None) if O else None,
                f'Ps{s}': getattr(O, 'Ps', None) if O else None,
                f'P{s}': getattr(O, 'Pt', None) if O else None,
                f'Ts{s}': getattr(O, 'Ts', None) if O else None,
                f'T{s}': getattr(O, 'Tt', None) if O else None,
                f'VEAS{s}': getattr(O, 'VEAS', None) if O else None,
                f'VCAS{s}': getattr(O, 'VCAS', None) if O else None,
                f'VTAS{s}': getattr(O, 'VTAS', None) if O else None,
            }
            return outputs
