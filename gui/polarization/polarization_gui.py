# -*- coding: utf-8 -*-
"""
This file contains the Qudi console GUI module.

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

import os

from core.module import Connector
from gui.guibase import GUIBase
from qtpy import QtWidgets
from qtpy import QtCore
from qtpy import uic


class PolarizationGui(GUIBase):
    """ A graphical interface to control polarization rotators by hand and change their calibration.
    """
    _modclass = 'polarization_gui'
    _modtype = 'gui'

    ## declare connectors
    polarlogic = Connector(interface='GenericLogic')

    def on_activate(self):
        """Create all UI objects and show the window.
        """
        self._mw = SwitchMainWindow()
        self._polar_logic = self.polarlogic()
        # get a list of active axes
        axes_list = self._polar_logic.get_axes_labels()
        # For each active axis add a widget to the GUI to show its state
        for axis in axes_list:
            frame = QtWidgets.QGroupBox(axis, self._mw.scrollAreaWidgetContents)
            frame.setAlignment(QtCore.Qt.AlignLeft)
            frame.setFlat(False)
            self._mw.layout.addWidget(frame)
            layout = QtWidgets.QVBoxLayout(frame)
            polar_widget = PolarizationWidget(axis, self._polar_logic)
            layout.addWidget(polar_widget)

        self.restoreWindowPos(self._mw)
        self.show()

    def show(self):
        """Make sure that the window is visible and at the top.
        """
        self._mw.show()

    def on_deactivate(self):
        """ Hide window and stop ipython console.
        """
        self.saveWindowPos(self._mw)
        self._mw.close()


class SwitchMainWindow(QtWidgets.QMainWindow):
    """ Helper class for window loaded from UI file.
    """
    def __init__(self):
        """ Create the switch GUI window.
        """
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_polarization_gui.ui')

        # Load it
        super().__init__()
        uic.loadUi(ui_file, self)
        self.show()

        # Add layout that we want to fill
        self.layout = QtWidgets.QVBoxLayout(self.scrollArea)


class PolarizationWidget(QtWidgets.QWidget):
    """ A widget that shows all data associated to a polarization rotator axis.
    """
    def __init__(self, axis, logic):
        """ Create a switch widget.

          @param string axis: axis for widget, taken from logic
          @param module? logic: reference to polarization control logic module
        """
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_polarization_widget.ui')

        # Load it
        super().__init__()
        uic.loadUi(ui_file, self)

        self.axis = axis
        self.pol_logic = logic

        # correct state at start
        self.angle_doubleSpinBox.setValue(self.pol_logic.get_pos({self.axis})[self.axis])

        # user actions
        self.pol_logic.signal_rotation_finished.connect(self.update_angle)
        self.angle_doubleSpinBox.editingFinished.connect(self.angle_changed)
        self.set_zero_pushButton.clicked.connect(self.set_zero)

    def set_zero(self):
        self.pol_logic.calibrate({self.axis})
        self.angle_doubleSpinBox.setValue(self.pol_logic.get_pos({self.axis})[self.axis])

    def angle_changed(self):
        self.pol_logic.move_abs({self.axis: self.angle_doubleSpinBox.value()})

    def update_angle(self):
        self.angle_doubleSpinBox.setValue(self.pol_logic.get_pos({self.axis})[self.axis])

