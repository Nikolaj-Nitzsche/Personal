import os

import h5py
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
from ipywidgets import interact, IntSlider
import sys

sys.path.append(r'C:/Users/nitzschenk/OneDrive - TNO/Documents/Code/TNO_scripts/Data_analysis')

from plot import *
from fit_v7 import *
from get_data import *

from class_definitions import *

test_plots_class.plot_1()
test_plots_class.plot_2()

folder = r"\\tsn.tno.nl\RA-Data\SV\sv-096125\03_Widefield\Data\Stark\2025_08_25"
file = r"20250821_134256_esr.h5"


ds_esr, ds_ql, ds_timetrace = h5_file_read_class.widefield_get_data(folder, file, ql_normalized=True)

data_ds = ds_ql.mean(dim="ql_blocks")


plt.figure(figsize=(12, 8))
plt.plot(data_ds.rf.values, data_ds.values, color='slateblue')
plt.title('ESR Spectrum')
plt.xlabel('RF Frequency (GHz)')
plt.ylabel('Normalized PL')
plt.axvline(x=2.87e9, color='orchid', linestyle='--', label='Zero Field Splitting (2.87 GHz)')
plt.legend()
plt.grid()
plt.show()