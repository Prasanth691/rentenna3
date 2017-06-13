import urllib

from bson import ObjectId
from pymongo import MongoClient
from pymongo.mongo_replica_set_client import MongoReplicaSetClient
from pymongo.read_preferences import ReadPreference

from web import config
from web import rutil
from web import keyserver
from web.mongo import MongoAggsModel

class AggsPipeline(object):

    __abstract__ = True

    def __init__(self, **kwargs):
        self.options = kwargs

    def addPipeline(self, pipeline, item):
        if item:
            pipeline.append(item)

    def buildPipelines(self):
        pipelines = []

        self.addPipeline( pipelines, self.preMatchStage() )
        self.addPipeline( pipelines, self.unwindStage() )
        self.addPipeline( pipelines, self.matchStage() )
        self.addPipeline( pipelines, self.groupStage() )
        self.addPipeline( pipelines, self.projectStage() )

        return pipelines
    
    def getPipelines(self):
        if not hasattr(self, '_pipelines'):
            self._pipelines = self.buildPipelines()
        return self._pipelines

    
    def preMatchStage(self):
        return None

    def unwindStage(self):
        return None

    def matchStage(self):
        return None
        
    def groupStage(self):
        return None
        
    def projectStage(self):
        return None

class TagDailyAggsPipeline(AggsPipeline):
    
    __abstract__ = True

    PRE_MATCH = None
    AGG_MATH = None
    DATE_FIELD_LOOKUP = None
    GROUP_BY_TEMPLATE = False

    def preMatchStage(self):
        if not hasattr(self, "_preMatchStage"):
            aggType = self.options.get("aggType")
            tags = self.options.get("tags")
            dateRange = self.options.get("dateRange")
            shard = self.options.get("shard") or "production"
            user = self.options.get("user")
            

            date = {}
            if dateRange['start']:
                date["$gte"] = dateRange['start']
            if dateRange['end']:
                date["$lte"] =  dateRange['end']
            
            self._preMatchStage = {
                "$match" : {
                    "tags" : {
                        "$in" : tags
                    },
                    "date" : date,
                    "shard" : shard,
                }
            }

            templates = self.options.get("templates") #note: this is only used for user daily email aggregation
            if templates:
                self._preMatchStage['$match']['template'] = {
                    "$in" : templates
                }

            match = self._preMatchStage["$match"]

            dateCol = self.DATE_FIELD_LOOKUP.get(aggType, 'date')
            if dateCol != 'date':
                del match['date']
                match[dateCol] = date

            more = self.PRE_MATCH[aggType]
            if more:
                # if isinstance(more, tuple):
                #     fieldName = more[0]
                #     if match.get(fieldName, None) is None:
                #         match[fieldName] = more[1]
                # else:
                for key in more:
                    if match.get(key, None) is None:
                        match[key] = more[key]
            if user:
                match['user'] = user

            # if templates:
            #     if not isinstance(templates, list)
            #         templates = [templates]
            #         match['template'] = { "$in" : templates}

        return self._preMatchStage
            
    def unwindStage(self):
        return {
            "$unwind" : "$tags"
        }

    def matchStage(self):
        tags = self.options.get("tags")
        if not hasattr(self, "_matchStage"):
            self._matchStage = {
                "$match" : {
                    "tags" : {
                        "$in" : tags
                    },
                    # "nonce" : {
                    #     "$exists" : True
                    # }
                },
            }
        return self._matchStage

    def groupStage(self):
        if not hasattr(self, "_groupStage"):
            aggType = self.options.get("aggType")

            date = '$%s' % self.DATE_FIELD_LOOKUP.get(aggType, 'date')
            formula = self.AGG_MATH[aggType]

            self._groupStage = {
                "$group" : {
                    '_id': {
                        'day' : {
                            '$dateToString': {
                                'format': "%Y-%m-%d",
                                'date': date
                            }
                        },
                        'tag' : '$tags',
                    },
                    'val': formula,
                    'first': {
                      '$first':  date
                    }
                }
            }

            if self.GROUP_BY_TEMPLATE:
                self._groupStage["$group"]["_id"]["template"] = "$template"

        return self._groupStage
        
    def projectStage(self):
        
        if not hasattr(self, "_projectStage"):
            self._projectStage = {
                "$project" : {
                    "_id":0, 
                    "day": "$_id.day",
                    "tag": "$_id.tag",
                    "dayDate" : "$first",
                    "val" : "$val",
                }
            }

            if self.GROUP_BY_TEMPLATE:
                self._projectStage["$project"]["template"] = "$_id.template"

        return self._projectStage

class EmailDailyAggsPipeline(TagDailyAggsPipeline):
    AGG_MATH = {
        'open' : {'$sum': 1},
        'click' : {'$sum': '$msgclc'},
        'delivery' : {'$sum': 1},
        'unsub' : {'$sum': 1},
        'total' : {'$sum': 1},
        'unopen' : {'$sum' : 1},
    }

    DATE_FIELD_LOOKUP = {
        'unsub' : 'unsubscribed'
    }

    PRE_MATCH = {
        'open' : {'msgopb' : True},
        'unopen' : {'msgopb' : {'$exists' : False}, 'suppressed' : False},
        'click' : {'msgclb' : True},
        'delivery' : {'suppressed' : False},
        #'unsub' : ('unsubscribed', {'$exists' : True}),
        'unsub' : None,
        'total' : None,
    }

