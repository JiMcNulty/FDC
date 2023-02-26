# FDC - Non-linear frame deformation compensation 2.1
### For 3D printers running Klipper

## What's this?
1. BI-Metallic 3D printer frames (aluminum + steel rail) will deform with temperature changes
2. This Klipper plugin will compensate for deformation in real time while printing

## What does it do?
1. Measure and generate the non-linear compensation profile
2. Dynamically adjust z height
3. Dynamically switches bed meshes
4. Dynamically tram your bed

# How to run 
## Prerequisite
### 1. Frame temperature sensor
1. X gantry on the opposite side of the X endstop at the end, touching the aluminum

### 2. Python
 1. Python 3.7+ required (3.7+ has ordered dicts by default)

### 3. z_thermal_adjust and other macros
1. Enable z_thermal_adjust in your config with temp_coeff=0
2. Remove VBG if you have it

### 4. Bed mesh settings
1. Adjust your bed mesh settings so that your mesh middle point is the center of the bed
2. Disable fade
3. Increase your bed mesh speed by reducing samples and increasing travel speed
4. 
```
[probe]
...
speed: 10.0
lift_speed: 15.0
samples: 1
samples_result: median
sample_retract_dist: 1.5
samples_tolerance: 0.02
samples_tolerance_retries: 1
```
```
[bed_mesh]
horizontal_move_z: 5
fade_end: 0
mesh_min: 40,40
mesh_max:260,260
probe_count: 7,7
# For TRAM_EVERYTIME = True add this:
z_positions:
	0,0
	150,300
	300,0
#######fast settings
speed: 500
```

## Run
### 1. Measure the frame deformation
1. Edit measure_thermal_behavior.py and change the required parameters.
2. <b>TRAM_EVERYTIME = True</b> - Only z_tilt printers are supported at the moment
3. Make sure the frame is at the lowest temperature possible (like after it was idle for a night)
4. If you have any fans / nevermore, start them after the first mesh is done
5. Run it on your PI

```
git clone https://github.com/JiMcNulty/FDC
cd FDC

vim measure_thermal_behavior.py

nohup python3 measure_thermal_behavior.py 0.1 > out.txt &
tail -F out.txt
```

### 2. Analyze and generate the compensation profile
```
generate_FDC_meshes_z_heights.py json_file 0.1 --filter_noise
```
      
### 3. Install FDC on Klipper
1. Copy the generated mesh from the new cfg file and paste it at the bottom of your printer.cfg
2. Copy the macro FDC.cfg to the same folder as printer.cfg
3. Edit the macro and copy the results from the console
4. Add [include FDC.cfg] to your printer.cfg
5. If applicable (TRAM_EVERYTIME = True)
```
    1. /home/pi/klipper/klippy/extras/
    2. replace bed_mesh.py
    3. delete bed_mesh.pyc
```
6. Save config (Klipper)
    1. Shutdown and start (to ensure the bed_mesh.py will load)


## * If you aren't convinced you need it or plan on using it, read the [Extended Readme](README_EXTENDED.md)



### Contact
You can dm me on discord if you have any issues, i'm on the Voron and Ratrig servers
I don't want to put the user name here to avoid bot spamming, but search for the github link, and you'll find me (t.c)

### Shere your results!
* I'm really interested in what your deformation looks like ;)
* Really, i'm curious to see the graphs and all other data you've collected about the printer
* There might be other things that I will see that can improve the script!

## Credits
* This project lies upon the hard work and dedication of [Deutherius](https://github.com/Deutherius), [alchemyEngine](https://github.com/alchemyEngine) and [tanaes]( https://github.com/tanaes)
* Although not involved in this specific project, most of the heavy lifting was done by them and most of the code in this project was writen by them.
* If there is someone I didn't credit it is only by mistake, please let me know!