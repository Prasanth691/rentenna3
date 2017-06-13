import cgi
import collections
import copy
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
from web.mongo import MongoModel
from web.models import *
from web.tracking import Tracker

from rentenna3 import util
from rentenna3 import base
from rentenna3.base import *
from rentenna3.data.cities import NEW_YORK_CITY_SLUGS_SET
from rentenna3.email import *

class BaseSf1MongoModel(MongoModel):

    def __init__(self, **kwargs):
        MongoModel.__init__(self, **kwargs)
        self.data = util.uncompressMongoBinary(self.data)

    def _getTableValues(self, tableId, cols):
        rowData = self.data.get(tableId)
        if not rowData:
            return None
        else:
            table = Sf1Table()
            offset = self._crawlTable(table, rowData, cols, 0)
            if len(rowData) != offset:
                raise ValueError("Data/Label Misalignment!!")
            return table

    def _crawlTable(self, table, rowData, labels, offset):
        for (name, children) in labels:
            value = rowData[offset]
            offset += 1

            subtable = table.addChild(name, value)
            offset = self._crawlTable(subtable, rowData, children, offset)
        return offset

class AcsSf1MongoModel(BaseSf1MongoModel):

    RACES = [
        'White Alone', 'Black Alone', 'Hispanic', 'Asian Alone',
        'One or More', 'Native American', 'Pacific Islander','Other'
    ]

    RACE_MAP = {
        'White Alone': 'A',
        'Black Alone': 'B',
        'Hispanic': 'I',
        'Asian Alone': 'D',
        'One or More': 'G',
        'Native American': 'C',
        'Pacific Islander': 'E',
        'Other': 'F',
    }

    collectionName = 'acsHeaders'

    def getChildren(self):
        return self._getTableValues('B11005', [
            ('Total', [
                ('Households with one or more people under 18 years', [
                    ('Family households', [
                        ('Married-couple family', []),
                        ('Other family', [
                            ('Male householder, no wife present', []),
                            ('Female householder, no husband present', []),
                        ]),
                    ]),
                    ('Nonfamily households', [
                        ('Male householder', []),
                        ('Female householder', []),
                    ]),
                ]),
                ('Households with no people under 18 years', [
                    ('Family households', [
                        ('Married-couple family', []),
                        ('Other family', [
                            ('Male householder, no wife present', []),
                            ('Female householder, no husband present', []),
                        ]),
                    ]),
                    ('Nonfamily households', [
                        ('Male householder', []),
                        ('Female householder', []),
                    ]),
                ]),
            ])
        ])

    def getCommuteMethods(self):
        return self._getTableValues('B08301', [
            ('Total', [
                ('Car', [
                    ('Drove alone', []),
                    ('Carpooled', [
                        ('2-person', []),
                        ('3-person', []),
                        ('4-person', []),
                        ('5-or-6-person', []),
                        ('7-or-more-person', []),
                    ]),
                ]),
                ('Public Transportation', [
                    ('Bus', []),
                    ('Streetcar', []),
                    ('Subway', []),
                    ('Railroad', []),
                    ('Ferryboat', []),
                ]),
                ('Taxicab', []),
                ('Motorcycle', []),
                ('Bicycle', []),
                ('Walked', []),
                ('Other means', []),
                ('Worked at home', []),
            ]),
        ])

    def getCommuteTimes(self):
        return self._getTableValues('B08303', [
            ('Total', [
                ('Under 5', []),
                ('5 to 9', []),
                ('10 to 14', []),
                ('15 to 19', []),
                ('20 to 24', []),
                ('25 to 29', []),
                ('30 to 34', []),
                ('35 to 39', []),
                ('40 to 44', []),
                ('45 to 59', []),
                ('60 to 89', []),
                ('90+', []),
            ]),
        ])

    def getEarningsBySex(self):
        incomes = [
            ('Under $2k', []),
            ('$2,000', []),
            ('$5,000', []),
            ('$7,000', []),
            ('$10,000', []),
            ('$12,000', []),
            ('$15,000', []),
            ('$17,000', []),
            ('$20,000', []),
            ('$22,000', []),
            ('$25,000', []),
            ('$30,000', []),
            ('$35,000', []),
            ('$40,000', []),
            ('$45,000', []),
            ('$50,000', []),
            ('$55,000', []),
            ('$65,000', []),
            ('$75,000', []),
            ('$100,000+', []),
        ]
        return self._getTableValues('B20001', [
            ('Total', [
                ('Male', incomes),
                ('Female', incomes)
            ])
        ])

    def getEducation(self):
        return self._getTableValues('B15003', [
            ('Total', [
                ('No Schooling', []),
                ('Nursery School', []),
                ('Kindergarten', []),
                ('1st grade', []),
                ('2nd grade', []),
                ('3rd grade', []),
                ('4th grade', []),
                ('5th grade', []),
                ('6th grade', []),
                ('7th grade', []),
                ('8th grade', []),
                ('9th grade', []),
                ('10th grade', []),
                ('11th grade', []),
                ('12th grade', []),
                ('High School Diploma', []),
                ('GED', []),
                ('Under a Year of College', []),
                ('Some College, No Degree', []),
                ('Associate\'s Degree', []),
                ('Bachelor\'s Degree', []),
                ('Master\'s Degree', []),
                ('Professional School Degree', []),
                ('Doctorate Degree', []),
            ])
        ])

    def getGeographicMobility(self):
        return self._getTableValues('B07003', [
            ('Total', [
                ('Male', []),
                ('Female', []),
                ('Same house 1 year ago', [
                    ('Male', []),
                    ('Female', []),
                ]),
                ('Moved within same county', [
                    ('Male', []),
                    ('Female', []),
                ]),
                ('Moved from same state', [
                    ('Male', []),
                    ('Female', []),
                ]),
                ('Moved from different state', [
                    ('Male', []),
                    ('Female', []),
                ]),
                ('Moved from abroad', [
                    ('Male', []),
                    ('Female', []),
                ]),
            ])
        ])

    def getHouseholdIncome(self):
        return self._getTableValues('B19001', [
            ('Total', [
                ('Under $10k', []),
                ('$10,000', []),
                ('$15,000', []),
                ('$20,000', []),
                ('$25,000', []),
                ('$30,000', []),
                ('$35,000', []),
                ('$40,000', []),
                ('$45,000', []),
                ('$50,000', []),
                ('$60,000', []),
                ('$75,000', []),
                ('$100,000', []),
                ('$125,000', []),
                ('$150,000', []),
                ('$200,000+', []),
            ]),
        ])

    def getMaritalStatus(self):
        return self._getTableValues('B11001', [
            ('Total', [
                ('Family households', [
                    ('Married-couple family', []),
                    ('Other family', [
                        ('Male householder, no wife present', []),
                        ('Female householder, no husband present', []),
                    ]),
                ]),
                ('Nonfamily households', [
                    ('Householder living alone', []),
                    ('Householder not living alone', []),
                ]),
            ]),
        ])

    def getMaritalStatusBySexAndAge(self):
        ages = [
            ('15-17', []),
            ('18-19', []),
            ('20-24', []),
            ('25-29', []),
            ('30-34', []),
            ('35-39', []),
            ('40-44', []),
            ('45-49', []),
            ('50-54', []),
            ('55-59', []),
            ('60-64', []),
            ('65-74', []),
            ('75-84', []),
            ('85+', []),
        ]
        return self._getTableValues('B12002', [
            ('Total', [
                ('Male', [
                    ('Never Married', ages),
                    ('Married, Spouse Present', [
                        ('Currently Married', ages),
                    ]),
                    ('Married, Spouse Absent', [
                        ('Seperated', ages),
                        ('Other', ages),
                    ]),
                    ('Widowed', ages),
                    ('Divorced', ages),
                ]),
                ('Female', [
                    ('Never Married', ages),
                    ('Married, Spouse Present', [
                        ('Currently Married', ages),
                    ]),
                    ('Married, Spouse Absent', [
                        ('Seperated', ages),
                        ('Other', ages),
                    ]),
                    ('Widowed', ages),
                    ('Divorced', ages),
                ])
            ])
        ])

    def getMedianAgeBySex(self):
        return self._getTableValues('B01002', [
            ('Total', [
                ('Male', []),
                ('Female', []),
            ]),
        ])

    def getMedianIncomeStats(self):
        return self._getTableValues('B19326', [
            ('Total', [
                ('Male', [
                    ('Worked Full-Time', []),
                    ('Other', []),
                ]),
                ('Female', [
                    ('Worked Full-Time', []),
                    ('Other', []),
                ]),
            ])
        ])

    def getMedianHouseholdIncome(self):
        return self._getTableValues('B19013', [('Total', [])])

    def getPlaceOfBirth(self):
        return self._getTableValues('B05002', [
            ('Total', [
                ('Native', [
                    ('In this State', []),
                    ('In Different State', [
                        ('Northeast', []),
                        ('Midwest', []),
                        ('South', []),
                        ('West', []),
                    ])
                ]),
                ('Outside of USA', [
                    ('Puerto Rico', []),
                    ('U.S. Island', []),
                    ('Abroad w/ U.S. Parents', []),
                ]),
                ('Foreign', [
                    ('Naturalized U.S. Citizen', []),
                    ('Not a U.S. Citizen', []),
                ])
            ])
        ])

    def getTotalPopulation(self):
        population = self._getTableValues('B01003', [('Total', [])])
        return population

    def getTimeLeavingForWork(self):
        return self._getTableValues('B08302', [
            ('Total', [
                ('12:00 AM to 4:59 AM', []),
                ('5:00 AM to 5:29 AM', []),
                ('5:30 AM to 5:59 AM', []),
                ('6:00 AM to 6:29 AM', []),
                ('6:30 AM to 6:59 AM', []),
                ('7:00 AM to 7:29 AM', []),
                ('7:30 AM to 7:59 AM', []),
                ('8:00 AM to 8:29 AM', []),
                ('8:30 AM to 8:59 AM', []),
                ('9:00 AM to 9:59 AM', []),
                ('10:00 AM to 10:59 AM', []),
                ('11:00 AM to 11:59 AM', []),
                ('12:00 PM to 3:59 PM', []),
                ('4:00 PM to 11:59 PM', []),
            ]),
        ])

    def getSexByAgeForRace(self, race):
        ages = [
            ('<5', []),
            ('5-9', []),
            ('10-14', []),
            ('15-17', []),
            ('18-19', []),
            ('20-24', []),
            ('25-29', []),
            ('30-34', []),
            ('35-44', []),
            ('45-54', []),
            ('55-64', []),
            ('65-74', []),
            ('75-84', []),
            ('85+', []),
        ]
        return self._getTableValues('B01001%s' % self.RACE_MAP[race], [
            ('Total', [
                ('Male', ages),
                ('Female', ages),
            ])
        ])

    def getRaceBySex(self):
        raceTables = [self.getSexByAgeForRace(race) for race in self.RACES]
        zipped = zip(self.RACES, raceTables)
        return {
            'Male': [(race, raceTable.get('Total', 'Male'))
                for (race, raceTable) in zipped],
            'Female': [(race, raceTable.get('Total', 'Female'))
                for (race, raceTable) in zipped],
        }

class Address(MongoModel):

    collectionName = 'addresses5_2'
    geoField = 'location'
    SKIP_GEO_FIELDS = {
        'geo' : 0,
        'geo_simple' : 0,
        'geometry' : 0
    }

    def __init__(self, **kwargs):
        MongoModel.__init__(self, **kwargs)
        if not self.get('city'):
            self.city = 'other'

    @classmethod
    def getByAddr(cls, addr):
        return cls.queryFirst({'addr': addr})

    @classmethod
    def getByCaddr(cls, caddrString):
        caddr = CanonicalAddrs.queryFirst({'_id': ObjectId(caddrString)})
        return Address.queryFirst({'addr': caddr.preferred})

    @classmethod
    def getBySlug(cls, slug):
        return cls.queryFirst({'slug': slug})

    @classmethod
    def simpleForm(cls, address):
        if not address:
            return None

        location = address.getLocation()
        latitude = None
        longitude = None
        if location:
            coords = location['coordinates']
            if coords and len(coords) > 1:
                longitude = coords[0]
                latitude = coords[1]

        addr = {
            'addressSlug' : address.slug,
            'street' : address.addrStreet,
            'city' : address.addrCity,
            'state' : address.addrState,
            'zipcode' : address.addrZip,
            'fullAddress' : address.getFullAddress(),
            'latitude' : latitude,
            'longitude' : longitude,
        }
        return addr

    def getArea(self, skipGeo=False):
        if self.areas:
            areaSlug = self.areas[0]
            if skipGeo:
                if not hasattr(self, '_areaSkipGeo'):
                    self._areaSkipGeo = Area.queryFirst({ 'slug': areaSlug }, fields=Address.SKIP_GEO_FIELDS)
                return self._areaSkipGeo
            else:
                if not hasattr(self, '_area'):
                    self._area = Area.queryFirst({ 'slug': areaSlug })
                return self._area

    def getAreas(self):
        if not hasattr(self, '_areas'):
            self._areas = Area.query({ 'slug': { '$in': self.areas } })
        return self._areas

    def getAreaSlug(self):
        if self.areas:
            return self.areas[0]

    def getCanonicalAddress(self):
        if self.isPreferred:
            return self
        else:
            caddr = CanonicalAddrs.queryFirst({'alt': self.addr})
            if not caddr:
                return self # well woops!
            else:
                return Address.queryFirst({'addr': caddr.preferred}) or self # woops again!

    def getCaddrString(self):
        return str(self.caddr)

    def getCity(self, skipGeo=False):
        if skipGeo:
            if not hasattr(self, '_citySkipGeo'):
                self._citySkipGeo = City.queryFirst({'slug' : self.city}, fields=Address.SKIP_GEO_FIELDS)
            return self._citySkipGeo
        else:
            if not hasattr(self, '_city'):
                self._city = City.forSlug(self.city)
            return self._city

    def getCityName(self):
        if self.city == 'other':
            return self.addrCity
        else:
            return self.getCity().name

    def getCitySlug(self):
        return self.city

    def getBuildingName(self, stats):
        return stats.get('buildingName')

    def getCommonName(self, stats):
        buildingName = self.getBuildingName(stats)
        commonName = buildingName or self.getShortName()
        return commonName

    def getFullName(self, stats):
        buildingName = self.getBuildingName(stats)
        if buildingName:
            fullName = "%s at %s" % (buildingName, self.getShortName())
        else:
            fullName = self.getShortName()
        return fullName

    def getLocation(self):
        return self.get(Address.geoField, None)

    def getProperty(self):
        address = self.getCanonicalAddress()
        propertyKey = ndb.Key(Property, address.slug)
        return Property.get(propertyKey, address=address)

    def getReportStatKey(self):
        return ndb.Key(Property, self.slug)

    def getState(self):
        city = self.getCity()
        if city and city.isOther():
            return city.getState()
        else:
            return ArState.forAbbr(self.addrState)

    def getFullAddress(self):
        return "%s, %s, %s %s" % (
            self.addrStreet,
            self.addrCity,
            self.addrState,
            self.addrZip,
        )

    def getShortName(self):
        return self.addrStreet

    def getUrl(self, domain=False, require=None):
        if require == 'email':
            url = "/send-me/property/%s/%s/" % (self.city, self.slug)
        else:
            url = "/report/property/%s/%s/" % (self.city, self.slug)
        if domain:
            return flask.request.appCustomizer.urlBase() + url
        else:
            return url

    def getZipcode(self):
        return self.addrZip

    def ndbKey(self):
        return ndb.Key(
            'caddr',
            self.getCaddrString()
        )

