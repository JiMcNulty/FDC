# -*- coding: utf-8 -*-
"""
Based on the projects of Deutherius
https://github.com/Deutherius/VGB
"""

import sys
import re
import numpy as np
import json
import configparser
import io
import decimal
import matplotlib.pyplot as plt
import os
from scipy.interpolate import make_interp_spline, BSpline
from scipy.signal import savgol_filter
import argparse

filter_noise = True

def add_bed_mesh(config, temperature, points, extra_params):
    mesh_template_name = "bed_mesh " + str(temperature)
    config.add_section(mesh_template_name)
    config.set(mesh_template_name, "version", str(1))
    points_formated = "\n"
    for line in points:
        lineChar = np.char.mod('%f', line)
        points_formated += str(', '.join(lineChar)) + "\n"

    config.set(mesh_template_name, "points", points_formated)
    for key in extra_params:
        config.set(mesh_template_name, key, str(extra_params[key]))


def add_bed_meshes(temp_list, mesh_list, mesh_params, step):
    new_meshes = configparser.ConfigParser()
    for i in range(len(temp_list)):
        add_bed_mesh(new_meshes, round_by_step(temp_list[i], step), mesh_list[i], mesh_params)

    return new_meshes


def get_middle_point_from_mesh(zpoints):
    if len(zpoints) % 2 == 0  or len(zpoints[0]) % 2 == 0:
        raise Exception("Mesh is supposed to have an odd number of probes! (5,5) (7,7) (9,9) and so on, current probe count (%s, %s)" % (len(zpoints), len(zpoints[0])))

    # 0.5 because of python's 3 round half to even
    middle_y = round(len(zpoints) / 2 + 0.5)
    middle_x = round(len(zpoints[0]) / 2 + 0.5)

    return zpoints[middle_y - 1][middle_x - 1]


def normal_mesh_to_point(zpoints, new_middle_z):
    return (np.array(zpoints) - new_middle_z).tolist()


def normal_mesh_to_zero_middle(zpoints, temp, tolerance=0.002):
    middle_z = get_middle_point_from_mesh(zpoints)
    # tolerance is just for the print
    if abs(middle_z) > tolerance:
        print("Normalizing mesh %s to middle zero, drift: %s" % (temp, middle_z))
    return normal_mesh_to_point(zpoints, middle_z)


def gen_lin_z_offset_two_points(low_temp, high_temp, low_z, high_z, step, extra_temp):
    # calculate per-point expansion coefficient
    deltaT = high_temp - low_temp
    deltaZ = high_z - low_z
    coeffs = deltaZ / deltaT

    # linearly generate new meshes every <step> °C with some tolerance
    multiplier = pow(10, len(str(high_temp)))  # hacky way of ensuring consistent numbers -> integers only
    degrees = np.arange(low_temp * multiplier - extra_temp * multiplier, high_temp * multiplier + extra_temp * multiplier,
                        step * multiplier)
    degrees = degrees / multiplier

    new_z_offsets = {}

    for temperature in degrees:
        new_z_offsets[temperature] = low_z + coeffs * (temperature - low_temp)

    return new_z_offsets


def precision(step):
    return abs(decimal.Decimal(str(step)).as_tuple().exponent)


def round_by_step(num, step):
    return round(round(num / step) * step, precision(step))


def generate_diff_offsets(new_z_offsets):
    new_diff_offsets = {}
    first_z = list(new_z_offsets.values())[0]
    for key, value in new_z_offsets.items():
        new_diff_offsets[key] = first_z - value
        first_z = value

    return new_diff_offsets


def convert_to_mm(new_z_offsets, step_distance):
    new_offsets_in_mm = {}
    for key, value in new_z_offsets.items():
        new_offsets_in_mm[key] = value * step_distance

    return new_offsets_in_mm


