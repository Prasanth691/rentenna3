import datetime
import logging

from web import memcache
from web import rtime
from web.base import BaseView, Route
from web.config import CONFIG
from web.counters.counterModels import CounterValue

class CounterReaper(BaseView):

    @Route('/background/reap-counters/')
    def reap(self):
        now = rtime.toTarget(datetime.datetime.now())
        for counter in CONFIG['COUNTERS']:
            key = counter['key']
            granularity = counter['granularity']
            timeKey = CounterValue.getTimeKey(now, granularity)
            modelKey = "%s/%s" % (key, timeKey)
            memcacheKey = 'web:counter:%s' % key
            amount = memcache.get(memcacheKey) or 0
            if amount:
                memcache.decr(memcacheKey, amount)

                existingCounter = CounterValue.get_by_id(modelKey)

                if existingCounter:
                    existingCounter.value += amount
                    logging.info("%s: %s (incr by %s)" % (
                        modelKey, 
                        existingCounter.value,
                        amount,
                    ))
                    existingCounter.put()
                else:
                    logging.info("%s: %s (new)" % (modelKey, amount))
                    CounterValue(
                        id=modelKey,
                        value=amount,
                    ).put()
        return "OK"