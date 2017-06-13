import calendar
import flask
import datetime
import re
import urllib
import urllib2
import StringIO
import json
import zlib
import base64
import math
import logging
import time
import subprocess
print subprocess.__file__
import tzlocal

import cloudstorage as gcs
from google.appengine.api import images
from google.appengine.ext import ndb
from google.appengine.ext import blobstore

from lxml import etree
from threading import Thread
from pytz import timezone
from unidecode import unidecode

from web import validate

LOCAL_ZONE = tzlocal.get_localzone()
TARGET_ZONE = timezone('US/Eastern')

def compress(obj, b64=False):
    serialized = json.dumps(obj)
    compressed = zlib.compress(serialized)
    if b64:
        compressed = base64.b64encode(compressed)
    return compressed

def chunkIterator(iter, chunkSize=1000):
    """
        Take in an iterator, and yield slices of up to chunkSize.
    """
    chunkBuffer = []
    for item in iter:
        chunkBuffer.append(item)
        if len(chunkBuffer) == chunkSize:
            yield chunkBuffer
            chunkBuffer = []
    if len(chunkBuffer) > 0:
        yield chunkBuffer

def chunkFile(f, startString, endString, yieldSegments=False, range=None):
    """
        Read a large file iteratively, producing chunks that begin with start and end with end.
        All other data is disposed of. So many things can go wrong...
    """
    CHUNK_SIZE = 10000
    buf = bytearray()
    EOF = False
    chunkStart = 0

    # skip to the beginning of the range if applicable
    if range:
        while (chunkStart + CHUNK_SIZE) < range[0]: 
            f.read(CHUNK_SIZE)
            chunkStart += CHUNK_SIZE
        f.read(range[0] - chunkStart)
        chunkStart = range[0]

    readLength = chunkStart
    while not EOF:
        if range:
            if readLength + CHUNK_SIZE < range[1]:
                chunk = f.read(CHUNK_SIZE)
            else:
                chunk = f.read(range[1] - readLength)
                EOF = True
        else:
            chunk = f.read(CHUNK_SIZE)
            if len(chunk) == 0:
                EOF = True

        readLength += len(chunk)
        buf += chunk
        hasChunks = True
        while hasChunks:
            try:
                startPos = buf.index(startString)
                offset = startPos + len(startString)
                endPos = buf.index(endString, offset)
                tail = (endPos+len(endString))
                substr = buf[startPos:tail]
                
                if not yieldSegments:
                    yield str(substr)
                else:
                    yield (chunkStart + startPos, chunkStart + tail)
            
                del buf[0:tail]
                chunkStart = chunkStart + tail
            except ValueError: # substrings not found
                hasChunks = False

def containDigit(strNumeric):
    if not strNumeric:
        return False
    return any(c.isdigit() for c in strNumeric)

def allDigits(strNumeric):
    if not strNumeric:
        return False
    return all(c.isdigit() for c in strNumeric)

def possibleZipcode(strNumeric):
    if strNumeric and len(strNumeric) == 5:
        return allDigits(strNumeric)
    return False

def diffPercent(v1, v2):
    return math.ceil(
        100 * (v1 - v2) 
        / max(v1, v2)
    )

def rateStr(numerator, denominator):
    if not denominator or numerator is None:
            return 'N/A'
    return "{0:.2f}%".format( (numerator*1.0)/(denominator*1.0) * 100)

def getYMD(date):
    if date is None:
        return None
    return datetime.datetime(date.year, date.month, date.day)

def getMaxYMD(date):
    if date is None:
        return None
    return datetime.datetime(date.year, date.month, date.day, 23,59,59)

def getYMDStr(date, pattern='%Y-%m-%d'):
    ymd = getYMD(date)
    if ymd is None:
        return None
    return ymd.strftime(pattern)

def estToLocal(time):
    time = timeWithEst(time)
    converted = time.astimezone(LOCAL_ZONE)
    return converted.replace(tzinfo=None)

def first(lst):
    """
        Safely retrieve the first element of a list, or None if it's not present.
    """
    if lst is None: return None
    elif len(lst) > 0: return lst[0]
    else: return None

