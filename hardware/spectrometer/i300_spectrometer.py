# -*- coding: utf-8 -*-

"""
This hardware file contains control commands for Spectra pro i300 (300i) spectrometer (Princeton Instrument) via pyvisa.
Spectrometer is autocalibrating after powering off and on.
Backlash correction on negative moves performed automatically.

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

from core.module import Base, ConfigOption
from interface.spectrometer_interface import SpectrometerInterface
import visa
import time

class I300(Base, SpectrometerInterface):
    """
    Main class for i300 Princeton Instruments spectrometer.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    _modclass = 'i300'
    _modtype = 'hardware'

    _com_port_i300 = ConfigOption('com_port_i300', 'ASRL1::INSTR', missing='warn')

    _spectrometer_handle = None  # handle to spectrometer

    # Default parameters of the spectrometer needed for pixel -> wavelength conversion
    # grating can be specified automatically
    _grating = None             # Initialize grating variable, will be filled later
    _inclusion_angle = 30.3     # degrees (default value for i300 according to )
    _focal_length = 300         # mm

    # hrconnectlogic = Connector(interface='SpectrometerInterface')

    def on_activate(self):
        """ Activate module."""
        self.connect()
        self.delay = 0.3  # 0.3 sec delay between read/write
        time.sleep(self.delay)
        self.write_speed(1000)

    def on_deactivate(self):
        """ Deactivate module."""
        self.disconnect()

    def connect(self):
        """
        Connects to i300 spectrometer.
        """
        self.rm = visa.ResourceManager()
        try:
            self._spectrometer_handle = self.rm.open_resource(self._com_port_i300,
                                                              baud_rate=9600,
                                                              data_bits=8,
                                                              write_termination='\r',
                                                              read_termination=None)
        except:
            self.log.warning('Cannot connect to spectrometer! Check ports.')

    def disconnect(self):
        """ Closes serial connection with 300i spectrometer."""
        self._spectrometer_handle.close()

    def read_position_nm(self):
        """
        Read the absolute position in nm.
        :return: float wavelength in nm. Resolution is 0.01 nm.
        """
        time.sleep(self.delay)
        answer = self._spectrometer_handle.query('?NM')
        return float(answer.split()[1])

    def is_busy(self):
        """
        Read the status of spectrometer's motors.
        '1' - ready, '0' - busy.
        :return: Boolean True if busy.
        """
        time.sleep(self.delay)
        answer = self._spectrometer_handle.query('MONO-?DONE')
        if int(answer.split()[1]) == 1:
            return False
        elif int(answer.split()[1]) == 0:
            return True
        else:
            print('Error!: unknown byte type')

    # def goto_position_nm_busy(self, wavelength_nm):
    #     """
    #     Go to monochromator position in nm. Applies MONO-STOP after movement as requested in manual.
    #     Do not return control until movement is done.
    #     :param float wavelength_nm: Requested position. Reads only 3 symbols after dot.
    #     """
    #     time.sleep(self.delay)
    #     self._spectrometer_handle.query(f'{wavelength_nm} >NM')
    #
    #     while self.is_busy():
    #         time.sleep(self.delay)
    #     time.sleep(self.delay)
    #
    #     self._spectrometer_handle.query('MONO-STOP')

    def move_to_nm(self, wavelength_nm):
        """
        Moves the grating to requested position with backlash compensation for negative moves.
        Does not return control until arriving at specified wavelength.
        Uses huge timeout for slow speeds.
        :param float wavelength_nm: Requested position in nm
        """
        time.sleep(self.delay)
        self._spectrometer_handle.timeout = 600000  # ms
        self._spectrometer_handle.query(f'{wavelength_nm} NM')
        self._spectrometer_handle.timeout = 2000

    def read_speed(self):
        """
        Gets speed of monochromator in nm/min.
        """
        time.sleep(self.delay)
        answer = self._spectrometer_handle.query('?NM/MIN')
        return float(answer.split()[1])

    def write_speed(self, speed):
        """
        Set speed of the monochromator in nm/min.
        :param float speed: Desired speed
        """
        time.sleep(self.delay)
        self._spectrometer_handle.query(f'{speed} NM/MIN')

    def read_grating(self):
        """
        Read grating number and basic info of currently active grating.
        Returns list [number, number of lines/mm, string of basic information]
        """
        time.sleep(self.delay)
        self._spectrometer_handle.write('?GRATINGS')
        answer = []
        for x in range(0, 11):
            answer.append(self._spectrometer_handle.read())
        grating_number = [x.find('\x1a') for x in answer].index(0)  # find active grating by looking \x1a (right arrow)
        grating_splitstring = answer[grating_number].split()
        grating_lines = int(grating_splitstring[1])
        grating_info = f'Grating {grating_lines} lines/mm, blazed for {grating_splitstring[4]} nm'
        return [grating_number, grating_lines, grating_info]

    def set_grating(self, grating_number):
        """
        Set grating. Only gratings 1 2 3 (turret 1) available in our setup.
        :param grating_number: Number of requested grating.
        """
        time.sleep(self.delay)
        self._spectrometer_handle.timeout = 600000  # ms
        self._spectrometer_handle.query(f'{grating_number} GRATING')
        self._spectrometer_handle.timeout = 2000

# some methods for abstract class
    def recordSpectrum(self):
        pass

    def setExposure(self, exposure_time):
        pass

    def getExposure(self):
        pass