def generate_z_offsets_plot(all_offsets, step_distance, name, output_path):
    xmin = xmax = ymin = ymax = None
    for stepper, z_offset in all_offsets.items():
        if not bool(z_offset):
            print("No tramming data")
            return
        new_offsets_in_mm = []
        first_z = 0
        for key, value in z_offset.items():
            first_z = first_z + value
            new_offsets_in_mm.append(first_z)

        plt.plot(list(z_offset.keys()), new_offsets_in_mm, label=stepper)
        if not xmin or xmin > min(z_offset.keys()):
            xmin = min(z_offset.keys())
        if not xmax or xmax < max(z_offset.keys()):
            xmax = max(z_offset.keys())
        if not ymin or ymin > min(new_offsets_in_mm):
            ymin = min(new_offsets_in_mm)
        if not ymax or ymax < max(new_offsets_in_mm):
            ymax = max(new_offsets_in_mm)

    plt.axis([xmin, xmax, ymin, ymax])
    plt.xlabel('Temperatures [C]')
    plt.ylabel('Z height [mm]')
    plt.title(name)
    plt.legend()
    plt.savefig(output_path + name + '.png', dpi=200)
    # plt.show()
    plt.close()

    return plt


def convert_meshes_json_to_list(meshes, step):
    one_point = []
    temp_list = []
    timestamps = sorted(meshes.keys())
    for i in range(0, len(timestamps), 1):
        temp = round_by_step(meshes[timestamps[i]]["frame_temp"], step)
        if temp in temp_list:
            print("Temperature %s already exists, skipping" % temp)
            continue
        if temp_list and temp < max(temp_list):
            print("Temperature %s lower then max, skipping" % temp)
            continue
        measurement = meshes[timestamps[i]]["mesh"]
        # the frame warping continue even while bed probing, so we want to reset the zero
        measurement_points_normalized = normal_mesh_to_zero_middle(measurement["points"], temp)
        one_point.append(measurement_points_normalized)
        temp_list.append(temp)

    return one_point, temp_list


def filter_noise_list(y):
    if not filter_noise:
        return y
    new_y = savgol_filter(y, int(len(y)), 5)
    return new_y
    # import statsmodels.api as sm
    #
    # new_y = sm.nonparametric.lowess(new_y, new_x, frac=0.3)  # 30 % lowess smoothing
    #
    # return new_y[:, 1]


def interpolate_list(x,new_x, y):
    spl = make_interp_spline(x, y, k=3)  # type: BSpline
    new_y = spl(new_x)
    return filter_noise_list(new_y)


def gen_missing_meshes_by_step_interpolated(meshes, step):
    z_meshes_3d, temp_list = convert_meshes_json_to_list(meshes, step)
    steps_length = int(round((temp_list[-1] - temp_list[0]) / step))
    temp_list_new = np.linspace(temp_list[0], temp_list[-1], steps_length + 1)
    meshes_2d = np.moveaxis(z_meshes_3d, 0, -1).reshape(-1, len(z_meshes_3d))
    z_meshes_3d_interpolated = []
    for point_mesh in meshes_2d:
        z_smooth = interpolate_list(temp_list, temp_list_new, point_mesh)
        z_meshes_3d_interpolated.append(z_smooth)

    z_meshes_3d_interpolated = np.array(z_meshes_3d_interpolated)
    new_meshes = np.moveaxis(z_meshes_3d_interpolated.reshape(len(z_meshes_3d[0]), len(z_meshes_3d[0][0]), len(z_meshes_3d_interpolated[0])), -1, 0)
    mesh_params = meshes[list(meshes.keys())[0]]["mesh"]["mesh_params"]
    new_meshes_parsed = add_bed_meshes(temp_list_new, new_meshes, mesh_params, step)
    plt.plot(temp_list, meshes_2d[5], label=" before interpolation mesh(random point, 5)")
    plt.plot(temp_list_new, z_meshes_3d_interpolated[5], label=" interpolated mesh(random point, 5)")
    plt.legend()
    plt.show()
    return new_meshes_parsed


