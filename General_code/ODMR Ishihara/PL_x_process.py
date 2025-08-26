import numpy as np
import matplotlib.pyplot as plt
import json
import argparse
import os
import re
import random
from datetime import datetime
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.widgets import Slider, Button
import mplcursors
import imageio
import webbrowser
import argparse

def process_x_scan(filename, show_peaks=False, suppress_plot=False, refractive_index_adjust=False):
    """
    Process an x-scan data file and plot x-position vs PL intensity.
    Optionally applies refractive index correction (n=2.4) for x-scans when `refractive_index_adjust=True`.
    """
    filename_base = filename[:-4]
    settings_file = filename_base + ".json"
    
    n_diamond = 2.4  # Refractive index of diamond
    threshold_factor = 7.0  # Factor to detect PL increase (adjustable)
    
    try:
        if not os.path.exists(filename) or os.path.getsize(filename) == 0:
            raise ValueError("File is empty or does not exist.")
        PL_data = np.load(filename)
        with open(settings_file, 'r') as f:
            settings = json.load(f)
    except Exception as e:
        print(f"Error loading files: {e}")
        return None, None

    if PL_data.size == 0:
        print(f"Warning: No data found in {filename}")
        return None, None

    x1 = settings.get("x1", 0)
    x2 = settings.get("x2", x1)  # Default x2 to x1 if missing
    num_points = len(PL_data)

    # Convert x positions to micrometers
    x_positions = np.linspace(x1, x2, num_points) * 1e6
    if x1 > x2:
        x_positions = x_positions[::-1]

    # --- Apply refractive index correction only if enabled ---
    x_positions_corrected = np.copy(x_positions)

    if refractive_index_adjust:
        # Detect air-diamond transition
        baseline_PL = np.mean(PL_data[:10])  # Estimate baseline from first 10 points
        entry_index = np.argmax(PL_data > threshold_factor * baseline_PL)  # First PL rise
        x_entry_air = x_positions[entry_index]  # Position of laser entry into diamond

        # Apply refractive index correction for x > x_entry_air
        x_positions_corrected[entry_index:] = x_entry_air + (x_positions[entry_index:] - x_entry_air) * n_diamond
    else:
        x_entry_air = None  # No air-diamond correction applied

    # Find max PL position in the corrected coordinates
    max_idx = np.argmax(PL_data)
    x_max_pos = x_positions[max_idx]
    x_max_pos_corrected = x_positions_corrected[max_idx]  # Corrected max PL position
    max_PL_value = PL_data[max_idx]
    
    settings["max_PL_xpos"] = float(x_max_pos)
    settings["max_PL_xpos_corrected"] = float(x_max_pos_corrected) if refractive_index_adjust else float(x_max_pos)
    settings["max_PL_value"] = float(max_PL_value)
    settings["refractive_index_adjusted"] = refractive_index_adjust  # Store setting in JSON

    if refractive_index_adjust:
        settings["x_entry_air"] = float(x_entry_air)

    with open(settings_file, 'w') as f:
        json.dump(settings, f, indent=4)

    if not suppress_plot:
        plt.figure(figsize=(8, 8), dpi=150)
        plt.plot(x_positions_corrected, PL_data, linestyle='-', color='darkslateblue', linewidth=2, alpha=0.8, 
                 label='PL intensity (corrected)' if refractive_index_adjust else 'PL intensity')
        
        if refractive_index_adjust:
            plt.axvline(x=x_entry_air, color='lightblue', linestyle=':', linewidth=1, label=f'Air-Diamond Entry at {x_entry_air:.2f} μm')
            plt.axvline(x=x_max_pos_corrected, color='darkorange', linestyle='-.', linewidth=1, 
                        label=f'Max PL at {x_max_pos_corrected:.2f} μm (corrected)')
        else:
            plt.axvline(x=x_max_pos, color='darkorange', linestyle='-.', linewidth=1, 
                        label=f'Max PL at {x_max_pos:.2f} μm')

        plt.xlabel("Corrected x-position ($\\mu$m)" if refractive_index_adjust else "x-position ($\\mu$m)", fontsize=14)
        plt.ylabel("PL Intensity (counts/s)", fontsize=14)
        plt.title("X-Scan PL Intensity Profile (Air-to-Diamond Corrected)" if refractive_index_adjust else "X-Scan PL Intensity Profile", fontsize=16)
        plt.grid(True, linestyle=':', linewidth=0.7, alpha=0.7)
        plt.legend()
        plt.savefig(os.path.join(os.path.dirname(filename), filename_base + "_xscan_plot_corrected.png") if refractive_index_adjust 
                    else os.path.join(os.path.dirname(filename), filename_base + "_xscan_plot.png"), dpi=150)
        plt.show()
    
    return x_max_pos_corrected if refractive_index_adjust else x_max_pos, max_PL_value

    
