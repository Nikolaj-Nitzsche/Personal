from pylablib.devices import Attocube
import numpy as np
from datetime import datetime
import time
import json
import TimeTagger

def main() -> int:
    settings = {
        "save_folder": "/home/Documents/Nikolaj Nitzsche/Cryo/2D-Scans/",
        "x_steps": 5,
        "y_steps": 5,
        "z_steps": 50,
        "dwell_time": 2e11,  # picoseconds
        "num_measurements": 100,
        "min_freq": 2.8e9,
        "max_freq": 2.94e9,
        "num_sweeps": 1,
        "x1": 4833.33e-6,  # mm
        "y1": 4000e-6, #--------------------------------------
        "z1": 4000e-6, #--------------------------------------
        "x2": 200e-6,
        "y2": 200e-6,
        "z2": 200e-6,
        "measurement_type": "move",
        "steps_to_autozero": 1000,
        "triangle": None,
    }


    # Create TimeTagger for measurement
    tagger = TimeTagger.createTimeTaggerNetwork('localhost:41101')
    #tagger = TimeTagger.createTimeTaggerNetwork('ip:port')
    countrate = TimeTagger.Countrate(tagger=tagger, channels=[5])
    
    
    # Initialize Attocube ANC350
    atc = Attocube.ANC350()
    atc.set_frequency(0, 800)
    atc.set_frequency(1, 800)
    atc.set_frequency(2, 800)
    atc.set_voltage(0, 30)
    atc.set_voltage(1, 30)
    atc.set_voltage(2, 40)
    
    xmove = settings["x1"]
    ymove = settings["y1"]
    zmove = settings["z1"]
    xmove_back = settings["x2"]
    ymove_back = settings["y2"]
    zmove_back = settings["z2"]
    
    atc.move_to(0, xmove)
    atc.move_to(1, ymove)
    atc.move_to(2, zmove)
    print(f"moving to x={xmove:.6f} m")
    print(f"moving to y={ymove:.6f} m")
    print(f"moving to z={zmove:.6f} m")
    atc.wait_move(0)
    atc.wait_move(1)
    atc.wait_move(2)
    time.sleep(5)
    #print(f"Arrived at y ={ymove:.6f} m and z ={zmove:.6f} m")
    #atc.stop(1)
    #atc.stop(2)
    
    atc.move_to(0, xmove_back)
    atc.move_to(1, ymove_back)
    atc.move_to(2, zmove_back)
    print(f"moving to x={xmove_back:.6f} m")
    print(f"moving to y={ymove_back:.6f} m")
    print(f"moving to z={zmove_back:.6f} m")
    atc.wait_move(0)
    atc.wait_move(1)
    atc.wait_move(2)
    
    atc.stop(0)
    atc.stop(1)
    atc.stop(2)
    
    #print(f"Moved to: x={xpos:.6f} m, PL count: {rate:.2f}")
    
    #try:
    #    while True:
    #        # Perform measurement
    #        countrate.startFor(settings["dwell_time"])
    #        countrate.waitUntilFinished()
    #        rate = countrate.getData()[0]
    #        print(f"PL count: {rate:.2f}")
    #        time.sleep(0.1)  # Small delay to avoid excessive looping
   # 
   # except KeyboardInterrupt:
   #     print("Measurement stopped by user.")
    
    #return 0

if __name__ == "__main__":
    exitcode = main()