# -*- coding: utf-8 -*-
"""
This file contains the Qudi logic class for performing polarisation dependence measurements.

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

from core.module import Connector
from logic.generic_logic import GenericLogic
from qtpy import QtCore


class PolarisationDepLogic(GenericLogic):
    """
    This logic module rotates polarisation and records signal as a function of angle.
    """

    _modclass = 'polarisationlogic'
    _modtype = 'logic'

    # declare connectors
    motor = Connector(interface='MotorInterface')

    signal_rotation_finished = QtCore.Signal()

    def on_activate(self):
        """ Initialisation performed during activation of the module.
        """

        self._rotator = self.motor()

    def on_deactivate(self):
        """
        Deinitialisation performed during deactivation of the module.
        """
        return

    def move_abs(self, param_dict):
        """ Rotate selected axis to absolute value.

        @param param_dict: dictionary containing axis and angle
        """
        self._rotator.move_abs(param_dict)
        self.wait_until_stop()
        self.signal_rotation_finished.emit()

    def move_rel(self, param_dict):
        """ Rotate selected axis by relative value.

        @param param_dict: dictionary containing axis and angle
        """
        self._rotator.move_rel(param_dict)

    def get_pos(self, param_dict=None):
        """ Gets the position of all or a specific axis.

        @param param_dict: dictionary containing axis and angle
        """
        return self._rotator.get_pos(param_dict)

    def calibrate(self, param_dict):
        """ Set zero for specified axis.

        @param param_dict: dictionary containing axis and angle
        """
        self._rotator.calibrate(param_dict)

    def get_number_of_axes(self):
        """ Get a number of active axes

        @return int: number of active axes
        """
        return len(self._rotator._device_dictionary)

    def get_axes_labels(self):
        """ Get a labels of the axes

        @return list: number of active axes
        """
        return list(self._rotator._device_dictionary.keys())

    def wait_until_stop(self, param_dict=None):
        """ Waits until all axes are stopped
        """
        self._rotator.wait_until_stop(param_dict)
