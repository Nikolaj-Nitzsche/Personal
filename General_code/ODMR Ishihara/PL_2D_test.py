import argparse
import os
import sys
import time
import json
import numpy as np
import subprocess
import TimeTagger
import matplotlib.pyplot as plt
from datetime import datetime
from tqdm import tqdm
from pylablib.devices import Attocube
from qmi.core.context import QMI_Context
from rtcs.devices.rohde_schwarz.rs_base_signal_gen import RohdeSchwarz_Base

# RF Instrument Connection Details
instrument_name = "SMA100B"
instrument_ip   = "169.254.91.32"
transport       = f"tcp:{instrument_ip}:5025"

# Path to the external fix script
FIX_SCRIPT  = "/home/dl-lab-pc3/Dylan/lasd/pyanc350/example_new.py"

def recover_piezo(atc, settings):
    """Attempts to recover from a piezo glitch by moving to the center position."""
    print("Piezo glitch detected! Recovering to center...")
    center_y = (settings["y1"] + settings["y2"]) / 2
    atc.move_to(1, center_y)
    atc.wait_move(1)
    print(f"Recovered to y = {center_y:.6f} m")
    time.sleep(2)

def check_y(atc, tagger, settings):
    """Single-line y scan and plot."""
    ymove = np.linspace(settings["y1"], settings["y2"], settings["y_steps"])
    PL = np.zeros(settings["y_steps"])
    countrate = TimeTagger.Countrate(tagger=tagger, channels=[5])
    for iy, y in enumerate(ymove):
        atc.move_to(1, y); atc.wait_move(1)
        countrate.startFor(settings["dwell_time"])
        countrate.waitUntilFinished()
        PL[iy] = countrate.getData()[0]
        print(f"y={y:.6f} m → PL={PL[iy]:.2f}")
    plt.plot(ymove * 1e6, PL, marker='o')
    plt.xlabel("Y (μm)")
    plt.ylabel("PL count")
    plt.title("PL vs Y")
    plt.grid()
    plt.show()

