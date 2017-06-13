import datetime
import flask
import random
import time
import geohash
import uuid
import bson
import json
import re

from google.appengine.ext import ndb
from google.appengine.api import memcache

from web import validate
from web import tracking
from web.base import BaseView, Route
from web.config import CONFIG

from rentenna3 import geocoder
from rentenna3 import api
from rentenna3.base import Report
from rentenna3.models import *
from rentenna3.backgroundViews import *
from rentenna3.email import *

class AlertService(BaseView):

    @Route('/service/subscribe-alerts/')
    def subscribe(self):
        user = User.get()
        propertySlug = validate.get('property', validate.Required())
        propertyKey = ndb.Key(Property, propertySlug)
        if validate.get('subscribe', validate.ParseBool()):
            appCustomizer = flask.request.appCustomizer
            skipConfirmationEmail = appCustomizer.skipAlertConfirmation()
            AlertSubscription.subscribe(propertyKey, skipConfirmationEmail=skipConfirmationEmail)
        else:
            AlertSubscription.unsubscribe(propertyKey)
        return "OK"

class AutocompleteService(BaseView):

    @Route('/service/autocomplete/')
    def autocomplete(self):
        query = validate.get('query', validate.Required())
        types = validate.get('types', validate.ParseJson())
        bias = validate.get('bias', validate.ParseJson())

        if not bias:
            fromHeader = flask.request.headers.get('X-AppEngine-CityLatLong')
            if fromHeader:
                latLong = fromHeader.split(",")
                bias = {
                    'type': "Point",
                    'coordinates': [
                        float(latLong[1]),
                        float(latLong[0]),
                    ]
                }

        results = []

        if len(query) >= 2:
            if ((not types) or ('address' in types)) and (query[0] in '0123456789'):
                googleResults = api.googleAutocomplete(query, bias=bias)
                for prediction in googleResults['predictions']:
                    description = prediction['description'].encode('utf-8')
                    if description[0] in '0123456789':
                        results.append({
                            'type': "address",
                            'name': ", ".join(description.split(",")[:-1]),
                            'reference': prediction['reference'],
                            'reportUrl': "/find-address/?%s" % urllib.urlencode({
                                'query': description,
                                'callback': "report",
                            }),
                        })

            hasUnitResult = False
            unitEnabled = CONFIG['AUTOCOMPLETE']['unit']
            if unitEnabled:
                isUnitSearch = not results and query[0] in '0123456789' and \
                    ( not types or (len(types) == 1 and 'address' in types) )

                pickLimitedUnitsOnly = False
                if not isUnitSearch:
                    if '#' in query and query[0] in '0123456789':
                        isUnitSearch = True
                        pickLimitedUnitsOnly = True

                # seach property with unit
                if isUnitSearch:
                    unitResults = AutocompleteUnitElastic.search(
                                query,
                                types=types,
                                bias=bias,
                            )
                    hasUnitResult = len(unitResults) > 0
                    if pickLimitedUnitsOnly:
                        results = unitResults[:2] + results
                    else:
                        results += unitResults
            
            if not hasUnitResult:
                if (not types) or ('city' in types) or ('zip' in types) or ('area' in types):
                    elastic = CONFIG['AUTOCOMPLETE']['elastic']

                    if elastic:
                        elasticResults = AutocompleteElastic.search(
                                query,
                                types=types,
                                bias=bias,
                            )

                        results += elasticResults
                    else:
                        results += [
                            result.getJson()
                            for result
                            in Autocomplete.search(
                                query,
                                types=types,
                                bias=bias,
                            )
                        ]

        if ((not types) or ('zip' in types)) and (re.match(r'^[0-9]{5}$', query)):
            results = sorted(results, key=lambda x: (x['type'] != 'zip'))

        return flask.jsonify({
            'status': "OK",
            'results': results,
        })

class ComputeReportStats(BaseView):

    @Route('/service/compute-report-stats/')
    def get(self):
        type = validate.get('type')
        targetKey = validate.get('target', validate.NdbKey())
        if type == 'property':
            target = Address.getBySlug(targetKey.id())
            if not target:
                target = geocoder.getAddressBySlugWorkaround(targetKey.id())
            city = target.getCity()
        elif type == 'city':
            target = City.forSlug(targetKey.id())
            city = target
        elif type == 'neighborhood':
            target = Area.forSlug(targetKey.id())
            city = target.getCity()
        elif type == 'zipcode':
            target = ZipcodeArea.forSlug(targetKey.id())
            city = target.getCity()
        else:
            flask.abort(400)
        reporterName = validate.get('reporter', validate.Required())
        verbose = validate.get('verbose', validate.ParseBool())

        report = Report(
            type,
            city,
            targetKey,
            target,
            doMinimal=False,
            limitReporter=reporterName,
        )
        stats = report.runReporter(reporterName)
        if verbose:
            logging.info(stats)
        return flask.jsonify({
            'status': "OK",
        })