class AlertSubscription(BackedupNdbModel):

    date = ndb.DateTimeProperty(auto_now_add=True)
    property = ndb.KeyProperty(kind='Property')
    user = ndb.KeyProperty(kind='User')

    @classmethod
    def subscribe(cls,
            propertyKey,
            mode='alert',
            user=None,
            partner=None,
            quiz=False,
            skipConfirmationEmail=False,
            quizSlug=None
        ):
        if not user:
            user = User.get()

        # if user.unsubscribed:
        #     user.unsubscribed = None
        #     user.put()

        existing = cls.get(propertyKey, userKey=user.key)
        if not existing:
            userHasAlert = cls.hasAlert(user.key)

            property = Property.get(propertyKey)
            key = AlertSubscription(
                user=user.key,
                property=propertyKey,
            ).put()

            saveUser = False
            if not userHasAlert:
                saveUser = True
                user.firstSubDate = datetime.datetime.now()
            
            if not user.street:
                address = Address.getBySlug(propertyKey.id())
                if address:
                    saveUser = True
                    user.setAddressInfo(address, addressFrom='alert')

            if saveUser:    
                user.put()

            if not skipConfirmationEmail:
                if mode == 'alert':
                    SubscribeForAlerts.send(
                        property=property,
                        user=user,
                    )
                else:
                    address = property.getAddress()
                    ReportGenerated.send(
                        commonName=address.getShortName(),
                        target=address.getUrl(True),
                        type='address',
                        user=user,
                    )

    @classmethod
    def unsubscribe(cls, propertyKey, userKey=None):
        existing = cls.get(propertyKey, userKey=userKey)
        if existing:
            # TODO: unsubscribe without deleting!
            existing.key.delete()

    @classmethod
    def unsubscribeAll(cls, userKey):
        keys = AlertSubscription.query()\
                .filter(AlertSubscription.user == userKey)\
                .iter(keys_only=True)
        # TODO: unsubscribe without deleting!
        ndb.delete_multi(keys)

    @classmethod
    def get(cls, propertyKey, userKey=None):
        if not userKey:
            userKey = User.get().key
        if userKey:
            return AlertSubscription.query()\
                .filter(AlertSubscription.user == userKey)\
                .filter(AlertSubscription.property == propertyKey)\
                .get()

    @classmethod
    def hasAlert(cls, userKey):
        alert = AlertSubscription.query()\
            .filter(AlertSubscription.user == userKey)\
            .get()

        if alert:
            return True
        return False

    @classmethod
    def firstAlert(cls, userKey):
        alert = AlertSubscription.query()\
            .filter(AlertSubscription.user == userKey)\
            .order(AlertSubscription.date)\
            .get()

        return alert

    @classmethod
    def isSubscribed(cls, propertyKey):
        existing = cls.get(propertyKey)
        return existing is not None

    def getAddress(self):
        return Address.getBySlug(self.property.id())

class Area(MongoModel):

    collectionName = 'obiBoundariesNh3_2'
    geoField = 'geometry'

    @classmethod
    def forCity(cls, citySlug):
        return cls.queryEx(
            {'city': citySlug},
            sort=[('name', 1)],
            fields={'city': 1, 'slug': 1, 'name': 1, 'children': 1},
            limit=1000,
        )

    @classmethod
    def forSlug(cls, areaSlug):
        area = cls.query(
            {'slug': areaSlug},
            fields={'geometry': False},
        )

        if area:
            return area[0]
        else:
            return None

    def getUrl(self):
        return "/report/neighborhood/%s/%s/" % (self.city, self.slug)

    def __init__(self, **kwargs):
        MongoModel.__init__(self, **kwargs)
        self.parent = None
        self.name = self.get('name')
        self.children=(self.get('children') or [])

    def getCity(self):
        return City.forSlug(self.city)

    def getChildren(self):
        return cls.query({ 'slug': { '$in': self.children } })

    def getDepth(self):
        parent = self.getParent()
        if parent:
            return 1 + parent.getDepth()
        else:
            return 1

    def getFieldValue(self, fieldname):
        field = self.get(fieldname)
        if field:
            return field
        else:
            return self.getFullCopy().get(fieldname)

    def getFullCopy(self):
        return Area.queryFirst({'slug': self.slug})

    def getGeo(self):
        return self.getFieldValue('geometry')

    def getGeoSimple(self):
        return self.getFieldValue('geometry')

    def getParent(self):
        if self.parent:
            return Area.forSlug(self.parent)

    def getRanks(self):
        ranking = AreaRanking.get_by_id(self.slug)
        if ranking:
            return ranking.ranks

    def getReportStatKey(self):
        return ndb.Key('Area', self.slug)

    def getUrl(self, domain=False, require=None, page=None):
        if require == 'email':
            url = "/send-me/neighborhood/%s/%s/" % (self.city, self.slug)
        else:
            url = "/report/neighborhood/%s/%s/" % (self.city, self.slug)
            if page is not None:
                url += "%s/" % page
        if domain:
            return flask.request.appCustomizer.urlBase() + url
        else:
            return url

class ArState(State):

    def getUrl(self):
        return '/%s-cities/' % self.slug

class AreaVoterCounts(MongoModel):

    collectionName = 'areaVoterCounts3'

    def toDict(self):
        counts = dict(self.__dict__)
        del counts['_id']
        del counts['area']
        return counts

class AreaRanking(ndb.Model):

    # id is slug

    ranks = ndb.PickleProperty() # slug -> [rank, total]

class ArDataControl(MongoModel):

    collectionName = 'arDataControl'

    @classmethod
    def forName(cls, name):
        shard = config.CONFIG['EMAIL']['shard']
        return cls.queryFirst({'name': name, 'shard' : shard})

    def getName(self):
        return self.name

    def getLiveCollection(self):
        return self.liveCollection

    def getUpdated(self):
        return self.updated

    def getEmailed(self):
        return self.emailed

    def getBatchId(self):
        return self.batchId

class Autocomplete(MongoModel):

    collectionName = 'autoc3_1'
    geoField = 'center'

    @classmethod
    def search(cls, prefix, types=None, bias=None):
        # TODO: bias by location
        prefix = prefix.strip()
        origPrefix = prefix
        terms = re.split(',+', prefix)
        prefix = terms[0].strip()

        statePrefix = None
        if len(terms) == 2:
            statePrefix = terms[1].strip()

        cityPrefix = None
        if len(terms) >= 3:
            cityPrefix = terms[1].strip()
            statePrefix = terms[2].strip()

        query = cls.buildQuery(prefix, statePrefix, cityPrefix, types)

        result = cls.fetchResult(query, bias)
        if not result and statePrefix is None and cityPrefix is None:
            result = cls.reFetch(result, origPrefix, bias, types)

        return result

    @classmethod
    def buildQuery(cls, prefix, statePrefix, cityPrefix, types):
        query = {
            'search': {
                '$regex': '^%s.*' % prefix.upper(),
            },
        }

        cls.updateStateAndCityFilter(query, statePrefix, cityPrefix)

        if types:
            query['type'] = {
                '$in': types,
            }
        return query

    @classmethod
    def updateStateAndCityFilter(cls, query, statePrefix, cityPrefix):
        if not statePrefix:
            return query

        if cityPrefix:
            query['cityState'] = {
                '$regex': '^%s.*' % statePrefix.upper(),
            }

            query['city'] = {
                '$regex': '^%s.*' % cityPrefix.lower(),
            }
        else:
            query['$or'] = [
                {
                    'cityState' : {
                        '$regex': '^%s.*' % statePrefix.upper(),
                    }
                }
                ,
                {
                    'city' : {
                        '$regex': '^%s.*' % statePrefix.lower(),
                    }
                }
                ,
            ]
        return query

    @classmethod
    def fetchResult(cls, query, bias):
        if bias:
            return cls.getNearest(location=bias, filter=query, limit=10)
        else:
            return cls.query(query, limit=10)

    @classmethod
    def reFetch(cls, oldResult, prefix, bias, types):
        terms = re.split('\W+', prefix)
        if len(terms) > 1:
            statePrefix = terms.pop().strip()
            prefix = ' '.join(terms)
            
            query = cls.buildQuery(prefix, statePrefix, None, types)
            return cls.fetchResult(query, bias)

        return oldResult

    def getJson(self):
        cityName = rutil.safeAccess(self, 'cityName') or ''
        cityState = rutil.safeAccess(self, 'cityState') or ''
        if self.type == 'area':
            return {
                'type': self.type,
                'name': self.name,
                'city': self.city,
                'cityName': cityName,
                'cityState': cityState,
                'slug': self.slug,
                'reportUrl': "/report/neighborhood/%s/%s/" % (
                    self.city,
                    self.slug,
                )
            }
        elif self.type == 'city':
            return {
                'type': self.type,
                'name': self.name,
                'cityState': cityState,
                'slug': self.slug,
                'reportUrl': "/report/city/%s/" % (
                    self.slug,
                ),
            }
        elif self.type == 'zip':
            return {
                'type': self.type,
                'name': self.name,
                'city': self.city,
                'cityName': cityName,
                'cityState': cityState,
                'slug': self.slug,
                'reportUrl': "/report/zip/%s/%s/" % (
                    self.city,
                    self.slug,
                ),
            }

class AutocompleteElastic(object):

    indexName = 'autoc3_1'
    typeName = 'nh_city_zip'
    geoField = 'loc'

    @classmethod
    def search(cls, prefix, types=None, bias=None):
        # TODO: bias by location
        prefix = prefix.strip()
        origPrefix = prefix
        terms = re.split(',+', prefix)
        prefix = terms[0].strip()

        statePrefix = None
        cityPrefix = None

        if len(terms) == 2:
            last = terms[1].strip()
            if len(last) < 3:
                statePrefix = last
            else:
                cityPrefix = last
 
        if len(terms) >= 3:
            cityPrefix = terms[1].strip()
            statePrefix = terms[2].strip()

        if not cityPrefix and not statePrefix:
            terms = re.split('\s+', prefix)
            if len(terms) >= 3:
                terms.pop(0)
                cityPrefix = " ".join(terms)

        query = cls.buildQuery(origPrefix, prefix, statePrefix, cityPrefix, types, bias)

        from elasticsearch import Elasticsearch
        
        es = Elasticsearch(['104.196.164.82', '104.196.160.244'],send_get_body_as='POST')
        results = es.search(
            index=cls.indexName, 
            doc_type=cls.typeName, 
            body={
                "query": query
            },
            #filter_path=['hits.hits._source'],
        )

        sources = [cls.getJson(item['_source']) for item in results['hits']['hits']]
        return sources

    @classmethod
    def buildQuery(cls, term, prefix, statePrefix, cityPrefix, types, bias):
        boolQuery = {
            "must" : [
                {
                    "match" : {
                        "searchline2" : {
                            "query" : prefix,
                            "analyzer" : "standard"
                        }
                    }
                }
            ],
        }

        query = { "bool" : boolQuery }

        if types:
            filtered = {
                "filtered" : {
                    "query" : query,
                    "filter" : {
                        "terms" : { "type" : types}
                    }
                }
            }
            query = filtered

        should = []
        boolQuery["should"] = should

        should.append({
            "prefix" : {
                "search" : prefix[:3]
            }
        })

        if cityPrefix or statePrefix:
            if statePrefix:
                should.append({
                    "match" : {
                        "cityState.cityStateLine" : {
                            "query" : statePrefix,
                            "analyzer" : "standard"
                        }
                    }
                })

            if cityPrefix:
                should.append({
                    "match" : {
                        "cityName.cityNameLine" : {
                            "query" : cityPrefix,
                            "analyzer" : "standard"
                        }
                    }
                })

        if bias:
            query = {
                    "function_score" : {
                        "functions" : [
                            {
                                "exp" : { 
                                    "loc" : {
                                        "origin" : {"lat" : bias['coordinates'][1], "lon" : bias['coordinates'][0]},
                                        "scale" : "4000km",
                                        "offset": "200km",
                                    }
                                } 
                            }
                        ]
                        ,
                        "query" : query
                        ,
                        "score_mode" : "sum"
                    }
                }

        return query

    @classmethod
    def getJson(cls, item):
        cityName = rutil.safeAccess(item, 'cityName') or ''
        cityState = rutil.safeAccess(item, 'cityState') or ''
        locType = item['type']
        city = item['city']
        slug = item['slug']
        obj = {
            'type': locType,
            'name': item['name'],
            'city': city,
            'cityName': cityName,
            'cityState': cityState,
            'slug': slug,
        }
        if locType == 'area':
            obj['reportUrl'] = "/report/neighborhood/%s/%s/" % (
                    city,
                    slug,
                )
            return obj
        elif locType == 'city':
            obj['reportUrl'] = "/report/city/%s/" % (
                    slug,
                )
            return obj
        elif locType == 'zip':
            obj['reportUrl'] = "/report/zip/%s/%s/" % (
                    city,
                    slug,
                )
            return obj

class AutocompleteUnitElastic(object):

    indexName = 'autoc_units3'
    typeName = 'property_with_unit'
    geoField = 'loc'

    @classmethod
    def search(cls, prefix, types=None, bias=None):

        # TODO: bias by location
        prefix = prefix.strip()
        tokens = re.split('\s+', prefix)
        if len(tokens) < 3:
            return []
        
        query = cls.buildQuery(prefix, types, bias)

        from elasticsearch import Elasticsearch
        
        es = Elasticsearch(['104.196.164.82', '104.196.160.244'],send_get_body_as='POST')
        results = es.search(
            index=cls.indexName, 
            doc_type=cls.typeName, 
            body={
                "query": query
            },
            #filter_path=['hits.hits._source'],
        )
        sources = [cls.getJson(item['_source']) for item in results['hits']['hits']]
        return sources

    @classmethod
    def buildQuery(cls, term, types, bias):
        query = {
            "match" : {
                "oneline" : {
                    "query" : term,
                    "analyzer" : "standard"
                }
            }
        }

        # we may not need the bias for unit search to improve performance
        # if bias:
        #     query = {
        #             "function_score" : {
        #                 "functions" : [
        #                     {
        #                         "exp" : { 
        #                             "loc" : {
        #                                 "origin" : {"lat" : bias['coordinates'][1], "lon" : bias['coordinates'][0]},
        #                                 "scale" : "4000km",
        #                                 "offset": "200km",
        #                             }
        #                         } 
        #                     }
        #                 ]
        #                 ,
        #                 "query" : query
        #                 ,
        #                 "score_mode" : "sum"
        #             }
        #         }

        return query

    @classmethod
    def getJson(cls, item):

        desc = item['oneline']
        query = desc
        zipcode = item['OBI_ZIP']
        if zipcode:
            query = "%s %s" % (query, zipcode)
        obj = {
            'type': "address",
            'name': desc,
            'reference': '',
            'reportUrl': "/find-address/?%s" % urllib.urlencode({
                'query': query,
                'callback': "report",
            }),
        }
        return obj