class EmailDailyTemplateAggsPipeline(EmailDailyAggsPipeline):
    GROUP_BY_TEMPLATE = True

class ReportViewDailyAggsPipeline(TagDailyAggsPipeline):
    AGG_MATH = {
        'reportview' : {'$sum': 1},
    }

    DATE_FIELD_LOOKUP = {
        'reportview' : 'viewed'
    }

    PRE_MATCH = {
        'reportview' : None,
    }

class MsgSentAggregate(MongoAggsModel):
    collectionName = 'msgsnd'

class ReportViewsAggregate(MongoAggsModel):
    collectionName = 'reportViews'

class UserCountAggregate(MongoAggsModel):
    collectionName = 'user'

class UserCountDailyAggsPipeline(TagDailyAggsPipeline):
    AGG_MATH = {
        'user' : {'$sum': 1},
        'subscriber' : {'$sum': 1},
    }

    DATE_FIELD_LOOKUP = {
        'user' : 'registered',
        'subscriber' : 'firstSubDate',
    }

    PRE_MATCH = {
        'user' : None,
        'subscriber' : {'firstSubDate' : {'$ne' : None}},
    }

class PartnerSummaryAggsPipeline(AggsPipeline):

    def preMatchStage(self):
        if not hasattr(self, "_preMatchStage"):
            tags = self.options.get("tags")
            dateRange = self.options.get("dateRange")
            shard = self.options.get("shard") or "production"

            date = {}
            if dateRange['start']:
                date["$gte"] = dateRange['start']
            if dateRange['end']:
                date["$lte"] =  dateRange['end']
            
            self._preMatchStage = {
                "$match" : {
                    "tag" : {
                        "$in" : tags,
                    },
                    "dayDate" : date,
                    "shard" : shard,
                }
            }
        return self._preMatchStage

    def groupStage(self):
        if not hasattr(self, "_groupStage"):
            self._groupStage = {
                "$group" : {
                    '_id': '$tag',
                    'reportViews' : {'$sum' : '$reportview'},
                    'sent' : {'$sum' : '$total'},
                    'delivered' : {'$sum' : '$delivery'},
                }
            }
        return self._groupStage

    def projectStage(self):
        if not hasattr(self, "_projectStage"):
            self._projectStage = {
                "$project" : {
                    "_id":0, 
                    "tag": "$_id",
                    "reportViews" : "$reportViews",
                    "sent" : "$sent",
                    "delivered" : "$delivered",
                }
            }
        return self._projectStage

class PartnerSummaryAggregate(MongoAggsModel):
    collectionName = 'partnerDailyAggs'

# class PartnerTemplateSummaryAggregate(MongoAggsModel):
#     collectionName = 'partnerTemplateDailyAggs'

class MongoCollectionUserHelper(object):
    USER_FIELD_LOOKUP = {
        "user" : "ndbKey",
        "msgsnd" : "user",
        "reportViews" : "user"
    }

    @classmethod
    def userField(cls, collectionName):
        if collectionName in cls.USER_FIELD_LOOKUP:
            return cls.USER_FIELD_LOOKUP[collectionName]
        return None

class UserDrilldownPipelineHelper(object):
    @classmethod
    def groupStage(cls, target):
        if not hasattr(target, "_groupStage"):
            aggType = target.options.get("aggType")
            collectionName = target.options.get("collectionName")
            userField = MongoCollectionUserHelper.userField(collectionName)

            date = '$%s' % target.DATE_FIELD_LOOKUP.get(aggType, 'date')
            formula = target.AGG_MATH[aggType]

            target._groupStage = {
                "$group" : {
                    '_id': {
                        'user' : '$%s' % userField,
                    },
                    'val': formula,
                }
            }
        return target._groupStage

    @classmethod
    def projectStage(cls, target):
        
        if not hasattr(target, "_projectStage"):
            target._projectStage = {
                "$project" : {
                    "_id":0,
                    "user" : "$_id.user",
                    "val" : "$val",
                }
            }

        return target._projectStage

class UserDrilldownEmailPipeline(EmailDailyAggsPipeline):
    def groupStage(self):
        return UserDrilldownPipelineHelper.groupStage(self)
        
    def projectStage(self):
        return UserDrilldownPipelineHelper.projectStage(self)

class UserDrilldownReportViewPipeline(ReportViewDailyAggsPipeline):
    def groupStage(self):
        return UserDrilldownPipelineHelper.groupStage(self)
        
    def projectStage(self):
        return UserDrilldownPipelineHelper.projectStage(self)

class UserDrilldownUserCountPipeline(UserCountDailyAggsPipeline):
    def groupStage(self):
        return UserDrilldownPipelineHelper.groupStage(self)
        
    def projectStage(self):
        return UserDrilldownPipelineHelper.projectStage(self)