class DistrictBoundary(BaseView):

    @Route('/service/load-district-boundary/')
    def get(self):
        id = validate.get('id')
        district = SchoolDistrict.queryFirst({'obId': id}, {"geo" : 1})
        if district:
            return flask.jsonify({
                'status': "OK",
                'geo': district['geo'],
            })
        else:
            return flask.jsonify({
                'status': "NOT_FOUND",
            })

    @Route('/service/load-school-boundary/')
    def getSchool(self):
        id = validate.get('id')
        school = School.queryFirst({'obId': id}, {"geo" : 1})
        if school:
            return flask.jsonify({
                'status': "OK",
                'geo': school['geo'],
            })
        else:
            return flask.jsonify({
                'status': "NOT_FOUND",
            })

class LoadMapPois(BaseView):

    @Route('/service/load-citibike-stations/')
    def getCitibike(self):
        return self.getBounded(
            'citibike-3',
            CitibikeStation,
            fields=['geo', 'id']
        )

    @Route('/service/load-crime-pins/')
    def getCrime(self):
        lastYear = datetime.datetime.now() - datetime.timedelta(days=365)
        return self.getBounded(
            'nypd',
            NypdCrimeMongoModel,
            limit=1000,
            filter={
                'crime': {
                    '$ne': "GRAND LARCENY"
                },
                'date': {
                    '$gte': lastYear
                }
            },
            fields=['geo', 'crime', 'count', 'gxId'],
        )

    @Route('/service/load-demolitions/')
    def getDemolitions(self):
        lastYear = datetime.datetime.now() - datetime.timedelta(days=365)
        return self.getBounded(
            'demolition',
            NycDobJob,
            filter={
                'JobType': 'DM',
                'FullyPaid': {'$gt': lastYear},
            },
            fields=['location', 'JobType', 'Job'],
        )

    @Route('/service/load-adjacent-flood-zones/')
    def getFloodZones(self):
        return self.getBounded(
            'floodzone',
            FloodZoneMongoModel,
            idField='id',
            fields=['geo', 'Zone', 'id']
        )

    @Route('/service/load-new-buildings/')
    def getNewBuildings(self):
        lastYear = datetime.datetime.now() - datetime.timedelta(days=365)
        return self.getBounded(
            'new-building',
            NycDobJob,
            filter={
                'JobType': 'NB',
                'FullyPaid': {'$gt': lastYear},
            },
            fields=['location', 'JobType', 'Job'],
        )

    @Route('/service/load-noise-complaints/')
    def getNoisePins(self):
        lastPeriod = datetime.datetime.now() - datetime.timedelta(days=365)
        return self.getBounded(
            'noise-2',
            Nyc311CallModel,
            filter={
                'complaint_type': {
                    '$in': Nyc311CallModel.NOISE_TYPES
                },
                'created_date': {
                    '$gte': lastPeriod
                }
            },
            fields=['location', 'complaint_type', 'descriptor', 'unique_key'],
            precision=7,
        )

    @Route('/service/load-filth-complaints/')
    def getFilthPins(self):
        lastPeriod = datetime.datetime.now() - datetime.timedelta(days=365)
        return self.getBounded(
            'filth-2',
            Nyc311CallModel,
            filter={
                'complaint_type': {
                    '$in': Nyc311CallModel.FILTH_TYPES
                },
                'created_date': {
                    '$gte': lastPeriod
                }
            },
            fields=['location', 'complaint_type', 'descriptor', 'unique_key'],
            precision=7,
        )

    @Route('/service/load-rodent-complaints/')
    def getRodentPins(self):
        lastPeriod = datetime.datetime.now() - datetime.timedelta(days=180)
        return self.getBounded(
            'rodent-2',
            Nyc311CallModel,
            filter={
                'complaint_type': 'Rodent',
            }, fields=['location', 'complaint_type', 'descriptor', 'unique_key'],
            precision=7,
        )

    @Route('/service/load-scaffolds/')
    def getScaffolds(self):
        lastYear = datetime.datetime.now() - datetime.timedelta(days=90)
        return self.getBounded(
            'scaffold',
            NycDobJob,
            filter={
                'PermitSubtype': {'$in': ['SF', 'SH']},
                'JobStartDate': {'$gt': lastYear},
            },
            fields=['location', 'JobType', 'Job', 'PermitSubtype'],
        )

    @Route('/service/load-street-complaints/')
    def getStreetPins(self):
        lastPeriod = datetime.datetime.now() - datetime.timedelta(days=365)
        return self.getBounded(
            'street-3',
            Nyc311CallModel,
            filter={
                'complaint_type': {
                    '$in': Nyc311CallModel.STREET_TYPES
                },
                'created_date': {
                    '$gte': lastPeriod
                }
            }, fields=['location', 'complaint_type', 'descriptor', 'unique_key'],
            precision=7,
        )

    @Route('/service/load-street-trees/')
    def getStreetTrees(self):
        return self.getBounded(
            'trees-4',
            StreetTree,
            fields=['geo', 'id'],
            precision=7,
        )

    def getBounded(self, key, model, idField=None, precision=6, **kwargs):
        north = validate.get('north', validate.ParseFloat(), validate.Required())
        south = validate.get('south', validate.ParseFloat(), validate.Required())
        east = validate.get('east', validate.ParseFloat(), validate.Required())
        west = validate.get('west', validate.ParseFloat(), validate.Required())

        count = 0
        results = {}
        if (north != south) and (east != west):
            geohashes = self._getGeohashes(north, south, east, west, precision)
            for (hashcode, bounds) in geohashes:
                subresults = self._query(
                    key,
                    hashcode,
                    bounds,
                    model,
                    kwargs
                )
                for result in subresults:
                    count += 1
                    if idField:
                        results[result.get(idField)] = result
                    else:
                        results[count] = result
        return flask.jsonify({
            'status': "OK",
            'results': results.values(),
        })

    def _getGeohashes(self, north, south, east, west, precision):
        # get all geohashes of provided precision that intersect the bounds
        # TODO: there is most certainly a more efficient way to compute these bad boys

        centerLat = (north + south) / 2.
        centerLon = (west + east) / 2.

        hashcode = geohash.encode(centerLat, centerLon, precision=precision)
        geohashes = {hashcode: geohash.bbox(hashcode)}
        for i in range(0, 3): # limit to 3 iterations
            if self._geohashesContainBounds(geohashes, north, south, east, west):
                break
            else:
                self._growGeohashes(geohashes)

        return self._trimGeohashes(geohashes, north, south, east, west)

    def _geohashesContainBounds(self, geohashes, north, south, east, west):
        # returns true if the provided bounds are entirely contained by the geohashes
        maxNorth = max(geo['n'] for geo in geohashes.itervalues())
        minSouth = min(geo['s'] for geo in geohashes.itervalues())
        maxEast = max(geo['e'] for geo in geohashes.itervalues())
        minWest = min(geo['w'] for geo in geohashes.itervalues())
        return (maxNorth >= north)\
            and (minSouth <= south)\
            and (maxEast >= east)\
            and (minWest <= west)

    def _growGeohashes(self, geohashes):
        # add all neighbors of all geohashes to the dictionary
        for hashcode in geohashes.keys():
            for neighbor in geohash.neighbors(hashcode):
                if neighbor not in geohashes:
                    geohashes[neighbor] = geohash.bbox(neighbor)

    def _query(self, key, hashcode, bounds, model, kwargs):
        memkey = "geohash-%s:%s" % (key, hashcode)
        results = memcache.get(memkey)
        if results is None:
            coordinates = [[
                [bounds['e'], bounds['n']],
                [bounds['w'], bounds['n']],
                [bounds['w'], bounds['s']],
                [bounds['e'], bounds['s']],
                [bounds['e'], bounds['n']],
            ]]
            items = model.inBounds(coordinates, **kwargs)
            results = [item.public() for item in items]
            memcache.set(memkey, results)
        return results

    def _trimGeohashes(self, geohashes, north, south, east, west):
        # return only the geohashes that intersect the bounds
        results = []
        for (hashcode, bounds) in geohashes.iteritems():
            if (bounds['s'] <= north)\
                    and (bounds['n'] >= south)\
                    and (bounds['w'] <= east)\
                    and (bounds['e'] >= west):
                results.append((hashcode, bounds))
        return results

