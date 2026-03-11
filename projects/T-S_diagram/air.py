import numpy as np
import matplotlib.pyplot as plt
import cantera as ct

# --- Settings ---
T_C = np.linspace(-20.0, 1700.0, 600)
T_K = T_C + 273.15
p_bar_list = [1, 2, 5, 10, 25]
p_Pa_list = [p * 1e5 for p in p_bar_list]  # 1 bar = 1e5 Pa

LABEL_ANGLE_DEG = 60   # <-- change this to whatever you like
LABEL_IDX = 510        # <-- where along the curve to place labels (0..len(T_C)-1)

# Gas object
gas = ct.Solution("gri30.yaml")
gas.X = {"O2": 0.21, "N2": 0.79}  # Air (frozen composition)

fig, ax = plt.subplots(figsize=(8, 6))

# Store entropy curves for clipping iso-entropy lines
s_data = {}

# --- Plot isobars and add labels ---
for j, (p_bar, p) in enumerate(zip(p_bar_list, p_Pa_list)):
    s_vals = np.empty_like(T_K, dtype=float)

    for i, T in enumerate(T_K):
        gas.TP = T, p
        s_vals[i] = gas.entropy_mass  # J/kg/K

    s_vals = s_vals / 1000.0  # kJ/kg/K
    ax.plot(s_vals, T_C)

    if p_bar in [1, 25]:
        s_data[p_bar] = s_vals.copy()

    # Label text: first one "p = 1 bar", others just the number
    label_text = f"p = {p_bar} bar" if j == 0 else f"{p_bar}"

    # Place label with fixed rotation (so it's easy to control)
    idx = max(2, min(LABEL_IDX, len(T_C) - 3))
    ax.annotate(
        label_text,
        xy=(s_vals[idx], T_C[idx]),
        xytext=(6, 0),
        textcoords="offset points",
        rotation=LABEL_ANGLE_DEG,
        rotation_mode="anchor",
        ha="left",
        va="center",
        fontsize=10
    )

# --- Bounded iso-entropy lines (vertical segments clipped to 1-25 bar) ---
s_const_values = [7, 8]  # kJ/kg/K

for s_const in s_const_values:
    # Draw only if within entropy range of the envelope
    if (s_const >= s_data[25].min()) and (s_const <= s_data[1].max()):
        # Assumes s(T) is monotonic for these isobars over the chosen T range
        T_low = np.interp(s_const, s_data[25], T_C)
        T_high = np.interp(s_const, s_data[1], T_C)

        ax.plot(
            [s_const, s_const],
            [T_low, T_high],
            linestyle="--",
            linewidth=2,
            label=f"s = {s_const} kJ/kg/K"
        )

# --- Formatting ---
ax.set_xlabel("Specific entropy, s (kJ/kg/K)")
ax.set_ylabel("Temperature, T (°C)")
ax.set_title("T-s Diagram with Isobars (1-25 bar)")
ax.grid(True)
ax.legend()
fig.tight_layout()
plt.show()
