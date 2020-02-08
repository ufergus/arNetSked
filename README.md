# arNetSked
Amateur Radio utility for transmitting APRS object beacons for local nets.  

Requires a network or bluetooth TNC such as Direwolf or Mobilinkd.  Serial TNCs are not supported at this time.

Object beacons will begin 30 minutes prior to the schedule time at a 10 minute interval.  Once the net begins, beacons will be transmitted as specified by the interval and duration parameters.  Once the duration has elapsed, several additional beacons will be transmitted killing the APRS object.  

Nets are assumed to repeat every seven days.  Alternative repeat schedules are not supported at this time.

Conforms to the frequency object specification so modern radios should support directly tuning to the advertised frequency with little effort.

# Objective
Advertise Amateur Radio nets on the local APRS network to attract new and traveling operators.

# Background
This script is based on the netsked concept from Bob Bruninga, WB4APR found here.
- http://www.aprs.org/info/netsked.txt
- http://www.aprs.org/info/freqspec.txt

# Usage
```
Usage: arNetSked.py [OPTIONS]

  Process schedule for APRS NetSked beacons and transmit over network TNC
  KISS server.

Options:
  -s, --schedule PATH  Schedule file to be processed  [required]
  -c, --call TEXT      Operator callsign  [required]
  -h, --host TEXT      TNC network or bluetooth host  [required]
  -p, --port INTEGER   TNC network port or bluetooth channel
  --verbose            Verbose output
  --help               Show this message and exit.
```

# Schedule Format
```
DAY TIME    RATE LATITUDE LONGITUDE NAME      FREQ    TONE RA/O PATH      COMMENT
--- ------- ---- -------- --------- --------- ------- ---- ---- --------- -------------|---------
FRI 08:00PM 3/30 0000.00N 00000.00W NET-????? 146.520 none R05m none      NetSked Example
SAT 09:00AM 5/45 0000.00N 00000.00W NET-????? 147.265 T100 +060 WIDE2-1   NetSked Example
```

## DAY
Three letter abbreviation for the day.
```SUN,MON,TUE,WED,THU,FRI,SAT```

## TIME
Start time of the day for the net event.
```HH:MM[AP]M```

## RATE - Interval / Duration
### Interval
Beacon interval while net is active in minutes.
### Duration
Estimated net duration in minutes.

## LATITUDE / LONGITUDE
Location of repeater or central area for simplex nets in hours/minutes format.
```HHMM.MM[NS] HHHMM.MM[EW]```
## NAME
9 Character name for the net object.

## FREQUENCY
Frequency in MHz of the repeater output or simplex channel.

## TONE
PL Tone for channel
```
Cxxx - CTCSS
Txxx - Tone
Dxxx - DCS

none - If not required
```
## Range / Offset
This field specifies either the estimated range of the net or offset of the repeater.  Note, repeater offset should only be required if using a non-standard offset.
```
Rxxm - Range in miles
Rxxk - Range in kilometers

+xxx - Positive offset in 10KHz, 0.6MHz offset would be +060
-xxx - Negative offset in 10KHz, 5 MHz offset would be -500

none - If not specified
```

## PATH
Digipeater path for beacon, only single entry supported
```
WIDE2-2
WIDE1-1
W3ABC-1

none - If not specified
```

### COMMENT
Additional comments for the object beacon.  Limited to 13 characters if using Tone, Range or Offset, else 23 characters.  Not required and can be left blank.



 



