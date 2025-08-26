from pylablib.devices import Attocube
import numpy as np
import time
import json
import os
from datetime import datetime
import TimeTagger
import subprocess
import matplotlib.pyplot as plt

def perform_pl_x_scan(settings, atc, tagger, countrate):
    """Perform PL vs X scan and return the X position with maximum PL count."""
    xmove = np.linspace(settings["x1"], settings["x2"], settings["x_steps"])
    PL = np.zeros(settings["x_steps"])
    
    try:
        for ix, xpos in enumerate(xmove):
            atc.move_to(0, xpos)  # X-axis
            atc.move_to(1, settings["y"])  # Y position
            atc.move_to(2, settings["z"])  # Z position
            
            atc.wait_move(0)
            atc.wait_move(1)
            atc.wait_move(2)
            
            # Perform measurement
            countrate.startFor(settings["dwell_time"])
            countrate.waitUntilFinished()
            rate = countrate.getData()[0]
            PL[ix] = rate
            print(f"Moved to: x={xpos:.6f} m, PL count: {rate:.2f}")
            
        print("X-axis scan complete!")
        # Get X position corresponding to max PL value
        max_x = xmove[np.argmax(PL)]
        max_PL_value = PL[np.argmax(PL)]
        print(f"Max PL value of {max_PL_value:.2f} at x={max_x:.6f} m")
        return max_x, xmove, PL
    except Exception as e:
        print(f"Error during scan: {e}")
        return None, None, None

def save_plot(x_positions, PL_data, position_name, save_path, max_x):
    """Save PL vs X plot for each position and indicate max PL point."""
    plt.figure(figsize=(8, 6), dpi=150)
    plt.plot(x_positions * 1e6, PL_data, linestyle='-', color='darkslateblue', linewidth=2, alpha=0.8, label='PL Intensity')
    plt.axvline(x=max_x * 1e6, color='red', linestyle='--', linewidth=1.5, label=f'Max PL at {max_x * 1e6:.2f} µm')
    plt.xlabel("X-position (µm)", fontsize=14)
    plt.ylabel("PL Intensity (counts/s)", fontsize=14)
    plt.title(f"X-Scan PL Intensity Profile ({position_name})", fontsize=16)
    plt.grid(True, linestyle=':', linewidth=0.7, alpha=0.7)
    plt.legend()
    plot_filename = os.path.join(save_path, f"PL_x_scan_{position_name}.png")
    plt.savefig(plot_filename, dpi=150)
    plt.close()
    
def suggest_x(y, z, reference_x, reference_y, reference_z, dx_dy, dx_dz):
    """Suggest the x value for a given y and z coordinate based on the calculated tilt."""
    suggested_x = reference_x + dx_dy * (y - reference_y) + dx_dz * (z - reference_z)
    print(f"Suggested x-value for y={y:.6f}, z={z:.6f}: {suggested_x:.6f} m")
    return suggested_x

