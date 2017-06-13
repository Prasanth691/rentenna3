import json
import flask
import copy
import re
import urllib
import uuid
import bson
import datetime
import base64
import datetime
import hashlib

from google.appengine.datastore.datastore_query import Cursor

from web import validate
from web import memcache
from web import rtime

from rentenna3 import util
from rentenna3.models import *

class SimplePager(object):

    __abstract__ = True

    def __init__(self, query, pageSize, url):
        self._query = query
        self._pageSize = pageSize
        self._url = url
        self._items = None
        self._hasNext = False
        self._redirectUrl = None
        self.page()

    def redirectUrl(self):
        return self._redirectUrl

    def items(self):
        return self._items

    def hasNext(self):
        return self._hasNext

    def queryId(self, page):
        raise NotImplemented

    def page(self):
        if not hasattr(self, '_page'):
            page = validate.get('page', validate.ParseInt())
            if not page:
                page = 1
            self._page = page
        return self._page


class NdbSimplePager(SimplePager):
    def __init__(self, query, pageSize, url):
        SimplePager.__init__(self, query, pageSize, url)

        page = self.page()
          
        qryId = self.queryId(page)
        cursor = memcache.get(qryId)
        
        if page > 1 and  cursor is None:
            self._redirectUrl = '%s?page=1' % url
        else:
            if cursor:    
                cursor = Cursor(urlsafe=cursor)

            items, cursor, more = query\
                .fetch_page (
                    pageSize,
                    start_cursor=cursor,
                ) 
            
            self._items = items
            if more:
                nextQryId = self.queryId(page+1)
                if memcache.get(nextQryId) is None:
                    memcache.set(nextQryId, cursor.urlsafe(), expires=3600)
                self._hasNext = True

    def queryId(self, page):
        hsh = hashlib.md5()
        hsh.update(repr(self._query))
        qryId = '%s:%s:%s' % ( hsh.hexdigest(), self._pageSize, page )
        return qryId

class MongoTimePager(SimplePager):
    
    dateFormat = "%Y-%m-%dT%H:%M:%S.%f"

    def __init__(self, modelCls, query, pageSize, url, dateField):
        SimplePager.__init__(self, query, pageSize, url)
        self._modelCls = modelCls
        self._dateField = dateField

        self._queryOrg = copy.deepcopy(query)
        
        page = self.page()

        qryId = self.queryId(page)
        cursor = memcache.get(qryId)

        if page > 1 and  cursor is None:
            self._redirectUrl = '%s?page=1' % url
        else:
            if cursor:    
                date = datetime.datetime.strptime(cursor, self.dateFormat)
                query[dateField] = {'$lt': date}

            items = modelCls.query(query, sort=[(dateField, -1)], limit=pageSize)
            more = False
            if items and len(items) == pageSize:
                cursor = items[-1][dateField].strftime(self.dateFormat)
                more = True
            else:
                cursor = None
                more = False
            
            self._items = items
            if more:
                nextQryId = self.queryId(page+1)
                if memcache.get(nextQryId) is None:
                    memcache.set(nextQryId, cursor, expires=3600)
                self._hasNext = True

    def queryId(self, page):
        
        qry = {
            'query' : self._queryOrg,
            'dateField' : self._dateField,
            'cls' : self._modelCls,
        }

        hsh = hashlib.md5()
        hsh.update(repr(qry))
        qryId = '%s:%s:%s' % ( hsh.hexdigest(), self._pageSize, page )
        return qryId




