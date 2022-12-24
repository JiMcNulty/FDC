#!/usr/bin/env python3

"""
Based on the projects of alchemyEngine and tanaes
https://github.com/alchemyEngine/measure_thermal_behavior
https://github.com/tanaes/measure_thermal_behavior
"""

from datetime import timedelta, datetime
from os import error
from time import sleep
from requests import get, post
import re
import json
import sys
import decimal

######### META DATA #################
# For data collection organizational purposes only. Useful when sharing dataset.
USER_ID = ''            # e.g. Discord handle
PRINTER_MODEL = ''      # e.g. 'voron_v2_350'
HOME_TYPE = ''          # e.g. 'nozzle_pin', 'microswitch_probe', etc.
PROBE_TYPE = ''         # e.g. 'klicky', 'omron', 'bltouch', etc.
X_RAILS = ''            # e.g. '1x_mgn12_front', '2x_mgn9'
BACKERS = ''            # e.g. 'steel_x_y', 'Ti_x-steel_y', 'mgn9_y'
NOTES = ''              # anything note-worthy about this particular run,
                        #     no "=" characters
#####################################

######### CONFIGURATION #############
BASE_URL = 'http://127.0.0.1:7125'  # Printer URL (e.g. http://192.168.1.15)
                                    # leave default if running locally on Pi.

BED_TEMPERATURE = 80               # Bed target temperature for measurements.

HE_TEMPERATURE = 220                # Extruder temperature for measurements.

HOT_DURATION = 4                    # time after bed temp reached to continue
                                    # measuring [hours]

SOAK_TIME = 0                       # Time to wait for bed to heatsoak after
                                    # reaching BED_TEMPERATURE [minutes].
                                    # Recommended 0min

MEASURE_GCODE = 'G28 Z'             # G-code called on repeated Z measurements,
                                    # single line command or macro only.

TRAMMING_METHOD = "z_tilt" # One of: "quad_gantry_level", "z_tilt", or None

TRAMMING_CMD = "Z_TILT_ADJUST"  # Command for QGL/Z-tilt adjustments.
                                    # e.g. "QUAD_GANTRY_LEVEL", "Z_TILT_ADJUST",
                                    # "CUSTOM_MACRO", or None.

MESH_CMD = "BED_MESH_CALIBRATE"     # Command to measure bed mesh for gantry/bed
                                    # bowing/deformation measurements.

STOWABLE_PROBE_BEGIN_BATCH = " STOWABLE_PROBE_BEGIN_BATCH"  # Can be None.
STOWABLE_PROBE_END_BATCH = "STOWABLE_PROBE_END_BATCH"       # Can be None.

SAVE_CONFIG = "SAVE_CONFIG"

# If using the Z_THERMAL_ADJUST module. [True/False]
Z_THERMAL_ADJUST = True

# If using the FDC macro [True/False]
FDC_MACRO = True

# Full config section name of the frame temperature sensor (if any, can be None). E.g:
CHAMBER_SENSOR = "temperature_sensor chamber"
#CHAMBER_SENSOR = None

# Extra temperature sensors to collect. E.g:
# EXTRA_SENSORS = {"ambient": "temperature_sensor ambient",
#                  "mug1": "temperature_sensor coffee"}
# can be left empty if none to define.
EXTRA_SENSORS = {}
############### DO NOT CHANGE ###################
SAVE_MESH = "BED_MESH_PROFILE SAVE=<name>"  # Must insert the string <name>, it will be replaced with the current temp

MCU_Z_POS_RE = re.compile(r'(?P<mcu_z>(?<=stepper_z:)-*[0-9.]+)')

date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
DATA_FILENAME = "thermal_quant_%s_%s.json" % (USER_ID,
                                              date_str)
start_time = datetime.now() + timedelta(days=1)
index = 0
hot_data = {}
metadata = {}
BASE_URL = BASE_URL.strip('/')  # remove any errant "/" from the address


