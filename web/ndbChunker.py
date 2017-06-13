# NOTE: Be careful not to import * from this, otherwise you will overwrite view defintions

import flask
import pickle
import uuid

from google.appengine.ext import ndb

from web import taskqueue
from web import validate
from web.base import BaseView, Route

class ChunkNdb(BaseView):

    __abstract__ = True
    route = None
    keysOnly = True
    continuationBefore = False

    class __metaclass__(type):

        def __init__(cls, name, bases, dict):
            type.__init__(cls, name, bases, dict)

            if '__abstract__' not in dict:
                def get(self):
                    return self.process()

                router = Route(cls.route, methods=['POST'])
                cls.get = router(get)

    @classmethod
    def invoke(
            cls, 
            query,
            orderDirection='ASC', # or DESC
            orderField=None,
            queue='default', 
            chunkSize=100, 
            taskName=None, 
            **kwargs
        ):
        if taskName is None:
            taskName = str(uuid.uuid4())
        taskqueue.add(
            url=cls.route,
            params={
                'query': pickle.dumps(query),
                'orderDirection': orderDirection,
                'orderField': orderField,
                'queue': queue,
                'chunkSize': chunkSize,
                'kwargs': pickle.dumps(kwargs),
                'name': taskName,
                'number': 0,
            },
            queue_name=queue,
            name="%s-%s" % (taskName, 0),
            swallow=True,
        )

    def process(self):
        query = validate.get('query', validate.Unpickle())
        cursor = validate.get('cursor', validate.Unpickle())
        chunkSize = validate.get('chunkSize', validate.ParseInt())
        kwargs = validate.get('kwargs', validate.Unpickle())
        queue = validate.get('queue')

        orderDirection = validate.get('orderDirection')
        orderField = validate.get('orderField')
        if orderField:
            queryClass = flask.current_app.ndbModels[query.kind]
            orderProperty = getattr(queryClass, orderField)
            if orderDirection == 'DESC':
                orderProperty = -orderProperty
            orderedQuery = query.order(orderProperty)
        else:
            orderedQuery = query

        results, cursor, more = orderedQuery.fetch_page(
            chunkSize,
            start_cursor=cursor,
            keys_only=self.keysOnly,
        )
        
        if results:
            if not self.continuationBefore:
                stop = self.handle(results, **kwargs)
            else:
                stop = False

            if not stop:
                # schedule next page
                name = validate.get('name')
                number = 1 + validate.get('number', validate.ParseInt())
                taskqueue.add(
                    url=self.route,
                    params={
                        'query': pickle.dumps(query),
                        'orderDirection': orderDirection,
                        'orderField': orderField,
                        'cursor': pickle.dumps(cursor),
                        'queue': queue,
                        'chunkSize': chunkSize,
                        'kwargs': pickle.dumps(kwargs),
                        'name': name,
                        'number': number,
                    },
                    queue_name=queue,
                    name="%s-%s" % (name, number),
                    swallow=True,
                )
            if self.continuationBefore:
                self.handle(results, **kwargs)
        else:
            self.finalize(**kwargs)

        return "OK"

    def handle(self, chunk, **kwargs):
        pass

    def finalize(self, **kwargs):
        pass

class ResultYieldingChunker(ChunkNdb):

    __abstract__ = True
    continuationBefore = True

    def process(self):
        final = validate.get('final', validate.ParseBool())
        check = validate.get('check', validate.ParseBool())
        if final:
            name = validate.get('name')
            number = validate.get('number', validate.ParseInt())
            kwargs = validate.get('kwargs', validate.Unpickle())
            keys = [
                ndb.Key(ResultYieldingChunkerResult, '%s-%s' % (name, i)) 
                for i 
                in range(0, number)
            ]
            results = ndb.get_multi(keys)
            results = [result.result for result in results]
            self.complete(results, **kwargs)
        elif check:
            self.checkForCompletion()
        else:
            ChunkNdb.process(self)
        return "OK"

    def complete(self, results, **kwargs):
        pass

    def run(self, chunk, **kwargs):
        pass

    def handle(self, chunk, **kwargs):
        result = self.run(chunk, **kwargs)
        name = validate.get('name')
        number = validate.get('number', validate.ParseInt())
        ResultYieldingChunkerResult(
            id='%s-%s' % (name, number),
            result=result,
        ).put()

    def finalize(self, **kwargs):
        self.checkForCompletion()

    def checkForCompletion(self):
        name = validate.get('name')
        number = validate.get('number', validate.ParseInt())
        kwargs = validate.get('kwargs', validate.Unpickle())
        queue = validate.get('queue')
        keys = [
            ndb.Key(ResultYieldingChunkerResult, '%s-%s' % (name, i)) 
            for i 
            in range(0, number)
        ]
        results = ndb.get_multi(keys)
        if None not in results:
            taskqueue.add(
                url=self.route,
                params={
                    'kwargs': pickle.dumps(kwargs),
                    'name': name,
                    'final': 'true',
                    'number': number,
                    'queue': queue,
                },
                queue_name=queue,
                name="%s-final" % (name),
                swallow=True,
            )
        else:
            taskqueue.add(
                url=self.route,
                params={
                    'kwargs': pickle.dumps(kwargs),
                    'name': name,
                    'check': 'true',
                    'number': number,
                    'queue': queue,
                },
                queue_name=queue,
                countdown=10,
            )

class InvokeForAllNdb(ChunkNdb):

    route = '/background/invoke-for-all-ndb/'

    def handle(self, chunk, task, params=None):
        queue = validate.get('queue')
        for result in chunk:
            payload = {
                'key': result.urlsafe(),
            }
            if params:
                payload.update(params)
            taskqueue.add(
                url=task,
                params=payload,
                queue_name=queue,
            )
#This is for testing purpose, currently it is used by /admin/reap-alerts-temp/
class InvokeForOneNdbForTest(ChunkNdb):

    route = '/background/invoke-for-one-ndb-temp/'

    def handle(self, chunk, task, params=None):
        queue = validate.get('queue')
        for result in chunk:
            payload = {
                'key': result.urlsafe(),
            }
            if params:
                payload.update(params)
            taskqueue.add(
                url=task,
                params=payload,
                queue_name=queue,
            )
            break
        return True

class ResultYieldingChunkerResult(ndb.Model):

    result = ndb.PickleProperty()

class ResultYieldingChunkerInvocation(ndb.Model):

    number = ndb.IntegerProperty()