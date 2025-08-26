import time
import numpy as np
import matplotlib.pyplot as plt
import TimeTagger
from datetime import datetime, timedelta

# === Settings ===
TAGGER_ADDRESS = 'localhost:41101'
CHANNELS = [4]  # Adjust to your PL channel(s)
MEASUREMENT_INTERVAL = 0.05  # seconds
TOTAL_DURATION = 5  # 2 days in seconds
LIVE_PLOT = False #Whether the graph should be shown live. If False, the plot will only be drawn and showed after the whole measurement is done. False works better for long measurements.

# === Initialize TimeTagger ===
tagger = TimeTagger.createTimeTaggerNetwork(TAGGER_ADDRESS)
countrate = TimeTagger.Countrate(tagger=tagger, channels=CHANNELS)
print("Live PL monitor started.")

# === Live Plot Setup ===
plt.ion()
fig, ax = plt.subplots()
line, = ax.plot([], [], marker='o', linestyle='-')
ax.set_xlabel("Time (HH:MM:SS)")
ax.set_ylabel("PL Count Rate (Hz)")
ax.set_title("Live PL Monitor")
plt.tight_layout()

# === Data Storage ===
timestamps = []
counts = []

# === Time Tracking ===
start_time = time.time()
end_time = start_time + TOTAL_DURATION

# === Live Monitoring Loop ===
measurement_count = 0
try:
    while time.time() < end_time:
        now_str = datetime.now().strftime("%H:%M:%S")
        data = countrate.getData()
        rate = sum(data)  # Sum if multiple channels

        # Skip first two measurements
        if measurement_count >= 0:
            timestamps.append(now_str)
            counts.append(rate)

            # Update plot
            if(LIVE_PLOT):
                line.set_xdata(np.arange(len(counts)))
                line.set_ydata(counts)
                ax.set_xticks(np.arange(len(timestamps))[::10])
                ax.set_xticklabels(timestamps[::10], rotation=45, ha='right')
                ax.relim()
                ax.autoscale_view()
                plt.pause(0.05)
            else:
                print("Count rate:", rate)

        measurement_count += 1
        time.sleep(MEASUREMENT_INTERVAL)

    print("\nMeasurement complete. 2-day monitoring finished.")

except KeyboardInterrupt:
    print("\nLive PL monitor manually stopped.")
finally:
    if not LIVE_PLOT:
        #Do one update in order to actually see something.
        line.set_xdata(np.arange(len(counts)))
        line.set_ydata(counts)
        ax.set_xticks(np.arange(len(timestamps))[::10])
        ax.set_xticklabels(timestamps[::10], rotation=45, ha='right')
        ax.relim()
        ax.autoscale_view()
        plt.pause(0.05)
    plt.ioff()
    plt.show()