class BuildingMongoModel(MongoModel):

    collectionName = 'buildings'

    @classmethod
    def getBySlug(cls, slug):
        building = util.first(cls.query({'id.slug': slug}, limit=1))
        return building

    def __init__(self, **kwargs):
        MongoModel.__init__(self, **kwargs)
        if not 'city' in self:
            self.city = 'other'

    def getAreas(self):
        if 'areas' in self:
            for area in self.areas:
                yield Area.forSlug(area)

    def getCanonicalBuilding(self):
        if 'canonicalAddrId' in self:
            if self.canonicalAddrId not in self.id['addr']:
                canonicalBuilding = util.first(BuildingMongoModel.query(
                    {'id.addr': self.canonicalAddrId}
                ))
                if canonicalBuilding:
                    return canonicalBuilding
        return self

    def getCity(self):
        return City.forSlug(self.city)

    def getFullAddress(self):
        return "%s, %s, %s %s" % (
            self.address['canonical'],
            self.address['city'],
            self.address['state'],
            self.address['zip'],
        )

    def getFullName(self):
        return self.getFullAddress()

    def getShortName(self):
        return self.address['canonical']

    def isCanonicalBuilding(self):
        if 'canonicalAddrId' not in self:
            return True
        else:
            return self.canonicalAddrId in self.id['addr']

class CanonicalAddrs(MongoModel):

    collectionName = 'caddrs3'

class CensusSf1MongoModel(BaseSf1MongoModel):

    collectionName = 'censusHeaders'

    def getHouseholdSizeByType(self):
        return self._getTableValues('p28', [
            ('Total', [
                ('Family', [
                    ('2', []),
                    ('3', []),
                    ('4', []),
                    ('5', []),
                    ('6', []),
                    ('7+', []),
                ]),
                ('Nonfamily', [
                    ('1', []),
                    ('2', []),
                    ('3', []),
                    ('4', []),
                    ('5', []),
                    ('6', []),
                    ('7+', []),
                ]),
            ]),
        ])

    def getAgeBySex(self):
        ages = ['0']
        ages += [str(x) for x in range(1, 100)]
        ages += ['100-104', '105-109', '110+']
        ages = [(age, []) for age in ages]
        return self._getTableValues('pct12', [
            ('Total', [
                ('Male', ages),
                ('Female', ages),
            ])
        ])

class ChicagoBuildingFootprint(MongoModel):

    collectionName = 'chicagoBuildingFootprints'

class CitibikeStation(MongoModel):

    collectionName = 'nycCitibikes'

    def public(self):
        return {
            'location': self.geo,
            'key': self.id,
        }

class City(MongoModel):

    collectionName = 'obiBoundariesCp3_2'
    geoField = 'geometry'

    @classmethod
    def important(cls):
        from rentenna3.data.cities import CITIES
        return cls.query({ 'slug': { '$in': CITIES } })

    @classmethod
    def forSlug(cls, slug):
        from rentenna3.data import cities
        if (slug is not None) and (slug != 'other'):
            city = cls.query(
                {'slug': slug},
            )

            if city:
                return city[0]

        return cls(slug='other', **cities.PSEUDO_CITY_OTHER)

    @classmethod
    def forState(cls, state):
        return cls.query(
            {'state': state.abbr},
            fields={'name': 1, 'slug': 1, 'center': 1, 'bounds': 1, 'state': 1},
            sort=[('name', 1)],
            limit=10000,
        )

    def __init__(self, focus=None, distance=None, searchName=None, **kwargs):
        MongoModel.__init__(
            self,
            focus=focus,
            distance=distance,
            searchName=searchName,
            **kwargs
        )

    def public(self):
        return {
            'name': self.name,
            'slug': self.slug,
            'center': self.center,
            'bounds': self.bounds,
        }

    def getCity(self):
        return self

    def getFieldValue(self, fieldname):
        field = self.get(fieldname)
        if field:
            return field
        else:
            return self.getFullCopy().get(fieldname)

    def getFullCopy(self):
        return City.queryFirst({'slug': self.slug})

    def getGeo(self):
        return self.getFieldValue('geometry')

    def getGeoSimple(self):
        return self.getFieldValue('geometry')

    def getDistance(self, type):
        from rentenna3.data.cities import DISTANCE_DEFAULTS
        if self.distance:
            return self.distance[type]
        else:
            return DISTANCE_DEFAULTS[type]

    def getFocus(self):
        return self.focus or self.bounds

    def getReportStatKey(self):
        return ndb.Key('City', self.slug)

    def getSearchName(self):
        if self.searchName:
            return self.searchName
        else:
            return "%s, %s" % (self.name, self.state)

    def getState(self):
        return ArState.forAbbr(self.state)

    def getUrl(self, domain=False, require=None, page=None):
        if require == 'email':
            url = '/send-me/city/%s/' % self.slug
        else:
            url = '/report/city/%s/' % self.slug
            if page is not None:
                url += "%s/" % page
        if domain:
            return flask.request.appCustomizer.urlBase() + url
        else:
            return url

    def isOther(self):
        return self.slug == "other"

    def isFull(self):
        return self.slug in NEW_YORK_CITY_SLUGS_SET

class CrawlLog(ndb.Model):

    crawler = ndb.StringProperty()
    count = ndb.IntegerProperty()
    date = ndb.DateTimeProperty(auto_now_add=True)
    target = ndb.StringProperty()

class EmailSendLog(MongoModel):

    collectionName = 'msgsnd'

    # date
    # nonce
    # suppressed
    # shard
    # user
    # unsubscribed
    # fromEmail
    # toEmail
    # subject
    # email

    @classmethod
    def make(
            cls,
            nonce,
            suppressed,
            userKey,
            emailFields,
            template,
            tags,
        ):
        from web import config
        sendLogId = EmailSendLog(
            nonce=nonce,
            suppressed=suppressed,
            shard=config.CONFIG['EMAIL']['shard'],
            user=userKey.urlsafe(),
            fromEmail=emailFields['fromEmail'],
            toEmail=emailFields['toEmail'],
            toBcc=emailFields['toBcc'],
            subject=emailFields['subject'],
            template=template,
            tags=tags,
        ).put()
        EmailSendLogContent(
            _id=sendLogId,
            **emailFields
        ).put()
        return sendLogId

    def __init__(self, **kwargs):
        if 'date' not in kwargs:
            kwargs['date'] = datetime.datetime.now()
        MongoModel.__init__(self, **kwargs)

    def getAdminLink(self):
        return "/admin/email-log/%s/" % (MongoModel.urlsafe(self._id))

    def getClicks(self):
        clicks = rutil.safeAccess(self, 'msgcl')
        return clicks or []

    def getClicksCount(self):
        clicks = rutil.safeAccess(self, 'msgclc')
        return clicks or 0

    def getOpens(self):
        opens = rutil.safeAccess(self, 'msgop')
        return opens or []

    def getOpensCount(self):
        opens = rutil.safeAccess(self, 'msgopc')
        return opens or 0

    def getUser(self):
        if self.user:
            try:
                key = ndb.Key(urlsafe=self.user)
            except TypeError:
                logging.error(self.user)
                return None
            return key.get()

class EmailSendLogContent(MongoModel):

    collectionName = 'msgct'

    # fromName
    # fromEmail
    # toName
    # toEmail
    # html
    # nonce
    # subject
    # date

    def __init__(self, **kwargs):
        if 'date' not in kwargs:
            kwargs['date'] = datetime.datetime.now()
        MongoModel.__init__(self, **kwargs)

class PartnerEmailSendLog(MongoModel):

    collectionName = 'partner_msgsnd'

    # date
    # nonce
    # suppressed
    # shard
    # partner
    # unsubscribed
    # fromEmail
    # toEmail
    # subject
    # email

    @classmethod
    def make(
            cls,
            nonce,
            suppressed,
            partnerKey,
            emailFields,
            template,
            tags,
        ):
        from web import config
        sendLogId = PartnerEmailSendLog(
            nonce=nonce,
            suppressed=suppressed,
            shard=config.CONFIG['EMAIL']['shard'],
            partner=partnerKey.urlsafe(),
            fromEmail=emailFields['fromEmail'],
            toEmail=emailFields['toEmail'],
            toBcc=emailFields['toBcc'],
            subject=emailFields['subject'],
            template=template,
            tags=tags,
        ).put()
        PartnerEmailSendLogContent(
            _id=sendLogId,
            **emailFields
        ).put()
        return sendLogId

    def __init__(self, **kwargs):
        if 'date' not in kwargs:
            kwargs['date'] = datetime.datetime.now()
        MongoModel.__init__(self, **kwargs)

    def getAdminLink(self):
        return "/admin/partner-email-log/%s/" % (MongoModel.urlsafe(self._id))

    def getClicks(self):
        clicks = rutil.safeAccess(self, 'msgcl')
        return clicks or []

    def getClicksCount(self):
        clicks = rutil.safeAccess(self, 'msgclc')
        return clicks or 0

    def getOpens(self):
        opens = rutil.safeAccess(self, 'msgop')
        return opens or []

    def getOpensCount(self):
        opens = rutil.safeAccess(self, 'msgopc')
        return opens or 0

    def getPartner(self):
        if self.partner:
            try:
                key = ndb.Key(urlsafe=self.partner)
            except TypeError:
                logging.error(self.partner)
                return None
            return key.get()

class PartnerEmailSendLogContent(MongoModel):

    collectionName = 'partner_msgct'

    # fromName
    # fromEmail
    # toName
    # toEmail
    # html
    # nonce
    # subject
    # date

    def __init__(self, **kwargs):
        if 'date' not in kwargs:
            kwargs['date'] = datetime.datetime.now()
        MongoModel.__init__(self, **kwargs)

class ArEmailSendLog(MongoModel):

    collectionName = 'ar_msgsnd'

    # date
    # nonce
    # suppressed
    # shard
    # partner -- the partner is supposed to be getting the email
    # unsubscribed
    # fromEmail
    # toEmail
    # subject
    # email

    @classmethod
    def make(
            cls,
            nonce,
            suppressed,
            partnerKey,
            emailFields,
            template,
            tags,
        ):

        partnerValue = None
        if partnerKey:
            partnerValue = partnerKey.urlsafe()

        from web import config
        sendLogId = ArEmailSendLog(
            nonce=nonce,
            suppressed=suppressed,
            shard=config.CONFIG['EMAIL']['shard'],
            partner=partnerValue,
            fromEmail=emailFields['fromEmail'],
            toEmail=emailFields['toEmail'],
            toBcc=emailFields['toBcc'],
            subject=emailFields['subject'],
            template=template,
            tags=tags,
        ).put()
        ArEmailSendLogContent(
            _id=sendLogId,
            **emailFields
        ).put()
        return sendLogId

    def __init__(self, **kwargs):
        if 'date' not in kwargs:
            kwargs['date'] = datetime.datetime.now()
        MongoModel.__init__(self, **kwargs)

    def getAdminLink(self):
        return "/admin/ar-email-log/%s/" % (MongoModel.urlsafe(self._id))

    def getPartner(self):
        if self.partner:
            try:
                key = ndb.Key(urlsafe=self.partner)
            except TypeError:
                logging.error(self.partner)
                return None
            return key.get()

class ArEmailSendLogContent(MongoModel):

    collectionName = 'ar_msgct'

    # fromName
    # fromEmail
    # toName
    # toEmail
    # html
    # nonce
    # subject
    # date

    def __init__(self, **kwargs):
        if 'date' not in kwargs:
            kwargs['date'] = datetime.datetime.now()
        MongoModel.__init__(self, **kwargs)

class PartnerFreeTrialLog(BackedupNdbModel):
    accepted = ndb.BooleanProperty(default=False)
    acceptedDate = ndb.DateTimeProperty()
    agreementRecipient = ndb.StringProperty()
    partnerKey = ndb.KeyProperty()
    partnerName = ndb.StringProperty()
    partnerId = ndb.StringProperty()

    @classmethod
    def get(cls, partnerKey):
        return cls.query( ancestor=cls.parentKey() ).filter(cls.partnerKey == partnerKey).get()

    @classmethod
    def create(cls, partner):
        return cls(parent=cls.parentKey(), partnerKey=partner.key, partnerName=partner.name, partnerId=partner.pid)

    @classmethod
    def parentKey(cls):
        return ndb.Key('PartnerFreeTrailLogDummyParent', 'ThisIsForDataConsistencyPurposeFreeTrailLog')

class GooglePlace(object):

    @classmethod
    def find(cls, types, location, radius):
        endpoint = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        args = {
            'key': keyserver.get()['google']['server_key'],
            'sensor': 'false',
            'location': "%s,%s" % (
                location['coordinates'][1],
                location['coordinates'][0],
            ),
            'types': "|".join(types),
            'radius': radius,
        }
        payload = urllib.urlencode(args)
        response = urlfetch.fetch("%s?%s" % (endpoint, payload))
        output = []
        for result in json.loads(response.content)['results']:
            output.append(GooglePlace(**result))
        return output

    @classmethod
    def findRadar(cls, types, location, radius):
        # count the results yo...
        endpoint = "https://maps.googleapis.com/maps/api/place/radarsearch/json"
        args = {
            'key': keyserver.get()['google']['server_key'],
            'sensor': "false",
            'location': "%s,%s" % (
                location['coordinates'][1],
                location['coordinates'][0],
            ),
            'types': "|".join(types),
            'radius': radius,
        }
        payload = urllib.urlencode(args)
        response = urlfetch.fetch("%s?%s" % (endpoint, payload))
        result = json.loads(response.content)
        return len(result['results'])

    def __init__(self, **kwargs):
        self.data = kwargs

class GoogleGeocodedResult(ndb.Model):
    addressId = ndb.StringProperty()
    generated = ndb.DateTimeProperty(auto_now_add=True)
    addressComponents = ndb.PickleProperty()
    version = ndb.IntegerProperty()
    result = ndb.PickleProperty()
    isBadResult = ndb.BooleanProperty(default=False)

    @classmethod
    def create(cls, addressId, addressComponents, result):
        isBadResult = result.get('isBadResult')
        obj = cls(
            addressId=addressId,
            addressComponents=addressComponents,
            result=result,
            isBadResult=isBadResult,
            version=1
        )
        obj.put()
        return obj

    @classmethod
    def forAddressId(cls, addressId):
        return cls.query().filter(cls.addressId == addressId).get()

class FloodZoneMongoModel(MongoModel):

    collectionName = 'floodZones'
    geoField = 'geo_simple'

    @classmethod
    def forAddress(cls, address):
        return util.first(cls.queryGeoref(address.location))

    def public(self):
        return {
            'id': self.id,
            'geo': self.geo,
            'zone': self.Zone
        }

