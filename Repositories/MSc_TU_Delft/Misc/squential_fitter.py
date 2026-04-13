import os
import time
import xarray as xr
from dask.distributed import Client
import numpy as np
from fit.fit_v7 import Fit
from fit.get_data import widefield_get_data
from manual_fitter import correct_esr_dips, manual_fit_from_clicks
from scipy.signal import find_peaks

USE_MANUAL_FIRST = True   # Set to False for normal fitter, True for manual fitter
MAX_SHIFT_MHZ = 10  # Maximum allowed shift in MHz between consecutive measurements
MIN_DIP_DEPTH = 0.0001  # Minimum required dip depth (0.01% below baseline)
SEARCH_WINDOW_MHZ = 15  # Search window around expected position in MHz

def find_nearby_valid_dips(data, rf_freqs, expected_positions, min_depth=MIN_DIP_DEPTH, search_window_MHz=SEARCH_WINDOW_MHZ):
    """
    Find valid dips near expected positions.
    Returns array of corrected positions or None if can't find enough valid dips.
    """
    baseline = np.median(data)
    threshold = baseline * (1 - min_depth)
    search_window_Hz = search_window_MHz * 1e6
    
    corrected_positions = []
    
    for i, expected_freq in enumerate(expected_positions):
        # Define search window
        min_freq = expected_freq - search_window_Hz
        max_freq = expected_freq + search_window_Hz
        
        # Find indices within search window
        mask = (rf_freqs >= min_freq) & (rf_freqs <= max_freq)
        window_indices = np.where(mask)[0]
        
        if len(window_indices) == 0:
            print(f"  Dip {i+1}: No data in search window around {expected_freq/1e9:.3f} GHz")
            corrected_positions.append(expected_freq)  # Keep original
            continue
        
        # Find local minima in this window
        window_data = data[window_indices]
        
        # Find peaks in inverted data (to find minima)
        peaks, properties = find_peaks(-window_data, height=-threshold)
        
        if len(peaks) == 0:
            print(f"  Dip {i+1}: No valid dips found near {expected_freq/1e9:.3f} GHz")
            corrected_positions.append(expected_freq)  # Keep original
        else:
            # Find the closest valid dip to expected position
            peak_freqs = rf_freqs[window_indices[peaks]]
            distances = np.abs(peak_freqs - expected_freq)
            closest_idx = np.argmin(distances)
            corrected_freq = peak_freqs[closest_idx]
            shift_MHz = (corrected_freq - expected_freq) / 1e6
            
            print(f"  Dip {i+1}: Corrected from {expected_freq/1e9:.3f} to {corrected_freq/1e9:.3f} GHz (shift: {shift_MHz:.2f} MHz)")
            corrected_positions.append(corrected_freq)
    
    return np.array(corrected_positions)

def create_corrected_popt(original_popt, corrected_positions):
    """
    Create a new popt array with corrected center positions.
    """
    corrected_popt = original_popt.copy()
    
    for i in range(8):
        center_idx = 2 + i * 3
        corrected_popt[center_idx] = corrected_positions[i]
    
    return corrected_popt

def check_minima_shift(current_popt, previous_popt, max_shift_MHz=20):
    """
    Check if minima positions have shifted too much between files.
    Returns True if shifts are acceptable, False if there's a large jump.
    """
    # Extract center frequencies from popt (indices 2, 5, 8, 11, 14, 17, 20, 23)
    current_centers = []
    previous_centers = []
    
    for i in range(8):
        center_idx = 2 + i * 3
        current_centers.append(current_popt[center_idx])
        previous_centers.append(previous_popt[center_idx])
    
    # Sort both arrays to match corresponding dips
    current_sorted = np.sort(current_centers)
    previous_sorted = np.sort(previous_centers)
    
    # Check maximum shift
    max_shift = np.max(np.abs(current_sorted - previous_sorted))
    max_shift_MHz_found = max_shift / 1e6
    
    print(f"Maximum dip shift: {max_shift_MHz_found:.2f} MHz")
    
    return max_shift < max_shift_MHz * 1e6  # Convert MHz to Hz

def check_dip_depths(data, popt, rf_freqs, min_depth=MIN_DIP_DEPTH):
    """
    Check if all fitted dips are deep enough (below threshold).
    Returns True if all dips meet the minimum depth requirement.
    """
    offset = popt[0]  # baseline level
    threshold = offset * (1 - min_depth)  # e.g., 0.999 * baseline for 0.1% depth
    
    invalid_dips = 0
    
    for i in range(8):
        center_idx = 2 + i * 3
        center_freq = popt[center_idx]
        
        # Find the closest data point to the fitted center
        closest_idx = np.argmin(np.abs(rf_freqs - center_freq))
        data_value = data[closest_idx]
        
        # Check if the data at this position is below the threshold
        if data_value > threshold:
            print(f"  Dip {i+1} at {center_freq/1e9:.3f} GHz: value={data_value:.4f} > threshold={threshold:.4f}")
            invalid_dips += 1
    
    if invalid_dips > 0:
        print(f"{invalid_dips}/8 dips fail depth requirement (< {min_depth*100:.1f}% below baseline)")
        return False
    
    return True

