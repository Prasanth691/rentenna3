import uuid
import flask
import csv
import math
import numpy
import json
import logging
import pickle
import datetime
import random
import re
import traceback
import urllib
import urllib2
import uuid
import xlrd
import zipfile
import zlib

import cloudstorage as gcs

from bson import ObjectId
from dateutil.relativedelta import relativedelta
from fastkml import kml
from StringIO import StringIO
from zipfile import ZipFile

from google.appengine.api import urlfetch
from google.appengine.ext.blobstore import blobstore
from google.appengine.api.datastore_types import BlobKey

from web import api as rapi
from web import config
from web import counters
from web import keyserver
from web import rtime
from web import taskqueue
from web import validate
from web.base import BaseView, Route
from web.crawling import CrawlResponse, CrawlSelector

from rentenna3 import api
from rentenna3 import geocoder
from rentenna3 import util
from rentenna3.base import _alertReporters
from rentenna3.base import _hybridAlertReporters
from rentenna3.base import _partnerAlertReporters
from rentenna3.models import *
from rentenna3.email import *

from web.ndbChunker import InvokeForAllNdb,InvokeForOneNdbForTest

class AlertReaper(BaseView):

    @Route('/background/reap-alerts/')
    def reap(self):
        # TODO: other types
        # TODO: other schedules
        today = datetime.datetime.now().strftime("%A")
        overrideDay = validate.get('overrideDay')
        if overrideDay:
            today = overrideDay
        logging.info("Evaluating %s alerts" % today)
        for alert in _alertReporters['property'].values():
            if alert.schedule == today and alert.isDataReady():
                logging.info("Today's alert: %s" % alert.__name__)
                alerts = AlertSubscription.query()
                InvokeForAllNdb.invoke(
                    alerts, 
                    task='/background/reap-alerts/for-property/',
                    queue='alerts',
                    params={
                        'type': alert.__name__
                    }
                )
        return "OK"

    @Route('/background/reap-alerts/for-property/', methods=['GET', 'POST'])
    def forProperty(self):
        type = validate.get('type')
        alert = validate.get('key', validate.NdbKey()).get()
        address = alert.getAddress()
        if not address:
            address = geocoder.getAddressBySlugWorkaround(alert.property.id())
        alerterCls = _alertReporters['property'][type]
        if (alerterCls.cities is None) or (address.city in alerterCls.cities):
            alerter = alerterCls(alert, address)
            payload = alerter.report()
            if payload:
                alerter.template.send(
                    user=alert.user.get(),
                    property=alert.property.get(),
                    **payload
                )
        return "OK"

    @Route('/background/reap-hybrid-alerts/')
    def reapHybrid(self):
        # TODO: other types
        # TODO: other schedules
        today = datetime.datetime.now().strftime("%A")
        overrideDay = validate.get('overrideDay')
        if overrideDay:
            today = overrideDay
        logging.info("Evaluating %s hybrid alerts" % today)
        for alert in _hybridAlertReporters['property'].values():
            if alert.schedule == today and alert.isHybrid and alert.isDataReady():
                meta = alert.getMetadata()
                params = {
                        'type': alert.__name__,
                        'metadata': pickle.dumps(meta),
                    }

                logging.info("Today's hybrid alert: %s" % alert.__name__)
                alerts = AlertSubscription.query()
                InvokeForAllNdb.invoke(
                    alerts, 
                    task='/background/reap-hybrid-alerts/for-property/',
                    queue='alerts',
                    params=params
                )
        return "OK"

    @Route('/background/reap-hybrid-alerts/for-property/', methods=['GET', 'POST'])
    def forHybridProperty(self):
        type = validate.get('type')
        alert = validate.get('key', validate.NdbKey()).get()
        metadata = validate.get('metadata', validate.Unpickle())

        address = alert.getAddress()
        if not address:
            address = geocoder.getAddressBySlugWorkaround(alert.property.id())
        alerterCls = _hybridAlertReporters['property'][type]
        
        if (alerterCls.cities is None) or (address.city in alerterCls.cities):
            alerter = alerterCls(alert, address)
            payload = alerter.report(**metadata)
            if payload:
                alerter.template.send(
                    user=alert.user.get(),
                    property=alert.property.get(),
                    **payload
                )
        return "OK"

    @Route('/background/reap-partner-alerts/')
    def reapPartner(self):
        today = datetime.datetime.now().strftime("%A")
        overrideDay = validate.get('overrideDay')
        if overrideDay:
            today = overrideDay
        logging.info("Evaluating %s partner alerts" % today)
        for alert in _partnerAlertReporters['partner'].values():
            if alert.schedule == today:
                logging.info("Today's partner alert: %s" % alert.__name__)
                alerts = Partner.query().filter(Partner.status == 'active')
                InvokeForAllNdb.invoke(
                    alerts, 
                    task='/background/reap-partner-alerts/for-partner/',
                    queue='partner-alerts',
                    params={
                        'type': alert.__name__
                    }
                )
        return "OK"

    @Route('/background/reap-partner-alerts/for-partner/', methods=['GET', 'POST'])
    def forPartner(self):
        type = validate.get('type')
        partner = validate.get('key', validate.NdbKey()).get()
        alerterCls = _partnerAlertReporters['partner'][type]
        alerter = alerterCls(partner)
        payload = alerter.report()
        if payload:
            alerter.template.send(
                partner=partner,
                **payload
            )
        return "OK"

    #TODO: this is test endpoint, 
    @Route('/admin/reap-alerts-temp/')
    def reaptemp(self):
        from web.admin import requireRole
        #from web.ndbChunker import InvokeForOneNdbForTest
        requireRole('admin')

        alertName = validate.get('alert_reporter')
        today = datetime.datetime.now().strftime("%A")

        logging.info("Evaluating %s alerts" % today)
        for alert in _alertReporters['property'].values():
            if alert.__name__ == alertName:
                logging.info("Today's alert: %s" % alert.__name__)
                alerts = AlertSubscription.query()
                InvokeForOneNdbForTest.invoke(
                    alerts, 
                    task='/background/reap-alerts/for-property/',
                    queue='alerts',
                    params={
                        'type': alert.__name__
                    }
                )
        return "OK"

    #TODO: this is test endpoint, 
    @Route('/admin/reap-hybrid-alerts-temp/')
    def reapHybridTemp(self):
        from web.admin import requireRole
        #from web.ndbChunker import InvokeForOneNdbForTest
        requireRole('admin')

        alertName = validate.get('alert_reporter')
        today = datetime.datetime.now().strftime("%A")

        logging.info("Evaluating %s alerts" % today)
        for alert in _hybridAlertReporters['property'].values():
            if alert.__name__ == alertName:
                meta = alert.getMetadata()
                params = {
                        'type': alert.__name__,
                        'metadata': pickle.dumps(meta),
                    }
                logging.info("Today's alert: %s" % alert.__name__)
                alerts = AlertSubscription.query()
                InvokeForOneNdbForTest.invoke(
                    alerts, 
                    task='/background/reap-hybrid-alerts/for-property/',
                    queue='alerts',
                    params=params
                )
        return "OK"

    #TODO: this is test endpoint, 
    @Route('/admin/reap-demo-partner-alerts-temp/')
    def reaptempDemoPartner(self):
        from web.admin import requireRole
        #from web.ndbChunker import InvokeForOneNdbForTest
        requireRole('admin')

        today = datetime.datetime.now().strftime("%A")
        shard=config.CONFIG['EMAIL']['shard']
        logging.info("Evaluating %s demo partner alerts" % today)
        for alert in _partnerAlertReporters['partner'].values():
            logging.info("Today's alert: %s" % alert.__name__)

            apiKey = '4e004d4c-1e1e-4d5f-9632-b88e75e54fba'
            if shard == 'qa':
                apiKey = 'a55e6392-faed-4568-96ec-96aa9fe7b423'
            if shard == 'staging':
                apiKey = "e0d73422-27c2-4604-b28a-02bd9b9468ff"
            if shard == 'production':
                apiKey = 'c4619846-82d5-4015-b627-a5e285cf8c8b'

            alerts = Partner.query().filter(Partner.status == 'active').filter(Partner.apiKey==apiKey)
            InvokeForOneNdbForTest.invoke(
                alerts, 
                task='/background/reap-partner-alerts/for-partner/',
                queue='partner-alerts',
                params={
                    'type': alert.__name__
                }
            )
        return "OK"

class CityReportBuilding(BaseView):
    """
        Computes stats for all cities
    """

    @Route('/background/compute-city-reports/', methods=['GET', 'POST'])
    def start(self):
        for state in ArState.all():
            taskqueue.add(
                url='/background/compute-city-reports/state/%s/' % state.slug,
                queue_name='default',
            )
        return "OK"

    @Route('/background/compute-city-reports/state/<state>/', methods=['GET', 'POST'])
    def forState(self, state):
        state = ArState.forSlug(state)
        for city in City.forState(state):
            taskqueue.add(
                url='/background/compute-city-reports/city/%s/' % city.slug,
                queue_name='default',
            )
        return "OK"

    @Route('/background/compute-city-reports/city/<citySlug>/', methods=['GET', 'POST'])
    def computeStats(self, citySlug):
        city = City.forSlug(citySlug)
        cityKey = ndb.Key('City', citySlug)
        reporter = validate.get('reporter')

        report = Report(
            type='city',
            city=city,
            key=city.getReportStatKey(),
            target=city,
            limitReporter=reporter,
            doMinimal=False,
            isPrecompute=True,
        )

        if reporter:
            logging.info("%s - %s" % (citySlug, reporter))
            try:
                stats = report.runReporter(reporter)
                logging.info(stats)
            except Exception as e:
                logging.error(traceback.format_exc())
        else:
            for reporter in report.getPendingReporters():
                taskqueue.add(
                    url='/background/compute-city-reports/city/%s/' % citySlug,
                    params={
                        'reporter': reporter['name'],
                    },
                    queue_name='default',
                )

        return "OK"

