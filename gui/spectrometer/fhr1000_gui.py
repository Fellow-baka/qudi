# -*- coding: utf-8 -*-

"""
This file contains a gui to control FHR1000 HORIBA JOBIN YVON monochromator.
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


class Fhr1000MainWindow(QtWidgets.QMainWindow):
    """ Create the main window based on the *.ui file."""

    sigRead = QtCore.Signal()

    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_fhr1000.ui')

        # Load it
        super().__init__()
        uic.loadUi(ui_file, self)
        self.show()


class Fhr1000Gui(GUIBase):
    """ This is the GUI Class for FHR1000 measurements"""

    _modclass = 'fhr1000gui'
    _modtype = 'gui'

    fhrconnectlogic = Connector(interface='Fhr1000Logic')

    sigRead = QtCore.Signal()
    sigBusy = QtCore.Signal()
    sigLoadPosition = QtCore.Signal()

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
        self.log.debug('The following configuration was found.')

    def on_activate(self):
        """ Initialization of the GUI and connections"""

        self._fhr_logic = self.fhrconnectlogic()  # logic module

        self._mw = Fhr1000MainWindow()

        ##############################
        # Connecting user interactions
        ##############################

        # self._mw.readPositionButton.clicked.connect(self.button_position_clicked)
        # self.sigRead.connect(self._hr_logic.get_from_file)
        #
        # self._mw.readBusyButton.clicked.connect(self.button_busy_clicked)
        # self.sigBusy.connect(self._hr_logic.ask_busy)

        self._mw.laserLineBox.valueChanged.connect(self.laserline_box_changed)
        self._mw.wavelengthBox.valueChanged.connect(self.wavelength_box_changed)
        self._mw.energyBox.valueChanged.connect(self.energy_box_changed)
        self._mw.ramanShiftBox.valueChanged.connect(self.raman_shift_box_changed)
        self._mw.slitWidthBox.valueChanged.connect(self.slit_width_box_changed)

        #####################
        # starting the physical measurement
        self.update_boxes()

        # self.readButton.clicked.connect(self.read)
        # self.connect()

        # self.laserLineBox.valueChanged.connect(self.onCurrentTextChanged)

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
        self._fhr_logic.laserline = self._mw.laserLineBox.value()
        self.update_boxes()

    def wavelength_box_changed(self):
        """ Move spectrometer to a new position of wavelength box value when the value changed.
            Works only when the focus is on box (basically you have to press enter when box focused)
            resets focus afterwards.
        """
        if self._mw.wavelengthBox.hasFocus():
            self._mw.wavelengthBox.clearFocus()
            self.log.warning("I'm going to move grating! (wavelength box value changed)")
            target = self._mw.wavelengthBox.value()
            self._fhr_logic.move_grating_nm(target)
        else:
            # self.log.warning("Not in focus")
            pass
        self.update_boxes()

    def energy_box_changed(self):
        """ Move spectrometer to a new position form the energy box value when the value changed.
            Works only when the focus is on box (basically you have to press enter when box focused)
            resets focus afterwards.
        """
        if self._mw.energyBox.hasFocus():
            self._mw.energyBox.clearFocus()
            self.log.warning("I'm going to move grating! (energy box value changed)")
            target = 1239.84193 / self._mw.energyBox.value()  # convert from eV to nm
            self._fhr_logic.move_grating_nm(target)
        else:
            # self.log.warning("Not in focus")
            pass
        self.update_boxes()

    def raman_shift_box_changed(self):
        """ Move spectrometer to a new position form the raman shift box value when the value changed.
            Works only when the focus is on box (basically you have to press enter when box focused)
            resets focus afterwards.
        """
        if self._mw.ramanShiftBox.hasFocus():
            self._mw.ramanShiftBox.clearFocus()
            self.log.warning("I'm going to move grating! (raman shift box value changed)")
            laserline_nm = self._fhr_logic.laserline
            target = -(1e7*laserline_nm)/(-1e7+laserline_nm*self._mw.ramanShiftBox.value())  # from cm-1 to nm
            self._fhr_logic.move_grating_nm(target)
        else:
            # self.log.warning("Not in focus")
            pass
        self.update_boxes()

    def slit_width_box_changed(self):
        """ Change spectrometer entrance slit width.
            Works only when the focus is on box (basically you have to press enter when box focused)
            resets focus afterwards.
        """
        if self._mw.slitWidthBox.hasFocus():
            self._mw.slitWidthBox.clearFocus()
            self.log.warning("I'm going to move slit! (slit width box value changed)")
            target = self._mw.slitWidthBox.value()
            self._fhr_logic.move_slit_um(target)
        else:
            # self.log.warning("Not in focus")
            pass

    def update_boxes(self):
        """ Calculates and updates all the boxes with positions"""
        laserline_nm = self._fhr_logic.laserline
        wavelength_nm = self._fhr_logic.read_grating_nm()
        slit_width_um = self._fhr_logic.read_slit_um()
        raman_shift = (1 / laserline_nm - 1 / wavelength_nm) * 1e7  # Raman shift in cm-1
        self._mw.wavelengthBox.setValue(wavelength_nm)
        self._mw.energyBox.setValue(1239.84193 / wavelength_nm)
        self._mw.ramanShiftBox.setValue(raman_shift)
        self._mw.slitWidthBox.setValue(slit_width_um)

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = Fhr1000MainWindow()
    sys.exit(app.exec_())