class HybridAlertLog(ndb.Model):
    user = ndb.KeyProperty(kind='User')
    email = ndb.StringProperty()
    batchId = ndb.StringProperty()
    alertType = ndb.StringProperty()
    obId = ndb.StringProperty()

    @classmethod
    def exists(cls, user, email, batchId, alertType, obId):

        logKey = cls._createKey(user, email, batchId, alertType, obId)
        if logKey.get() is None:
            return False
        return True

    @classmethod
    @ndb.transactional
    def create(cls, user, email, batchId, alertType, obId):
        logKey = cls._createKey(user, email, batchId, alertType, obId)
        log = logKey.get()
        if log is None:
            cls(
                key=logKey, 
                user=user, 
                email=email, 
                batchId=batchId, 
                alertType=alertType, 
                obId=obId
            ).put()
            return True
        return False

    @classmethod
    def _createKey(cls, user, email, batchId, alertType, obId):
        parent = cls._parentKey(batchId, alertType)
        keyVal = '%s:%s' % (email, obId)
        return ndb.Key(cls, keyVal, parent=parent)

    @classmethod
    def _parentKey(cls, batchId, alertType):
        keyVal = '%s:%s' % (alertType, batchId)
        return ndb.Key('Parent', keyVal)
    
class Image(ndb.Model):

    mimetype = ndb.StringProperty()
    data = ndb.BlobProperty()

class InsurentBuildingModel(MongoModel):

    collectionName = 'insurentBuildings'

    @classmethod
    def forAddress(cls, address):
        return cls.queryFirst({'caddr': address['caddr']})

class Intersection(MongoModel):

    collectionName = 'intersections'

    def getName(self):
        streetNameA = self.streets[0]
        streetNameB = self.streets[1]
        if 'AVE' in streetNameA.upper():
            return "%s and %s" % (streetNameB, streetNameA)
        else:
            return "%s and %s" % (streetNameA, streetNameB)

class JsjArticle(BackedupNdbModel):

    data = ndb.BlobKeyProperty()
    date = ndb.DateTimeProperty(auto_now_add=True)
    description = ndb.TextProperty()
    slug = ndb.StringProperty()
    template = ndb.StringProperty()
    title = ndb.StringProperty()
    status = ndb.StringProperty() # publish or draft or deleted

    @classmethod
    def forSlug(cls, slug):
        return JsjArticle\
            .query(ancestor=ndb.Key('Jsj', 'default'))\
            .filter(JsjArticle.slug == slug)\
            .get()

    @classmethod
    def new(cls):
        return JsjArticle(parent=ndb.Key('Jsj', 'default'))

    def getAdminUrl(self):
        return "/admin/jsj/edit-post/?post=%s" % self.slug

    def getUrl(self):
        return "/data-lab/%s/" % self.slug

class Nyc311CallModel(MongoModel):

    collectionName = 'nyc311Calls'
    geoField = 'location'

    FILTH_TYPES = [
        "Sewer",
        "Graffiti",
        "Air Quality",
        "Urinating in Public",
        "Hazardous Materials",
        "Sanitation Condition",
        "Dirty Conditions",
        "Industrial Waste",
    ]
    NOISE_TYPES = [
        "Noise",
        "Noise - Commercial",
        "Noise - Street/Sidewalk",
        "Noise - Vehicle",
        "Noise Survey",
        "Noise - House of Worship",
        "Noise - Helicopter",
        "Collection Truck Noise",
        "Noise - Park",
    ]
    STREET_TYPES = [
        "Street Light Condition",
        "Street Condition",
        "Scaffold Safety",
        "Dead Tree",
        "Sidewalk Condition",
        "Broken Parking Meter",
        "Broken Muni Meter",
    ]

    @classmethod
    def getNearestFilthComplaints(cls, location, maxRadius, daysBack=365, count=False):
        lastPeriod = datetime.datetime.now() - datetime.timedelta(days=daysBack)
        return cls.getNearest(
            location,
            maxRadius,
            count=count,
            filter={
                'complaint_type': {
                    '$in': cls.FILTH_TYPES
                },
                'created_date': {
                    '$gte': lastPeriod
                }
            }
        )

    @classmethod
    def getNearestNoiseComplaints(cls, location, maxRadius, daysBack=365, count=False):
        lastPeriod = datetime.datetime.now() - datetime.timedelta(days=daysBack)
        return cls.getNearest(
            location,
            maxRadius,
            count=count,
            filter={
                'complaint_type': {
                    '$in': cls.NOISE_TYPES
                },
                'created_date': {
                    '$gte': lastPeriod
                }
            }
        )

    @classmethod
    def getNearestStreetComplaints(cls, location, maxRadius, daysBack=365, count=False):
        lastPeriod = datetime.datetime.now() - datetime.timedelta(days=daysBack)
        return cls.getNearest(
            location,
            maxRadius,
            count=count,
            filter={
                'complaint_type': {
                    '$in': cls.STREET_TYPES
                },
                'created_date': {
                    '$gte': lastPeriod
                }
            }
        )

    @classmethod
    def getNearestRodentComplaints(cls, location, maxRadius, daysBack=365, count=False):
        lastPeriod = datetime.datetime.now() - datetime.timedelta(days=daysBack)
        return cls.getNearest(
            location,
            maxRadius,
            count=count,
            filter={
                'complaint_type': 'Rodent',
                'created_date': {
                    '$gte': lastPeriod,
                },
            }
        )

    def getShortComplaintDescription(self, topic):
        if topic == 'Street':
            description = "%s: %s" % (self.complaint_type, self.descriptor)
        else:
            description = self.descriptor

        return description

    def public(self):
        return {
            'location': self.location,
            'type': self.complaint_type,
            'descriptor': self.descriptor,
            'key': self.unique_key,
        }

class NycBiswebBuilding(MongoModel):

    collectionName = 'nycBiswebBuildings'

    CLASS_MAP = {
        'A': ("Single-Family", "Single-Family Dwelling"),
        'B': ("Two-Family", "Two-Family Dwelling"),
        'C0': ("Walk-Up", "Walk-Up Building"),
        'C1': ("Walk-Up", "Walk-Up Building"),
        'C2': ("Walk-Up", "Walk-Up Building"),
        'C3': ("Walk-Up", "Walk-Up Building"),
        'C4': ("Walk-Up", "Walk-Up Building"),
        'C5': ("Walk-Up", "Walk-Up Building"),
        'C6': ("Walk-Up", "Walk-Up Co-op Building"),
        'C7': ("Walk-Up", "Walk-Up Building"),
        'C8': ("Walk-Up", "Walk-Up Co-op Building"),
        'C9': ("Walk-Up", "Walk-Up Building"),
        'D0': ("Elevator", "Elevator Co-op Building"),
        'D1': ("Elevator", "Elevator Building"),
        'D2': ("Elevator", "Elevator Building"),
        'D3': ("Elevator", "Elevator Building"),
        'D4': ("Elevator", "Elevator Co-op Building"),
        'D5': ("Elevator", "Elevator Building"),
        'D6': ("Elevator", "Mixed-Use Elevator Building"),
        'D7': ("Elevator", "Mixed-Use Elevator building"),
        'D8': ("Elevator", "Elevator Building"),
        'D9': ("Elevator", "Elevator Building"),
        'E': ("Warehouse", "Warehouse Building"),
        'F': ("Industrial", "Industrial Building"),
        'G': ("Garage", "Garage Facility"),
        'H1': ("Hotel", "Hotel Building"),
        'H2': ("Hotel", "Hotel Building"),
        'H3': ("Hotel", "Hotel Building"),
        'H4': ("Hotel", "Hotel Building"),
        'H5': ("Club", "Club Building"),
        'H6': ("Hotel", "Hotel/Apartment Building"),
        'H7': ("Hotel", "Hotel Co-op Building"),
        'H8': ("Dormitory", "Dormitory Building"),
        'H9': ("Hotel", "Hotel Building"),
        'I': ("Healthcare", "Healthcare Facility"),
        'J': ("Theatre", "Theatre Building"),
        'K1': ("Commercial", "Commercial Building"),
        'K2': ("Commercial", "Commercial Building"),
        'K3': ("Commercial", "Commercial Building"),
        'K4': ("Mixed-Use", "Mixed-Use Building"),
        'K5': ("Commercial", "Commercial Building"),
        'K6': ("Commercial", "Commercial Building"),
        'K7': ("Commercial", "Commercial Building"),
        'K9': ("Commercial", "Commercial Building"),
        'L': ("Loft", "Loft Building"),
        'M': ("Worship", "Worship Space"),
        'N': ("Asylum", "Asylum"),
        'O1': ("Office", "Office Building"),
        'O2': ("Office", "Office Building"),
        'O3': ("Office", "Office Building"),
        'O4': ("Office", "Office Building"),
        'O5': ("Office", "Office Building"),
        'O6': ("Office", "Office Building"),
        'O7': ("Office", "Office Building"),
        'O8': ("Mixed-Use", "Mixed-Use Building"),
        'O9': ("Office", "Office Building"),
        'P': ("Cultural", "Cultural Space"),
        'Q': ("Recreational", "Recreational Space"),
        'R0': ("Residential", "Residential Building"),
        'R1': ("Condo", "Condo Unit"),
        'R2': ("Condo", "Condo Unit"),
        'R3': ("Condo", "Condo Unit"),
        'R4': ("Condo", "Condo Unit"),
        'R5': ("Commercial", "Commercial Unit"),
        'R6': ("Condo", "Condo Unit"),
        'R7': ("Commercial", "Commercial Unit"),
        'R8': ("Commercial", "Commercial Unit"),
        'R9': ("Co-op", "Co-op Condo Unit"),
        'RA': ("Commercial", "Commercial Unit"),
        'RB': ("Office", "Office Space"),
        'RG': ("Parking", "Parking Space"),
        'RH': ("Hotel", "Hotel Unit"),
        'RK': ("Retail", "Retail Space"),
        'RP': ("Parking", "Parking Space"),
        'RR': ("Rental", "Rental Unit"),
        'RS': ("Storage", "Storage Unit"),
        'RT': ("Terrace", "Terrace Space"),
        'RW': ("Industrial", "Industrial Space"),
        'S': ("Mixed-Use", "Mixed-Use Building"),
        'T': ("Transportation", "Transportation Facility"),
        'U': ("Utility", "Utility Facility"),
        'V': ("Lot", "Zoned Lot"),
        'W': ("Educational", "Educational Facility"),
        'Y': ("Government", "Government Facility"),
        'Z0': ("Recreational", "Recreational Building"),
        'Z1': ("Court", "Court House"),
        'Z2': ("Parking", "Parking Facility"),
        'Z3': ("Post Office", "Post Office Building"),
        'Z4': ("Consulate", "Consulate Building"),
        'Z5': ("UN", "UN Building"),
        'Z6': ("Government", "Government Facility"),
        'Z7': ("Easement", "Easement"),
        'Z8': ("Cemetery", "Cemetery"),
    }

    def getBuildingType(self):
        buildingClass = self.get('DepartmentofFinanceBuildingClassification')
        if buildingClass:
            majorClass = buildingClass[0]
            minorClass = buildingClass[0:2]
            return self.CLASS_MAP.get(minorClass) \
                or self.CLASS_MAP.get(majorClass) \
                or ("Other", "Other Space")

class NycDobBin(MongoModel):

    collectionName = 'nycDobBins'

    @classmethod
    def forCaddr(cls, caddr):
        record = cls.queryFirst({'caddr': caddr})
        if record:
            return record.dobBin
    @classmethod
    def getByBin(cls, dobBin):
        return cls.queryFirst({'dobBin' : dobBin})

class NycDobJob(MongoModel):

    collectionName = 'nycDobJobs'
    geoField = 'location'

    SUBTYPE_MAP = {
        'CH': "Chute Work",
        'FN': "Fence Work",
        'SH': "Sidewalk Shed Installation",
        'SF': "Scaffold Installation",
        'BL': "Boiler Work",
        'FA': "Fire Alarm Work",
        'FB': "Fuel-Burner Work",
        'FP': "Fire Suppression Work",
        'FS': "Fuel-Storage Work",
        'MH': "Mechanical/HVAC Work",
        'SD': "Stand-Pipe Work",
        'SP': "Sprinkler System Work",
    }

    TYPE_MAP = {
        'A1': "Major Alteration",
        'A2': "Alteration",
        'A3': "Minor Alteration",
        'NB': "New Building",
        'DM': "Demolition",
    }

    def hasBool(self, field):
        rawValue = self.get(field) or ''
        value = rawValue.strip()
        return bool(value)

    def getDate(self):
        nextYear = datetime.datetime.now() + datetime.timedelta(days=365)

        if 'JobStartDate' not in self or self.get('JobStartDate') > nextYear:
            if 'FullyPaid' in self:
                return self.get('FullyPaid')
            else:
                return self.get('FilingDate')
        else:
            return self.get('JobStartDate')

    def getType(self):
        subtype = self.SUBTYPE_MAP.get(self.get('PermitSubtype'))
        if subtype: return subtype

        if self.hasBool('HorizontalEnlrgmt'):
            return "Horizontal Enlargement"
        if self.hasBool('VerticalEnlrgmt'):
            return "Vertical Enlargement"
        if self.hasBool('FireAlarm'):
            return "Fire Alarm Work"
        if self.hasBool('FireSuppression'):
            return "Fire Suppression Work"
        if self.hasBool('FuelBurning'):
            return "Fuel-Burner Work"
        if self.hasBool('FuelStorage'):
            return "Fuel-Storage Work"
        if self.hasBool('Plumbing'):
            return "Plumbing Work"
        if self.hasBool('Sprinkler'):
            return "Sprinkler System Work"
        if self.hasBool('Standpipe'):
            return "Stand-Pipe Work"
        if self.hasBool('Boiler'):
            return "Boiler Work"
        if self.hasBool('CurbCut'):
            return "Curb Cut Installation"
        if self.hasBool('Mechanical'):
            return "Mechanical/HVAC Work"

        type = self.TYPE_MAP.get(self.get('JobType'))
        if type: return type

        return "Other Work"

    def public(self):
        return {
            'location': self.location,
            'type': self.JobType,
            'key': self.Job,
            'subtype': self.get('PermitSubtype'),
        }

class NycHpdBuildingInfo(MongoModel):

    collectionName = 'nycHpdBuildings'

class NycHpdComplaintModel(MongoModel):

    collectionName = 'nycHpdComplaints'

    @classmethod
    def forHpdId(cls, hpdId):
        return cls.query(
            {'BuildingID': hpdId},
            limit=1000
        )

    def __init__(self, **kwargs):
        MongoModel.__init__(self, **kwargs)
        self.Problems = [NycHpdProblemModel(**result) for result in self.Problems]

    def getProblemCount(self):
        return len(self.Problems)

    def getOpenProblemCount(self):
        count = 0
        for problem in self.Problems:
            if problem.getStatus() == "Open":
                count += 1
        return count

class NycHpdId(MongoModel):

    collectionName = 'nycHpdIds'

    @classmethod
    def forCaddr(cls, caddr):
        record = cls.queryFirst({'caddr': caddr})
        if record:
            return record.hpdId

