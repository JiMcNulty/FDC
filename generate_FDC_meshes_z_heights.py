# -*- coding: utf-8 -*-
import sys
import re
import numpy as np
import json
import configparser
import io
from collections import OrderedDict
import decimal
import matplotlib.pyplot as plt

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
            print("temp already exists", low_temp)
            continue

        if low_temp >= high_temp:
            print("next temp is the same or lower", low_temp)
            continue

        if low_temp + step == high_temp:
            print("high temp higher by step, just saving the current points", low_temp)
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


def generate_diff_offsets(new_z_offsets, step_distance):
    new_offsets_in_mm = {}
    first_z = list(new_z_offsets.values())[0]
    for key, value in new_z_offsets.items():
        new_offsets_in_mm[key] = (first_z - value) * step_distance
        first_z = value

    return new_offsets_in_mm


def generate_z_offsets_plot(new_z_offsets, step_distance):
    new_offsets_in_mm = []
    first_z = list(new_z_offsets.values())[0]
    for key, value in new_z_offsets.items():
        new_offsets_in_mm.append((first_z - value) * step_distance)

    plt.plot(list(new_z_offsets.keys()), new_offsets_in_mm)
    plt.axis([list(new_z_offsets.keys())[0], list(new_z_offsets.keys())[-1], new_offsets_in_mm[0], new_offsets_in_mm[-1]])
    plt.xlabel('Temperatures [C]')
    plt.ylabel('Z height [mm]')
    plt.show()

    return new_offsets_in_mm


def gen_z_offsets_per_step(z_offsets, step, extra_temp, step_distance):
    new_z_offsets = OrderedDict()
    timestamps = sorted(z_offsets.keys())
    for i in range(0, len(timestamps) - 2, 1):
        low_z = z_offsets[timestamps[i]]["mcu_z"]
        high_z = z_offsets[timestamps[i+1]]["mcu_z"]
        low_temp = round_by_step(z_offsets[timestamps[i]]["frame_temp"], step)
        high_temp = round_by_step(z_offsets[timestamps[i+1]]["frame_temp"], step)
        if low_temp in new_z_offsets:
            print("temp already exists", low_temp)
            continue

        if low_temp >= high_temp:
            print("next temp is the same or lower", low_temp)
            continue

        new_offsets = gen_lin_z_offset_two_points(low_temp, high_temp, low_z, high_z, step, 0)
        new_z_offsets.update(new_offsets)

    new_offsets_in_mm = generate_diff_offsets(new_z_offsets, step_distance)
    generate_z_offsets_plot(new_z_offsets, step_distance)

    total_z_drift = 0
    for value in new_offsets_in_mm.values():
        total_z_drift -= value
    print("z drift in mm: ", total_z_drift)

    total_z_drift = 0
    for i in range(0, len(timestamps) - 2, 1):
        low_z = z_offsets[timestamps[i]]["mcu_z"]
        high_z = z_offsets[timestamps[i+1]]["mcu_z"]
        total_z_drift += (high_z - low_z) * step_distance
    print("debug - z drift in mm unfiltered: ", total_z_drift )
    print("debug - z drift in mm max-min: ", (z_offsets[timestamps[-1]]["mcu_z"] - z_offsets[timestamps[0]]["mcu_z"]) * step_distance)

    return new_offsets_in_mm


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
    new_meshes = gen_missing_lin_meshes_by_step(thermal_data["hot_mesh"], step, extra_temp)
    new_offsets_in_mm = gen_z_offsets_per_step(thermal_data["hot_mesh"], step, extra_temp, thermal_data["metadata"]["z_axis"]["step_dist"])

    print("\n\n")
    print("Writing file", dest_file)
    write_config(new_meshes, dest_file)
    print("\n\n")

    print("variable_z_height_temps:", new_offsets_in_mm)
    print("variable_temp_min:", list(new_offsets_in_mm.keys())[0])
    print("variable_temp_max:", list(new_offsets_in_mm.keys())[-1])
    print("variable_step:", step)
    print("variable_precision:", precision(step))


if __name__ == "__main__":
    try:
        main(sys.argv)
    except KeyboardInterrupt:
        print("This is fine")
