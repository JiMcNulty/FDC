# -*- coding: utf-8 -*-
import sys
import re
import numpy as np
import json
import configparser
import io
from collections import OrderedDict
import decimal


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
    dec_point = abs(decimal.Decimal(str(step)).as_tuple().exponent)
    new_meshes = configparser.ConfigParser()
    timestamps = sorted(meshes.keys())
    for i in range(0, len(timestamps)-2, 1):
        low_measurement = meshes[timestamps[i]]["mesh"]
        high_measurement = meshes[timestamps[i + 1]]["mesh"]
        low_temp = round(round(meshes[timestamps[i]]["frame_temp"] / step) * step, dec_point)
        high_temp = round(round(meshes[timestamps[i+1]]["frame_temp"] / step) * step, dec_point)

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


def gen_z_offsets_per_step(z_offsets, step, extra_temp, step_distance):
    dec_point = abs(decimal.Decimal(str(step)).as_tuple().exponent)
    new_z_offsets = OrderedDict()
    timestamps = sorted(z_offsets.keys())
    for i in range(0, len(timestamps) - 2, 1):
        low_z = z_offsets[timestamps[i]]["mcu_z"]
        high_z = z_offsets[timestamps[i+1]]["mcu_z"]
        low_temp = round(round(z_offsets[timestamps[i]]["frame_temp"] / step) * step, dec_point)
        high_temp = round(round(z_offsets[timestamps[i+1]]["frame_temp"] / step) * step, dec_point)
        if low_temp in new_z_offsets:
            print("temp already exists", low_temp)
            continue

        if low_temp >= high_temp:
            print("next temp is the same or lower", low_temp)
            continue

        new_offsets = gen_lin_z_offset_two_points(low_temp, high_temp, low_z, high_z, step, 0)
        new_z_offsets.update(new_offsets)

    new_offsets_in_mm = {}
    first_z = list(new_z_offsets.values())[0]
    for key, value in new_z_offsets.items():
        new_offsets_in_mm[key] = (first_z - value) * step_distance
        first_z = value

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


def main():
    source_file = sys.argv[1]
    dest_file = source_file[:-5] + '_NEW.cfg'
    step = float(sys.argv[2]) if len(sys.argv) > 2 else 0.1
    extra_temp = float(sys.argv[3]) if len(sys.argv) > 3 else 3

    # Read the thermal_quant_*.json
    with open(source_file, "r") as f:
        data = f.read()

    thermal_data = json.loads(data)
    new_meshes = gen_missing_lin_meshes_by_step(thermal_data["hot_mesh"], step, extra_temp)

    print("Writing file", dest_file)
    write_config(new_meshes, dest_file)

    new_offsets_in_mm = gen_z_offsets_per_step(thermal_data["hot_mesh"], step, extra_temp, thermal_data["metadata"]["z_axis"]["step_dist"])
    print("variable_z_height_temps:", new_offsets_in_mm)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("This is fine")