def gen_z_offsets_per_step_interpolated(z_offsets, stepper, step, step_distance):
    z_offset_list = []
    temp_list = []
    timestamps = sorted(z_offsets.keys())
    carry = z_offsets[timestamps[0]]["z_pos"][stepper]
    sum = 0
    for i in range(0, len(timestamps), 1):
        temp = round_by_step(z_offsets[timestamps[i]]["frame_temp"], step)
        if temp in temp_list:
            print("Temperature %s already exists, skipping" % temp)
            continue
        if temp_list and temp < max(temp_list):
            print("Temperature %s lower then max, skipping" % temp)
            continue
        z_offset = (carry - z_offsets[timestamps[i]]["z_pos"][stepper]) * step_distance
        carry = z_offsets[timestamps[i]]["z_pos"][stepper]
        sum = z_offset + sum
        z_offset_list.append(sum)
        temp_list.append(temp)

    steps_length = int(round((temp_list[-1] - temp_list[0]) / step))
    temp_list_new = np.linspace(temp_list[0], temp_list[-1], steps_length + 1)
    z_smooth = interpolate_list(temp_list, temp_list_new, z_offset_list)

    plt.plot(temp_list, z_offset_list, label=stepper + " before interpolation")
    plt.plot(temp_list_new, z_smooth, label=stepper + " interpolated")
    plt.legend()
    plt.show()

    prev_point=0
    new_offsets_in_mm = {}
    for i in range(len(z_smooth)):
        new_offsets_in_mm[round_by_step(temp_list_new[i], step)] = z_smooth[i] - prev_point
        prev_point = z_smooth[i]

    return new_offsets_in_mm


def gen_z_offsets_per_step(z_offsets, stepper, step, extra_temp, step_distance):
    new_z_tram_offsets = {}
    timestamps = sorted(z_offsets.keys())
    for i in range(0, len(timestamps) - 1, 1):
        low_temp = round_by_step(z_offsets[timestamps[i]]["frame_temp"], step)
        high_temp = round_by_step(z_offsets[timestamps[i+1]]["frame_temp"], step)
        if low_temp in new_z_tram_offsets:
            # print("temp already exists", low_temp)
            continue

        if low_temp >= high_temp:
            # print("next temp is the same or lower", low_temp)
            continue

        if z_offsets[timestamps[i]]["z_pos_before_tram"]:
            low_z_tram = z_offsets[timestamps[i]]["z_pos"][stepper] - z_offsets[timestamps[i]]["z_pos_before_tram"][stepper]
            high_z_tram = z_offsets[timestamps[i+1]]["z_pos"][stepper] - z_offsets[timestamps[i+1]]["z_pos_before_tram"][stepper]

            new_tram_offsets = gen_lin_z_offset_two_points(low_temp, high_temp, low_z_tram, high_z_tram, step, 0)
            new_z_tram_offsets.update(new_tram_offsets)

    new_z_tram_offsets_in_mm = convert_to_mm(new_z_tram_offsets, step_distance)

    return new_z_tram_offsets_in_mm


def debug_prints(z_offsets, new_offsets_in_mm, new_z_tram_offsets_in_mm, stepper, step_distance):
    timestamps = sorted(z_offsets.keys())
    # fit_points_to_curve(z_offsets, step_distance)
    total_z_tram_drift = 0
    for value in new_z_tram_offsets_in_mm.values():
        total_z_tram_drift += value
    print(stepper, "z tram drift in mm: ", total_z_tram_drift)

    total_z_drift = 0
    for key, value in new_offsets_in_mm.items():
        if key < 30.7 or key > 34.1:
            continue
        total_z_drift += value
    print("z drift in mm: ", total_z_drift)

    # total_z_drift = 0
    # for value in new_offsets_in_mm.values():
    #     total_z_drift += value
    # print("z drift in mm: ", total_z_drift)

    total_z_drift = 0
    for i in range(0, len(timestamps) - 2, 1):
        low_z = z_offsets[timestamps[i]]["z_pos"][stepper]
        high_z = z_offsets[timestamps[i+1]]["z_pos"][stepper]
        total_z_drift += (high_z - low_z) * step_distance
    print("debug - z drift in mm unfiltered: ", total_z_drift )
    print("debug - z drift in mm max-min: ", (z_offsets[timestamps[-1]]["z_pos"][stepper] - z_offsets[timestamps[0]]["z_pos"][stepper]) * step_distance)