def getBbox(shape):
    # returns [min longitude, max longitude, min latitude, max latitude]
    if shape['type'] == "Point":
        longs = [shape['coordinates'][0]]
        lats = [shape['coordinates'][1]]
    elif shape['type'] == "LineString":
        longs = [x[0] for x in shape['coordinates']]
        lats = [x[1] for x in shape['coordinates']]
    elif shape['type'] == "Polygon":
        coordinates = shape['coordinates']
        longs = []
        lats = []
        for ring in coordinates:
            longs += [x[0] for x in ring]
            lats += [x[1] for x in ring]
    elif shape['type'] == "MultiPolygon":
        coordinates = shape['coordinates']
        longs = []
        lats = []
        for polygon in coordinates:
            for ring in polygon:
                longs += [x[0] for x in ring]
                lats += [x[1] for x in ring]
    elif shape['type'] == "GeometryCollection":
        longs = []
        lats = []
        for geo in shape['geometries']:
            bounds = getBbox(geo)
            longs += bounds[0:2]
            lats += bounds[2:4]
    else:
        raise ValueError("Can't adapt that shape: %s!" % shape['type'])

    return [
        min(longs), max(longs),
        min(lats), max(lats),
    ]

def getRequire():
    requireEmail = validate.get('require_email', validate.ParseBool())
    require = validate.get('require')
    if require is None:
        if requireEmail:
            require = 'email'
    else:
        require = require.lower()
    return require

def getPrevDateRange(dateRange):
    if dateRange is None:
        return None
    end = dateRange['start'] - datetime.timedelta(days=1)
    return {
        "start" : end - (dateRange['end'] - dateRange['start']),
        "end" : end
    }

def getAggregationInterval(data):
    interval = data.get('interval')
    if interval in ['daily', 'weekly', 'monthly']:
        return interval
    return 'daily'

def hasMethod(obj, methodName):
    op = getattr(obj, methodName, None)
    return callable(op)

def handleUpload(filename):
    file = flask.request.files.get(filename)
    if file:
        headers = re.split(r'( *; *)|([\r\n]+)', str(file.headers))
        for header in headers:
            if header is not None:
                if header.startswith('blob-key='):
                    key = header.replace('blob-key=', '')
                    key = key.replace('"', '')
                    return file, key

def inheritIfPresent(key, origin, destination, destinationKey=None):
    if key in origin:
        destination[destinationKey or key] = origin.get(key)

def inheritIfTruthy(key, origin, destination, destinationKey=None):
    if origin.get(key):
        destination[destinationKey or key] = origin.get(key)

def setAttrIfPresent(key, origin, destination, destinationKey=None):
    if key in origin:
        setattr( destination, destinationKey or key, origin.get(key) )

def setAttrIfTruthy(key, origin, destination, destinationKey=None):
    if origin.get(key):
        setattr( destination, destinationKey or key, origin.get(key) )

def inheritIfMissing(key, origin, destination):
    if key in origin and key not in destination:
        destination[key] = origin.get(key)

def setMissingAttrs(origin, destination, destinationKey=None):
    if origin and destination:
        for key in origin:
            inheritIfMissing(key, origin, destination)
    return destination

def isSearchEngine():
    ua = flask.request.headers.get('User-Agent')
    if 'bingbot' in ua: return True
    if 'Googlebot' in ua: return True
    if 'Yahoo! Slurp' in ua: return True
    if 'Baiduspider' in ua: return True
    return False

def localToEst(time):
    time = timeWithLocal(time)
    return time.astimezone(TARGET_ZONE)

def keyify(key):
    #TODO: need to replace this with keyify2, same for the rutil.keyify
    return re.sub(r'[^a-zA-Z0-9]', '', key)

def keyify2(key):
    """
        Return a string with all non-alphanumeric characters removed, suitable for a mongo key
    """
    return re.sub(r'[^a-zA-Z0-9\-]', '', unidecode(key).lower().replace(' ', '-'))

def openFromCloudstorage(cloudstorageFilename):
    return gcs.open(cloudstorageFilename, 'r')

def parallelize(payloads):
    threads = []
    for payload in payloads:
        target = payload[0]
        
        if len(payload) >= 2:
            args = payload[1]
        else:
            args = None
        
        if len(payload) >= 3:
            kwargs = payload[2]
        else:
            kwargs = None

        threads.append(Thread(
            target=target,
            args=args,
            kwargs=kwargs,
        ))
    
    for thread in threads:
        thread.start()
        thread.join()

    # for thread in threads:
    #     thread.join()