class NycHpdProblemModel(object):

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def getPriority(self):
        descriptions = {
            'EMERG': "Emergency",
            'HAZAR': "Hazardous",
            'N EMERG': "Non-Emergency",
            'DIRE': "Immediate Emergency",
            'REFERRAL': "Referral",
        }
        return descriptions[self.Type]

    def getProblem(self):
        # TODO: fetch the longer string based on the current code
        return "%s: %s" % (self.MinorCategory, self.Code)

    def getSpace(self):
        return self.SpaceType

    def getStatus(self):
        if self.Status == 'OPEN':
            return "Open"
        else:
            return "Resolved"

class NycHpdRegistration(MongoModel):

    collectionName = 'nycHpdRegistrations'

class NycHpdViolationModel(MongoModel):

    collectionName = 'nycHpdViolations'

    @classmethod
    def forHpdId(cls, hpdId):
        return cls.query(
            {'BuildingID': hpdId},
            limit=1000
        )

    def getClass(self):
        descriptions = {
            'A': 'Non Hazardous',
            'B': 'Hazardous',
            'C': 'Immediately Hazardous',
        }
        return descriptions.get(self.Class, 'Other')

    def getFullStatus(self):
        # TODO: Prettify this shit
        return self.CurrentStatus

    def getStatus(self):
        if self.CurrentStatus == "OPEN":
            return "Open"
        else:
            return "Closed"

    def getProblem(self):
        from rentenna3.data.violations import VIOLATION_MAPPINGS
        # TODO: Return mapping based off self.OrderNumber
        return VIOLATION_MAPPINGS.get(self.OrderNumber, "Other")

class NycPolicePrecinctMongoModel(MongoModel):

    collectionName = 'policePrecincts'
    geoField = 'geo_simple'

    @classmethod
    def forAddress(cls, address):
        return util.first(cls.queryGeoref(address.location))

class NycSubwayEntranceMongoModel(MongoModel):

    collectionName = 'subwayEntrances'

    @classmethod
    def getNearest(cls, location, maxRadius, limit=None, **kwargs):
        results = []
        subways = NycSubwayEntranceMongoModel.query(
            {
                'geo': {
                    '$nearSphere': {
                        '$geometry': location,
                        '$maxDistance': maxRadius,
                    }
                },
            },
            limit=limit,
        )

        observedLines = set()
        for subway in subways:
            newLineAccess = False
            for line in subway.getLines():
                if line not in observedLines:
                    newLineAccess = True
                observedLines.add(line)

            if newLineAccess:
                subway.distance = rutil.distance(subway.geo, location)
                results.append(subway)

        return results

    def getNiceName(self):
        return self.NAME.split(' At ')[0]

    def getLines(self):
        if self.LINE == '@': # wtf does this mean?
            return []
        else:
            return self.LINE.split("-")

class NycTaxiIntersection(MongoModel):

    collectionName = 'nycTaxiIntersections'

class NypdCrimeMongoModel(MongoModel):

    collectionName = 'nypdCrimes'

    def __init__(self, **kwargs):
        MongoModel.__init__(self, **kwargs)

    def public(self):
        return {
            'gxId': self.gxId,
            'count': self.count,
            'geo': self.geo,
            'crime': self.crime,
        }

class NyVoter(MongoModel):

    collectionName = 'nyVoters'

    PARTY_MAP = {
        'BLK': "Blank",
        'CON': "Conservative",
        'DEM': "Democrat",
        'GRE': "Green Party",
        'IND': "Independent",
        'REP': "Republican",
        'WOR': "Working Families",
        'APP': "Antiprohibition",
        'FDM': "Freedom Party",
        'LBT': "Libertarian",
        'RTH': "Rent is Too Damn High",
        'SWP': "Socialist",
        'TXP': "Taxpayer Party",
    }

    @classmethod
    def forAddress(cls, address):
        return cls.query(
            {'caddr': address.caddr},
            fields=['ENR', 'OTH', 'S'],
        )

    def getParty(self):
        party = self.ENR or self.OTH
        return self.PARTY_MAP.get(party, 'Other')

class ObiAvmResponse(object):

    PROPERTY_TYPE_MAP = {
        '1': ("Single-Family", "Single Family Home"),
        '2': ("Condo", "Condo Building"),
        '3': ("Multi-Family", "Multi-Family Home"),
        '5': ("Co-op", "Residential Co-op Unit"),
        '6': ("Commercial", "Commercial Building"),
        '7': ("Hotel", "Hotel or Motel"),
        '8': ("Condo", "Commercial Condominium"),
        '9': ("Retail", "Retail Building"),
        '11': ("Office", "Office Building"),
        '12': ("Warehouse", "Warehouse"),
        '13': ("Financial", "Financial Institution"),
        '14': ("Hospital", "Hospital"),
        '15': ("Parking", "Parking Structure"),
        '16': ("Recreational", "Recreational Facility"),
        '17': ("Industrial", "Industrial"),
        '18': ("Industrial", "Light Industrial"),
        '19': ("Industrial", "Heavy Industrial"),
        '21': ("Utility", "Utility Building"),
        '22': ("Agricultural", "Agricultural Building"),
        '23': ("Vacant", "Vacant Building"),
    }

    def __init__(self,
            highValue,
            lowValue,
            indicatedValue,
            confidence,
            bedrooms,
            bathrooms,
            area,
            yearBuilt,
            sqft,
            lotSize,
            numberFloors,
            propertyId,
            propertyType,
            apn,
            unitValue=None,
        ):
        self.highValue = highValue
        self.lowValue = lowValue
        self.indicatedValue = indicatedValue
        self.confidence = confidence
        self.bedrooms = bedrooms
        self.bathrooms = bathrooms
        self.area = area
        self.yearBuilt = yearBuilt
        self.sqft = sqft
        self.lotSize = lotSize
        self.numberFloors = numberFloors
        self.propertyId = propertyId
        self.propertyType = propertyType
        self.apn = apn
        self.unitValue = unitValue

    def getBuildingType(self):
        if self.propertyType:
            return self.PROPERTY_TYPE_MAP.get(self.propertyType) \
                or ("Other", "Other Space")

class ObiCommunityResponse(object):

    def __init__(self, data):
        self.data = data

    def get(self, key):
        return self.data.get(key)

class ObiSale(object):

    def __init__(self, data):
        self.data = data

    def get(self, key):
        return self.data.get(key)

    def getPropertyLink(self, domain=False):
        url = "/find-address/?%s" % urllib.urlencode({
            'textQuery': "%s, %s, %s, %s" % (
                self.get('street'),
                self.get('city'),
                self.get('state'),
                self.get('zip'),
            )
        })
        if domain:
            return config.CONFIG['URL']['BASE'] + url
        else:
            return url

    def getJson(self):
        data = dict(self.data)
        data['closeDate'] = data['closeDate'].strftime('%m/%d/%Y')
        data['addedDate'] = data['addedDate'].strftime('%m/%d/%Y')
        data['link'] = self.getPropertyLink(True)
        return data

class OtuToken(MongoModel):

    collectionName = 'otu'

    @classmethod
    def getData(self):
        token = validate.get('otu')
        if token:
            otu = OtuToken.queryFirst({
                '_id': MongoModel.fromUrlsafe(token),
            })
            if otu:
                if otu['used']:
                    data = None
                    logging.info("Used OTU")
                elif otu['expires'] < datetime.datetime.now():
                    data = None
                    logging.info("Expired OTU")
                else:
                    logging.info("OK OTU")
                    data = otu['data']
                    otu.used = True
                    otu.put()
                    return data

    def __init__(self, **kwargs):
        if 'created' not in kwargs:
            kwargs['created'] = datetime.datetime.now()
        MongoModel.__init__(self, **kwargs)

class Partner(ndb.Model):

    parentKey = ndb.KeyProperty()
    ancestorKeys = ndb.KeyProperty(repeated=True) # order is top to bottom
    apiKey = ndb.StringProperty()
    apiSecret = ndb.StringProperty()
    domains = ndb.StringProperty('subdomain', repeated=True)
    name = ndb.StringProperty()
    pid = ndb.StringProperty() # pid is only unique among all sibilings
    status = ndb.StringProperty(default="active")

    created = ndb.DateTimeProperty(auto_now_add=True)
    updated = ndb.DateTimeProperty(auto_now=True)

    forceRules = ndb.PickleProperty()
    settings = ndb.PickleProperty()

    @classmethod
    def _get_kind(cls):
        return 'SubdomainProperty_V2'

    @classmethod
    def get(cls, host):
        partner = Partner\
            .query()\
            .filter(Partner.domains == host)\
            .filter(Partner.parentKey == None)\
            .filter(Partner.status == 'active')\
            .get()

        #TODO: find out a better way to deal with same domain
        if partner is None:
            partner = Partner\
                .query()\
                .filter(Partner.domains == host)\
                .filter(Partner.status == 'active')\
                .get()

        return partner

    @classmethod
    def forApiKey(cls, apiKey, activeOnly=True):
        qry = Partner\
            .query()\
            .filter(Partner.apiKey == apiKey)
        if activeOnly:
            qry = qry.filter(Partner.status == 'active')
         
        partner = qry.get()
        if partner is not None and partner.ancestorKeys:
            for ancestor in ndb.get_multi(partner.ancestorKeys):
                if activeOnly and ancestor.status == 'inactive':
                    return None
        return partner

    @classmethod
    def getPartnerCount(cls, partnerKey, status):
        qry = Partner\
            .query()\
            .filter(Partner.ancestorKeys == partnerKey)

        if status != 'all' and status:
            qry = qry.filter(Partner.status == status)
         
        count = qry.count()  
        return count    

    @classmethod
    def _createKeyId(cls, parentPartner, pid):
        keyId = pid
        if parentPartner is not None:
            keyId ='%s.%s' % (parentPartner.key.urlsafe(), pid)
        return keyId

    @classmethod
    def create(cls, parentPartner, pid):
        partner = None
        if pid:
            keyId = Partner._createKeyId(parentPartner, pid)
            partner = Partner(id=keyId)
            partner.pid = pid
        else:
            partner = Partner()
        partner._initNew(parentPartner)
        return partner

    @classmethod
    def getDefaultForceRules(cls):
        """
        use string values for future expansion:
            'Yes'
            'No'
            'Local'
            None
        """
        return {
            "createSubPartner" : "Local",
            "notificationEmail" : "Local",
            "leadDistributionEmail" : "Local",
            "leadEmail" : "Local",
            "notificationRecipient" : "Yes",
        }

    @classmethod
    def getDefaultSettings(cls):
        return {
            'alerts': False,
            'enableBreadcrumbs': False,
            'enableReplyTo': False,
            'createSubPartner': False,
            'nav': False,
            'renderFullReports': True,
            'leadDistribution' : True,
            'users': False,
            'branding.position' : 'right',
            'branding.cobranding' : True,
            'notificationRecipient' : 'allPartners', # allPartners, topPartner, subPartners
            'skipAlertConfirmation' : False,
            'suppression.city.Social Buzz.socialPhotos' : True,
            'suppression.property.Social Buzz.socialPhotos' : True,
            'suppression.neighborhood.Social Buzz.socialPhotos' : True,
            #'headerDisplay' : True,
        }

    @classmethod
    def adminOnlyFields(cls):
        return [
            'trackingHeaderSection',
            'trackingFooterSection',
        ]

    @classmethod
    def prefixRuleValue(cls, name, prefixRules):
        kvs = list( (k,v) for (k,v) in prefixRules.items() if name.startswith(k) )
        if kvs:
            sortedKvs = sorted(kvs, key=lambda pair: len(pair[0]), reverse=True)
            return sortedKvs[0][1]

    @classmethod
    @ndb.tasklet
    def topBottomName_async(cls, partner):
        if not partner:
            raise ndb.Return('')
        name = partner.name or partner.pid
        topName = None

        if partner.ancestorKeys:
            topPartner = yield partner.ancestorKeys[0].get_async()
            topName = topPartner.name or topPartner.pid

        if topName:
            raise  ndb.Return( "%s: %s" % (topName, name) )
        raise ndb.Return(name)

    @classmethod
    def topBottomName(cls, partner):
        if not partner:
            return ''
        name = partner.name or partner.pid
        topName = None

        if partner.ancestorKeys:
            topPartner = partner.ancestorKeys[0].get()
            topName = topPartner.name or topPartner.pid

        if topName:
            return "%s: %s" % (topName, name)
        return name

    def hasAccess(self, targetPartner):
        if not targetPartner: 
            return False
        if self.apiKey == targetPartner.apiKey:
            return True
        if self.key in targetPartner.ancestorKeys:
            return True
        return False        

    def allowCreateSubpartner(self):
        return self.getSetting("createSubPartner") == True

    def allowAlerts(self):
        return self.getSetting('alerts') == True

    def ancestors(self):
        if self.ancestorKeys:
            if not hasattr(self, "_ancestors"):
                self._ancestors = ndb.get_multi(self.ancestorKeys)
            return self._ancestors
        return None

    def setAncestors(self, ancestors):
        self._ancestors = ancestors

    def decorateUrl(self, url, hashTag=None):
        parsed = urlparse.urlparse(url)
        url = "%s?%s" % (parsed.path, parsed.query)
        hashTag = hashTag or parsed.fragment
        return "%s/goto-url/?%s" % (
            self.getPreferredDomain(),
            urllib.urlencode({
                'api_key': self.apiKey,
                'url': url,
                'hash_tag': hashTag or '',
            }),
        )

    def _initNew(self, parentPartner=None):
        if not self.apiKey:
            self.apiKey = str(uuid.uuid4())
        if not self.apiSecret:
            self.apiSecret = str(uuid.uuid4())

        if parentPartner is not None:
            self.parentKey = parentPartner.key
            self.ancestorKeys = parentPartner.ancestorKeys + [parentPartner.key]

        self.settings = {}

    def getAdminUrl(self):
        return "/admin/partners/%s/" % self.key.urlsafe()

    def getAllowedStates(self):
        settings = self.getSettings()
        states = list(stateAbbr[6:] for (stateAbbr, val) in settings.items() if val is True and stateAbbr.startswith('state.') )
        return states

    def getLeadRestrictions(self):
        settings = self.getSettings()
        restrictions = list(rkey[17:] for (rkey, val) in settings.items() if val is True and rkey.startswith('lead.restriction.') )
        return restrictions

    def getEmailSuppressions(self):
        settings = self.getSettings()
        suppressions = list(rkey[18:] for (rkey, val) in settings.items() if val is True and rkey.startswith('email.suppression.') )
        return suppressions

    def isEmailSuppressed(self, className):
        if className in self.getEmailSuppressions():
            return True
        return False

    def getPreferredDomain(self):
        domain = self.getSetting('preferredDomain')
        if domain and not domain.lower().startswith('http'):
            parseUrl = urlparse.urlparse(config.CONFIG["URL"]["BASE"])
            scheme = parseUrl.scheme or 'http'
            domain = "%s://%s" % (parseUrl.scheme, domain)
        return domain

    def hasSubpartner(self, activeOnly=True):

        qry = Partner\
            .query()\
            .filter(Partner.parentKey == self.key)
        if activeOnly:
            qry = qry.filter(Partner.status == 'active')
        sub = qry.get(keys_only=True)
        return sub is not None

    def getSubpartnerById(self, subpartnerId, keysOnly=False, activeOnly=True):
        qry = Partner\
            .query()\
            .filter(Partner.parentKey == self.key)\
            .filter(Partner.pid == subpartnerId)
        if activeOnly:
            qry = qry.filter(Partner.status == 'active')
        return qry.get(keys_only=keysOnly)

    def getSetting(self, name):
        return self.getSettings().get(name)

    def getSettings(self):
        if not hasattr(self, "_combinedSettings"):
            combinedSettings = {}
            settingKeys = set()
            tupleList = [ (Partner.getDefaultSettings(), {}, {}) ]

            if self.ancestorKeys:        
                ancestors = self.ancestors()
                for ancestor in ancestors:
                    localSettings = ancestor.getLocalSettings()
                    forceRules = ancestor.getLocalForceRules()
                    prefixForceRules = ancestor.getLocalPrefixForceRules()

                    tupleList.append( (localSettings, forceRules, prefixForceRules) )
                    settingKeys.update(localSettings.keys())

            tupleList.append( (self.getLocalSettings(), {}, {}) )
            settingKeys.update(self.getLocalSettings().keys())

            for name in settingKeys:
                combinedSettings[name] = self.combineSettingValue(name, tupleList)

            self._combinedSettings = combinedSettings

        return self._combinedSettings

    def combineSettingValue(self, name, tupleList):
        result = None;
        for settings, rules, prefixRules in tupleList:
            val = settings.get(name)
            if val is not None:
                result = val

            if rules.get(name) == 'Yes' or Partner.prefixRuleValue(name, prefixRules) == 'Yes':
                return val
            if rules.get(name) == 'Local' or Partner.prefixRuleValue(name, prefixRules) == 'Local':
                localSettings = self.getLocalSettings()
                if name in localSettings:
                    return localSettings.get(name)
                else:
                    return self.getDefaultSettings().get(name)
        return result

    def getLocalSettings(self):
        if self.parentKey is None:
            return util.setMissingAttrs(Partner.getDefaultSettings(), self.settings) or Partner.getDefaultSettings()
            #return self.settings or Partner.getDefaultSettings()
        return self.settings or {}

    def getLocalForceRules(self):
        if self.parentKey is None:
            return util.setMissingAttrs(Partner.getDefaultForceRules(), self.forceRules) or Partner.getDefaultForceRules()
            #return self.forceRules or Partner.getDefaultForceRules()
        return self.forceRules or {}

    def getLocalPrefixForceRules(self):
        return {k[:-1]:v for (k,v) in self.getLocalForceRules().items() if k.endswith('.*')}

    def getTags(self):
        tags = []
        tags.append('partner_direct:%s' % self.key.urlsafe())
        tags.append('partner:%s' % self.key.urlsafe())
        for ancestorKey in self.ancestorKeys:
            tags.append('partner:%s' % ancestorKey.urlsafe())
        return tags

    def needNotification(self):
        
        email = self.getSetting("notificationEmail")
        if not email:
            return False

        recipient = self.getSetting("notificationRecipient")
        if recipient == 'allPartners':
            return True

        hasAncestor = self.ancestorKeys and len(self.ancestorKeys) > 0
        if recipient == 'topPartner':
            return not hasAncestor

        if recipient == 'subPartners':
            return hasAncestor

        return False

    def needSendLead(self):
        email = self.getSetting("leadEmail")
        if email:
            return True
        return False

