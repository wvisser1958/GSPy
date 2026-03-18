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
from typing import Dict, Optional
import math
import numpy as np

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
    """ISA temperature at geometric altitude (approx) using aerocalc if available."""
    if ac is not None:
        try:
            return ac.std_atm.alt2temp(alt_m, alt_units='m', temp_units='K')
        except Exception:
            pass
    # Fallback to piecewise ISA up to 32 km (sufficient for this use)
    # Layers: 0–11 km (L=-6.5 K/km); 11–20 km (isothermal 216.65 K); 20–32 km (+1.0 K/km)
    h = float(alt_m)
    if h <= 11_000.0:
        return T0 - 0.0065 * h
    elif h <= 20_000.0:
        return 216.65
    else:
        return 216.65 + 0.001 * (h - 20_000.0)


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

# ---- API ----
@dataclass
class AmbientInputs:
    alt_in: float
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
    switchDay: str = 'STANDARD'  # e.g. 'STANDARD' | 'HOT' | 'COLD' | '5PCTHOT' | ...
    switchHum: str = 'RH'        # 'RH' -> use humRel_in, 'SH' -> use humSp_in, '-' -> dry
    switchMode: str = 'MN'       # 'MN' | 'VTAS' | 'VEAS' | 'VCAS' | 'Tt' | 'Pt'

