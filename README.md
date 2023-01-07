# FDC - Non-linear frame deformation calibration and compensation 2.0
### For 3D printers running Klipper

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

## Why 2.0?
* I consider VGB + measure_thermal_behavior + Klipper's z_thermal_adjust to be v1.0
* 1.0 works well for a lot of people, but it's because the diff between the needed value and the generated linear value is pretty close.
* For printers that are bigger / hotter / weaker or just unlucky, linear compensation is not enough.
* As I learned while trying to fix my top layers, frame deformation isn't linear, and it's printer specific. 
* Furthermore, the need to measure the changes to the mesh and the changes to the z height where double the time it needs to be
* Hence - FDC:
  * Dynamic and non-linear VGB (up to one mesh per 0.1C!)
  * Dynamic and non-linear z height adjust using Klipper's z_thermal_adjust module 
  * Dynamic and Non-linear tramming
  

* ![image](https://user-images.githubusercontent.com/6442378/206245509-7aa45f54-f028-4fa7-9ada-b1f44663651c.png)
* The picture shows the Z height changes per temperature, in the middle of the bed

## Wait, Dynamic tramming?!
* Yes.
* But the bed mesh should take care of it!
  * Here why it doesn't - 
    * When you start measuring the deformation, you tram the bed at the beginning of the test (let's say at 25.1C)
    * All the bed meshes captured are relative to the current tramming
    * But when you start a print, you tram the bed again before your start, now at a different temperature (Let's say 35.6C)
    * Now all the bed meshes we are going to apply are relative to the tramming of a 25.1C frame
* There are two scenarios where we won't need dynamic tramming:
  * You can guarantee that the tramming of your bed won't change
    * i.e. You don't tram the bed before each print 
    * You don't have auto tramming (z_tilt or quad) and do manual tramming with screws or something else
  * You ran the script with TRAM_EVERYTIME = True and the graphs of your z steppers were pretty close
    * It should look something like this:
    * ![thermal_quant__2023-01-05_07-06-02z offsets](https://user-images.githubusercontent.com/6442378/211163204-e82433ef-5dc4-409c-9416-c13ad4436a07.png)
* So, if your output grapshs looks like this:
  * ![thermal_quant__2023-01-04_09-36-42z offsets](https://user-images.githubusercontent.com/6442378/211163224-762f99aa-8520-4af7-9857-9d8abb18908b.png)
  * ![thermal_quant__2023-01-04_09-36-42z tram offsets](https://user-images.githubusercontent.com/6442378/211163250-0e12cb6d-9bb9-4076-b6ea-53d7c3d3ae13.png)
* Sorry buddy, You gonna need dynamic tramming

## Dynamic tramming development status
* Support z tilt and quad_gantry_level
* Currently, the only way I found how to implement it is with FORCE_MOVE Klipper command
* It causes the head to pause for a moment when it can (when finishing a line)
  * The dynamic z_thermal_adjust doesn't do that
* I'm looking for better ways to implement it
  * Contact me if you have a better way!

### Tired of doing a bed mesh before each print?
* If you do have some changes in your bed mesh that require doing a bed mesh before each print, you can eliminate it all together with FDC and start your print faster

## What does it do?
1. Measure changes in bed mesh and z height for x time
2. Generate a cool graph that will show you the frame non-linear behavior
3. Generate a non-linear series of bed meshes and z height changes with linear changes in between data points
4. Dynamically adjust z height using the current z_thermal_adjust module to create a non-linear change
5. Dynamically switches bed meshes with the corresponding z height per temperature min, max and step
6. Dynamically tram your bed
7. Currently, only works in between the captured temps!
   1. So make sure the start really cold and time the test to finish with the hottest frame possible
   2. If you start the print with a lower temp then temp_min (or above temp_max) it will never change the z height
   3. If the frame temp goes above temp_max it will stop adjusting (but keep current adjustment)
   4. See roadmap

### It WILL work for "linear deformed frames", so it's not VBG or FDC, FDC is an improved version

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

## How to run 
0. You are going to need a frame temp sensor! has to physically touch the frame!
   1. Ideal place for it will be the middle of your X gantry (which is a real pain to do), Next best thing is the middle of your Y gantry above or below your linear rail (And touching the aluminum, not the rail) 
   2. Also python 3.7+ (3.7+ as ordered dicts by default)
   3. Improve the speed of your probing and disable fade -  long probe sequences will capture a distorted bed mesh due to the fast warming up of the bed and frame
      1. For our purposes, a quick probe is usually sufficient. Below are some suggested settings:
      2. Keep in mind - There is a real problem in the start of the test where the frame temps rise up really fast, that causes the mesh we captured to be distorted if the mesh takes too long

```
[probe]
...
speed: 10.0
lift_speed: 10.0
samples: 1
samples_result: median
sample_retract_dist: 1.5
samples_tolerance: 0.05
samples_tolerance_retries: 10

[bed_mesh]
...
speed: 500
horizontal_move_z: 10
fade_start: 1.0 
fade_end: 0
```
1. Enable z_thermal_adjust in your config with temp_coeff=0
   1. Remove VBG if you have it
2. Edit measure_thermal_behavior.py and change the required parameters.
   1. It is recommended that the bed temp will be your working bed temp, if you print ABS and PETG and require different bed temps there is a chance that the meshes will be different. A more robust version that support multiple bed temps will be made in the future
   2. You want to let it run as much as possible until the printer frame temperature reaches the highest temp you've seen during a long print
   3. Currently, the script will not generate bed meshes and z heights above and below the captured temperatures due to its non-linear behavior 
3. Make sure the frame is at the lowest temperature possible (like after it was idle for a night)
4. If you have any fans / nevermore, start them after the first mesh is done
   1. Simulate the same wind you going to have in the enclosure during a print
   2. But give it a chance to capture the initial bed mesh
5. NOTE: your X bowing is directly affected by the temperature of your X gantry
   1. So If you have a really long probe for example, the gantry will be higher from the bed then it would if it's printing the first layer, this 5mm-20mm will greatly affect the temperature of the gantry and the bowing.
   2. Part cooling fan cool the X gantry a bit, which will also reduce the bowing, and for the first layer there is no fan so take that into account
   3. Because it's hard and sometimes impossible to put the thermistor in the middle of the X gantry, we only have a guesstimation of it with the readings from the middle of the Y gantry, and that's why we want to reduce the things that create a large diff between the X and Y
6. Run nohup python3 measure_thermal_behavior.py temperature_step> out.txt &
   1. You can run tail -F out.txt to see the output prints in realtime  
   2. temperature_step = the step accuracy in degree Celsius, default to 0.1
7. restart without saving the config to remove all the bed meshes, they are there to save the progress as a recovery option, you don't need them if you got a full json file
   1. If you saved the config that's alright, you can manually delete the meshes later
8. Take the output json file and run generate_FDC_meshes_z_heights.py json_file temperature_step
   1. Run it on your local PC
9. Copy the generated mesh from the new cfg file and paste it at the bottom of your printer.cfg
10. Copy the macro FDC.cfg to the same folder as printer.cfg
11. Edit the macro with the min max temp, step and z_height_temps dictionary that was printed when you ran the script
    1. variable_precision is the precision of step. ie - 0.1 step is 1, 0.05 is 2, 1 is 0
12. Add [include FDC.cfg] to your printer.cfg
13. Save + Restart

### Contact
You can dm me on discord if you have any issues, i'm on the Voron and Ratrig servers
I don't want to put the user name here to avoid bot spamming, but search for the github link, and you'll find me (t.c)