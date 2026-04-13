import os
import time
import xarray as xr
from dask.distributed import Client
import numpy as np
from fit.fit_v7 import Fit
from fit.get_data import widefield_get_data
from manual_fitter import correct_esr_dips, manual_fit_from_clicks
from scipy.signal import find_peaks
from scipy.interpolate import interp1d
import matplotlib.pyplot as plt

# Configuration
NUM_MANUAL_FITS = 10
MAX_SHIFT_MHZ = 10
MIN_DIP_DEPTH = 0.0001
SEARCH_WINDOW_MHZ = 15
FORCE_REFIT = False  # Set to True to refit all files
REFIT_INDICES = []   # Optionally specify specific indices to refit, e.g., [10, 25, 100]
LOAD_EXISTING_MANUAL_FITS = True  # If True, load existing manual fits from previous runs

def create_interpolation_model(file_indices, popt_values):
    """
    Create interpolation functions for each parameter in popt.
    Returns a function that predicts popt values for any file index.
    """
    n_params = popt_values.shape[1]
    interpolators = []
    
    for param_idx in range(n_params):
        param_values = popt_values[:, param_idx]
        # Changed from 'linear' to 'cubic'
        interp_func = interp1d(file_indices, param_values, 
                              kind='cubic', fill_value='extrapolate')
        interpolators.append(interp_func)
    
    def predict_popt(file_idx):
        """Predict popt values for a given file index."""
        predicted_popt = np.zeros(n_params)
        for i, interp_func in enumerate(interpolators):
            predicted_popt[i] = interp_func(file_idx)
        return predicted_popt
    
    return predict_popt

def plot_interpolation_overview(manual_indices, all_indices, manual_popts, predict_popt):
    """Plot the manual fits and interpolated predictions for visualization."""
    fig, axes = plt.subplots(4, 2, figsize=(12, 10))
    axes = axes.flatten()
    
    # Plot the 8 center frequencies
    for dip_idx in range(8):
        ax = axes[dip_idx]
        param_idx = 2 + dip_idx * 3  # Center frequency indices
        
        # Manual fits
        manual_freqs = [popt[param_idx] / 1e9 for popt in manual_popts]
        ax.scatter(manual_indices, manual_freqs, color='red', s=50, 
                  label='Manual fits', zorder=3)
        
        # Predicted values for all files
        predicted_freqs = []
        for idx in all_indices:
            pred_popt = predict_popt(idx)
            predicted_freqs.append(pred_popt[param_idx] / 1e9)
        
        ax.plot(all_indices, predicted_freqs, 'b--', alpha=0.5, 
               label='Interpolated', zorder=1)
        
        ax.set_xlabel('File index')
        ax.set_ylabel('Frequency (GHz)')
        ax.set_title(f'Dip {dip_idx + 1}')
        ax.grid(True, alpha=0.3)
        if dip_idx == 0:
            ax.legend()
    
    plt.suptitle('Manual Fits and Interpolation Model')
    plt.tight_layout()
    return fig

# Include the helper functions from your original code
def find_nearby_valid_dips(data, rf_freqs, expected_positions, min_depth=MIN_DIP_DEPTH, search_window_MHz=SEARCH_WINDOW_MHZ):
    """Find valid dips near expected positions."""
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
            corrected_positions.append(expected_freq)
            continue
        
        # Find local minima in this window
        window_data = data[window_indices]
        peaks, properties = find_peaks(-window_data, height=-threshold)
        
        if len(peaks) == 0:
            corrected_positions.append(expected_freq)
        else:
            # Find the closest valid dip to expected position
            peak_freqs = rf_freqs[window_indices[peaks]]
            distances = np.abs(peak_freqs - expected_freq)
            closest_idx = np.argmin(distances)
            corrected_freq = peak_freqs[closest_idx]
            corrected_positions.append(corrected_freq)
    
    return np.array(corrected_positions)

def check_dip_depths(data, popt, rf_freqs, min_depth=MIN_DIP_DEPTH):
    """Check if all fitted dips are deep enough."""
    offset = popt[0]
    threshold = offset * (1 - min_depth)
    
    for i in range(8):
        center_idx = 2 + i * 3
        center_freq = popt[center_idx]
        closest_idx = np.argmin(np.abs(rf_freqs - center_freq))
        data_value = data[closest_idx]
        
        if data_value > threshold:
            return False
    
    return True

