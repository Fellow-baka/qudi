# -*- coding: utf-8 -*-

"""
This file contains logic to control acton i300 and 2300 Princeton Instruments monochromators.
"""

from core.module import Connector, StatusVar
from core.util.mutex import Mutex
from core.util.network import netobtain
from logic.generic_logic import GenericLogic


class I300Logic(GenericLogic):
    """This logic module deals with i300 spectrometer."""

    _modclass = 'i300logic'
    _modtype = 'logic'

    # declare connectors
    hardware = Connector(interface='SpectrometerInterface')

    # status variables
    _current_wavelength_nm = None
    _current_grating_lines = None

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

        self.laserline = 488.0

        self._current_wavelength_nm = self.read_wavelength_nm()
        self._current_grating_lines = self._hardware.read_grating()[1]

    def on_deactivate(self):
        """ Deinitialisation performed during deactivation of the module."""
        pass

    def move_grating_nm(self, requested_position_nm):
        self._hardware.move_to_nm(requested_position_nm)
        self._current_wavelength_nm = self.read_grating_nm()

    def read_grating_nm(self):
        return self._hardware.read_position_nm()

    def read_slit_um(self):
        # TODO: remove this for i300
        # there is no automatic slit
        # return self._hardware.read_slit_um()
        pass

    def move_slit_um(self, requested_slit_width_um):
        # TODO: remove this for i300
        # there is no automatic slit
        # self._hardware.move_slit_absolute_um(requested_slit_width_um)
        pass

    def set_grating(self, grating_number):
        self._hardware.set_grating(grating_number)
        self._current_grating_lines = self._hardware.read_grating()[1]

    #####################################
    # DEFINITIONS FROM HR640 (and FHR1000 after)! TODO: REFACTOR THIS
    #####################################

    def read_wavelength_nm(self):
        return self.read_grating_nm()

    def move_to_nm(self, target_nm):
        self.move_grating_nm(target_nm)
        self._current_wavelength_nm = self.read_wavelength_nm()
