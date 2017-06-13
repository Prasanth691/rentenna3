import urllib

from bson import ObjectId
from pymongo import MongoClient
from pymongo.mongo_replica_set_client import MongoReplicaSetClient
from pymongo.read_preferences import ReadPreference

from web import config
from web import rutil
from web import keyserver

class MongoModel(object):

    collectionName = None
    geoField = 'geo' # default field used by inBounds and getNearest

    def __init__(self, fromDb=False, **kwargs):
        self.__fromDb = fromDb
        for key, value in kwargs.items():
            setattr(self, key, value)

    @classmethod
    def inBounds(cls, coordinates, filter=None, geoField=None, **kwargs):
        geoField = geoField or cls.geoField
        query = {
            geoField: {
                '$geoIntersects': {
                    '$geometry': {
                        'type': "Polygon",
                        'coordinates': coordinates,
                    }
                }
            }
        }
        if filter:
            query.update(filter)
        return cls.query(query, **kwargs)

    @classmethod
    def insert(cls, document):
        mongo = cls.getMongo()
        collection = getattr(mongo, cls.collectionName)
        return collection.insert(document)

    @classmethod
    def getBulkOperator(cls):
        mongo = cls.getMongo()
        collection = getattr(mongo, cls.collectionName)
        return collection.initialize_unordered_bulk_op()

    @classmethod
    def getById(cls, id):
        return cls.queryFirst({'_id': cls.fromUrlsafe(id)})

    @classmethod
    def getMongo(cls):
        if not hasattr(MongoModel, '_mongo'):
            credentials = keyserver.get()['mongo']
            mongoClient = MongoClient(
                host=credentials['host'],
                port=credentials['port'],
            )
            mongoDb = getattr(mongoClient, credentials['database'])
            mongoDb.authenticate(
                credentials['user'],
                credentials['password'],
                mechanism='SCRAM-SHA-1',
            )
            MongoModel._mongo = mongoDb
        return MongoModel._mongo

    @classmethod
    def getNearest(cls, location, maxRadius=None, filter=None, geoField=None, count=False, **kwargs):
        geoField = geoField or cls.geoField
        query = {
            geoField: {
                '$nearSphere': {
                    '$geometry': location,
                }
            }
        }
        if maxRadius:
            query[geoField]['$nearSphere']['$maxDistance'] = maxRadius

        if filter:
            query.update(filter)
        if count:
            return cls.queryCount(query)
        else:
            results = cls.queryEx(query, **kwargs)
            for result in results:
                geo = result[geoField]
                if geo:
                    distance = rutil.distance(geo, location)
                    result.distance = distance
            return results

    @classmethod
    def fromUrlsafe(cls, id):
        if isinstance(id, ObjectId):
            return id
        else:
            if id.startswith('OID__'):
                return ObjectId(id[5:])
            else:
                return id

    # TODO: need to replace query method with this one, 
    # this one is for temp usage for old city,area at this moment
    @classmethod
    def queryEx(cls, query, fields=None, sort=None, limit=500, collectionName=None):
        mongo = cls.getMongo()
        collectionName = collectionName or cls.collectionName
        collection = getattr(mongo, collectionName)

        cursor = collection.find(query, fields=fields, sort=sort)
        #cursor = collection.find(query, sort=sort)
        if limit: cursor.limit(limit)
        return [cls(fromDb=True, **result) for result in cursor]

    @classmethod
    def query(cls, query, fields=None, sort=None, limit=500):
        mongo = cls.getMongo()
        collection = getattr(mongo, cls.collectionName)
        # cursor = collection.find(query, fields=fields, sort=sort)
        cursor = collection.find(query, sort=sort)
        if limit: cursor.limit(limit)
        return [cls(fromDb=True, **result) for result in cursor]

    @classmethod
    def queryCount(cls, query, limit=None, **kwargs):
        mongo = cls.getMongo()
        collection = getattr(mongo, cls.collectionName)
        cursor = collection.find(query)
        if limit: cursor.limit(limit)
        return cursor.count(True)

    @classmethod
    def queryIter(cls, query, fields=None, sort=None, limit=None):
        mongo = cls.getMongo()
        collection = getattr(mongo, cls.collectionName)
        # cursor = collection.find(query, fields=fields, sort=sort)
        cursor = collection.find(query, sort=sort)
        for result in cursor:
            yield cls(fromDb=True, **result)

    @classmethod
    def queryIterEx(cls, query, fields=None, sort=None, limit=None):
        mongo = cls.getMongo()
        collection = getattr(mongo, cls.collectionName)
        #cursor = collection.find(query, sort=sort)
        for result in cursor:
            yield cls(fromDb=True, **result)

    @classmethod
    def queryGeoref(cls, geo, filter=None, count=False, **kwargs):
        query = {
            cls.geoField: {
                '$geoIntersects': {
                    '$geometry': geo
                }
            }
        }
        if filter:
            query.update(filter)
        if count:
            return cls.queryCount(query, **kwargs)
        else:
            return cls.query(query, **kwargs)

    @classmethod
    def queryFirst(cls, query, fields=None):
        mongo = cls.getMongo()
        collection = getattr(mongo, cls.collectionName)

        if fields:
            result = collection.find_one(query, fields)
        else:
            result = collection.find_one(query)
        if result:
            return cls(fromDb=True, **result)
        else:
            return None

    @classmethod
    def urlsafe(cls, id):
        if isinstance(id, ObjectId):
            return 'OID__%s' % id
        else:
            return id

    @classmethod
    def update(cls, query, update, multi=False, upsert=False):
        mongo = cls.getMongo()
        collection = getattr(mongo, cls.collectionName)
        result = collection.update(query, update, multi=multi, upsert=upsert)
        return result

    @classmethod
    def distinct(cls, query, field):
        mongo = cls.getMongo()
        collection = getattr(mongo, cls.collectionName)
        cursor = collection.find(query)
        return cursor.distinct(field)
        #return [cls(fromDb=True, **result) for result in cursor]

    def get(self, key, default=None):
        return self.__dict__.get(key, default)

    def set(self, key, val):
        if self.__fromDb:
            raise NotImplementedError("can not set if data is from Db")
        setattr(self, key, val)
        return True

    def put(self):
        document = self.__json__()
        if hasattr(self, '_id'):
            self.__class__.update(
                {'_id': self._id},
                {'$set': document},
                upsert=True,
            )
        else:
            id = self.__class__.insert(document)
            self._id = id
        return self._id

    def __getitem__(self, key):
        return self.__dict__.get(key)

    def __contains__(self, key):
        return key in self.__dict__

    def __json__(self):
        document = {}
        for key, value in self.__dict__.items():
            if '__' not in key:
                document[key] = value
        return document

    def __str__(self):
        return "%s(%s)" % (self.__class__.__name__, self.__dict__)

    def __repr__(self):
        return self.__str__()

