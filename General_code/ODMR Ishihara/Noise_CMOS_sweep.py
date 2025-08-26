#!/usr/bin/env python3
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

# Instrument parameters
instrument_name = "SMA100B"
instrument_ip   = "169.254.91.32"
transport       = f"tcp:{instrument_ip}:5025"

# ESR Sweep Parameters
start_freq = 2.85e9
end_freq   = 2.89e9
step_size  = 1e5    # 0.1 MHz steps
ref_freq   = 2.85e9
sweep_freqs = np.arange(start_freq + step_size, end_freq + step_size, step_size)
interleaved_freqs = np.empty(len(sweep_freqs) * 2)
interleaved_freqs[0::2] = ref_freq
interleaved_freqs[1::2] = sweep_freqs

rf_power    = 15
num_sweeps  = 300     # ~1 hour if 10
dwell_time  = 2e11  # picoseconds

# Folder structure
base_save_folder = "/home/dl-lab-pc3/Documents/Nikolaj_Nitzsche/Cryo/NbTiN_sample/ESR_sweep/"
os.makedirs(base_save_folder, exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
measurement_folder = os.path.join(base_save_folder, f"ESR_Sweep_{timestamp}")
os.makedirs(measurement_folder, exist_ok=True)
individual_data_folder = os.path.join(measurement_folder, "individual_sweeps")
os.makedirs(individual_data_folder, exist_ok=True)

# TimeTagger setup
tagger    = TimeTagger.createTimeTaggerNetwork('localhost:41101')
countrate = TimeTagger.Countrate(tagger=tagger, channels=[5])

# Metadata
metadata = {
    "start_freq": start_freq,
    "end_freq": end_freq,
    "step_size": step_size,
    "num_sweeps": num_sweeps,
    "rf_power": rf_power,
    "reference_frequency": ref_freq,
    "dwell_time": dwell_time,
    "timestamp": timestamp,
    "notes": "Normalized ESR sweep alternating with reference."
}
with open(os.path.join(measurement_folder, f"ESR_Sweep_{timestamp}.json"), 'w') as json_file:
    json.dump(metadata, json_file, indent=4)

# QMI / SMA100B setup
context = QMI_Context("rs_signal_gen_context")
context.start()
sma100b = RohdeSchwarz_Base(context, instrument_name, transport)
sma100b.open()

try:
    PL_counts = np.zeros((num_sweeps, len(interleaved_freqs)))
    start_time = time.time()
    progress_bar = tqdm(total=num_sweeps, desc="Sweep Progress", unit="sweep")

    for sweep in range(num_sweeps):
        progress_bar.update(1)
        print(f"\nSweep {sweep + 1}/{num_sweeps}")

        # Turn RF on once per sweep and let it settle
        sma100b.set_power(rf_power)
        sma100b.set_output_state(True)
        time.sleep(0.02)

        sweep_data = []

        for i, freq in enumerate(interleaved_freqs):
            print(f"Setting frequency to {freq / 1e9:.4f} GHz")
            sma100b.set_frequency(freq)
            time.sleep(0.01)  # let frequency lock

            # Now do the full dwell at settled power & frequency
            countrate.startFor(dwell_time)
            countrate.waitUntilFinished()
            PL = countrate.getData()[0]
            PL_counts[sweep, i] = PL

            print(f"PL Count at {freq / 1e9:.4f} GHz: {PL:.2f} Hz")
            sweep_data.append((freq / 1e9, PL))

        # Turn RF off between sweeps
        sma100b.set_output_state(False)

        # Save individual sweep data to CSV
        sweep_filename = os.path.join(individual_data_folder, f"Sweep_{sweep + 1}.csv")
        with open(sweep_filename, 'w', newline='') as sweep_file:
            writer = csv.writer(sweep_file)
            writer.writerow(["Frequency (GHz)", "PL Count"])
            writer.writerows(sweep_data)

    progress_bar.close()

    # Process averages & normalization
    avg_PL = np.mean(PL_counts, axis=0)
    ref_vals   = avg_PL[0::2]   # Reference
    sweep_vals = avg_PL[1::2]   # Swept freqs
    norm_PL    = sweep_vals / ref_vals

    # Save normalized CSV
    csv_filename = os.path.join(measurement_folder, f"Normalized_ESR_Sweep_{timestamp}.csv")
    with open(csv_filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Frequency (GHz)", "Raw PL", "Reference PL", "Normalized PL"])
        for fghz, raw, ref, n in zip(sweep_freqs/1e9, sweep_vals, ref_vals, norm_PL):
            writer.writerow([fghz, raw, ref, n])

    # Plot 1: Raw sweep vs frequency
    plt.figure()
    plt.plot(sweep_freqs / 1e9, sweep_vals, label='Raw Sweep PL')
    plt.xlabel("Frequency (GHz)")
    plt.ylabel("PL Counts")
    plt.title("Raw PL Sweep")
    plt.grid(True)
    plt.savefig(os.path.join(measurement_folder, f"Raw_Sweep_{timestamp}.png"))
    plt.show()

    # Plot 2: Reference PL vs frequency
    plt.figure()
    plt.plot(sweep_freqs / 1e9, ref_vals, label='Reference PL')
    plt.xlabel("Frequency (GHz)")
    plt.ylabel("Reference PL")
    plt.title("Reference PL")
    plt.grid(True)
    plt.savefig(os.path.join(measurement_folder, f"Reference_PL_{timestamp}.png"))
    plt.show()

    # Plot 3: Normalized PL
    plt.figure()
    plt.plot(sweep_freqs / 1e9, norm_PL, label='Normalized PL')
    plt.xlabel("Frequency (GHz)")
    plt.ylabel("Normalized PL")
    plt.title("Normalized PL (Sweep / Reference)")
    plt.grid(True)
    plt.savefig(os.path.join(measurement_folder, f"Normalized_PL_{timestamp}.png"))
    plt.show()

    # Plot 4: Overlay of all raw sweeps
    plt.figure(figsize=(10, 6))
    for sweep_idx in range(num_sweeps):
        sweep_data = PL_counts[sweep_idx, 1::2]  # only sweep (not reference)
        plt.plot(sweep_freqs / 1e9, sweep_data, alpha=0.5, label=f"Sweep {sweep_idx + 1}")
    plt.xlabel("Frequency (GHz)")
    plt.ylabel("PL Count")
    plt.title("Overlay of Raw Sweep Measurements")
    plt.legend(fontsize='small', loc='upper right', ncol=2)
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(measurement_folder, f"Overlay_Raw_Sweeps_{timestamp}.png"))
    plt.show()

    print(f"\nMeasurement Complete! Total Time: {time.time() - start_time:.2f} s")

finally:
    del tagger
    sma100b.close()
    context.stop()
    print("\nESR Sweep Complete. Connection Closed.")
