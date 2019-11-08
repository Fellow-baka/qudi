# -*- coding: utf-8 -*-

"""
This module controls standa motors with the use of 8SMC5-USB-B8-1 controller via USB interface.
Tested only with 8MPR16-1 compact rotational stages.

XIMC library from standa is needed to use this module. Only full-step mode is supported.

Some parameters (acceleration, deceleration, antiplay speed) are hardcoded,
since, most likely, they will not be changed.

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
    """
    Module for 8SMC5-USB-B8-1 controller for 8MPR16-1 (and maybe others, not tested) stages sold by standa.
    Using ximc libraries from standa.
    Connected with USB interface.

    Only non-network connected stages/controlles were tested.
    Only single axis was tested.
    """

    _modclass = 'standa_rotator'
    _modtype = 'hardware'

    # _libdir = ConfigOption('ximc_path',
    #                        'C:\\Users\\Eight\\PycharmProjects\\standa\\ximc-2.10.5\\ximc\\win64',
    #                        missing='error')

    _steps_per_degree = 80  # number of steps per degree, 80 for 8MPR16-1
    _refresh_interval_ms = 20  # refresh interval in milliseconds used for wait_for_stop method

    _first_axis_label = ConfigOption('first_axis_label', None, missing='warn')
    _second_axis_label = ConfigOption('second_axis_label', None, missing='warn')
    _third_axis_label = ConfigOption('third_axis_label', None, missing='warn')

    _first_device_id = None
    _second_device_id = None
    _third_device_id = None

    _first_open_name = None
    _second_open_name = None
    _third_open_name = None

    _device_dictionary = {}

    def on_activate(self):
        """
        Connect to and initialize controller/motor.
        """
        _devenum = lib.enumerate_devices(EnumerateFlags.ENUMERATE_PROBE)  # only non-network connected

        # TODO: refactor this boilerplate code later
        if self._first_axis_label is not None:
            self._first_open_name = lib.get_device_name(_devenum, 0)  # 0 == first device
            self._first_device_id = lib.open_device(self._first_open_name)
            self._device_dictionary[self._first_axis_label] = self._first_device_id
        if self._second_axis_label is not None:
            self._second_open_name = lib.get_device_name(_devenum, 1)
            self._second_device_id = lib.open_device(self._second_open_name)
            self._device_dictionary[self._second_axis_label] = self._second_device_id
        if self._third_axis_label is not None:
            self._third_open_name = lib.get_device_name(_devenum, 2)
            self._third_device_id = lib.open_device(self._third_open_name)
            self._device_dictionary[self._third_axis_label] = self._third_device_id

        self.log.info(f'{lib.get_device_count(_devenum)} motors are found.')

    def on_deactivate(self):
        """
        Close device connection.
        """
        lib.close_device(byref(cast(self._first_device_id, POINTER(c_int))))
        lib.close_device(byref(cast(self._second_device_id, POINTER(c_int))))
        lib.close_device(byref(cast(self._third_device_id, POINTER(c_int))))

    def get_constraints(self):
        pass

    def move_rel(self, param_dict):
        """ Moves stage in given direction (relative movement) for asked amount of degrees.

        @param dict param_dict: dictionary, which passes all the relevant
                                parameters, which should be changed. Usage:
                                 {'axis_label': <the-rel-pos-value>}.
                                 'axis_label' must correspond to a label given
                                 to one of the axis.

        TODO: A smart idea would be to ask the position after the movement.

        @return int: error code (0:OK, -1:error)
        """
        try:
            for axis_label in param_dict:
                angle = param_dict[axis_label]
                steps = int(angle * self._steps_per_degree)
                lib.command_movr(self._device_dictionary[axis_label], int(steps), 0)
            return 0
        except:
            self.log.error('Could not move (rel) motors for some reason')
            return -1

    def move_abs(self, param_dict):
        """ Moves stage to absolute position (absolute movement) in degrees

        @param dict param_dict: dictionary, which passes all the relevant
                                parameters, which should be changed. Usage:
                                 {'axis_label': <the-abs-pos-value>}.
                                 'axis_label' must correspond to a label given
                                 to one of the axis.

        @return int: error code (0:OK, -1:error)
        """
        try:
            for axis_label in param_dict:
                angle = param_dict[axis_label]
                steps = int(angle * self._steps_per_degree)
                lib.command_move(self._device_dictionary[axis_label], int(steps), 0)
            return 0
        except:
            self.log.error('Could not move (abs) motors for some reason')
            return -1

    def abort(self, param_dict=None):
        """ Stops (soft stop) movement of the stage for selected of all axes.

        @return int: error code (0:OK, -1:error)
        """
        if param_dict is None:
            for axis_label in self._device_dictionary:
                lib.command_sstp(self._device_dictionary[axis_label])
        else:
            for axis_label in param_dict:
                lib.command_sstp(self._device_dictionary[axis_label])
        return 0

    def get_pos(self, param_dict=None):
        """ Gets current position (in degrees) of the motors

        @param dict param_dict: optional, if a specific position of an axis
                                is desired, then the labels of the needed
                                axis should be passed in the param_list.
                                If nothing is passed, then from each axis the
                                position is asked.

        @return dict: with keys being the axis labels and item the current
                      position.
        """
        returned_dict = {}
        try:
            if param_dict is None:
                for axis_label in self._device_dictionary:
                    pos = get_position_t()
                    lib.get_position(self._device_dictionary[axis_label], byref(pos))
                    returned_dict[axis_label] = pos.Position / self._steps_per_degree
                return returned_dict
            else:
                for axis_label in param_dict:
                    pos = get_position_t()
                    lib.get_position(self._device_dictionary[axis_label], byref(pos))
                    returned_dict[axis_label] = pos.Position / self._steps_per_degree
                return returned_dict
        except:
            self.log.error('Could not get position of motors for some reason')
            return -1

    def get_status(self, param_list=None):
        """ Get the status of the position TODO: should do smth with that

        @param list param_list: optional, if a specific status of an axis
                                is desired, then the labels of the needed
                                axis should be passed in the param_list.
                                If nothing is passed, then from each axis the
                                status is asked.

        @return dict: with the axis label as key and the status number as item.
        """
        x_status = status_t()
        result = lib.get_status(self._second_device_id, byref(x_status))
        print("Result: " + repr(result))
        if result == Result.Ok:
            print("Status.Ipwr: " + repr(x_status.Ipwr))
            print("Status.Upwr: " + repr(x_status.Upwr))
            print("Status.Iusb: " + repr(x_status.Iusb))
            print("Status.Flags: " + repr(hex(x_status.Flags)))

        return [x_status.Ipwr, x_status.Upwr, x_status.Iusb, x_status.Flags, x_status.MoveSts]

    def calibrate(self, param_dict=None):
        """ Sets the current position as a zero for a selected or all the axes.

        @param dict param_dict: param_list: optional, if a specific calibration
                                of an axis is desired, then the labels of the
                                needed axis should be passed in the param_list.
                                If nothing is passed, then all connected axis
                                will be calibrated.

        @return int: error code (0:OK, -1:error)
        """
        try:
            if param_dict is None:
                for axis_label in self._device_dictionary:
                    lib.command_zero(self._device_dictionary[axis_label])
            else:
                for axis_label in param_dict:
                    lib.command_zero(self._device_dictionary[axis_label])
            return 0
        except:
            self.log.error('Could not set zero for motors for some reason')
            return -1

    def get_velocity(self, param_dict=None):
        """ Gets the current velocity for all connected axes in steps/s.

        @param dict param_dict: optional, if a specific velocity of an axis
                                is desired, then the labels of the needed
                                axis should be passed as the param_list.
                                If nothing is passed, then from each axis the
                                velocity is asked.

        @return dict : with the axis label as key and the velocity as item.
        """
        returned_dict = {}
        try:
            if param_dict is None:
                for axis_label in self._device_dictionary:
                    mvst = move_settings_t()
                    lib.get_move_settings(self._device_dictionary[axis_label], byref(mvst))
                    returned_dict[axis_label] = mvst.Speed
                return returned_dict
            else:
                for axis_label in param_dict:
                    mvst = move_settings_t()
                    lib.get_move_settings(self._device_dictionary[axis_label], byref(mvst))
                    returned_dict[axis_label] = mvst.Speed
                return returned_dict
        except:
            self.log.error('Could not get speed of the motors for some reason')
            return -1

    def set_velocity(self, param_dict):
        """ Sets a new value for velocity. Acceleration, Deceleration and Antiplay speed are hardcoded.

        @param dict param_dict: dictionary, which passes all the relevant
                                parameters, which should be changed. Usage:
                                 {'axis_label': <the-velocity-value>}.
                                 'axis_label' must correspond to a label given
                                 to one of the axis.

        @return int: error code (0:OK, -1:error)
        """
        try:
            for axis_label in param_dict:
                mvst = move_settings_t()
                mvst.Speed = int(param_dict[axis_label])
                mvst.Accel = 2000  # hardcoded values, recommended by standa for 8MPR16-1
                mvst.Decel = 4000
                mvst.AntiplaySpeed = 1000
                lib.set_move_settings(self._device_dictionary[axis_label], byref(mvst))
            return 0
        except:
            self.log.error('Could not get speed of the motors for some reason')
            return -1

    def wait_until_stop(self, param_dict=None):
        """
        Waits until movement is finished for a specific or for all axes.

        @param dict param_dict: optional, if a specific velocity of an axis
                                is desired, then the labels of the needed
                                axis should be passed as the param_list.
                                If nothing is passed, then from each axis the
                                velocity is asked.

        @return dict : with the axis label as key and the velocity as item.
        """
        try:
            if param_dict is None:
                for axis_label in self._device_dictionary:
                    lib.command_wait_for_stop(self._device_dictionary[axis_label], self._refresh_interval_ms)
            else:
                for axis_label in param_dict:
                    lib.command_wait_for_stop(self._device_dictionary[axis_label], self._refresh_interval_ms)
            return 0
        except:
            self.log.error('Could not wait for the motors stop for some reason')
            return -1

    def get_info(self):
        """Prints some information about library and active axes."""

        sbuf = create_string_buffer(64)
        lib.ximc_version(sbuf)
        print("XIMC library version: " + sbuf.raw.decode())
        print("Path to the library: " + libdir)
        print(f'{len(self._device_dictionary)} motors are found:')

        # list of open names
        t = [self._first_open_name, self._second_open_name, self._third_open_name]

        for axis_label in self._device_dictionary:
            if axis_label is not None:
                id = self._device_dictionary[axis_label]
                ximc_name = str(t[id-1])
                print("qudi axis label: '" + axis_label + "'; device id: " + str(id) + "; XIMC name: " + ximc_name)

    # TODO: update microstep stuff if needed
    def test_set_microstep_mode_full(self):
        print("\nSet microstep mode to 256")
        # Create engine settings structure
        eng = engine_settings_t()
        # Get current engine settings from controller
        result = lib.get_engine_settings(self._first_device_id, byref(eng))
        # Print command return status. It will be 0 if all is OK
        print("Read command result: " + repr(result))
        # Change MicrostepMode parameter to MICROSTEP_MODE_FRAC_256
        # (use MICROSTEP_MODE_FRAC_128, MICROSTEP_MODE_FRAC_64 ... for other microstep modes)
        eng.MicrostepMode = MicrostepMode.MICROSTEP_MODE_FULL
        # Write new engine settings to controller
        result = lib.set_engine_settings(self._first_device_id, byref(eng))
        # Print command return status. It will be 0 if all is OK
        print("Write command result: " + repr(result))

    def get_mode(self):
        # Create engine settings structure
        eng = engine_settings_t()
        # Get current engine settings from controller
        result = lib.get_engine_settings(self._second_device_id, byref(eng))
        # Print command return status. It will be 0 if all is OK
        print("Read command result: " + repr(eng.MicrostepMode))
        # # Change MicrostepMode parameter to MICROSTEP_MODE_FRAC_256
        # # (use MICROSTEP_MODE_FRAC_128, MICROSTEP_MODE_FRAC_64 ... for other microstep modes)
        # eng.MicrostepMode = MicrostepMode.MICROSTEP_MODE_FULL
        # # Write new engine settings to controller
        # result = lib.set_engine_settings(self._device_id, byref(eng))
        # # Print command return status. It will be 0 if all is OK
        # print("Write command result: " + repr(result))