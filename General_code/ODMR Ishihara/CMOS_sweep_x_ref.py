import time
import numpy as np
import matplotlib.pyplot as plt
import os
import csv
import json
from datetime import datetime
import TimeTagger
from tqdm import tqdm
from qmi.core.context import QMI_Context
from rtcs.devices.rohde_schwarz.rs_base_signal_gen import RohdeSchwarz_Base
from pylablib.devices import Attocube

# === Instrument & sweep parameters ===
instrument_name = "SMA100B"
instrument_ip   = "169.254.91.32"
transport       = f"tcp:{instrument_ip}:5025"

start_freq   = 2.85e9
end_freq     = 2.89e9
step_size    = 1e5
sweep_freqs  = np.arange(start_freq, end_freq + step_size, step_size)
ref_freq     = start_freq       # reference frequency
rf_power     = 15
num_sweeps   = 30

# Piezo X positions (example: 4 points; change as needed)
x_positions = np.linspace(3100e-6, 3400e-6, 5)

# === Prepare folders & metadata ===
base_save_folder = "/home/dl-lab-pc3/Documents/Nikolaj_Nitzsche/Cryo/CMOS_ESR/"
os.makedirs(base_save_folder, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
measurement_folder = os.path.join(base_save_folder, f"ESR_Sweep_{timestamp}")
os.makedirs(measurement_folder, exist_ok=True)

# sub‑folders for per‑point plots
raw_folder     = os.path.join(measurement_folder, "Raw")
ref_folder     = os.path.join(measurement_folder, "Reference")
norm_folder    = os.path.join(measurement_folder, "Normalized")
overlay_folder = os.path.join(measurement_folder, "Overlay")
for fld in (raw_folder, ref_folder, norm_folder, overlay_folder):
    os.makedirs(fld, exist_ok=True)

# metadata
metadata = {
    "start_freq":         start_freq,
    "end_freq":           end_freq,
    "step_size":          step_size,
    "num_sweeps":         num_sweeps,
    "rf_power":           rf_power,
    "reference_frequency":ref_freq,
    "num_x_steps":        len(x_positions),
    "x_positions":        x_positions.tolist(),
    "timestamp":          timestamp,
    "notes":              "Interleaved reference measurement between each sweep point."
}
with open(os.path.join(measurement_folder, f"ESR_Sweep_{timestamp}.json"), 'w') as jf:
    json.dump(metadata, jf, indent=4)
print(f"Metadata saved to {measurement_folder}")

# === QMI & devices initialization ===
context = QMI_Context("rs_signal_gen_context")
context.start()
sma100b = RohdeSchwarz_Base(context, instrument_name, transport)
sma100b.open()

tagger    = TimeTagger.createTimeTaggerNetwork('localhost:41101')
countrate = TimeTagger.Countrate(tagger=tagger, channels=[5])

# === Build interleaved frequency array ===
interleaved_freqs = np.empty(len(sweep_freqs) * 2)
interleaved_freqs[0::2] = ref_freq
interleaved_freqs[1::2] = sweep_freqs

# prepare array to hold all data: (n_positions, n_sweeps, 2*n_freqs)
all_data = np.zeros(
    (len(x_positions), num_sweeps, len(interleaved_freqs)),
    dtype=float
)

try:
    # Attocube setup
    atc = Attocube.ANC350()
    for ax in (0, 1, 2):
        atc.set_frequency(ax, 800)
        atc.set_voltage(ax, 50)

    total_steps  = num_sweeps * len(interleaved_freqs) * len(x_positions)
    overall_pbar = tqdm(total=total_steps,
                        desc="Total Progress",
                        unit="step",
                        position=0,
                        dynamic_ncols=True)

    # === Main measurement loops ===
    for x_idx, x_pos in enumerate(x_positions):
        print(f"\nMoving to X = {x_pos:.6f} m ({x_idx+1}/{len(x_positions)})")
        atc.move_to(0, x_pos)
        atc.wait_move(0)

        for sweep_idx in range(num_sweeps):
            desc = f"X {x_idx+1}/{len(x_positions)}, Sweep {sweep_idx+1}/{num_sweeps}"
            with tqdm(total=len(interleaved_freqs),
                      desc=desc,
                      unit="freq",
                      position=1,
                      leave=False,
                      dynamic_ncols=True) as sweep_pbar:

                for i, freq in enumerate(interleaved_freqs):
                    sma100b.set_frequency(freq)
                    sma100b.set_power(rf_power)
                    sma100b.set_output_state(True)

                    countrate.startFor(2e11)
                    countrate.waitUntilFinished()
                    all_data[x_idx, sweep_idx, i] = countrate.getData()[0]

                    sweep_pbar.update(1)
                    overall_pbar.update(1)

                sma100b.set_output_state(False)

    overall_pbar.close()

    # === Per‑position plotting & saving ===
    for x_idx, x_pos in enumerate(x_positions):
        data = all_data[x_idx]           # shape (num_sweeps, 2*n_freqs)
        avg  = data.mean(axis=0)         # average over sweeps

        refs = avg[0::2]                 # reference PL
        raws = avg[1::2]                 # raw sweep PL
        norm = raws / refs               # normalized PL

        # 1) Raw PL
        plt.figure(figsize=(8,5))
        plt.plot(sweep_freqs/1e9, raws, linestyle='-')
        plt.xlabel("Frequency (GHz)")
        plt.ylabel("Raw PL (arb. units)")
        plt.title(f"Raw PL at X={x_pos:.6f} m")
        plt.grid(True)
        fn = os.path.join(raw_folder, f"ESR_X_{x_idx+1}_Raw.png")
        plt.savefig(fn, dpi=300)
        plt.close()

        # 2) Reference PL
        plt.figure(figsize=(8,5))
        plt.plot(sweep_freqs/1e9, refs, linestyle='-')
        plt.xlabel("Frequency (GHz)")
        plt.ylabel("Reference PL (arb. units)")
        plt.title(f"Reference PL at X={x_pos:.6f} m")
        plt.grid(True)
        fn = os.path.join(ref_folder, f"ESR_X_{x_idx+1}_Ref.png")
        plt.savefig(fn, dpi=300)
        plt.close()

        # 3) Normalized PL
        plt.figure(figsize=(8,5))
        plt.plot(sweep_freqs/1e9, norm, linestyle='-')
        plt.xlabel("Frequency (GHz)")
        plt.ylabel("Normalized PL")
        plt.title(f"Normalized PL at X={x_pos:.6f} m")
        plt.grid(True)
        fn = os.path.join(norm_folder, f"ESR_X_{x_idx+1}_Norm.png")
        plt.savefig(fn, dpi=300)
        plt.close()

        # 4) Overlay Raw & Reference
        plt.figure(figsize=(8,5))
        plt.plot(sweep_freqs/1e9, raws, linestyle='-',  label='Raw PL')
        plt.plot(sweep_freqs/1e9, refs, linestyle='--', label='Reference PL')
        plt.xlabel("Frequency (GHz)")
        plt.ylabel("PL (arb. units)")
        plt.title(f"Raw vs Reference at X={x_pos:.6f} m")
        plt.legend()
        plt.grid(True)
        fn = os.path.join(overlay_folder, f"ESR_X_{x_idx+1}_Overlay.png")
        plt.savefig(fn, dpi=300)
        plt.close()

    # === Combined‑across‑all‑X plots ===
    # first normalize per‑position, then average
    refs_mat = all_data[:, :, 0::2].mean(axis=1)   # (n_pos, n_freq)
    raw_mat  = all_data[:, :, 1::2].mean(axis=1)
    norm_mat = raw_mat / refs_mat                  # (n_pos, n_freq)

    mean_refs = refs_mat.mean(axis=0)
    mean_raws = raw_mat.mean(axis=0)
    mean_norm = norm_mat.mean(axis=0)

    # Combined Raw
    plt.figure(figsize=(8,5))
    plt.plot(sweep_freqs/1e9, mean_raws, linestyle='-')
    plt.xlabel("Frequency (GHz)")
    plt.ylabel("Avg Raw PL")
    plt.title("Combined Avg Raw PL Across All X")
    plt.grid(True)
    fn = os.path.join(measurement_folder, f"Combined_Raw_{timestamp}.png")
    plt.savefig(fn, dpi=300)
    plt.close()

    # Combined Reference
    plt.figure(figsize=(8,5))
    plt.plot(sweep_freqs/1e9, mean_refs, linestyle='-')
    plt.xlabel("Frequency (GHz)")
    plt.ylabel("Avg Reference PL")
    plt.title("Combined Avg Reference PL Across All X")
    plt.grid(True)
    fn = os.path.join(measurement_folder, f"Combined_Ref_{timestamp}.png")
    plt.savefig(fn, dpi=300)
    plt.close()

    # Combined Normalized
    plt.figure(figsize=(8,5))
    plt.plot(sweep_freqs/1e9, mean_norm, linestyle='-')
    plt.xlabel("Frequency (GHz)")
    plt.ylabel("Avg Normalized PL")
    plt.title("Combined Avg Normalized PL Across All X")
    plt.grid(True)
    plt.savefig(os.path.join(measurement_folder, f"Combined_Norm_{timestamp}.png"), dpi=300)
    plt.show()

    # === Save CSV data ===
    csvfile = os.path.join(measurement_folder, f"ESR_Data_{timestamp}.csv")
    with open(csvfile, 'w', newline='') as cf:
        writer = csv.writer(cf)
        writer.writerow(["X Position (m)", "Frequency (GHz)",
                         "Avg Ref PL", "Avg Raw PL", "Avg Normalized PL"])
        for xi, x_pos in enumerate(x_positions):
            avg   = all_data[xi].mean(axis=0)
            refs  = avg[0::2]
            raws  = avg[1::2]
            norms = raws/refs
            for f, r, s, n in zip(sweep_freqs/1e9, refs, raws, norms):
                writer.writerow([f"{x_pos:.6e}", f, r, s, n])

    # === Save binary data as compressed NumPy archive ===
    np.savez(
        os.path.join(measurement_folder, f"ESR_data_{timestamp}.npz"),
        x_positions    = x_positions,
        sweep_freqs    = sweep_freqs,
        reference_freq = ref_freq,
        pl_counts      = all_data
    )

    print(f"\nDone! Sub‑folders contain the per‑point plots, combined images and data saved in:\n"
          f"  {measurement_folder}\n"
          f"  CSV → {csvfile}\n"
          f"  NumPy archive → {measurement_folder}/ESR_data_{timestamp}.npz")

finally:
    sma100b.close()
    context.stop()
    print("Measurement complete, connections closed.")