def gather_metadata():
    resp = get(BASE_URL + '/printer/objects/query?configfile').json()
    config = resp['result']['status']['configfile']['settings']

    # Gather Z axis information
    config_z = config['stepper_z']
    if 'rotation_distance' in config_z.keys():
        rot_dist = config_z['rotation_distance']
        steps_per = config_z['full_steps_per_rotation']
        micro = config_z['microsteps']
        if config_z['gear_ratio']:
            gear_ratio_conf = config_z['gear_ratio']           
            gear_ratio = float(gear_ratio_conf[0][0])
            for reduction in gear_ratio_conf[1:]:
                gear_ratio = gear_ratio/float(reduction)
        else:
            gear_ratio = 1.
        step_distance = (rot_dist / (micro * steps_per))/gear_ratio
    elif 'step_distance' in config_z.keys():
        step_distance = config_z['step_distance']
    else:
        step_distance = "NA"
    max_z = config_z['position_max']
    if 'second_homing_speed' in config_z.keys():
        homing_speed = config_z['second_homing_speed']
    else:
        homing_speed = config_z['homing_speed']

    # Organize
    meta = {
        'user': {
            'id': USER_ID,
            'printer': PRINTER_MODEL,
            'home_type': HOME_TYPE,
            'probe_type': PROBE_TYPE,
            'x_rails': X_RAILS,
            'backers': BACKERS,
            'notes': NOTES,
            'timestamp': datetime.now().strftime(
                "%Y-%m-%d_%H-%M-%S")
        },
        'script': {
            'version': "FDC 2.0",
            'data_structure': 3,
            'hot_duration': HOT_DURATION,
        },
        'z_axis': {
            'step_dist': step_distance,
            'max_z': max_z,
            'homing_speed': homing_speed
        }
    }
    return meta


def write_metadata(meta):
    with open(DATA_FILENAME, 'w') as dataout:
        dataout.write('### METADATA ###\n')
        for section in meta.keys():
            print(section)
            dataout.write("## %s ##\n" % section.upper())
            for item in meta[section]:
                dataout.write('# %s=%s\n' % (item, meta[section][item]))
        dataout.write('### METADATA END ###\n')


def query_axis_bounds(axis):
    resp = get(BASE_URL + '/printer/objects/query?configfile').json()
    config = resp['result']['status']['configfile']['settings']

    stepper = 'stepper_%s' % axis

    axis_min = config[stepper]['position_min']
    axis_max = config[stepper]['position_max']

    return(axis_min, axis_max) 


def query_xy_middle():
    resp = get(BASE_URL + '/printer/objects/query?configfile').json()
    config = resp['result']['status']['configfile']['settings']

    x_min = config['stepper_x']['position_min']
    x_max = config['stepper_x']['position_max']
    y_min = config['stepper_y']['position_min']
    y_max = config['stepper_y']['position_max']

    x_mid = x_max - (x_max-x_min)/2
    y_mid = y_max - (y_max-y_min)/2

    return [x_mid, y_mid]


def send_gcode_nowait(cmd=''):
    url = BASE_URL + "/printer/gcode/script?script=%s" % cmd
    post(url)
    return True


def send_gcode(cmd='', retries=1):
    url = BASE_URL + "/printer/gcode/script?script=%s" % cmd
    for i in range(retries):
        resp = post(url)
        try:
            success = 'ok' in resp.json()['result']
        except KeyError:
            print("G-code command '%s', failed. Retry %i/%i" % (cmd,
                                                                i+1,
                                                                retries))
            sleep(3)
        else:
            return True
    return False


def park_head_center():
    xy_coords = query_xy_middle()
    send_gcode_nowait("G1 Z10 F300")

    park_cmd = "G1 X%.1f Y%.1f F18000" % (xy_coords[0], xy_coords[1])
    send_gcode_nowait(park_cmd)


def park_head_high():
    xmin, xmax = query_axis_bounds('x')
    ymin, ymax = query_axis_bounds('y')
    zmin, zmax = query_axis_bounds('z')

    xpark = xmax
    ypark = ymax
    zpark = zmax * 0.8
    print(f"Parking toolhead at Z={zpark:.1f}mm for bed heating...", end='', flush=True)
    park_cmd = "G1 X%.1f Y%.1f Z%.1f F1000" % (xpark, ypark, zpark)
    send_gcode_nowait(park_cmd)


def set_bedtemp(t=0):
    temp_set = False
    cmd = 'SET_HEATER_TEMPERATURE HEATER=heater_bed TARGET=%.1f' % t
    temp_set = send_gcode(cmd, retries=3)
    if not temp_set:
        raise RuntimeError("Bed temp could not be set.")


def set_hetemp(t=0):
    temp_set = False
    cmd = 'SET_HEATER_TEMPERATURE HEATER=extruder TARGET=%.1f' % t
    temp_set = send_gcode(cmd, retries=3)
    if not temp_set:
        raise RuntimeError("HE temp could not be set.")


def gantry_leveled():
    if not TRAMMING_METHOD: return True
    url = BASE_URL + f'/printer/objects/query?{TRAMMING_METHOD}'
    resp = get(url).json()['result']
    return resp['status'][TRAMMING_METHOD]['applied']


def tram(retries=30):
    if not TRAMMING_CMD or not TRAMMING_METHOD:
        print("No tramming configurated. Skipping.")
        return True
    if gantry_leveled():
        print("Gantry/bed already trammed."
              "But we gonna tram it again because it might have changed since warm up and going up and down 80%")

    print("Tramming gantry/bed...", end='', flush=True)
    send_gcode_nowait(TRAMMING_CMD)
    for attempt in range(retries):
        if gantry_leveled():
            print("DONE", flush=True)
            return True
        else:
            print(".", end='')
            sleep(10)
    raise RuntimeError("Could not tram the gantry/bed!")