@dataclass
class AmbientOutputs:
    alt: float
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
    - Flight condition selection via switchMode: 'MN' (preferred), 'VTAS', 'VEAS', 'VCAS', 'Tt', 'Pt'.
    """

    def __init__(self):
        self.outputs: Optional[AmbientOutputs] = None

    # ---- Core compute ----
    def run(self, I: AmbientInputs) -> AmbientOutputs:
        alt = float(I.alt_in)

        # Day temperature at altitude (single profile)
        TsDay = profile_temp(str(I.switchDay), alt)
        TsStd = _isa_temp(alt)

        # Ts
        Ts = I.Ts_in if I.Ts_in is not None else TsDay + (I.dTs_in or 0.0)
        dTs = Ts - TsDay
        dTsStd = Ts - TsStd

        # Ps (from ISA vs pressure altitude unless overridden)
        Ps = I.Ps_in if I.Ps_in is not None else self._isa_pressure(alt)

        # Mach / speeds
        a = speed_of_sound(Ts)
        MN: float
        mode = (I.switchMode or 'MN').upper()

        if mode == 'MN' and I.MN_in is not None:
            MN = max(0.0, float(I.MN_in))
        elif mode == 'VTAS' and I.VTAS_in is not None:
            MN = max(0.0, float(I.VTAS_in) / a)
        elif mode == 'VEAS' and I.VEAS_in is not None:
            rho = rho_from_P_T(Ps, Ts)
            vtas = vtas_from_veas_rho(float(I.VEAS_in), rho)
            MN = max(0.0, vtas / a)
        elif mode == 'VCAS' and I.VCAS_in is not None:
            MN = M_from_vcas(Ps, float(I.VCAS_in))
        elif mode == 'TT' and I.Tt_in is not None:
            MN = M_from_total_T(Ts, float(I.Tt_in))
        elif mode == 'PT' and I.Pt_in is not None:
            MN = M_from_total_P(Ps, float(I.Pt_in))
        else:
            # Default: fallbacks in priority
            if I.MN_in is not None:
                MN = max(0.0, float(I.MN_in))
            elif I.VTAS_in is not None:
                MN = max(0.0, float(I.VTAS_in) / a)
            elif I.VEAS_in is not None:
                rho = rho_from_P_T(Ps, Ts)
                vtas = vtas_from_veas_rho(float(I.VEAS_in), rho)
                MN = max(0.0, vtas / a)
            elif I.VCAS_in is not None:
                MN = M_from_vcas(Ps, float(I.VCAS_in))
            elif I.Tt_in is not None:
                MN = M_from_total_T(Ts, float(I.Tt_in))
            elif I.Pt_in is not None:
                MN = M_from_total_P(Ps, float(I.Pt_in))
            else:
                MN = 0.0

        # Totals
        Tt = I.Tt_in if I.Tt_in is not None else total_T_from_M(Ts, MN)
        Pt = I.Pt_in if I.Pt_in is not None else total_P_from_M(Ps, MN)

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
        VTAS = I.VTAS_in if I.VTAS_in is not None else MN * a
        rho = rho_from_P_T(Ps, Ts)
        VEAS = I.VEAS_in if I.VEAS_in is not None else veas_from_vtas_rho(VTAS, rho)
        VCAS = I.VCAS_in if I.VCAS_in is not None else vcas_from_M(Ps, MN)

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
            TsDay=TsDay,
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
            TAmbient_AS210(name, stationnr, Altitude, Macha, dTs, Psa, Tsa)

        Additional optional configuration:
            SetConditionsAS210(switchDay='STANDARD', switchHum='RH',
                               humRel_in=None, humSp_in=None)
        """

        def __init__(self, name, stationnr, Altitude, Macha, dTs=None, Psa=None, Tsa=None):
            super().__init__(name, '', None)
            self.stationnr = stationnr

            # Store DP conditions (GSPy convention)
            self.SetConditions('DP', Altitude, Macha, dTs, Psa, Tsa)

            # Defaults for the AS210 additions
            self.switchDay = 'STANDARD'
            self.switchHum = 'RH'
            self.humRel_in = None
            self.humSp_in = None

        # ------------------------------------------------------------------
        # User-facing configuration of AS210 day type and humidity handling
        # ------------------------------------------------------------------
        def SetConditionsAS210(self, switchDay='STANDARD', switchHum='RH',
                               humRel_in=None, humSp_in=None):
            self.switchDay = switchDay
            self.switchHum = switchHum
            self.humRel_in = humRel_in
            self.humSp_in = humSp_in

        # ------------------------------------------------------------------
        # Store DP or OD conditions for later use
        # ------------------------------------------------------------------
        def SetConditions(self, Mode, Altitude, Macha, dTs, Psa, Tsa):
            if Mode == 'DP':
                self.Altitude_des = Altitude
                self.Macha_des = Macha
                self.dTs_des = dTs
                self.Psa_des = Psa
                self.Tsa_des = Tsa
            else:
                self.Altitude = Altitude
                self.Macha = Macha
                self.dTs = dTs
                self.Psa = Psa
                self.Tsa = Tsa

        # ------------------------------------------------------------------
        # Core of the adapter — executed every DP or OD simulation step
        # ------------------------------------------------------------------
        def Run(self, Mode, PointTime):

            # Apply DP conditions if needed (GSPy convention)
            if Mode == 'DP':
                self.Altitude = self.Altitude_des
                self.Macha    = self.Macha_des
                self.dTs      = self.dTs_des
                self.Psa      = self.Psa_des
                self.Tsa      = self.Tsa_des

            # Build the input object for the AS210 computational model
            inputs = AmbientInputs(
                alt_in=self.Altitude,
                dTs_in=self.dTs,
                MN_in=self.Macha,
                Ps_in=self.Psa,
                Ts_in=self.Tsa,
                switchDay=self.switchDay,
                switchHum=self.switchHum,
                humRel_in=self.humRel_in,
                humSp_in=self.humSp_in,
                switchMode='MN'
            )

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
            self.V     = O.VTAS   # GSPy uses "V" = VTAS
            # AS210-specific
            self.TsDay = O.TsDay  # <-- REQUIRED to avoid AttributeError
            self.VEAS  = O.VEAS
            self.VCAS  = O.VCAS

            # --------------------------------------------------------------
            # Set the inlet state in Cantera (if available)
            # --------------------------------------------------------------
            if ct is not None:
                self.Gas_Ambient = ct.Quantity(fg.gas)
                fsys.gaspath_conditions[self.stationnr] = self.Gas_Ambient
                self.Gas_Ambient.TPY = O.Tt, O.Pt, fg.s_air_composition_mass
            else:
                self.Gas_Ambient = None

        # ------------------------------------------------------------------
        # Push outputs into gspy.core.system output dictionary
        # ------------------------------------------------------------------
        def AddOutputToDict(self, Mode):
            fsys.output_dict["Alt"]      = getattr(self, 'Altitude', None)
            fsys.output_dict["dTs"]      = getattr(self, 'dTs', None)
            fsys.output_dict["dTsStd"]   = getattr(self.outputs, "dTsStd", None)
            fsys.output_dict["Tsa"]      = getattr(self, 'Tsa', None)
            fsys.output_dict["Psa"]      = getattr(self, 'Psa', None)
            fsys.output_dict["Tta"]      = getattr(self, 'Tta', None)
            fsys.output_dict["Pta"]      = getattr(self, 'Pta', None)
            fsys.output_dict["Macha"]    = getattr(self, 'Macha', None)

            # AS210-specific outputs
            fsys.output_dict["TsDay"]    = getattr(self, 'TsDay', None)
            fsys.output_dict["VEAS"]     = getattr(self, 'VEAS', None)
            fsys.output_dict["VCAS"]     = getattr(self, 'VCAS', None)
            fsys.output_dict["VTAS"]     = getattr(self, 'V', None)
            fsys.output_dict["switchDay"]= getattr(self, 'switchDay', None)