class DeliverLead(BaseView):

    @Route('/background/deliver-lead/', methods=['GET', 'POST'])
    def deliver(self):
        logging.info(validate.get('quizAnswers'))
        quizAnswers = validate.get('quizAnswers', validate.NdbKey()).get()
        answers = quizAnswers.answers
        # TODO: at some point, we need to build a proper lead delivery engine
        if quizAnswers.slug == 'bartlett':
            self.deliverBartlett(quizAnswers)
        elif quizAnswers.slug == 'real':
            self.deliverReal(quizAnswers)
        elif \
                (answers.get('dish-offer') == "Yes")\
                and (answers.get('dish-contact') == "Yes"):
            self.deliverWallamedia(quizAnswers)
        elif \
                (answers.get('solar-interest') == "yes")\
                and (answers.get('monthly-bill') != "0")\
                and (answers.get('roof-shade') != "a lot"):
            self.deliverSolarJoy(quizAnswers)
        return "OK"

    def deliverBartlett(self, quizAnswers):
        key = keyserver.get()['bartlett']['api_key']

        answers = quizAnswers.answers
        user = quizAnswers.user.get()

        customFields = []

        addressRelationship = answers.get('address-relationship')
        if addressRelationship:
            if addressRelationship == 'want-own':
                answer = "Looking to buy"
            elif addressRelationship == 'want-rent':
                answer = "Looking to rent"
            elif addressRelationship == 'own':
                answer = "Own this address"
            elif addressRelationship == 'rent':
                answer = "Rent at this address"
            else:
                answer = None
            customFields.append({
                'custom_field_definition_id': 22, 
                'text_value': answer,
            })

        foundFinancing = answers.get('found-financing')
        if foundFinancing:
            customFields.append({
                'custom_field_definition_id': 32, 
                'text_value': foundFinancing,
            })

        veteran = answers.get('veteran')
        if foundFinancing:
            answer = (veteran == 'yes')
            customFields.append({
                'custom_field_definition_id': 24, 
                'boolean_value': answer,
            })

        lookingAtMoving = answers.get('looking-at-moving')
        if lookingAtMoving:
            if lookingAtMoving == 'within-6-months':
                answer = "Yes, within 6 months"
            elif lookingAtMoving == 'not-sure-when':
                answer = "Yes, but not sure when"
            elif lookingAtMoving == 'no':
                answer = "No"
            else:
                answer = None
            customFields.append({
                'custom_field_definition_id': 25, 
                'text_value': answer,
            })

        interestedSection = answers.get('interested-section')
        if interestedSection:
            if interestedSection == 'property-value':
                answer = "Property Value"
            elif interestedSection == 'crime-stats':
                answer = "Crime Stats"
            elif interestedSection == 'building-details':
                answer = "Building Details"
            elif interestedSection == 'neighborhood-info':
                answer = "Neighborhood Info"
            elif interestedSection == 'neighbors':
                answer = "Who are the neighbors"
            elif interestedSection == 'schools':
                answer = "Schools"
            elif interestedSection == 'air':
                answer = "Air Quality / Pollutants"
            elif interestedSection == 'everything':
                answer = "Everything"
            else:
                answer = None
            customFields.append({
                'custom_field_definition_id': 26, 
                'text_value': answer,
            })

        creditScore = answers.get('credit-score')
        if creditScore:
            customFields.append({
                'custom_field_definition_id': 27, 
                'text_value': creditScore,
            })

        consideringRefinancing = answers.get('considering-refinancing')
        if consideringRefinancing:
            customFields.append({
                'custom_field_definition_id': 33, 
                'text_value': consideringRefinancing,
            })

        currentLoanType = answers.get('current-loan-type')
        if currentLoanType:
            customFields.append({
                'custom_field_definition_id': 29, 
                'text_value': currentLoanType,
            })

        currentLoanTerm = answers.get('current-loan-term')
        if currentLoanTerm:
            customFields.append({
                'custom_field_definition_id': 31, 
                'text_value': currentLoanTerm,
            })

        streetNumber = answers.get('streetNumber')
        if streetNumber:
            answer = "%s %s, %s, %s, %s" % (
                answers.get('streetNumber'),
                answers.get('street'),
                answers.get('city'),
                answers.get('state'),
                answers.get('zip'),
            )
            customFields.append({
                'custom_field_definition_id': 30, 
                'text_value': answer,
            })

        response = urlfetch.fetch(
            url='https://bartlettmortgage.batchbook.com/api/v1/people.json?auth_token=%s' % key,
            payload=json.dumps({
                'person': {
                    'emails': [{
                        'address': user.email, 
                        'label': "main", 
                        'primary': True
                    }], 
                    'cf_records': [{
                        'custom_field_set_id': 5, 
                        'custom_field_values': customFields,
                    }],
                    'tags': [{
                        'name': "lead",
                    }]
                }
            }),
            method='POST',
            headers={
                'Content-Type': "application/json",
            }
        )

    def deliverReal(self, quizAnswers):
        #key = keyserver.get()['real']['api_key']

        answers = quizAnswers.answers
        user = quizAnswers.user.get()

        category = None
        addressRelationship = answers.get('address-relationship')
        if addressRelationship:
            if addressRelationship == 'want-own':
                category = "buy"
            elif addressRelationship == 'want-rent':
                category = "rent"
            elif addressRelationship == 'rent':
                category = "rent"
            else:
                category = None

        address = None
        zipcode = None
        longitude = None
        latitude = None

        try:
            if 'address' in answer:
                address = answer.get('address')
                address = json.loads(address)
                if 'name' in address:
                    address = address['name']
                else:
                    address = None
        except Exception, e:
            pass

        addressSlug = answers.get('addressSlug')
        if addressSlug:
            addressObj = Address.getBySlug(addressSlug)
            if addressObj:
                if not address:
                    address = addressObj.getFullAddress()
                if not zipcode:
                    zipcode = addressObj.addrZip
                location = addressObj[Address.geoField]
                if location:
                    coords = location['coordinates']
                    if coords:
                        longitude = coords[0]
                        latitude = coords[1]

        if not address:
            parts = []
            if user.street:
                parts.append(user.street)
            if user.city:
                parts.append(user.city)
            if user.state:
                parts.append(user.state)
            if user.zipcode:
                parts.append(user.zipcode)
                zipcode = user.zipCode

            if parts:
                address = ", ".join(parts)

        notes = []

        homeInterest = answers.get('home-interest')
        if homeInterest:
            notes.append('owner interest: %s' % homeInterest)

        curiousInterest = answers.get('curious-interest')
        if curiousInterest:
            notes.append('curious interest: %s' % curiousInterest)

        rentingInterest = answers.get('renting-interest')
        if rentingInterest:
            notes.append('renter interest: %s' % rentingInterest)

        timeline = answers.get('timeline')
        if timeline:
            if util.containDigit(timeline):
                notes.append('timeline: %s months' % timeline)
            else:
                notes.append('timeline: %s' % timeline)

        contentInterested = answers.get('interested-section')
        if contentInterested:
            notes.append('content interested: %s' % contentInterested)

        buyingBudget = answers.get('buying-budget')
        if buyingBudget:
            notes.append('buying budget: %s' % buyingBudget)
        
        rentingBudget = answers.get('rental-budget')
        if rentingBudget:
            notes.append('renting budget: %s' % rentingBudget)

        foundFinancing = answers.get('found-financing')
        if foundFinancing:
            notes.append('found financing: %s' % foundFinancing)

        veteran = answers.get('veteran')
        if veteran:
            notes.append('veteran: %s' % veteran)
            
        lookingAtMoving = answers.get('looking-at-moving')
        if lookingAtMoving:
            notes.append('looking at moving: %s' % lookingAtMoving)

        creditScore = answers.get('credit-score')
        if creditScore:
            notes.append('credit score: %s' % creditScore)

        consideringRefinancing = answers.get('considering-refinancing')
        if consideringRefinancing:
            notes.append('consider refinancing: %s' % consideringRefinancing)

        currentLoanType = answers.get('current-loan-type')
        if currentLoanType:
            notes.append('current loan type: %s' % currentLoanType)

        currentLoanTerm = answers.get('current-loan-term')
        if currentLoanTerm:
            notes.append('current loan term: %s' % currentLoanTerm)

        reportUrl = answers.get('reportUrl')
        if reportUrl:
            notes.append('report url: %s' % reportUrl)

        if address:
            notes.append('address: %s' % address)

        if homeInterest == 'sell' or curiousInterest == 'sell':
            category = 'sell'

        if homeInterest == 'buy' or curiousInterest == 'buy':
            category = 'buy'

        notes = '\n'.join(notes)

        source = quizAnswers.source
        reference = quizAnswers.reference

        lead = {
            'lead' : {
                'name': '%s %s' % ( self.getStr(user.firstName), self.getStr(user.lastName) ),
                'phone': self.getStr(user.phone),
                'email': self.getStr(user.email),
                'source': 'OBI',
                'zip': zipcode,
                'notes': notes,
                'latitude': latitude,
                'longitude': longitude,
                'category': category,
                'source' : source,
                'reference' : reference,
            }
        }

        shard = config.CONFIG['EMAIL']['shard']
        url = "http://stg.realapis.com/leads/obi"
        if shard == 'production':
            url = "http://www.realapis.com/leads/obi"

        response = urlfetch.fetch(
            url=url,
            payload=json.dumps(lead),
            method='POST',
            headers={
                'Content-Type': "application/json",
            }
        )
        respObj = json.loads(response.content)

        if respObj.get('error'):
            logging.warning("Lead delivery error for Real:%s" % respObj.get('error'))
            logging.warning(lead)
            
    def deliverWallamedia(self, quizAnswers):
        key = keyserver.get()['WALLAMEDIA_CRM']['KEY']
        answers = quizAnswers.answers
        if quizAnswers.tracker:
            ip = quizAnswers.tracker.get().ipAddress
        else:
            ip = '127.0.0.1'
        params = {
            'key': key,
            'em': answers.get('email'),
            'ph': answers.get('phone'),
            'fullName': answers.get('name'),
            'city': answers.get('city'),
            'state': answers.get('state'),
            'zip': answers.get('zip'),
            'signupDate': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'src': "https://www.addressreport.com/",
            'ip': ip,
        }
        url = "http://api.wallamedia.com/coreg/lead_submit/?%s" % urllib.urlencode(
            params
        )
        response = urlfetch.fetch(
            url=url,
            method='GET',
        )
        logging.info(response.content)
        return "OK"

    def deliverSolarJoy(self, quizAnswers):
        cred = keyserver.get()['SOLARJOY_CRM']
        answers = quizAnswers.answers
        
        if quizAnswers.tracker:
            ip = quizAnswers.tracker.get().ipAddress
        else:
            ip = '127.0.0.1'
        
        name = answers.get('name')
        if name:
            nameParts = name.strip().split(" ", 1)
            if len(nameParts) == 2:
                firstName = nameParts[0]
                lastName = nameParts[1]
            else:
                firstName = nameParts[0]
                lastName = "Unprovided"
        else:
            firstName = "Unprovided"
            lastName = "Unprovided"

        params = {
            'lsid': cred['lsid'],
            'lcid': cred['lcid'],
            'key': cred['key'], 
            'email': answers.get('email'),
            'fname': firstName,
            'lname': lastName,
            'address': "%s %s" % (
                answers.get('streetNumber'),
                answers.get('street'),
            ),
            'city': answers.get('city'),
            'state': answers.get('state'),
            'zip': answers.get('zip'),
            'homephone': answers.get('phone'),
            'monthly_bill': answers.get('monthly-bill'),
            'roof_shade': answers.get('roof-shade'),
            'homeowner': "yes",
            'electricity_provider': answers.get('electricity-provider'),
            'ip': ip,
            'source_url': "https://www.addressreport.com/",
        }
        print params
        url = "https://leads.admediary.com/postlead.php?input_format=querystring&output_format=json"
        response = urlfetch.fetch(
            url=url,
            payload=urllib.urlencode(params),
            method='POST',
        )
        print urllib.urlencode(params)
        logging.info(response.content)
        return "OK"

    def getStr(self, str):
        if str:
            return str
        return ''

