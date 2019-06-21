# -*- coding: utf-8 -*-

"""
This file contains a gui to control monochromator (hr640) for this case.
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


class Hr640MainWindow(QtWidgets.QMainWindow):
    """ Create the main window based on the *.ui file."""

    sigRead = QtCore.Signal()

    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_hr640.ui')

        # Load it
        super().__init__()
        uic.loadUi(ui_file, self)
        self.show()


class Hr640Gui(GUIBase):
    """ This is the GUI Class for HR 640 measurements"""

    _modclass = 'HR640gui'
    _modtype = 'gui'

    hrconnectlogic = Connector(interface='Hr640Logic')

    sigRead = QtCore.Signal()
    sigBusy = QtCore.Signal()
    sigLoadPosition = QtCore.Signal()

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
        self.log.debug('The following configuration was found.')

    def on_activate(self):
        """ Initialization of the GUI and connections"""

        self._hr_logic = self.hrconnectlogic()  # logic module

        self._mw = Hr640MainWindow()

        ##############################
        # Connecting user interactions
        ##############################

        # self._mw.readPositionButton.clicked.connect(self.button_position_clicked)
        # self.sigRead.connect(self._hr_logic.get_from_file)
        #
        # self._mw.readBusyButton.clicked.connect(self.button_busy_clicked)
        # self.sigBusy.connect(self._hr_logic.ask_busy)

        self._mw.laserLineBox.valueChanged.connect(self.laserline_box_changed)
        self._mw.absolutePositionBox.valueChanged.connect(self.absolute_position_box_changed)
        self.sigLoadPosition.connect(self._hr_logic.load_position)
        self._mw.wavelengthBox.valueChanged.connect(self.wavelength_box_changed)
        self._mw.energyBox.valueChanged.connect(self.energy_box_changed)
        self._mw.ramanShiftBox.valueChanged.connect(self.raman_shift_box_changed)

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
        """ Change value of the laserline and recalculates boxes """
        self._hr_logic.laserline = self._mw.laserLineBox.value()
        self.update_boxes()

    def absolute_position_box_changed(self):
        """ Change value of the absolute position, put it in file and recalculates boxes """
        self._hr_logic.absolute_position = self._mw.absolutePositionBox.value()
        self._hr_logic.put_absolute_position_to_file(self._hr_logic.absolute_position)
        self.update_boxes()
        self.sigLoadPosition.emit()

    def wavelength_box_changed(self):
        """ Move spectrometer to a new position of wavelength box value when the value changed
            works only when the focus is on box (basically you have to press enter when box focused)
            resets focus afterwards.
        """
        if self._mw.wavelengthBox.hasFocus():
            self._mw.wavelengthBox.clearFocus()
            self.log.warning("I'm going to move grating! (wavelength box value changed)")
            target = self._hr_logic.wavelength_to_absolute_position(self._mw.wavelengthBox.value())
            self._hr_logic.move_to_nm(target)
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
            wavelength_nm = 1239.84193 / self._mw.energyBox.value()  # convert from eV to nm
            target = self._hr_logic.wavelength_to_absolute_position(wavelength_nm)
            self._hr_logic.move_to_nm(target)
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
            laserline_nm = self._hr_logic.laserline
            wavelength_nm = -(1e7*laserline_nm)/(-1e7+laserline_nm*self._mw.ramanShiftBox.value())  # from cm-1 to nm
            target = self._hr_logic.wavelength_to_absolute_position(wavelength_nm)
            self._hr_logic.move_to_nm(target)
        else:
            # self.log.warning("Not in focus")
            pass
        self.update_boxes()

    def update_boxes(self):
        """ Calculates and updates all the boxes with positions"""
        laserline_nm = self._hr_logic.laserline
        absolute_position_nm = self._hr_logic.absolute_position
        wavelength_nm = self._hr_logic.absolute_position_to_wavelength(absolute_position_nm)
        raman_shift = (1 / laserline_nm - 1 / wavelength_nm) * 1e7  # Raman shift in cm-1
        self._mw.absolutePositionBox.setValue(self._hr_logic.absolute_position)
        self._mw.wavelengthBox.setValue(wavelength_nm)
        self._mw.energyBox.setValue(1239.84193 / wavelength_nm)
        self._mw.ramanShiftBox.setValue(raman_shift)

    # def button_position_clicked(self):
    #     self.sigRead.emit()

    # def button_busy_clicked(self):
    #     self.sigBusy.emit()


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = Hr640MainWindow()
    sys.exit(app.exec_())
