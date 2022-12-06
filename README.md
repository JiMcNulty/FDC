# FDC - Non-linear frame deformation calibration and compensation 2.0

## Credits
* This project lies upon the hard work and dedication of [Deutherius](https://github.com/Deutherius), [alchemyEngine](https://github.com/alchemyEngine) and [tanaes]( https://github.com/tanaes)
* Although not involved in this specific project, most of the heavy lifting was done by them and most of the code in this project was writen by them.
* If there is someone I didn't credit it is only by mistake, please let me know!

## Why do you need it?
If you suffer from any of the following:
1) Nicely laid first layer, but second layer is too high / too low and looks like crap
2) Z offset changes between prints (too high / too low when the printer is heat soaked, but too low when it is not, or vice versa)
3) Bed mesh doesn't seem to work well on full plates
4) Have to heat soak the printer for hours just for the above problems to disappear

## Why 2.0?
* I consider VGB + measure_thermal_behavior + klipper's z_thermal_adjust to be 1.0
* 1.0 works well for a lot of people, but it's because the diff between the needed value and the generated linear value is pretty close.
* For printers that are bigger / hotter / weaker or just unlucky, linear compensation is not enough.
* As I learned while trying to fix my top layers, frame deformation isn't linear, and it's printer specific. 
* Furthermore, the need to measure the changes to the mesh and the changes to the z height where double the time it needs to take
* Hence - FDC

## What does it do?
1. Measure changes in bed mesh and z height for x time
2. Generate a non-linear series of bed meshes and z height changes with linear changes in between data points
3. Dynamically adjust z height using the current z_thermal_adjust module to create a non-linear change
4. Dynamically switches bed meshes with the corresponding z height per temperature min, max and step

## Want to understand more?
Check out the following repositories:

[Gantry bowing-induced Z-offset correction through relative reference index](https://github.com/Deutherius/Gantry-bowing-induced-Z-offset-correction-through-relative-reference-index), to fix that inconsistent Z offset between heatsoaked and not-as-well heatsoaked printer (pairs nicely with virtual gantry backers, but do this one first)

[Virtual Gantry Backers](https://github.com/Deutherius/VGB), a dynamic mesh loading system that counteracts gantry bowing due to bimetallic thermal expansion of gantry members

[measure_thermal_behavior](https://github.com/alchemyEngine/measure_thermal_behavior), This script runs a series of defined homing and probing routines designed to characterize how the perceived Z height of the printer changes as the printer frame heats up. It does this by interfacing with the Moonraker API, so you will need to ensure you have Moonraker running.

## How to run 
0. You are going to need a frame temp sensor! has to physically touch the frame!
1. Enable z_thermal_adjust in your config with temp_coeff=0
2. Edit measure_thermal_behavior.py and change the required parameters.
   1. It is recommended that the bed temp will be your working bed temp, if you print ABS and PETG and require different bed temps there is a chance that the meshes will be different. A more robust version that support multiple bed temps will be made in the future
   2. You want to let it run as much as possible until the printer frame temperature reaches the highest temp you've seen during a long print
   3. Currently, the script will not generate bed meshes and z heights above and below the captured temperatures due to its non-linear behavior 
3. Make sure the frame is at the lowest temperature possible (like after it was idle for a night)
4. If you have any fans / nevermore, start them to simulate the same wind you going to have in the enclouser during a print
5. Run nohup python3 measure_thermal_behavior.py > out.txt &
6. Take the output json file and run generate_FDC_meshes_z_heights.py json_file temperature_step
7. Copy the generated mesh from the new cfg file and paste it at the bottom of your printer.cfg
8. Copy the macro FDC.cfg to the same folder as printer.cfg
9. Edit the macro with the min max temp, step and z_height_temps dictionary that was printed when you ran the script
   1. variable_precision is the precision of step. ie - 0.1 step is 1, 0.05 is 2, 1 is 0
10. Add [include FDC.cfg] to your printer.cfg
11. Restart