from web.mongoAggs import *
class UserDailyAggregation(BaseView):
    #queueName = 'mongoaggs'
    queueName = 'default'

    EMAIL_AGGS = set(('total', 'delivery', 'open', 'click', 'unsub'))
    REPORT_VIEW_AGGS = set( ('reportview',) )
    AGG_TYPES = ['total', 'delivery', 'open', 'click', 'unsub', 'reportview']

    def getDateKey(self, date):
        return util.getYMDStr(date)

    def getMongoPipeline(self, aggType, options):
        cls = None
        if aggType in self.EMAIL_AGGS:
            cls = EmailDailyAggsPipeline
        elif aggType in self.REPORT_VIEW_AGGS:
            cls = ReportViewDailyAggsPipeline

        if cls:
            return cls(**options).getPipelines()
        return None

    def getMongoBulkOperator(self, aggType):
        return UserDailyAggs.getBulkOperator()

    def aggregate(self, aggType, options):
        pipelines = self.getMongoPipeline(aggType, options)

        cls = None
        if aggType in self.EMAIL_AGGS:
            cls = MsgSentAggregate
        elif aggType in self.REPORT_VIEW_AGGS:
            cls = ReportViewsAggregate

        if cls:
            return cls.query(pipelines)
        return None    

    @Route('/background/user-daily-agg/', methods=['GET','POST'])
    def processAggregations(self):
        partnerTags = validate.get('partnerTags', validate.Unpickle())
        startDate = validate.get(
            'startDate', 
            validate.ParseDate('%Y-%m-%d', convertFromEst=False)
        )

        aggTypes = validate.get("aggTypes", validate.Unpickle())
        aggType = aggTypes.pop()
        shard = validate.get("shard")
        user = validate.get("user")
        options = {
            'tags' : partnerTags,
            'aggType' : aggType,
            'dateRange' : {
                'start' : startDate,
                'end' : None,
            },
            'shard' : shard,
            'user' : user,
        }

        aggs = self.aggregate(aggType, options)

        if aggs and len(aggs.result) > 0:
            bulkOp = self.getMongoBulkOperator(aggType)
            for row in aggs.result:
                #print "== row : %s " % row
                data = UserDailyAggs(
                    day=row['day'], 
                    tag=row['tag'], 
                    shard=shard, 
                    dayDate=row['dayDate'],
                    user=user,
                )
                data.set(aggType, row['val'])

                bulkOp.find(
                    {
                        'user': user,
                        'tag': row['tag'],
                        'day': row['day'],
                    }
                )\
                .upsert()\
                .update(
                    {
                        '$set': data.__json__()
                    }
                )

            bulkResult = bulkOp.execute()

        log = ndb.Key(urlsafe=validate.get("logKey")).get()
        log.done = True
        log.put()

        return "OK"

class UserDailyEmailTemplateAggregation(BaseView):
    #queueName = 'mongoaggs'
    queueName = 'default'

    EMAIL_AGGS = set(('total', 'delivery', 'open', 'click', 'unsub'))
    AGG_TYPES = ['total', 'delivery', 'open', 'click', 'unsub']

    def getDateKey(self, date):
        return util.getYMDStr(date)

    def getMongoPipeline(self, aggType, options):
        cls = None
        if aggType in self.EMAIL_AGGS:
            cls = EmailDailyTemplateAggsPipeline
        if cls:
            return cls(**options).getPipelines()
        return None

    def getMongoBulkOperator(self, aggType):
        return UserDailyEmailTemplateAggs.getBulkOperator()

    def aggregate(self, aggType, options):
        pipelines = self.getMongoPipeline(aggType, options)

        cls = None
        if aggType in self.EMAIL_AGGS:
            cls = MsgSentAggregate

        if cls:
            return cls.query(pipelines)
        return None    

    @Route('/background/user-daily-email-template-agg/', methods=['GET','POST'])
    def processAggregations(self):
        partnerTags = validate.get('partnerTags', validate.Unpickle())
        templates = validate.get("templates", validate.Unpickle())
        startDate = validate.get(
            'startDate', 
            validate.ParseDate('%Y-%m-%d', convertFromEst=False)
        )

        aggTypes = validate.get("aggTypes", validate.Unpickle())
        aggType = aggTypes.pop()
        shard = validate.get("shard")
        user = validate.get("user")
        options = {
            'tags' : partnerTags,
            'aggType' : aggType,
            'dateRange' : {
                'start' : startDate,
                'end' : None,
            },
            'shard' : shard,
            'user' : user,
            'templates' : templates,
        }

        aggs = self.aggregate(aggType, options)

        if aggs and len(aggs.result) > 0:
            bulkOp = self.getMongoBulkOperator(aggType)
            for row in aggs.result:
                data = UserDailyEmailTemplateAggs(
                    day=row['day'], 
                    tag=row['tag'], 
                    shard=shard, 
                    dayDate=row['dayDate'],
                    user=user,
                    template=row['template']
                )
                data.set(aggType, row['val'])

                bulkOp.find(
                    {
                        'user': user,
                        'tag': row['tag'],
                        'day': row['day'],
                        'template' : row['template']
                    }
                )\
                .upsert()\
                .update(
                    {
                        '$set': data.__json__()
                    }
                )

            bulkResult = bulkOp.execute()

        log = ndb.Key(urlsafe=validate.get("logKey")).get()
        log.done = True
        log.put()

        return "OK"

