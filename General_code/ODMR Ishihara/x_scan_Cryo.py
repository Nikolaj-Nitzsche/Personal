#!/usr/bin/env python3

import argparse
import os
import time
import numpy as np
import json
from datetime import datetime
import TimeTagger
import subprocess
import matplotlib.pyplot as plt
from pylablib.devices import Attocube

def main():
    parser = argparse.ArgumentParser(description="Perform X-axis PL scan with optional max move")
    parser.add_argument("-move_max", action="store_true", help="Move to the x position with max PL after scan")
    parser.add_argument("-only_move_x", action="store_true", help="Only move along the x-axis without adjusting y and z")
    parser.add_argument("-avg_num", type=int, default=1, help="Number of full sweeps to average")
    parser.add_argument("-osc_time", type=float, default=10.0,
                        help="Seconds to oscillate around the max PL position")
    args = parser.parse_args()

    # Settings
    settings = {
        "save_folder": "/home/dl-lab-pc3/Documents/Nikolaj_Nitzsche/Cryo/X-Scans/",
        "x_steps":    300,
        "x1":      1250e-6,
        "x2":      1550e-6,
        "y0":      2682e-6,
        "z0":      1574e-6,
        "dwell_time": 2e11,    # picoseconds
        "only_move_x": args.only_move_x,
        "avg_num":   args.avg_num
    }

    # Folders & save settings
    now = datetime.now()
    ts  = str(round(now.timestamp()))
    base = settings["save_folder"]
    savePath   = f"{base}X_PL_scan_y{settings['y0']}_z{settings['z0']}_{ts}"
    plot_folder= savePath + "_plots"
    os.makedirs(plot_folder, exist_ok=True)
    with open(os.path.join(plot_folder, "settings.json"), "w") as f:
        json.dump({**settings, "savePath": savePath, "timestamp": str(now)}, f, indent=4)

    print(f"Plots will be saved in: {plot_folder}")

    # Motion grid
    xmove = np.linspace(settings["x1"], settings["x2"], settings["x_steps"])

    # TimeTagger
    tagger    = TimeTagger.createTimeTaggerNetwork('localhost:41101')
    countrate = TimeTagger.Countrate(tagger=tagger, channels=[5])

    try:
        # Init piezo
        atc = Attocube.ANC350()
        for ax in (0,1,2):
            atc.set_frequency(ax, 800)
            atc.set_voltage(ax, 50)
        print("Piezo initialized:", atc.get_frequency())

        # Run scan
        averaged_PL, sweep_data = run_scan(settings, countrate, atc, xmove, plot_folder)

        # Optional move+oscillate
        if args.move_max:
            oscillate_around_peak(atc, xmove, averaged_PL, countrate,
                                  settings["dwell_time"],
                                  osc_time=args.osc_time)

    except Exception as e:
        print("Error during scan:", e)

    finally:
        # Save data & cleanup
        np.save(savePath + ".npy", averaged_PL)
        with open(savePath + ".json", "w") as f:
            json.dump(settings, f, indent=4)
        print("Scan complete! Data saved to:", savePath + ".npy")
        if 'atc' in locals():
            atc.stop(); atc.close()
        del tagger

    # Post‑process
    process_x_scan(savePath)


def run_scan(settings, countrate, atc, xmove, plot_folder):
    num_pts = len(xmove)
    sweeps  = settings["avg_num"]
    data    = np.zeros((sweeps, num_pts))

    for sw in range(sweeps):
        print(f"Starting sweep {sw+1}/{sweeps}")
        for ix, xpos in enumerate(xmove):
            atc.move_to(0, xpos)
            if not settings["only_move_x"]:
                atc.move_to(1, settings["y0"])
                atc.move_to(2, settings["z0"])
            atc.wait_move(0)
            if not settings["only_move_x"]:
                atc.wait_move(1); atc.wait_move(2)
            data[sw, ix] = measure_PL(countrate, settings["dwell_time"])
            print(f"  x={xpos:.6f} → {data[sw, ix]:.2f}")
        print()

    avg = np.mean(data, axis=0)

    # Plot averaged points
    plt.figure(figsize=(10,6))
    plt.plot(xmove, avg, 'o')
    plt.xlabel("X (m)"); plt.ylabel("PL count")
    plt.title("Averaged PL Scan"); plt.grid(True)
    plt.savefig(os.path.join(plot_folder, "avg_points.png"), dpi=300)
    plt.close()

    # Plot line
    plt.figure(figsize=(10,6))
    plt.plot(xmove, avg, '-')
    plt.xlabel("X (m)"); plt.ylabel("PL count")
    plt.title("Averaged PL Scan (Line)"); plt.grid(True)
    plt.savefig(os.path.join(plot_folder, "avg_line.png"), dpi=300)
    plt.close()

    print("Plots saved.")
    return avg, data


def measure_PL(countrate, dwell):
    countrate.startFor(dwell)
    countrate.waitUntilFinished()
    return countrate.getData()[0]


def oscillate_around_peak(atc, xmove, PL, countrate, dwell_time, osc_time=10.0):
    """
    Find the index of max(PL), move there, then oscillate
    between that point and its two neighbors for `osc_time` seconds.
    """
    idx_peak = np.argmax(PL)
    x_peak   = xmove[idx_peak]
    print(f"Peak at idx {idx_peak}, x={x_peak:.8f}")

    # Determine neighbors
    left  = xmove[idx_peak-1] if idx_peak>0 else x_peak
    right = xmove[idx_peak+1] if idx_peak< len(xmove)-1 else x_peak

    # Move to peak
    atc.move_to(0, x_peak); atc.wait_move(0)

    # Oscillation loop
    dwell_s   = dwell_time * 1e-12
    # approximate #loops: each loop has 4 moves
    loops = max(1, int(osc_time / (4*dwell_s)))
    print(f"Oscillating for ~{osc_time}s ({loops} loops)...")

    for i in range(loops):
        for xpos in (left, x_peak, right, x_peak):
            atc.move_to(0, xpos); atc.wait_move(0)
            pl = measure_PL(countrate, dwell_time)
            print(f"[osc {i}] x={xpos:.8f} → PL={pl:.2f}")

    print("Oscillation complete; holding at peak.")


def process_x_scan(path):
    try:
        subprocess.run(["python", "PL_x_process.py", path + ".npy"], check=True)
        print("Processing done.")
    except subprocess.CalledProcessError as e:
        print("Post‑process error:", e)


if __name__ == "__main__":
    main()
