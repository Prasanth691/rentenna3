from google.appengine.ext import ndb

from web import rtime

class CounterValue(ndb.Model):

    @classmethod
    def find(cls, key, time, granularity):
        # TODO: maybe look up the granularity from the config?
        timeKey = cls.getTimeKey(time, granularity)
        modelKey = "%s/%s" % (key, timeKey)
        return CounterValue.get_by_id(modelKey)

    @classmethod
    def getTimeKey(cls, time, granularity):
        if granularity == 'month':
            timeKey = time.strftime('%Y-%m')
        elif granularity == 'week':
            timeKey = str(rtime.getWeek(time))
        elif granularity == 'day':
            timeKey = time.strftime('%Y-%m-%d')
        elif granularity == 'hour':
            timeKey = time.strftime('%Y-%m-%dT%H')
        return timeKey

    value = ndb.IntegerProperty()