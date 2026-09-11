"""
Joint distribution of water supply (W) and water demand (D).

- Marginals: gamma, loc=0 (locked at zero)
- Dependence: gaussian copula (rank correlation), so marginals stay exactly gamma
- Joint panel: hexbin density
- Red 1:1 line D = W -> region above it is water insecurity (D > W)

Output: SVG with live text and vector hexagons, ready for Inkscape.
"""

import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from scipy.stats import gamma, norm

# ----------------------------------------------------------------------
# parameters
# ----------------------------------------------------------------------
SEED = 42

# gamma(shape a, scale) with loc = 0
W_A, W_SCALE = 3.00, 7.50     # supply: mode = 15, mean = 22.5, broad with right tail
D_A, D_SCALE = 1.80, 5.00     # demand: mode = 4.0, mean = 9.0, still zero-anchored

RHO = -0.50                   # copula correlation (dry year: less supply, more demand)
N_PLOT = 60_000               # points fed to hexbin
N_MC = 2_000_000              # points for P(D > W)

GRIDSIZE = 32
CMAP = "YlGnBu"
INSEC_COLOR = "#b2182b"

# ----------------------------------------------------------------------
# sampling: gaussian copula + gamma marginals
# ----------------------------------------------------------------------
def sample(n, rho, seed):
    rng = np.random.default_rng(seed)
    cov = np.array([[1.0, rho], [rho, 1.0]])
    z = rng.multivariate_normal(np.zeros(2), cov, size=n)
    u = norm.cdf(z)
    w = gamma.ppf(u[:, 0], W_A, loc=0.0, scale=W_SCALE)
    d = gamma.ppf(u[:, 1], D_A, loc=0.0, scale=D_SCALE)
    return w, d


w, d = sample(N_PLOT, RHO, SEED)
w_mc, d_mc = sample(N_MC, RHO, SEED + 1)
p_insecure = float(np.mean(d_mc > w_mc))
print(f"P(D > W) = {p_insecure:.4f}")

# ----------------------------------------------------------------------
# figure
# ----------------------------------------------------------------------
mpl.rcParams.update({
    "svg.fonttype": "none",      # keep text editable in Inkscape
    "font.family": "sans-serif",
    "font.size": 9,
    "axes.linewidth": 0.8,
    "path.simplify": False,
})

LIM = 55.0
fig = plt.figure(figsize=(6.9, 6.9))
gs = GridSpec(
    2, 2,
    width_ratios=[1, 3], height_ratios=[3, 1],
    wspace=0.06, hspace=0.06, figure=fig,
)

ax_j = fig.add_subplot(gs[0, 1])                     # joint
ax_d = fig.add_subplot(gs[0, 0], sharey=ax_j)        # left marginal, f_D(x)
ax_w = fig.add_subplot(gs[1, 1], sharex=ax_j)        # bottom marginal, f_W(x)
fig.add_subplot(gs[1, 0]).axis("off")

# --- joint panel -------------------------------------------------------
hb = ax_j.hexbin(
    w, d,
    gridsize=GRIDSIZE, extent=(0, LIM, 0, LIM),
    cmap=CMAP, mincnt=2, linewidths=0.0, bins="log",
)

# insecurity region: above the 1:1 line
ax_j.fill_between([0, LIM], [0, LIM], [LIM, LIM],
                  color=INSEC_COLOR, alpha=0.08, lw=0, zorder=3)
ax_j.plot([0, LIM], [0, LIM], color=INSEC_COLOR, lw=1.4, zorder=4)

ax_j.annotate(
    f"water insecurity\n$D > W$\n$P = {p_insecure:.2f}$",
    xy=(0.24 * LIM, 0.72 * LIM), color=INSEC_COLOR,
    ha="center", va="center", fontsize=9, zorder=5,
)

ax_j.set_xlim(0, LIM)
ax_j.set_ylim(0, LIM)
ax_j.set_aspect("equal")
ax_j.tick_params(labelbottom=False, labelleft=False, length=3)
for s in ("top", "right"):
    ax_j.spines[s].set_visible(False)

# --- left marginal: demand (pdf drawn horizontally, axis mirrored) ------
x = np.linspace(0, LIM, 600)
pdf_d = gamma.pdf(x, D_A, loc=0.0, scale=D_SCALE)
pdf_w = gamma.pdf(x, W_A, loc=0.0, scale=W_SCALE)

ax_d.plot(pdf_d, x, color="#1a3a6b", lw=1.6)
ax_d.fill_betweenx(x, 0, pdf_d, color="#1a3a6b", alpha=0.10, lw=0)
ax_d.set_xlim(1.12 * pdf_d.max(), 0)      # mirrored: grows leftwards
ax_d.set_ylabel("Water demand, $D$")
ax_d.set_xlabel("$f_D(x)$")
ax_d.tick_params(labelbottom=False, length=3)
for s in ("top", "right"):
    ax_d.spines[s].set_visible(False)

# --- bottom marginal: supply ------------------------------------------
ax_w.plot(x, pdf_w, color="#1a3a6b", lw=1.6)
ax_w.fill_between(x, 0, pdf_w, color="#1a3a6b", alpha=0.10, lw=0)
ax_w.set_ylim(0, 1.12 * pdf_w.max())      # grows upwards, baseline at top axis
ax_w.set_xlabel("Water supply, $W$")
ax_w.set_ylabel("$f_W(x)$")
ax_w.tick_params(labelleft=False, length=3)
for s in ("top", "right"):
    ax_w.spines[s].set_visible(False)

# --- colorbar ----------------------------------------------------------
cax = fig.add_axes([0.135, 0.16, 0.135, 0.020])
cb = fig.colorbar(hb, cax=cax, orientation="horizontal")
cb.set_label("joint density (log count)", fontsize=8)
cb.ax.tick_params(labelsize=7, length=2)
cb.outline.set_linewidth(0.6)

fig.savefig("/mnt/user-data/outputs/water_supply_demand_joint.svg",
            format="svg", bbox_inches="tight", transparent=True)
print("saved")
