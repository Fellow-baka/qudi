# -*- coding: utf-8 -*-
"""
This module controls the Oxford Instruments Mercury iTC temperature controller.
In current state supports only single temperature sensor and single heater (no flow control, pressure sensor, etc).

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

# System commands are used for system-level settings:
# |     Commands     |            Options            | Read/Write |                    Description                     |
# |------------------|-------------------------------|------------|----------------------------------------------------|
# | SYS CAT          |                               | R          | Returns a list of existing hardware devices        |
# | SYS DISP DIMA    | OFF:ON                        | R/W        | Set automatic display brightness                   |
# | SYS DISP DIMT    | 0-10                          | R/W        | Sets the time for the automatic dimming            |
# | SYS DISP BRIG    | 0-100                         | R/W        | Sets the brightness                                |
# | SYS MAN HVER     |                               | R          | Reads Hardware version of the Box                  |
# | SYS MAN HVER     |                               | R          | Reads Hardware version of the Box                  |
# | SYS MAN FVER     |                               | R          | Cryosys version                                    |
# | SYS MAN SERL     |                               | R          | Serial number of the box                           |
# | SYS TIME         | hh:mm:ss                      | R/W        | Sets the time of the box                           |
# | SYS DATE         | yyyy:MM:dd                    | R/W        | Sets the date of the box                           |
# | SYS USER         | NONE:GUEST:NORM:ENG           | R/W        | Set remote usr lvl (a pass may be required after!) |
# | SYS PASS         |                               | W          | Sets a new password for the present user level     |
# | SYS LOCK         | OFF:SOFT:ON                   | W          | Sets the lock mode on the unit when in remote mode |
# | SYS RST          |                               | W          | Resets the hardware                                |
# | SYS FLSH         |                               | R          | Reads the available memory in the box              |
# | SYS RAM          |                               | R          | Reads the available RAM in the box                 |
# | SYS ALRM         |                               | R          | Lists current alarms                               |
# | SYS RUN          | Command Name                  | W          | Runs pre-loaded system commands                    |
# | SYS GUI CHAN UID | signal name                   | R/W        | Set the signal display for a given channel widget  |
# | SYS GPIB ADDR    | 1-31                          | R/W        | Sets the GPIB address of the box                   |
# | SYS TCP ADDR     | #.#.#.#                       | R/W        | Sets the IP address of the box                     |
# | SYS TCP DHCP     | OFF:ON                        | R/W        | Sets DHCP search                                   |
# | SYS TCP GATE     | #.#.#.#                       | R/W        | Sets the gateway                                   |
# | SYS TCP SUBN     | #.#.#.#                       | R/W        | Sets the subnet mask                               |
# | SYS RS232 ADDR   | 1-255                         | R/W        | Sets the Isobus address                            |
# | SYS RS232 BAUD   | 9600:19200:38400:57600:115200 | R/W        | Sets the Baudrate                                  |
# | SYS RS232 STOP   | 1-2                           | R/W        | Sets the number of stop bits                       |
# | SYS RS232 DATA   | 7-8                           | R/W        | Sets the number of data bits                       |
# | SYS RS232 PAR    | none:odd:even:mark:space      | R/W        | Sets the parity                                    |
# | SYS RS232 FLOW   | none:hardware:Xon/Xoff        | R/W        | Sets the flow control                              |

# Configuration for temperature sensor (use as  DEV:<UID>:TEMP:smth)
# | MAN HVER  |                     | R   | Reads the hardware version of the daughter card                     |
# | MAN FVER  |                     | R   | Reads the firmware version of the daughter card                     |
# | MAN SERL  |                     | R   | Reads the serial number of the daughter card                        |
# | NICK      |                     | R/W | Sets the name of the device                                         |
# | TYPE      | DUM:PTC:NTC:TCE:DDE | R/W | Sets the sensor type                                                |
# | EXCT TYPE | UNIP:BIP:SOFT       | R/W | Sets the excitation type                                            |
# | EXCT MAG  | 0-1000              | R/W | Sets the excitation magnitude                                       |
# | CAL OFFS  | 0-1000              | R/W | Sets the offset of the calibration curve                            |
# | CAL SCAL  | 0-1000              | R/W | Sets the scale of the calibration curve                             |
# | CAL FILE  |                     | R/W | Sets the calibration file to use to calculate the temperature       |
# | CAL INT   | NONE:LIN:SPL:LAGR   | R/W | Sets the interpolation method for the calibration file.             |
# | CAL HOTL  | 0-2000              | R/W | Set the maximum value for temperature setpoint (hot limit)          |
# | CAL COLDL | 0-1000              | R/W | Set the minimum value for temperature setpoint (cold limit)         |
# | CAL CAL   |                     | R/W | Calibrates hardware. Reads the time of the last calibr. (Unix time) |
# | CSMP      |                     | R/W | Control filter buffer length (number of samples)                    |
# | CSMP      |                     | R/W | Signal filter buffer length (number of samples)                     |

# The signals for a temperature sensor (use as  DEV:<UID>:TEMP:smth)
# | SIG VOLT | R | Sensor voltage                            |
# | SIG CURR | R | Sensor current                            |
# | SIG TEMP | R | Measured temperature                      |
# | SIG CTMP | R | Control temperature                       |
# | SIG RTMP | R | Raw temperature                           |
# | SIG POWR | R | Sensor power dissipation                  |
# | SIG RES  | R | Measured resistance (PTC/NTC)             |
# | SIG SLOP | R | Temperature to resistance ratio (PTC/NTC) |
# | SIG REF  | R | Thermocouple reference temperature        |

# The configuration settings for a control loop (use as  DEV:<UID>:TEMP:smth):
# | LOOP HTR UID |                       | R/W | Assign Heater device to Temperature                                   |
# | LOOP AUX UID |                       | R/W | Assign Auxiliary device to Temperature                                |
# | LOOP P       |                       | R/W | Set the P Value                                                       |
# | LOOP I       |                       | R/W | Set the I Value                                                       |
# | LOOP D       |                       | R/W | Set the D Value                                                       |
# | LOOP PIDT    | OFF:ON                | R/W | Sets automatic PID values (from table)                                |
# | LOOP PIDF    |                       | R/W | Sets the file to read from for the automatic PID Table                |
# | LOOP THTF    |                       | R/W | Sets the file to read from for the Target Heater Table                |
# | LOOP SWFL    |                       | R/W | Sets the file to read from for the Sweep Table                        |
# | LOOP SWMD    | FIX:SWP               | R/W | Sets the sweep mode                                                   |
# | LOOP ENAB    | OFF:ON                | R/W | Enables(Auto)/disables(Manual) the PID control                        |
# | LOOP TSET    | 0-2000                | R/W | Sets the temperature set point                                        |
# | LOOP HSET    | 0-100                 | R/W | Sets the Heater percentage (in Manual)                                |
# | LOOP FSET    | 0-100                 | R/W | Sets the flow percentage (Manual flow)                                |
# | LOOP RSET    | 0-inf                 | R/W | Sets the ramp rate for when the loop is in ramp mode                  |
# | LOOP FAUT    | OFF:ON or Manual:Auto | R/W | Controls flow control. (Use Manual:Auto for Cryosys 1.0.11 and older) |
# | LOOP RENA    | OFF:ON                | R/W | Enables/Disables ramp mode                                            |

# The configuration settings for a heater controller are DEV:<UID>: HTR
# | MAN HVER |         | R   | Reads the hardware version of the daughter card  |
# | MAN FVER |         | R   | Reads the firmware version of the daughter card  |
# | MAN SERL |         | R   | Reads the serial number of the daughter card     |
# | NICK     |         | R/W | Sets the name of the device                      |
# | VLIM     | 0-40    | R/W | Sets the Maximum voltage limit for the heater    |
# | STAT     |         | R   | Reads the alarm flags of the device (Hex Format) |
# | RES      | 10-2000 | R/W | Sets the heater resistance                       |
# | PMAX     | 0-80    | R   | Indicates the maximum power of the heater        |
# | CAL      |         | W   | Calibrates the hardware                          |

# The signals for a heater controller are DEV:<UID>: HTR followed by:
# | SIG VOLT | R/W | Heater voltage            |
# | SIG CURR | R   | Heater current            |
# | SIG POWR | R/W | Heater power dissipation  |

from core.module import Base, ConfigOption
import visa
import time

class MercuryiTC(Base):
    """ This module implements communication with Mercury iTC temperature controller.

    Example config for copy-paste:

    tempcontroller_ctc100:
        module.Class: 'CTC100_temperature.CTC100'
        interface: 'ASRL1::INSTR'
    """

    _modclass = 'mercury_itc'
    _modtype = 'hardware'

    # config options
    _interface = ConfigOption('interface', missing='error')

    def on_activate(self):
        """ Activate modeule
        """
        self.connect(self._interface)

    def on_deactivate(self):
        """ Deactivate modeule
        """
        self.disconnect()

    def connect(self, interface):
        """ Connect to Instrument.

            @param str interface: visa interface identifier

            @return bool: connection success
        """
        try:
            self.rm = visa.ResourceManager()
            self.inst = self.rm.open_resource(interface, read_termination='\n')
        except visa.VisaIOError as e:
            self.log.exception("")
            return False
        else:
            return True

    def disconnect(self):
        """ Close the connection to the instrument.
        """
        self.inst.close()
        self.rm.close()

    def get_temperature(self):
        return self.inst.query('READ:DEV:MB1.T1:TEMP:SIG:TEMP').split(':')[-1][:-1]
