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
import sys
import re
import datetime as dt
from pytz import timezone
import click
import math
import threading
import signal
import socket
import struct
import binascii

from arElement import arElement
from arTNCKiss import arTNCKiss

def td2min(td):
    res = td.days * 24*60*60
    res += td.seconds
    res /= 60
    return round(res)

class arNet(arElement, threading.Thread):
    def __init__(self, call, txCB, tz = None):
        arElement.__init__(self)

        self._day = 0              # sunday
#        self._repeat = 7         # weekly
        self._timeofday = 20 * 60  # 8pm
        self._interval = 3         # beacon every 3 minutes
        self._duration = 30        # becaon for 30 minutes
        self._objname = "NET-TEST" # beacon object name
        self._objfreq = "146.520"  # freq in MHz
        self._objtone = "none"     # PL Tone
        self._objrange = "none"    # Repeater range
        self._path  = "none"       # Packet path
        self._lat = "0000.00N"     # latitude
        self._lon = "00000.00W"    # longitude
        self._comment = ""         # comment

        if tz is not None:
            self.arTz = tz
        self._dt = self.arGetLocalTime()
        self._stopped = threading.Event()

        self.opcall = call
        self.txCB = txCB

        # object mode for beacon text
        # 0 = out of time window
        # 1 = pre net 
        # 2 = net active
        # 3 = post net (kill beacon)
        self.objmode = 0

        threading.Thread.__init__(self)


    @property
    def day(self):
        return self._day

    @day.setter
    def day(self, v):
        lut = {
            "MON" : 0,
            "TUE" : 1,
            "WED" : 2,
            "THU" : 3,
            "FRI" : 4,
            "SAT" : 5,
            "SUN" : 6,
            0 : 0,
            1 : 1,
            2 : 2,
            3 : 3,
            4 : 4,
            5 : 5,
            6 : 6
        }
        av = lut.get(v, -1)
        if av < 0:
            raise ValueError("Invalid day[%s], valid arguments are SUN,MON,TUE,WED,THU,FRI,SAT" % v)
        self._day = av

    @property
    def timeofday(self):
        return self._timeofday

    @day.setter
    def timeofday(self, v):
        # expeted format
        # HH:MM[AP]M
        rem = re.fullmatch("^([0-9]?[0-9]):([0-9][0-9])([AP]M)$", v)
        if rem:
            h = int(rem.group(1))
            m = int(rem.group(2))
            o = rem.group(3)
        else:
            raise ValueError("Invalid time[%s], format must match HH:MM[AP]M" % v)

        if not (h > 0 and h <= 12):
            raise ValueError("Invalid time[%s], 0 < hours <= 12" % v)

        if not (m >= 0 and m < 60):
            raise ValueError("Invalid time[%s], 0 <= minutes < 60" % v)

        if not (o == "AM" or o == "PM"):
            raise ValueError("Invalid time[%s], AM or PM" % v)

        if h == 12:
            h = 0
        if o == 'PM':
            h += 12

        self._timeofday = h * 60 + m

    @property
    def interval(self):
        return self._interval

    @interval.setter
    def interval(self, v):
        vi = int(v)
        if vi < 1 or vi > 10:
            raise ValueError("Invalid interval[%s], 1 <= interval <= 10" % v)

        self._interval = vi

    @property
    def duration(self):
        return self._duration

    @duration.setter
    def duration(self, v):
        vi = int(v)

        if vi < 1 or vi > 60:
            raise ValueError("Invalid duration[%s], 1 <= duration <= 60" % v)

        self._duration = vi

    @property
    def objname(self):
        return self._objname

    @objname.setter
    def objname(self, v):
        v = v.ljust(9)
        if len(v) > 9:
            raise ValueError("Invalid objname[%s], len <= 9" % v)

        self._objname = v
        self.arName = v

    @property
    def objfreq(self):
        return self._objfreq

    @objfreq.setter
    def objfreq(self, v):
        v = v.ljust(7)
        if len(v) > 7:
            raise ValueError("Invalid objfreq, len <= 7" % v)

        if not re.fullmatch('[\d ]\d\d\.\d\d[\d ]', v):
            raise ValueError("Invalid objfreq[%], format [\d ]\d\d.\d\d[\d ]" % v)

        self._objfreq = v

    @property
    def objtone(self):
        return self._objtone

    @objtone.setter
    def objtone(self, v):
        v = v.ljust(4)
        if len(v) > 4:
            raise ValueError("Invalid objtone, len <= 4" % v)

        if v != 'none' and not re.fullmatch('[CDTcdt]\d\d\d', v) \
                and not re.fullmatch('[1l]750', v):
            raise ValueError("Invalid objtone[%s], format none, [1l]750 or [CDTcdt]\d\d\d" % v)

        self._objtone = v

    @property
    def objrange(self):
        return self._objrange

    @objrange.setter
    def objrange(self, v):
        v = v.ljust(4)
        if len(v) > 4:
            raise ValueError("Invalid objrange, len <= 4")

        if v != 'none' and not re.fullmatch('R\d\d[mk]', v) \
                and not re.fullmatch('[+-]\d\d\d', v):
            raise ValueError("Invalid objrange[%s], format none or R\d\d[mk]" % v)

        self._objrange = v

    @property
    def path(self):
        return self._path

    @path.setter
    def path(self, v):
        v = v.ljust(9)
        if len(v) > 9:
            raise ValueError("Invalid path, len <= 9")
        v = v.rstrip()

        if v != 'none' and \
           not re.fullmatch('WIDE[21]-[21]', v) and \
           not re.fullmatch('[A-Za-z]{1,2}\d[A-Za-z]{1,3}-\d{1,2}', v):
            raise ValueError("Invalid path[%s], format none or WIDEN-M or call-ssid" % v)

        self._path = v

    @property
    def latitude(self):
        return self._latitude

    @latitude.setter
    def latitude(self, v):
        v = v.rjust(8,'0')

        if len(v) > 8:
            raise ValueError("Invalid latitude[%s], len == 8" % v)

        if not re.fullmatch('[0-9]{4}\.[0-9]{2}[NS]', v):
            raise ValueError("Invalid latitude[%s], format 0000.00[SN]" % v)

        self._latitude = v

    @property
    def longitude(self):
        return self._longitude

    @longitude.setter
    def longitude(self, v):
        v = v.rjust(9,'0')

        if len(v) > 9:
            raise ValueError("Invalid longitude[%s], len == 9" % v)

        if not re.fullmatch('[0-9]{5}\.[0-9]{2}[EW]', v):
            raise ValueError("Invalid longitude[%s], format 00000.00[EW]" % v)

        self._longitude = v

    @property
    def comment(self):
        return self._comment

    @comment.setter
    def comment(self, v):
        if len(v) > 32:
            raise ValueError("Invalid comment[%s], len <= 32" % v)

        self._comment = v

    def initTime(self):
        # initialize _dt to next future net time
        # unless net is currently active

        self._dt = self.arGetLocalTime()
        dayshift = self._day - self._dt.weekday()
        if dayshift < 0:
            dayshift += 7

        hrs = math.floor(self._timeofday / 60)
        mins = self._timeofday % 60
        self._dt = self._dt.replace(hour=hrs, minute=mins, second=0) + \
                    dt.timedelta(days=dayshift)

        if td2min(self._dt - self.arGetLocalTime()) + self._duration < 0:
            self._dt += dt.timedelta(days = 7)

        self.arPrint("Time initialized, next NET starts at %s" % self._dt.strftime("%c"))

    def calcWaitTime(self):
        # calculate next wait time
        # start beacons 30 minutes before net time, every 10 minutes
        # once net starts, beacon at interval rate specified
        # for duration, beacon 3 times after to kill every 3 minutes

        # calc delta time in minutes, negative after net start
        dMin = td2min(self._dt - self.arGetLocalTime())
        self.arPrint("Minutes until NET start: %d" % dMin)
        retVal = 604800 # 1week
        if dMin > 30:
            #print ("CALC> mode: 0")
            #outside net beacon time
            self.objmode = 0
            retVal = (dMin - 30) * 60
        elif dMin <= 30 and dMin > 0:
            #print ("CALC> mode: 1")
            #pre net beacon time
            self.objmode = 1
            retVal = (dMin % 10) * 60
            retVal = retVal if retVal != 0 else 10 * 60
        elif dMin <= 0 and (dMin + self._duration) >= 0:
            #print ("CALC> mode: 2")
            #net beacon time
            self.objmode = 2
            retVal = ((dMin+self._duration) % self._interval) * 60
            retVal = retVal if retVal != 0 else self._interval * 60
        elif (dMin + self._duration) < 0 and (dMin + self._interval + self._duration + 7) >= 0:
            #print ("CALC> mode: 3")
            #post net beacon time
            self.objmode = 3
            retVal = 3*60
        else:
            #print ("CALC> mode: 4")
            #update _dt for next net beacon time
            self.objmode = 0
            self._dt += dt.timedelta(days=7)
            dMin = td2min(self._dt - self.arGetLocalTime())
            retVal = (dMin - 30) * 60

        # safety net to not rapid fire network
        retVal = retVal if retVal >= 60 else 60
        self.arPrint("Second delay until next beacon: %s" % retVal)
        return retVal

    def stop(self):
        self._stopped.set()
        self.join()

    def run(self):
        self.arPrint("Starting NET element...")

        wt = self.calcWaitTime() # also sets beacon mode
        # send out initial beacon if in range
        if self.objmode > 0:
            self.txCB(self.buildPacket())

        while not self._stopped.wait(wt):
            self.arPrint("Delay complete at %s" % self.arGetLocalTime())
            wt = self.calcWaitTime()
            if not self._stopped.is_set() and self.objmode > 0:
                self.txCB(self.buildPacket())


    def packHeader(self, call, path):
        valb = struct.pack('6s B', 'APZFRG'.encode('utf-8'), 0x70)

        m = re.search("([A-Za-z]{1,2}\d[A-Za-z]{1,3})-(\d{1,2})", call)
        if m:
            callbase = m.group(1).ljust(6)
            callssid = int(m.group(2))
            if callssid < 0 or callssid > 15:
                raise ValueError("Callsign SSID out of range, 0 <= ssid <= 15")
        else:
            raise ValueError("Invalid callsign format, must include ssid")

        vals = []
        vals.append(callbase.encode('utf-8'))
        vals.append(0x70|callssid)
        valb += struct.pack('6s B', *vals)

        vals = []
        dp = re.search("([A-Za-z]{1,2}\d[A-Za-z]{1,3})-(\d{1,2})", path)
        wp = re.search("(WIDE[12])-([12])", path)
        if dp:
            pathbase = dp.group(1).ljust(6)
            pathssid = int(dp.group(2))
            if pathssid < 0 or pathssid > 15:
                raise ValueError("Via path SSID out of range, 0 <= ssid <= 15")

            vals.append(pathbase.encode('utf-8'))
            vals.append(0x30|pathssid)
            valb += struct.pack('6s B', *vals)
        elif wp:
            pathbase = wp.group(1).ljust(6)
            pathssid = int(wp.group(2))

            vals.append(pathbase.encode('utf-8'))
            vals.append(0x30|pathssid)
            valb += struct.pack('6s B', *vals)
        elif path == 'none':
            pass
        else:
            raise ValueError("Invalid via path format")

        # shift octets, mark last for as final
        valbs = b''
        for c in valb[:-1]:
            valbs += (c<<1).to_bytes(1, sys.byteorder)
        valbs += (valb[-1]<<1|0x1).to_bytes(1, sys.byteorder)

        # add on control field and protocol id
        valbs += struct.pack('B B', 0x03, 0xf0)

        return valbs

    def buildPacket(self):
        bstr = self.packHeader(self.opcall, self._path)
        objc = '*' if self.objmode < 3 else '_' # kill object beacon
        objs = 'E' if self.objmode < 3 else '.' # switch to X when killing object
        objstr = ";%s%c%s%s/%s%c" % \
                   (self._objname, objc, \
                    self.arGetUTCTime().strftime("%d%H%Mz"), \
                    self._latitude, \
                    self._longitude, \
                    objs )

        objstr += "%sMHz" % self._objfreq
        commentlen = 32
        if self._objtone != 'none' or self._objrange != 'none':
            objstr += (" %s" % self._objtone) if self._objtone != 'none' else "    "
            objstr += (" %s" % self._objrange) if self._objrange != 'none' else "    "
            commentlen -= 10

        if self.objmode == 1:
            objstr += (" @%s" % self._dt.strftime("%I:%M%p"))
            commentlen -= 9
        elif self.objmode == 2:
            objstr += " ON-AIR"
            commentlen -= 7
        else:
            objstr += " OFF-AIR"
            commentlen -= 8

        if self._comment:
            objstr += " " + self._comment[:commentlen]

        self.arPrint("OBEACON: %s" % objstr)
        #print(binascii.hexlify(bstr+objstr.encode('UTF-8')))
        return bstr+objstr.encode('UTF-8')

