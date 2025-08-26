import numpy as np
import matplotlib.pyplot as plt
import os
import h5py
import numpy as np
import xarray as xr


class test_plots_class:
    def plot_1():
        # Create a grid of x and y values from 0 to 100
        x = np.arange(0, 1001)
        y = np.arange(0, 1001)
        X, Y = np.meshgrid(x, y)

        # Smooth transition parameters
        transition_width = 5  # width of the transition region

        # Create smooth masks using a sigmoid function for both X and Y
        def smooth_step(val, edge0, edge1, width):
            # Smoothly transitions from 0 to 1 between edge0 and edge1
            return 1 / (1 + np.exp(-(val - edge0) / width)) * (1 - 1 / (1 + np.exp(-(val - edge1) / width)))

        # Calculate smooth masks for X and Y
        mask_x = smooth_step(X, 150, 850, transition_width)
        mask_y = smooth_step(Y, 150, 850, transition_width)
        smooth_mask = mask_x * mask_y

        # Each pixel value is the sum of its x and y coordinates
        Z_add = X + Y
        Z_sub = abs(X - Y)

        # Blend between add and subtract using the smooth mask
        Z = (1 - smooth_mask) * Z_add + smooth_mask * Z_sub

        plt.figure(figsize=(12, 8))
        plt.imshow(Z, origin='lower', extent=[0, 1000, 0, 1000], cmap='inferno', aspect='auto')
        plt.colorbar(label='Pixel Value')
        plt.xlabel('x-axis')
        plt.ylabel('y-axis')
        plt.title('2D Plot: Add or Subtract Based on Region (Smooth Transition)')
        plt.show()


    def plot_2():
        # Create a grid of x and y values from 0 to 100
        x = np.arange(0, 1001)
        y = np.arange(0, 1001)
        X, Y = np.meshgrid(x, y)

        # Smooth transition parameters
        transition_width = 5  # width of the transition region

        # Create smooth masks using a sigmoid function for both X and Y
        def smooth_step(val, edge0, edge1, width):
            # Smoothly transitions from 0 to 1 between edge0 and edge1
            return 1 / (1 + np.exp(-(val - edge0) / width)) * (1 - 1 / (1 + np.exp(-(val - edge1) / width)))

        # Calculate smooth masks for X and Y
        mask_x = smooth_step(X, 150, 850, transition_width)
        mask_y = smooth_step(Y, 150, 850, transition_width)
        smooth_mask = mask_x * mask_y

        # Each pixel value is the sum of its x and y coordinates
        Z_add = X + Y
        Z_sub = abs(X - Y)

        # Blend between add and subtract using the smooth mask
        Z = (1 - smooth_mask) * Z_add + smooth_mask * Z_sub
        
        plt.figure(figsize=(12, 8))
        plt.imshow(Z, origin='lower', extent=[0, 1000, 0, 1000], cmap='magma', aspect='auto')
        plt.colorbar(label='Pixel Value')
        plt.xlabel('x-axis')
        plt.ylabel('y-axis')
        plt.title('2D Plot: Add or Subtract Based on Region (Smooth Transition)')
        plt.show()

    
class h5_file_read_class:
    def widefield_get_data(
        folder,
        file,
        esr_normalized=True,
        get_ql=True,
        ql_normalized=True,
        get_timetrace=True,
        chunksize=10,
    ):
        ds = xr.open_dataset(
            os.path.join(folder, file),
            group="data",
            chunks={
                "phony_dim_0": 1,
                "phony_dim_1": chunksize,
                "phony_dim_2": chunksize,
                "phony_dim_4": 1,
            },
        )

        ds = ds.rename_dims(
            {
                "phony_dim_0": "blocks",
                "phony_dim_1": "y",
                "phony_dim_2": "x",
                "phony_dim_3": "rf",
                "phony_dim_4": "ql_blocks",
            }
        )

        f = h5py.File(os.path.join(folder, file), "r")
        xdata = f["rf_frequencies"][:]

        if esr_normalized:
            ds_esr = xr.DataArray(
                ds["esr_normalized"],
                coords=[
                    np.arange(ds.sizes["blocks"]),
                    np.arange(ds.sizes["y"]),
                    np.arange(ds.sizes["x"]),
                    xdata,
                ],
                dims=["blocks", "y", "x", "rf"],
            )
        else:
            ds_esr = xr.DataArray(
                ds["esr"],
                coords=[
                    np.arange(ds.sizes["blocks"]),
                    np.arange(ds.sizes["y"]),
                    np.arange(ds.sizes["x"]),
                    xdata,
                ],
                dims=["blocks", "y", "x", "rf"],
            )
        if get_ql:
            if ql_normalized:
                ds_ql = xr.DataArray(
                    ds["quicklook_normalized"],
                    coords=[np.arange(ds.sizes["ql_blocks"]), xdata],
                    dims=["ql_blocks", "rf"],
                )
            else:
                ds_ql = xr.DataArray(
                    ds["quicklook"],
                    coords=[np.arange(ds.sizes["ql_blocks"]), xdata],
                    dims=["ql_blocks", "rf"],
                )
        else:
            ds_ql = None

        if get_timetrace:
            if "timetrace" in ds:
                ds_timetrace = xr.DataArray(
                    ds["timetrace"],
                    coords=[
                        np.arange(ds.sizes["ql_blocks"]),
                        np.arange(ds.sizes["y"]),
                        np.arange(ds.sizes["x"]),
                    ],
                    dims=["ql_blocks", "y", "x"],
                )
            else:
                ds_timetrace = None
                print("Warning: there is no timetrace in the file; ds_timetrace = None.")
        else:
            ds_timetrace = None

        return ds_esr, ds_ql, ds_timetrace
    
        
if __name__ == "__main__":
    test_plots_class.plot_1()
    test_plots_class.plot_2()