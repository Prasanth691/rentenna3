import cgi
import collections
import urllib
import urllib2
import urlparse
import json
import datetime
import re
import flask
import uuid
import logging
import hashlib
import random
import pickle
import numpy

from google.appengine.ext import ndb
from google.appengine.api import urlfetch
from google.appengine.api import memcache
from google.appengine.ext import blobstore
from bson import ObjectId

from web import config
from web import keyserver
from web import rutil
from web import tracking
from web import validate
from web.api import *
from web.backups import BackedupNdbModel
from web.blog.blogModels import *
from web.data.states import State
from web.mongo import NdbMongoModel
from web.models import *
from web.tracking import Tracker

from rentenna3 import util
from rentenna3 import base
from rentenna3.models import AlertSubscription
from rentenna3.base import *
from rentenna3.data.cities import NEW_YORK_CITY_SLUGS_SET
from rentenna3.email import *

class User(NdbMongoModel):

    collectionName = 'user'
    ndbClassName = 'User'
    geoField = None

    @classmethod
    def convert(cls, item):
        obj = item.to_dict()
        obj['ndbKey'] = item.key.urlsafe()
        obj['shard'] = config.CONFIG['EMAIL']['shard']
        if item.partner:
            partner= item.partner.get()
            if partner:
                obj['partner'] = {
                    'ndbKey' : item.partner.urlsafe(),
                    'name' : partner.name,
                    'apiKey' : partner.apiKey,
                    'domain' : partner.getPreferredDomain(),
                }
                obj['tags'] = partner.getTags()
            else:
                del obj['partner']
                obj['tags'] = [
                    "partner:address-report",
                    "partner_direct:address-report"
                ]
        else:
            obj['tags'] = [
                "partner:address-report",
                "partner_direct:address-report"
            ]

        if item.tracker:
            tracker = item.tracker.get()
            if tracker:
                obj['tracker'] = tracker.to_dict()
                if obj['tracker']['parentId']:
                    del obj['tracker']['parentId']
                obj['tracker']['ndbKey'] = tracker.key.urlsafe()
                cls.removeNdbKey(obj['tracker'])
            else:
                del obj['tracker']

        if item.registeredTracker:
            tracker = item.registeredTracker.get()
            if tracker:
                obj['registeredTracker'] = tracker.to_dict()
                if obj['registeredTracker']['parentId']:
                    del obj['registeredTracker']['parentId']
                obj['registeredTracker']['ndbKey'] = tracker.key.urlsafe()
                cls.removeNdbKey(obj['registeredTracker'])
            else:
                del obj['registeredTracker']

        if not item.firstSubDate:
            firstAlert = AlertSubscription.firstAlert(item.key)
            if firstAlert:
                obj['firstSubDate'] = firstAlert.date

        if obj.get("partnerKey"):
            del obj["partnerKey"]

        if obj.get("charges"):
            del obj["charges"]

        if obj.get("stripeCustomer"):
            del obj["stripeCustomer"]

        if obj.get("chargeKeys"):
            del obj["chargeKeys"]

        if obj.get("plan"):
            del obj["plan"]

        geoPt = item.location
        if geoPt:
            obj['location'] = {
                "type" : "GeoPt",
                "latitude" : geoPt.lat,
                "longitude" : geoPt.lon,
            }
        cls.removeNdbKey(obj)

        return obj

    @classmethod
    def removeNdbKey(self, obj):
        from google.appengine.ext.ndb.key import Key
        if obj:
            for k,v in obj.items():
                if isinstance(v, Key):
                    del obj[k]