def find_all_max_values(base_folder_path):
    """
    Find the maximum PL intensity and corresponding x-values for all scans.
    """
    files_to_process = [f for f in os.listdir(base_folder_path) if f.endswith(".npy") and "X_PL_scan" in f]
    
    max_values_list = []
    
    for file in files_to_process:
        file_path = os.path.join(base_folder_path, file)
        x_max_pos, max_PL_value = process_x_scan(file_path, suppress_plot=True)
        
        if max_PL_value is not None:
            max_values_list.append((file, x_max_pos, max_PL_value))
    
    print("Maximum values for each scan:")
    for entry in max_values_list:
        print(f"File: {entry[0]}, Max x-position: {entry[1]} μm, Max PL Value: {entry[2]}")
    
    return max_values_list

def calculate_tilt(base_folder_path):
    """
    Calculate the tilt in the z and y direction by computing the difference in
    the x value for max PL at the upper limit values of y and z.
    """
    files_to_process = [f for f in os.listdir(base_folder_path) if f.endswith(".npy") and "X_PL_scan" in f]
    
    data = []  # Store (y, z, x_max_position) values
    
    for file in files_to_process:
        file_path = os.path.join(base_folder_path, file)
        settings_file = file_path[:-4] + ".json"
        
        with open(settings_file, 'r') as f:
            settings = json.load(f)
        
        x_max_pos = settings.get("max_PL_xpos", None)
        if x_max_pos is None:
            continue
        
        match = re.search(r"y([\d\.e-]+)_z([\d\.e-]+)", file)
        if match:
            y_val = float(match.group(1)) * 1e6  # Convert to micrometers
            z_val = float(match.group(2)) * 1e6  # Convert to micrometers
            x_max_pos *= 1e6  # Convert to micrometers
            
            data.append((y_val, z_val, x_max_pos))
    
    if len(data) < 2:
        print("Not enough data points to calculate tilt.")
        return None
    
    # Sorting data by y and z
    data.sort()  # Sorts first by y, then by z

    # Extract min/max y and their corresponding x-values
    min_y = min(data, key=lambda v: v[0])  # Lowest y
    max_y = max(data, key=lambda v: v[0])  # Highest y
    dx_y = max_y[2] - min_y[2]  # Difference in x at min/max y
    dy = max_y[0] - min_y[0]  # Difference in y
    
    # Extract min/max z and their corresponding x-values
    min_z = min(data, key=lambda v: v[1])  # Lowest z
    max_z = max(data, key=lambda v: v[1])  # Highest z
    dx_z = max_z[2] - min_z[2]  # Difference in x at min/max z
    dz = max_z[1] - min_z[1]  # Difference in z
    
    # Compute tilt values
    tilt_y = dx_y / dy if dy != 0 else None
    tilt_z = dx_z / dz if dz != 0 else None
    
    starting_x_value = min_y[2]  # Use x at lowest y as reference
    print(f"Calculated tilt adjustments: tilt_y = {tilt_y:.6f}, tilt_z = {tilt_z:.6f}")
    print(f"Recommended starting x value: {starting_x_value:.6f} μm")
    
    return tilt_y, tilt_z, starting_x_value

