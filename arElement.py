#!/usr/bin/python3
#
# Copyright (C) 2020 Richard Ferguson, K3FRG.
#                    k3frg@arrl.net
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
import datetime as dt
import pytz
from tzlocal import get_localzone

import threading

class arElement():
    def __init__(self):
        self._arName = "%s" % (self.__class__.__name__)
        self._arTz = get_localzone()
        self._arPrintLock = threading.Lock()

    @property
    def arName(self):
        return self._arName

    @arName.setter
    def arName(self, v):
        self._arName = "%s:%s" % (self.__class__.__name__, v)

    @property
    def arTz(self):
        return self._arTz

    @arTz.setter
    def arTz(self, v):
        self._arTz = v

    def arGetLocalTime(self):
        return self._arTz.localize(dt.datetime.now())

    def arGetUTCTime(self):
        return pytz.utc.localize(dt.datetime.utcnow())

    def arPrint(self, message):
        self._arPrintLock.acquire()
        print("[%s] %s" % (self._arName, message))
        self._arPrintLock.release()