class PartnerDailyAggs(MongoModel):
    collectionName = 'partnerDailyAggs'
    # day
    # dayDate
    # tag
    # total
    # delivery
    # open
    # click
    # unsub
    # user
    # subscriber
    # date
    # shard

    @classmethod
    def createEmpty(cls, tag, dayDate):
        day = dayDate.strftime('%Y-%m-%d')
        return PartnerDailyAggs(
                day=day,
                dayDate=dayDate,
                tag=tag,
                total=0,
                delivery=0,
                open=0,
                click=0,
                unsub=0,
                user=0,
                subscriber=0,
            )

    def __init__(self, **kwargs):
        if 'date' not in kwargs:
            kwargs['date'] = datetime.datetime.now()
        MongoModel.__init__(self, **kwargs)

    def getClickCount(self):
        return rutil.safeAccess(self, 'click') or 0

    def getDeliveryCount(self):
        return rutil.safeAccess(self, 'delivery') or 0
    
    def getTotalCount(self):
        return rutil.safeAccess(self, 'total') or 0

    def getOpenCount(self):
        return rutil.safeAccess(self, 'open') or 0

    def getUnsubscribeCount(self):
        return rutil.safeAccess(self, 'unsub') or 0

    def getReportViewCount(self):
        return rutil.safeAccess(self, "reportview") or 0

    def getUnopenCount(self):
        return self.getDeliveryCount() - self.getOpenCount()

    def getUserCount(self):
        return rutil.safeAccess(self, "user") or 0

    def getSubscriberCount(self):
        return rutil.safeAccess(self, "subscriber") or 0

    @classmethod
    def getAggs(cls, partnerTag, shard, start, end):
        aggs = cls.queryEx(
            query={
                'tag' : partnerTag,
                'dayDate' : {
                    '$gte' : start,
                    '$lte' : end,
                },
                'shard' : shard,
            },
            fields={
                '_id' : 0,
                'tag' : 0,
                'date': 0,
            },
            sort=[
                ('dayDate', -1),
            ]
        )

        return aggs

    # def getDeliveryRate(self):
    #     return util.rateStr(
    #         self.getDeliveryCount(), 
    #         self.getTotalCount(),
    #     )

    # def getOpenRate(self):
    #     return util.rateStr(
    #         self.getOpenCount(),
    #         self.getDeliveryCount(), 
    #     )

    # def getUnopenRate(self):
    #     return util.rateStr(
    #         self.getUnopenCount(),
    #         self.getDeliveryCount(), 
    #     )

    # def getClickRate(self):
    #     return util.rateStr(
    #         self.getClickCount(),
    #         self.getDeliveryCount(), 
    #     ) 
    # def getReportViewRate(self):
    #     return util.rateStr(
    #         self.getReportViewCount(),
    #         self.getClickCount(),
    #     )

class PartnerDailyEmailTemplateAggs(PartnerDailyAggs):
    collectionName = 'partnerDailyEmailTemplateAggs'
    # template

    @classmethod
    def createEmpty(cls, tag, dayDate, template):
        day = dayDate.strftime('%Y-%m-%d')
        return PartnerDailyAggs(
                day=day,
                dayDate=dayDate,
                tag=tag,
                template=template,
                total=0,
                delivery=0,
                open=0,
                click=0,
                unsub=0,
                user=0,
                subscriber=0,
            )

    @classmethod
    def getAggs(cls, partnerTag, templates, shard, start, end):
        templates = rutil.listify(templates)
        limit = 366 * len(templates)
        aggs = cls.queryEx(
            query={
                'tag' : partnerTag,
                'template' : {"$in" : templates},
                'dayDate' : {
                    '$gte' : start,
                    '$lte' : end,
                },
                'shard' : shard,
            },
            fields={
                '_id' : 0,
                'tag' : 0,
                'date': 0,
            },
            sort=[
                ('dayDate', -1),
            ],
            limit=limit,
        )
        return aggs

class PasswordResetToken(ndb.Model):

    uid = ndb.StringProperty()
    user = ndb.KeyProperty(kind='User')
    expires = ndb.DateTimeProperty()

class Property(ndb.Model):

    city = ndb.StringProperty()
    lists = ndb.StringProperty(repeated=True)
    rank = ndb.FloatProperty()
    shortName = ndb.StringProperty()

    @classmethod
    def get(cls, key, address=None):
        existing = key.get()
        if existing:
            return existing
        else:
            if address is None:
                address = Address.getBySlug(key.id())
            property = Property(
                key=key,
                city=address.city,
                rank=random.random(),
                shortName=address.getShortName(),
            )
            property.put()
            return property

    def getAddress(self):
        return Address.getBySlug(self.key.id())

    def getTags(self):
        return [
            'property:%s' % self.key.id(),
            'city:%s' % self.city,
        ]

    def getUrl(self, domain=False):
        if self.city is None:
            city = 'other'
        else:
            city = self.city
        url = "/report/property/%s/%s/" % (city, self.key.id())
        if domain:
            url = config.CONFIG['URL']['BASE'] + url
        return url

class QuizAnswers(BackedupNdbModel):

    answers = ndb.PickleProperty()
    entryDate = ndb.DateTimeProperty(auto_now_add=True)
    user = ndb.KeyProperty(kind='User')
    slug = ndb.StringProperty()
    tracker = ndb.KeyProperty(kind='Tracker')
    referringUrl = ndb.TextProperty()
    isNewUser = ndb.BooleanProperty(default=False)
    finished = ndb.BooleanProperty(default=False)
    source = ndb.StringProperty() # external parameter passed in from url
    reference = ndb.StringProperty() # external parameter passed in from url
    geocodedAddress = ndb.PickleProperty()  

class ReportStat(ndb.Model):

    # TODO: NDB is probably not the best datastore for these!

    generated = ndb.DateTimeProperty(auto_now_add=True)
    name = ndb.StringProperty()
    version = ndb.IntegerProperty()
    stats = ndb.PickleProperty()

    @classmethod
    def _get_kind(cls):
        # schema change, easier to just drop them all
        return 'ReporterStat_1'

    @classmethod
    def create(cls, type, parent, reporterName, reporterVersion, stats):
        report = ReportStat(
            parent=parent,
            id=reporterName,
            name=reporterName,
            version=reporterVersion,
            stats=stats,
        )
        report.put()
        return report

    @classmethod
    def getExisting(cls, type, parent, reporterNames=None):
        if reporterNames:
            if reporterNames:
                keys = [
                    ndb.Key(
                        cls._get_kind(),
                        name,
                        parent=parent,
                    )
                    for name
                    in reporterNames
                ]
                stats = ndb.get_multi(keys)
            else:
                stats = []
        else:
            query = ReportStat.query(ancestor=parent)
            stats = query.fetch()
        result = {}
        # later generated stats overwrite older ones
        for stat in sorted(stats, key=lambda x: x.generated):
            result[(stat.name, stat.version)] = stat
        return result

class ReportViewed(MongoModel):
    #city
    #slug
    #tags
    #viewed
    #user
    #shard
    collectionName = 'reportViews'

class RecentPoi(MongoModel):

    collectionName = None #'recentPoiTemp'

    @classmethod
    def forGeoId(cls, collectionName, geoId):
        query = {
            'geoIds': geoId,
        }

        results = cls.queryEx(query, limit=3, collectionName=collectionName)
        return results

    def fullAddress(self):
        return '%s, %s, %s %s' % (self.STREET, self.CITY, CENSUS_STATE_STUSABS.get(self.STATE, ''), self.ZIP)

class School(MongoModel):

    collectionName = 'schools2'

    @classmethod
    def forAddress(cls, address, districtIds, level, skipGeo=False):
        query = {
            'OB_DISTRICT_NUMBER': {'$in' : districtIds},
        }

        if level == 'e':
            query['ELEMENTARY'] = "Y"
        elif level == 'm':
            query['MIDDLE'] = "Y"
        else:
            query['HIGH'] = "Y"

        kwargs = {}
        if skipGeo:
            # pass
            kwargs['fields'] = {
                'geo' : 0,
                'geo_simple' : 0,
                'geometry' : 0,
            }

        if districtIds:
            results = cls.getNearest(
                address.location,
                20000,
                filter=query,
                geoField='location',
                limit=4,
                **kwargs
            )
            if results:
                return results

        del query['OB_DISTRICT_NUMBER']
        results = cls.getNearest(
            address.location,
            20000,
            filter=query,
            geoField='location',
            limit=4,
            **kwargs
        )
        return results

    def getEnrollment(self):
        return [
            ('K', int(self.get('ENROLLMENT_BY_GRADE_K') or 0)),
            ('1', int(self.get('ENROLLMENT_BY_GRADE_ONE') or 0)),
            ('2', int(self.get('ENROLLMENT_BY_GRADE_TWO') or 0)),
            ('3', int(self.get('ENROLLMENT_BY_GRADE_THREE') or 0)),
            ('4', int(self.get('ENROLLMENT_BY_GRADE_FOUR') or 0)),
            ('5', int(self.get('ENROLLMENT_BY_GRADE_FIVE') or 0)),
            ('6', int(self.get('ENROLLMENT_BY_GRADE_SIX') or 0)),
            ('7', int(self.get('ENROLLMENT_BY_GRADE_SEVEN') or 0)),
            ('8', int(self.get('ENROLLMENT_BY_GRADE_EIGHT') or 0)),
            ('9', int(self.get('ENROLLMENT_BY_GRADE_NINE') or 0)),
            ('10', int(self.get('ENROLLMENT_BY_GRADE_TEN') or 0)),
            ('11', int(self.get('ENROLLMENT_BY_GRADE_ELEVEN') or 0)),
            ('12', int(self.get('ENROLLMENT_BY_GRADE_TWELVE') or 0)),
        ]

    def getName(self):
        return self.get('name') or self.get('INSTITUTION_NAME')

class SchoolDistrict(MongoModel):

    collectionName = 'schoolDistricts2'
    geoField = 'geo_simple'

    @classmethod
    def forAddress(cls, address):
        schoolDistricts = cls.queryGeoref(address.location)
        filteredDistricts = []
        if schoolDistricts and address.city:
            city = City.forSlug(address.city)
            allPrimarySDs = city.allPrimarySDs
            if allPrimarySDs:
                for sd in schoolDistricts:
                    if sd.geo_id in allPrimarySDs:
                        filteredDistricts.append(sd)

            if filteredDistricts:
                return filteredDistricts

        return [cls.pickBest(schoolDistricts)]

    @classmethod
    def forCity(cls, city):
        return cls.fromGeoIds(city.allPrimarySDs)

        # schoolDistricts = cls.queryGeoref(city.getGeoSimple())

        # for district in schoolDistricts:
        #     citySlug = "%s-%s" % (\
        #         district.LOCATION_CITY.lower().replace(' ', '-'),\
        #         district.STATE_ABBREV.lower()\
        #     )
        #     if (citySlug == 'new-york-ny' and (city.slug in NEW_YORK_CITY_SLUGS_SET))\
        #         or citySlug == city.slug:
        #         return district

        # return cls.pickBest(schoolDistricts)

    @classmethod
    def forRegion(cls, region):
        return cls.fromGeoIds(region.allPrimarySDs)
        #return cls.pickBest(cls.queryGeoref(region.getGeoSimple()))

    @classmethod
    def pickBest(cls, schoolDistricts):
        return max(
            schoolDistricts,
            key=lambda x: x.getCountSchools()
        )

    @classmethod
    def fromGeoIds(cls, geoIds):
        sds = []
        if geoIds:
            for geoId in geoIds:
                sd = cls.queryFirst({"geo_id" : geoId})
                if sd:
                    sds.append(sd)
        return sds

    def getCountSchools(self):
        total = 0
        if self['NUMBER_OF_SCHOOLS']:
            total += int(self['NUMBER_OF_SCHOOLS'])
        return total

class SchoolMaxBoundary(MongoModel):

    #collectionName = 'schoolMaxBoundaries'
    collectionName = 'schools2'
    geoField = 'geo_simple'

