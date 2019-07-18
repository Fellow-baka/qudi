# -*- coding: utf-8 -*-

"""

This hardware file contains control commands for FHR1000 spectrometer (HORIBA JOBIN YVON) but can be used to
control any TRIAX spectrometer via serial interface using pyvisa.
Before starting this code connect/initialize spectrometer via 'Hardware Configuration and Control' utility from
JOBIN YVON. It will automatically

"""

# qudi imports
from core.module import Base, Connector
from interface.spectrometer_interface import SpectrometerInterface

# other imports
import visa
import time
import math
from itertools import chain
from scipy import optimize

# all the commands to play with spectrometer is just ascii sequences which we transfer through RS232 by pyvisa
# read position in nm: "Z62"     Examples:     Input: "Z62,0\r"              Output: "o546.074\r"
# load position in nm: "Z61"     Examples:     Input: "Z62,0,500.0\r"        Output: "o" (note absence of "\r"!)
# test if motors are busy: "E"   Examples:     Input: "E\r"                  Output: "oz" is not "oq" is busy
# read slit position: "j"        Examples:     Input: "j0,0\r"               Output: "o100\r"
# move slit relative: "k"        Examples:     Input: "k0,0,200\r"           Output: "o"

# TODO: allow to change port in config file


class Fhr1000(Base, SpectrometerInterface):
    """Main class for FHR1000 HORIBA Jobin Yvon spectrometer
       Every load_ method ending with read to empty buffer.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    _modclass = 'fhr1000'
    _modtype = 'hardware'

    _spectrometer_handle = None  # handle to spectrometer

    # hrconnectlogic = Connector(interface='SpectrometerInterface')

    def on_activate(self):
        """ Activate module."""
        # self.connect()
        self.connect()
        self.delay = 0.3  # 0.3 sec delay between read/write is recommended by manual

    def on_deactivate(self):
        """ Deactivate module."""
        self.disconnect()

    def connect(self, port='ASRL1::INSTR'):
        """
        Connects to spectrometer.
        :param string port: Serial port to connect. Default port is COM1.
        """
        # TODO: Test "A" command for auto initialization without JOBIN YVON hardware thingy
        self.rm = visa.ResourceManager()
        try:
            self._spectrometer_handle = self.rm.open_resource(port, baud_rate=19200, data_bits=8,
                                                              write_termination='\r', read_termination='\r')
        except:
            self.log.warning('Cannot connect to spectrometer! Check ports.')

    def disconnect(self):
        """ Closes serial connection with FHR1000."""
        self._spectrometer_handle.close()

    def initialize(self):
        """Auto initialize spectrometer. It can take over a minute thus timeout is increased to 100 s"""
        self._spectrometer_handle.timeout = 100000
        self._spectrometer_handle.write("A")
        time.sleep(self.delay)
        self._spectrometer_handle.read_bytes(1)
        self._spectrometer_handle.timeout = 2000
        time.sleep(self.delay)

    def read_position_nm(self):
        """
        Read the absolute position in nm.
        :return: float wavelength in nm.
        """
        time.sleep(self.delay)
        return float(self._spectrometer_handle.query('Z62,0')[1:])  # strip first symbol 'o' in answer

    def is_busy(self):
        """
        Read the status of spectrometer's motors.
        'z' - ready, 'q' - busy.
        :return: Boolean True if busy.
        """
        time.sleep(self.delay)
        self._spectrometer_handle.write('E')
        time.sleep(self.delay)
        answer = self._spectrometer_handle.read_bytes(2)[1]
        if  answer == 122:
            return False
        elif answer == 113:
            return True
        else:
            print('Error!: unknown byte type')
        time.sleep(self.delay)

    def goto_position_nm_busy(self, wavelength_nm):
        """
        Go to monochromator position in nm and flush output by reading single byte.
        Do not return control until movement is done.
        :param float wavelength_nm: Requested position
        """
        time.sleep(self.delay)
        self._spectrometer_handle.write(f'Z61,0,{wavelength_nm}')
        time.sleep(self.delay)
        self._spectrometer_handle.read_bytes(1)
        while self.is_busy():
            time.sleep(self.delay)
        time.sleep(self.delay)

    def move_to_nm(self, wavelength_nm):
        """
        Moves the grating to requested position with backlash compensation.
        :param float wavelength_nm: Requested position
        """
        # TODO: Round to third(?) number to no move motor if position is the same
        time.sleep(self.delay)
        current_position_nm = round(self.read_position_nm(), 2)  # round due to the finite precision of

        if current_position_nm < wavelength_nm:
            time.sleep(self.delay)
            self.goto_position_nm_busy(wavelength_nm)
        elif current_position_nm > wavelength_nm:
            time.sleep(self.delay)
            self.goto_position_nm_busy(wavelength_nm - 5)
            time.sleep(self.delay)
            self.goto_position_nm_busy(wavelength_nm)
        else:
            self.log.info('No shift, the position is the same.')

    def read_slit_steps(self):
        time.sleep(self.delay)
        return float(self._spectrometer_handle.query('j0,0')[1:])  # strip first symbol 'o' in answer

    def read_slit_um(self):
        """
        Read current slit width. 1 step = 2 um.
        :return: Slit width in micrometers.
        """
        time.sleep(self.delay)
        return float(self._spectrometer_handle.query('j0,0')[1:])*2  # strip first symbol 'o' in answer

    def move_slit_relative_steps(self, requested_slit_steps):
        """
        Relative movement of the slits. Positive number is opening of the slit, negative is closing.
        :param gap_steps: Steps to move. For 270M & HR460 2mm slits one step = 2 micrometer gap
        :return:
        """
        time.sleep(self.delay)
        self._spectrometer_handle.write(f'k0,0,{requested_slit_steps}')
        time.sleep(self.delay)
        self._spectrometer_handle.read_bytes(1)
        while self.is_busy():
            time.sleep(self.delay)

    def move_slit_absolute_um(self, requested_slit_um):
        """
        Move slits to specified absolute position. Perform backlash correction (200 steps)
        for negative moves. If slit is less than 100 um go to 0 and then to requested slit.
        :param requested_slit_um: Requested width in micrometers.
        """
        # TODO: accept only even numbers of requested slit width, since steps are discrete.
        # TODO: refactor using only um, not steps
        time.sleep(self.delay)
        current_slit_um = self.read_slit_steps()*2
        time.sleep(self.delay)
        if 0 <= requested_slit_um <= 2000:
            if requested_slit_um > current_slit_um:
                self.move_slit_relative_steps((requested_slit_um-current_slit_um)/2)
            elif current_slit_um > requested_slit_um >= 100:
                self.move_slit_relative_steps(((requested_slit_um - current_slit_um) / 2) - 50)
                self.move_slit_relative_steps(50)
            elif current_slit_um > requested_slit_um < 100:
                self.move_slit_relative_steps(-current_slit_um / 2)
                self.move_slit_relative_steps(requested_slit_um / 2)
            else:
                pass
        else:
            self.log.warning("Wrong slit is requested! 0-2000 um is acceptable.")

# some methods for abstract class
    def recordSpectrum(self):
        pass

    def setExposure(self, exposure_time):
        pass

    def getExposure(self):
        pass
