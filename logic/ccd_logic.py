# -*- coding: utf-8 -*-
"""
Buffer for simple data

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

import numpy as np
import time

from core.module import Connector
from logic.generic_logic import GenericLogic
from qtpy import QtCore


class CCDLogic(GenericLogic):
    """ Logic module agreggating multiple hardware switches.
    """
    _modclass = 'ccd'
    _modtype = 'logic'

    simpledata = Connector(interface='SimpleDataInterface')

    sigRepeat = QtCore.Signal()
    sigAquired = QtCore.Signal()

    sigUpdateDisplay = QtCore.Signal()
    sigAcquisitionFinished = QtCore.Signal()
    sigVideoFinished = QtCore.Signal()

    # _data = None
    _focus_exposure = 1.
    _acquisition_exposure = 10.
    _gain = 1.
    _mode = "1D"  # dummy value to distinguish between spectra/image
    _roi = []

    def on_activate(self):
        """ Prepare logic module for work.
        """
        self._hardware = self.simpledata()
        self.resolution_x = self._hardware.get_size()[0]
        self.resolution_y = self._hardware.get_size()[1]
        self._roi = [0, self.resolution_x, 1, 0, self.resolution_y, 1]
        self.stopRequest = False
        self.buf_spectrum = np.zeros((1, self.resolution_x))
        self.sigRepeat.connect(self.focus_loop, QtCore.Qt.QueuedConnection)

    def on_deactivate(self):
        """ Deactivate module.
        """
        self.stop_focus()

    def start_single_acquisition(self):
        """Get single spectrum from hardware"""
        # self.module_state.lock()
        self._hardware._exposure = self._acquisition_exposure
        self._hardware.start_single_acquisition()
        self.buf_spectrum = self._hardware.get_acquired_data()
        self.sigUpdateDisplay.emit()
        self.sigAcquisitionFinished.emit()

        # self.module_state.unlock()

    def start_focus(self):
        """ Start measurement: zero the buffer and call loop function."""
        self._hardware._exposure = self._focus_exposure
        self.module_state.lock()
        self.sigRepeat.emit()

    def stop_focus(self):
        """ Ask the measurement loop to stop. """
        self.stopRequest = True
        self.sigAcquisitionFinished.emit()

    def focus_loop(self):
        """ Continuously read data from camera """
        if self.stopRequest:
            self.stopRequest = False
            self.module_state.unlock()
            return

        self.buf_spectrum = self._hardware.get_acquired_data()
        self.sigRepeat.emit()

    def set_parameter(self, par, value):
        self.log.warning(f"Changing parameter {par} to value {value}")
        if par == "focus_exposure":
            self._focus_exposure = value
            self._hardware.set_exposure(value * 1000)  # Convert from seconds (in gui) to miliseconds
        elif par == "acquisition_exposure":
            self._acquisition_exposure = value
            self._hardware.set_exposure(value * 1000)  # Convert from seconds (in gui) to miliseconds
        elif par == "roi":
            self._hardware.set_roi(*self._roi)
        elif par == "bin":
            self._roi[5] = value
            self._hardware.set_roi(*self._roi)
        else:
            pass