def clear_bed_mesh():
    mesh_cleared = False
    cmd = 'BED_MESH_CLEAR'
    mesh_cleared = send_gcode(cmd, retries=3)
    if not mesh_cleared:
        raise RuntimeError("Could not clear mesh.")


def take_bed_mesh():
    cmd = MESH_CMD
    send_gcode(cmd, retries=3)
    save_bed_mesh()
    mesh = query_bed_mesh()
    return mesh


def save_bed_mesh():
    global index
    current_temps = query_temp_sensors()
    cmd = SAVE_MESH.replace("<name>", "{:.1f}-{:.1f}-{}".format(current_temps["bed_target"], current_temps["frame_temp"], index))
    send_gcode(cmd)


def save_config():
    cmd = SAVE_CONFIG
    send_gcode_nowait(cmd)


def stowable_start_batch():
    if not STOWABLE_PROBE_BEGIN_BATCH:
        return
    cmd = STOWABLE_PROBE_BEGIN_BATCH
    send_gcode_nowait(cmd)


def stowable_end_batch():
    if not STOWABLE_PROBE_END_BATCH:
        return
    cmd = STOWABLE_PROBE_END_BATCH
    send_gcode_nowait(cmd)


def query_bed_mesh(retries=3):
    url = BASE_URL + '/printer/objects/query?bed_mesh'
    mesh_received = False
    for attempt in range(retries):
        # print('.', end='', flush=True)
        resp = get(url).json()['result']
        meshes = resp['status']['bed_mesh']
        if meshes['mesh_matrix'] != [[]]:
            try:
                mesh = meshes['profiles'][meshes['profile_name']]
                mesh_received = True
                break
            except KeyError:
                pass
        else:
            sleep(10)
    if not mesh_received:
        raise RuntimeError("Could not retrieve mesh")

    return mesh


def query_temp_sensors():
    extra_t_str = ''
    if CHAMBER_SENSOR:
        extra_t_str += '&%s' % CHAMBER_SENSOR
    if Z_THERMAL_ADJUST:
        extra_t_str += '&%s' % "z_thermal_adjust"
    if EXTRA_SENSORS:
        extra_t_str += '&%s' % '&'.join(EXTRA_SENSORS.values())

    base_t_str = 'extruder&heater_bed'
    url = BASE_URL + '/printer/objects/query?{0}{1}'.format(base_t_str,
                                                            extra_t_str)
    resp = get(url).json()['result']['status']
    try:
        chamber_current = resp[CHAMBER_SENSOR]['temperature']
    except KeyError:
        chamber_current = -180.
    try:
        frame_current = resp["z_thermal_adjust"]['temperature']
    except KeyError:
        frame_current = -180.

    extra_temps = {}
    if EXTRA_SENSORS:
        for sensor in EXTRA_SENSORS:
            try:
                extra_temps[sensor] = resp[EXTRA_SENSORS[sensor]]['temperature']
            except KeyError:
                extra_temps[sensor] = -180.

    bed_current = resp['heater_bed']['temperature']
    bed_target = resp['heater_bed']['target']
    he_current = resp['extruder']['temperature']
    he_target = resp['extruder']['target']
    return({'frame_temp': frame_current,
            'chamber_temp': chamber_current,
            'bed_temp': bed_current,
            'bed_target': bed_target,
            'he_temp': he_current,
            'he_target': he_target,
            **extra_temps})


def get_cached_gcode(n=1):
    url = BASE_URL + "/server/gcode_store?count=%i" % n
    resp = get(url).json()['result']['gcode_store']
    return resp


def query_mcu_z_pos():
    send_gcode(cmd='get_position', 5)
    gcode_cache = get_cached_gcode(n=1)
    for msg in gcode_cache:
        pos_matches = list(MCU_Z_POS_RE.finditer(msg['message']))
        if len(pos_matches) > 1:
            return int(pos_matches[0].group())
    return None


def heatsoak_bed():
    print(f"Waiting for bed to reach {BED_TEMPERATURE:.1f} degC...", end='', flush=True)
    temps = query_temp_sensors()
    while(temps['bed_temp'] < BED_TEMPERATURE-0.5):
        temps = query_temp_sensors()
        sleep(1)
    print("DONE", flush=True)
    start_soak = datetime.now()
    while(datetime.now() - start_soak < timedelta(minutes=SOAK_TIME)):
        remaining = SOAK_TIME*60 - (datetime.now() - start_soak).seconds
        print(f"Heatsoaking bed for {SOAK_TIME}min...[{int(remaining)}s remaining]", end='\r', flush=True)
        sleep(0.2)
    print(f"Heatsoaking bed for {SOAK_TIME}min...DONE"," "*20, flush=True)


