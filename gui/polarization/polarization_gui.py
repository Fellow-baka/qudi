# -*- coding: utf-8 -*-
"""
This file contains the gui for polarization control. Only one axis is available now.

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


class PolarizationMainWindow(QtWidgets.QMainWindow):
    """ Create the main window based on the *.ui file."""

    sigRead = QtCore.Signal()

    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_polarization_rotation.ui')

        # Load it
        super().__init__()
        uic.loadUi(ui_file, self)
        self.show()


class PolarizationGui(GUIBase):
    """ This is the GUI Class for Polarization Rotation measurements"""

    _modclass = 'PolarizationRotationGui'
    _modtype = 'gui'

    polarlogic = Connector(interface='GenericLogic')

    sigRead = QtCore.Signal()
    sigBusy = QtCore.Signal()
    sigLoadPosition = QtCore.Signal()

    def on_activate(self):
        """Create all UI objects and show the window.
        """
        self._mw = PolarizationMainWindow()

        self._polar_logic = self.polarlogic()

        # For each switch that the logic has, add a widget to the GUI to show its state
        # for hw in lsw.switches:
        #     frame = QtWidgets.QGroupBox(hw, self._mw.scrollAreaWidgetContents)
        #     frame.setAlignment(QtCore.Qt.AlignLeft)
        #     frame.setFlat(False)
        #     self._mw.layout.addWidget(frame)
        #     layout = QtWidgets.QVBoxLayout(frame)
        #     for switch in lsw.switches[hw]:
        #         swidget = SwitchWidget(switch, lsw.switches[hw][switch])
        #         layout.addWidget(swidget)

        # self.restoreWindowPos(self._mw)

        self._mw.angle_doubleSpinBox.valueChanged.connect(self.angle_changed)
        self._mw.set_zero_pushButton.clicked.connect(self.zero_clicked)

        self._mw.angle_doubleSpinBox.setValue(self._polar_logic.get_pos())

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

    def angle_changed(self):
        self._polar_logic.mov_abs(self._mw.angle_doubleSpinBox.value())

    def zero_clicked(self):
        self._polar_logic.set_zero()
        self._mw.angle_doubleSpinBox.setValue(0.0)
