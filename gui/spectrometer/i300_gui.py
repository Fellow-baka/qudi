# -*- coding: utf-8 -*-

"""
This file contains a gui to control i300 and acton 2300 Princeton Instruments monochromators .
"""

import sys
import os

from core.module import Connector
from gui.guibase import GUIBase
from gui.colordefs import QudiPalettePale as palette
from qtpy import QtWidgets
from qtpy import QtCore
from qtpy import uic
# TODO: filter out wheel events for spinboxes
# TODO: test for small differences in boxes when change energy through wavelength e.g. 487.995 instead of 488.000


class I300MainWindow(QtWidgets.QMainWindow):
    """ Create the main window based on the *.ui file."""

    sigRead = QtCore.Signal()

    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_i300.ui')

        # Load it
        super().__init__()
        uic.loadUi(ui_file, self)
        self.show()


class I300Gui(GUIBase):
    """ This is the GUI Class for I300 monochromator"""

    _modclass = 'i300gui'
    _modtype = 'gui'

    i300connectlogic = Connector(interface='I300Logic')

    sigRead = QtCore.Signal()
    sigBusy = QtCore.Signal()
    sigLoadPosition = QtCore.Signal()

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
        self.log.debug('The following configuration was found.')

    def on_activate(self):
        """ Initialization of the GUI and connections"""

        self._i300_logic = self.i300connectlogic()  # logic module

        self._mw = I300MainWindow()

        ##############################
        # Connecting user interactions
        ##############################

        self._mw.laserLineBox.valueChanged.connect(self.laserline_box_changed)
        self._mw.wavelengthBox.valueChanged.connect(self.wavelength_box_changed)
        self._mw.energyBox.valueChanged.connect(self.energy_box_changed)
        self._mw.ramanShiftBox.valueChanged.connect(self.raman_shift_box_changed)

        #####################
        # starting the physical measurement
        self.update_boxes()

    def show(self):
        """ Make window visible and put it above all other windows. """
        QtWidgets.QMainWindow.show(self._mw)
        self._mw.activateWindow()
        self._mw.raise_()

    def on_deactivate(self):
        """ Deactivates module """
        self._mw.close()

    def laserline_box_changed(self):
        """ Change value of the laserline, recalculate and update boxes """
        self._i300_logic.laserline = self._mw.laserLineBox.value()
        self.update_boxes()

    def wavelength_box_changed(self):
        """ Move spectrometer to a new position of wavelength box value when the value changed.
            Works only when the focus is on box (basically you have to press enter when box focused)
            resets focus afterwards.
        """
        if self._mw.wavelengthBox.hasFocus():
            self._mw.wavelengthBox.clearFocus()
            target = self._mw.wavelengthBox.value()
            self._i300_logic.move_grating_nm(target)
        else:
            pass
        self.update_boxes()

    def energy_box_changed(self):
        """ Move spectrometer to a new position form the energy box value when the value changed.
            Works only when the focus is on box (basically you have to press enter when box focused)
            resets focus afterwards.
        """
        if self._mw.energyBox.hasFocus():
            self._mw.energyBox.clearFocus()
            target = 1239.84193 / self._mw.energyBox.value()  # convert from eV to nm
            self._i300_logic.move_grating_nm(target)
        else:
            pass
        self.update_boxes()

    def raman_shift_box_changed(self):
        """ Move spectrometer to a new position form the raman shift box value when the value changed.
            Works only when the focus is on box (basically you have to press enter when box focused)
            resets focus afterwards.
        """
        if self._mw.ramanShiftBox.hasFocus():
            self._mw.ramanShiftBox.clearFocus()
            laserline_nm = self._i300_logic.laserline
            target = -(1e7*laserline_nm)/(-1e7+laserline_nm*self._mw.ramanShiftBox.value())  # from cm-1 to nm
            self._i300_logic.move_grating_nm(target)
        else:
            pass
        self.update_boxes()

    def update_boxes(self):
        """ Calculates and updates all the boxes with positions"""
        laserline_nm = self._i300_logic.laserline
        wavelength_nm = self._i300_logic.read_grating_nm()
        if wavelength_nm == 0:
            raman_shift = 0
            wavelength_eV = 0
        else:
            raman_shift = (1 / laserline_nm - 1 / wavelength_nm) * 1e7  # Raman shift in cm-1
            wavelength_eV = 1239.84193 / wavelength_nm
        self._mw.wavelengthBox.setValue(wavelength_nm)
        self._mw.energyBox.setValue(wavelength_eV)
        self._mw.ramanShiftBox.setValue(raman_shift)


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = I300MainWindow()
    sys.exit(app.exec_())