class MongoAggsModel(object):

    collectionName = None

    def __init__(self, fromDb=False, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    @classmethod
    def getById(cls, id):
        return cls.queryFirst({'_id': cls.fromUrlsafe(id)})

    @classmethod
    def getMongo(cls):
        if not hasattr(MongoModel, '_mongo'):
            credentials = keyserver.get()['mongo']
            mongoClient = MongoClient(
                host=credentials['host'],
                port=credentials['port'],
            )
            mongoDb = getattr(mongoClient, credentials['database'])
            mongoDb.authenticate(
                credentials['user'],
                credentials['password'],
                mechanism='SCRAM-SHA-1',
            )
            MongoModel._mongo = mongoDb
        return MongoModel._mongo

    @classmethod
    def fromUrlsafe(cls, id):
        if isinstance(id, ObjectId):
            return id
        else:
            if id.startswith('OID__'):
                return ObjectId(id[5:])
            else:
                return id

    @classmethod
    def query(cls, pipelines):
        mongo = cls.getMongo()
        collection = getattr(mongo, cls.collectionName)
        result = collection.aggregate(pipelines)

        if result:
            return cls(fromDb=True, **result)
        else:
            return None

    @classmethod
    def urlsafe(cls, id):
        if isinstance(id, ObjectId):
            return 'OID__%s' % id
        else:
            return id

    @classmethod
    def distinct(cls, query, field):
        mongo = cls.getMongo()
        collection = getattr(mongo, cls.collectionName)
        cursor = collection.find(query)
        return cursor.distinct(field)

    def get(self, key, default=None):
        return self.__dict__.get(key, default)

    def __getitem__(self, key):
        return self.__dict__.get(key)

    def __contains__(self, key):
        return key in self.__dict__

    def __json__(self):
        document = {}
        for key, value in self.__dict__.items():
            if '__' not in key:
                document[key] = value
        return document

    def __str__(self):
        return "%s(%s)" % (self.__class__.__name__, self.__dict__)

    def __repr__(self):
        return self.__str__()


class NdbMongoModel(MongoModel):
    __abstract__ = True
    ndbClassName = None

    @classmethod
    def convert(cls, obj):
        raise NotImplementedError("convert from ndb to mongo json obj")