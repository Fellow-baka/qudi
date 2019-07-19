# -*- coding: utf-8 -*-

"""
This file contains hardware to control monochromator (hr640) for this case via serial interface.
THe spectrometer's controller have no energy independed memory to save mono position, so it should be saved in file.
"""

# qudi imports
from core.module import Base, ConfigOption
from interface.spectrometer_interface import SpectrometerInterface

# other imports
import visa
import time
import math
from itertools import chain
from scipy import optimize

#  all the commands to play with spectrometer is just binary sequences which we transfer through RS232 by pyvisa
#  load absolute: 65 [three meaningful bytes]
#  load target: 84 [three meaningful bytes]
#  read absolute: 97 [three meaningful bytes]
#  read target: 116 [three meaningful bytes]
#  go : 71
#  load speed: 83 [two meaningful bytes]
#  read speed: 115 [two meaningful bytes]
#  busy: [58,2,0,0,63,58]

# convert from bytes to wavelength in angstrom
# TODO: compensate for 0.08 nm backlash
# TODO: test different wait times for serial communication with HR
# TODO: Should remove all the read_position() checks by saving current position in global variable somewhere? self.?
# TODO: Check the extreme values of input parameters
# TODO: Flush input/output!


class Hr640(Base, SpectrometerInterface):
    """Main class for HR640 Jobin Yvon spectrometer
       Every load_ method ending with read to empty buffer.
    """
    # def __init__(self):
    #     # empty handle
    #     self.mono = None
    #     self.port = 'COM1'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    _modclass = 'hr640'
    _modtype = 'hardware'

    _spectrometer_handle = None  # handle to spectrometer

    # hrconnectlogic = Connector(interface='SpectrometerInterface')

    # Default parameters of the spectrometer needed for pixel -> wavelength conversion
    _grating = ConfigOption('grating', 1200, missing='warn')  # lines/mm
    _inclusion_angle = 17.351  # degrees
    _focal_length = 640  # mm

    def on_activate(self):
        """ Activate module."""
        # self.connect()
        self.connect()
        self.delay = 0.1  # 0.1 sec delay between read/write and byte sequences
        # self._hr_logic = self.hrconnectlogic()  # logic module
        self.load_speed_bytes()

    def on_deactivate(self):
        """ Deactivate module."""
        self.disconnect()

    def connect(self, port='ASRL1::INSTR'):
        """
        Connects to spectrometer creating global variable. No termination is used.
        :param string port: Serial port to connect.
        """
        self.rm = visa.ResourceManager()
        try:
            self._spectrometer_handle = self.rm.open_resource(port, baud_rate=4800, data_bits=8,
                                                              write_termination=None, read_termination=None)
        except:
            self.log.warning('Cannot connect to instrument! Check ports. ')

    def disconnect(self):
        """ Closes serial connection with HR640. """
        self._spectrometer_handle.close()

    def convert_from_bytes_to_nm(self, wavelength_bytes):
        """
        Convert from byte array to wavelength in nm.
        :param list wavelength_bytes: decimal byte array.
        :return: wavelength in nanometers.
        """
        wavelength_bytes = wavelength_bytes[::-1]
        return (wavelength_bytes[0] * 65536 + wavelength_bytes[1]
                * 256 + wavelength_bytes[2]) / 1000

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

    def read_position_bytes(self):
        """
        Read the absolute position in bytes.
        :return: byte list of wavelength.
        """
        arr = [58, 2, 97, 3, 63, 63, 63, 58]
        for i in arr:
            self._spectrometer_handle.write_raw(bytes([i]))
            time.sleep(self.delay)
        read = self._spectrometer_handle.read_bytes(8)
        time.sleep(self.delay)
        return [read[4], read[5], read[6]]

    def read_position_nm(self):
        """
        Read the absolute position in nm.
        :return: float wavelength in nm.
        """
        return self.convert_from_bytes_to_nm(self.read_position_bytes())

    def read_target_bytes(self):
        """
        Read the target position in bytes.
        :return: byte list of wavelength of target position.
        """
        arr = [58, 2, 116, 3, 63, 63, 63, 58]
        for i in arr:
            self._spectrometer_handle.write_raw(bytes([i]))
            time.sleep(self.delay)
        read = self._spectrometer_handle.read_bytes(8)
        time.sleep(self.delay)
        return [read[4], read[5], read[6]]

    def read_target_nm(self):
        """
        Read the target position in nm.
        :return: float wavelength of target in nm.
        """
        return self.convert_from_bytes_to_nm(self.read_target_bytes())

    def is_busy(self):
        """
        Read the status of spectrometer by testing fifth byte.
        Small 'b' - ready, big 'B' - busy.
        :return: Boolean True if busy.
        """
        arr = [58, 2, 0, 0, 63, 58]
        for i in arr:
            self._spectrometer_handle.write_raw(bytes([i]))
            time.sleep(self.delay)
        read = self._spectrometer_handle.read_bytes(6)
        time.sleep(self.delay)
        if read[4] == 98:
            return False
        elif read[4] == 66:
            return True
        else:
            print('Error!: unknown byte type')

    def read_speed_bytes(self):
        """
        Read speed in bytes by reading 5 and 6 bytes.
        :return: byte list of the speed # TODO: return as nm/min?
        """
        arr = [58, 2, 115, 2, 63, 63, 58]
        for i in arr:
            self._spectrometer_handle.write_raw(bytes([i]))
            time.sleep(self.delay)
        read = self._spectrometer_handle.read_bytes(7)
        time.sleep(self.delay)
        return [read[4], read[5]]

    def load_position_bytes(self, wavelength_bytes):
        """
        Load absolute position as a list of bytes.
        :param list wavelength_bytes: list of bytes.
        """
        arr = [58, 2, 65, 3] + wavelength_bytes + [58]
        for i in arr:
            self._spectrometer_handle.write_raw(bytes([i]))
            time.sleep(self.delay)
        self._spectrometer_handle.read_bytes(7)
        time.sleep(self.delay)

    def load_position_nm(self, wavelength_nm):
        """
        Load absolute position.
        :param float wavelength_nm: float in nm.
        """
        wavelength_bytes = self.convert_from_nm_to_bytes(wavelength_nm)
        arr = [58, 2, 65, 3] + wavelength_bytes + [58]
        for i in arr:
            self._spectrometer_handle.write_raw(bytes([i]))
            time.sleep(self.delay)
        self._spectrometer_handle.read_bytes(8)
        time.sleep(self.delay)

    def load_target_bytes(self, wavelength_bytes):
        """
        Load target as a float in nm.
        :param list wavelength_bytes: list of bytes as a target position.
        """
        arr = [58, 2, 84, 3] + wavelength_bytes + [58]
        for i in arr:
            self._spectrometer_handle.write_raw(bytes([i]))
            time.sleep(self.delay)
        self._spectrometer_handle.read_bytes(8)
        time.sleep(self.delay)

    def load_target_nm(self, wavelength_nm):
        """
        Load position as a float in nm.
        :param float wavelength_nm: target position in nm.
        """
        wavelength_bytes = self.convert_from_nm_to_bytes(wavelength_nm)
        arr = [58, 2, 84, 3] + wavelength_bytes + [58]
        for i in arr:
            self._spectrometer_handle.write_raw(bytes([i]))
            time.sleep(self.delay)
        self._spectrometer_handle.read_bytes(8)
        time.sleep(self.delay)

    def load_speed_bytes(self, speed_bytes=[60, 0]):
        """
        Load speed using list of bytes.
        (max speed = 42000 nm min / Desired speed) to two bytes
        :param list speed_bytes: speed. Default value [60, 0] should be ok.
        """
        arr = [58, 2, 83, 2] + speed_bytes + [58]
        for i in arr:
            self._spectrometer_handle.write_raw(bytes([i]))
            time.sleep(self.delay)
        self._spectrometer_handle.read_bytes(7)
        time.sleep(self.delay)

    def go(self):
        """ Start moving to target. Returns control immediately. """
        arr = [58, 2, 71, 0, 58]
        for i in arr:
            self._spectrometer_handle.write_raw(bytes([i]))
            time.sleep(self.delay)
        self._spectrometer_handle.read_bytes(5)
        time.sleep(self.delay)

    def go_busy(self):
        """ Start moving to target. Prints stuff while busy. """
        arr = [58, 2, 71, 0, 58]
        for i in arr:
            self._spectrometer_handle.write_raw(bytes([i]))
            time.sleep(self.delay)
        print("Moving", end="")
        self._spectrometer_handle.read_bytes(5)
        time.sleep(self.delay)
        while self.is_busy():
            time.sleep(self.delay)
            print(".", end="")

    def get_absolute_position_from_file(self, path='C:/Users/pwalbers/PycharmProjects/HR640/spectralink.pos'):
        """
        Get an absolute position from the second line of 'spectralink.pos' file.
        Read it as float and convert to nm by dividing to 10 (number in file in angstrom)
        :param string path: Path to .pos file
        :return float: Absolute position in nm.
        """
        with open(path, "r") as pos:
            dat = pos.readlines()
        return float(dat[1].strip()) / 10

    def put_absolute_position_to_file(self, wavelength_nm, path='C:/Users/pwalbers/PycharmProjects/HR640/spectralink.pos'):
        """
        Put current absolute position to the second line of 'spectralink.pos' file.
        Put it as float and convert to A by multiplying to 10 (number in file in angstrom!)
        :param float wavelength_nm: Absolute position of spectrometer.
        :param string path: Path to .pos file
        :return float: Absolute position in nm.
        """
        wavelength_a = round(wavelength_nm*10, 3)
        with open(path, "w+") as out:
            out.writelines(["Absolute position for HR640 monochromator:\n", str(wavelength_a)])

    def get_coefficients_from_file(self, path='C:/Users/pwalbers/PycharmProjects/HR640/spectralink.cal'):
        """
        Get the coefficients from file 'spectralink.cal' for cubic parabola, return list of floats
        :param string path: Path to .cal file
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
        :return float: absolute position in nanometers
        """
        coeffs = self.get_coefficients_from_file('spectralink.cal')
        return optimize.newton(
            lambda x: coeffs[0] + coeffs[1] * x + coeffs[2] * x ** 2 + coeffs[3] * x ** 3 - wavelength_nm * 10,
            5000) / 10  # nm to A

    def move_to_nm(self, wavelength_nm):
        """
        Move grating to the specified position
        :param wavelength_nm: target wavelength to move to
        """
        target = self.wavelength_to_absolute_position(wavelength_nm)
        self.load_target_nm(target)
        position_now = self.read_position_nm()
        if position_now < wavelength_nm:
            self.load_target_nm(wavelength_nm-1)
            self.go_busy()
        elif position_now > wavelength_nm:
            self.go_busy()
        else:
            pass

# some methods for abstract class
    def recordSpectrum(self):
        pass

    def setExposure(self, exposure_time):
        pass

    def getExposure(self):
        pass
