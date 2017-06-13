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
from web.mongo import NdbMongoModel

class NdbToMongoLog(ndb.Model):

    modelCls = ndb.StringProperty()
    cutTime = ndb.DateTimeProperty()
    created = ndb.DateTimeProperty(auto_now_add=True)
    errorKeys = ndb.KeyProperty(repeated=True)
    hasError = ndb.BooleanProperty(default=False)
    notes = ndb.TextProperty(repeated=True)

class DumpModelsByClassTask(ChunkNdb):

    route = '/background/dump-to-mongo-by-class/'
    keysOnly = False

    def handle(self, chunk, modelCls, log):
        
        asDicts = []
        bulkOp = modelCls.getBulkOperator()
        hasError = False
        hasItem = False
        objs = []
        for item in chunk:
            obj = None
            try:
                obj = modelCls.convert(item)
                objs.append(obj)
                bulkOp.find(
                    {
                        'ndbKey': obj['ndbKey'],
                    }
                )\
                .upsert()\
                .replace_one(obj)
                hasItem = True
            except Exception as ee:
                hasError = True
                log.hasError = True
                log.errorKeys.append(item.key)

        if hasItem:
            try:
                logging.info(bulkOp.execute())
            except Exception as e:
                log.hasError = True
                for item in objs:
                    log.notes.append(str(item))
                log.put()
                raise e

        if hasError:
            log.put()

class DumpToMongoStarter(BaseView):

    @Route('/background/start-dump-ndb-to-mongo/')
    def get(self):
        queue = 'default'
        for module in flask.current_app.ndbMongoModelModules:
            for modelCls in rutil.getSubclasses(module, NdbMongoModel):
                modelName = modelCls.__name__
                recent = NdbToMongoLog.query()\
                    .filter(NdbToMongoLog.modelCls == modelName)\
                    .order(-NdbToMongoLog.created)\
                    .get()
                
                ndbCls = flask.current_app.ndbModels[modelCls.ndbClassName]
                if not ndbCls:
                    logging.warning('Can not find corresponding ndb class name: %s ' % modelCls.ndbClassName)
                else:
                    query = ndbCls.query()
                    if recent is not None:
                        query = query.filter(ndbCls.lastUpdate >= recent.cutTime)
                    
                    cutTime = datetime.datetime.now() - datetime.timedelta(minutes=70)    
                    log = NdbToMongoLog(modelCls=modelName, cutTime=cutTime)
                    log.put()
                    
                    DumpModelsByClassTask.invoke(
                        query=query, 
                        modelCls=modelCls,
                        queue=queue,
                        orderDirection='ASC',
                        orderField='lastUpdate',
                        log=log,
                    )
        return "OK"