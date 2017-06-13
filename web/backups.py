import cloudstorage
import datetime
import flask
import uuid
import pickle
import logging

from google.appengine.ext import ndb

from web.base import BaseView, Route
from web.ndbChunker import ChunkNdb
from web import rutil
from web import config

class BackedupNdbModel(ndb.Model):

    __abstract__ = True

    lastUpdate = ndb.DateTimeProperty(auto_now=True)

    @classmethod
    def getBackupQuery(cls):
        return cls.query()

class BackupLog(ndb.Model):

    modelCls = ndb.StringProperty()
    time = ndb.DateTimeProperty(auto_now_add=True)

class BackupModelsByClassTask(ChunkNdb):

    route = '/background/backup-by-class/'
    keysOnly = False

    def handle(self, chunk, modelCls):
        filename = "%s/%s+%s" % (
            modelCls.__name__,
            datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
            str(uuid.uuid4()),
        )
        bucket = config.CONFIG['BACKUP']['BUCKET']
        path = "/%s/%s" % (bucket, filename)
        logging.info(path)
        asDicts = []
        for item in chunk:
            asDict = item.to_dict()
            asDict['key'] = item.key
            asDicts.append(asDict)
        with cloudstorage.open(path, 'w') as outfile:
            pickle.dump(asDicts, outfile)

class BackupStarter(BaseView):

    @Route('/background/start-backups/')
    def get(self):
        queue = config.CONFIG['BACKUP']['QUEUE']
        for module in flask.current_app.modelModules:
            for modelCls in rutil.getSubclasses(module, BackedupNdbModel):
                modelName = modelCls.__name__
                recent = BackupLog.query()\
                    .filter(BackupLog.modelCls == modelName)\
                    .order(-BackupLog.time)\
                    .get()
                
                query = modelCls.getBackupQuery()
                if recent is not None:
                    query = query.filter(modelCls.lastUpdate >= recent.time)
                    
                log = BackupLog(modelCls=modelName)
                log.put()
                
                BackupModelsByClassTask.invoke(
                    query=query, 
                    modelCls=modelCls,
                    queue=queue,
                )
        return "OK"