def main():
    # Define scan positions
    positions = {
        "top_left": {"y": 556e-6, "z": 1776e-6},
        "top_right": {"y": 1566e-6, "z": 1776e-6},
        "bottom_left": {"y": 556e-6, "z": 2917e-6},
        "bottom_right": {"y": 1566e-6, "z": 2927e-6}
    }
    
    settings = {
        "save_folder": "/home/dl-lab-pc3/Documents/Nikolaj_Nitzsche/Cryo/X-Scans/Tilt/",
        "x_steps": 200,
        "x1": 2700e-6,
        "x2": 3100e-6,
        "y0": 310e-6,
        "z0": 1500e-6,
        "dwell_time": 2e11,
        "measurement_type": "PL",
        "note": "Maarten sample tilt measuremnt"
    }
    
    # Create a new folder with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(settings["save_folder"], timestamp)
    os.makedirs(save_path, exist_ok=True)
    settings["save_folder"] = save_path
    
    # Initialize devices
    atc = Attocube.ANC350()
    atc.set_frequency(0, 800)
    atc.set_frequency(1, 800)
    atc.set_frequency(2, 800)
    atc.set_voltage(0, 50)
    atc.set_voltage(1, 50)
    atc.set_voltage(2, 50)
    
    # Ensure TimeTagger is created only once
    try:
        tagger = TimeTagger.createTimeTaggerNetwork('localhost:41101')
    except Exception as e:
        print(f"Error initializing TimeTagger: {e}")
        return
    
    countrate = TimeTagger.Countrate(tagger=tagger, channels=[5])
    
    max_x_positions = {}
    
    try:
        for pos_name, coords in positions.items():
            print(f"Scanning at {pos_name} position: y={coords['y']}, z={coords['z']}")
            settings.update(coords)  # Set Y and Z for this scan
            max_x, x_positions, PL_data = perform_pl_x_scan(settings, atc, tagger, countrate)
            if max_x is not None:
                max_x_positions[pos_name] = max_x
                save_plot(x_positions, PL_data, pos_name, save_path, max_x)
    
        print("All scans completed and plots saved.")
    
        # Compute slopes for the tilt along the y-direction and z-direction.
        dx_dy_top = (max_x_positions["top_right"] - max_x_positions["top_left"]) / \
                    (positions["top_right"]["y"] - positions["top_left"]["y"])
        
        dx_dy_bottom = (max_x_positions["bottom_right"] - max_x_positions["bottom_left"]) / \
                       (positions["bottom_right"]["y"] - positions["bottom_left"]["y"])
        
        dx_dz_left = (max_x_positions["bottom_left"] - max_x_positions["top_left"]) / \
                     (positions["bottom_left"]["z"] - positions["top_left"]["z"])
        
        dx_dz_right = (max_x_positions["bottom_right"] - max_x_positions["top_right"]) / \
                      (positions["bottom_right"]["z"] - positions["top_right"]["z"])
        
        print(f"dx/dy (top): {dx_dy_top:.6f}, dx/dy (bottom): {dx_dy_bottom:.6f}")
        print(f"dx/dz (left): {dx_dz_left:.6f}, dx/dz (right): {dx_dz_right:.6f}")
        
        # Compute the expected (average) slopes from opposing sides.
        expected_dx_dy = (dx_dy_top + dx_dy_bottom) / 2
        expected_dx_dz = (dx_dz_left + dx_dz_right) / 2
        
        print(f"Expected dx/dy (average of top and bottom): {expected_dx_dy:.6f}")
        print(f"Expected dx/dz (average of left and right): {expected_dx_dz:.6f}")
        
        # Optionally, you could also compute the deviation of each measured slope from the expected value if needed.
        diff_dxdy_top = abs(dx_dy_top - expected_dx_dy)
        diff_dxdy_bottom = abs(dx_dy_bottom - expected_dx_dy)
        diff_dxdz_left = abs(dx_dz_left - expected_dx_dz)
        diff_dxdz_right = abs(dx_dz_right - expected_dx_dz)
        
        print(f"Deviation of top dx/dy from expected: {diff_dxdy_top:.6f}")
        print(f"Deviation of bottom dx/dy from expected: {diff_dxdy_bottom:.6f}")
        print(f"Deviation of left dx/dz from expected: {diff_dxdz_left:.6f}")
        print(f"Deviation of right dx/dz from expected: {diff_dxdz_right:.6f}")
    
        # Compute expected X value for bottom-right corner using the expected slopes
        expected_x_br = max_x_positions["bottom_left"] + expected_dx_dy * (positions["bottom_right"]["y"] - positions["bottom_left"]["y"]) + expected_dx_dz * (positions["bottom_right"]["z"] - positions["bottom_left"]["z"])
        measured_x_br = max_x_positions["bottom_right"]
        deviation_percentage = abs((measured_x_br - expected_x_br) / expected_x_br) * 100
        
        print(f"Expected X at bottom-right: {expected_x_br:.6f}, Measured X at bottom-right: {measured_x_br:.6f}")
        print(f"Deviation percentage: {deviation_percentage:.2f}%")
        
        # Check if the slopes are consistent within 10% relative tolerance
        if np.isclose(dx_dy_top, dx_dy_bottom, rtol=0.1) and np.isclose(dx_dz_left, dx_dz_right, rtol=0.1):
            print("dx/dy and dx/dz are consistent across positions.")
        else:
            print("Warning: dx/dy or dx/dz values are not consistent.")
            
        # Example usage of the suggestion function
        suggest_x(settings["y0"], settings["z0"], max_x_positions["top_left"], positions["top_left"]["y"], positions["top_left"]["z"], expected_dx_dy, expected_dx_dz)
        
    finally:
        atc.stop()
        atc.close()
        del tagger

if __name__ == "__main__":
    main()
