# -*- coding: utf-8 -*-

"""
This file contains a gui to communicate with princeton instrument cameras.
Allows to plot data and change acquisition parameters, e.g. exposition, binning, shutter state.

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
import os
import sys
import pyqtgraph as pg
import time

from core.module import Connector
from gui.guibase import GUIBase
from gui.colordefs import QudiPalettePale as palette
from qtpy import QtWidgets
from qtpy import QtCore
from qtpy import uic
from qtpy import QtGui


class CCDMainWindow(QtWidgets.QMainWindow):
    """ Create the Main Window based on the *.ui file. """

    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ccd_gui.ui')

        # Load it
        super().__init__()
        uic.loadUi(ui_file, self)
        self.show()


class CCDGui(GUIBase):
    """ FIXME: Please document
    """
    _modclass = 'ccdgui'
    _modtype = 'gui'

    # declare connectors
    ccdd = Connector(interface='CCDLogic')

    sigFocusStart = QtCore.Signal()
    sigFocusStop = QtCore.Signal()
    sigAcquisitionStart = QtCore.Signal()
    sigAcquisitionStop = QtCore.Signal()

    _image = []
    _is_x_flipped = False
    _x_axis_mode = "Pixel"

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
        self.log.debug('The following configuration was found.')

        # checking for the right configuration
        for key in config.keys():
            self.log.info('{0}: {1}'.format(key, config[key]))

    def on_activate(self):
        """ Definition and initialisation of the GUI.
        """
        self._ccd_logic = self.ccdd()

        #####################
        # Configuring the dock widgets
        # Use the inherited class 'CounterMainWindow' to create the GUI window
        self._mw = CCDMainWindow()

        # Setup dock widgets
        self._mw.centralwidget.hide()
        self._mw.setDockNestingEnabled(True)

        # spectrum
        self._sw = self._mw.spectrum_PlotWidget  # pg.PlotWidget(name='Counter1')
        self._plot_spectrum = self._sw.plotItem

        self._curve1 = self._sw.plot()
        self._curve1.setPen(palette.c1, width=2)

        self._plot_spectrum.showAxis('top')
        self._plot_spectrum.showAxis('right')

        self._plot_spectrum.setLabel('bottom', 'x-axis (Pixels)')
        self._plot_spectrum.setLabel('left', 'Intensity (Counts)')

        # image (old version with PlotWidget)
        # self._iw = self._mw.image_PlotWidget  # pg.PlotWidget(name='Counter1')
        # self._plot_image = self._iw.plotItem

        # image (New version with pg.ImageView)
        self._iw = pg.ImageView(view=pg.PlotItem())
        self._mw.widget = QtGui.QWidget()
        self._mw.widget.setLayout(QtGui.QHBoxLayout())
        self._mw.widget.layout().addWidget(self._iw)
        self._mw.image2DockWidget.setWidget(self._iw)
        # self._iw.setImage(np.random.random((256, 256)))

        self._iw.view.showAxis('top')
        self._iw.view.showAxis('right')

        self._iw.view.setLabel('bottom', 'x-axis (Pixels)')
        self._iw.view.setLabel('left', 'y-axis (Pixels)')

        # create a new ViewBox, link the right axis to its coordinate system
        # self._right_axis = pg.ViewBox()
        # self._plot_item.showAxis('right')
        # self._plot_item.scene().addItem(self._right_axis)
        # self._plot_item.getAxis('right').linkToView(self._right_axis)
        # self._right_axis.setXLink(self._plot_item)

        # make correct button state
        self._mw.focus_Action.setChecked(False)

        # load boxes states
        self._mw.focus_doubleSpinBox.setValue(self._ccd_logic._focus_exposure)
        # self._mw.acquisition_doubleSpinBox.editingFinished.connect(self.acquisition_time_changed)

        #####################
        # Connecting user interactions
        #####################
        # Actions/buttons
        self._mw.focus_Action.triggered.connect(self.focus_clicked)  # Start/stop focus mode
        self._mw.acquisition_Action.triggered.connect(self.acquisition_clicked)  # Start single spectra/image
        self._mw.save_Action.triggered.connect(self.save_clicked)

        # Boxes
        # Time and number
        self._mw.focus_doubleSpinBox.editingFinished.connect(self.focus_time_changed)
        self._mw.acquisition_doubleSpinBox.editingFinished.connect(self.acquisition_time_changed)

        # ROI spinboxes and checkbox
        self._mw.roi_x0_spinBox.editingFinished.connect(self.roi_changed)
        self._mw.roi_x_max_spinBox.editingFinished.connect(self.roi_changed)
        self._mw.roi_y0_spinBox.editingFinished.connect(self.roi_changed)
        self._mw.roi_y_max_spinBox.editingFinished.connect(self.roi_changed)

        self._mw.bin_checkBox.stateChanged.connect(self.bin_clicked)
        self._mw.flip_x_checkBox.stateChanged.connect(self.flip_clicked)

        # Other stuff
        self._mw.energy_selector_comboBox.currentIndexChanged.connect(self.energy_unit_changed)

        #####################
        # starting the physical measurement
        self.sigFocusStart.connect(self._ccd_logic.start_focus)
        self.sigFocusStop.connect(self._ccd_logic.stop_focus)
        self.sigAcquisitionStart.connect(self._ccd_logic.start_single_acquisition)

        self._ccd_logic.sigUpdateDisplay.connect(self.update_data)
        self._ccd_logic.sigAcquisitionFinished.connect(self.acquisition_finished)
        # self.sigAcquisitionStop.connect(self._ccd_logic.start_single_acquisition)

        self._ccd_logic.sigRepeat.connect(self.update_data)

    def show(self):
        """Make window visible and put it above all other windows.
        """
        QtWidgets.QMainWindow.show(self._mw)
        self._mw.activateWindow()
        self._mw.raise_()

    def on_deactivate(self):
        """ Deactivate the module properly.
        """
        # FIXME: !
        self._ccd_logic.stop_focus()
        self._mw.close()

    def update_data(self):
        """ The function that grabs the data and sends it to the plot.
            If the data is 1D send it to spectrum widget, if not to image.
            Asks logic module to convert x-axis to target units, changing axis labels.
            TODO: Double check if the data flipped/rotated properly.
        """
        data = self._ccd_logic.buf_spectrum
        # data = np.rot90(data)

        if self._is_x_flipped:
            if data.shape[0] == 1:
                data = np.fliplr(data)
            else:
                data = np.flipud(data)

        # TODO: refactor this later
        if self._x_axis_mode == "Wavelength (nm)":
            wavelength_middle = self._ccd_logic._mono.absolute_position_to_wavelength(
                self._ccd_logic._mono._hardware.read_position_nm())
            x_axis = np.array(self._ccd_logic.convert_from_pixel_to_nm(wavelength_middle, 0))
            self._plot_spectrum.setLabel('bottom', f'{self._x_axis_mode}')
            # self._plot_image.setLabel('bottom', f'{self._x_axis_mode}')
        elif self._x_axis_mode == "Raman shift (cm-1)":
            wavelength_middle = self._ccd_logic._mono.absolute_position_to_wavelength(
                self._ccd_logic._mono._hardware.read_position_nm())
            x_nm = np.array(self._ccd_logic.convert_from_pixel_to_nm(wavelength_middle, 0))
            x_axis = self._ccd_logic.convert_energy_units(x_nm, "Raman shift (cm-1)")
            self._plot_spectrum.setLabel('bottom', f'{self._x_axis_mode}')
            # self._plot_image.setLabel('bottom', f'{self._x_axis_mode}')
        elif self._x_axis_mode == "Energy (eV)":
            wavelength_middle = self._ccd_logic._mono.absolute_position_to_wavelength(
                self._ccd_logic._mono._hardware.read_position_nm())
            x_nm = np.array(self._ccd_logic.convert_from_pixel_to_nm(wavelength_middle, 0))
            x_axis = self._ccd_logic.convert_energy_units(x_nm, "Energy (eV)")
            self._plot_spectrum.setLabel('bottom', f'{self._x_axis_mode}')
            # self._plot_image.setLabel('bottom', f'{self._x_axis_mode}')
        elif self._x_axis_mode == "Wavenumber (cm-1)":
            wavelength_middle = self._ccd_logic._mono.absolute_position_to_wavelength(
                self._ccd_logic._mono._hardware.read_position_nm())
            x_nm = np.array(self._ccd_logic.convert_from_pixel_to_nm(wavelength_middle, 0))
            x_axis = self._ccd_logic.convert_energy_units(x_nm, "Wavenumber (cm-1)")
            self._plot_spectrum.setLabel('bottom', f'{self._x_axis_mode}')
            # self._plot_image.setLabel('bottom', f'{self._x_axis_mode}')
        elif self._x_axis_mode == "Frequency (THz)":
            wavelength_middle = self._ccd_logic._mono.absolute_position_to_wavelength(
                self._ccd_logic._mono._hardware.read_position_nm())
            x_nm = np.array(self._ccd_logic.convert_from_pixel_to_nm(wavelength_middle, 0))
            x_axis = self._ccd_logic.convert_energy_units(x_nm, "Frequency (THz)")
            self._plot_spectrum.setLabel('bottom', f'{self._x_axis_mode}')
            # self._plot_image.setLabel('bottom', f'{self._x_axis_mode}')
        else:  # Pixels
            x_axis = np.arange(1, data.size+1, 1)
            self._plot_spectrum.setLabel('bottom', 'X-axis (Pixels)')
            # self._plot_image.setLabel('bottom', 'X-axis (Pixels)')

        if data.shape[0] == 1:
            self._iw.clear()
            data = np.fliplr(data)
            data = data[0]
            # x_axis = np.array(self._ccd_logic.convert_from_pixel_to_nm(502.56, 0))
            self._curve1.setData(x=x_axis, y=data)
        else:
            self._curve1.clear()
            self._iw.clear()
            # image = pg.ImageItem(image=data)  #, x=np.arange(50, data.size+50, 1))
            self._iw.setImage(data)

    def focus_clicked(self):
        """ Handling the Focus button to stop and start continuous acquisition """
        self._mw.number_of_spectra_spinBox.setFocus()
        self._mw.acquisition_Action.setDisabled(True)
        self._mw.save_Action.setDisabled(True)
        if self._ccd_logic.module_state() == 'locked':
            self.sigFocusStop.emit()
        else:
            self.sigFocusStart.emit()

    def acquisition_clicked(self):
        """ Handling the Acquisition button for getting one image/spectrum """
        self.sigAcquisitionStart.emit()
        self._mw.focus_Action.setDisabled(True)
        self._mw.acquisition_Action.setDisabled(True)
        self._mw.save_Action.setDisabled(True)

    def acquisition_finished(self):
        self._mw.focus_Action.setDisabled(False)
        self._mw.acquisition_Action.setDisabled(False)
        self._mw.save_Action.setDisabled(False)

    def save_clicked(self):
        """ Handling the save button to save the data into a file.
        """
        return

    def focus_time_changed(self):
        self._ccd_logic.set_parameter("focus_exposure", self._mw.focus_doubleSpinBox.value())
        pass

    def acquisition_time_changed(self):
        self._ccd_logic.set_parameter("acquisition_exposure", self._mw.acquisition_doubleSpinBox.value())
        pass

    def roi_changed(self):
        """ ROI changed through SpinBoxes interaction """
        self._ccd_logic._roi[0] = self._mw.roi_x0_spinBox.value()
        self._ccd_logic._roi[1] = self._mw.roi_x_max_spinBox.value() - self._mw.roi_x0_spinBox.value()
        self._ccd_logic._roi[3] = self._mw.roi_y0_spinBox.value()
        self._ccd_logic._roi[4] = self._mw.roi_y_max_spinBox.value() - self._mw.roi_y0_spinBox.value()
        self._ccd_logic.set_parameter("roi", "baka")  # TODO: check what this line is doing.

    def bin_clicked(self, state):
        if state == QtCore.Qt.Checked:
            self._ccd_logic.set_parameter("bin", self._mw.roi_y_max_spinBox.value() - self._mw.roi_y0_spinBox.value())
        else:
            self._ccd_logic.set_parameter("bin", 1)

    def flip_clicked(self, state):
        """
        Changes the variable responsible for horizontal flipping the data. Updates spectrum/image afterwards.
        """
        if state == QtCore.Qt.Checked:
            self._is_x_flipped = True
        else:
            self._is_x_flipped = False
        self.update_data()

    def energy_unit_changed(self, index):
        box_text = self._mw.energy_selector_comboBox.currentText()
        self.log.info(f"Selected x axis units: {box_text}")
        self._x_axis_mode = box_text
        self.update_data()
        # if index == 0:
        #     pass
        #     # self.log.info(f"Selected x axis units: {box_text}")
        # elif index == 1:
        #     pass
        #     # self.log.info(f"{self._mw.energy_selector_comboBox.currentText()}")
        # elif index == 2:
        #     pass


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    ex = CCDMainWindow()
    sys.exit(app.exec_())