if __name__ == "__main__":
    client = Client(n_workers=12, threads_per_worker=1)
    
    folder = r"\\tsn.tno.nl\RA-Data\SV\sv-096125\03_Widefield\Data\Stark\2025_09_19"
    output_folder = os.path.join(folder, "fit_results_interpolated")
    os.makedirs(output_folder, exist_ok=True)
    
    # Load all files
    all_files = sorted(f for f in os.listdir(folder) if f.endswith("esr.h5"))
    print(f"Found {len(all_files)} ESR .h5 files")
    
    # Select files for manual fitting (equally spaced)
    manual_indices = np.linspace(0, len(all_files)-1, NUM_MANUAL_FITS, dtype=int)
    
    print(f"\n{'='*60}")
    print("STEP 1: Manual fitting of anchor points")
    print('='*60)
    
    manual_popts = []
    manual_fits = {}
    
    if LOAD_EXISTING_MANUAL_FITS:
        print("Loading existing manual fits...")
        
        # Load existing manual fits
        for file_idx in manual_indices:
            manual_fit_path = os.path.join(output_folder, f"manual_{file_idx}_" + 
                                         all_files[file_idx].replace(".h5", "_odmr_fit.h5"))
            if os.path.exists(manual_fit_path):
                fit_result = xr.load_dataset(manual_fit_path)
                popt = fit_result.popt.values.flatten()
                manual_popts.append(popt)
                manual_fits[file_idx] = {
                    'file': all_files[file_idx],
                    'popt': popt,
                    'fit_result': fit_result
                }
                print(f"Loaded manual fit for index {file_idx}")
            else:
                print(f"No manual fit found for index {file_idx}")
        
        if len(manual_popts) < 2:
            print("\nNot enough manual fits found. Need at least 2.")
            print("Set LOAD_EXISTING_MANUAL_FITS = False to create new manual fits.")
            exit()
            
    else:
        # Original manual fitting code here
        print(f"\nSelected {NUM_MANUAL_FITS} files for manual fitting:")
        for i, idx in enumerate(manual_indices):
            print(f"  [{idx}] {all_files[idx]}")
            
        # THIS LOOP SHOULD BE INSIDE THE ELSE BLOCK
        for i, file_idx in enumerate(manual_indices):
            file = all_files[file_idx]
            print(f"\n[Manual {i+1}/{NUM_MANUAL_FITS}] Fitting file index {file_idx}: {file}")
            
            # Load ESR data
            ds_esr_norm, _, _ = widefield_get_data(
                folder, file,
                chunksize=10,
                esr_normalized=True,
                ql_normalized=True,
                get_ql=False
            )
            
            subset_ds = ds_esr_norm.sel(x=slice(20, 30), y=slice(20, 30)).mean(dim=["blocks", "y", "x"])
            
            # Manual fitting
            print("Please click on the 8 ESR dips...")
            corrected_ds, dip_guesses = correct_esr_dips(subset_ds)
            
            if dip_guesses and len(dip_guesses) == 8:
                fit_result = manual_fit_from_clicks(
                    corrected_ds, dip_guesses, linewidth=2.0e6
                )
                fit_result["minima"] = ("nr_of_minima", np.array(dip_guesses))
                
                # Store results
                popt = fit_result.popt.values.flatten()
                manual_popts.append(popt)
                manual_fits[file_idx] = {
                    'file': file,
                    'popt': popt,
                    'fit_result': fit_result
                }
                
                # Save manual fit
                out_path = os.path.join(output_folder, f"manual_{file_idx}_" + 
                                       file.replace(".h5", "_odmr_fit.h5"))
                fit_result.to_netcdf(out_path, engine="h5netcdf")
                print(f"Manual fit saved: {out_path}")
            else:
                print("Manual fit failed - need exactly 8 dips")
                continue
    
    if len(manual_popts) < 2:
        print("\nNot enough manual fits for interpolation. Need at least 2.")
        exit()
    
    manual_popts = np.array(manual_popts)
    actual_manual_indices = [idx for idx in manual_indices if idx in manual_fits]
    
    # Create interpolation model
    print(f"\n{'='*60}")
    print("STEP 2: Creating interpolation model")
    print('='*60)
    
    predict_popt = create_interpolation_model(actual_manual_indices, manual_popts)
    
    # Visualize interpolation
    fig = plot_interpolation_overview(actual_manual_indices, 
                                     list(range(len(all_files))), 
                                     manual_popts, predict_popt)
    plt.savefig(os.path.join(output_folder, "interpolation_overview.png"), dpi=150)
    plt.show()
    
    # Process all files
    print(f"\n{'='*60}")
    print("STEP 3: Processing all files with interpolation guidance")
    print('='*60)

    for idx, file in enumerate(all_files):
        print(f"\n[{idx+1}/{len(all_files)}] Processing {file}")
        
        # Skip if manually fitted
        if idx in manual_fits:
            print("Using existing manual fit")
            continue
        
        # Check if already fitted
        out_path_odmr = os.path.join(output_folder, file.replace(".h5", "_odmr_fit.h5"))
        
        if os.path.exists(out_path_odmr) and not FORCE_REFIT and idx not in REFIT_INDICES:
            print(f"Already fitted - skipping")
            continue
        
    # Continue with fitting...
        
        # If not fitted, continue with the rest of the code...
        # Load ESR data
        ds_esr_norm, _, _ = widefield_get_data(
            folder, file,
            chunksize=10,
            esr_normalized=True,
            ql_normalized=True,
            get_ql=False
        )
    
    # ... rest of the fitting code continues as before
        
        subset_ds = ds_esr_norm.sel(x=slice(20, 30), y=slice(20, 30)).mean(dim=["blocks", "y", "x"])
        rf_freqs = subset_ds.coords["rf"].values
        data_values = subset_ds.values
        
        # Create Fit object
        fit_obj = Fit(
            subset_ds,
            nr_of_dips=8,
            linewidth=2.0e6,
            min_distance=0,
            nitrogen=15,
            strain=False,
            divide_zfs=True
        )
        
        # Get interpolated initial guess
        p0 = predict_popt(idx)
        print(f"Using interpolated initial guess")
        
        # Fit with interpolated initial guess
        fit_obj.fit_odmr_data_0d(p0=p0)
        fit_result_ODMR = fit_obj.fit_result
        current_popt = fit_result_ODMR.popt.values.flatten()
        
        # Validate fit
        depth_ok = check_dip_depths(data_values, current_popt, rf_freqs, MIN_DIP_DEPTH)
        
        if not depth_ok:
            print("Fit validation failed, correcting to nearby valid dips...")
            
            # Extract expected positions from current fit
            expected_positions = []
            for i in range(8):
                center_idx = 2 + i * 3
                expected_positions.append(current_popt[center_idx])
            
            # Find valid dips near expected positions
            corrected_positions = find_nearby_valid_dips(
                data_values, rf_freqs, expected_positions,
                min_depth=MIN_DIP_DEPTH, search_window_MHz=SEARCH_WINDOW_MHZ
            )
            
            # Create corrected popt
            for i in range(8):
                center_idx = 2 + i * 3
                current_popt[center_idx] = corrected_positions[i]
            
            # Update fit_result with corrected values
            fit_result_ODMR["popt"] = xr.DataArray(current_popt)
            fit_obj.fit_result = fit_result_ODMR
            
            print("Applied corrections based on nearby valid dips")
        
        # Save ODMR results
        out_path_odmr = os.path.join(output_folder, file.replace(".h5", "_odmr_fit.h5"))
        fit_result_ODMR.to_netcdf(out_path_odmr, engine="h5netcdf")
        print(f"Saved ODMR results -> {out_path_odmr}")
        
        # B-field fit
        if np.isnan(fit_obj.fit_result["minima"].values).any():
            print(f"Skipping B-field fit -> invalid ODMR minima")
        else:
            try:
                start_time = time.time()
                fit_obj.fit_B_field_0d()
                print(f"B-field fit took {time.time() - start_time:.2f} seconds")
                fit_result_B = fit_obj.fit_B_result
                
                # Save B-field results
                out_path_B = os.path.join(output_folder, file.replace(".h5", "_B_fit.h5"))
                fit_result_B.to_netcdf(out_path_B, engine="h5netcdf")
                print(f"Saved B-field results -> {out_path_B}")
            except np.linalg.LinAlgError:
                print(f"B-field fit failed -> singular matrix")
    
    print(f"\n{'='*60}")
    print("COMPLETED: All files processed")
    print('='*60)
    print(f"\nResults saved in: {output_folder}")
    
    # Create summary plot of all fitted dips
    print("\nGenerating summary plot...")
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Plot all fitted center frequencies
    for idx, file in enumerate(all_files):
        if idx in manual_fits:
            # Manual fit
            popt = manual_fits[idx]['popt']
            color = 'red'
            marker = 'o'
            label = 'Manual fit' if idx == actual_manual_indices[0] else ''
        else:
            # Load fitted result
            fit_path = os.path.join(output_folder, file.replace(".h5", "_odmr_fit.h5"))
            if os.path.exists(fit_path):
                fit_result = xr.load_dataset(fit_path)
                popt = fit_result.popt.values
                color = 'steelblue'
                marker = '.'
                label = 'Auto fit' if idx == 0 else ''
            else:
                continue
        
        # Extract centers
        for dip_idx in range(8):
            center_idx = 2 + dip_idx * 3
            center_freq = popt[center_idx] / 1e9
            
            if label:
                ax.scatter(idx, center_freq, color=color, marker=marker, 
                          s=20, label=label if dip_idx == 0 else '', alpha=0.7)
            else:
                ax.scatter(idx, center_freq, color=color, marker=marker, 
                          s=20, alpha=0.7)
    
    ax.set_xlabel('File Index')
    ax.set_ylabel('Frequency (GHz)')
    ax.set_title('All Fitted ESR Dip Centers')
    ax.grid(True, alpha=0.3)
    ax.legend()
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_folder, "all_fits_summary.png"), dpi=150)
    plt.show()
    
    print("\n Processing complete")