def collect_datapoint(index):
    stamp = datetime.now().strftime("%Y/%m/%d-%H:%M:%S")
    mesh = take_bed_mesh()
    if not send_gcode(MEASURE_GCODE, 10):
        set_bedtemp()
        set_hetemp()
        err = 'MEASURE_GCODE (%s) failed. Stopping.' % MEASURE_GCODE
        raise RuntimeError(err)
    pos = query_mcu_z_pos()
    t_sensors = query_temp_sensors()
    datapoint = {
        stamp: {
            'mesh': mesh,
            'sample_index': index,
            'mcu_z': pos,
            **t_sensors
            }
    }
    return datapoint


def measure():
    global index, hot_data
    print('\r',' '*50,end='\r')
    print('Measuring (#%i)...' % index,end='',flush=True)
    data = collect_datapoint(index)
    hot_data.update(data)
    index += 1
    print('DONE', " "*20, flush=True)
    return data


def precision(step):
    return abs(decimal.Decimal(str(step)).as_tuple().exponent)


def round_by_step(num, step):
    return round(round(num / step) * step, precision(step))


def get_current_frame_temp_rounded(step):
    t_sensors = query_temp_sensors()
    return round_by_step(t_sensors['frame_temp'], step)


def save_results():
    # write output
    output = {'metadata': metadata,
              'hot_mesh': hot_data}

    print(f"Writing results to file {DATA_FILENAME}...", end='')
    with open(DATA_FILENAME, "w") as out_file:
        json.dump(output, out_file, indent=4, sort_keys=True, default=str)
    print("DONE")

def main(args):
    global start_time, hot_data, index, metadata
    step = float(args[2]) if len(args) > 2 else 0.1
    metadata = gather_metadata()

    stowable_start_batch()

    print("Starting!\nHoming...", end='', flush=True)
    # Home all
    if send_gcode('G28'):
        print("DONE", flush=True)
    else:
        raise RuntimeError("Failed to home. Aborted.")

    clear_bed_mesh()
    tram()

    print("Homing...", end='', flush=True)
    if send_gcode('G28'):
        print("DONE", flush=True)
    else:
        raise RuntimeError("Failed to home. Aborted.")

    if Z_THERMAL_ADJUST: send_gcode('SET_Z_THERMAL_ADJUST enable=0')
    if FDC_MACRO: send_gcode('SET_FDC ENABLE=0')

    print(f'Setting heater targets: Bed={BED_TEMPERATURE:.1f} degC; Tool={HE_TEMPERATURE:.1f} degC')
    set_bedtemp(BED_TEMPERATURE)
    set_hetemp(HE_TEMPERATURE)

    park_head_high()
    print("DONE", flush=True)

    heatsoak_bed()
    tram()
    start_time = datetime.now()

    print('Taking meshes measurements for the next %s min.' % (HOT_DURATION * 60), flush=True)
    last_temp = 0
    while (datetime.now() - start_time) < timedelta(hours=HOT_DURATION):
        current_temp = get_current_frame_temp_rounded(step)
        if current_temp <= last_temp:
            sleep(15)
            continue
        data = measure()
        last_temp = round_by_step(next(iter(data.values()))["frame_temp"], step)
        sleep(5)

    stowable_end_batch()

    print('Hot measurements complete!')
    set_bedtemp()

    save_results()

    set_bedtemp()
    set_hetemp()
    if Z_THERMAL_ADJUST: send_gcode('SET_Z_THERMAL_ADJUST enable=1')
    if FDC_MACRO: send_gcode('SET_FDC ENABLE=1')
    print('='*26, "ALL MEASUREMENTS COMPLETE!","="*26, sep='\n')


def debug():
    SOAK_TIME = 0.1
    start_soak = datetime.now()
    while(datetime.now() - start_soak < timedelta(minutes=SOAK_TIME)):
        remaining = SOAK_TIME*60 - (datetime.now() - start_soak).seconds
        print(f"Heatsoaking bed for {SOAK_TIME}min...[{int(remaining)}s remaining]", end='\r', flush=True)
        sleep(0.2)
    print(f"Heatsoaking bed for {SOAK_TIME}min...DONE"," "*20, flush=True)


if __name__ == "__main__":
    try:
        main(sys.argv)
    except (KeyboardInterrupt, RuntimeError) as error:
        save_results()
        set_bedtemp()
        set_hetemp()
        if Z_THERMAL_ADJUST: send_gcode('SET_Z_THERMAL_ADJUST enable=1')
        if FDC_MACRO: send_gcode('SET_FDC ENABLE=1')
        stowable_end_batch()
        print("\nStopped unexpectedly! Heaters disabled and saved the results.", error)