def parseDateRange(dateRange, guardStartDate=True):

    # start and end are inclusive
    def buildDateRange(days):
        endStart, end = getDayStartEnd( datetime.datetime.now() - datetime.timedelta(days=1) )
        start = endStart - datetime.timedelta(days=days-1)
        return {
            "start" : start,
            "end" : end,
        }

    def getDayStartEnd(daytime):
        if isinstance(daytime, basestring):
            daytime = datetime.datetime.strptime(daytime, '%Y-%m-%d')
        start = getYMD(daytime)
        end =  start + datetime.timedelta(hours=23, minutes=59, seconds=59, microseconds=999999)
        return start, end

    if dateRange is None:
        return None

    if isinstance(dateRange, basestring):
        dateRange = dateRange.lower()
        if dateRange == 'lastweek':
            return buildDateRange(7)
        if dateRange == 'lasttwoweeks':
            return buildDateRange(14)
        if dateRange == 'lastmonth':
            return buildDateRange(30)
        if dateRange == 'lastquarter':
            return buildDateRange(90)
        if dateRange == 'lastyear':
            return buildDateRange(365)

    ydaStart, yda = getDayStartEnd( datetime.datetime.now() - datetime.timedelta(days=1) )
    nowStart, now = getDayStartEnd( datetime.datetime.now() )
    if dateRange.get('end', None) is not None:
        endStart, end = getDayStartEnd( dateRange['end'] )
        end = min(end, now)
    else:
        end = now

    start = None
    if dateRange.get('start', None) is not None:
        start, startEnd = getDayStartEnd( dateRange['start'] ) 
    else:
        if guardStartDate:
            start = getYMD(end - datetime.timedelta(days=6))

    if guardStartDate:
        start = max( start, getYMD(now - datetime.timedelta(days=365)) )  

    return {
        "start" : start,
        "end" : end
    }

def uncompressMongoBinary(binary, b64=False):
    if b64:
        binary = base64.b64decode(binary)
    decompressed = zlib.decompress(binary)
    return json.loads(decompressed)

def uniqueId(prefix='id'):
    if not hasattr(flask.request, 'uniqueId'):
        flask.request.uniqueId = 0
    id = flask.request.uniqueId
    flask.request.uniqueId += 1
    return "%s_%s" % (prefix, id)

def safeDivide(top, bottom):
    if bottom == 0:
        return 0
    else:
        return top / bottom

def isExistingFileInCloudstorage(cloudstorageFilename):
    try:
        gcs.stat(cloudstorageFilename)
        return True
    except Exception, e:
        return False
    return False

def getPhotoServingUrl(gsFilePath, size=None):
    blobKey = blobstore.create_gs_key('/gs%s' % gsFilePath)
    return images.get_serving_url(blobKey, size=size, secure_url=True)

def sideloadToCloudstorage(targetUrl, cloudstorageFilename):
    response = urllib2.urlopen(targetUrl)
    _saveToCloudstorage(response, cloudstorageFilename)

def saveImageToCloudstorage(targetUrl, cloudstorageFilename, ):
    respone = None
    try:
        #response = urllib2.urlopen(targetUrl)
        req = urllib2.Request(targetUrl, headers={'User-Agent' : "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/534.30 (KHTML, like Gecko) Ubuntu/11.04 Chromium/12.0.742.112 Chrome/12.0.742.112 Safari/534.30"})
        response = urllib2.urlopen(req)
    except urllib2.URLError, e:
        msg = "failed to fetch image: %s" % targetUrl
        logging.error("%s,  original: %s" % (msg, e))
        return False, msg

    mimetype = response.info()['content-type']
    if mimetype in ['image/gif', 'image/jpeg', 'image/png']:
        _saveToCloudstorage(response, cloudstorageFilename, mimetype=mimetype)
        return True, None
    return False, "mimetype %s" % mimetype

def _saveToCloudstorage(response, cloudstorageFilename, mimetype=None):
    BUFFER_SIZE = 100 * 1024 # 100kb
    with gcs.open(cloudstorageFilename, 'w', content_type=mimetype) as gcsFile:
        while True:
            buffer = response.read(BUFFER_SIZE)
            gcsFile.write(buffer)
            if buffer == "":
                break

def segmentFile(file, startTag, endTag, blockSize):
    rangeIterator = chunkFile(file, startTag, endTag, yieldSegments=True)
    count = 0
    segments = []
    for rangeChunks in chunkIterator(rangeIterator, blockSize):
        count += len(rangeChunks)
        segments.append((rangeChunks[0][0], rangeChunks[-1][1]))
    return {
        'segments': segments,
        'count': count,
    }

def statFromCloudstorage(cloudstorageFilename):
    return gcs.stat(cloudstorageFilename)

def strip(str):
    if str:
        return str.strip()
    return str

def tabularize(objects):
    """
        Given a list of dictionaries, create a tabular array.
    """
    keys = set()

    for object in objects:
        for key in object.keys():
            keys.add(key)

    header = sorted(keys)

    table = []
    for object in objects:
        row = []
        for key in header:
            value = object.get(key, None)
            row.append(value)
        table.append(row)

    return {
        'header': header,
        'table': table,
    }

def timeWithEst(dt):
    return TARGET_ZONE.localize(dt)

def timeWithLocal(dt):
    return LOCAL_ZONE.localize(dt)

def timestamp(dt):
    timetuple = dt.timetuple()
    return calendar.timegm(timetuple)