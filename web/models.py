import flask
import pipeline
import hashlib
import datetime
import re
import hashlib
import uuid
import pickle
import base64

from pipeline import PipelineStatusError
from google.appengine.ext import ndb

from web import config
from web import memcache
from web import tracking
from web.backups import BackedupNdbModel

class ChangeLog(ndb.Model):

    entryDate = ndb.DateTimeProperty(auto_now_add=True)
    oldValues = ndb.PickleProperty() # dict
    newValues = ndb.PickleProperty() # dict
    note = ndb.TextProperty()

    @classmethod
    def getChanges(cls, target):
        return ChangeLog.query(ancestor=target.key)\
            .order(-ChangeLog.entryDate)\
            .fetch()

    @classmethod
    def update(cls, target, newValues, note=None):
        oldValues = {}
        updated = False

        for key, newValue in newValues.iteritems():
            oldValue = getattr(target, key)
            if newValue != oldValue:
                oldValues[key] = oldValue
                setattr(target, key, newValue)
                newValues[key] = newValue
                updated = True

        if oldValues or note:
            ChangeLog(
                parent=target.key,
                oldValues=oldValues, 
                newValues=newValues,
                note=note,
            ).put()

        return updated

class Counter(ndb.Model):

    value = ndb.IntegerProperty()

    @classmethod
    @ndb.transactional(use_cache=False, use_memcache=False)
    def getNext(cls, key, initValue=0, step=1):
        model = Counter.get_by_id(key)
        if model is None:
            model = Counter(value=initValue, id=key)
        elif model.value < initValue:
            model.value = initValue
        else:
            model.value += step
        model.put()
        return model.value

class PartnerBulkLog(ndb.Model):
    action = ndb.StringProperty()
    csvKeys = ndb.KeyProperty(repeated=True)
    gcsName = ndb.StringProperty()
    partnerKey = ndb.KeyProperty()
    created = ndb.DateTimeProperty(auto_now_add=True)
    user = ndb.StringProperty()

    @classmethod
    def forPartnerKey(cls, partnerKey, limit=10):
        return PartnerBulkLog\
            .query()\
            .filter(PartnerBulkLog.partnerKey == partnerKey)\
            .order(-PartnerBulkLog.created)\
            .fetch(limit)

    def createCsvLog(self, name, headers):
        csvLog = PartnerCsvLog()
        csvLog.initLog(name, headers)
        csvLog.put()
        self.csvKeys.append(csvLog.key)
        return csvLog

    def getLog(self):
        log = self.getSimpleLog()
        log["user"] = self.user
        log["partnerKey"] = self.partnerKey.urlsafe()
        files = []
        for csvLog in ndb.get_multi(self.csvKeys):
            files.append({
                    csvLog.name : csvLog.info 
                })

        log["files"] = files
        return log
        
    def getSimpleLog(self):
        total, totalLines = self.getTotalCounts()
        return {
            "action" : self.action,
            "created" : str(self.created),
            "total" : total,
            "totalLines" : totalLines,
            "finished" : self.isFinished(),
            "gcsName" : self.gcsName,
        }

    def isFinished(self):
        logs = ndb.get_multi(self.csvKeys)
        for log in logs:
            if log.info['status'] != 'finished':
                return False;
        return True

    def getTotalCounts(self):
        total = 0
        totalLines = 0
        logs = ndb.get_multi(self.csvKeys)
        for log in logs:
            total += log.info["count"]
            totalLines += log.info["lineCount"]
        return total, totalLines

class PartnerCsvLog(ndb.Model):
    info = ndb.PickleProperty()
    name = ndb.StringProperty()

    def initLog(self, name, headers):
        self.name = name
        self.info = {
            "count" : 0,
            "lineCount" : 0,
            "status" : "processing",
            "headers" : headers,
            "log" : [],
        }

class PartnerDailyAggsLog(ndb.Model):
    tag = ndb.StringProperty()
    prevDate = ndb.DateTimeProperty()
    nextDate = ndb.DateTimeProperty()
    date = ndb.DateTimeProperty(auto_now_add=True)

    @classmethod
    def create(cls, tag, prevDate, nextDate):
        obj = cls(id=tag, tag=tag, prevDate=prevDate, nextDate=nextDate)
        return obj

class PartnerDailyEmailTemplateAggsLog(PartnerDailyAggsLog):
    pass

class LongTermCache(ndb.Model):

    created = ndb.DateTimeProperty(auto_now_add=True)
    payload = ndb.PickleProperty()

    @classmethod
    def getKey(cls, key, returnTime=False):
        return cls.getKeyMulti([key], returnTime)[0]

    @classmethod
    def getKeyMulti(cls, keys, returnTime=False):
        ndbKeys = [
            ndb.Key(LongTermCache, key)
            for key 
            in keys
        ]
        results = []
        for result in ndb.get_multi(ndbKeys):
            if result:
                if returnTime:
                    results.append((result.created, result.payload))
                else:
                    results.append(result.payload)
            else:
                results.append(None)

        return results

    @classmethod
    def putArbitrary(cls, value):
        return LongTermCache(
            payload=value,
        ).put()

    @classmethod
    def putKey(cls, key, value):
        LongTermCache(
            id=key,
            payload=value,
        ).put()

class TaskPayload(ndb.Model):

    payload = ndb.PickleProperty()

class UserAggsTaskLog(ndb.Model):
    aggKeys = ndb.KeyProperty(repeated=True)
    created = ndb.DateTimeProperty(auto_now_add=True)
    params = ndb.PickleProperty()
    user = ndb.StringProperty()


    def createAggLog(self, aggType):
        log = UserSingleTaskLog(aggType=aggType, done=False)
        log.put()
        self.aggKeys.append(log.key)
        return log

    def isDone(self):
        logs = ndb.get_multi(self.aggKeys, use_cache=False)
        for log in logs:
            if not log.done:
                return False;
        return True
class SingleTaskLog(ndb.Model):
    done = ndb.BooleanProperty()
    created = ndb.DateTimeProperty(auto_now_add=True)
    updated = ndb.DateTimeProperty(auto_now=True)

class UserSingleTaskLog(SingleTaskLog):
    aggType = ndb.StringProperty()

class ExportLog(ndb.Model):
    exportType = ndb.StringProperty()
    fileType = ndb.StringProperty()
    queryStr = ndb.TextProperty()
    isDone = ndb.BooleanProperty(default=False)
    created = ndb.DateTimeProperty(auto_now_add=True)
    ended = ndb.DateTimeProperty(auto_now=True)
    gcsName = ndb.StringProperty()
    gcsPath = ndb.StringProperty()
    segments = ndb.PickleProperty()
    headers = ndb.PickleProperty()
    bucket = ndb.StringProperty()

class UserExportLog(ExportLog):
    isAR = ndb.BooleanProperty()
    partnerName = ndb.StringProperty()
    partnerApiKey = ndb.StringProperty()
    targetPartnerName = ndb.StringProperty()
    targetPartnerApiKey = ndb.StringProperty()
    dateRange = ndb.PickleProperty()
    pass

class PartnerExportSingleTaskLog(SingleTaskLog):
    pass

class PartnerExportLog(ExportLog):
    partnerKey = ndb.KeyProperty()
    dateRange = ndb.PickleProperty()
    shard = ndb.StringProperty()

    @classmethod
    def forPartnerKey(cls, partnerKey, limit=10):
        return PartnerBulkLog\
            .query()\
            .filter(PartnerBulkLog.partnerKey == partnerKey)\
            .order(-PartnerBulkLog.created)\
            .fetch(limit)

    
