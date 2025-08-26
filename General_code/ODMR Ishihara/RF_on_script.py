from qmi.core.context import QMI_Context
from rtcs.devices.rohde_schwarz.rs_base_signal_gen import RohdeSchwarz_Base
import time

try:
    # Instrument parameters
    instrument_name = "SMA100B"
    instrument_ip = "169.254.91.32"
    transport = f"tcp:{instrument_ip}:5025"

    rf_freq = 2.87e9
    rf_power = 15 #dBm
    context = QMI_Context("rs_signal_gen_context")
    context.start()
    sma100b = RohdeSchwarz_Base(context, instrument_name, transport)
    sma100b.open()

    print(f"Setting frequency to {rf_freq / 1e9:.4f} GHz")
    sma100b.set_frequency(rf_freq)
    sma100b.set_power(rf_power)
    sma100b.set_output_state(True)
    
    while(True):
        time.sleep(0.1)
except:
    pass

finally:
    sma100b.set_output_state(False)
    sma100b.close()