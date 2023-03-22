# FDC - Non-linear frame deformation calibration and compensation 2.1
### For 3D printers running Klipper

## Benefits
1. Dynamically readjusting your z height, bed mesh and tram the bed to make sure your first layer and every layer after that are perfect!
   1. The need to dynamically readjust z height is caused by the change in temperature of your frame
   2. Bimetallic frame components (Aluminum extrusion with steel linear rail) have different thermal expansion values
   3. This will make the bimetallic part deform as temperature raise up
2. Improve overall print time by eliminating the need to do a bed mesh before each print
3. Improve overall print time by enabling you to start the print without heat soaking

## Credits
* This project lies upon the hard work and dedication of [Deutherius](https://github.com/Deutherius), [alchemyEngine](https://github.com/alchemyEngine) and [tanaes]( https://github.com/tanaes)
* Although not involved in this specific project, most of the heavy lifting was done by them and most of the code in this project was writen by them.
* If there is someone I didn't credit it is only by mistake, please let me know!

## Why do you need it?
If you suffer from any of the following:
1) You've tried Virtual Gantry Backers and / or z_thermal_adjust and it made an improvement but didn't fully fix your problem
2) Nicely laid first layer, but second layer is too high / too low and looks like crap
3) Z offset changes between prints (too high / too low when the printer is heat soaked, but too low when it is not, or vice versa)
4) Bed mesh doesn't seem to work well on full plates
5) Have to heat soak the printer for hours just for the above problems to disappear

## I DON'T NEED IT!
* Run the measure script without committing to anything, see what you get, it's free

### Tired of doing a bed mesh before each print?
* If you do have some changes in your bed mesh that require doing a bed mesh before each print, you can eliminate it all together with FDC and start your print faster

## Why 2.0?
* I consider VGB + measure_thermal_behavior + Klipper's z_thermal_adjust to be v1.0
* 1.0 works well for a lot of people, but it's because the diff between the needed value and the generated linear value is pretty close.
* For printers that are bigger / hotter / weaker or just unlucky, linear compensation is not enough.
* As I learned while trying to fix my top layers, frame deformation isn't linear, and it's printer specific. 
* Furthermore, the need to measure the changes to the mesh and the changes to the z height where double the time it needs to be
* Hence - FDC:
  * Improved measure script
  * Improved generate thermal data scripts 
  * Dynamic and non-linear VGB (up to one mesh per 0.1C!)
  * Dynamic and non-linear z height adjust using Klipper's z_thermal_adjust module 
  * Dynamic and Non-linear tramming
  
