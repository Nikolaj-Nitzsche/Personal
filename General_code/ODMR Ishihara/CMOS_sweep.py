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

# Define instrument parameters
instrument_name = "SMA100B"
instrument_ip = "169.254.91.32"
transport = f"tcp:{instrument_ip}:5025"  # Use TCP/IP SCPI over Ethernet

# Define ESR Sweep Parameters
start_freq = 2.85e9   # 5.7 GHz
end_freq = 2.89e9     # 5.78 GHz
step_size = 1e5       # 0.1 MHz steps
frequencies = np.arange(start_freq, end_freq + step_size, step_size)
rf_power = 15         # in dBm

# Number of times to repeat the sweep
num_sweeps = 10  # Change this to increase the number of sweeps

# Define base save folder
base_save_folder = "/home/dl-lab-pc3/Documents/Nikolaj_Nitzsche/Cryo/CMOS_ESR/"

# Ensure the base save folder exists
os.makedirs(base_save_folder, exist_ok=True)

# Generate a timestamped folder for this measurement
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
measurement_folder = os.path.join(base_save_folder, f"ESR_Sweep_{timestamp}")
os.makedirs(measurement_folder, exist_ok=True)

# Define metadata dictionary
metadata = {
    "start_freq": start_freq,
    "end_freq": end_freq,
    "step_size": step_size,
    "num_sweeps": num_sweeps,
    "rf_power": rf_power,
    "timestamp": timestamp,
    "notes": "Enter your measurement notes here."
}

# Save metadata as JSON
json_filename = os.path.join(measurement_folder, f"ESR_Sweep_{timestamp}.json")
with open(json_filename, 'w') as json_file:
    json.dump(metadata, json_file, indent=4)

print(f"\nMetadata saved to JSON: {json_filename}")

# Initialize QMI framework
context = QMI_Context("rs_signal_gen_context")
context.start()

# Create an instance of the SMA100B driver
sma100b = RohdeSchwarz_Base(context, instrument_name, transport)

try:
    # Open connection to the signal generator
    sma100b.open()
    
    # Create TimeTagger for measurement
    tagger = TimeTagger.createTimeTaggerNetwork('localhost:41101')
    countrate = TimeTagger.Countrate(tagger=tagger, channels=[5])

    # Initialize storage for PL data across sweeps
    PL_counts = np.zeros((num_sweeps, len(frequencies)))

    # Start timer
    start_time = time.time()

    print("\nStarting Multiple ESR Frequency Sweeps...")

    # Create a single progress bar for sweeps
    progress_bar = tqdm(total=num_sweeps, desc="Sweep Progress", unit="sweep", dynamic_ncols=True)

    for sweep in range(num_sweeps):
        # Update progress bar only once per sweep
        progress_bar.update(1)
        print(f"\nStarting Sweep {sweep + 1}/{num_sweeps}...")

        for i, freq in enumerate(frequencies):
            step_start_time = time.time()  # Track time per step

            print(f"Setting frequency to {freq / 1e9:.4f} GHz")

            # Set the frequency on the signal generator
            sma100b.set_frequency(freq)
            sma100b.set_power(metadata["rf_power"])

            # Enable RF output
            sma100b.set_output_state(True)

            # Wait a short time to stabilize
            #time.sleep(0.5)

            # Measure PL signal
            countrate.startFor(2e11)  # 2-second dwell time
            countrate.waitUntilFinished()
            PL_intensity = countrate.getData()[0]  # Get the PL counts

            # Store PL intensity for this sweep
            PL_counts[sweep, i] = PL_intensity

            # Calculate elapsed time and estimate remaining time
            elapsed_time = time.time() - start_time
            remaining_sweeps = num_sweeps - (sweep + 1)
            avg_sweep_time = elapsed_time / (sweep + 1)
            estimated_remaining_time = avg_sweep_time * remaining_sweeps

            print(f"Sweep {sweep + 1}: Measured PL Count: {PL_intensity}") #| Step Time: {time.time() - step_start_time:.2f}s")
           #print(f"Elapsed Time: {elapsed_time:.2f}s | Estimated Time Remaining: {estimated_remaining_time:.2f}s")

        # Turn off RF output after each sweep
        sma100b.set_output_state(False)

    # Close progress bar after all sweeps
    progress_bar.close()

    # Compute the average PL values across all sweeps
    avg_PL_counts = np.mean(PL_counts, axis=0)

    # Normalize PL Data
    normalized_PL = avg_PL_counts / np.max(avg_PL_counts)  # Normalize to max value

    # Save data to CSV
    csv_filename = os.path.join(measurement_folder, f"ESR_Sweep_{timestamp}.csv")
    with open(csv_filename, mode='w', newline='') as csv_file:
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(["Frequency (GHz)", "Average PL Count", "Normalized PL"])
        for i in range(len(frequencies)):
            csv_writer.writerow([frequencies[i] / 1e9, avg_PL_counts[i], normalized_PL[i]])
    
    print(f"\nData saved to CSV: {csv_filename}")

    # Generate the plot
    plt.figure(figsize=(8, 5))
    plt.plot(frequencies / 1e9, normalized_PL, marker='o', linestyle='-', label=f"Averaged over {num_sweeps} sweeps")
    plt.xlabel("Frequency (GHz)")
    plt.ylabel("Normalized PL Intensity")
    plt.title("Averaged ESR Frequency Sweep")
    plt.legend()
    plt.grid(True)

    # Save the plot
    plot_filename = os.path.join(measurement_folder, f"ESR_Sweep_{timestamp}.png")
    plt.savefig(plot_filename, dpi=300)
    
    print(f"\nPlot saved to: {plot_filename}")

    # Show the plot
    plt.show()
    
        # Plot PL counts vs frequency
    plt.figure(figsize=(8, 5))
    plt.plot(frequencies / 1e9, avg_PL_counts, marker='s', linestyle='-', label='Raw PL Counts')
    plt.xlabel("Frequency (GHz)")
    plt.ylabel("PL Count Rate")
    plt.title("Raw PL Counts vs Frequency")
    plt.legend()
    plt.grid(True)

    # Save raw PL count plot
    raw_plot_filename = os.path.join(measurement_folder, f"ESR_Sweep_RawCounts_{timestamp}.png")
    plt.savefig(raw_plot_filename, dpi=300)
    
    print(f"\nRaw PL plot saved to: {raw_plot_filename}")

    # Show the raw PL plot
    plt.show()
    
    plt.figure(figsize=(10, 6))
    for sweep_idx in range(num_sweeps):
        plt.plot(frequencies / 1e9, PL_counts[sweep_idx], alpha=0.4, label=f"Sweep {sweep_idx+1}")

    plt.xlabel("Frequency (GHz)")
    plt.ylabel("PL Counts")
    plt.title("Individual ESR Sweeps")
    plt.grid(True)
    plt.legend(fontsize='small', loc='upper right', ncol=2)
    plt.tight_layout()

    # Optionally save
    multi_sweep_plot = os.path.join(measurement_folder, f"ESR_Sweep_IndividualSweeps_{timestamp}.png")
    plt.savefig(multi_sweep_plot, dpi=300)
    plt.show()

    # Final execution time
    total_time = time.time() - start_time
    print(f"\nMeasurement Complete! Total Execution Time: {total_time:.2f} seconds")

finally:
    # Close connection and stop QMI context
    del tagger
    sma100b.close()
    context.stop()
    print("\nESR Sweep Complete. Connection Closed.")
