import serial
import glob
import sys
import numpy as np


from imswitch.imcommon.model import initLogger


class ESP32Driver:
    def __init__(self, address):
        self.__logger = initLogger(self, tryInheritParent=False)
        try:
            self.serial = serial.Serial(
                address, baudrate=115200, timeout=0.050)
            self.__logger.debug("ESP32 connected")
            self.is_connected = True
        except:
            self.__logger.warning("No ESP32 connected - Check port?")
            self.is_connected = False

        if self.is_connected:
            self._write("<L1OF,L2OF")

        # illumination settings
        self.laser_intensity = 0
        self.led_state = 0

        # self.is_debug = True

    def serial_ports(self):
        if sys.platform.startswith('win'):
            ports = ['COM%s' % (i + 1) for i in range(256)]
        elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
            # this excludes your current terminal "/dev/tty"
            ports = glob.glob('/dev/tty[A-Za-z]*')
        elif sys.platform.startswith('darwin'):
            ports = glob.glob('/dev/tty.*')
        else:
            raise EnvironmentError('Unsupported platform')

        result = []
        for port in ports:
            try:
                s = serial.Serial(port)
                s.close()
                result.append(port)
            except (OSError, serial.SerialException):
                pass
        return result

    def _write(self, command):
        # if self.is_debug: print(command)
        if self.is_connected:
            self.serial.write(command.encode())

    def close(self):
        self.serial.close()

    # --------------
    # Code for stage
    # --------------

    def set_laser_intensity(self, intensity):
        self.laser_intensity = intensity
        if self.led_state:
            suffix = "ON"
        else:
            suffix = "OF"

        cmd = "<L1" + suffix + ">"
        return self._write(cmd)

    def set_led(self, channel, state=1):
        # state is either 1 or 0
        self.led_state = state
        if self.led_state:
            suffix = "ON"
        else:
            suffix = "OF"

        cmd = "<L" + str(channel) + suffix + ">"
        return self._write(cmd)

    # --------------
    # Code for stage
    # --------------

    def move_rel(self, position_rel=(0, 0, 0), blocking=True, pingwait=0.25):
        """Move axises relaitve to current position"""
        self.move_xyz(position_rel, blocking=blocking, config="rel")

    def move_abs(self, position_rel=(0, 0, 0), blocking=True, pingwait=0.25):
        """Move axises absolute"""
        self.move_xyz(position_rel, blocking=blocking, config="abs")

    def move_xyz(self, position=(0, 0, 0), blocking=True, pingwait=0.25, config="abs"):
        """Move axis with optional blocking"""
        self.get_positions()
        if config == "abs":
            to_go = np.array(position)
        elif config == "rel":
            to_go = np.array((position[0]+self.positions[0],
                              position[1]+self.positions[1],
                              position[2]+self.positions[2]))



if __name__ == "__main__":

    port = "/dev/ttyUSB0"
    board = ESP32Driver(address=port)
    print(board.serial_ports())