def run_fix_subprocess():
    """Runs the external fix script, streaming stdout/stderr."""
    print(f"Pausing scan: running fix script {FIX_SCRIPT}")
    try:
        proc = subprocess.Popen(
            [sys.executable, FIX_SCRIPT],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        for line in iter(proc.stdout.readline, ""):
            print("[fix STDOUT]", line.rstrip())
        for line in iter(proc.stderr.readline, ""):
            print("[fix STDERR]", line.rstrip())
        proc.wait()
        print(f"Fix script exited with code {proc.returncode}")
        if proc.returncode == -11:
            print("Segmentation fault detected; delaying before reconnect")
            time.sleep(10)
    except Exception as e:
        print("Error running fix subprocess:", e)
    time.sleep(5)  # give time to free resources

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-z_shape", action="store_true", help="Use Z-snake scan")
    parser.add_argument("-check_y", action="store_true", help="Do single y check")
    rf_group = parser.add_mutually_exclusive_group()
    rf_group.add_argument("-rf_on",  action="store_true")
    rf_group.add_argument("-rf_off", action="store_true")
    args = parser.parse_args()

    # default to RF-off
    if not (args.rf_on or args.rf_off):
        args.rf_off = True
        print("No RF flag: default RF-off")

    settings = {
        "save_folder":      "/home/dl-lab-pc3/Documents/Nikolaj_Nitzsche/Cryo/2D-Scans/Single_NV_TNO/",
        "y_steps":          240,
        "z_steps":          240,
        "y1":             2622e-6,
        "y2":             2682e-6,
        "z1":             1514e-6,
        "z2":             1574e-6,
        "x1":             1450.13e-6,#1364.32e-6, #<-------------------------
        "x0":             4721e-6,
        "z0":              900e-6,
        "ay":                 0.0,
        "az":                 0.0,
        "dwell_time":     1e12,
        "measurement_type":"PL",
        "Note":            "RF-off",
        "rf_freq":       2.87e9,
        "rf_power":           15,
        "y_fix_steps":        50,
        "pause_time":        0,
    }

    # handle RF connection
    rf_device = None; context = None
    if args.rf_on or args.rf_off:
        try:
            context   = QMI_Context("rs_signal_gen_context")
            context.start()
            rf_device = RohdeSchwarz_Base(context, instrument_name, transport)
            rf_device.open()
            if args.rf_on:
                rf_device.set_frequency(settings["rf_freq"])
                rf_device.set_power(settings["rf_power"])
                rf_device.set_output_state(True)
                settings["Note"] = "RF-on"
                print("RF turned ON")
            else:
                rf_device.set_output_state(False)
                settings["Note"] = "RF-off"
                print("RF turned OFF")
        except Exception as e:
            print("RF init error:", e)

    # timestamped save path
    now = datetime.now()
    ts  = int(now.timestamp())
    save_folder = settings["save_folder"]
    os.makedirs(save_folder, exist_ok=True)
    savePath = os.path.join(save_folder, f"2D_PL_scan_{ts}")
    settings["savePath"]   = savePath
    settings["Start time"] = now.isoformat()

    # prepare scan
    ymove = np.linspace(settings["y1"], settings["y2"], settings["y_steps"])
    zmove = np.linspace(settings["z1"], settings["z2"], settings["z_steps"])
    PL = np.zeros((settings["y_steps"], settings["z_steps"]))

    tagger = TimeTagger.createTimeTaggerNetwork('localhost:41101')

    # single-line check and exit
    if args.check_y:
        atc = Attocube.ANC350()
        check_y(atc, tagger, settings)
        return

    # initialize Attocube
    atc = Attocube.ANC350()
    for axis in (0,1,2):
        atc.set_frequency(axis, 800)
        atc.set_voltage(axis,   40)
    print("Piezo initialized.")

    y_count = 0
    try:
        print("Starting 2D scan")
        with tqdm(total=settings["z_steps"], desc="Scanning Progress") as pbar:
            for iz, z in enumerate(zmove):
                for jy in range(settings["y_steps"]):
                    iy = jy if (args.z_shape or iz % 2 == 0) else settings["y_steps"]-1-jy
                    y = ymove[iy]
                    diff_z = settings["az"] * (z - settings["z1"])
                    diff_y = settings["ay"] * (y - settings["y1"])
                    x = settings["x1"] + diff_z + diff_y

                    atc.move_to(0, x)
                    atc.move_to(1, y)
                    atc.move_to(2, z)
                    atc.wait_move(0); atc.wait_move(1); atc.wait_move(2)

                    time.sleep(settings["pause_time"])
                    c = TimeTagger.Countrate(tagger=tagger, channels=[5])
                    c.startFor(settings["dwell_time"])
                    c.waitUntilFinished()
                    rate = c.getData()[0]
                    PL[iy, iz] = rate

                    print(f"Moved to: x={x:.6f} m, y={y:.6f} m, z={z:.6f} m")
                    print(f"Photoluminescence count: {rate:.2f}")

                # after each y-slice
                y_count += 1
                if y_count >= settings["y_fix_steps"]:
                    atc.stop(); atc.close()
                    time.sleep(5)
                    run_fix_subprocess()
                    atc = Attocube.ANC350()
                    for axis in (0,1,2):
                        atc.set_frequency(axis, 800)
                        atc.set_voltage(axis,   40)
                    print("Resuming scan")
                    y_count = 0

                pbar.update(1)

        print("2D scan complete!")

    except Exception as e:
        print("Error during scan:", e)

    finally:
        # save data
        np.save(savePath + ".npy", PL)
        with open(savePath + ".json", "w") as f:
            json.dump(settings, f, indent=2)
        print(f"Data saved to {savePath}.*")

        atc.stop(); atc.close()
        print("Piezo closed.")
        if rf_device:
            rf_device.set_output_state(False)
            rf_device.close()
        if context:
            context.stop()
        del tagger

        # run processing script
        try:
            subprocess.run(
                ["python", "PL_2D_process.py", savePath + ".npy"],
                check=True
            )
            print("Post-processing complete.")
        except Exception as e:
            print("Post-processing error:", e)

if __name__ == "__main__":
    main()
