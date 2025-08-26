import os
from rtcs.devices.zurichinstruments.shfsg_rtcs import ShfsgRtcs
from time import sleep
import TimeTagger
import matplotlib.pyplot as plt
from laboneq.simple import DeviceSetup, Session
import json
import time
import numpy as np
from datetime import datetime

# ======= SETUP OUTPUT DIRECTORY ===========
save_dir = "/home/dl-lab-pc3/Documents/Nikolaj_Nitzsche/Cryo/Rabi"
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # Timestamped folder
save_path = os.path.join(save_dir, f"Rabi_{timestamp}")
os.makedirs(save_path, exist_ok=True)  # Create folder if it doesn't exist
print(f"Saving data to: {save_path}")

# ======= INITIALIZE SHFSG DEVICE ===========
sh = ShfsgRtcs(serial_number='DEV12120')
sh.open()
print('Device is open')

# ======= SETUP DEVICE SESSION ===========
server_host = "localhost"  # Your server host (replace if necessary)
descriptor = """
instruments:
    SHFSG:
        - address: DEV12120
          uid: device_shfsg
          interface: 1GbE

connections:
    device_shfsg:
        - iq_signal: q0/drive_line
          ports: SGCHANNELS/0/OUTPUT
        - iq_signal: q1/drive_line
          ports: SGCHANNELS/1/OUTPUT
"""

my_setup = DeviceSetup.from_descriptor(
    yaml_text=descriptor,
    server_host=server_host,
    server_port='8004',
    setup_name='Setup_Name'
)
my_session = Session(device_setup=my_setup)
my_session.connect()

# ======= CONFIGURE AWG CHANNEL ===========
device = my_session.devices['device_shfsg']
channel_index = 1  # Set the desired channel (1 for SGCHANNELS/1/OUTPUT)
output_range = 0  # Adjust as needed
center_frequency = 2.87e9  # 2.87 GHz frequency
rf_path = 1  # Adjust as needed

device.sgchannels[channel_index].configure_channel(
    enable=True, 
    output_range=output_range, 
    center_frequency=center_frequency,
    rf_path=rf_path  # Required parameter
)

osc1_frequency = 7e7  # Example oscillator frequency
gains_cw = (0.0, 0.95, 0.95, 0.0)

device.sgchannels[channel_index].configure_sine_generation(
    enable=True,
    osc_index=0,
    osc_frequency=osc1_frequency,
    phase=0,
    gains=gains_cw
)

# ======= SETUP TIMETAGGER FOR PL MEASUREMENT ===========
tagger = TimeTagger.createTimeTaggerNetwork('localhost:41101')
countrate = TimeTagger.Countrate(tagger=tagger, channels=[1])

# ======= EXPERIMENT PARAMETERS ===========
num_pulse_trains = 40
start_time_ms = 0.00001  # Start driving time in ms
end_time_ms = 0.0002  # End driving time in ms
driving_times = np.linspace(start_time_ms, end_time_ms, num_pulse_trains)

num_measurements = 500  # Number of train sequences  #100 trains with 20 points ~8 min
PL_values = np.zeros((num_measurements, num_pulse_trains))

# ======= RUN EXPERIMENT ===========
for measurement_num in range(num_measurements):
    print(f"------------------ Measurement {measurement_num + 1} of {num_measurements} ----------------")
    
    for pulse_num in range(num_pulse_trains):
        driving_time_s = driving_times[pulse_num] / 1000

        print(f"Pulse {pulse_num+1}: Driving time = {driving_times[pulse_num]} ms")

        # Laser on
        sh.set_marker_state(1, 1)
        sleep(0.010)  # 10 milliseconds

        # AWG ON
        sh.set_marker_state(1, 0)  # Turn laser off
        device.sgchannels[channel_index].configure_sine_generation(
            enable=True, osc_index=0, osc_frequency=center_frequency, phase=0
        )
        sleep(driving_time_s)

        # AWG OFF
        device.sgchannels[channel_index].configure_sine_generation(enable=False)

        # Laser on again
        sh.set_marker_state(1, 1)
        
        # PL Measurement
        countrate.startFor(10e6)  
        countrate.waitUntilFinished()
        pl_rate = countrate.getData()[0]
        print(f"PL Measurement after pulse {pulse_num+1}: {pl_rate} counts")
        sh.set_marker_state(1, 0)

        # Store PL data
        PL_values[measurement_num, pulse_num] = pl_rate

# ======= AVERAGE PL VALUES ===========
avg_pl = np.mean(PL_values, axis=0)  # Average over all measurements

# ======= SAVE DATA ===========
np.save(os.path.join(save_path, "PL_values.npy"), PL_values)  # Save as .npy
np.savetxt(os.path.join(save_path, "PL_values.csv"), PL_values, delimiter=",")  # Save as CSV
np.savetxt(os.path.join(save_path, "averaged_PL.csv"), np.column_stack((driving_times, avg_pl)), delimiter=",", header="Driving Time (ms), PL (counts)")

# ======= PLOT & SAVE FIGURE ===========
plt.figure(figsize=(8, 6))
plt.plot(driving_times, avg_pl, marker='o', linestyle='-', color='b', label="Averaged PL vs. Driving Time")
plt.xlabel('Driving Time (ms)')
plt.ylabel('PL (counts)')
plt.title('Average PL vs. Pulse Time (Rabi Oscillations)')
plt.grid(True)
plt.legend()
plt.savefig(os.path.join(save_path, "Rabi_Oscillations.png"))  # Save plot as PNG
plt.show()

print(f"Data and plot saved in: {save_path}")
