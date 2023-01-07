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

def gen_lin_meshes_two_points(low_temp, high_temp, low_mesh, high_mesh, step, extra_temp):
    # calculate per-point expansion coefficient
    deltaT = high_temp - low_temp
    deltaZ = np.array(high_mesh) - np.array(low_mesh)
    coeffs = deltaZ / deltaT

    # linearly generate new meshes every <step> °C with some tolerance
    multiplier = pow(10, len(str(high_temp)))  # hacky way of ensuring consistent numbers -> integers only
    degrees = np.arange(low_temp * multiplier - extra_temp * multiplier, high_temp * multiplier + extra_temp * multiplier,
                        step * multiplier)
    degrees = degrees / multiplier

    new_meshes = {}

    for temperature in degrees:
        new_mesh_fc = low_mesh + coeffs * (temperature - low_temp)
        new_meshes[temperature] = new_mesh_fc.tolist()
        # compare mesh if similar temp as test mesh exists
        # if np.abs(temperature - TESTtemp) < step / 1.5:
        #     print("Testing! " + str(i) + " and " + str(TESTtemp))
        #     print("Absolute error:")
        #     error = np.array(TEST) - new_mesh_fc
        #     print(error)
        #     MSE = np.mean(np.power(error, 2))
        #     print("MSE: " + str(MSE))
        #     print("Maximum absolute error is " + str(np.round(np.max(np.abs(error)), 5)) + " mm (" + str(
        #         np.round(np.max(np.abs(error)) * 1000, 2)) + " microns)")
    return new_meshes


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


def gen_missing_lin_meshes_by_step(meshes, step, extra_temp):
    new_meshes = configparser.ConfigParser()
    timestamps = sorted(meshes.keys())
    for i in range(0, len(timestamps)-2, 1):
        low_measurement = meshes[timestamps[i]]["mesh"]
        high_measurement = meshes[timestamps[i + 1]]["mesh"]
        low_temp = round_by_step(meshes[timestamps[i]]["frame_temp"], step)
        high_temp = round_by_step(meshes[timestamps[i+1]]["frame_temp"], step)

        if new_meshes.has_section("bed_mesh " + str(low_temp)):
            # print("temp already exists", low_temp)
            continue

        if low_temp >= high_temp:
            # print("next temp is the same or lower", low_temp)
            continue

        if low_temp + step == high_temp:
            # print("high temp higher by step, just saving the current points", low_temp)
            add_bed_mesh(new_meshes, low_temp, low_measurement["points"], low_measurement["mesh_params"])

            continue

        new_points = gen_lin_meshes_two_points(low_temp, high_temp,low_measurement["points"], high_measurement["points"], step, 0)

        for temperature in new_points:
            add_bed_mesh(new_meshes, temperature, new_points[temperature], low_measurement["mesh_params"])

    return new_meshes


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


def gen_z_offsets_per_step(z_offsets, stepper, step, extra_temp, step_distance):
    new_z_offsets = {}
    new_z_tram_offsets = {}
    timestamps = sorted(z_offsets.keys())

    for i in range(0, len(timestamps) - 2, 1):
        low_z = z_offsets[timestamps[i]]["z_pos"][stepper]
        high_z = z_offsets[timestamps[i+1]]["z_pos"][stepper]
        low_temp = round_by_step(z_offsets[timestamps[i]]["frame_temp"], step)
        high_temp = round_by_step(z_offsets[timestamps[i+1]]["frame_temp"], step)
        if low_temp in new_z_offsets:
            # print("temp already exists", low_temp)
            continue

        if low_temp >= high_temp:
            # print("next temp is the same or lower", low_temp)
            continue

        new_offsets = gen_lin_z_offset_two_points(low_temp, high_temp, low_z, high_z, step, 0)
        new_z_offsets.update(new_offsets)
        if z_offsets[timestamps[i]]["z_pos_before_tram"]:
            low_z_tram = z_offsets[timestamps[i]]["z_pos"][stepper] - z_offsets[timestamps[i]]["z_pos_before_tram"][stepper]
            high_z_tram = z_offsets[timestamps[i+1]]["z_pos"][stepper] - z_offsets[timestamps[i+1]]["z_pos_before_tram"][stepper]
            new_tram_offsets = gen_lin_z_offset_two_points(low_temp, high_temp, low_z_tram, high_z_tram, step, 0)
            new_z_tram_offsets.update(new_tram_offsets)

    new_diff_offsets = generate_diff_offsets(new_z_offsets)

    new_offsets_in_mm = convert_to_mm(new_diff_offsets, step_distance)
    new_z_tram_offsets_in_mm = convert_to_mm(new_z_tram_offsets, step_distance)

    return new_offsets_in_mm, new_z_tram_offsets_in_mm


