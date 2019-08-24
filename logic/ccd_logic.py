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
from collections import OrderedDict

from core.module import Connector, StatusVar
from logic.generic_logic import GenericLogic
from qtpy import QtCore


class CCDLogic(GenericLogic):
    """ Logic module agreggating multiple hardware switches.
    """
    _modclass = 'ccd'
    _modtype = 'logic'

    simpledata = Connector(interface='SimpleDataInterface')
    monochromator = Connector(interface='CCDLogic')
    savelogic = Connector(interface='SaveLogic')

    sigRepeat = QtCore.Signal()
    sigAquired = QtCore.Signal()

    sigUpdateDisplay = QtCore.Signal()
    sigAcquisitionFinished = QtCore.Signal()
    sigVideoFinished = QtCore.Signal()

    # different variables
    _focus_exposure = StatusVar(default=0.1)
    _acquisition_exposure = StatusVar(default=0.1)
    _constant_background = StatusVar(default=0)
    _mode = StatusVar(default='1D')  # Var defining spectra/image mode
    _ccd_offset_nm = StatusVar(default=0.0)
    _laser_power_mW = StatusVar(default=0.0)
    _x_flipped = StatusVar(default=False)
    _roi = StatusVar(default=[])
    _raw_data_dict = OrderedDict()
    _proceed_data_dict = OrderedDict()

    def on_activate(self):
        """ Prepare logic module for work.
        """
        self._hardware = self.simpledata()
        self._mono = self.monochromator()
        self._save_logic = self.savelogic()

        self.resolution_x = self._hardware.get_size()[0]
        self.resolution_y = self._hardware.get_size()[1]
        # self._roi = [0, self.resolution_x, 1, 0, self.resolution_y, 1]

        self.stopRequest = False
        self.sigRepeat.connect(self.focus_loop, QtCore.Qt.QueuedConnection)

        # Apply all status vars to camera
        self.set_parameter("focus_exposure", self._focus_exposure)
        self.set_parameter("acquisition_exposure", self._acquisition_exposure)
        self._hardware.send_configuration()

    def on_deactivate(self):
        """ Deactivate module.
        """
        self.module_state.unlock()
        self.stop_focus()

    def start_single_acquisition(self):
        """Get single spectrum from hardware"""
        # self.module_state.lock()
        self._hardware._exposure = self._acquisition_exposure
        self._hardware.start_single_acquisition()
        self._raw_data_dict['Pixels'] = np.arange(self._roi[0]+1, self._roi[1]+1, 1)
        self._raw_data_dict['Counts'] = self._hardware.get_acquired_data()
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
        self._raw_data_dict['Counts'] = self._hardware.get_acquired_data()
        self.sigRepeat.emit()

    def set_parameter(self, par, value):
        self.log.info(f"Changing parameter {par} to value {value}")
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

    def set_parameter_propagator(self, par, value):
        """
        Propagate chane of parameter directly to camera
        :param par:
        :param value:
        :return:
        """
        self._hardware.set_parameter(par, value)
        self._hardware.send_configuration()

    def get_parameter_propagator(self, par):
        """
        Propagate chane of parameter directly to camera
        :return:
        """
        return self._hardware.get_parameter(par)

    def convert_from_pixel_to_nm(self, pixels, w_mid_nm, offset_nm=0):
        """
        Creates list of wavelengts to plot spectra/image in gui.
        Asks CCD for the size of the chip and pixel size.
        Asks monochromator for inclusion angle, grating, diffraction order and focal length.
        Works only with full chip x.
        Output in nm.
        TODO: Make it possible to work with arbitrary number of pixels.
        TODO: Ask hardware details from monochromtor.
        :param ndarray pixels: Array of pixels.
        :param float w_mid_nm: Wavelength at the middle of ccd in nm. Corresponds to position of the grating.
        :param float offset_nm: Offset in nanometers.
        """
        # d = 1 / (self._hardware._grating * 1000)  # distance between lines of the grating
        # incluison = np.deg2rad(self._hardware._inclusion_angle)
        # f = self._hardware._focal_length
        d = 1 / (1200 * 1000)  # distance between lines of the grating
        inclusion = np.deg2rad(17.351)
        f = 640
        x = self._hardware.get_parameter("PixelWidth") / 1000  # um -> mm
        m = 1  # diffraction order
        delta = 0  # deviation of the CCD from the plane, will be used later
        w_mid_m = w_mid_nm * 1e-9  # nm -> m
        pixels = pixels - self.resolution_x // 2  # Kinda select pixels from the middle of ccd

        xi = [np.arctan((n * x * np.cos(delta))/(f + n * x * np.sin(delta))) for n in pixels]
        psi = np.arcsin((m * w_mid_m)/(2 * d * np.cos(inclusion/2)))
        alpha = psi - inclusion / 2
        beta_prime = [psi + inclusion / 2 + xi_n for xi_n in xi]

        w_prime = [(d / m) * (np.sin(alpha) + np.sin(beta_prime_n)) * 1e9 + offset_nm for beta_prime_n in beta_prime]

        return w_prime

    def convert_energy_units(self, data_array=[], out_unit="Wavelength (nm)"):
        """
        Converts received array in nm to array in other units.
        :param out_unit: Target units
        :param data_array: array of values in nm needed to be converted to target units.
        :return: Array of the target units
        """
        if out_unit == "Pixels":
            return self._raw_data_dict['Pixels']
        elif out_unit == "Wavelength (nm)":
            return data_array
        elif out_unit == "Raman shift (cm-1)":
            laserline_nm = self._mono.laserline
            return [(1 / laserline_nm - 1 / x) * 1e7 for x in data_array]
        elif out_unit == "Energy (eV)":
            return [1239.84193 / x for x in data_array]
        elif out_unit == "Energy (meV)":
            return [(1239.84193 / x) * 1000 for x in data_array]
        elif out_unit == "Wavenumber (cm-1)":
            return [1e7 / x for x in data_array]
        elif out_unit == "Frequency (THz)":
            return [299_792.458 / x for x in data_array]
        elif out_unit == "Energy RELATIVE (meV)":
            laserline_nm = self._mono.laserline
            return [(1 / laserline_nm - 1 / x) * 1e7 / 8.06554 for x in data_array]
        elif out_unit == "Frequency RELATIVE (THz)":
            laserline_nm = self._mono.laserline
            return [(1 / laserline_nm - 1 / x) * 1e7 / 33.35641 for x in data_array]

    def get_availiable_values(self, param):
        return self._hardware.get_availiable_values(param)

    def save_data(self, name_tag='', custom_header=None):
        """
        :param string name_tag: postfix name tag for saved filename.
        :param OrderedDict custom_header:
        :return:
            This ordered dictionary is added to the default data file header. It allows arbitrary
            additional experimental information to be included in the saved data file header.
        """
        filepath = self._save_logic.get_path_for_module(module_name='spectroscopy')

        # TODO: introduce some real and additional parameters
        parameters = OrderedDict()
        parameters['Exposure (s)'] = self._acquisition_exposure
        parameters['Constant background (Counts)'] = self._constant_background
        parameters['CCD offset (nm)'] = self._ccd_offset_nm
        parameters['Is X-axis flipped'] = self._x_flipped
        parameters['Region of interest (ROI)'] = self._roi
        parameters['Position of monochromator (nm)'] = self._mono._current_wavelength_nm
        parameters['Excitation line (nm)'] = self._mono.laserline

        # add any custom header params
        if custom_header is not None:
            for key in custom_header:
                parameters[key] = custom_header[key]

        # self._proceed_data_dict.popitem('Pixels')
        pro = self._proceed_data_dict

        data = OrderedDict()
        x_axis_list = ['Pixels',
                       'Wavelength (nm)',
                       'Raman shift (cm-1)',
                       'Energy (eV)',
                       'Energy (meV)',
                       'Wavenumber (cm-1)',
                       'Frequency (THz)',
                       "Energy RELATIVE (meV)",
                       "Frequency RELATIVE (THz)"]
        y_axis_list = ['Counts', 'Counts / s', 'Counts / (s * mW)']

        if self._mode == '1D':
            filelabel = 'spectrum'
            data.update({k: v for (k, v) in pro.items() if k in x_axis_list})
            data.update({k: v[0] for (k, v) in pro.items() if k in y_axis_list})  # v[0] for 1D representation
        else:
            filelabel = 'image'
            data.update({k: v for (k, v) in pro.items() if k in x_axis_list})
            data['Counts'] = np.flipud(np.rot90(self._proceed_data_dict['Counts']))

        # Add name_tag as postfix to filename
        if name_tag != '':
            filelabel = filelabel + '_' + name_tag

        self._save_logic.save_data(data,
                                   filepath=filepath,
                                   parameters=parameters,
                                   filelabel=filelabel)
        self.log.debug('Spectrum saved to:\n{0}'.format(filepath))

    def correct_background(self, data, background):
        """
        Corrects spectra for background. TODO: add correction for background spectra
        :param data: Numpy array of the input data.
        :param background: Constant background value.
        :return: Numpy array of corrected data.
        """
        return data - background

    def convert_data(self, data, target_units):
        """
        Converts data from nanometers to target units.
        :param data: Array of data in nm.
        :param target_units: Requested units.
        :return:
        """
        pass

    def flip_data(self, data):
        if data.shape[0] == 1:
            self._proceed_data_dict['Counts'] = np.fliplr(data)
        else:
            self._proceed_data_dict['Counts'] = np.flipud(data)

    def flip_datar(self, data):
        if self._x_flipped:
            if data.shape[0] == 1:
                return np.fliplr(data)
            else:
                return np.flipud(data)
        else:
            return data

    def normalize_data(self, data, out_units):
        if out_units == 'Counts':
            return data
        elif out_units == 'Counts / s':
            return data / self._acquisition_exposure
        elif out_units == 'Counts / (s * mW)':
            return data / self._acquisition_exposure / self._laser_power_mW

    def get_monochromator_parameters(self):
        pass

    def convert_spectra(self, x_axis, y_axis):
        """
        Converts raw spectra (Counts vs pixels) to proceed
        :param x_axis: string of requested units for x-axis
        :param y_axis: string of requested units for y-axis
        :return: Ordered dictionary of requested units
        """
        self._proceed_data_dict = OrderedDict()

        wavelength_middle = self._mono._current_wavelength_nm
        pixels = self._raw_data_dict['Pixels']
        offset = self._ccd_offset_nm
        nm = self.convert_from_pixel_to_nm(pixels, wavelength_middle, offset)
        converted_x = self.convert_energy_units(nm, x_axis)
        self._proceed_data_dict[x_axis] = np.array(converted_x)

        counts = self._raw_data_dict['Counts']
        background_corr = self.correct_background(counts, self._constant_background)
        flipped = self.flip_datar(background_corr)
        converted_y = self.normalize_data(flipped, y_axis)
        self._proceed_data_dict[y_axis] = converted_y

        return self._proceed_data_dict

