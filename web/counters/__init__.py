import datetime

from web import memcache
from web import rtime
from web.base import AppSubcomponent

from web.counters.counterModels import CounterValue

def getValue(key, granularity, time=None):
    if time is None:
        time = rtime.toTarget(datetime.datetime.now())
    counter = CounterValue.find(key, time, granularity)
    if counter:
        return counter.value
    else:
        return 0

def increment(key, amount=1):
    memcache.incr("web:counter:%s" % key, amount)

class CounterSubcomponent(AppSubcomponent):

    def augmentEnvironment(self, appInfo):
        import web.counters.counterViews
        appInfo.viewModules.append(web.counters.counterViews)