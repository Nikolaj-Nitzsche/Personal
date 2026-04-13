from fit.get_data import widefield_get_data
import os
import re
import xarray as xr
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter

# --- Paths ---
folder = r"\\tsn.tno.nl\RA-Data\SV\sv-096125\03_Widefield\Data\Stark\2025_09_09"
fit_folder = os.path.join(folder, "fit_results")
refit_folder = os.path.join(folder, "fit_results_refit")
refit_folder_manual = os.path.join(folder, "fit_results_refit_manual")
output_gif = r"C:\Users\nitzschenk\OneDrive - TNO\Documents\Data\Pole piece\Magnetic_measurements\esr_fits.gif"

# --- Collect ODMR fit files ---
fit_files_odmr = [f for f in os.listdir(fit_folder) if f.endswith("odmr_fit.h5")][0:450]
odmr_fit_dict = {}
for f in fit_files_odmr:
    match = re.search(r"(\d{8}_\d{6})", f)
    if match:
        odmr_fit_dict[match.group(1)] = f

# --- Collect B-field fit files ---
fit_files_B = [f for f in os.listdir(fit_folder) if f.endswith("B_fit.h5")][0:450]

redchi_list = []

for fit_file in fit_files_B:
    try:
        # Extract timestamp
        match = re.search(r"(\d{8}_\d{6})", fit_file)
        if not match:
            continue
        timestamp = match.group(1)

        # Prefer re-fit if exists
        refit_file = f"{timestamp}_esr_B_refit.h5"

        if os.path.exists(os.path.join(refit_folder_manual, refit_file)):
            fit_path = os.path.join(refit_folder_manual, refit_file)
            print(f"Using re-fit B-field: {refit_file}---------")
        elif os.path.exists(os.path.join(refit_folder, refit_file)):
            fit_path = os.path.join(refit_folder, refit_file)
            print(f"Using re-fit B-field: {refit_file}")
        else:
            fit_path = os.path.join(fit_folder, fit_file)
            print(f"Using original B-field: {fit_file}")

        # Load dataset
        fit_ds = xr.load_dataset(fit_path, engine="h5netcdf")

        # Get redchi
        redchi = fit_ds.redchi.values.item()

        # Corresponding raw ESR file
        raw_file = f"{timestamp}_esr.h5"
        if not os.path.exists(os.path.join(folder, raw_file)):
            continue

        # Corresponding ODMR fit file
        if timestamp not in odmr_fit_dict:
            continue
        odmr_fit_file = odmr_fit_dict[timestamp]

        redchi_list.append((redchi, raw_file, odmr_fit_file))

    except Exception as e:
        print(f"Skipping {fit_file}: {e}")

# --- Sort by redchi descending ---
redchi_list.sort(reverse=True, key=lambda x: x[0])
print(f"Found {len(redchi_list)} ESR fits with redchi")

# --- Animation plotting ---
fig, ax = plt.subplots(figsize=(6,4))

def update(idx):
    ax.clear()
    redchi, raw_file, fit_file = redchi_list[idx]

    # Load ESR raw data
    ds_esr, _, _ = widefield_get_data(
        folder, raw_file, esr_normalized=True,
        ql_normalized=False, get_ql=False, get_timetrace=False
    )
    ds_esr = ds_esr.sel(x=slice(200, 300), y=slice(200, 300))
    data_ds = ds_esr.mean(dim=["blocks", "y", "x"])

    # Detect frequency coordinate automatically
    freq_coord = [c for c in data_ds.coords if "freq" in c.lower()]
    if not freq_coord:
        raise ValueError(f"No frequency coordinate found in {raw_file}")
    freq = data_ds.coords[freq_coord[0]].values

    ax.plot(freq, data_ds.values, color='blue')
    ax.set_title(f"{raw_file} | redchi={redchi:.2f}")
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Signal (a.u.)")

ani = FuncAnimation(fig, update, frames=len(redchi_list), repeat=True)

# Save as GIF
ani.save(output_gif, writer=PillowWriter(fps=2))
print(f"GIF saved to {output_gif}")
