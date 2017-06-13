import datetime
import tzlocal
import math

from pytz import timezone, utc
from web import bisect

EPOCH_START = datetime.datetime(1970, 1, 1)
SECONDS_PER_WEEK = 60 * 60 * 24 * 7
WEEK_EPOCH_START = datetime.datetime(1970, 1, 4)

def dateOfDateTime(dt):
    return datetime.date(dt.year, dt.month, dt.day)

def dateTimeOfDate(dt):
    return datetime.datetime(dt.year, dt.month, dt.day, 0, 0, 0)

def deepochify(sec):
    return EPOCH_START + datetime.timedelta(seconds=sec)

def epochify(dt):
    if dt is not None:
        return int((dt - EPOCH_START).total_seconds())

def getDateFilter(start=None, end=None):
    if (start is not None) and (end is not None):
        return lambda date: start <= date <= end
    elif (start is not None):
        return lambda date: start <= date
    elif (end is not None):
        return lambda date: date <= end
    else:
        return lambda date: True

def getLocalZone():
    return utc

def getTargetZone():
    # return the default desired timezone
    if not hasattr(getTargetZone, 'zone'):
        getTargetZone.zone = timezone('US/Eastern')
    return getTargetZone.zone

def getWeek(date):
    if date.tzinfo:
        date = toLocal(date, naive=True)
    # return the number of weeks since Sunday, January 4, 1970
    return int(
        math.floor(
            (date - WEEK_EPOCH_START).total_seconds() 
            / 
            SECONDS_PER_WEEK
        )
    )

def formatTime(date, pattern="%Y-%m-%d %H:%M:%S"):
    if not date:
        return ''
    date = toTarget(date)
    return date.strftime(pattern)

def incrementMonth(date, months):
    monthInt = 12 * date.year + (date.month - 1)
    newMonthInt = monthInt + months
    newMonth = 1 + (newMonthInt % 12)
    newYear = newMonthInt / 12
    return date.replace(year=newYear, month=newMonth)

def _secondsToMidnight(tz):
    tznow = datetime.datetime.now(tz)
    tznowUp = tznow + datetime.timedelta(days=1)
    tz_dst_now = datetime.datetime(tznowUp.year, tznowUp.month, tznowUp.day, tzinfo=tz)

    diff = tz_dst_now.utcoffset().seconds - tznow.utcoffset().seconds
    seconds = (tz_dst_now - tznow).total_seconds() + diff
    return seconds

def secondsToPacificMidnight():
    return _secondsToMidnight(timezone('US/Pacific'))

def sliceTuples(data, start=None, end=None):
    if start:
        left = bisect.find_ge(data, start, key=lambda x: x[0])
        if left is None:
            return []
    else:
        left = 0

    if end:
        right = bisect.find_le(data, end, key=lambda x: x[0])
        if right is None:
            return []
    else:
        right = len(data) - 1

    return data[left:right+1]

def toTarget(time):
    # convert a datetime to the target timezone
    # if it is naive, we will assume it is the local timezone
    if not time.tzinfo:
        time = withLocal(time)
    return time.astimezone(getTargetZone())

def toLocal(time, naive=False):
    # convert a datetime to the local timezon (assumed to be utc)
    # if it is naive, we will assume it is in the target timezone
    if not time.tzinfo:
        time = withTarget(time)
    result = time.astimezone(getLocalZone())
    if naive:
        result = result.replace(tzinfo=None)
    return result

def toOther(time, fromZone, toZone, naive=False):
    # convert a datetime from one timezone to another
    if not time.tzinfo:
        time = fromZone.localize(time)
    result = time.astimezone(toZone)
    if naive:
        result = result.replace(tzinfo=None)
    return result

def withTarget(time):
    # Add the target tzinfo to a naive datetime
    return getTargetZone().localize(time)

def withLocal(time):
    # Add the local tzinfo to a naive datetime
    return getLocalZone().localize(time)
