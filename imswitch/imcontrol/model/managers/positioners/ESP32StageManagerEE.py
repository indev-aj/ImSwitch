from imswitch.imcommon.model import initLogger
from .PositionerManager import PositionerManager
import time
import numpy as np


class ESP32StageManagerEE(PositionerManager):

    def __init__(self, positionerInfo, name, **lowLevelManagers):
        super().__init__(positionerInfo, name, initialPosition={
            axis: 0 for axis in positionerInfo.axes
        })

        self._rs232manager = lowLevelManagers['rs232sManager'][
            positionerInfo.managerProperties['rs232device']
        ]

        self.__logger = initLogger(self, instanceName=name)
        self.board = self._rs232manager._esp32

    def move(self, value: int, axis: str):
        dir = "P"
        if value < 0:
            dir = "N"
        
        value = abs(value)

        if axis == 'X':
            cmd = "<S1" + dir + str(value) + ">"
        elif axis == 'Y':
            cmd = "<S2" + dir + str(value) + ">"
        elif axis == 'Z':
            cmd = "<S3" + dir + str(value) + ">"
        else:
            self.__logger.warning('Wrong axis, has to be "X" "Y" or "Z"')
            return

        self.__logger.debug(cmd)
        self._rs232manager.query(cmd)
        self._position[axis] = self._position[axis] + value

    def setPosition(self, value: float, axis: str):
        self._position[axis] = value

    def setSpeed(self, speed, axis):
        pass


# # Copyright (C) 2020, 2021 The imswitch developers
# This file is part of ImSwitch.
#
# ImSwitch is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# ImSwitch is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