class LoadSchoolStats(BaseView):

    @Route('/service/load-test-scores/')
    def loadTestScores(self):
        schoolId = validate.get('schoolId')
        schoolMeasures = [
            measure.__json__()
            for measure
            in SchoolMeasures.query({
                'OB_INST_ID': schoolId
            })
        ]

        if schoolMeasures:
            responseData = {
                'status': "OK",
                'measures': schoolMeasures,
            }

            return flask.Response(
                bson.json_util.dumps(responseData),
                mimetype='text/json',
            )
        else:
            return flask.jsonify({
                'status': "NOT_FOUND",
            })

class SpeakWithExpert(BaseView):

    @Route('/service/speak-with-expert/')
    def speak(self):
        propertySlug = validate.get('property')
        userStatus = validate.get('userStatus')

        if userStatus == 'new':
            return "OK"

        user = User.get()
        reportUrl = None
        
        address = Address.getBySlug(propertySlug)
        if address:
            property = address.getProperty()
            if property:
                reportUrl = address.getUrl(domain=True)

        PartnerNewLead.sendAsNeeded(
            user=user,
            reportUrl=reportUrl,
            subjectSuffix='Existing Contact',
        )

        return "OK"

class UserServices(BaseView):

    @Route('/service/user/login/', methods=['POST'])
    def login(self):
        email = validate.get('email', validate.Required())
        password = validate.get('password', validate.Required())

        user = User.forEmail(email)
        if user is None:
            return flask.jsonify({
                'status': "NO-EMAIL",
            })
        else:
            passwordMatch = user.checkPassword(password)
            if passwordMatch:
                if user.tracker is None:
                    user.tracker = tracking.get().key
                    user.registeredTracker = tracking.get().key
                    user.put()
                user.login()
                return flask.jsonify({
                    'status': "OK",
                    'user': user.private(),
                })
            else:
                return flask.jsonify({
                    'status': "WRONG-PASSWORD",
                })

    @Route('/service/user/subscribe/', methods=['POST'])
    def subscribe(self):
        email = validate.get('email', validate.Required())
        propertySlug = validate.get('propertySlug')

        user = User.getOrRegisterEmailOnly(email, context="alert-subscription")
        user.login()
        #note: property page will automatically subscribe the alert thwen loginregistermodal receive the response
        # if propertySlug:
        #     address = Address.getBySlug(propertySlug)
        #     property = address.getProperty()

        #     if property:
        #         AlertSubscription.subscribe(
        #             propertyKey=property.key,
        #             user=user,
        #             skipConfirmationEmail=True,
        #         )

        return flask.jsonify({
            'status': "OK",
            'user': user.private(),
        })

    @Route('/service/user/register/', methods=['POST'])
    def register(self):
        email = validate.get('email', validate.Required())
        emailOnly = validate.get('emailOnly', validate.ParseBool())
        context = validate.get('context')
        propertySlug = validate.get('propertySlug')

        if emailOnly:
            password = str(uuid.uuid4())
        else:
            password = validate.get('password', validate.Required())

        existing = User.forEmail(email)
        if existing is not None:
            # if password matches, log in
            passwordMatch = existing.checkPassword(password)
            if passwordMatch:
                existing.login()
                return flask.jsonify({
                    'status': "LOGIN-REGISTER",
                    'user': existing.private()
                })
            else:
                # existing password
                return flask.jsonify({
                    'status': "IN-USE",
                })
        else:
            user = User.get()

            # It is possible to get here already registered
            # if you have multiple tabs open and then
            # register in one of them.
            if user.status == 'guest':
                user.email = email.lower()
                user.emailOnly = emailOnly
                user.setPassword(password)
                user.status = 'member'
                user.registered = datetime.datetime.now()
                user.registeredTracker = tracking.get().key
                user.moveDateString = validate.get('moveDate')
                user.moveStatus = validate.get('moveStatus')
                user.partner = flask.request.appCustomizer.partnerSilo()
                user.put()

                user.registrationCompleted(context, sendEmail=True)

                reportUrl = None
                if propertySlug:
                    address = Address.getBySlug(propertySlug)
                    property = address.getProperty()
                    if property:
                        reportUrl = address.getUrl(domain=True)
                        AlertSubscription.subscribe(
                            propertyKey=property.key,
                            user=user,
                            skipConfirmationEmail=True,
                        )

                if not reportUrl:
                    if user.tracker:
                        tracker = user.tracker.get()
                        reportUrl = tracker.landingUrl
                        
                PartnerNewLead.sendAsNeeded(
                    user=user,
                    reportUrl=reportUrl,
                )

            return flask.jsonify({
                'status': "OK",
                'user': user.private(),
            })

    @Route('/service/user/reset-password/', methods=['POST'])
    def resetPassword(self):
        email = flask.request.values.get('email')
        if email:
            user = User.query().filter(User.email == email).get()
            token = PasswordResetToken(
                user=user.key,
                expires=datetime.datetime.now()+datetime.timedelta(days=3),
                uid=str(uuid.uuid4()),
            )
            token.put()
            ResetPassword.send(token=token.uid, user=user)
        return "OK"
