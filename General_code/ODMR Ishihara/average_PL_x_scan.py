import os
import numpy as np
import matplotlib.pyplot as plt

# ─── User parameters ───────────────────────────────────────────────
folder = "/home/dl-lab-pc3/Documents/Nikolaj_Nitzsche/Cryo/2D_mapping/test_1"
x_start = 2946e-6       # X‐scan start position (m)
x_end   = 2950e-6       # X‐scan end position (m)
# ────────────────────────────────────────────────────────────────────

# Load all .npy files
files = sorted([f for f in os.listdir(folder) if f.endswith(".npy")])
if not files:
    raise ValueError(f"No .npy files found in {folder}")

data_list = [np.load(os.path.join(folder, f)) for f in files]

# Compute mean and standard deviation
stacked = np.vstack(data_list)              # shape: (n_scans, n_points)
mean_pl = np.mean(stacked, axis=0)
std_pl  = np.std(stacked, axis=0)

# Build the real X-axis values
n_points = mean_pl.size
x_values = np.linspace(x_start, x_end, n_points)

# Configure font to Cambria Math
plt.rc('font', family='serif', serif=['Cambria Math'])
plt.rc('mathtext', fontset='stix')  # use a math font compatible with serif

# Plot
plt.figure(figsize=(10, 6))
plt.plot(x_values, mean_pl, label=r"$\overline{\mathrm{PL}}$")
plt.fill_between(x_values,
                 mean_pl - std_pl,
                 mean_pl + std_pl,
                 alpha=0.3,
                 label=r"$\pm1\sigma$")
plt.xlabel(r"$x\ (\mathrm{m})$")
plt.ylabel(r"PL counts (Hz)")
plt.title("Average PL vs X Position")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()