def random_x_checker(base_folder_path, num_samples=5):
    """
    Randomly selects a given number of .npy files from the folder and plots x-values vs PL.
    """
    files_to_process = [f for f in os.listdir(base_folder_path) if f.endswith(".npy") and "X_PL_scan" in f]
    if len(files_to_process) == 0:
        print("No .npy files found in the directory.")
        return
    
    selected_files = random.sample(files_to_process, min(num_samples, len(files_to_process)))
    
    plt.figure(figsize=(12, 7), dpi=150)
    for file in selected_files:
        file_path = os.path.join(base_folder_path, file)
        x_max_pos, max_PL_value = process_x_scan(file_path, suppress_plot=True)
        if x_max_pos is not None:
            settings_file = file_path[:-4] + ".json"
            with open(settings_file, 'r') as f:
                settings = json.load(f)
            
            x_positions = np.linspace(settings.get("x2", 0), settings.get("x1", 0), settings.get("x_steps", 100))
            PL_data = np.load(file_path)
            plt.plot(x_positions * 1e6, PL_data, label=file)
    
    plt.xlabel("x-position ($\\mu$m)", fontsize=14)
    plt.ylabel("PL Intensity (counts/s)", fontsize=14)
    plt.title("Random X-Scan PL Profiles", fontsize=16)
    #plt.legend()
    plt.grid(True, linestyle=':', linewidth=0.7, alpha=0.7)
    plt.show()
    

def x_slice_plot(base_folder_path, x_value):
    """
    Extracts and plots the PL values for a given x-value across multiple scans as a 2D heatmap.
    """
    files_to_process = [f for f in os.listdir(base_folder_path) if f.endswith(".npy") and "X_PL_scan" in f]
    
    y_values, z_values, PL_values = [], [], []
    
    for file in files_to_process:
        file_path = os.path.join(base_folder_path, file)
        settings_file = file_path[:-4] + ".json"
        
        with open(settings_file, 'r') as f:
            settings = json.load(f)
        
        PL_data = np.load(file_path)
        x_positions = np.linspace(settings.get("x1", 0), settings.get("x2", 0), len(PL_data))
        if x_positions[0] > x_positions[-1]:  # Ensure correct ordering
            x_positions = x_positions[::-1]
        
        x_value_meters = x_value * 1e-6  # Convert µm to meters
        closest_idx = np.argmin(np.abs(x_positions - x_value_meters))

        #print(f"Processing file: {file}")
        #print(f"x_positions range: {x_positions[0]} - {x_positions[-1]}")
        #print(f"Requested x_value: {x_value}, Closest index: {closest_idx}, Closest x: {x_positions[closest_idx]}")
        #print(f"Selected PL value: {PL_data[closest_idx]}")
        
        match = re.search(r"y([\d\.e-]+)_z([\d\.e-]+)", file)
        if match:
            y_val = float(match.group(1)) * 1e6
            z_val = float(match.group(2)) * 1e6
            y_values.append(y_val)
            z_values.append(z_val)
            PL_values.append(PL_data[closest_idx])
    
    y_unique = np.sort(np.unique(y_values))
    z_unique = np.sort(np.unique(z_values))
    Y, Z = np.meshgrid(y_unique, z_unique)
    PL_grid = np.full(Y.shape, np.nan, dtype=float)
    
    for i, (y, z, pl) in enumerate(zip(y_values, z_values, PL_values)):
        yi = np.where(y_unique == y)[0][0]
        zi = np.where(z_unique == z)[0][0]
        PL_grid[zi, yi] = pl
    
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.set_aspect('equal')
    im = ax.pcolormesh(Y, Z, PL_grid, cmap='viridis', shading='auto')
    fig.colorbar(im, ax=ax, label='PL Intensity (counts/s)', location='right')
    ax.set_xlabel("y-position ($\\mu$m)", fontsize=14)
    ax.set_ylabel("z-position ($\\mu$m)", fontsize=14)
    ax.set_title(f"PL Intensity at x = {x_value:.1f} $\\mu$m", fontsize=16)
    plt.show()