class SchoolMeasures(MongoModel):

    collectionName = 'schoolMeasures2'

class SchoolRatings(MongoModel):

    #collectionName = 'schoolRatings'
    collectionName = 'schools2'

class SocialCityPhoto(MongoModel):

    collectionName = 'socialcityTemp'

    @classmethod
    def forAddress(cls, address):
        query = {
            'state' : address.addrState,
            'type' : 'neighborhood'
        }
        results = cls.getNearest(
            address.location,
            3000,
            filter=query,
            geoField='center',
            limit=4,
        )

        if not results and address.city:
            results = cls.getByCitySlug(address.city)

        return results

    @classmethod
    def forRegion(cls, area):
        query = {
            'nhSlug' : area.slug
        }
        results = cls.queryEx(
            query,
            limit=1,
        )
        return results

    @classmethod
    def forCity(cls, city):
        return cls.getByCitySlug(city.slug)

    @classmethod
    def getByCitySlug(cls, citySlug):
        query = {
            'citySlug' : citySlug,
            'type' : 'city'
        }
        results = cls.queryEx(
            query,
            limit=1,
        )
        return results

class Sf1Table(object):

    @classmethod
    def cloneShape(cls, table):
        newTable = Sf1Table(0)
        for label, subTable in table.children.items():
            newTable.children[label] = cls.cloneShape(subTable)
        return newTable

    def __init__(self, value=None):
        self.value = value
        self.children = collections.OrderedDict()

    def addChild(self, label, value):
        self.children[label] = Sf1Table(value)
        return self.children[label]

    def allLabels(self):
        for label, subTable in self.children.items():
            yield [label]
            for subLabels in subTable.allLabels():
                yield [label] + subLabels

    def get(self, *keys):
        if len(keys) == 0:
            return self.value
        else:
            child = self.children[keys[0]]
            return child.get(*keys[1:])

    def getAll(self, *keys):
        if len(keys) == 0:
            return [
                (label, child.value)
                for label, child
                in self.children.iteritems()
            ]
        else:
            child = self.children[keys[0]]
            return child.getAll(*keys[1:])

    def set(self, value, *keys):
        if len(keys) == 0:
            self.value = value
        else:
            child = self.children[keys[0]]
            child.set(value, *keys[1:])

    def rebucket(self, mappings, *keys):
        data = self.getAll(*keys)

        mappingDict = {}
        output = []
        for (i, (mapTo, mapFroms)) in enumerate(mappings):
            output.append([mapTo, 0])
            for mapFrom in mapFroms:
                mappingDict[mapFrom] = i

        for (key, value) in data:
            output[mappingDict[key]][1] += value

        return output

    def zipSum(self, *keySets):
        data = []
        for keySet in keySets:
            data.append(self.getAll(*keySet))

        sums = []
        for aligned in zip(*data):
            value = sum([item[1] for item in aligned])
            sums.append((aligned[0][0], value))

        return sums

    def __str__(self, indent=0):
        lines = []
        for (key, table) in self.children.iteritems():
            lines.append("%s%s: %s" % (
                "  " * indent,
                key,
                table.value
            ))
            childString = table.__str__(indent + 1)
            if childString:
                lines.append(childString)
        return "\n".join(lines)

class Sf1TableSummer(object):

    def __init__(self):
        self.cloned = None

    def add(self, table):
        if table:
            if self.cloned is None:
                self.cloned = Sf1Table.cloneShape(table)
                self.allLabels = list(self.cloned.allLabels())

            for labels in self.allLabels:
                value = table.get(*labels)
                if value is not None:
                    current = self.cloned.get(*labels)
                    if not current:
                        currentValue = 0
                        currentCount = 0
                    else:
                        currentValue, currentCount = current
                    self.cloned.set((currentValue+value, currentCount+1), *labels)

    def crunch(self, average=False):
        if self.cloned:
            resultTable = Sf1Table.cloneShape(self.cloned)
            for labels in self.allLabels:
                sumValue, count = self.cloned.get(*labels)
                if average:
                    resultTable.set(sumValue / float(count), *labels)
                else:
                    resultTable.set(sumValue, *labels)
            return resultTable

class Sitemap(ndb.Model):

    generated = ndb.DateTimeProperty(auto_now_add=True)

class SitemapPage(ndb.Model):

    sitemap = ndb.KeyProperty(kind=Sitemap)
    gcsPath = ndb.StringProperty()

class StreeteasyBuilding(MongoModel):

    collectionName = 'streeteasyBuildings'

    @classmethod
    def forAddress(cls, address):
        return cls.queryFirst({'caddr': address.caddr})

class StreetTree(MongoModel):

    collectionName = 'streetTreeCensus'

    def public(self):
        return {
            'key': self.id,
            'location': self.geo,
            'type': "tree",
        }

class TigerLineMongoModel(MongoModel):

    collectionName = 'tiger2010'
    geoField = 'geo'

    @classmethod
    def forAddress(cls, address):
        """
            Queries the tiger-line database for the appropriate
            building, based on its location.
        """
        tigers = cls.queryGeoref(address.location)

        groups = {}
        for tiger in tigers:
            groups[tiger.summaryLevel] = tiger

        return groups

    def __init__(self, **kwargs):
        MongoModel.__init__(self, **kwargs)
        if 'BLOCKCE10' in self:
            self.summaryLevel = "Block"
        elif 'BLKGRPCE10' in self:
            self.summaryLevel = "Block Group"
        else:
            self.summaryLevel = "Tract"

    def getAcsSf1(self):
        query = {
            'COUNTY': self.COUNTYFP10,
            'STUSAB': CENSUS_STATE_STUSABS.get(self.STATEFP10),
            'TRACT': self.TRACTCE10,
        }
        if self.summaryLevel == 'Block Group':
            # query = {
            #     'SUMLEV': "091",
            # }
            # TODO: no way to query these yet...
            return None
        elif self.summaryLevel == 'Tract':
            query['SUMLEVEL'] = "080"
        return AcsSf1MongoModel.queryFirst(query)

    def getCensusSf1(self):
        query = {
            'COUNTY': self.COUNTYFP10,
            'STUSAB': CENSUS_STATE_STUSABS.get(self.STATEFP10),
            'TRACT': self.TRACTCE10,
        }
        if self.summaryLevel == 'Block':
            query['SUMLEV'] = "101"
            query['BLOCK'] = self.BLOCKCE10
        elif self.summaryLevel == 'Block Group':
            # query = {
            #     'SUMLEV': "091",
            # }
            # TODO: no way to query these yet...
            return None
        elif self.summaryLevel == 'Tract':
            query['SUMLEV'] = "080"

        census = CensusSf1MongoModel.queryFirst(query)
        return census

class User(BackedupNdbModel):

    accountStatus = ndb.StringProperty() #v2 active, inactive
    briteverifyStatus = ndb.StringProperty()
    created = ndb.DateTimeProperty()
    contactId = ndb.StringProperty() # v2
    email = ndb.StringProperty()
    emailOnly = ndb.BooleanProperty()
    bcc = ndb.StringProperty()
    firstName = ndb.StringProperty() # v2
    lastName = ndb.StringProperty() # v2
    phone = ndb.StringProperty() # v3
    # leadControl = ndb.StringProperty() # v2
    # verticalAllowed = ndb.StringProperty(repeated=True) # v2
    moveDateString = ndb.StringProperty()
    moveStatus = ndb.StringProperty()
    partner = ndb.KeyProperty('partnerKey', kind='SubdomainProperty_V2')
    passwordHash = ndb.StringProperty()
    passwordSalt = ndb.StringProperty()
    registeredTracker = ndb.KeyProperty(tracking.Tracker)
    registered = ndb.DateTimeProperty()
    status = ndb.StringProperty() # guest, member, pro
    source = ndb.StringProperty() # v2
    tracker = ndb.KeyProperty(tracking.Tracker)
    uid = ndb.StringProperty()
    unsubscribed = ndb.DateTimeProperty()

    #TODO a schedule job to geocode the user address.
    street = ndb.StringProperty() # v2
    city = ndb.StringProperty() # v2
    state = ndb.StringProperty() # v2
    zipcode = ndb.StringProperty() # v2
    location = ndb.GeoPtProperty() # v2
    addressStatus = ndb.StringProperty() #v2

    brandingDate = ndb.DateTimeProperty()

    charges = ndb.BlobProperty() # deprecated, but needs to be around due to https://code.google.com/p/googleappengine/issues/detail?id=11520

    firstSubDate = ndb.DateTimeProperty() #v3  we have populate all user objects with this field 

    @classmethod
    def get(cls):
        if not hasattr(flask.request, 'user'):
            user = None
            otuData = OtuToken.getData()
            if otuData is not None:
                key = rutil.safeAccess(otuData, 'user', 'key')
                if key:
                    user = ndb.Key(urlsafe=key).get()
                    if user:
                        user.login()

            if not user:
                user = User.ensureUser()
                user.login()

            flask.request.user = user

        return flask.request.user

    @classmethod
    def getOrRegisterEmailOnly(cls, email, context="alert-subscription"):

        existing = User.forEmail(email)
        if existing is not None:
            user = existing
        else:
            user = User.get()
            User.simpleUser(user, email, context)
        return user

    @classmethod
    def ensureUser(cls):
        userStr = flask.session.get('user')

        contactId = flask.request.cookies.get("contactId")
        user = None
        if userStr:
            user = pickle.loads(userStr)

        if User.needNewUser(user, contactId):
            user = User(status='guest')

            user.created = datetime.datetime.now()
            user.tracker = tracking.get().key
            user.uid = str(uuid.uuid4())
            user.partner = flask.request.appCustomizer.partnerSilo()
            user.contactId = contactId

            user.login()

        return user

    @classmethod
    def needNewUser(cls, user, contactId):
        
        if user is None:
            return True

        if not contactId:
            return False

        if user.contactId == contactId:
            return False

        contactIdPartnerApiKey = flask.request.cookies.get("contactIdPartnerApiKey")
        apiKey = flask.session['api_key']
        if contactIdPartnerApiKey is not None and contactIdPartnerApiKey == apiKey:
            return True
        return False

    @classmethod
    def simpleUser(cls, user, email, context, sendEmail=True, **kwargs):
        if user is None or user.status != 'guest':
            user = User()
            user.created = datetime.datetime.now()
            user.tracker = tracking.get().key
            user.uid = str(uuid.uuid4())

        password = str(uuid.uuid4())
        user.email = email.lower()
        user.emailOnly = True
        user.bcc = kwargs.get('bcc')
        user.setPassword(password)
        user.source = context
        user.status = 'member'
        user.registered = datetime.datetime.now()
        user.registeredTracker = tracking.get().key

        user.partner = kwargs.get(
            'partner',
            flask.request.appCustomizer.partnerSilo()
        )

        user.contactId = kwargs.get('contactId', user.contactId)
        user.firstName = kwargs.get('firstName', user.firstName)
        user.lastName = kwargs.get('lastName', user.lastName)
        user.phone = kwargs.get('phone', user.phone)
        # user.leadControl = kwargs.get('leadControl')
        # user.verticalAllowed = kwargs.get('verticalAllowed') or []
        user.street = kwargs.get('street', None)
        user.city = kwargs.get('city', None)
        user.state = kwargs.get('state', None)
        user.zipcode = kwargs.get('zipcode', None)
        user.addressStatus = kwargs.get('addressStatus', None)

        util.setAttrIfTruthy('moveDateString', kwargs, user)
        util.setAttrIfTruthy('moveStatus', kwargs, user)

        user.put()

        user.registrationCompleted(context, sendEmail=sendEmail)

        return user

    @classmethod
    def forEmail(cls, email, partner=None):
        if not email:
            return None
            
        email = email.lower()
        if partner is None:
            partner = flask.request.appCustomizer.partnerSilo()
        return User.query()\
            .filter(User.email == email)\
            .filter(User.partner == partner)\
            .get()

    @classmethod
    def forContactId(cls, contactId, partner):
        if not contactId:
            return None
        return User.query()\
            .filter(User.contactId == contactId)\
            .filter(User.partner == partner)\
            .get()

    @classmethod
    def latestUsers(cls, startDate, endDate, partner=None, limit=20):
        qry = cls.query()\
            .filter(User.partner == partner)\
            .filter(User.status == 'member')\
            .filter(User.registered >= startDate)\
            .filter(User.registered <= endDate)\
            .order(-User.registered)
            
        return qry.fetch(limit)

    @classmethod
    def logout(self):
        if 'user' in flask.session:
            del flask.session['user']

    def checkPassword(self, password):
        targetHash = hashlib.sha224(self.passwordSalt + password).hexdigest()
        return targetHash == self.passwordHash

    def getAdminLink(self):
        return '/admin/users/get/?%s' % urllib.urlencode({'user': self.key.urlsafe()})

    def getBriteverifyStatusByApi(self):
        credentials = keyserver.get()
        payload = {
            'contact[email]': self.email,
            'apikey': credentials['BRITEVERIFY_KEY'],
        }
        url = "https://bpi.briteverify.com/contacts.json?%s" % urllib.urlencode(payload)
        response = urlfetch.fetch(url, deadline=60)
        if response.status_code == 200:
            data = json.loads(response.content)
            emailInfo = data.get('email')
            if emailInfo:
                status = emailInfo.get('status')
                if status:
                    return status
                else:
                    return 'no-status'
            else:
                return 'no-info'
        else:
            return 'error'

    def getId(self):
        return self.uid or self.key.id()

    def getName(self):
        parts = []
        if self.firstName:
            parts.append(self.firstName)
        if self.lastName:
            parts.append(self.lastName)
        return ' '.join(parts)

    def getPartner(self):
        if not hasattr(self, '_partner'):
            if self.partner and self.partner.kind() == Partner._get_kind():
                self._partner = self.partner.get()
            else:
                self._partner = None
        return self._partner

    def getTracker(self):
        if not hasattr(self, '_tracker'):
            if self.tracker:
                self._tracker = self.tracker.get()
            else:
                self._tracker = None
        return self._tracker

    def isBriteverifyOk(self):
        if not self.briteverifyStatus:
            self.briteverifyStatus = self.getBriteverifyStatusByApi()
            self.put()
        return (self.briteverifyStatus != 'invalid')

    def isLoggedIn(self):
        user = User.get()
        return user.getId() == self.getId()

    def login(self):
        user = self
        if self.key and user.status != 'guest':
            ndbuser = self.key.get()
            if ndbuser:
                user = ndbuser
                if user.brandingDate:
                    delta = datetime.datetime.now() - user.brandingDate
                    if delta.days < 8:
                        partner = flask.request.appCustomizer.partnerSilo()
                        if partner and user.partner and partner != user.partner:
                            flask.session['api_key'] = user.partner.get().apiKey
                            flask.session['user_branding_changed'] = True
                            
        flask.session['user'] = pickle.dumps(user)
        flask.session.permanent = True
        flask.request.user = user

    def put(self):
        ndb.Model.put(self)
        if flask.request.userFacing:
            if self.isLoggedIn():
                self.login()

    def private(self):
        data = {
            'id': self.getId(),
            'email': self.email,
            'status': self.status,
        }
        return data

    def registrationCompleted(self, context, sendEmail=True):
        if sendEmail and context not in ['alert-subscription', 'report-block']:
            RegisteredEmail.send()
            
    def setPassword(self, password):
        self.passwordSalt = str(uuid.uuid4())
        self.passwordHash = hashlib.sha224(self.passwordSalt + password).hexdigest()

    def setAddressInfo(self, address, addressFrom=None):
        if not address:
            return None
        self.street = address.addrStreet
        self.city = address.addrCity
        self.state = address.addrState
        self.zipcode = address.addrZip
        self.setLocationFromAddress(address)
        self.addressStatus = addressFrom

    def setLocationFromAddress(self, address):
        if not address:
            return None

        location = address.getLocation()
        if location:
            coords = location['coordinates']
            if coords and len(coords) > 1:
                longitude = coords[0]
                latitude = coords[1]
                self.location = ndb.GeoPt(latitude,longitude)