class PartnerDailyAggregation(BaseView):
    
    @Route('/background/all-partners-daily-aggs/', methods=['GET', 'POST'])
    def process(self):
        helper = self.getHelper()
        return helper.process()

    @Route('/background/partners-daily-aggs/', methods=['GET','POST'])
    def processPartners(self):
        helper = self.getHelper()
        return helper.processPartners()
    
    def getHelper(self):
        return PartnerDailyAggregationHelper('/background/partners-daily-aggs/')    

class PartnerDailyTemplateAggregation(BaseView):
    
    @Route('/background/all-partners-daily-template-aggs/', methods=['GET', 'POST'])
    def process(self):
        helper = self.getHelper()
        return helper.process()
    
    @Route('/background/partners-daily-template-aggs/', methods=['GET','POST'])
    def processPartners(self):
        helper = self.getHelper()
        return helper.processPartners()

    def getHelper(self):
        return PartnerDailyEmailTemplateAggregationHelper('/background/partners-daily-template-aggs/')

class PartnerDailyAggregationHelper(object):
    queueName = 'mongoaggs'

    EMAIL_AGGS = set(('total', 'delivery', 'open', 'click', 'unsub', 'unopen'))
    REPORT_VIEW_AGGS = set( ('reportview',) )
    USER_COUNT_AGGS = set( ('user', 'subscriber') )
    AGG_TYPES = ['total', 'delivery', 'open', 'click', 'unsub', 'reportview', 'user', 'subscriber', 'unopen']

    TASK_URL = None

    def __init__(self, taskUrl):
        self.TASK_URL = taskUrl

    def process(self):
        shard=config.CONFIG['EMAIL']['shard']
        chunkSize = 1000
        self._internalProcess(chunkSize, None, shard) 
        return "OK"

    def _internalProcess(self, chunkSize, cursor, shard):

        first = False
        if cursor is None:
            first = True

        keys, cursor, more = Partner\
            .query()\
            .filter(Partner.status == 'active')\
            .order(Partner.status, Partner.key)\
            .fetch_page (
                chunkSize,
                start_cursor=cursor,
                keys_only=True,
            ) 

        if keys:
            tags = list("partner:%s" % key.urlsafe() for key in keys)
            if first:
                tags.append("partner:address-report")

            logs = self.getLogs(tags)
            slots = {}
            exists = []
            for log in logs:
                nextDate = util.getYMD(log.nextDate)
                timeKey = self.getDateKey(nextDate)
                exists.append(log.tag)
                slot = slots.setdefault( timeKey, ([], nextDate) )
                slot[0].append(log.tag)

            rests = list(set(tags) - set(exists))

            if rests:
                nextDate = datetime.datetime(2013, 1, 1)
                slots[self.getDateKey(nextDate)] = (rests, nextDate)

            for slot in slots.values():
                self.addTaskQueue(slot[0], slot[1], self.AGG_TYPES, shard)

        if not more:
            return

        self._internalProcess(chunkSize, cursor, shard)

    
    def getDateKey(self, date):
        return util.getYMDStr(date)

    def getUserDrilldownMongoPipelineCls(self, aggType):
        cls = None
        if aggType in self.EMAIL_AGGS:
            cls = UserDrilldownEmailPipeline
        elif aggType in self.REPORT_VIEW_AGGS:
            cls = UserDrilldownReportViewPipeline
        elif aggType in self.USER_COUNT_AGGS:
            cls = UserDrilldownUserCountPipeline
        return cls

    def getMongoPipelineCls(self, aggType):
        cls = None
        if aggType in self.EMAIL_AGGS:
            cls = EmailDailyAggsPipeline
        elif aggType in self.REPORT_VIEW_AGGS:
            cls = ReportViewDailyAggsPipeline
        elif aggType in self.USER_COUNT_AGGS:
            cls = UserCountDailyAggsPipeline
        return cls

    def getMongoPipeline(self, aggType, options):
        cls = self.getMongoPipelineCls(aggType)
        if cls:
            return cls(**options).getPipelines()
        return None

    def getMongoBulkOperator(self, aggType):
        return PartnerDailyAggs.getBulkOperator()

    def buildDataFromResultRow(self, shard, aggType, row):
        data = PartnerDailyAggs(
            day=row['day'], 
            tag=row['tag'], 
            shard=shard, 
            dayDate=row['dayDate']
        )
        data.set(aggType, row['val'])

        return data

    def getFindQueryForBulkUpdate(self, row):
        return  {
                    'tag': row['tag'],
                    'day': row['day'],
                }

    def createLog(self, tag, startDate, nextDate):
        return  PartnerDailyAggsLog.create(
                    tag=tag,
                    prevDate=startDate,
                    nextDate=nextDate,
                )

    def getLogs(self, tags):
        logs = PartnerDailyAggsLog\
                .query()\
                .filter( PartnerDailyAggsLog.tag.IN(tags) )\
                .fetch()
        return logs

    def aggregateCls(self, aggType):
        cls = None
        if aggType in self.EMAIL_AGGS:
            cls = MsgSentAggregate
        elif aggType in self.REPORT_VIEW_AGGS:
            cls = ReportViewsAggregate
        elif aggType in self.USER_COUNT_AGGS:
            cls = UserCountAggregate
        return cls

    def aggregate(self, aggType, options):
        pipelines = self.getMongoPipeline(aggType, options)

        cls = self.aggregateCls(aggType)
        if cls:
            return cls.query(pipelines)
        return None    

    def processPartners(self):
        partnerTags = validate.get('partnerTags', validate.Unpickle())
        startDate = validate.get(
            'startDate', 
            validate.ParseDate('%Y-%m-%d %H:%M:%S', convertFromEst=False)
        )

        endDate = validate.get(
            'endDate', 
            validate.ParseDate('%Y-%m-%d %H:%M:%S', convertFromEst=False)
        )

        aggTypes = validate.get("aggTypes", validate.Unpickle())
        aggType = aggTypes.pop()
        shard = validate.get("shard")
        options = {
            'tags' : partnerTags,
            'aggType' : aggType,
            'dateRange' : {
                'start' : startDate,
                'end' : endDate,
            },
            'shard' : shard,
        }

        aggs = self.aggregate(aggType, options)

        if len(aggs.result) > 0:
            bulkOp = self.getMongoBulkOperator(aggType)
            for row in aggs.result:
                #print "== row : %s " % row
                data = self.buildDataFromResultRow(shard, aggType, row)

                bulkOp.find(
                    self.getFindQueryForBulkUpdate(row)
                )\
                .upsert()\
                .update(
                    {
                        '$set': data.__json__()
                    }
                )

            bulkResult = bulkOp.execute()
            #logging.info("Email daily aggs: [%s] for %s %s" % (aggType, partnerTag, bulkResult))

        if len(aggTypes) > 0:
            self.addTaskQueue(partnerTags, startDate, aggTypes, shard)
        else:
            next = endDate - datetime.timedelta(days=1)
            nextDate = util.getYMD(next)

            logs = []
            for tag in partnerTags:
                log = self.createLog(tag, startDate, nextDate)
                logs.append(log)
            
            ndb.put_multi(logs)

        return "OK"

    def addTaskQueue(self, tags, startDate, aggTypes, shard):
        if not tags:
            return

        # breakDate = datetime.datetime(2016, 1, 1)
        # endDate = min( 
        #     util.getMaxYMD(startDate + datetime.timedelta(days=30)),
        #     util.getMaxYMD(datetime.datetime.now())
        # )
        # if endDate < breakDate:
        #     endDate = util.getMaxYMD(breakDate)

        endDate = util.getMaxYMD(datetime.datetime.now())

        taskqueue.add(
            url=self.TASK_URL,
            params={
                'aggTypes' : pickle.dumps(aggTypes),
                'partnerTags' : pickle.dumps(tags),
                'shard' : shard,
                'startDate' : "%s" % startDate,
                'endDate' : "%s" % endDate,
            },
            queue_name=self.queueName
        )

class PartnerDailyEmailTemplateAggregationHelper(PartnerDailyAggregationHelper):
    queueName = 'mongoaggs'

    EMAIL_AGGS = set(('total', 'delivery', 'open', 'click', 'unopen'))
    AGG_TYPES = ['total', 'delivery', 'open', 'click', 'unopen']

    def getUserDrilldownMongoPipelineCls(self, aggType):
        cls = None
        if aggType in self.EMAIL_AGGS:
            cls = UserDrilldownEmailPipeline
        return cls

    def getMongoPipelineCls(self, aggType):
        cls = None
        if aggType in self.EMAIL_AGGS:
            cls = EmailDailyTemplateAggsPipeline
        return cls

    def getMongoPipeline(self, aggType, options):
        cls = None
        if aggType in self.EMAIL_AGGS:
            cls = EmailDailyTemplateAggsPipeline

        if cls:
            return cls(**options).getPipelines()
        return None

    def getMongoBulkOperator(self, aggType):
        return PartnerDailyEmailTemplateAggs.getBulkOperator()

    def buildDataFromResultRow(self, shard, aggType, row):
        data = PartnerDailyEmailTemplateAggs(
            day=row['day'], 
            tag=row['tag'],
            template=row['template'],
            shard=shard, 
            dayDate=row['dayDate']
        )
        data.set(aggType, row['val'])

        return data

    def getFindQueryForBulkUpdate(self, row):
        return  {
                    'tag': row['tag'],
                    'template': row['template'],
                    'day': row['day'],
                }

    def createLog(self, tag, startDate, nextDate):
        return  PartnerDailyEmailTemplateAggsLog.create(
                    tag=tag,
                    prevDate=startDate,
                    nextDate=nextDate,
                )

    def getLogs(self, tags):
        cls = PartnerDailyEmailTemplateAggsLog
        logs = cls\
                .query()\
                .filter( cls.tag.IN(tags) )\
                .fetch()
        return logs

    def aggregateCls(self, aggType):
        cls = None
        if aggType in self.EMAIL_AGGS:
            cls = MsgSentAggregate
        return cls

    def aggregate(self, aggType, options):
        pipelines = self.getMongoPipeline(aggType, options)
        cls = self.aggregateCls(aggType)
        if cls:
            return cls.query(pipelines)
        return None

