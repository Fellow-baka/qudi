# -*- coding: utf-8 -*-
"""
This file contains the gui for temperature measurements/control. Only one sensor/heater is supported now.

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

import sys
import os

from core.module import Connector
from gui.guibase import GUIBase
from gui.colordefs import QudiPalettePale as palette
from qtpy import QtWidgets
from qtpy import QtCore
from qtpy import uic


class TemperatureMainWindow(QtWidgets.QMainWindow):
    """ Create the main window based on the *.ui file."""

    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'mercury.ui')

        # Load it
        super().__init__()
        uic.loadUi(ui_file, self)
        self.show()


class TemperatureGui(GUIBase):
    """ This is the GUI Class for Temperature measurements"""

    _modclass = 'TemperatureGui'
    _modtype = 'gui'

    temperaturelogic = Connector(interface='GenericLogic')

    sigLoopTemperatureStart = QtCore.Signal()
    sigLoopTemperatureEnd = QtCore.Signal()

    def on_activate(self):
        """Create all UI objects and show the window.
        """
        self._mw = TemperatureMainWindow()

        self._temperature_logic = self.temperaturelogic()

        # make correct button and checkboxes states
        self._mw.temperatureLoopCheckBox.setChecked(False)

        #####################
        # Connecting user interactions
        #####################

        self._mw.temperatureLoopCheckBox.stateChanged.connect(self.read_loop_temperature_checked)
        self._mw.temperatureReadPushButton.clicked.connect(self.get_temperature_button_clicked)

        self.sigLoopTemperatureStart.connect(self._temperature_logic.start_temperature_measurement_loop)
        self.sigLoopTemperatureEnd.connect(self._temperature_logic.stop_temperature_measurement_loop)
        self._temperature_logic.sigRepeat.connect(self.update_display)

        self.show()

    def show(self):
        """Make sure that the window is visible and at the top.
        """
        self._mw.show()

    def on_deactivate(self):
        """ Hide window and stop ipython console.
        """
        # self.saveWindowPos(self._mw)
        self._mw.close()

    # def checkbox_changed(self):
    #     self._polar_logic.mov_abs(self._mw.angle_doubleSpinBox.value())
    #
    # def zero_clicked(self):
    #     self._polar_logic.set_zero()
    #     self._mw.angle_doubleSpinBox.setValue(0.0)

    def get_temperature_button_clicked(self):
        self._temperature_logic.get_temperature()
        self.update_display()

    def read_loop_temperature_checked(self):
        if self._mw.temperatureLoopCheckBox.checkState() == 0:
            print('end_thingy')
            self.sigLoopTemperatureEnd.emit()
        else:
            self.sigLoopTemperatureStart.emit()
            print('start_thingy')

    def update_display(self):
        self._mw.temperatureLCDNumber.display(self._temperature_logic._temperature)