* ![image](https://user-images.githubusercontent.com/6442378/206245509-7aa45f54-f028-4fa7-9ada-b1f44663651c.png)
* The picture shows the Z height changes per temperature, in the middle of the bed

## What changed in 2.1?
1. Dynamic un-tilt
2. Smooth generated data to seamlessly change z heights and bed meshes
3. Filter noise in generated data for even smoother operation (experimental)
   1. Will try to combat 1-5 microns changes that create small waves on flat layers
   
## Wait, Dynamic tramming?!
* Yes.
* Only applicable for auto tramming Z TILT at the moment
  * QGL can be supported - see details below
* But the bed mesh should take care of it!
  * Here why it doesn't - 
    * When you start the measuring phase -  measuring the deformation, the script automatically tram the bed (QGL / Z TILT) once at the beginning of the test (let's say at 25.1C)
    * All the bed meshes captured are relative to the current tramming
    * You inserted the results into the macro and off you go to happily start a print
    * But when you start a print, you tram the bed <b>again</b> before your start, now at a different temperature (Let's say 35.6C)
      * This new tramming (QGL / Z TILT) values will probably be different from the one you captured all the bed meshes in your measurement phase
    * Now all the bed meshes FDC is going to dynamically apply are relative to the tramming of a 25.1C frame
      * They are invalid, and will not affectively compensate the current deformation
* There are two scenarios where we won't need dynamic tramming:
  1. If you can guarantee that the tramming of your bed won't change ever and is identical to the one used in the measurement script (Which is unrealistic)
    * i.e. You don't tram the bed before each print - Manual tramming with screws or something else 
    * You disable auto tramming (QGL / Z TILT)
  2. You ran the script with TRAM_EVERYTIME = True and the graphs of your z steppers were pretty close
    * It should look something like this:
    * ![thermal_quant__2023-01-05_07-06-02z offsets](https://user-images.githubusercontent.com/6442378/211163204-e82433ef-5dc4-409c-9416-c13ad4436a07.png)
* So, if your output graphs looks like this:
  * ![thermal_quant__2023-01-04_09-36-42z offsets](https://user-images.githubusercontent.com/6442378/211163224-762f99aa-8520-4af7-9857-9d8abb18908b.png)
  * ![thermal_quant__2023-01-04_09-36-42z tram offsets](https://user-images.githubusercontent.com/6442378/211163250-0e12cb6d-9bb9-4076-b6ea-53d7c3d3ae13.png)
* Sorry buddy, You gonna need dynamic tramming

## Dynamic tramming development status
* Support z tilt 
  * quad_gantry_level is not supported at the moment because I don't have a quad printer
  * I don't see any big obstacle implementing support for it, but it does require a different implantation then z tilt
  * If anyone with a quad that ran TRAM_EVERYTIME = True and saw a need for it
    * And also want to help - contact me, so I can maybe try and figure out the impalement together
  * Another option is to hook me up with a quad printer
* The way it is implanted is by dynamically un-tilting the bed mesh itself using the modified bed_mesh.py klipper extra
  * It's super cool, and I invested too many hours on it
  * A new command that un-tilt and call z_thermal_adjust 
    * BED_MESH_PROFILE TILT_AND_LOAD={current_temp} CURRENT_TEMP={current_temp} REF_TEMP={ref_temp} stepper_z2=VAL2mm stepper_z=VAL0mm stepper_z1=VAL1mm
  * You can actually see the modified bed mesh in the heightmap mainsail page (without the metadata)
  * So bed mesh does take care of it?!?! well yes, now it does :) 
  
## What does it do?
1. Measure changes in bed mesh, z height and bed tramming for x time
2. Generate a cool graph that will show you the frame non-linear behavior
3. Generate a non-linear series of bed meshes and z height changes with linear changes in between data points
4. Interpolate them and filter noises to create a smooth graph
5. Dynamically adjust z height using the current z_thermal_adjust module to create a non-linear change
6. Dynamically switches bed meshes with the corresponding z height per temperature min, max and step
7. Dynamically tram your bed - control each z stepper motor independently and apply in real time tilt / QGL corrections(not yet) to keep the bed plane parallel to the gantry plane, the amount of adjustments is made according to the data that was captured in the measurement phase
8. Currently, only works in between the captured temps!
   1. So make sure the start really cold and time the test to finish with the hottest frame possible
   2. If you start the print with a lower temp then temp_min (or above temp_max) it will never change the z height
   3. If the frame temp goes above temp_max it will stop adjusting (but keep current adjustment)
   4. See roadmap

## What to expect?
* When I developed this solution, I modified my printer to make the deformation more prominent, or should I say - extreme
  * This enabled me to see exactly which solutions worked and which didn't
  * And if it worked in this extreme case,and be so precise  with just a few microns, it will surly work everywhere
* And work it did! it has been working flawless for some time now without hiccups
* It's not just great first layers, it's making sure every layer is beautifully buttery lushes and silky smooth
* Having said all that, you should know that there is a lot of guesstimations going on, and it can only be so accurate
  * There might be some "waves" on your flat layers, that's just the nature of the ever-changing frame and the script fighting it
  * Most of the time it will be smooth without any waves
  * When the waves accrue they should be minimal - 2-5 microns
  * If it's more than that and your layers become rough - too low / too high
    * Contact me please

### It WILL work for "linear deformed frames", so it's not about choosing between VBG and FDC, FDC is an improved version

## Roadmap 
1. Research different bed temps to see if there is a difference in the way things scale
   1. Implement multi bed temp support if needed
2. Generate non-linear equation to produce more points below and above captured temps
3. (Done) <s>Save results to disk for every new mesh</s> (Will now saves data if there is a keyboard interrupt or a runtime exception)
   1. <s>Currently, only saves at the end</s>

## Want to understand more?
Check out the following repositories:

[Gantry bowing-induced Z-offset correction through relative reference index](https://github.com/Deutherius/Gantry-bowing-induced-Z-offset-correction-through-relative-reference-index), to fix that inconsistent Z offset between heatsoaked and not-as-well heatsoaked printer (pairs nicely with virtual gantry backers, but do this one first)

[Virtual Gantry Backers](https://github.com/Deutherius/VGB), a dynamic mesh loading system that counteracts gantry bowing due to bimetallic thermal expansion of gantry members

[measure_thermal_behavior](https://github.com/alchemyEngine/measure_thermal_behavior), This script runs a series of defined homing and probing routines designed to characterize how the perceived Z height of the printer changes as the printer frame heats up. It does this by interfacing with the Moonraker API, so you will need to ensure you have Moonraker running.

# How to run 
## Prerequisite
### Bed mesh settings
0. The most important thing to know is that we need a point in the mesh to be in the center of the bed
   1. Without it the script won't work!
   2. Example: for 400 bed and 9,9 mesh point number 41 should be the middle of the bed (200x200)
1. Make sure that when you home Z, the PROBE (not nozzle) is at the center of the bed
   1. Sometimes the Z home doesn't take into account the probe location!
   2. You will have to fix it before you can continue
   3. If you are using RatOS, it's currently a known issue, here is the [fix](https://github.com/JiMcNulty/RatOS-configuration/pull/1/files)
2. Improve the speed of your probing and disable fade -  long probe sequences will capture a distorted bed mesh due to the fast warming up of the bed and frame
   1. For our purposes, a quick probe is usually sufficient. Below are some suggested settings:
   2. Keep in mind - There is a real problem in the start of the test where the frame temps rise up really fast, that causes the mesh we captured to be distorted if the mesh takes too long
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
3. <b>Mesh min/max</b> - find out the maximum you can probe with your current probe.
   1. your mesh min max should have the same offset.
      1. if you can reach x max of 280, then mesh min should be 20, if 250 then min is 50
4. <b>probe_count</b> - Have to be an odd number so will be left with a center point!
   1. (5, 5) / (7,7) / (9,9) are good options
5. <b>fade</b> - DISABLED!
6. <b>horizontal_move_z</b> - as low as possible without wreaking havoc
7. <b>z_positions</b> - our modified version of bed_mesh.py requires it.
   1. You only need it if you gonna use the TRAM_EVERYTIME = True feature
   2. It's the same as in z_tilt
8.  
```
[bed_mesh]
#######fast settings
speed: 500
horizontal_move_z: 5 # Should be more than your z_offset otherwise you will crash your nozzle!
fade_end: 0
mesh_min: 40,40
mesh_max:260,260
probe_count: 7,7
# For TRAM_EVERYTIME = True add this:
z_positions:
	0,0
	150,300
	300,0
```
9. When everything is set up correctly, you should have a 0.0 point in the middle of the array after a bed mesh
   1. Maybe not 0.0 but close to it
### z_thermal_adjust and other macros
1. Enable z_thermal_adjust in your config with temp_coeff=0
   1. This is where you define your frame sensor
2. Remove VBG if you have it
### Frame temperature sensor
1. X gantry on the opposite side of the X endstop at the end, touching the aluminum
   1. I know, it's a pain to find a way to install it, but it's the only place to put the sensor that will give accurate results
   2. Other places are a gamble, try it if you want - if it works, great, if it doesn't, you know why
   3. I used a cheap ATC Semitec 104GT-2 104NT-4-R025H42G Thermistor Cartridge
      1. You can use whatever you want as long as it touches the aluminum (and not the rail!)
      2. Make sure to cover i. so it will be isolated from the air
      3. I put it on my umbilical, with drag chains it might be easier
2. They way I did it is by sacrificing the last screw on my linear rail, push the thermistor to it and then shoved a piece of foam between the thermistor and the rail to have consistent good contact with the aluminum
![Foam](https://user-images.githubusercontent.com/6442378/219497026-756944da-1d53-4cb5-bfb1-fa79a2c94f15.jpg)
![Thermistor](https://user-images.githubusercontent.com/6442378/219496984-f9313234-1fd6-4051-85b0-19f689f36890.jpg)

### Python
 1. Python 3.7+ required (3.7+ has ordered dicts by default)
### Measure the deformation
 2. Edit measure_thermal_behavior.py and change the required parameters.
    1. It is recommended that the bed temp will be your working bed temp, if you print ABS and PETG and require different bed temps there is a chance that the meshes will be different. A more robust version that support multiple bed temps will be made in the future
    2. You want to let it run as much as possible until the printer frame temperature reaches the highest temp you've seen during a long print
    3. Currently, the script will not generate bed meshes and z heights above and below the captured temperatures due to its non-linear behavior
 3. <b>HOT_DURATION</b> - Recommended is 3 hours, you wanna catch them all (temperature data points)
 4. The bed and hotend temperature should be the exect one you print your first layer with
    1. If you print ABS and PETG, you currently need to do the test separately for each bed and hotend temperature
 5. <b>TRAM_EVERYTIME = True</b> - Only z_tilt printers are supported at the moment
    1. You want to set it to False if your printer is not supported
    2. And you want to then wait a day and run it again with True to see what your tilt situation is
 6. Make sure the frame is at the lowest temperature possible (like after it was idle for a night)
 7. If you have any fans / nevermore, start them after the first mesh is done
    1. Simulate the same wind you going to have in the enclosure during a print
    2. But give it a chance to capture the initial bed mesh
 8. NOTE: your X bowing is directly affected by the temperature of your X gantry
    1. So If you have a really long probe for example, the gantry will be higher from the bed then it would if it's printing the first layer, this 5mm-20mm will greatly affect the temperature of the gantry and the bowing.
    2. Part cooling fan cool the X gantry a bit, which will also reduce the bowing, and for the first layer there is no fan so take that into account (don't run the cooling fan during the test)
 9. 
```
git clone https://github.com/JiMcNulty/FDC
cd FDC

vim measure_thermal_behavior.py

nohup python3 measure_thermal_behavior.py 0.1 > out.txt &
tail -F out.txt
```
8. temperature_step = the step accuracy in degree Celsius, default to 0.1
9. restart without saving the config to remove all the bed meshes, they are there to save the progress as a recovery option, you don't need them if you got a full json file
10. If you saved the config that's alright, you can manually delete the meshes later
### Analyze and generate the deformation data
1. Take the output json file and run generate_FDC_meshes_z_heights.py json_file temperature_step --filter_noise / --no-filter_noise
   1. Run it on your local PC
   2. noise filter -  Enable filtering noise for a smoother graph. if the generated graphs don't look right, disable it (default: True)
2. 
```
python3 -m pip install -r requirements.txt
python3 generate_FDC_meshes_z_heights.py json_file 0.1 --filter_noise
```
3. While running, you will be shown some generated graphs and the smooth version of them
   1. It is shown to you so you can examine it
   2. If they don't look right to you i.e. the filtering and smoothing made it look like it doesn't follow the points - don't use the data
      1. Disable filtering and try again
      
### Install FDC on Klipper
9. Copy the generated mesh from the new cfg file and paste it at the bottom of your printer.cfg
10. Copy the macro FDC.cfg to the same folder as printer.cfg
11. Edit the macro with the min max temp, step and z_height_temps dictionary that was <b>printed when you ran the script</b>
    1. variable_precision is the precision of step. ie - 0.1 step is 1, 0.05 is 2, 1 is 0
12. Add [include FDC.cfg] to your printer.cfg
13. If applicable - replace bed_mesh.py
    1. /home/pi/klipper/klippy/extras/
    2. delete bed_mesh.pyc
14. Save
    1. Shutdown and start (to ensure the bed_mesh.py will load)
    2. Don't forget to check that it's still there after you do a Klipper update
    3. If you did a bed mesh every start print you can disable it, you won't need it anymore
15. <b>Reset and redo your z_offset!!!
    1. Fail to do so will risk crashing the nozzle!!</b>

### Running for the first time
1. Take note of your min and max temp, if you start a print when your frame temp is below or above it, the script won't run
   1. You will see a repeating error during printing
2. Bed meshes will be switched dynamically and seamless
3. z_themral_adjust will be adjusted in real time
   1. Turning it from a linear module to non-linear
    

### Contact
You can dm me on discord if you have any issues, i'm on the Voron and Ratrig servers
I don't want to put the user name here to avoid bot spamming, but search for the github link, and you'll find me (t.c)

### Shere your results!
* I'm really interested in what your deformation looks like ;)
* Really, i'm curious to see the graphs and all other data you've collected about the printer
* There might be other things that I will see that can improve the script!