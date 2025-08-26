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

# Define instrument parameters
instrument_name = "SMA100B"
instrument_ip = "169.254.91.32"
transport = f"tcp:{instrument_ip}:5025"  # Use TCP/IP SCPI over Ethernet

# Define ESR Sweep Parameters
start_freq = 2.85e9   # 5.7 GHz
end_freq = 2.89e9     # 5.78 GHz
step_size = 1e5       # 1 MHz steps
frequencies = np.arange(start_freq, end_freq + step_size, step_size)
rf_power = 15         # in dBm

# Number of times to repeat the sweep
num_sweeps = 3  # Change this to increase the number of sweeps

# Piezo X-range for movement (example)
x_positions = np.linspace(3100e-6, 3400e-6, 20)  # Example: Move from 4490e-6 to 4520e-6 in 5 steps

# Define base save folder
base_save_folder = "/home/dl-lab-pc3/Documents/Nikolaj_Nitzsche/Cryo/CMOS_ESR/"

# Ensure the base save folder exists
os.makedirs(base_save_folder, exist_ok=True)

# Generate a timestamped folder for this measurement
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
start_time = time.time()
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

# Initialize storage for PL data across sweeps
PL_counts_all_positions = []  # Store PL counts for all positions

try:
    # Open connection to the signal generator
    sma100b.open()
    
    # Create TimeTagger for measurement
    tagger = TimeTagger.createTimeTaggerNetwork('localhost:41101')
    countrate = TimeTagger.Countrate(tagger=tagger, channels=[5])

    print("\nStarting Multiple ESR Frequency Sweeps at Different X-Positions...")

    # Create a progress bar for the entire process
    total_steps = num_sweeps * len(frequencies) * len(x_positions)
    progress_bar = tqdm(total=total_steps, desc="Sweep Progress", unit="step", dynamic_ncols=True)

    atc = Attocube.ANC350()
    atc.set_frequency(0, 800)
    atc.set_frequency(1, 800)
    atc.set_frequency(2, 800)
    atc.set_voltage(0, 50)
    atc.set_voltage(1, 50)
    atc.set_voltage(2, 50)
    
    for x_idx, x_pos in enumerate(x_positions):
        print(f"\nMoving to X position: {x_pos:.6f} m")

        # Move piezo to the new X position
        atc.move_to(0, x_pos)
        atc.wait_move(0)

        # Initialize storage for PL counts at this position
        PL_counts_position = np.zeros((num_sweeps, len(frequencies)))

        print(f"Starting Sweep at X = {x_pos:.6f} m...")
        time.sleep(1)
        progress_bar.update(1)
        for sweep in range(num_sweeps):
            for i, freq in enumerate(frequencies):
                # Update progress bar after each frequency sweep

                # Set the frequency on the signal generator
                sma100b.set_frequency(freq)
                sma100b.set_power(15)
                # Enable RF output
                sma100b.set_output_state(True)

                # Measure PL signal
                countrate.startFor(2e11)  # 2-second dwell time
                countrate.waitUntilFinished()
                PL_intensity = countrate.getData()[0]  # Get the PL counts

                # Store PL intensity for this sweep and x-position
                PL_counts_position[sweep, i] = PL_intensity

                print(f"Sweep {sweep + 1}/{num_sweeps}: Measured PL Count: {PL_intensity} at {freq/1e9:.4f} GHz")

            # Turn off RF output after each sweep
            sma100b.set_output_state(False)

        # Update progress bar after finishing one X position
        progress_bar.set_postfix({"X position": f"{x_pos:.6f} m"})
        print(f"Completed X position: {x_pos:.6f} m")

        # Store the PL counts for this position
        PL_counts_all_positions.append((x_pos, PL_counts_position))

        # Plot for the current position
        avg_PL_counts_position = np.mean(PL_counts_position, axis=0)
        normalized_PL_position = avg_PL_counts_position / np.max(avg_PL_counts_position)

        plt.figure(figsize=(8, 5))
        plt.plot(frequencies / 1e9, normalized_PL_position, marker='o', linestyle='-', label=f"X = {x_pos:.6f} m")
        plt.xlabel("Frequency (GHz)")
        plt.ylabel("Normalized PL Intensity")
        plt.title(f"ESR Frequency Sweep at X = {x_pos:.6f} m")
        plt.legend()
        plt.grid(True)

        # Save the plot for this position
        plot_filename = os.path.join(measurement_folder, f"ESR_Sweep_{timestamp}_X_{x_pos:.6f}.png")
        plt.savefig(plot_filename, dpi=300)

        print(f"Plot for X = {x_pos:.6f} m saved to: {plot_filename}")

    # Final combined plot
    plt.figure(figsize=(8, 5))

    for x_pos, PL_counts_position in PL_counts_all_positions:
        avg_PL_counts_position = np.mean(PL_counts_position, axis=0)
        normalized_PL_position = avg_PL_counts_position / np.max(avg_PL_counts_position)
        plt.plot(frequencies / 1e9, normalized_PL_position, marker='o', linestyle='-', label=f"X = {x_pos:.6f} m")

    plt.xlabel("Frequency (GHz)")
    plt.ylabel("Normalized PL Intensity")
    plt.title(f"Combined ESR Frequency Sweep at All X Positions")
    plt.legend()
    plt.grid(True)

    # Save the final combined plot
    final_plot_filename = os.path.join(measurement_folder, f"ESR_Sweep_{timestamp}_Combined.png")
    plt.savefig(final_plot_filename, dpi=300)
    plt.show()

    print(f"\nCombined Plot saved to: {final_plot_filename}")

    # Save data to CSV
    csv_filename = os.path.join(measurement_folder, f"ESR_Sweep_{timestamp}.csv")
    with open(csv_filename, mode='w', newline='') as csv_file:
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(["Frequency (GHz)", "Average PL Count", "Normalized PL"])
        for i in range(len(frequencies)):
            # Averaging across all X positions
            avg_PL_counts_all_positions = np.mean([np.mean(PL_counts_position[:, i]) for _, PL_counts_position in PL_counts_all_positions])
            normalized_PL_all_positions = avg_PL_counts_all_positions / np.max(avg_PL_counts_all_positions)
            csv_writer.writerow([frequencies[i] / 1e9, avg_PL_counts_all_positions, normalized_PL_all_positions])

    print(f"\nData saved to CSV: {csv_filename}")

    # Final execution time
    total_time = time.time() - start_time
    print(f"\nMeasurement Complete! Total Execution Time: {total_time:.2f} seconds")

finally:
    # Close connection and stop QMI context
    sma100b.close()
    context.stop()
    print("\nESR Sweep Complete. Connection Closed.")
