# Cryo_ODMR
Script library for cryo-ODMR setup

Ownership goes to the Ishihara lab at TUDelft Qutech. Not allowed to use or distribute without the consent of the owner N.K.Nitzsche.

Scripts-----

%!TEX root
% ******************************* Python Control Scripts ****************************

Linux OS Python Scripts

## Python Control Scripts

Below is a list of the Python scripts used in this project. You can find them in the GitHub repository or on the lab's Ubuntu PC.

### Scripts:

- **CMOS_sweep.py**  
  This script initiates a connection with the R&S AWG, sweeping over the specified bandwidth and plotting PL versus frequency to create ESR measurements.

- **CMOS_sweep_x.py**  
  Similar to `CMOS_sweep.py`, this script performs sweeps in the style of an x-scan, moving to several points in the x-direction, showing the different ESR scans in the x direction.

- **Data_diff.py**  
  This script is useful for comparing measurements taken under different conditions (e.g., RF_on vs RF_off, or RT vs CT). It takes two input folders and plots the difference in PL in a third given output folder (which must be created beforehand).

- **Data_merger.py**  
  If measurements fail due to the piezo stage crashing, this script allows you to merge multiple measurement folders, creating a single processable file from where the measurement left off.

- **Noise_CMOS_sweep.py**  
  Similar to `CMOS_sweep.py`, but this script normalizes the total scan using a reference frequency, combating oscillations and noise during the measurement.

- **PL_2D.py**  
  An older version of `PL_2D_test.py` that connects to the ZI AWG. The script handles piezo glitches by moving the piezo back to the center and trying to return it to the correct position. It sometimes fails and may require a timeout to stop the measurement.

- **PL_2D_mapping.py**  
  The main 3D PL measurement script. It uses the `PL_x_process.py` script for processing, with error handling for piezo glitches through the `fix-atocube` option. The number of steps for this "piezo rest" process can be adjusted in the settings to reduce drift.

- **PL_2D_process.py**  
  A processing script for 2D PL scans, based on an older available version. It includes code for ESR dip fits and strain measurements for future use.

- **PL_2D_test.py**  
  The main version for 2D PL scans at the time of writing. It contains various arguments to adjust measurement sequences, such as z-shape or meandering motion, and uses the `fix-atocube` script for glitch error handling.

- **PL_test.py**  
  A simple script used to move the piezo stages to specific locations without having to use a Python terminal.

- **PL_vs_time.py**  
  This script tracks the PL over a specific period, used to characterize the PL oscillations discussed in the ESR section. It uses the ZI AWG on channel 4.

- **PL_x_process.py**  
  The main processing code for most scripts, especially for `x_scan_Cryo.py` and `2D_PL_mapping.py`. It offers several arguments, which are listed when running the following in the terminal:
  ```bash
  python3 PL_x_process.py -h
  
- **Rabi.py**  
  Rabi oscillations have been attempted but with no success. This code generates an initialization green laser pulse, an RF driving sweep, followed by a green readout laser pulse. The PL is then measured and plotted against different RF driving times.

- **RF_on_script.py**  
  Some of the codes include a built-in RF toggle switch as arguments. For those that do not, this script turns the R&S AWG on at a specific frequency (default: 2.87 GHz). It can be run like any other script and stopped using `ctrl + c`. The AWG will remain on as long as the process is not interrupted.

- **rs_base_signal_gen.py**  
  A QMI base class for R&S AWG instrument control.

- **sma100b.py**  
  An older QMI version of `rs_base_signal_gen.py`.

- **start_remote_swabian_server.py**  
  Starts the Swabian server. This must be done in a separate terminal by running:
  ```bash
  python3 start_remote_swabian_server.py

    Followed by `ctrl + c`, or `ctrl + shift + \` to stop the server. 
  `Ctrl + c` is the recommended option. The computer has crashed before because of the other combination being used too much (several days without restarting the PC).

- **tilt_calc.py**  
  Calculates the tilt based on four measurement points. I found that using `dx/dy` (top) and `dx/dz` (right) gave the best results for `ay` and `az`, respectively.

- **x_scan_Cryo.py**  
  This is the script that runs the x-scan. Arguments allow for more options during and after the measurement.

---

### Error Handling

Several errors and issues were encountered during this project. Below are some solutions to address these problems:

#### Piezo

A frequent error that can occur is related to `USB-connection-timeout` or `USB-busy`. The first solution is to try running the `fix-atocube` option directly from a free terminal (no `python3` needed). Alternatively, unplugging and re-inserting the USB connection may solve the issue. If you are not near the Linux PC, the following code can be used to disconnect and reconnect the USB connection:

`
# Disconnecting driver
```bash
echo -n "1-10.2.1.1" | sudo tee /sys/bus/usb/drivers/usb/unbind
echo 0 | sudo tee /sys/bus/usb/devices/1-10.2.1.1/authorized
lsusb | grep 16c0:055b
```

# Reconnecting driver
```bash
echo 1 | sudo tee /sys/bus/usb/devices/1-10.2.1.1/authorized
echo -n "1-10.2.1.1" | sudo tee /sys/bus/usb/drivers/usb/bind
```


Finally, this can also occur if the piezo stage is being controlled from an open Python terminal somewhere. The piezo can be run using the terminal as follows:
```bash
directory$ python3
>>> from pylablib.devices import Attocube
>>> atc = Attocube.ANC350()
>>> atc.move_to(0,0.003000)
>>> exit()
```


These lines should be run one after the other. It will first open a Python shell, initialize the piezo, and then move the x-axis to 3000 µm. Finally, once done, the shell can be closed using `exit()`.

If the limit of the piezo stage is changing over time, the best solution is to check for loose connections at the cryostat or elsewhere. Additionally, try turning off the piezo controller for a few days (e.g., over the weekend).

If the piezo stage is not moving (hitting a wall on the piezo controller screen), it could be due to several reasons:
- The voltage over the piezo stage may be too low and the weight on the stage too high.
- The stage may have hit its limit (lower limit ranges per stage).
- Something may be blocking the stage from moving inside the piezo.

The first problem can be solved by increasing the voltage, while the last one is situational. The piezo should be able to work with lower voltages at cryogenic temperatures.

---

### AWG (R&S) and Timetagger

In this case, there are generally not many issues. The Timetagger may have trouble initializing if a server connection is used with the internet server option. This can be solved by disconnecting or removing the Timetagger connection from the web application.

As for the AWG, there has been only one issue, which was already discussed in the section on AWG_IP. This solution will reopen the IP connection through a specific port.



-------------Interactive plots----
Download and open in browser to use the interactive plot.