class GenerateSitemaps(BaseView):

    @Route('/background/generate-sitemaps/', methods=['GET', 'POST'])
    def process(self):
        sitemap = Sitemap()
        sitemap.put()

        taskqueue.add(
            url='/background/generate-sitemaps-properties/',
            params={
                'sitemap': pickle.dumps(sitemap),
            },
            queue_name='default',
        )

        taskqueue.add(
            url='/background/generate-sitemaps-areas/',
            params={
                'sitemap': pickle.dumps(sitemap),
            },
            queue_name='default',
        )

        taskqueue.add(
            url='/background/generate-sitemaps-cities/',
            params={
                'sitemap': pickle.dumps(sitemap),
            },
            queue_name='default',
        )

        return "OK"

    @Route('/background/generate-sitemaps-properties/', methods=['GET', 'POST'])
    def processProperties(self):
        sitemap = validate.get('sitemap', validate.Unpickle())
        cursor = validate.get('cursor', validate.Unpickle())

        query = Property.query().order(-Property.rank)

        results, cursor, more = query.fetch_page(
            2000,
            start_cursor=cursor,
        )

        self._writeUrls(sitemap, (
            str(property.getUrl()) 
            for property 
            in results
        ))

        if more:
            taskqueue.add(
                url='/background/generate-sitemaps-properties/',
                params={
                    'sitemap': pickle.dumps(sitemap),
                    'cursor': pickle.dumps(cursor),
                },
                queue_name='default',
            )

        return "OK"

    @Route('/background/generate-sitemaps-areas/', methods=['GET', 'POST'])
    def processAreas(self):
        return self._processMongo(
            Area, 
            '/background/generate-sitemaps-areas/',
        )

    @Route('/background/generate-sitemaps-cities/', methods=['GET', 'POST'])
    def processCities(self):
        return self._processMongo(
            City, 
            '/background/generate-sitemaps-cities/',
        )

    def _processMongo(self, mongoCls, taskUrl):
        sitemap = validate.get('sitemap', validate.Unpickle())
        lastId = validate.get('lastId', validate.Unpickle())

        if lastId is None:
            query = {}
        else:
            query = {'_id': {'$gt': lastId}}

        results = mongoCls.query(query, 
            fields={'slug': 1, 'city': 1}, 
            sort=[('_id', 1)], 
            limit=2000,
        )
        lastId = None
        urls = []
        for result in results:
            lastId = result['_id']
            url = result.getUrl()
            urls.append(url)

        self._writeUrls(sitemap, urls)

        if lastId is not None:
            taskqueue.add(
                url=taskUrl,
                params={
                    'sitemap': pickle.dumps(sitemap),
                    'lastId': pickle.dumps(lastId),
                },
                queue_name='default',
            )

        return "OK"

    def _writeUrls(self, sitemap, urls):

        filepath = "/rentenna-sitemaps/%s" % str(uuid.uuid4())
        with gcs.open(filepath, 'w') as f:
            for url in urls:
                print >> f, str(url)

        SitemapPage(
            sitemap=sitemap.key,
            gcsPath=filepath,
        ).put()

class InvokeForAllMongo(BaseView):

    @classmethod
    def invoke(
            cls, 
            collection, 
            task, 
            queue, 
            query=None,
            payload=None, 
            sampleProportion=1.0,
            lastId=None,
        ):
        if query is None:
            query = {}
        if payload is None:
            payload = {}
        taskqueue.add(
            url='/background/invoke-for-all-mongo/',
            params={
                'collection': collection,
                'query': pickle.dumps(query),
                'payload': pickle.dumps(payload),
                'sampleProportion': sampleProportion,
                'task': task,
                'queue': queue,
                'lastId': pickle.dumps(lastId)
            },
            queue_name=queue,
        )

    @Route('/background/invoke-for-all-mongo/', methods=['POST'])
    def process(self):
        collection = validate.get('collection')
        payload = validate.get('payload', validate.Unpickle())
        query = validate.get('query', validate.Unpickle())
        sampleProportion = validate.get('sampleProportion', validate.ParseFloat())
        lastId = validate.get('lastId', validate.Unpickle())
        task = validate.get('task')
        queue = validate.get('queue')

        mongoQuery = dict(query)
        if lastId:
            logging.info(lastId)
            mongoQuery['_id'] = {'$gt': lastId}

        ids = []
        lastId = None
        mongo = MongoModel.getMongo()
        for doc in getattr(mongo, collection)\
                .find(mongoQuery, {'_id': 1})\
                .sort('_id')\
                .limit(1000):
            lastId = doc['_id']
            if random.random() <= sampleProportion:
                ids.append(doc['_id'])

        if lastId is not None:
            taskqueue.add(
                url='/background/invoke-for-all-mongo/',
                params={
                    'collection': collection,
                    'payload': pickle.dumps(payload),
                    'query': pickle.dumps(query),
                    'sampleProportion': sampleProportion,
                    'lastId': pickle.dumps(lastId),
                    'task': task,
                    'queue': queue,
                },
                queue_name=queue,
            )
        else:
            logging.info('no more!')

        for id in ids:
            params = {'id': pickle.dumps(id)}
            params.update(payload)
            taskqueue.add(
                url=task,
                params=params,
                queue_name=queue,
            )

        logging.info("Total disbursed: %s" % len(ids))
            
        return "OK"

class MergeAlternateAddresses(BaseView):

    @Route('/background/merge-alternate-addresses/', methods=['GET', 'POST'])
    def process(self):
        bin = flask.request.values.get('bin')
        buildingInfo = NycBiswebBuilding.queryFirst({'bin': bin})

        alts = []
        for alt in buildingInfo.get('altAddresses', []):
            low = alt['low'].split("-")
            high = alt['high'].split("-")

            try:
                lowNumber = int(low[-1].split(" ")[0])
                highNumber = int(high[-1].split(" ")[0])

                street = alt['street']
                for number in range(lowNumber, highNumber + 1, 2):
                    streetNumber = "-".join(low[:-1] + [str(number)])
                    alts.append((streetNumber, street))

            except Exception as e:
                print e
                pass

        city = buildingInfo.get('boro', 'New York')
        if city == 'Manhattan' or not city:
            city = 'New York'
        zip = buildingInfo.get('zip')

        binRecord = NycDobBin.queryFirst({'dobBin': bin})

        if binRecord and zip:
            addresses = set()
            caddrs = set()
            for alt in alts:
                address = geocoder.getAddress({
                    'streetNumber': alt[0],
                    'street': alt[1],
                    'city': city,
                    'state': 'NY',
                    'zip': zip,
                })
                if address:
                    logging.info("found %s" % address['addr'])
                    addresses.add(address['addr'])
                    caddrs.add(address['caddr'])

            if addresses:
                addressBulkOp = Address.getBulkOperator()
                for address in addresses:
                    addressBulkOp.find(
                        {'addr': address}
                    ).update(
                        {'$set': {
                            'caddr': binRecord['caddr'],
                            'isPreferred': False,
                        }},
                    )
                logging.info(addressBulkOp.execute())

                caddrBulkOp = CanonicalAddrs.getBulkOperator() 
                for address in addresses:
                    caddrBulkOp.find(
                        {'_id': binRecord['caddr']}
                    ).update(
                        {'$addToSet': {'alt': address}}
                    )

                if binRecord['caddr'] in caddrs:
                    caddrs.remove(binRecord['caddr'])
                if caddrs:
                    for caddr in caddrs:
                        caddrBulkOp.find(
                            {'_id': caddr}
                        ).update(
                            {
                                '$set': {'deprecated': True},
                            }
                        )
                logging.info(caddrBulkOp.execute())

        return "OK"

