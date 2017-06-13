# a memcache wrapper that does gzip compression

import StringIO
import pickle
import zlib
import base64

from web import memcache

from web import rutil

def get(key):
    key = "GZ:" + key
    compressed = memcache.get(key)
    if compressed:
        return _decompress(compressed)

def set(key, value, expires):
    key = "GZ:" + key
    compressed = _compress(value)
    memcache.set(key, compressed, expires)

def _compress(obj):
    serialized = pickle.dumps(obj)
    compressed = zlib.compress(serialized)
    return compressed

def _decompress(binary):
    decompressed = zlib.decompress(binary)
    return pickle.loads(decompressed)