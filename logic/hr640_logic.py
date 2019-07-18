# -*- coding: utf-8 -*-

"""
This file contains logic to control monochromator (hr640) for this case.
"""

# TODO: add paths to calibration and position files as options for config
# TODO: smth wrong

from core.module import Connector, StatusVar
from core.util.mutex import Mutex
from core.util.network import netobtain
from logic.generic_logic import GenericLogic
from itertools import chain
from scipy import optimize
import math


class Hr640Logic(GenericLogic):
    """This logic module deals with hr640 spectrometer."""

    _modclass = 'hr640logic'
    _modtype = 'logic'

    absolute_position = 555
    # declare connectors
    hardware = Connector(interface='SpectrometerInterface')

    # status variables

    def __init__(self, **kwargs):
        """ Create SpectrometerLogic object with connectors.

          @param dict kwargs: optional parameters
        """
        super().__init__(**kwargs)

        # locking for thread safety
        self.threadlock = Mutex()

    def on_activate(self):
        """ Prepare module for work / initialize stuff"""

        self._hardware = self.hardware()

        # read position/coefficients from file
        self.laserline = 488.0
        self.absolute_position = self.get_absolute_position_from_file()
        self.coeffs = self.get_coefficients_from_file()

        # self.wavelength = self.absolute_position_to_wavelength(self.absolute_position)

    def on_deactivate(self):
        """ Deinitialisation performed during deactivation of the module."""
        pass

    def convert_from_nm_to_bytes(self, wavelength_nm):
        """
        Convert from wavelength in nm to byte array.
        :param float wavelength_nm: wavelength in nanometers.
        :return: decimal byte list
        """
        w = wavelength_nm * 1000
        b = [0, 0, 0]
        b[0] = math.floor(w / 65536)  # LSB
        b[1] = math.floor((w - b[0] * 65536) / 256)  # ISB
        b[2] = math.floor((w - b[0] * 65536 - b[1] * 256))  # MSB
        return b[::-1]  # change byte order

    def get_absolute_position_from_file(self,
                                        path='C:/Users/pwalbers/PycharmProjects/qudi/calibration/spectralink.pos'):
        """
        Get an absolute position from the second line of 'spectralink.pos' file.
        Read it as float and convert to nm by dividing to 10 (number in file in angstrom)
        :param string path: Path to .pos file #
        :return float: Absolute position in nm.
        """
        with open(path, "r") as pos:
            dat = pos.readlines()
        return float(dat[1].strip()) / 10

    def put_absolute_position_to_file(self, absolute_position_nm,
                                      path='C:/Users/pwalbers/PycharmProjects/qudi/calibration/spectralink.pos'):
        """
        Put current absolute position to the second line of 'spectralink.pos' file.
        Put it as float and convert to A by multiplying to 10 (number in file in angstrom!)
        :param float wavelength_nm: Absolute position of spectrometer.
        :param string path: Path to .pos file
        :return float: Absolute position in nm.
        """
        wavelength_a = round(absolute_position_nm * 10, 3)
        with open(path, "w+") as out:
            out.writelines(["Absolute position for HR640 monochromator:\n", str(wavelength_a)])

    def get_coefficients_from_file(self, path='C:/Users/pwalbers/PycharmProjects/qudi/calibration/spectralink.cal'):
        """
        Get the coefficients from file 'spectralink.cal' for cubic parabola, return list of floats
        :param string path: Path to .cal file TODO: allow to configure path from config
        :return list: Floats as coefficients for equation.
        """
        with open(path) as f:
            dat = f.readlines()
        dat = list(map(str.strip, dat[4:8]))  # strip all the lines, take only coefficients
        dat = list(map(str.split, dat))  # split
        dat = list(chain.from_iterable(dat))
        coeffs = []
        for t in dat:
            try:
                coeffs.append(float(t))
            except ValueError:
                pass
        return coeffs

    def absolute_position_to_wavelength(self, wavelength_nm):
        """
        Apply calibration from file, input in nm, output in nm.
        Input is absolute position, output is corresponding wavelength.
        COEFFICIENT FOR VALUE IN ANGSTROM!
        :param float wavelength_nm: wavelength in nanometers
        :return float:
        """
        coeffs = self.get_coefficients_from_file()
        x = wavelength_nm * 10
        return (coeffs[0] + x * coeffs[1] + x * x * coeffs[2] + x * x * x * coeffs[3]) / 10

    def wavelength_to_absolute_position(self, wavelength_nm):
        """
        Apply calibration to get the absolute position of spectrometer by optimizing cubic equation
        :param float wavelength_nm: wavelength in nanometers
        :param list coeffs: list of coefficients for applying calibration
        :return float: absolute position in nanometers
        """
        return optimize.newton(
            lambda x: self.coeffs[0] + self.coeffs[1] * x + self.coeffs[2] * x ** 2
            + self.coeffs[3] * x ** 3 - wavelength_nm * 10, 5000) / 10  # nm to A

    #####################################
    # interaction with gui and instrument
    #####################################

    def get_from_file(self):
        self.log.warning('Read button Pressed!')
        # self.absolute_position = self.get_absolute_position_from_file()
        self.log.warning(self._hardware.read_position_nm())

    def ask_busy(self):
        self.log.warning('Busy button Pressed!')
        self.log.warning(self._hardware.is_busy())

    def load_position(self):
        self._hardware.load_position_nm(self.absolute_position)

    # TODO: change the direction of backlash compensation
    def move_to_nm(self, target_nm):
        """ With backlash compensation if target have lower wavelength than absolute position. """
        if target_nm < self.absolute_position:
            self._hardware.load_target_nm(target_nm - 0.5)
            self._hardware.go_busy()
            self.absolute_position = target_nm
            self._hardware.load_target_nm(target_nm)
            self._hardware.go_busy()
            self.absolute_position = target_nm
        elif target_nm > self.absolute_position:
            self._hardware.load_target_nm(target_nm)
            self._hardware.go_busy()
            self.absolute_position = target_nm
        else:
            pass
