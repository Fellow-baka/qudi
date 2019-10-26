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
    ccdlogic = Connector(interface='CCDLogic')

    sigFocusStart = QtCore.Signal()
    sigFocusStop = QtCore.Signal()
    sigAcquisitionStart = QtCore.Signal()
    sigAcquisitionStop = QtCore.Signal()

    _image = []
    # _is_x_flipped = False
    _x_axis_mode = 'Pixels'
    _y_axis_mode = 'Counts'
    # _constant_background = 0

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
        self.log.debug('The following configuration was found.')

        # checking for the right configuration
        for key in config.keys():
            self.log.info('{0}: {1}'.format(key, config[key]))

    def on_activate(self):
        """ Definition and initialisation of the GUI.
        """
        self._ccd_logic = self.ccdlogic()

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

        # change font size
        font = QtGui.QFont()
        font.setPixelSize(16)
        self._sw.getAxis("left").tickFont = font
        self._sw.getAxis("left").setStyle(tickTextOffset=6)
        self._sw.getAxis("bottom").tickFont = font
        self._sw.getAxis("bottom").setStyle(tickTextOffset=6)
        self._sw.getAxis("top").tickFont = font
        self._sw.getAxis("top").setStyle(tickTextOffset=6)
        self._sw.getAxis("right").tickFont = font
        self._sw.getAxis("right").setStyle(tickTextOffset=6)

        # image (New version with pg.ImageView)
        self._iw = pg.ImageView(view=pg.PlotItem())
        self._mw.widget = QtGui.QWidget()
        self._mw.widget.setLayout(QtGui.QHBoxLayout())
        self._mw.widget.layout().addWidget(self._iw)
        self._mw.image2DockWidget.setWidget(self._iw)

        self._iw.view.showAxis('top')
        self._iw.view.showAxis('right')

        self._iw.view.setLabel('bottom', 'x-axis (Pixels)')
        self._iw.view.setLabel('left', 'y-axis (Pixels)')

        # change font size
        font = QtGui.QFont()
        font.setPixelSize(16)
        self._iw.view.getAxis("left").tickFont = font
        self._iw.view.getAxis("left").setStyle(tickTextOffset=6)
        self._iw.view.getAxis("bottom").tickFont = font
        self._iw.view.getAxis("bottom").setStyle(tickTextOffset=6)
        self._iw.view.getAxis("top").tickFont = font
        self._iw.view.getAxis("top").setStyle(tickTextOffset=6)
        self._iw.view.getAxis("right").tickFont = font
        self._iw.view.getAxis("right").setStyle(tickTextOffset=6)

        # make correct button and checkboxes states
        self._mw.focus_Action.setChecked(False)

        if self._ccd_logic._mode == '1D':  # bin y
            self._mw.bin_checkBox.setChecked(True)
        else:
            self._mw.bin_checkBox.setChecked(False)

        if self._ccd_logic._x_flipped:  # flip x
            self._mw.flip_x_checkBox.setChecked(True)
        else:
            self._mw.flip_x_checkBox.setChecked(False)

        # load spinboxes states
        self._mw.focus_doubleSpinBox.setValue(self._ccd_logic._focus_exposure)
        self._mw.acquisition_doubleSpinBox.setValue(self._ccd_logic._acquisition_exposure)
        self._mw.constant_background_spinBox.setValue(self._ccd_logic._constant_background)
        self._mw.ccd_offset_nm_doubleSpinBox.setValue(self._ccd_logic._ccd_offset_nm)

        self._mw.laser_power_mW_doubleSpinBox.setValue(self._ccd_logic._laser_power_mW)
        self._mw.magnetic_field_T_doubleSpinBox.setValue(self._ccd_logic._magnetic_field_T)
        self._mw.arbitrary_tag_lineEdit.setText(self._ccd_logic._arbitrary_tag)

        self._mw.roi_x0_spinBox.setValue(self._ccd_logic._roi[0])
        self._mw.roi_x_max_spinBox.setValue(self._ccd_logic._roi[1] + self._ccd_logic._roi[0])  # convert to coordinates from width
        self._mw.roi_y0_spinBox.setValue(self._ccd_logic._roi[3])
        self._mw.roi_y_max_spinBox.setValue(self._ccd_logic._roi[4] + self._ccd_logic._roi[3])

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

        # ROI and chip spinboxes and checkbox
        self._mw.roi_x0_spinBox.editingFinished.connect(self.roi_changed)
        self._mw.roi_x_max_spinBox.editingFinished.connect(self.roi_changed)
        self._mw.roi_y0_spinBox.editingFinished.connect(self.roi_changed)
        self._mw.roi_y_max_spinBox.editingFinished.connect(self.roi_changed)

        self._mw.bin_checkBox.stateChanged.connect(self.bin_clicked)
        self._mw.flip_x_checkBox.stateChanged.connect(self.flip_clicked)

        self._mw.ccd_offset_nm_doubleSpinBox.editingFinished.connect(self.ccd_offset_changed)

        # Background
        self._mw.constant_background_spinBox.editingFinished.connect(self.constant_background_changed)

        # Some metainformation
        self._mw.laser_power_mW_doubleSpinBox.editingFinished.connect(self.laser_power_changed)
        self._mw.magnetic_field_T_doubleSpinBox.editingFinished.connect(self.magnetic_field_changed)
        self._mw.arbitrary_tag_lineEdit.editingFinished.connect(self.arbitrary_tag_changed)

        # Adc and shutter stuff
        self.fill_interface_values()
        self._mw.adc_quality_comboBox.currentIndexChanged.connect(self.adc_quality_changed)
        self._mw.adc_analog_gain_comboBox.currentIndexChanged.connect(self.adc_analog_gain_changed)
        self._mw.shutter_timing_mode_comboBox.currentIndexChanged.connect(self.shutter_timing_mode_changed)
        self._mw.adc_speed_comboBox.currentIndexChanged.connect(self.adc_speed_changed)
        self._mw.vertical_shift_rate_comboBox.currentIndexChanged.connect(self.vertical_shift_rate_changed)

        # Comboboxes
        self._mw.energy_selector_comboBox.currentIndexChanged.connect(self.energy_unit_changed)
        self._mw.counts_selector_comboBox.currentIndexChanged.connect(self.counts_unit_changed)

        #####################
        # starting the physical measurement
        self.sigFocusStart.connect(self._ccd_logic.start_focus)
        self.sigFocusStop.connect(self._ccd_logic.stop_focus)
        self.sigAcquisitionStart.connect(self._ccd_logic.start_single_acquisition)
        self.sigAcquisitionStop.connect(self._ccd_logic.stop_acquisition, QtCore.Qt.DirectConnection)

        self._ccd_logic.sigUpdateDisplay.connect(self.update_data)
        self._ccd_logic.sigAcquisitionFinished.connect(self.acquisition_finished)

        self._ccd_logic.sigRepeat.connect(self.update_data)

    def show(self):
        """ Make window visible and put it above all other windows """
        QtWidgets.QMainWindow.show(self._mw)
        self._mw.activateWindow()
        self._mw.raise_()

    def on_deactivate(self):
        """ Deactivate the module properly """
        # FIXME: !
        self._ccd_logic.stop_focus()
        self._mw.close()

    def update_data(self):
        """ The function that grabs the data and sends it to the plot.
            If the data is 1D send it to spectrum widget, if not to image.
            Asks logic module to convert x-axis to target units and do corrections/normalizations.
            Changing axis labels accordingly.
            TODO: Double check if the data flipped/rotated properly.
        """
        # self._ccd_logic._proceed_data_dict['Pixels'] = self._ccd_logic._raw_data_dict['Pixels']

        # raw_data = self._ccd_logic._raw_data_dict['Counts']
        # self._ccd_logic._proceed_data_dict['Counts'] = self._ccd_logic.correct_background(raw_data, self._ccd_logic._constant_background)
        # data = self._ccd_logic._proceed_data_dict['Counts']

        if self._ccd_logic._raw_data_dict['Counts'] == []:
            return None  # TODO: Just clean some code

        self._ccd_logic._proceed_data_dict = self._ccd_logic.convert_spectra(self._x_axis_mode, self._y_axis_mode)
        # data = self._ccd_logic._proceed_data_dict[self._y_axis_mode]

        # if self._ccd_logic._x_flipped:
        #     self._ccd_logic.flip_data(data)

        # Fill
        # self._ccd_logic._proceed_data_dict['Pixels'] = self._ccd_logic._raw_data_dict['Pixels']

        # Convert to target units and change labels

        if self._ccd_logic._mode == '1D':                  # Spectrum mode
            self._iw.clear()
            x_axis = self._ccd_logic._proceed_data_dict[self._x_axis_mode]
            # data = self._ccd_logic._proceed_data_dict[self._y_axis_mode][0]
            y_axis = self._ccd_logic._proceed_data_dict[self._y_axis_mode][0]

            self._curve1.setData(x=x_axis, y=y_axis)

            if self._x_axis_mode in ("Energy (eV)",
                                     "Energy (meV)",
                                     "Wavenumber (cm-1)",
                                     "Frequency (THz)",
                                     # "Energy RELATIVE (meV)",
                                     # "Frequency RELATIVE (THz)"
                                     ):
                self._sw.invertX(True)
            else:
                self._sw.invertX(False)
            # self._sw.plotItem.autoRange()
        else:                                   # Image mode
            self._curve1.clear()
            # self._iw.clear()
            self._iw.setImage(self._ccd_logic._proceed_data_dict[self._y_axis_mode])
            self._iw.view.setRange(xRange=[640, 680])
            self._iw.view.setRange(yRange=[0, 100])
            # self._iw.imageItem.resetTransform()

            if self._x_axis_mode != 'Pixels':
                x_axis = self._ccd_logic._proceed_data_dict[self._x_axis_mode]
                # self._iw.imageItem.resetTransform()
                shape = self._ccd_logic._proceed_data_dict['Counts'].shape[0]
            #     self._iw.imageItem.translate(x_axis[0], 0)
            #     self._iw.imageItem.scale((x_axis[-1] - x_axis[0])/shape, 1)
            #     self._iw.view.getViewBox().invertY(False)
            #     aspect_ratio = shape / (x_axis[-1] - x_axis[0])
            #     self._iw.view.getViewBox().setAspectLocked(lock=True, ratio=aspect_ratio)
            # elif self._x_axis_mode == 'Pixels':
            #     self._iw.view.getViewBox().setAspectLocked(lock=True, ratio=1)
            #
            # if self._x_axis_mode in ("Energy (eV)",
            #                          "Energy (meV)",
            #                          "Wavenumber (cm-1)",
            #                          "Frequency (THz)",
            #                          # "Energy RELATIVE (meV)",
            #                          # "Frequency RELATIVE (THz)"
            #                          ):
            #     self._iw.view.getViewBox().invertX(True)
            #     self._iw.view.getViewBox().invertY(True)
            # else:
            #     self._iw.view.getViewBox().invertX(False)
            #     self._iw.view.getViewBox().invertY(False)
            # self._iw.autoRange()

        # Refresh lables!
        self._plot_spectrum.setLabel('bottom', f'{self._x_axis_mode}')
        self._iw.view.setLabel('bottom', f'{self._x_axis_mode}')

        # self._plot_spectrum.setLabel('left', f'Intensity ({self._y_axis_mode})')
        # self._iw.view.setLabel('left', f'Intensity ({self._y_axis_mode})')

    def focus_clicked(self):
        """ Handling the Focus button to stop and start continuous acquisition """
        # self._mw.number_of_spectra_spinBox.setFocus()
        self._mw.acquisition_Action.setDisabled(True)
        self._mw.save_Action.setDisabled(True)
        if self._ccd_logic.module_state() == 'locked':
            self.sigFocusStop.emit()
        else:
            self.sigFocusStart.emit()

    def acquisition_clicked(self):
        """ Handling the Acquisition button for getting one image/spectrum """
        # self.sigAcquisitionStart.emit()
        self._mw.focus_Action.setDisabled(True)
        # self._mw.acquisition_Action.setDisabled(True)
        self._mw.save_Action.setDisabled(True)
        if self._ccd_logic.module_state() == 'locked':
            self.sigAcquisitionStop.emit()
        else:
            self.sigAcquisitionStart.emit()

    def acquisition_finished(self):
        """ Change state of the buttons after finishing acquisition """
        self._mw.focus_Action.setDisabled(False)
        self._mw.acquisition_Action.setDisabled(False)
        self._mw.acquisition_Action.setChecked(False)
        self._mw.save_Action.setDisabled(False)

    def save_clicked(self):
        """ Handling the save button to save the data into a file.
        """
        self._ccd_logic.save_data()

    def focus_time_changed(self):
        self._ccd_logic.set_parameter("focus_exposure", self._mw.focus_doubleSpinBox.value())

    def acquisition_time_changed(self):
        self._ccd_logic.set_parameter("acquisition_exposure", self._mw.acquisition_doubleSpinBox.value())

    def laser_power_changed(self):
        self._ccd_logic._laser_power_mW = self._mw.laser_power_mW_doubleSpinBox.value()

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
            self._ccd_logic._mode = '1D'
        else:
            self._ccd_logic.set_parameter("bin", 1)
            self._ccd_logic._mode = '2D'

    def flip_clicked(self, state):
        """
        Changes the variable responsible for horizontal flipping the data. Updates spectrum/image afterwards.
        """
        if state == QtCore.Qt.Checked:
            self._ccd_logic._x_flipped = True
        else:
            self._ccd_logic._x_flipped = False
        self.update_data()

    def energy_unit_changed(self, index):
        box_text = self._mw.energy_selector_comboBox.currentText()
        self._x_axis_mode = box_text
        self.log.info(f"Selected x axis units: {box_text}")
        self.update_data()

    def counts_unit_changed(self, index):
        box_text = self._mw.counts_selector_comboBox.currentText()
        self._y_axis_mode = box_text
        self.log.info(f"Selected y axis units: {box_text}")
        self.update_data()

    def constant_background_changed(self):
        self._ccd_logic._constant_background = self._mw.constant_background_spinBox.value()
        self.update_data()

    def ccd_offset_changed(self):
        self._ccd_logic._ccd_offset_nm = self._mw.ccd_offset_nm_doubleSpinBox.value()
        self.update_data()

    def magnetic_field_changed(self):
        self._ccd_logic._magnetic_field_T = self._mw.magnetic_field_T_doubleSpinBox.value()

    def arbitrary_tag_changed(self):
        self._ccd_logic._arbitrary_tag = self._mw.arbitrary_tag_lineEdit.text()

    # TODO: Refactor this whole part. It seems it is possible to make this more elegant.

    def adc_quality_changed(self):
        di = self._ccd_logic.get_availiable_values('AdcQuality')
        val = di[self._mw.adc_quality_comboBox.currentText()]
        self._ccd_logic.set_parameter_propagator('AdcQuality', val)

    def adc_analog_gain_changed(self):
        di = self._ccd_logic.get_availiable_values('AdcAnalogGain')
        val = di[self._mw.adc_analog_gain_comboBox.currentText()]
        self._ccd_logic.set_parameter_propagator('AdcAnalogGain', val)

    def shutter_timing_mode_changed(self):
        di = self._ccd_logic.get_availiable_values('ShutterTimingMode')
        val = di[self._mw.shutter_timing_mode_comboBox.currentText()]
        self._ccd_logic.set_parameter_propagator('ShutterTimingMode', val)

    def adc_speed_changed(self):
        val = float(self._mw.adc_speed_comboBox.currentText())
        self._ccd_logic.set_parameter_propagator('AdcSpeed', val)

    def vertical_shift_rate_changed(self):
        val = float(self._mw.vertical_shift_rate_comboBox.currentText())
        self._ccd_logic.set_parameter_propagator('VerticalShiftRate', val)

    def fill_interface_values(self):
        """
        Fills in available parameters for the selected camera and selects current/default values.
        """
        # for enumerated collections
        self._mw.adc_quality_comboBox.addItems(
            list(self._ccd_logic.get_availiable_values('AdcQuality').keys()))
        par = self._ccd_logic.get_parameter_propagator('AdcQuality')
        di = self._ccd_logic.get_availiable_values('AdcQuality')
        act = dict(map(reversed, di.items()))[par]
        self._mw.adc_quality_comboBox.setCurrentText(act)

        self._mw.adc_analog_gain_comboBox.addItems(
            list(self._ccd_logic.get_availiable_values('AdcAnalogGain').keys()))
        par = self._ccd_logic.get_parameter_propagator('AdcAnalogGain')
        di = self._ccd_logic.get_availiable_values('AdcAnalogGain')
        act = dict(map(reversed, di.items()))[par]
        self._mw.adc_analog_gain_comboBox.setCurrentText(act)

        self._mw.shutter_timing_mode_comboBox.addItems(
            list(self._ccd_logic.get_availiable_values('ShutterTimingMode').keys()))
        par = self._ccd_logic.get_parameter_propagator('ShutterTimingMode')
        di = self._ccd_logic.get_availiable_values('ShutterTimingMode')
        act = dict(map(reversed, di.items()))[par]
        self._mw.shutter_timing_mode_comboBox.setCurrentText(act)

        # for float things
        self._mw.adc_speed_comboBox.addItems(
            list(map(str, self._ccd_logic.get_availiable_values('AdcSpeed'))))
        par = self._ccd_logic.get_parameter_propagator('AdcSpeed')
        self._mw.adc_speed_comboBox.setCurrentText(str(par))

        self._mw.vertical_shift_rate_comboBox.addItems(
            list(map(str, self._ccd_logic.get_availiable_values('VerticalShiftRate'))))
        par = self._ccd_logic.get_parameter_propagator('VerticalShiftRate')
        self._mw.vertical_shift_rate_comboBox.setCurrentText(str(par))


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    ex = CCDMainWindow()
    sys.exit(app.exec_())
