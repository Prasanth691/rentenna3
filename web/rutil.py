import base64
import math
import time
import logging
import re
import pickle
import csv
import inspect
import hashlib
import os
import urllib
import urlparse

from google.appengine.ext import ndb

def augmentUrl(url, values):
    parseUrl = urlparse.urlparse(url)
    parseDict = dict(urlparse.parse_qsl(parseUrl.query))
    parseDict.update((k,v) for k,v in values.items() if v is not None)
    urlParams = urllib.urlencode(parseDict)
    newUrl = '%s%s?%s' % (
        parseUrl.netloc,
        parseUrl.path, 
        urlParams
    )
    if parseUrl.scheme:
        newUrl = "%s://%s" % (parseUrl.scheme, newUrl)
    return newUrl

def b64Pickle(obj):
    return base64.b64encode(pickle.dumps(obj))

def b64Unpickle(obj):
    return pickle.loads(base64.b64decode(obj))

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

def distance(p1, p2):
    # compute distance of two geojson points without being ridiculous
    # fuck you brian ledger... outputs meters
    from math import sin, cos, sqrt, atan2, radians

    R = 6373000.0

    lat1 = radians(p1['coordinates'][1])
    lon1 = radians(p1['coordinates'][0])
    lat2 = radians(p2['coordinates'][1])
    lon2 = radians(p2['coordinates'][0])

    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = (sin(dlat/2))**2 + cos(lat1) * cos(lat2) * (sin(dlon/2))**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

def getSubclasses(module, parent):
    for key in dir(module):
        if not key.startswith('_'):
            cls = getattr(module, key)
            if inspect.isclass(cls) and ('__abstract__' not in cls.__dict__)\
                    and issubclass(cls, parent):
                yield cls

def isDev():
    return os.environ.get('SERVER_SOFTWARE','Development').startswith('Development')

@ndb.tasklet
def returnTasklet(value):
    raise ndb.Return(value)

@ndb.tasklet
def sumCountAsync(query1, query2):
    count1, count2 = yield(query1.count_async(), query2.count_async())
    raise ndb.Return(count1 + count2)

def keyify(string):
    if string:
        string = string.lower()
        string = re.sub(r'[^a-z0-9]', ' ', string)
        string = string.strip()
        string = re.sub(r' +', '-', string)
        return string

def listify(item):
    if isinstance(item, list):
        return item
    elif item:
        return [item]
    else:
        return []

def naturalSorted(items, key=lambda x: x):

    def atoi(text):
        return int(text) if text.isdigit() else text

    def naturalKeys(value, first=True):
        if first:
            value = key(value)
        
        if value is None:
            return "~~~~~~~~~~~~~~~~~~~~~"
        elif isinstance(value, basestring):
            keys = [atoi(c) for c in re.split(r'(\d+)', value)]
            return keys
        elif isinstance(value, list) or isinstance(value, tuple):
            return [naturalKeys(x, False) for x in value]
        else:
            return value

    return sorted(items, key=naturalKeys)

def ndbGetMemo(key, memo):
    if key not in memo:
        memo[key] = key.get()
    return memo[key]

def ndbGetMultiCachable(keys, expires=None, bypassCache=False):
    from web import gzmemcache
    from google.appengine.ext import ndb
    sha = hashlib.sha224()
    for key in keys:
        sha.update(key.urlsafe())
    cacheKey = "rutil.ndbGetMultiCachable:1:%s" % (sha.hexdigest())
    results = gzmemcache.get(cacheKey)
    if bypassCache or (results is None):
        results = ndb.get_multi(keys)
        gzmemcache.set(cacheKey, results, expires)
    return results

def ndbIterate(query, chunkSize=100, **queryOptions):
    for chunk in ndbIterateChunked(query, chunkSize, **queryOptions):
        for result in chunk:
            yield result

def ndbIterateChunked(query, chunkSize=100, **queryOptions):
    cursor = None
    hasMore = True
    while hasMore:
        results, cursor, hasMore = query.fetch_page(chunkSize, start_cursor=cursor, **queryOptions)
        yield results

def ndbPaginate(page, perPage, query, countLimit=None, **queryOptions):
    totalCount = query.count(limit=countLimit)
    totalPages = int(math.ceil(totalCount / float(perPage)))
    start = (page-1) * perPage
    results = query.fetch(perPage, offset=start, **queryOptions)
    return {
        'total': totalCount,
        'page': page,
        'pages': totalPages,
        'results': results,
    }

def paginateIterator(iter, total, perPage):
    totalPages = int(math.ceil(total / float(perPage)))
    for (i, chunk) in enumerate(chunkIterator(iter, perPage)):
        yield {
            'total': total,
            'page': i+1,
            'pages': totalPages,
            'results': chunk,
        }

def plural(number, singularVersion, pluralVersion=None):
    return "%s %s" % (number, 
        pluralName(number, singularVersion, pluralVersion))

def pluralName(number, singularVersion, pluralVersion=None):
    if number == 1:
        return singularVersion
    else:
        return pluralVersion or (singularVersion + "s")

def portableStrHash(string):
    md5 = hashlib.md5()
    md5.update(str(string))
    digest = md5.hexdigest()
    hash = int(digest, 16)
    return hash

def safeAccess(obj, *keys):
    current = obj
    for key in keys:
        if current is not None:
            try:
                current = current[key]
            except (KeyError, IndexError, TypeError) as err:
                if isinstance(key, basestring):
                    current = getattr(current, key, None)
                else:
                    current = None
    return current

def updateInTx(model, **kwargs):
    @ndb.transactional(use_cache=False, use_memcache=False)
    def update():
        if isinstance(model, ndb.Key):
            fresh = model.get()
        else:  
            fresh = model.key.get()
        for key, value in kwargs.items():
            if isinstance(value, TxIncrement):
                oldValue = getattr(fresh, key, 0)
                newValue = oldValue + value.value
                setattr(fresh, key, newValue)
            else:  
                setattr(fresh, key, value)
        fresh.put()
        return fresh
    fresh = update()
    for key in kwargs.keys():
        if isinstance(model, ndb.Key):
            setattr(model.get(), key, getattr(fresh, key))
        else:
            setattr(model, key, getattr(fresh, key))

def unicodeCsvReader(infile, **kwargs):
    reader = csv.reader(infile, **kwargs)
    for row in reader:
        yield [unicode(cell, 'utf-8') for cell in row]

class Interner(object):

    def __init__(self):
        self.map = {}
        self.inverseMap = {}
        self.count = 0

    def intern(self, string):
        if string not in self.map:
            self.map[string] = self.count
            self.inverseMap[self.count] = string
            self.count += 1
        return self.map[string]

    def unintern(self, id):
        return self.inverseMap.get(id)

class Profile(object):

    def __init__(self, label="Profile"):
        self.label = label

    def __enter__(self):
        self.start = time.time()

    def __exit__(self, extype, exvalue, traceback):
        duration = time.time() - self.start
        logging.info("%s: %ss" % (self.label, duration))

class TxIncrement(object):

    # used by updateInTx to mark an incremental update

    def __init__(self, value):
        self.value = value