class Nyc311ComplaintUpdater(BaseView):

    @Route('/background/update-311/', methods=['POST', 'GET'])
    def update311(self):
        pages = 1000 # at 100 per page, that's the most recent 100,000 calls
        for page in range(0, pages):
            taskqueue.add(
                url='/background/update-311/chunk/',
                params={
                    'page': page,
                },
                queue_name='crawl',
                countdown=page * 5,
            )
        return "OK"

    @Route('/background/update-311/chunk/', methods=['POST','GET'])
    def update311Chunk(self):
        page = int(flask.request.values.get('page'))
        calls = list(self._getCalls(page))
        if calls:
            bulkOp = Nyc311CallModel.getBulkOperator()
            for data in calls:
                bulkOp.find(
                    {'unique_key': data['unique_key']}
                ).upsert().update(
                    {'$set': data}
                )
            logging.info(bulkOp.execute())
        return "OK"

    def _getCalls(self, page):
        # abstracting these ODATA accesses would be a good idea
        root = CrawlResponse(
            "http://data.cityofnewyork.us/OData.svc/erm2-nwe9",
            params={
                '$orderby': "created_date desc",
                '$top': 100,
                '$skip': 100 * page,
            }
        ).selector
        dateValidator = validate.ParseDate('%Y-%m-%dT%H:%M:%S')
        for sel in root.select('//entry'):
            data = {
                'unique_key': sel.first('.//unique_key/text()'),
                'created_date': sel.first('.//created_date/text()', dateValidator),
                'closed_date': sel.first('.//closed_date/text()', dateValidator),
                'due_date': sel.first('.//due_date/text()', dateValidator),
                'resolution_action_updated_date': sel.first(
                    './/resolution_action_updated_date/text()', dateValidator),
                'agency': sel.first('.//agency/text()'),
                'complaint_type': sel.first('.//complaint_type/text()'),
                'descriptor': sel.first('.//descriptor/text()'),
                'incident_address': sel.first('.//incident_address/text()'),
                'incident_zip': sel.first('.//incident_zip/text()'),
                'city': sel.first('.//city/text()'),
                'cross_street_1': sel.first('.//cross_street_1/text()'),
                'cross_street_2': sel.first('.//cross_street_2/text()'),
                'address_type': sel.first('.//address_type/text()'),
                'location_type': sel.first('.//location_type/text()'),
                'street_name': sel.first('.//street_name/text()'),
                'status': sel.first('.//status/text()'),
                'park_facility_name': sel.first('.//park_facility_name/text()'),
                'school_name': sel.first('.//school_name/text()'),
                'vehicle_type': sel.first('.//vehicle_type/text()'),
                'taxi_pick_up_location': sel.first('.//taxi_pick_up_location/text()'),
            }
            latitude = sel.first('.//latitude/text()')
            longitude = sel.first('.//longitude/text()')
            if latitude and longitude:
                data['location'] = {
                    'type': "Point",
                    'coordinates': [float(longitude), float(latitude)],
                }
            yield data

class NycDobJobUpdater(BaseView):

    filenameTemplates = [
        "job%02d%02dexcel.zip",
        "per%02d%02dexcel.zip",
    ]

    @Route('/background/nyc-dob-job-update/', methods=['POST', 'GET'])
    def process(self):
        for filenameTemplate in self.filenameTemplates:
            now = datetime.datetime.now()
            month = datetime.datetime(2014, 7, 1)
            while month < now:
                filename = filenameTemplate % (
                    month.month, 
                    month.year-2000 # TODO: fix in y2.1k
                )
                existing = CrawlLog.query()\
                    .filter(CrawlLog.crawler == 'NycDobJobUpdater/process')\
                    .filter(CrawlLog.target == filename)\
                    .get()
                if existing is None:
                    logging.info("disbursing %s" % filename)
                    taskqueue.add(
                        url='/background/nyc-dob-job-update/run/',
                        params={
                            'file': filename,
                        },
                        queue_name='crawl',
                    )
                month += relativedelta(months=1)
        return "OK"

    @Route('/background/nyc-dob-job-update/run/', methods=['POST', 'GET'])
    def processFile(self):
        filename = flask.request.values.get('file')
        #url = "http://www.nyc.gov/html/dob/downloads/download/foil/%s" % filename
        url = "http://www1.nyc.gov/assets/buildings/foil/%s" % filename
        response = urlfetch.fetch(url)
        logging.info(url)
        logging.info(response.status_code)
        if response.status_code == 200:
            zf = zipfile.ZipFile(StringIO(response.content))
            ef = zf.open(zf.namelist()[0])
            workbook = xlrd.open_workbook(file_contents=ef.read())
            worksheets = workbook.sheet_names()
            worksheet = workbook.sheet_by_name(worksheets[0])
            header = [util.keyify(x.value) for x in worksheet.row(2)]
            count = 0
            for chunk in util.chunkIterator(self._readFile(worksheet), 10):
                count += len(chunk)
                taskqueue.add(
                    url='/background/nyc-dob-job-update/chunk/',
                    params={
                        'header': pickle.dumps(header),
                        'chunk': pickle.dumps(chunk),
                    },
                    queue_name='crawl',
                )
            logging.info(count)
            CrawlLog(
                crawler='NycDobJobUpdater/process',
                target=filename,
                count=count,
            ).put()

            # if filename.startswith('per'):
            #     type = "permits"
            # else:
            #     type = "jobs"
            # month = int(filename[3:5])
            # year = 2000 + int(filename[5:7])
            # rapi.webPutHealthStat(
            #     'PeriodicActivityStatus',
            #     'AddressReport:nyc-dob-%s' % type,
            #     {
            #         'month': month,
            #         'year': year,
            #         'status': "OK",
            #         'count': count,
            #     }
            # )
        return "OK"

    @Route('/background/nyc-dob-job-update/chunk/', methods=['POST', 'GET'])
    def processChunk(self):
        header = validate.get('header', validate.Unpickle())
        chunk = validate.get('chunk', validate.Unpickle())
        if chunk:
            bulkOp = NycDobJob.getBulkOperator()
            for row in chunk:
                data = dict(zip(header, row))
                matched = self._matchDoc(data)
                if not matched:
                    self._geocodeDoc(data)
                if '' in data:
                    del data['']
                bulkOp.find(
                    {'Job': data['Job']}
                ).upsert().update(
                    {'$set': data}
                )
            logging.info(bulkOp.execute())
        return "OK"

    def _geocodeDoc(self, data):
        cityStateZip = (data.get('CityStateZip') or '').strip().rsplit(" ", 2)
        if data['House']\
                and data['StreetName']\
                and isinstance(data['StreetName'], basestring)\
                and isinstance(data['House'], basestring)\
                and len(cityStateZip) == 3:
            streetNumber = data['House'].strip()
            streetName = data['StreetName'].strip()
            city = cityStateZip[0]
            state = cityStateZip[1]
            zipCode = cityStateZip[2]
            address = geocoder.getAddress({
                'streetNumber': streetNumber,
                'street': streetName,
                'city': city,
                'state': state,
                'zip': zipCode,
            })
            if address:
                data['addr'] = address['addr']
                data['caddr'] = address['caddr']
                data['location'] = address['location']
                return True
        return False

    def _matchDoc(self, data):
        mongo = MongoModel.getMongo()
        # matchBin= mongo.nycDobBins.find_one({'dobBin': data['Bin']})
        matchBin = NycDobBin.getByBin(data['Bin'])
        if matchBin:
            # address = mongo.addresses.find_one({'addr': matchBin['addr']})
            address = Address.getByAddr(matchBin['addr'])
            if address:
                data['addr'] = address['addr']
                data['caddr'] = address['caddr']
                data['location'] = address['location']
                return True
            #logging.info('matched bin, but did not get address with %s' % matchBin['addr'])
        return False

    def _readCell(self, cell):
        if cell.ctype == 0:
            return None
        elif cell.ctype == 1:
            return cell.value
        elif cell.ctype == 2:
            return str(int(cell.value))
        elif cell.ctype == 3:
            return datetime.datetime(1900, 1, 1) + datetime.timedelta(days=cell.value)

    def _readFile(self, worksheet):
        for i in range(3, worksheet.nrows):
            yield [self._readCell(x) for x in worksheet.row(i)]

