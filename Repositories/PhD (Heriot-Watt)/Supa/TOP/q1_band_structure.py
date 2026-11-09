"""
PH5024 Problem Sheet 1, Question 1
Band structure of the 2D square-lattice nearest-neighbour tight-binding model
along the path Gamma - M - X - Gamma.

High-symmetry points use the labelling given on the problem sheet:
    Gamma = (0, 0), M = (1, 0), X = (1, 1)   in units of pi/a.
(Note: many textbooks use the opposite names, X = (pi/a, 0) and M = (pi/a, pi/a).)
"""

import numpy as np
import matplotlib.pyplot as plt

# ---------------------------------------------------------------------------
# Step 1: parameters
# ---------------------------------------------------------------------------
t = 0.1            # nearest-neighbour hopping integral (eV), from the sheet
a = 1.0            # lattice constant; a = 1 means k is measured in units of 1/a
n_per_unit = 200   # number of k-points per unit of path length (path length in pi/a)


# ---------------------------------------------------------------------------
# Step 2: the dispersion relation (lecture notes, Eq. 86)
# ---------------------------------------------------------------------------
def dispersion(kx, ky, t=t, a=a):
    """Band energy eps(k) in eV.

    kx, ky are in units of 1/a. They can be single numbers or numpy arrays;
    numpy then evaluates the formula for every element at once.
    """
    return -2.0 * t * (np.cos(kx * a) + np.cos(ky * a))


# ---------------------------------------------------------------------------
# Step 3: the corners of the path, in units of pi/a
# ---------------------------------------------------------------------------
G = np.array([0.0, 0.0])   # Gamma
M = np.array([1.0, 0.0])   # M (sheet's labelling)
X = np.array([1.0, 1.0])   # X (sheet's labelling)

corners = [G, M, X, G]
corner_labels = [r"$\Gamma$", "M", "X", r"$\Gamma$"]


# ---------------------------------------------------------------------------
# Step 4: build the list of k-points along the path
# ---------------------------------------------------------------------------
def build_path(corners, n_per_unit):
    """Return the k-points along a piecewise-straight path, plus distances.

    Each straight segment from 'start' to 'end' is parametrised as
        k(s) = start + s * (end - start),   0 <= s < 1.
    s = 0 gives 'start'; s = 1 would give 'end'. We leave out s = 1 on each
    segment (endpoint=False) so the corner points are not included twice,
    and add the very last corner by hand at the end.
    """
    segments = []
    for start, end in zip(corners[:-1], corners[1:]):
        seg_length = np.linalg.norm(end - start)          # Pythagoras
        n = max(2, int(round(n_per_unit * seg_length)))   # points on this segment
        s = np.linspace(0.0, 1.0, n, endpoint=False)      # n values of s in [0, 1)
        segments.append(start + s[:, None] * (end - start))
    segments.append(corners[-1][None, :])                 # final corner
    k_path = np.vstack(segments)                           # shape (N, 2)

    # Distance travelled along the path, used as the horizontal plot axis.
    step_lengths = np.linalg.norm(np.diff(k_path, axis=0), axis=1)
    distance = np.concatenate(([0.0], np.cumsum(step_lengths)))

    # Where each corner sits on that axis (for tick marks and vertical lines).
    seg_lengths = [np.linalg.norm(e - s) for s, e in zip(corners[:-1], corners[1:])]
    corner_distance = np.concatenate(([0.0], np.cumsum(seg_lengths)))

    return k_path, distance, corner_distance


k_path, distance, corner_distance = build_path(corners, n_per_unit)

# Convert from units of pi/a to units of 1/a before evaluating cosines.
kx = np.pi * k_path[:, 0] / a
ky = np.pi * k_path[:, 1] / a


# ---------------------------------------------------------------------------
# Step 5: evaluate the band energy at every k-point on the path
# ---------------------------------------------------------------------------
energy = dispersion(kx, ky)


# ---------------------------------------------------------------------------
# Step 6: sanity check -- compare with values you can work out by hand
# ---------------------------------------------------------------------------
for label, k in zip(["Gamma", "M", "X"], [G, M, X]):
    e = dispersion(np.pi * k[0] / a, np.pi * k[1] / a)
    print(f"eps({label}) = {e:+.4f} eV")


# ---------------------------------------------------------------------------
# Step 7: plot
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(6, 4))
ax.plot(distance, energy, color="C0", lw=2)

for d in corner_distance:
    ax.axvline(d, color="grey", lw=0.8)

ax.set_xticks(corner_distance)
ax.set_xticklabels(corner_labels)
ax.set_xlim(corner_distance[0], corner_distance[-1])
ax.set_ylabel("Energy (eV)")
ax.set_xlabel(r"Wavevector along path (path length in units of $\pi/a$)")
ax.set_title(f"Square-lattice tight-binding band, t = {t} eV")

fig.tight_layout()
fig.savefig("q1_band_structure.png", dpi=200)
plt.show()
