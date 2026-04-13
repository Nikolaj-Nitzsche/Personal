import os
import time

import h5py
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
from ipywidgets import interact, IntSlider

from fit.fit_v7 import Fit
from fit.plot import (
    Plot_ODMR_0D,
    Plot_ODMR_1D,
    Plot_ODMR_2D,
    Plot_Hamiltonian_Parameters,
    Plot_Sensitivity,
)

from fit.get_data import *
from dask.distributed import Client

if __name__ == "__main__":

    client = Client(
        n_workers=12, threads_per_worker=1
    )  # start distributed scheduler locally.

    folder = r"\\tsn.tno.nl\RA-Data\SV\sv-096125\03_Widefield\Data\Stark\2025_09_19"
    file = r"20250918_162916_esr.h5"

    output_folder = os.path.join(folder, "fit_results")
    os.makedirs(output_folder, exist_ok=True)

    all_files = sorted(f for f in os.listdir(folder) if f.endswith("esr.h5"))
    print(f"Found {len(all_files)} ESR .h5 files")

    # Loop through files
    for idx, file in enumerate(all_files, start=1):
        print(f"[{idx}/{len(all_files)}] Running file: {file}")
        
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

        fit_obj = Fit(
            subset_ds,
            nr_of_dips=8,
            linewidth=2.0e6,
            min_distance=0,
            nitrogen=15,
            strain=False,
            divide_zfs=True
        )

        # --- ODMR fit ---
        start_time = time.time()
        fit_obj.fit_odmr_data_0d()
        print(f"ODMR fit took {time.time() - start_time:.2f} seconds")
        fit_result_ODMR = fit_obj.fit_result

        # Save ODMR results
        out_path_odmr = os.path.join(output_folder, file.replace(".h5", "_odmr_fit.h5"))
        fit_result_ODMR.to_netcdf(out_path_odmr, engine="h5netcdf")
        print(f"Saved ODMR results -> {out_path_odmr}")

        # --- B-field fit ---
        start_time = time.time()
        fit_obj.fit_B_field_0d()
        print(f"B-field fit took {time.time() - start_time:.2f} seconds")
        fit_result_B = fit_obj.fit_B_result

        # Save B-field results
        out_path_B = os.path.join(output_folder, file.replace(".h5", "_B_fit.h5"))
        fit_result_B.to_netcdf(out_path_B, engine="h5netcdf")
        print(f"Saved B-field results -> {out_path_B}\n")