if __name__ == "__main__":
    client = Client(n_workers=12, threads_per_worker=1)
    
    folder = r"\\tsn.tno.nl\RA-Data\SV\sv-096125\03_Widefield\Data\Stark\2025_09_19"
    output_folder = os.path.join(folder, "fit_results_seq_with_prev")
    os.makedirs(output_folder, exist_ok=True)

    all_files = sorted(f for f in os.listdir(folder) if f.endswith("esr.h5"))[95:]

    print(f"Found {len(all_files)} ESR .h5 files")
    
    # Keep track of the last valid fit parameters
    last_valid_popt = None

    for idx, file in enumerate(all_files, start=1):
        print(f"\n[{idx}/{len(all_files)}] Running file: {file}")

        # --- Load ESR data ---
        ds_esr_norm, _, _ = widefield_get_data(
            folder, file,
            chunksize=10,
            esr_normalized=True,
            ql_normalized=True,
            get_ql=False
        )

        subset_ds = ds_esr_norm.sel(x=slice(20, 30), y=slice(20, 30)).mean(dim=["blocks", "y", "x"])
        rf_freqs = subset_ds.coords["rf"].values
        data_values = subset_ds.values

        # --- Create Fit object ---
        fit_obj = Fit(
            subset_ds,
            nr_of_dips=8,
            linewidth=1.0e6,
            min_distance=0,
            nitrogen=15,
            strain=False,
            divide_zfs=True
        )

        if idx > 1 and last_valid_popt is not None:
            print("Using previous fit parameters as initial guess")
            fit_obj.fit_odmr_data_0d(p0=last_valid_popt)
            fit_result_ODMR = fit_obj.fit_result
            
            # Check if the shift is acceptable AND dips are deep enough
            current_popt = fit_result_ODMR.popt.values.flatten()
            shift_ok = check_minima_shift(current_popt, last_valid_popt, MAX_SHIFT_MHZ)
            depth_ok = check_dip_depths(data_values, current_popt, rf_freqs, MIN_DIP_DEPTH)
            
            if not shift_ok or not depth_ok:
                print("\nFit validation failed, searching for nearby valid dips...")
                
                # Extract expected positions from previous fit
                expected_positions = []
                for i in range(8):
                    center_idx = 2 + i * 3
                    expected_positions.append(last_valid_popt[center_idx])
                
                # Find valid dips near expected positions
                corrected_positions = find_nearby_valid_dips(
                    data_values, rf_freqs, expected_positions,
                    min_depth=MIN_DIP_DEPTH, search_window_MHz=SEARCH_WINDOW_MHZ
                )
                
                # Create corrected popt
                current_popt = create_corrected_popt(current_popt, corrected_positions)
                
                # Update fit_result with corrected values
                fit_result_ODMR["popt"] = xr.DataArray(current_popt)
                fit_obj.fit_result = fit_result_ODMR
                
                print("Applied corrections based on nearby valid dips")
            
            # Update last valid popt
            last_valid_popt = current_popt
            
            # Save ODMR results
            out_path_odmr = os.path.join(output_folder, file.replace(".h5", "_odmr_fit.h5"))
            fit_result_ODMR.to_netcdf(out_path_odmr, engine="h5netcdf")
            print(f"Saved ODMR results -> {out_path_odmr}")

        else:
            print("First file, no previous fit available")
            if USE_MANUAL_FIRST:
                print("Using manual fitter for first file")
                corrected_ds, dip_guesses = correct_esr_dips(subset_ds)

                if dip_guesses:
                    fit_result_ODMR = manual_fit_from_clicks(
                        corrected_ds, dip_guesses, linewidth=fit_obj.linewidth
                    )
                    # Store the clicked minima explicitly
                    fit_result_ODMR["minima"] = ("nr_of_minima", np.array(dip_guesses))

                    # assign to fit_obj so later code works
                    fit_obj.fit_result = fit_result_ODMR

                else:
                    print("No dips clicked, falling back to normal fit")
                    fit_obj.fit_odmr_data_0d()
                    fit_result_ODMR = fit_obj.fit_result
            else:
                fit_obj.fit_odmr_data_0d()  # first file normal
                fit_result_ODMR = fit_obj.fit_result

            # Store the first valid popt
            last_valid_popt = fit_result_ODMR.popt.values.flatten()

            # Save ODMR results (overwrite if exists)
            out_path_odmr = os.path.join(output_folder, file.replace(".h5", "_odmr_fit.h5"))
            fit_result_ODMR.to_netcdf(out_path_odmr, engine="h5netcdf")
            print(f"Saved ODMR results -> {out_path_odmr}")
        
        # --- B-field fit ---
        if np.isnan(fit_obj.fit_result["minima"].values).any():
            print(f"Skipping B-field fit for {file} -> invalid ODMR minima")

        else:
            try:
                start_time = time.time()
                fit_obj.fit_B_field_0d()
                print(f"B-field fit took {time.time() - start_time:.2f} seconds")
                fit_result_B = fit_obj.fit_B_result

                # Save B-field results (overwrite if exists)
                out_path_B = os.path.join(output_folder, file.replace(".h5", "_B_fit.h5"))
                fit_result_B.to_netcdf(out_path_B, engine="h5netcdf")
                print(f"Saved B-field results -> {out_path_B}\n")
            except np.linalg.LinAlgError:
                print(f"B-field fit failed for {file} -> singular matrix")