def debug_prints(z_offsets, new_offsets_in_mm, new_z_tram_offsets, stepper, step_distance):
    timestamps = sorted(z_offsets.keys())
    #fit_points_to_curve(z_offsets, step_distance)

    total_z_drift = 0
    for value in new_z_tram_offsets.values():
        total_z_drift -= value * step_distance
    print("z tram drift in mm: ", total_z_drift)

    total_z_drift = 0
    for value in new_offsets_in_mm.values():
        total_z_drift -= value
    print("z drift in mm: ", total_z_drift)

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
    source_file = args[1]
    dest_file = source_file[:-5] + '_NEW.cfg'
    step = float(args[2]) if len(args) > 2 else 0.1
    extra_temp = float(args[3]) if len(args) > 3 else 3

    # Read the thermal_quant_*.json
    with open(source_file, "r") as f:
        data = f.read()

    thermal_data = json.loads(data)
    step_distance = thermal_data["metadata"]["z_axis"]["step_dist"]
    steppers = list(thermal_data["hot_mesh"][list(thermal_data["hot_mesh"].keys())[0]]["z_pos"].keys())
    all_z_offsets = {}
    all_z_tram_offsets = {}
    for stepper in steppers:
        new_meshes = gen_missing_lin_meshes_by_step(thermal_data["hot_mesh"], step, extra_temp)
        new_offsets_in_mm, new_z_tram_offsets = gen_z_offsets_per_step(thermal_data["hot_mesh"], stepper, step,
                                                                       extra_temp, step_distance)
        debug_prints(thermal_data["hot_mesh"], new_offsets_in_mm, new_z_tram_offsets, stepper, step_distance)
        all_z_offsets[stepper] = new_offsets_in_mm
        if bool(new_z_tram_offsets):
            all_z_tram_offsets[stepper] = new_z_tram_offsets

    generate_z_offsets_plot(all_z_offsets, step_distance, "z offsets", source_file[:-5])
    generate_z_offsets_plot(all_z_tram_offsets, step_distance, "z tram offsets", source_file[:-5])

    print("variable_z_height_temps:", new_offsets_in_mm)
    print("")
    print("variable_last_trams:", gen_init_last_trams(all_z_tram_offsets))
    print("variable_z_trams_temps:", all_z_tram_offsets)
    if bool(all_z_tram_offsets):
        print("variable_enable_tram: 1")
    else:
        print("variable_enable_tram: 0")
    print("")
    print("variable_temp_min:", list(new_offsets_in_mm.keys())[0])
    print("variable_temp_max:", list(new_offsets_in_mm.keys())[-1])
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


if __name__ == "__main__":
    try:
        main(sys.argv)
    except KeyboardInterrupt:
        print("This is fine")











# def generate_z_offsets_plot(new_z_offsets, step_distance):
#     new_offsets_in_mm = []
#     first_z = list(new_z_offsets.values())[0]
#     for key, value in new_z_offsets.items():
#         new_offsets_in_mm.append((first_z - value) * step_distance)
#
#     plt.plot(list(new_z_offsets.keys()), new_offsets_in_mm)
#     plt.axis([list(new_z_offsets.keys())[0], list(new_z_offsets.keys())[-1], min(new_offsets_in_mm), max(new_offsets_in_mm)])
#     plt.xlabel('Temperatures [C]')
#     plt.ylabel('Z height [mm]')
#     plt.show()
#
#     return new_offsets_in_mm

# def fit_points_to_curve(new_z_offsets, step_distance):
#     from sklearn.svm import SVR
#     from sklearn.pipeline import make_pipeline
#     from sklearn.preprocessing import StandardScaler
#     new_offsets_in_mm = []
#     temps = []
#     first_z = list(new_z_offsets.values())[0]["mcu_z"]
#     for key, value in new_z_offsets.items():
#         low_z = value["mcu_z"]
#         new_offsets_in_mm.append((first_z - low_z) * step_distance)
#         temps.append(round_by_step(value["frame_temp"], 0.1))
#
#     plt.plot(temps, new_offsets_in_mm)
#     plt.axis([temps[0], temps[-1], new_offsets_in_mm[0], new_offsets_in_mm[-1]])
#     plt.xlabel('Temperatures [C]')
#     plt.ylabel('Z height [mm]')
#     plt.show()
#
#     print(new_offsets_in_mm)
#     regr = SVR(kernel = 'rbf')
#     x = np.array(temps)
#     y = np.array(new_offsets_in_mm)
#     x = x.reshape(-1, 1)
#     #y = y.reshape(1, -1)
#
#     result = regr.fit(x, y)
#
#     new_offsets = []
#     new_temps = []
#     for temp in np.arange(temps[0], temps[-1], 0.1):
#         new_offsets.append(result.predict([[temp]])[0])
#         new_temps.append(round_by_step(temp, 0.1))
#     print(new_temps, new_offsets)
#     plt.plot(new_temps, new_offsets)
#     plt.axis([new_temps[0], new_temps[-1], new_offsets[0], new_offsets[-1]])
#     plt.xlabel('Temperatures [C]')
#     plt.ylabel('Z height [mm]')
#     plt.show()
#
#     import statsmodels.api as sm
#     lowess = sm.nonparametric.lowess
#
#     z = lowess(y, x)
#     w = lowess(y, x, frac=1. / 3)
#     print(z,w)