def update_plot(ax, base_folder_path, files_to_process, x_value):
    """
    Update function for plotting a given x_value.
    """
    ax.clear()
    y_values, z_values, PL_values = [], [], []
    
    for file in files_to_process:
        file_path = os.path.join(base_folder_path, file)
        settings_file = file_path[:-4] + ".json"
        
        with open(settings_file, 'r') as f:
            settings = json.load(f)
        
        x_positions = np.linspace(settings.get("x1", 0), settings.get("x2", 0), settings.get("x_steps", 100))
        if x_positions[0] > x_positions[-1]:
            x_positions = x_positions[::-1]
        
        PL_data = np.load(file_path)
        closest_idx = np.searchsorted(x_positions, x_value, side='left')
        closest_idx = min(closest_idx, len(PL_data) - 1)
        
        match = re.search(r"y([\d\.e-]+)_z([\d\.e-]+)", file)
        if match:
            y_val = float(match.group(1)) * 1e6
            z_val = float(match.group(2)) * 1e6
            y_values.append(y_val)
            z_values.append(z_val)
            PL_values.append(PL_data[closest_idx])
    
    y_unique = np.sort(np.unique(y_values))
    z_unique = np.sort(np.unique(z_values))  # No flipping
    Z, Y = np.meshgrid(z_unique, y_unique, indexing='ij')  # Corrected order
    PL_grid = np.full(Y.shape, np.nan, dtype=float)
    
    for i, (y, z, pl) in enumerate(zip(y_values, z_values, PL_values)):
        yi = np.searchsorted(y_unique, y)
        zi = np.searchsorted(z_unique, z)
        PL_grid[zi, yi] = pl
    
    ax.set_aspect('equal')
    im = ax.pcolormesh(Y, Z, PL_grid, cmap='viridis', shading='auto')
    ax.set_xlabel("y-position ($μm)", fontsize=14)
    ax.set_ylabel("z-position ($μm)", fontsize=14)
    ax.set_title(f"2D PL Intensity plot (x = {x_value:.2f} μm)", fontsize=16)
    ax.invert_yaxis()
    return im

