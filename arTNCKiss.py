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

import os
import os.path
import sys
import datetime
import time
import struct

from arElement import arElement

#from AQPUtils import msleep, aprint

# Special Characters
FEND  = 0xc0
FESC  = 0xdb
TFEND = 0xdc
TFESC = 0xdd

# Transmit Commands
DATA_FRAME      = 0x00
CMD_TXDELAY     = 0x01
CMD_P           = 0x02
CMD_SLOTTIME    = 0x03
CMD_TXTAIL      = 0x04
CMD_FULLDUPLEX  = 0x05
CMD_SETHARDWARE = 0x06
CMD_RETURN      = 0xff

# RX State Machine
ST_IDL = 1
ST_PKT = 2
ST_ESC = 3

class arTNCKiss(arElement):
    def __init__(self, packet_cb):
        arElement.__init__(self)

        self._packet_cb = packet_cb
        self._rx_state = ST_IDL
        self._rx_buf = bytearray(0)

    # byte in, bytearray out
    def recvChar(self,c):
        hc = struct.unpack("B",c)[0]
#        self.arPrint("rx_char> %x" % hc)

        if self._rx_state == ST_IDL:
            if hc == FEND:
                self._rx_state = ST_PKT
                return
        elif self._rx_state == ST_PKT:
            if hc == FEND:
                # packet complete
                if len(self._rx_buf) > 0:
                    # verify command field or drop packet
                    if self._rx_buf[0] != 0x0:
                        #self.arPrint("invalid KISS command on packet receive")
                        pass
                    else:
                        self._packet_cb(self._rx_buf[1:])
                    self._rx_buf = bytearray(0)
                self._rx_state = ST_IDL
            elif hc == FESC:
                self._rx_state = ST_ESC
            else:
                self._rx_buf = self._rx_buf + c
        elif self._rx_state == ST_ESC:
            if hc == TFEND:
                self._rx_buf = self._rx_buf + struct.pack("B",0xc0)
                self._rx_state = ST_PKT
            elif hc == TFESC:
                self._rx_buf = self._rx_buf + struct.pack("B",0xdb)
                self._rx_state = ST_PKT
            else:
                pass
                #arPrint("invalid KISS escape character!")

    # string in, bytearray out
    def framePacket(self,buf):
        tx_buf = struct.pack("B B", FEND, DATA_FRAME)

        for c in buf:
            hc = c.to_bytes(1, sys.byteorder)
            if hc == FEND:
                tx_buf = tx_buf + struct.pack("B", FESC)
                tx_buf = tx_buf + struct.pack("B", TFEND)
            elif hc == FESC:
                tx_buf = tx_buf + struct.pack("B", FESC)
                tx_buf = tx_buf + struct.pack("B", TFESC)
            else:
                tx_buf = tx_buf + hc

        tx_buf =  tx_buf + struct.pack("B", FEND)

        return tx_buf