class arNetSked(arElement):
    def __init__(self, call, skedfile, host, port, tz, verbose):
        arElement.__init__(self)

        self._objlist = []

        self.call = call
        self.skedfile = skedfile
        self.tnchost = host
        self.tncport = port
        if tz is not None:
            self.arTz = timezone(tz)

        self.verbose = verbose


    def abortSignal(self, signum, frame):
        self.abort()

    def abort(self):
        if len(self._objlist):
            self.arPrint("Stopping arNetSked")
            for o in self._objlist:
                o.stop()

        if self.tncsock:
            self.arPrint("Closing TNC socket")
            try:
                self.tncsock.close()
            except OSError:
                pass

    def start(self):

        # connect to TNC
        self.arPrint("Binding TNC client socket...")

        if re.fullmatch("\S\S:\S\S:\S\S:\S\S:\S\S:\S\S", self.tnchost):
            self.arPrint("Bluetooth host address detected")
            if self.tncport == 8001:
                self.arPrint("Setting default bluetooth RFCOMM channel to 1")
                self.tncport = 1
            self.tncsock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)

        else:
            self.tncsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            self.tncsock.connect((self.tnchost, self.tncport))
        except ConnectionError as e:
            self.arPrint("Socket connection refused to %s[%s]" % (self.tnchost, self.tncport))
            exit(1)
        except OSError as e:
            self.arPrint("Host unavailable %s[%s]" % (self.tnchost, self.tncport))
            exit(1)

        self.tncsock.settimeout(1) # 1s timeout

        self.tnckiss = arTNCKiss(self.recvPacketCB)


        self.arPrint("Opening schedule file...")
        with open(self.skedfile) as f:
            # skip first two lines
            d = f.readline()
            d = f.readline()
            lineno = 2
            for line in f:
                lineno += 1
                if re.search('^\s*#', line):
                    continue
    #            print (line)
                line = line.ljust(75)

                objn = arNet(self.call, self.tranPacketCB, self.arTz)
                opts = line.split()
                try:
                    objn.day       = opts[0]
                    objn.timeofday = opts[1]
                    iad = opts[2].split('/')
                    objn.interval  = iad[0]
                    objn.duration  = iad[1]
                    objn.latitude  = opts[3]
                    objn.longitude = opts[4]
                    objn.objname   = opts[5]
                    objn.objfreq   = opts[6]
                    objn.objtone   = opts[7]
                    objn.objrange  = opts[8]
                    objn.path      = opts[9]
                    if len(opts) > 9:
                        objn.comment = " ".join(opts[10:])

                except ValueError as err:
                    self.arPrint("Error processing schedule line[%d]" % lineno)
                    self.arPrint(err)
                    self.abort()
                    break

                self._objlist.append(objn)
                objn.initTime()
                objn.start()

        self.arPrint("NET elements started...")
        # wait for net objects to cleanup
        ndy = 1
        while ndy > 0:
            ndy = 0
            for o in self._objlist:
                o.join(1)
                ndy += 1 if o.is_alive() else 0
                # discard inbound packets from tnc
                more_rx = 1
                while more_rx:
                    try:
                        c = self.tncsock.recv(1)
                    except socket.timeout:
                        more_rx = 0
                    except OSError:
                        more_rx = 0
                    else:
                        if len(c) == 0: # can this happen?
                            more_rx = 0
                        else:
                            self.tnckiss.recvChar(c)

        # close socket
        try:
            self.tncsock.close()
        except OSError:
            pass

    def tranPacketCB(self, pkt):
        #print(binascii.hexlify(frame))
        self.tncsock.sendall(self.tnckiss.framePacket(pkt))

    def recvPacketCB(self, pkt):
        # drop inbound packets
        pass


@click.command()
@click.option("--schedule", "-s", "sfile", required=True,
    help="Schedule file to be processed",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    )
@click.option("--call", "-c", "call", required=True,
    help="Operator callsign",
    )
@click.option("--host", "-h", "host", required=True,
    help="TNC network or bluetooth host",
    )
@click.option("--port", "-p", "port", default=8001,
    help="TNC network port or bluetooth channel",
    )
@click.option("--timezone", "-t", "tz", required=False,
    help="Timezone of schedule information",
    )
@click.option("--verbose", is_flag=True, help="Verbose output")
def main(sfile, call, host, port, tz, verbose):
    """Process schedule for APRS NetSked beacons and
    transmit over network TNC KISS server.
    """

    netsked = arNetSked(call, sfile, host, port, tz, verbose)
    signal.signal(signal.SIGINT, netsked.abortSignal)
#    signal.signal(signal.SIGTERM, netsked.abort)

    try:
        netsked.start()
    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print("== EXCEPTION ==")
        print("== %s\n== %s" % (exc_type, e))
        print("== File:%s[%s]" % (fname, exc_tb.tb_lineno))
        netsked.abort()


if __name__ == "__main__":
    main()
