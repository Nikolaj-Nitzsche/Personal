import numpy as np
import matplotlib.pyplot as plt
import sys
from scipy.optimize import curve_fit
from scipy.signal import find_peaks
import json
import argparse

# Plot settings
plt.rcParams.update({'font.size': 24,})
plt.rcParams.update({'figure.autolayout': True})
PL_color = "inferno"
contrast_color = "plasma"
ps_color = "viridis"
fshift_color = "cividis"
interpolation = "nearest"

# Strain constants
d_perp = 0.8e9  # Hz
d_axial = 1.54e9  # Hz

def Lorentzian(x, I, x0, gamma):
    """Three-parameter Lorentzian."""
    return I * (gamma**2 / ((x - x0)**2 + gamma**2))

def double_dip(x, height, distance, center, gamma, max_value):
    """Double Lorentzian dip fitting function."""
    loc1 = center - 0.5 * distance
    loc2 = center + 0.5 * distance
    peak1 = Lorentzian(x, height, loc1, gamma)
    peak2 = Lorentzian(x, height, loc2, gamma)
    return max_value - peak1 - peak2

def fit_double_dip(x, PL_graph):
    """Fits a double dip on a normalized PL map."""
    popt, _ = curve_fit(
        double_dip,
        x,
        PL_graph,
        p0=[0.1, 4e7, 2.87e9, 2e7, 1],
        bounds=([0, 0, 2.8e9, 0, 0.5], [1.5, 1e8, 3.0e9, 1e8, 1.5]),
    )
    return popt

def format_coord(x, y):
    return f'z = {y:.2f} μm, y = {x:.2f} μm'

def plot_map(data, settings, color_label, unit_conversion_factor=1, title=None, suffix="out.png", filename_base="", cmap="Inferno"):
    """Creates a 2D color map with equal aspect ratio and improved sizing."""

    y_extent = [settings["y1"] * 1e6, settings["y2"] * 1e6]
    z_extent = [settings["z1"] * 1e6, settings["z2"] * 1e6]
    y_steps, z_steps = data.shape

    pixel_aspect_ratio = (y_extent[1] - y_extent[0]) / y_steps / ((z_extent[1] - z_extent[0]) / z_steps)

    plt.figure(figsize=(12, 12))
    img = plt.imshow(
        data.T * unit_conversion_factor,
        cmap=cmap,
        interpolation="nearest",
        extent=[y_extent[0], y_extent[1], z_extent[0], z_extent[1]],
        origin="lower",
        aspect=pixel_aspect_ratio
    )
    plt.gca().invert_yaxis()
    plt.xlabel("y ($\mu$m)", fontweight="normal")
    plt.ylabel("z ($\mu$m)", fontweight="normal")

    cb = plt.colorbar(img)
    cb.set_label(color_label, rotation=270, fontweight="normal", labelpad=30)

    # Set custom coordinate display
    plt.gca().format_coord = format_coord

    plt.savefig(filename_base + suffix, dpi=100, transparent=False, bbox_inches="tight")
    plt.show()


def main() -> int:
    parser = argparse.ArgumentParser(description="Process 2D or 3D ODMR/PL data.")
    parser.add_argument('filename', help="Path to the .npy file to process. Requires a matching .json file for settings.")
    args = parser.parse_args()
    filename = args.filename
    filename_base = filename[:-4]
    settings_file = filename_base + ".json"  # JSON settings file

    # Load data and settings
    try:
        PL = np.load(filename)
        with open(settings_file, 'r') as f:
            settings = json.load(f)
    except Exception as e:
        print(f"Error loading files: {e}")
        return 1

    # Determine the measurement type and process accordingly
    if len(PL.shape) == 1:
        # 1D z-scan
        zmove = np.linspace(settings["z1"], settings["z2"], settings["z_steps"]) * 1e6  # Convert to microns
        plt.figure()
        plt.plot(zmove, PL)
        plt.xlabel("z ($\mu$m)")
        plt.ylabel("I (counts/s)")
        plt.savefig(filename_base + "_plot.png", dpi=100, transparent=False, bbox_inches="tight")
        plt.show()
        return 0

    elif len(PL.shape) == 2:
        # 2D y-z map
        plot_map(PL, settings, "counts/s", 1, title="PL map", suffix="_plot_PL.png", filename_base=filename_base, cmap=PL_color)
        plot_map(np.log10(PL), settings, "log PL ($_{10}$log counts/s)", 1, title="Log PL map", suffix="_plot_log_PL.png", filename_base=filename_base, cmap=PL_color)
        return 0

    if settings["measurement_type"] == "3DPL":
        # 3D PL processing
        y_steps = settings["y_steps"]
        z_steps = settings["z_steps"]
        z_arr = np.linspace(settings["z1"], settings["z2"], settings["z_steps"]) * 1e6  # Convert to microns
        y_arr = np.linspace(settings["y1"], settings["y2"], settings["y_steps"]) * 1e6  # Convert to microns

        # Compute height maps
        count_threshold = 1000
        top_surface = np.zeros((y_steps,))
        back_surface = np.zeros((y_steps,))
        for iy in range(y_steps):
            # Find top and back surface
            for iz in range(z_steps):
                if PL[iy, iz] > count_threshold:
                    top_surface[iy] = z_arr[iz]
                    break
            for iz in range(z_steps - 1, -1, -1):
                if PL[iy, iz] > count_threshold:
                    back_surface[iy] = z_arr[iz]
                    break

        thickness_map = np.abs(top_surface - back_surface)

        # Plot results
        plot_map(np.clip(top_surface, z_arr[0], z_arr[-1]), settings, "z ($\mu$m)", 1, title="Top Surface Height Map", suffix="_top_surface.png", filename_base=filename_base, cmap=PL_color)
        plot_map(np.clip(back_surface, z_arr[0], z_arr[-1]), settings, "z ($\mu$m)", 1, title="Back Surface Height Map", suffix="_back_surface.png", filename_base=filename_base, cmap=PL_color)
        plot_map(thickness_map, settings, "Δz ($\mu$m)", 1, title="Thickness Map", suffix="_thickness.png", filename_base=filename_base, cmap=PL_color)
        return 0

    print("Unknown data shape. Exiting.")
    return 1


if __name__ == "__main__":
    exitcode = main()
    if exitcode != 0:
        sys.exit(exitcode)