class UserDailyAggs(MongoModel):
    collectionName = 'userDailyAggs'
    # day
    # dayDate
    # tag
    # total
    # delivery
    # open
    # click
    # unsub
    # date
    # shard
    # user

    @classmethod
    def createEmpty(cls, tag, user, dayDate):
        day = dayDate.strftime('%Y-%m-%d')
        return PartnerDailyAggs(
                day=day,
                dayDate=dayDate,
                tag=tag,
                total=0,
                delivery=0,
                open=0,
                click=0,
                unsub=0,
                user=user,
            )
    def __init__(self, **kwargs):
        if 'date' not in kwargs:
            kwargs['date'] = datetime.datetime.now()
        MongoModel.__init__(self, **kwargs)

    def getClickCount(self):
        return rutil.safeAccess(self, 'click') or 0

    def getDeliveryCount(self):
        return rutil.safeAccess(self, 'delivery') or 0
    
    def getTotalCount(self):
        return rutil.safeAccess(self, 'total') or 0

    def getOpenCount(self):
        return rutil.safeAccess(self, 'open') or 0

    def getUnsubscribeCount(self):
        return rutil.safeAccess(self, 'unsub') or 0

    def getReportViewCount(self):
        return rutil.safeAccess(self, "reportview") or 0

    def getUnopenCount(self):
        return self.getDeliveryCount() - self.getOpenCount()

class UserDailyEmailTemplateAggs(UserDailyAggs):
    collectionName = 'userDailyEmailTemplateAggs'

    @classmethod
    def createEmpty(cls, tag, user, dayDate, template):
        day = dayDate.strftime('%Y-%m-%d')
        return PartnerDailyAggs(
                day=day,
                dayDate=dayDate,
                tag=tag,
                template=template,
                total=0,
                delivery=0,
                open=0,
                click=0,
                unsub=0,
                user=user,
            )

    # def __init__(self, **kwargs):
    #     if 'date' not in kwargs:
    #         kwargs['date'] = datetime.datetime.now()
    #     MongoModel.__init__(self, **kwargs)

    # def getClickCount(self):
    #     return rutil.safeAccess(self, 'click') or 0

    # def getDeliveryCount(self):
    #     return rutil.safeAccess(self, 'delivery') or 0
    
    # def getTotalCount(self):
    #     return rutil.safeAccess(self, 'total') or 0

    # def getOpenCount(self):
    #     return rutil.safeAccess(self, 'open') or 0

    # def getUnsubscribeCount(self):
    #     return rutil.safeAccess(self, 'unsub') or 0

    # def getReportViewCount(self):
    #     return rutil.safeAccess(self, "reportview") or 0

    # def getUnopenCount(self):
    #     return self.getDeliveryCount() - self.getOpenCount()

class ZipcodeArea(MongoModel):

    collectionName = 'obiBoundariesZip3_2'
    geoField = 'geometry'

    @classmethod
    def forCity(cls, citySlug):
        zipcodeAreas = ZipcodeArea.query(
            { 'city': citySlug },
            limit=1000,
        )

        return zipcodeAreas

    @classmethod
    def forSlug(cls, zipcodeAreaSlug):
        matched = cls.queryFirst({'slug': zipcodeAreaSlug})
        if matched:
            return matched

    def getUrl(self):
        return "/report/zip/%s/%s/" % (self.city, self.slug)

    def getCity(self):
        return City.forSlug(self.city)

    def __init__(self, **kwargs):
        MongoModel.__init__(self, **kwargs)
        self.name = self.slug

    def getFieldValue(self, fieldname):
        field = self.get(fieldname)
        if field:
            return field
        else:
            return self.getFullCopy().get(fieldname)

    def getFullCopy(self):
        return ZipcodeArea.queryFirst({'_id': self._id})

    def getGeo(self):
        return self.getFieldValue('geometry')

    def getGeoSimple(self):
        return self.getFieldValue('geometry')

    def getReportStatKey(self):
        return ndb.Key('ZipcodeArea', self.slug)

    def getUrl(self, domain=False, require=None, page=None):
        if require == 'email':
            url = "/send-me/zip/%s/%s/" % (self.city, self.slug)
        else:
            url = "/report/zip/%s/%s/" % (self.city, self.slug)
            if page is not None:
                url += "%s/" % page
        if domain:
            return flask.request.appCustomizer.urlBase() + url
        else:
            return url

class ZipcodeVoterCounts(MongoModel):

    collectionName = 'zipcodeVoterCounts2'

    def toDict(self):
        counts = dict(self.__dict__)
        del counts['_id']
        del counts['area']
        return counts

# def paginateByTimeMongo(baseQuery, modelCls, dateField='date'):
#     query = baseQuery

#     dateFormat = "%Y-%m-%dT%H:%M:%S.%f"
#     cursorString = flask.request.values.get('cursor')
#     if cursorString:
#         date = datetime.datetime.strptime(cursorString, dateFormat)
#         query[dateField] = {'$lt': date}

#     events = modelCls.query(query, sort=[(dateField, -1)], limit=20)
#     if events:
#         cursor = events[-1][dateField].strftime(dateFormat)
#     else:
#         cursor = None
#     return events, cursor

# def paginateEmails():
#     query = {'shard': config.CONFIG['EMAIL']['shard']}
#     return paginateByTimeMongo(query, EmailSendLog)

CENSUS_STATE_STUSABS = {
    '02': 'AK',
    '01': 'AL',
    '05': 'AR',
    '60': 'AS',
    '04': 'AZ',
    '06': 'CA',
    '08': 'CO',
    '09': 'CT',
    '11': 'DC',
    '10': 'DE',
    '12': 'FL',
    '13': 'GA',
    '66': 'GU',
    '15': 'HI',
    '19': 'IA',
    '16': 'ID',
    '17': 'IL',
    '18': 'IN',
    '20': 'KS',
    '21': 'KY',
    '22': 'LA',
    '25': 'MA',
    '24': 'MD',
    '23': 'ME',
    '26': 'MI',
    '27': 'MN',
    '29': 'MO',
    '28': 'MS',
    '30': 'MT',
    '37': 'NC',
    '38': 'ND',
    '31': 'NE',
    '33': 'NH',
    '34': 'NJ',
    '35': 'NM',
    '32': 'NV',
    '36': 'NY',
    '39': 'OH',
    '40': 'OK',
    '41': 'OR',
    '42': 'PA',
    '72': 'PR',
    '44': 'RI',
    '45': 'SC',
    '46': 'SD',
    '47': 'TN',
    '48': 'TX',
    '49': 'UT',
    '51': 'VA',
    '78': 'VI',
    '50': 'VT',
    '53': 'WA',
    '55': 'WI',
    '54': 'WV',
    '56': 'WY',
}


class OldCity2(MongoModel):

    collectionName = 'obiBoundariesCp2_3'
    geoField = 'geometry'

    @classmethod
    def important(cls):
        from rentenna3.data.cities import CITIES
        return cls.query({ 'slug': { '$in': CITIES } })

    @classmethod
    def forSlug(cls, slug, fields=None):
        from rentenna3.data import cities
        if (slug is not None) and (slug != 'other'):
            city = cls.queryEx(
                {'slug': slug},
                fields=fields,
            )
            if city:
                return city[0]

        return OldCity2(slug='other', **cities.PSEUDO_CITY_OTHER)

    @classmethod
    def forState(cls, state):
        return cls.query(
            {'state': state.abbr},
            fields={'name': 1, 'slug': 1, 'center': 1, 'bounds': 1, 'state': 1},
            sort=[('name', 1)],
            limit=10000,
        )

    @classmethod
    def forSlugNoGeo(cls, slug):
        return cls.forSlug(slug, fields={'geometry':False})

    def __init__(self, focus=None, distance=None, searchName=None, **kwargs):
        MongoModel.__init__(
            self,
            focus=focus,
            distance=distance,
            searchName=searchName,
            **kwargs
        )

    def getCity(self):
        return self

    def getFieldValue(self, fieldname):
        field = self.get(fieldname)
        if field:
            return field
        else:
            return self.getFullCopy().get(fieldname)

    def isOther(self):
        return self.slug == "other"


class OldCity(MongoModel):

    collectionName = 'goodCities'
    geoField = 'geo'

    @classmethod
    def important(cls):
        from rentenna3.data.cities import CITIES
        return cls.query({ 'slug': { '$in': CITIES } })

    @classmethod
    def forSlug(cls, slug, fields=None):
        from rentenna3.data import cities
        if (slug is not None) and (slug != 'other'):
            city = cls.queryEx(
                {'slug': slug},
                fields=fields,
            )
            if city:
                return city[0]

        return OldCity(slug='other', **cities.PSEUDO_CITY_OTHER)

    @classmethod
    def forSlugNoGeo(cls, slug):
        return cls.forSlug(slug, fields={'geo':False, 'geo_simple':False})

    @classmethod
    def forState(cls, state):
        return cls.query(
            {'state': state.abbr},
            fields={'name': 1, 'slug': 1, 'center': 1, 'bounds': 1, 'state': 1},
            sort=[('name', 1)],
            limit=10000,
        )

    def __init__(self, focus=None, distance=None, searchName=None, **kwargs):
        MongoModel.__init__(
            self,
            focus=focus,
            distance=distance,
            searchName=searchName,
            **kwargs
        )

    def public(self):
        return {
            'name': self.name,
            'slug': self.slug,
            'center': self.center,
            'bounds': self.bounds,
        }

    def getCity(self):
        return self

    def getFieldValue(self, fieldname):
        field = self.get(fieldname)
        if field:
            return field
        else:
            return self.getFullCopy().get(fieldname)

    def getFullCopy(self):
        return OldCity.queryFirst({'slug': self.slug})

    def getGeo(self):
        return self.getFieldValue('geo')

    def getGeoSimple(self):
        return self.getFieldValue('geo')

    def getDistance(self, type):
        from rentenna3.data.cities import DISTANCE_DEFAULTS
        if self.distance:
            return self.distance[type]
        else:
            return DISTANCE_DEFAULTS[type]

    def getFocus(self):
        return self.focus or self.bounds

    def getReportStatKey(self):
        return ndb.Key('City', self.slug)

    def getSearchName(self):
        if self.searchName:
            return self.searchName
        else:
            return "%s, %s" % (self.name, self.state)

    def getStateAbbr(self):
        return self.getFieldValue('state') or ''

    def getState(self):
        return ArState.forAbbr(self.state)

    def getUrl(self, domain=False, require=None, page=None):
        if require == 'email':
            url = '/send-me/city/%s/' % self.slug
        else:
            url = '/report/city/%s/' % self.slug
            if page is not None:
                url += "%s/" % page
        if domain:
            return flask.request.appCustomizer.urlBase() + url
        else:
            return url

    def isOther(self):
        return self.slug == "other"

    def isFull(self):
        return self.slug in [
            'manhattan',
            'queens',
            'brooklyn',
            'staten-island',
            'bronx',
        ]

class OldArea2(MongoModel):

    collectionName = 'obiBoundariesNh2_3'
    geoField = 'geometry'

    @classmethod
    def forCity(cls, citySlug):
        return cls.query(
            {'city': citySlug},
            sort=[('name', 1)],
            fields={'city': 1, 'slug': 1, 'name': 1, 'children': 1},
            limit=1000,
        )

    @classmethod
    def forSlug(cls, areaSlug, fields=None):
        area = cls.queryEx(
            {'slug': areaSlug},
            fields=fields,
        )

        if area:
            return area[0]
        else:
            return None

    @classmethod
    def forSlugNoGeo(cls, slug):
        return cls.forSlug(slug, fields={'geometry':False})


    def __init__(self, **kwargs):
        MongoModel.__init__(self, **kwargs)
        self.parent = None
        self.name = self.get('name')
        self.children=(self.get('children') or [])

    def getCity(self):
        return OldCity2.forSlug(self.city)

    
    def getFieldValue(self, fieldname):
        field = self.get(fieldname)
        if field:
            return field
        else:
            return self.getFullCopy().get(fieldname)

class OldArea(MongoModel):

    collectionName = 'goodAreas'
    geoField = 'geo_simple'

    @classmethod
    def forCity(cls, citySlug):
        return cls.queryEx(
            {'city': citySlug},
            sort=[('name', 1)],
            fields={'city': 1, 'slug': 1, 'name': 1, 'children': 1},
            limit=1000,
        )

    @classmethod
    def forSlug(cls, areaSlug, fields=None):
        area = cls.queryEx(
            {'slug': areaSlug},
            fields=fields,
        )

        if area:
            return area[0]
        else:
            return None

    @classmethod
    def forSlugNoGeo(cls, areaSlug):
        return cls.forSlug(areaSlug, fields={'geo':False, 'geo_simple':False})

    def getUrl(self):
        return "/report/neighborhood/%s/%s/" % (self.city, self.slug)

    def __init__(self, **kwargs):
        MongoModel.__init__(self, **kwargs)
        self.parent = None
        self.name = self.get('name')
        self.children=(self.get('children') or [])

    def getCity(self):
        return OldCity.forSlug(self.city)

    def getChildren(self):
        return OldArea.query({ 'slug': { '$in': self.children } })

    def getDepth(self):
        parent = self.getParent()
        if parent:
            return 1 + parent.getDepth()
        else:
            return 1

    def getFieldValue(self, fieldname):
        field = self.get(fieldname)
        if field:
            return field
        else:
            return self.getFullCopy().get(fieldname)

    def getFullCopy(self):
        return OldArea.queryFirst({'slug': self.slug})

    def getGeo(self):
        return self.getFieldValue('geo')

    def getGeoSimple(self):
        return self.getFieldValue('geo_simple')

    def getParent(self):
        if self.parent:
            return Area.forSlug(self.parent)

    def getRanks(self):
        ranking = AreaRanking.get_by_id(self.slug)
        if ranking:
            return ranking.ranks

    def getReportStatKey(self):
        return ndb.Key('Area', self.slug)

    def getUrl(self, domain=False, require=None, page=None):
        if require == 'email':
            url = "/send-me/neighborhood/%s/%s/" % (self.city, self.slug)
        else:
            url = "/report/neighborhood/%s/%s/" % (self.city, self.slug)
            if page is not None:
                url += "%s/" % page
        if domain:
            return flask.request.appCustomizer.urlBase() + url
        else:
            return url