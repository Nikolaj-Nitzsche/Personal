import os
import numpy as np
import time
import json
import sys
from datetime import datetime
import TimeTagger
import subprocess
from pylablib.devices import Attocube
import matplotlib.pyplot as plt
from tqdm import tqdm

def main():
    # Define settings
    settings = {
        "save_folder": "/home/dl-lab-pc3/Documents/Nikolaj_Nitzsche/Cryo/2D_mapping/",  # Updated folder
        "x_steps": 70,                   # Total execution time: 10 h (30,50x50)
        "x1": 1280e-6,  # Start position
        "x2": 1350e-6,  # End position
        "y_points": 60,  # Number of points in y-axis
        "z_points": 60,  # Number of points in z-axis
        "y_range": [2652e-6, 2682e-6],  # Y position range
        "z_range": [1544e-6, 1574e-6],  # Z position range
        "ay": 0, #-0.031831, #-0.0067,  # Tilt adjustment factor for y
        "az": 0, #0.067340, #0.03625,#021645,  # Tilt adjustment factor for z
        "dwell_time": 2e11,  # picoseconds
        "measurement_type": "PL",
        "y_fix_steps": "50",
        "note": "test to check the reset doesnt change the position."
    }

    timestamp_folder = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_save_folder = os.path.join(settings["save_folder"], timestamp_folder)
    os.makedirs(new_save_folder, exist_ok=True)
    settings["save_folder"] = new_save_folder

    start_time = time.time()

    y_positions = np.linspace(settings["y_range"][0], settings["y_range"][1], settings["y_points"])
    z_positions = np.linspace(settings["z_range"][0], settings["z_range"][1], settings["z_points"])
    
    # Create the progress bar
    total_scans = len(y_positions) * len(z_positions)  # Total number of y,z points
    progress_bar = tqdm(total=total_scans, desc="2D Scan Progress", unit="scan", dynamic_ncols=True)

    # Create TimeTagger for measurement
    tagger = TimeTagger.createTimeTaggerNetwork('localhost:41101')
    countrate = TimeTagger.Countrate(tagger=tagger, channels=[5])
    
    atc = Attocube.ANC350()
    atc.set_frequency(0, 800)
    atc.set_frequency(1, 800)
    atc.set_frequency(2, 800)
    atc.set_voltage(0, 50)
    atc.set_voltage(1, 50)
    atc.set_voltage(2, 50)
    
    y_step_count = 0
    
    try:
        for y in y_positions:
            for z in z_positions:
                timestamp_string = str(round(datetime.now().timestamp()))
                savePath = os.path.join(settings['save_folder'], f"X_PL_scan_y{y:.6f}_z{z:.6f}_{timestamp_string}")
                print(f"Starting scan at y={y:.6f} m, z={z:.6f} m")
                run_scan(y, z, settings, countrate, atc, savePath)
                progress_bar.update(1)  # Update the progress bar by one step
                
            y_step_count += 1

            if y_step_count >= int(settings["y_fix_steps"]):
                print(f"Pausing after {y_step_count} y-steps. Running subprocess and waiting for a few seconds.")
                
                # Stop and fully close Attocube
                atc.stop()
                atc.close()

                # Ensure device resources are freed
                time.sleep(5)  # Short delay before running subprocess

                try:
                    # Run the subprocess with the correct Python executable
                    process = subprocess.Popen(
                        [sys.executable, "/home/dl-lab-pc3/Dylan/lasd/pyanc350/example_new.py"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )

                    # Print output and errors in real-time
                    for line in iter(process.stdout.readline, ''):
                        print("[Subprocess STDOUT]:", line.strip())

                    for line in iter(process.stderr.readline, ''):
                        print("[Subprocess STDERR]:", line.strip())

                    process.wait()
                    print(f"Subprocess finished with exit code {process.returncode}")

                    if process.returncode == -11:
                        print("⚠️ Subprocess crashed with segmentation fault (-11). Delaying fix code to avoid conflicts.")
                        time.sleep(10)  # Extra delay before reconnecting

                except Exception as e:
                    print(f"Unexpected error while running subprocess: {e}")

                # Ensure Attocube is fully powered down before reconnecting
                time.sleep(5)

                # Reconnect Attocube AFTER the subprocess
                print("Reconnecting Attocube...")
                atc = Attocube.ANC350()
                atc.set_frequency(0, 800)
                atc.set_frequency(1, 800)
                atc.set_frequency(2, 800)
                atc.set_voltage(0, 50)
                atc.set_voltage(1, 50)
                atc.set_voltage(2, 50)

                print("Resuming scan...")
                y_step_count = 0

    finally:
        del tagger
        atc.stop()
        atc.close()
        progress_bar.close()
        print("atc closed down. RTB for reload.")

    process_2d_scan(settings["save_folder"])
    end_time = time.time()
    print(f"Total execution time: {end_time - start_time:.2f} seconds")

def run_scan(y, z, settings, countrate, atc, savePath):
    settings["y0"] = y
    settings["z0"] = z
    settings["savePath"] = savePath
    settings["Start time"] = str(datetime.now())

    xmove = np.linspace(settings["x1"], settings["x2"], settings["x_steps"])
    PL = np.zeros(settings["x_steps"])
    print(f"X-axis scan complete at y={y:.8f} m, z={z:.8f} m")  # Confirmation after scan
    try:
        for ix, x_base in enumerate(xmove):
            diff_z_set = settings["az"] * (z - settings["z_range"][0])
            diff_y_set = settings["ay"] * (y - settings["y_range"][0])
            x_adjusted = x_base + diff_z_set + diff_y_set
            
            atc.move_to(0, x_adjusted)
            atc.move_to(1, settings["y0"])
            atc.move_to(2, settings["z0"])
            atc.wait_move(0)
            atc.wait_move(1)
            atc.wait_move(2)
            
            countrate.startFor(settings["dwell_time"])
            countrate.waitUntilFinished()
            rate = countrate.getData()[0]
            PL[ix] = rate
            print(f"Moved to: x={x_adjusted:.6f} m, PL count: {rate:.2f}")

        print("X-axis scan complete!")
        
        max_PL_value = np.max(PL)
        max_PL_index = np.argmax(PL)
        max_PL_xpos = xmove[max_PL_index]
        
        settings["max_PL_value"] = float(max_PL_value)
        settings["max_PL_xpos"] = float(max_PL_xpos)
    
    except Exception as e:
        print(f"Error during scan: {e}")
    finally:
        np.save(savePath + ".npy", PL)
        with open(savePath + ".json", 'w') as f:
            json.dump(settings, f, indent=4)
        print(f"Scan complete! File saved as: {savePath}.npy and {savePath}.json")

def process_2d_scan(folder_path):
    subprocess.run(["python", "PL_x_process.py", folder_path], check=True)
    print("2D scan processing complete.")

if __name__ == "__main__":
    main()
