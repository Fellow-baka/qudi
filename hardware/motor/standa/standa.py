# -*- coding: utf-8 -*-

"""
This module controls compact rotation stage 8MPR16-1 with the help of
8SMC5-USB-B8-1 controller via USB interface.

You have to have some ximc libraries from standa.

80 steps = 1 degree of movement for 8MPR16-1.

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

    _libdir = ConfigOption('ximc_path',
                           'C:\\Users\\Eight\\PycharmProjects\\standa\\ximc-2.10.5\\ximc\\win64',
                           missing='error')

    _axis_label = ConfigOption('axis_label', 'phi', missing='error')

    _conv_factor = 80  # convert from steps to degrees
    _refresh_interval_ms = 20  # refresh interval in milliseconds used for wait_for_stop method

    _device_id = None
    _open_name = None

    def on_activate(self):
        """
        Connect to and initialize controller/motor.
        """
        devenum = lib.enumerate_devices(EnumerateFlags.ENUMERATE_PROBE)  # only non-network connected
        self._open_name = lib.get_device_name(devenum, 0)  # 0 == first device

        self.log.info(f'{lib.get_device_count(devenum)} motors are found.')

        self._device_id = lib.open_device(self._open_name)
        print(self._device_id)

    def on_deactivate(self):
        """
        Close device connection.
        """
        lib.close_device(byref(cast(self._device_id, POINTER(c_int))))

    def get_constraints(self):
        pass

    def move_rel(self, param_dict):
        """ Moves stage in given direction (relative movement) for asked amount of full steps.

        @param dict param_dict: dictionary, which passes all the relevant
                                parameters, which should be changed. Usage:
                                 {'axis_label': <the-abs-pos-value>}.
                                 'axis_label' must correspond to a label given
                                 to one of the axis.

        A smart idea would be to ask the position after the movement.

        @return int: error code (0:OK, -1:error)
        """
        if self._axis_label in param_dict:
            rel = param_dict[self._axis_label]
            lib.command_movr(self._device_id, int(rel*self._conv_factor), 0)
            self.wait_until_stop()
            pos = self.get_pos()
            return {self._axis_label: pos}
        return -1

    def move_abs(self, param_dict):
        """ Moves stage to absolute position (absolute movement)

        @param dict param_dict: dictionary, which passes all the relevant
                                parameters, which should be changed. Usage:
                                 {'axis_label': <the-abs-pos-value>}.
                                 'axis_label' must correspond to a label given
                                 to one of the axis.

        @return int: error code (0:OK, -1:error)
        """
        if self._axis_label in param_dict:
            abs = param_dict[self._axis_label]
            lib.command_move(self._device_id, int(abs * self._conv_factor), 0)
            self.wait_until_stop()
            pos = self.get_pos()
            return {self._axis_label: pos}
        return -1

    def abort(self, param_dict=None):
        """ Stops (soft stop) movement of the stage and gives position

        @return int: error code (0:OK, -1:error)
        """
        if self._axis_label in param_dict:
            lib.command_sstp(self._device_id)
            pos = self.get_pos()
            return {self._axis_label: pos}
        return -1

    def get_pos(self, param_list=None):
        """ Gets current position (in degrees) of the stage arms

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
            return x_pos.Position / self._conv_factor
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
        x_status = status_t()
        result = lib.get_status(self._device_id, byref(x_status))
        print("Result: " + repr(result))
        if result == Result.Ok:
            print("Status.Ipwr: " + repr(x_status.Ipwr))
            print("Status.Upwr: " + repr(x_status.Upwr))
            print("Status.Iusb: " + repr(x_status.Iusb))
            print("Status.Flags: " + repr(hex(x_status.Flags)))

        return [x_status.Ipwr, x_status.Upwr, x_status.Iusb, x_status.Flags, x_status.MoveSts]

    def calibrate(self, param_dict=None):
        """ Calibrates the stage.

        @param dict param_dict: param_list: optional, if a specific calibration
                                of an axis is desired, then the labels of the
                                needed axis should be passed in the param_list.
                                If nothing is passed, then all connected axis
                                will be calibrated.

        @return int: error code (0:OK, -1:error)

        After calibration the stage moves to home position which will be the
        zero point for the passed axis. The calibration procedure will be
        different for each stage.
        """
        # if self._axis_label in param_dict:
        lib.command_zero(self._device_id)
        # return -1

    def get_velocity(self, param_list=None):
        """ Gets the current velocity for all connected axes.

        @param dict param_list: optional, if a specific velocity of an axis
                                is desired, then the labels of the needed
                                axis should be passed as the param_list.
                                If nothing is passed, then from each axis the
                                velocity is asked.

        @return dict : with the axis label as key and the velocity as item.
        """
        # Create move settings structure
        mvst = move_settings_t()
        # Get current move settings from controller
        result = lib.get_move_settings(self._device_id, byref(mvst))
        # Print command return status. It will be 0 if all is OK
        return mvst.Speed

    def set_velocity(self, param_dict):
        """ Write new value for velocity.

        @param dict param_dict: dictionary, which passes all the relevant
                                parameters, which should be changed. Usage:
                                 {'axis_label': <the-velocity-value>}.
                                 'axis_label' must correspond to a label given
                                 to one of the axis.

        @return int: error code (0:OK, -1:error)
        """
        if self._axis_label in param_dict:
            mvst = move_settings_t()
            mvst.Speed = int(param_dict[self._axis_label])
            lib.set_move_settings(self._device_id, byref(mvst))
            return {self._axis_label: mvst.Speed}
        return -1

    def wait_until_stop(self):
        """
        Waits until movement is finished.
        """
        lib.command_wait_for_stop(self._device_id, self._refresh_interval_ms)

    def baka(self):
        x_status = edges_settings_t()
        result = lib.get_status(self._device_id, byref(x_status))
        print("Result: " + repr(result))
        return [x_status.BorderFlags, x_status.EnderFlags, x_status.LeftBorder, x_status.RightBorder]

    def get_info(self):
        """Prints bunch of information about library, controller, and stage."""

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

    def test_set_microstep_mode_full(self):
        print("\nSet microstep mode to 256")
        # Create engine settings structure
        eng = engine_settings_t()
        # Get current engine settings from controller
        result = lib.get_engine_settings(self._device_id, byref(eng))
        # Print command return status. It will be 0 if all is OK
        print("Read command result: " + repr(result))
        # Change MicrostepMode parameter to MICROSTEP_MODE_FRAC_256
        # (use MICROSTEP_MODE_FRAC_128, MICROSTEP_MODE_FRAC_64 ... for other microstep modes)
        eng.MicrostepMode = MicrostepMode.MICROSTEP_MODE_FULL
        # Write new engine settings to controller
        result = lib.set_engine_settings(self._device_id, byref(eng))
        # Print command return status. It will be 0 if all is OK
        print("Write command result: " + repr(result))

    def get_mode(self):
        # Create engine settings structure
        eng = engine_settings_t()
        # Get current engine settings from controller
        result = lib.get_engine_settings(self._device_id, byref(eng))
        # Print command return status. It will be 0 if all is OK
        print("Read command result: " + repr(eng.MicrostepMode))
        # # Change MicrostepMode parameter to MICROSTEP_MODE_FRAC_256
        # # (use MICROSTEP_MODE_FRAC_128, MICROSTEP_MODE_FRAC_64 ... for other microstep modes)
        # eng.MicrostepMode = MicrostepMode.MICROSTEP_MODE_FULL
        # # Write new engine settings to controller
        # result = lib.set_engine_settings(self._device_id, byref(eng))
        # # Print command return status. It will be 0 if all is OK
        # print("Write command result: " + repr(result))