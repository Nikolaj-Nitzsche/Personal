import argparse
from pylablib.devices import Attocube
import numpy as np
import time
import json
from datetime import datetime
import TimeTagger
import subprocess  # For running the processing script
from tqdm import tqdm

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("-z_shape", action="store_true", help="Use Z-shaped scan pattern instead of snake scan")
    args = parser.parse_args()  # Correct way to parse arguments

    # Define settings
    settings = {
        "save_folder": "/home/dl-lab-pc3/Documents/Nikolaj_Nitzsche/Cryo/2D-Scans/Broken_bulk_sample/",
        "y_steps": 50,  
        "z_steps": 50,
        "z1": 60e-6,  
        "z2": 1100e-6,  
        "y1": 1500e-6,  
        "y2": 2500e-6,  
        "x1": 4795.51e-6, # Value used from x_scan
        "x0": 4000e-6, #x2
        "y0": 1450e-6,
        "z0": 200e-6,
        "az": 0,  
        "ay": 0,  
        "dwell_time": 2e11,  
        "measurement_type": "PL",
    }

    # Create save path
    current_time = datetime.now()
    start_time = time.time()
    timestamp_string = str(round(current_time.timestamp()))
    save_folder = settings["save_folder"]
    savePath = f"{save_folder}2D_PL_scan_{timestamp_string}"
    settings["savePath"] = savePath
    settings["Start time"] = str(current_time)

    # Prepare motion parameters
    ymove = np.linspace(settings["y1"], settings["y2"], settings["y_steps"])
    zmove = np.linspace(settings["z1"], settings["z2"], settings["z_steps"])

    # Initialize data storage
    PL = np.zeros((settings["y_steps"], settings["z_steps"]))

    # Create TimeTagger for measurement
    tagger = TimeTagger.createTimeTaggerNetwork('localhost:41101')
    #tagger = TimeTagger.createTimeTaggerNetwork('ip:port')
    countrate = TimeTagger.Countrate(tagger=tagger, channels=[5])

    try:
        # Initialize Attocube ANC350
        atc = Attocube.ANC350()
        atc.set_frequency(0, 800)
        atc.set_frequency(1, 800)
        atc.set_frequency(2, 800)
        atc.set_voltage(0, 30)
        atc.set_voltage(1, 40)
        atc.set_voltage(2, 50)

        print("Piezo initialized with frequency:", atc.get_frequency())
        a_z = (settings["x1"] - settings["x0"]) / (settings["z2"] - settings["z1"])
        a_y = (settings["x1"] - settings["x0"]) / (settings["y2"] - settings["y1"])
        print(f"az is equal to: {a_z}, ay is equal to {a_y}")
        
        
        # Check which scan pattern to use
        if args.z_shape:
            print("Running in Z-shape scanning mode")
            with tqdm(total=settings["z_steps"], desc="Scanning Progress") as pbar:
                for iz in range(settings["z_steps"]):
                    for iy in range(settings["y_steps"]):
                        diff_z_set = settings["az"] * (zmove[iz] - settings["z1"])
                        diff_y_set = settings["ay"] * (ymove[iy] - settings["y1"])
                        x_move = settings["x1"] + diff_z_set + diff_y_set

                        atc.move_to(0, x_move)
                        atc.move_to(1, ymove[iy])
                        atc.move_to(2, zmove[iz])
                        
                        atc.wait_move(0)
                        atc.wait_move(1)
                        atc.wait_move(2)
                        
                        time.sleep(0.1)  # Small delay for stability  

                        countrate.startFor(settings["dwell_time"])
                        countrate.waitUntilFinished()
                        rate = countrate.getData()[0]
                        PL[iy][iz] = rate

                        print(f"Moved to: x={x_move:.6f} m, y={ymove[iy]:.6f} m, z={zmove[iz]:.6f} m")
                        print(f"Photoluminescence count: {rate:.2f}")

                    if iz < settings["z_steps"] - 1:
                        atc.move_to(1, settings["y1"])
                        atc.wait_move(1)

                    pbar.update(1)  # Update progress bar

        else:
            print("Running in snake scanning mode")
            with tqdm(total=settings["z_steps"], desc="Scanning Progress") as pbar:
                for iz in range(settings["z_steps"]):
                    for iy_loop in range(settings["y_steps"]):
                        iy = iy_loop if iz % 2 == 0 else settings["y_steps"] - iy_loop - 1
                        diff_z_set = settings["az"] * (zmove[iz] - settings["z1"])
                        diff_y_set = settings["ay"] * (ymove[iy] - settings["y1"])
                        x_move = settings["x1"] + diff_z_set + diff_y_set

                        atc.move_to(0, x_move)
                        atc.move_to(1, ymove[iy])
                        atc.move_to(2, zmove[iz])

                        atc.wait_move(0)
                        atc.wait_move(1)
                        atc.wait_move(2)

                        countrate.startFor(settings["dwell_time"])
                        countrate.waitUntilFinished()
                        rate = countrate.getData()[0]
                        PL[iy][iz] = rate

                        print(f"Moved to: x={x_move:.6f} m, y={ymove[iy]:.6f} m, z={zmove[iz]:.6f} m")
                        print(f"Photoluminescence count: {rate:.2f}")

                    pbar.update(1)  # Update progress bar


                print("Measurement complete!")
                
        # End timing and calculate elapsed time
        end_time = time.time()
        elapsed_time = end_time - start_time
        formatted_time = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))

        print(f"---------------------------- Total measurement time: {formatted_time} ----------------------------")

    except Exception as e:
        print(f"Error during test: {e}")
    finally:
        np.save(savePath + ".npy", PL)
        with open(savePath + ".json", 'w') as f:
            json.dump(settings, f, indent=4)

        print(f"Measurement complete! File saved as: {savePath}.npy")
        if 'atc' in locals():
            atc.stop()
            atc.close()
            print("atc closed down. RTB for reload.")
        del tagger

    # AUTOMATICALLY RUN PROCESSING SCRIPT
    try:
        process_script = "PL_2D_process.py"
        subprocess.run(["python", process_script, savePath + ".npy"], check=True)
        print("Processing script executed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error running processing script: {e}")

if __name__ == "__main__":
    main()