def interactive_x_slice_plot(base_folder_path, x_value=None):
    """
    Interactive plot with a slider to switch between x-values and a hover tool to show PL values.
    """
    files_to_process = [f for f in os.listdir(base_folder_path) if f.endswith(".npy") and "X_PL_scan" in f]
    if not files_to_process:
        print("No .npy files found.")
        return
    
    sample_file = os.path.join(base_folder_path, files_to_process[0])
    settings_file = sample_file[:-4] + ".json"
    with open(settings_file, 'r') as f:
        settings = json.load(f)
    
    x_positions = np.linspace(settings.get("x1", 0), settings.get("x2", 0), settings.get("x_steps", 100))
    if x_positions[0] > x_positions[-1]:  # Ensure x_positions are increasing
        x_positions = x_positions[::-1]
    
    fig, ax = plt.subplots(figsize=(8, 8))
    plt.subplots_adjust(right=0.85, bottom=0.2)
    
    x_value_display = plt.text(0.5, 1.05, f"Current x-value: {x_positions[0]:.2f} μm", 
                               horizontalalignment='center', verticalalignment='bottom', 
                               transform=ax.transAxes, fontsize=12, weight='bold')
    cbar = None
    PL_grid = None
    Y, Z = None, None  # Ensure Y and Z are defined
    
    def format_coord(x, y):
        if PL_grid is not None:
            idx = np.argmin(np.abs(Y.flatten() - x) + np.abs(Z.flatten() - y))
            return f'y = {x:.2f} μm, z = {y:.2f} μm, PL: {PL_grid.flatten()[idx]:.2f} counts/s'
        else:
            return f'y = {x:.2f} μm, z = {y:.2f} μm'
    
    ax.format_coord = format_coord
    
    def update(val):
        nonlocal cbar, PL_grid, Y, Z
        ax.clear()
        x_value = slider.val
        x_value_display.set_text(f"Current x-value: {x_value:.2f} μm")
        
        y_values, z_values, PL_values = [], [], []
        
        for file in files_to_process:
            file_path = os.path.join(base_folder_path, file)
            settings_file = file_path[:-4] + ".json"
            
            with open(settings_file, 'r') as f:
                settings = json.load(f)
            
            x_positions = np.linspace(settings.get("x1", 0), settings.get("x2", 0), settings.get("x_steps", 100))
            if x_positions[0] > x_positions[-1]:
                x_positions = x_positions[::-1]
            
            PL_data = np.load(file_path)
            closest_idx = np.searchsorted(x_positions, x_value, side='left')
            closest_idx = min(closest_idx, len(PL_data) - 1)
            
            match = re.search(r"y([\d\.e-]+)_z([\d\.e-]+)", file)
            if match:
                y_val = float(match.group(1)) * 1e6
                z_val = float(match.group(2)) * 1e6
                y_values.append(y_val)
                z_values.append(z_val)
                PL_values.append(PL_data[closest_idx])
        
        y_unique = np.sort(np.unique(y_values))
        z_unique = np.sort(np.unique(z_values))
        Z, Y = np.meshgrid(z_unique, y_unique, indexing='ij')
        PL_grid = np.full(Y.shape, np.nan, dtype=float)
        
        for i, (y, z, pl) in enumerate(zip(y_values, z_values, PL_values)):
            yi = np.searchsorted(y_unique, y)
            zi = np.searchsorted(z_unique, z)
            PL_grid[zi, yi] = pl
        
        ax.set_aspect('equal')
        im = ax.pcolormesh(Y, Z, PL_grid, cmap='viridis', shading='auto')
        if cbar:
            cbar.remove()
        cbar = fig.colorbar(im, ax=ax, label='PL Intensity (counts/s)', location='right')
        ax.set_xlabel("y-position ($\\mu$m)", fontsize=14)
        ax.set_ylabel("z-position ($\\mu$m)", fontsize=14)
        ax.set_title("2D PL Intensity plot", fontsize=16)
        ax.invert_yaxis()
        
        fig.canvas.draw_idle()
    
    slider_ax = plt.axes([0.9, 0.2, 0.03, 0.65])
    slider = Slider(slider_ax, 'x-value', x_positions.min(), x_positions.max(), valinit=x_positions[0], valstep=np.diff(x_positions).mean(), orientation='vertical')
    slider.on_changed(update)
    button_ax_prev = plt.axes([0.05, 0.02, 0.1, 0.05])
    button_prev = Button(button_ax_prev, 'Previous')
    
    button_ax_next = plt.axes([0.17, 0.02, 0.1, 0.05])
    button_next = Button(button_ax_next, 'Next')
    
    def prev_x(event):
        current_x = slider.val
        new_x = max(x_positions[0], current_x - np.diff(x_positions).mean())
        slider.set_val(new_x)
    
    def next_x(event):
        current_x = slider.val
        new_x = min(x_positions[-1], current_x + np.diff(x_positions).mean())
        slider.set_val(new_x)
    
    button_prev.on_clicked(prev_x)
    button_next.on_clicked(next_x)
    
    update(x_positions[0])
    plt.show()