class NycHpdDataUpdater(BaseView):

    dateValidator = validate.ParseDate('%Y-%m-%dT%H:%M:%S') # maybe that should be a standard

    BORO_MAP = {
        "QUEENS": "Queens",
        "BROOKLYN": "Brooklyn",
        "BRONX": "Bronx",
        "STATEN ISLAND": "Staten Island",
        "STATEN": "Staten Island",
    }

    targets = {
        'Buildings': {
            'collection': "nycHpdBuildings",
            'handler': "_processBuilding",
            'keyField': "BuildingID",
            'startTag': """<Building xmlns:i="http://www.w3.org/2001/XMLSchema-instance">""",
            'endTag': """</Building>""",
        },
        'Complaints': {
            'collection': "nycHpdComplaints",
            'handler': "_processComplaint",
            'keyField': "ComplaintID",
            'startTag': """<Complaint xmlns:i="http://www.w3.org/2001/XMLSchema-instance">""",
            'endTag': """</Complaint>""",
        },
        'Violations': {
            'collection': "nycHpdViolations",
            'handler': "_processViolation",
            'keyField': "ViolationID",
            'startTag': """<Violation xmlns:i="http://www.w3.org/2001/XMLSchema-instance">""",
            'endTag': """</Violation>""",
        },
        'Registrations': {
            'collection': "nycHpdRegistrations",
            'handler': "_processRegistration",
            'keyField': "RegistrationID",
            'startTag': """<Registration xmlns:i="http://www.w3.org/2001/XMLSchema-instance">""",
            'endTag': """</Registration>""",
        }
    }

    @Route('/background/nyc-hpd-data-update/', methods=['POST', 'GET'])
    def process(self):
        for name, target in self.targets.items():
            date = datetime.datetime(2014,1,1)
            while True:
                filename = "%s%s.zip" % (name, date.strftime('%Y%m%d'))
                if filename == 'Violations20150301.zip':
                    filename = 'Violation20150301.zip' # some naming variation from hpd site
                # choose the oldest one we have not crawled yet
                existing = CrawlLog.query()\
                    .filter(CrawlLog.crawler == 'NycHpdDataUpdater/process:1')\
                    .filter(CrawlLog.target == filename)\
                    .get()
                date = rtime.incrementMonth(date, 1)
                if existing is None:
                    logging.info("disbursing %s" % filename)
                    taskqueue.add(
                        url='/background/nyc-hpd-data-update/run/',
                        params={
                            'name': name,
                            'file': filename,
                        },
                        queue_name='crawl',
                    )
                    break
        return "OK"

    @Route('/background/nyc-hpd-data-update/run/', methods=['POST', 'GET'])
    def processFile(self):
        name = flask.request.values.get('name')
        filename = flask.request.values.get('file')
        targetUrl = "http://www1.nyc.gov/assets/hpd/downloads/misc/%s" % filename
        gcsName = "/rentenna-data/%s" % filename

        target = self.targets[name]
        startTag = target['startTag']
        endTag = target['endTag']
        
        logging.info(targetUrl)

        util.sideloadToCloudstorage(targetUrl, gcsName)

        with util.openFromCloudstorage(gcsName) as gcsFile:
            xmlFile = self._getXmlFromZip(gcsFile)
            segmentInfo = util.segmentFile(xmlFile, startTag, endTag, 100)
            for segment in segmentInfo['segments']:
                taskqueue.add(
                    url='/background/nyc-hpd-data-update/run-segment/',
                    params={
                        'name': name,
                        'file': filename,
                        'startRange': segment[0],
                        'endRange': segment[1],
                    },
                    queue_name='crawl',
                )
            CrawlLog(
                crawler='NycHpdDataUpdater/process:1',
                target=filename,
                count=segmentInfo['count'],
            ).put()
            
            date = re.sub(r'[^0-9]', '', filename)
            type = re.sub(r'[0-9]', '', filename).split(".")[0]
            year = int(date[0:4])
            month = int(date[4:6])

        return "OK"

    @Route('/background/nyc-hpd-data-update/run-segment/', methods=['POST', 'GET'])
    def processFileSegment(self):
        name = flask.request.values.get('name')
        filename = flask.request.values.get('file')
        startRange = flask.request.values.get('startRange')
        endRange = flask.request.values.get('endRange')
        gcsName = "/rentenna-data/%s" % filename

        target = self.targets[name]
        startTag = target['startTag']
        endTag = target['endTag']

        range = (int(startRange), int(endRange))
        logging.info(range)
        processor = getattr(self, target['handler'])
        
        def upsertGenerator():
            with util.openFromCloudstorage(gcsName) as gcsFile:
                xmlFile = self._getXmlFromZip(gcsFile)
                for xmlChunk in util.chunkFile(xmlFile, startTag, endTag, range=range):
                    try:
                        doc = processor(xmlChunk)
                        upsert = (
                            {target['keyField']: doc[target['keyField']]},
                            {'$set': doc}
                        )
                        yield upsert
                    except Exception as e:
                        print e

        count = 0
        for upserts in util.chunkIterator(upsertGenerator(), 10):
            if upserts:
                count += len(upserts)
                mongo = MongoModel.getMongo()
                collection = getattr(mongo, target['collection'])
                bulkOp = collection.initialize_unordered_bulk_op()
                for search, update in upserts:
                    bulkOp.find(search).upsert().update(update)
                logging.info(bulkOp.execute())

        return "OK"

    def _getXmlFromZip(self, gcsFile):
        zipFile = ZipFile(gcsFile)
        for subfile in zipFile.filelist:
            if subfile.filename.endswith(".xml"):
                return zipFile.open(subfile.filename, 'r')

    def _processBuilding(self, chunk):
        sel = CrawlSelector(xml=chunk)
        data = {
            'BuildingID': sel.first('./BuildingID/text()'),
            'Boro': sel.first('./Boro/ShortName/text()'),
            'HouseNumber': sel.first('./HouseNumber/text()'),
            'LowHouseNumber': sel.first('./LowHouseNumber/text()'),
            'HighHouseNumber': sel.first('./HighHouseNumber/text()'),
            'StreetName': sel.first('./StreetName/text()'),
            'Zip': sel.first('./Zip/text()'),
            'Block': sel.first('./Block/text()'),
            'Lot': sel.first('./Lot/text()'),
            'BIN': sel.first('./BIN/text()'),
            'CommunityBoard': sel.first('./CommunityBoard/text()'),
            'CensusTract': sel.first('./CensusTract/text()'),
            'ManagementProgram': sel.first('./ManagementProgram/text()'),
            'DoBBuildingClass': sel.first('./DoBBuildingClass/LongName/text()'),
            'LegalStories': sel.first('./LegalStories/text()'),
            'LegalClassA': sel.first('./LegalClassA/text()'),
            'LegalClassB': sel.first('./LegalClassB/text()'),
            'RegistrationID': sel.first('./RegistrationID/text()'),
            'LifeCycle': sel.first('./LifeCycle/text()'),
            'RecordStatus': sel.first('./RecordStatus/ShortName/text()'),
        }
        address = geocoder.getAddress({
            'streetNumber': data['HouseNumber'],  
            'street': data['StreetName'], 
            'city': self.BORO_MAP.get(data['Boro'], 'New York'), 
            'state': 'NY', 
            'zip': data['Zip'],
        })
        if address:
            data['geo'] = address['location']
        return data

    def _processComplaint(self, chunk):
        sel = CrawlSelector(xml=chunk)
        data = {
            'ComplaintID': sel.first('./ComplaintID/text()'),
            'BuildingID': sel.first('./BuildingID/text()'),
            'Boro': sel.first('./Borough/ShortName/text()'),
            'HouseNumber': sel.first('./HouseNumber/text()'),
            'StreetName': sel.first('./StreetName/text()'),
            'Zip': sel.first('./Zip/text()'),
            'Apartment': sel.first('./Apartment/text()'),
            'ReceivedDate': sel.first('./ReceivedDate/text()', self.dateValidator),
            'ReferenceNumber': sel.first('./ReferenceNumber/text()'),
            'Status': sel.first('./Status/ShortName/text()'),
            'StatusDate': sel.first('./StatusDate/text()', self.dateValidator),
            'Problems': [],
        }
        for problem in sel.select('./Problems/Problem'):
            data['Problems'].append({
                'ProblemID': problem.first('./ProblemID/text()'),    
                'SpaceType': problem.first('./SpaceType/ShortName/text()'),
                'Type': problem.first('./Type/ShortName/text()'),
                'MajorCategory': problem.first('./MajorCategory/ShortName/text()'),
                'MinorCategory': problem.first('./MinorCategory/ShortName/text()'),
                'Code': problem.first('./Code/ShortName/text()'),
                'Status': problem.first('./Status/ShortName/text()'),
                'StatusDate': problem.first('./StatusDate/text()', self.dateValidator),
            })
        return data

    def _processRegistration(self, chunk):
        sel = CrawlSelector(xml=chunk)
        data = {
            'RegistrationID': sel.first('./RegistrationID/text()'),
            'BuildingID': sel.first('./BuildingID/text()'),
            'Boro': sel.first('./Boro/ShortName/text()'),
            'HouseNumber': sel.first('./HouseNumber/text()'),
            'LowHouseNumber': sel.first('./LowHouseNumber/text()'),
            'HighHouseNumber': sel.first('./HighHouseNumber/text()'),
            'StreetName': sel.first('./StreetName/text()'),
            'StreetCode': sel.first('./StreetCode/text()'),
            'Zip': sel.first('./Zip/text()'),
            'BIN': sel.first('./BIN/text()'),
            'LastRegistrationDate': sel.first('./LastRegistrationDate/text()', self.dateValidator),
            'RegistrationEndDate': sel.first('./RegistrationEndDate/text()', self.dateValidator),
            'Contacts': [],
        }
        for contact in sel.select('./Contacts/RegistrationContact'):
            data['Contacts'].append({
                'RegistrationContactID': contact.first('./RegistrationContactID/text()'),
                'Type': contact.first('./Type/text()'),
                'ContactDescription': contact.first('./ContactDescription/text()'),
                'CorporationName': contact.first('./CorporationName/text()'),
                'Title': contact.first('./Title/text()'),
                'FirstName': contact.first('./FirstName/text()'),
                'MiddleInitial': contact.first('./MiddleInitial/text()'),
                'LastName': contact.first('./LastName/text()'),
                'BusinessHouseNumber': contact.first('./BusinessHouseNumber/text()'),
                'BusinessStreetName': contact.first('./BusinessStreetName/text()'),
                'BusinessApartment': contact.first('./BusinessApartment/text()'),
                'BusinessCity': contact.first('./BusinessCity/text()'),
                'BusinessState': contact.first('./BusinessState/text()'),
                'BusinessZip': contact.first('./BusinessZip/text()'),
            })
        return data

    def _processViolation(self, chunk):
        sel = CrawlSelector(xml=chunk)
        data = {
            'ViolationID': sel.first('./ViolationID/text()'),
            'BuildingID': sel.first('./BuildingID/text()'),
            'RegistrationID': sel.first('./RegistrationID/text()'),
            'Boro': sel.first('./Boro/ShortName/text()'),
            'HouseNumber': sel.first('./HouseNumber/text()'),
            'LowHouseNumber': sel.first('./LowHouseNumber/text()'),
            'HighHouseNumber': sel.first('./HighHouseNumber/text()'),
            'StreetName': sel.first('./StreetName/text()'),
            'StreetCode': sel.first('./StreetCode/text()'),
            'Zip': sel.first('./Zip/text()'),
            'Class': sel.first('./Class/text()'),
            'InspectionDate': sel.first('./InspectionDate/text()', self.dateValidator),
            'OriginalCertifyByDate': sel.first('./OriginalCertifyByDate/text()', self.dateValidator),
            'OriginalCorrectByDate': sel.first('./OriginalCorrectByDate/text()', self.dateValidator),
            'NewCertifyByDate': sel.first('./NewCertifyByDate/text()', self.dateValidator),
            'NewCorrectByDate': sel.first('./NewCorrectByDate/text()', self.dateValidator),
            'CertifiedDate': sel.first('./CertifiedDate/text()', self.dateValidator),
            'OrderNumber': sel.first('./OrderNumber/text()'),
            'NOVID': sel.first('./NOVID/text()'),
            'NOVDescription': sel.first('./NOVDescription/text()'),
            'NOVIssuedDate': sel.first('./NOVIssuedDate/text()', self.dateValidator),
            'CurrentStatus': sel.first('./CurrentStatus/ShortName/text()'),
            'CurrentStatusDate': sel.first('./CurrentStatusDate/text()', self.dateValidator),
        }
        return data

