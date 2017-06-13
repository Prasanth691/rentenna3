# a memcache wrapper that honors the _nocache url parameter

import flask

from google.appengine.api import memcache

from web import rutil

def get(key):
    if flask.request.values.get('_nocache') is not None:
        return None
    else:
        return memcache.get(key)

def decr(key, delta=1):
    memcache.decr(key, delta=delta)

def incr(key, delta=1):
    memcache.incr(key, delta=delta, initial_value=delta)

def set(key, value, expires=3600):
    memcache.set(key, value, expires)

def set_multi(mapping, expires):
    memcache.set_multi(mapping, expires)