def process_2d_scan(base_folder_path):
    """
    Process multiple x-scan files and generate 2D and 3D visualizations.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_folder = os.path.join(base_folder_path, f"output_{timestamp}")
    os.makedirs(output_folder, exist_ok=True)

    files_to_process = [f for f in os.listdir(base_folder_path) if f.endswith(".npy") and "X_PL_scan" in f]
    max_positions = {}
    max_values = {}

    for file in files_to_process:
        src_path = os.path.join(base_folder_path, file)
        x_max_pos, max_PL_value = process_x_scan(src_path, show_peaks=True, suppress_plot=True)
        if x_max_pos is not None:
            match = re.search(r"y([\d\.e-]+)_z([\d\.e-]+)", file)
            if match:
                y_val = float(match.group(1))
                z_val = float(match.group(2))
                max_positions[(y_val, z_val)] = x_max_pos  # Store in meters
                max_values[(y_val, z_val)] = max_PL_value

    if max_positions:
        y_coords = np.array(sorted(set(y for y, _ in max_positions.keys())))
        z_coords = np.array(sorted(set(z for _, z in max_positions.keys())))
        Z, Y = np.meshgrid(z_coords, y_coords)
        X_max_pos = np.array([[max_positions.get((y, z), 0) * 1e6 for z in z_coords] for y in y_coords])
        PL_max_values = np.array([[max_values.get((y, z), 0) for z in z_coords] for y in y_coords])

        # Compute bin edges for the grid to align the pixels perfectly
        y_edges = np.linspace(Y.min(), Y.max(), Y.shape[0] + 1) * 1e6
        z_edges = np.linspace(Z.min(), Z.max(), Z.shape[1] + 1) * 1e6
        


        plt.figure(figsize=(8, 8), dpi=150)

        # Rotate the data clockwise 90 degrees
        PL_max_values_rotated = np.rot90(PL_max_values, k=-1)

        # Plot the rotated data
        plt.pcolormesh(y_edges, z_edges, PL_max_values_rotated, shading='auto', cmap='viridis')
        plt.colorbar(label='Max PL Intensity (counts/s)')

        # Invert the display of x-axis without modifying the data
        plt.gca().invert_xaxis()  
        plt.gca().invert_yaxis()  # Keep Y-axis inverted
        plt.xlabel('y ($\mu$m)', fontsize=14)
        plt.ylabel('z ($\mu$m)', fontsize=14)
        plt.title('Max PL Intensity Map', fontsize=16)
        plt.grid(True, linestyle=':', linewidth=0.7, alpha=0.7)
        plt.gca().set_aspect('equal', adjustable='box')
        plt.savefig(os.path.join(output_folder, f"2D_PL_max_map_{timestamp}.png"), dpi=150)
        plt.show()



        plt.figure(figsize=(8, 8), dpi=150)
        plt.pcolormesh(y_edges, z_edges, X_max_pos.T, shading='flat', cmap='plasma_r')
        plt.colorbar(label='X-position of max PL ($\mu$m)')
        plt.gca().invert_yaxis()
        plt.xlabel('y ($\mu$m)', fontsize=14)
        plt.ylabel('z ($\mu$m)', fontsize=14)
        plt.title('X-position at Maximum PL Map', fontsize=16)
        plt.grid(True, linestyle=':', linewidth=0.7, alpha=0.7)
        plt.gca().set_aspect('equal', adjustable='box')
        plt.savefig(os.path.join(output_folder, f"2D_X_max_map_{timestamp}.png"), dpi=150)
        plt.show()
   

        fig = plt.figure(figsize=(10, 8))
        ax = fig.add_subplot(111, projection='3d')

        # Scatter plot
        ax.scatter(Y * 1e6, Z * 1e6, X_max_pos, c=X_max_pos, cmap='coolwarm', marker='.')

        # Axis labels
        ax.set_xlabel('y ($\mu$m)')
        ax.set_ylabel('z ($\mu$m)')
        ax.set_zlabel('X max pos ($\mu$m)')
        ax.set_title('3D Visualization of X-position at Max PL')

        # Adjust viewing angle (elev = elevation, azim = azimuthal angle)
        ax.view_init(elev=50, azim=280)  # Change azim and elev for different perspectives

        # Invert Z-axis to make high values appear at the top
        ax.invert_zaxis()

        # Save and show
        plt.savefig(os.path.join(output_folder, f"3D_X_max_plot_{timestamp}.png"), dpi=150)
        plt.show()
        
def generate_x_slice_video(base_folder_path, output_filename='x_slice_animation.gif', duration=500):
    """
    Generates a GIF animation of all x-slice layers.
    """
    files_to_process = [f for f in os.listdir(base_folder_path) if f.endswith(".npy") and "X_PL_scan" in f]
    if not files_to_process:
        print("No .npy files found.")
        return
    
    sample_file = os.path.join(base_folder_path, files_to_process[0])
    settings_file = sample_file[:-4] + ".json"
    with open(settings_file, 'r') as f:
        settings = json.load(f)
    
    x_positions = np.linspace(settings.get("x1", 0), settings.get("x2", 0), settings.get("x_steps", 100))
    
    images = []
    output_filepath = os.path.join(base_folder_path, output_filename)
    print(f"loading...")
    for x_value in x_positions:
        fig, ax = plt.subplots()
        update_plot(ax, base_folder_path, files_to_process, x_value)
        fig.canvas.draw()
        image = np.array(fig.canvas.renderer.buffer_rgba())
        images.append(image)
        plt.close(fig)
    
    imageio.mimsave(output_filepath, images, duration=duration, loop=0)
    print(f"GIF saved at {output_filepath}")
    webbrowser.open(output_filepath)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process PL data.")
    parser.add_argument('filename', help="Path to the .npy file or directory for 2D scan.")
    parser.add_argument('-hide_peaks', action='store_true', help="Toggle to hide detected peaks.")
    parser.add_argument('-x_random_checker', type=int, nargs='?', const=5, help="Randomly process and plot a specified number of x-scans vs PL. Normal amount of plots is 5")
    parser.add_argument('-max_values', action='store_true', help="Find max PL intensity and x-position for all scans in direction.")
    parser.add_argument('-x_slider', action='store_true', help="Interactive slider for x-values in 2D plot showing y and z values vs PL.")
    parser.add_argument('-x_slice', type=float, help="Extract and plot PL values for a specific x-value showing y and z vs PL for that specific x_value. Value should be in um e.g. 4100. If that specific value is not available, finds closest x-value.")
    parser.add_argument("-slice_video", action="store_true", help="Generate an animation of all x-slice layers")
    parser.add_argument('-calculate_tilt', action='store_true', help="Calculate and display tilt adjustments based on y and z values.")
    parser.add_argument('-ref_ind_adjust', action='store_true', help="Apply refractive index correction (n=2.4) and detect air-diamond interface.")

    args = parser.parse_args()
    
    if args.x_slice is not None:
        x_slice_plot(args.filename, args.x_slice)
    elif args.x_slider:
        interactive_x_slice_plot(args.filename)
    elif args.max_values:
        find_all_max_values(args.filename)
    elif args.x_random_checker is not None:
        print(f"Randomly selecting {args.x_random_checker} scans to process...")
        random_x_checker(args.filename, num_samples=args.x_random_checker)
    elif args.slice_video:
        generate_x_slice_video(args.filename)
    elif args.calculate_tilt:
        calculate_tilt(args.filename)
    elif os.path.isdir(args.filename):
        print("Processing 2D scan...")
        process_2d_scan(args.filename)
    else:
        x_max_pos, max_PL_value = process_x_scan(args.filename, show_peaks=not args.hide_peaks, refractive_index_adjust=args.ref_ind_adjust)
        if x_max_pos is None:
            print("Processing failed due to empty or corrupt data.")