class NypdCrimeUpdater(BaseView):

    @Route('/background/update-crime/nypd/', methods=['POST', 'GET'])
    def update(self):
        table = "02378420399528461352-17772055697785505571"
        # table = "02378420399528461352-17234028967417318364" # 2014
        endpoint = "https://www.googleapis.com/mapsengine/v1/tables/%s/features" % table
        
        params = {
            'key': keyserver.get()['google']['server_key'],
            'version': "published",
            'maxResults': 1000,
        }
        
        pageToken = flask.request.values.get('pageToken')
        if pageToken:
            params['pageToken'] = pageToken

        url = "%s?%s" % (endpoint, urllib.urlencode(params))
        page = urlfetch.fetch(url)
        data = json.loads(page.content)
        features = data.get('features')
        
        for upserts in util.chunkIterator(self.getUpserts(features)):
            if upserts:
                bulkOp = NypdCrimeMongoModel.getBulkOperator()
                for search, update in upserts:
                    bulkOp.find(search).upsert().update(update)
                logging.info(bulkOp.execute())

        nextPageToken = data.get('nextPageToken')
        if nextPageToken:
            logging.info(nextPageToken)
            taskqueue.add(
                url='/background/update-crime/nypd/',
                params={
                    'pageToken': nextPageToken,
                },
                queue_name='crawl',
                countdown=1, # rate limiting
            )
        return "OK"

    def getUpserts(self, features):
        for feature in features:
            geo = feature['geometry']
            crime = feature['properties']['CR']
            count = feature['properties']['TOT']
            month = int(feature['properties']['MO'])
            year = int(feature['properties']['YR'])
            date = datetime.datetime(year, month, 15)
            gxId = "%s_%s_%s_%s_%s" % (
                feature['properties']['CR'],
                feature['properties']['X'],
                feature['properties']['Y'],
                feature['properties']['MO'],
                feature['properties']['YR'],
            )
            yield (
                {
                    'year': year,
                    'month': month,
                    'gxId': gxId,
                },
                {
                    '$set': {
                        'year': year,   
                        'month': month,
                        'gxId': gxId,
                        'geo': geo,
                        'crime': crime,
                        'count': count,
                        'date': date,
                    }
                },
            )

class PropertyCacheWarmer(BaseView):
    """
        Computes stats for a particular property

        TODO: rename for property-specificity
    """

    @Route('/background/warm-property-cache/', methods=['GET', 'POST'])
    def start(self):
        query = Property.query()
        start = validate.get('start')
        if start:
            query = query.filter(Property.key > ndb.Key(Property, start))
        InvokeForAllNdb.invoke(
            query=query,
            queue='cache-warmer',
            task='/background/warm-property-cache/compute-stats/',
        )
        return "OK"

    @Route('/background/warm-property-cache/compute-stats/', methods=['GET', 'POST'])
    def computeStats(self):
        requestedReporter = validate.get('reporter')
        
        slug = validate.get('slug')
        if slug:
            address = Address.getBySlug(slug)
            if not address:
                address = geocoder.getAddressBySlugWorkaround(slug)
            propertyKey = ndb.Key(Property, address['slug'])
        else:
            propertyKey = validate.get('key', validate.NdbKey())
            address = Address.getBySlug(propertyKey.id())
            if not address:
                address = geocoder.getAddressBySlugWorkaround(propertyKey.id())
        
        property = Property.get(propertyKey, address=address)
        if property:
            (reportersToRun, stats, completedReporters) = getReport(
                address['city'],
                address['addrState'],
                propertyKey,
                address,
                'property',
                forceRecompute=True,
                precompute=True,
            )
            for reporter in reportersToRun:
                reporterName = reporter.__name__
                if (not requestedReporter) or (reporterName == requestedReporter):
                    logging.info("%s - %s" % (address['slug'], reporterName))
                    try:
                        runReporter(
                            address,
                            address['city'],
                            propertyKey,
                            'property',
                            reporterName,
                        )
                    except Exception as e:
                        print e
        return "OK"

class PropertyIndexer(BaseView):

    @Route('/background/index-properties/')
    def process(self):
        query = Property.query()
        InvokeForAllNdb.invoke(
            query, 
            'default',
            task='/background/index-properties/run/', 
        )
        return "OK"

    @Route('/background/index-properties/run/', methods=['POST'])
    def processForArea(self):
        propertyKey = ndb.Key(urlsafe=validate.get('key'))
        property = propertyKey.get()
        address = property.getAddress()
        if property and address:
            report = Report(
                'property',
                address.getCity(),
                propertyKey,
                address,
                forceRecompute=False,
                isPrecompute=False,
                doMinimal=False,
            )
            stats = report.getStats()
            lists = []
            lists += self._indexAreas(property, address)
            lists += self._indexZip(property, address)
            print lists
            property.lists = lists
            property.rank = self._computeRank(property, stats)
            property.put()
        return "OK"

    def _computeRank(self, property, reportStats):
        # TODO: this is a really dumb ranking algorithm
        if 'buildingType' in reportStats:
            type = reportStats['buildingType']
            if type == 'Elevator':
                maxRank = 100
            elif type == 'Walk-Up':
                maxRank = 90
            elif type in ['Loft', 'Condo', 'Multi-Use']:
                maxRank = 80
            elif type in ['Two-Family', 'Single-Family']:
                maxRank = 70
            else:
                maxRank = 50
        else:
            maxRank = 50

        return random.random() * maxRank

    def _indexAreas(self, property, address):
        return [
            'area:%s' % area
            for area
            in address['areas']
        ]

    def _indexZip(self, property, address):
        return [
            'zip:%s' % address.addrZip
        ]

class RegionReportBuilding(BaseView):
    """
        Computes stats for all regions
    """

    @Route('/background/compute-<region>-reports/', methods=['GET', 'POST'])
    def start(self, region):
        if region == 'neighborhood':
            collection = 'obiBoundariesNh3_2'
        elif region == 'zipcode':
            collection = 'obiBoundariesZip3_2'

        InvokeForAllMongo.invoke(
            collection=collection,
            task='/background/compute-single-%s-report/' % region,
            queue='default',
        )

        return "OK"

    @Route('/background/compute-single-<region>-report/', methods=['GET', 'POST'])
    def computeStats(self, region):
        id = validate.get('id', validate.Unpickle())
        slug = validate.get('slug')

        if region == 'neighborhood':
            if id:
                area = Area.queryFirst({"_id": id})
            else:
                area = Area.queryFirst({"slug": slug})
            areaSlug = area.slug
            areaKey = ndb.Key('Area', areaSlug)
        elif region == 'zipcode':
            if id:
                area = ZipcodeArea.queryFirst({"_id": id})
            else:
                area = ZipcodeArea.queryFirst({"slug": slug})
            areaSlug = area.slug
            areaKey = ndb.Key('ZipcodeArea', areaSlug)

        reporter = validate.get('reporter')
        
        report = Report(
            type=region,
            city=area.getCity(),
            key=area.getReportStatKey(),
            target=area,
            limitReporter=reporter,
            doMinimal=False,
            isPrecompute=True,
        )

        if reporter:
            logging.info("%s - %s" % (areaSlug, reporter))
            try:
                stats = report.runReporter(reporter)
                logging.info(stats)
            except Exception as e:
                logging.error(traceback.format_exc())
        else:
            for reporter in report.getPendingReporters():
                taskqueue.add(
                    url='/background/compute-single-%s-report/' % region,
                    params={
                        'reporter': reporter['name'],
                        'id': validate.get('id'),
                        'slug': validate.get('slug'),
                    },
                    queue_name='default',
                )

        return "OK"