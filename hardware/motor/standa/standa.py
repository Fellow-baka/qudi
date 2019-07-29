# -*- coding: utf-8 -*-

"""
This module controls compact rotation stage 8MPR16-1 with the help of
8SMC5-USB-B8-1 controller via USB interface.

You have to have some ximc libraries from standa.

Qudi is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Qudi is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Qudi. If not, see <http://www.gnu.org/licenses/>.

Copyright (c) the Qudi Developers. See the COPYRIGHT.txt file at the
top-level directory of this distribution and at <https://github.com/Ulm-IQO/qudi/>
"""

from ctypes import *
import time
import os
import sys
import platform
import tempfile
import re
import urllib.parse

from collections import OrderedDict

from core.module import Base, ConfigOption
from interface.motor_interface import MotorInterface

# TODO: how to import this before or after? Right now the path is hardcoded
libdir = 'C:\\Users\\Eight\\PycharmProjects\\standa\\ximc-2.10.5\\ximc\\win64'
os.environ["Path"] = libdir + ";" + os.environ["Path"]  # add dll

from .pyximc import *


class MotorStanda(Base, MotorInterface):

    _modclass = 'standa_rotator'
    _modtype = 'hardware'

    _libdir = ConfigOption('ximc_path',
                           'C:\\Users\\Eight\\PycharmProjects\\standa\\ximc-2.10.5\\ximc\\win64',
                           missing='error')
    # os.environ["Path"] = _libdir + ";" + os.environ["Path"]  # add dll

    _device_id = None
    _open_name = None

    def on_activate(self):
        """
        Connect to and initialize controller/motor.
        """
        sbuf = create_string_buffer(64)
        lib.ximc_version(sbuf)
        print("Library version: " + sbuf.raw.decode())

        devenum = lib.enumerate_devices(EnumerateFlags.ENUMERATE_PROBE)  # only non-network connected
        print("Device enum handle: " + repr(devenum))
        print("Device enum handle type: " + repr(type(devenum)))

        dev_count = lib.get_device_count(devenum)
        print("Device count: " + repr(dev_count))

        controller_name = controller_name_t()
        for dev_ind in range(0, dev_count):
            enum_name = lib.get_device_name(devenum, dev_ind)
            result = lib.get_enumerate_device_controller_name(devenum, dev_ind, byref(controller_name))
            if result == Result.Ok:
                print("Enumerated device #{} name (port name): ".format(dev_ind) + repr(
                    enum_name) + ". Friendly name: " + repr(controller_name.ControllerName) + ".")

        self._open_name = lib.get_device_name(devenum, 0)

        print(self._open_name)

        if type(self._open_name) is str:
            self._open_name = self._open_name.encode()

        self._device_id = lib.open_device(self._open_name)
        print(self._device_id)

    def on_deactivate(self):
        lib.close_device(byref(cast(self._device_id, POINTER(c_int))))

    def get_constraints(self):
        pass

    def move_rel(self, param_dict):
        """ Moves stage in given direction (relative movement)

        @param dict param_dict: dictionary, which passes all the relevant
                                parameters, which should be changed. Usage:
                                 {'axis_label': <the-abs-pos-value>}.
                                 'axis_label' must correspond to a label given
                                 to one of the axis.

        A smart idea would be to ask the position after the movement.

        @return int: error code (0:OK, -1:error)
        """
        pass

    def move_abs(self, param_dict):
        """ Moves stage to absolute position (absolute movement)

        @param dict param_dict: dictionary, which passes all the relevant
                                parameters, which should be changed. Usage:
                                 {'axis_label': <the-abs-pos-value>}.
                                 'axis_label' must correspond to a label given
                                 to one of the axis.

        @return int: error code (0:OK, -1:error)
        """
        pass

    def abort(self):
        """ Stops movement of the stage

        @return int: error code (0:OK, -1:error)
        """
        pass

    def get_pos(self, param_list=None):
        """ Gets current position of the stage arms

        @param list param_list: optional, if a specific position of an axis
                                is desired, then the labels of the needed
                                axis should be passed in the param_list.
                                If nothing is passed, then from each axis the
                                position is asked.

        @return dict: with keys being the axis labels and item the current
                      position.
        """
        x_pos = get_position_t()
        result = lib.get_position(self._device_id, byref(x_pos))
        if result == Result.Ok:
            return [x_pos.Position, x_pos.uPosition]
        else:
            pass

    def get_status(self, param_list=None):
        """ Get the status of the position

        @param list param_list: optional, if a specific status of an axis
                                is desired, then the labels of the needed
                                axis should be passed in the param_list.
                                If nothing is passed, then from each axis the
                                status is asked.

        @return dict: with the axis label as key and the status number as item.
        """
        pass

    def calibrate(self, param_list=None):
        """ Calibrates the stage.

        @param dict param_list: param_list: optional, if a specific calibration
                                of an axis is desired, then the labels of the
                                needed axis should be passed in the param_list.
                                If nothing is passed, then all connected axis
                                will be calibrated.

        @return int: error code (0:OK, -1:error)

        After calibration the stage moves to home position which will be the
        zero point for the passed axis. The calibration procedure will be
        different for each stage.
        """
        pass

    def get_velocity(self, param_list=None):
        """ Gets the current velocity for all connected axes.

        @param dict param_list: optional, if a specific velocity of an axis
                                is desired, then the labels of the needed
                                axis should be passed as the param_list.
                                If nothing is passed, then from each axis the
                                velocity is asked.

        @return dict : with the axis label as key and the velocity as item.
        """
        pass

    def set_velocity(self, param_dict):
        """ Write new value for velocity.

        @param dict param_dict: dictionary, which passes all the relevant
                                parameters, which should be changed. Usage:
                                 {'axis_label': <the-velocity-value>}.
                                 'axis_label' must correspond to a label given
                                 to one of the axis.

        @return int: error code (0:OK, -1:error)
        """
        pass

# sbuf = create_string_buffer(64)
# lib.ximc_version(sbuf)
# print("Library version: " + sbuf.raw.decode())
#
# devenum = lib.enumerate_devices(EnumerateFlags.ENUMERATE_PROBE)  # only non-network connected
# print("Device enum handle: " + repr(devenum))
# print("Device enum handle type: " + repr(type(devenum)))
#
# dev_count = lib.get_device_count(devenum)
# print("Device count: " + repr(dev_count))
#
# controller_name = controller_name_t()
# for dev_ind in range(0, dev_count):
#     enum_name = lib.get_device_name(devenum, dev_ind)
#     result = lib.get_enumerate_device_controller_name(devenum, dev_ind, byref(controller_name))
#     if result == Result.Ok:
#         print("Enumerated device #{} name (port name): ".format(dev_ind) + repr(enum_name) + ". Friendly name: " + repr(controller_name.ControllerName) + ".")
#
# open_name = None
# open_name = lib.get_device_name(devenum, 0)
#
# print(open_name)
#
# if type(open_name) is str:
#     open_name = open_name.encode()
#
# print(open_name)
#
# device_id = lib.open_device(open_name)
#
# print(device_id)
#
# print("\nRead position")
# x_pos = get_position_t()
# result = lib.get_position(device_id, byref(x_pos))
# print("Result: " + repr(result))
# if result == Result.Ok:
#     print("Position: {0} steps, {1} microsteps".format(x_pos.Position, x_pos.uPosition))
# print(x_pos.Position, x_pos.uPosition)
# print(x_pos.Position)

# lib.command_move(device_id, 2000, 0)