def write_config(new_meshes, dest):
    output = io.StringIO()
    new_meshes.write(output)
    output.seek(0)
    # add new meshes to the new printer.cfg
    with open(dest, "w") as f:
        for lIndex in output:
            f.write("#*# ")
            f.write(lIndex)


def main(args):
    global filter_noise
    source_file = args[1]
    dest_file = source_file[:-5] + '_NEW.cfg'

    parser = argparse.ArgumentParser(description='Generate FDC data')
    parser.add_argument('--step', default=0.1, metavar='--S', type=float,
                        help='The resolution of the generated data, default is 0.1 which means a data point will'
                             ' be generated for every 0.1C temperature')
    parser.add_argument('--filter_noise', default=True, metavar='--FN', action=argparse.BooleanOptionalAction,
                        help='Enable filtering noise for a smoother graph. if the generated graphs don\'t look right, disable it')

    args_parser, unknown = parser.parse_known_args()
    step = args_parser.step
    filter_noise = args_parser.filter_noise

    # Read the thermal_quant_*.json
    with open(source_file, "r") as f:
        data = f.read()

    thermal_data = json.loads(data)
    step_distance = thermal_data["metadata"]["z_axis"]["step_dist"]
    tramming = thermal_data["metadata"]["z_axis"]["Tramming"]
    steppers = list(thermal_data["hot_mesh"][list(thermal_data["hot_mesh"].keys())[0]]["z_pos"].keys())
    new_meshes = gen_missing_meshes_by_step_interpolated(thermal_data["hot_mesh"], step)
    all_z_offsets = {}
    all_z_tram_offsets = {}

    for stepper in steppers:
        all_z_tram_offsets[stepper] = gen_z_offsets_per_step(thermal_data["hot_mesh"], stepper, step,0, step_distance)
        all_z_offsets[stepper] = gen_z_offsets_per_step_interpolated(thermal_data["hot_mesh"], stepper, step, step_distance)
        debug_prints(thermal_data["hot_mesh"], all_z_offsets[stepper], all_z_tram_offsets[stepper], stepper,step_distance)

    generate_z_offsets_plot(all_z_offsets, step_distance, "z offsets", source_file[:-5])

    if tramming:
        generate_z_offsets_plot(all_z_tram_offsets, step_distance, "z tram offsets", source_file[:-5])

    print("\n############################ COPY FROM HERE COPY FROM HERE COPY FROM HERE ####################################\n")
    print("variable_z_height_temps:", all_z_offsets["stepper_z"])
    print("")
    print("variable_last_trams:", gen_init_last_trams(all_z_tram_offsets))

    if tramming:
        print("variable_z_trams_temps:", all_z_offsets)
        print("variable_enable_tram: 1")
    else:
        print("variable_z_trams_temps:", gen_init_empty_z_trams(all_z_tram_offsets))
        print("variable_enable_tram: 0")
    print("")
    print("variable_temp_min:", list(all_z_offsets["stepper_z"].keys())[0])
    print("variable_temp_max:", list(all_z_offsets["stepper_z"].keys())[-1])
    print("variable_step:", step)
    print("variable_precision:", precision(step))

    print("\n\n")
    print("Writing file", dest_file)
    write_config(new_meshes, dest_file)
    print("\n\n")
    print("Copy the vars above to the FDC macro, and don't forget to copy the new bed meshes!")


def gen_init_last_trams(all_z_tram_offsets):
    if not bool(all_z_tram_offsets):
        return dict()
    init_last_trams = {}
    for stepper in all_z_tram_offsets.keys():
        init_last_trams[stepper] = 0
    return init_last_trams


def gen_init_empty_z_trams(all_z_tram_offsets):
    if not bool(all_z_tram_offsets):
        return dict()
    init_last_trams = {}
    for stepper in all_z_tram_offsets.keys():
        init_last_trams[stepper] = {}
    return init_last_trams


if __name__ == "__main__":
    try:
        main(sys.argv)
    except KeyboardInterrupt:
        print("This is fine")


