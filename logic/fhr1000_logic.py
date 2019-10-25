# -*- coding: utf-8 -*-

"""
This file contains logic to control FHR1000 HORIBA JOBIN YVON monochromator.
"""

from core.module import Connector, StatusVar
from core.util.mutex import Mutex
from core.util.network import netobtain
from logic.generic_logic import GenericLogic


class Fhr1000Logic(GenericLogic):
    """This logic module deals with FHR1000 spectrometer."""

    _modclass = 'fhr1000logic'
    _modtype = 'logic'

    # declare connectors
    hardware = Connector(interface='SpectrometerInterface')

    # status variables
    _current_wavelength_nm = None

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

    def on_deactivate(self):
        """ Deinitialisation performed during deactivation of the module."""
        pass

    def move_grating_nm(self, requested_position_nm):
        self._hardware.move_to_nm(requested_position_nm)
        self._current_wavelength_nm = self.read_grating_nm()

    def read_grating_nm(self):
        return self._hardware.read_position_nm()

    def read_slit_um(self):
        return self._hardware.read_slit_um()

    def move_slit_um(self, requested_slit_width_um):
        self._hardware.move_slit_absolute_um(requested_slit_width_um)

    #####################################
    # DEFINITIONS FROM HR640! TODO: REFACTOR THIS
    #####################################

    def read_wavelength_nm(self):
        return self.read_grating_nm()

    def move_to_nm(self, target_nm):
        self.move_grating_nm(target_nm)
        self._current_wavelength_nm = self.read_wavelength_nm()
