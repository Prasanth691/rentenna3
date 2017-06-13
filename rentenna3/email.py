import datetime

import math
from web import rutil
import util
import json

from rentenna3.base import BaseEmail, BasePartnerEmail, BaseArEmail

class PropertyEmail(BaseEmail):

    __abstract__ = True
    isAlert = True

    @classmethod
    def getTestData(cls):
        from rentenna3.models import Property, ndb
        data = BaseEmail.getTestData()
        data['property'] = Property(
            key=ndb.Key(Property, '45-wall-street'),
            city='manhattan-ny',
            rank=1,
            shortName='Test Property',
        )
        return data

    def __init__(self, property, **kwargs):
        BaseEmail.__init__(self, **kwargs)
        self.property = property

    def getTags(self):
        tags = BaseEmail.getTags(self)
        tags += self.property.getTags()
        return tags

    def getTemplateContext(self):
        context = BaseEmail.getTemplateContext(self)
        context['property'] = self.property
        return context

class AlertFor311(PropertyEmail):

    template = 'email/311Alert.jinja2'

    @classmethod
    def getTestData(cls):
        from rentenna3.models import ObiAvmResponse, ObiSale
        data = PropertyEmail.getTestData()
        data['filth'] = 1
        data['noise'] = 3
        data['street'] = 0
        data['rodent'] = 20
        data['distance'] = "within 1 mile"
        return data

    def __init__(self, filth, noise, street, rodent, distance, **kwargs):
        PropertyEmail.__init__(self, **kwargs)
        self.filth = filth
        self.noise = noise
        self.street = street
        self.rodent = rodent
        self.distance = distance

    def getSubject(self):
        total = self.getTotal()
        return "New %s Alert: %s Reported this Week" % (
            self.property.shortName,
            rutil.plural(total, "Complaint"),
        )

    def getTemplateContext(self):
        context = PropertyEmail.getTemplateContext(self)
        context['filth'] = self.filth
        context['noise'] = self.noise
        context['street'] = self.street
        context['rodent'] = self.rodent
        context['distance'] = self.distance
        context['total'] = self.getTotal()
        return context

    def getTotal(self):
        return (
            self.filth
            +
            self.noise
            +
            self.street
            +
            self.rodent
        )

class AlertForAirQuality(PropertyEmail):

    template = 'email/airQualityAlert.jinja2'

    @classmethod
    def getTestData(cls):
        from rentenna3.models import ObiAvmResponse, ObiSale
        data = PropertyEmail.getTestData()
        data['thisWeek'] = {
            'datetime': "07/04/15",
            'breezometer_aqi': 99,
            'breezometer_description': "Excellent Air Quality",
            'breezometer_color': "#00E400",
            'random_recommendations': {
                'children': "No reason to panic, but pay attention to changes in air quality and any signals of breathing problems in your children",
                'sport': "You can exercise outdoors - but make sure to stay alert to our notifications",
                'health': "There is no real danger for people with health sensitivities. Just keep an eye out for changes in air quality for the next few hours",
                'inside': "The amount of pollutants in the air is noticeable, but still there is no danger to your health - It is recommended to continue monitoring changes in the coming hours",
                'outside': "You can go out, but please pay attention for changes in air quality",
            },
            'dominant_pollutant_canonical_name': "o3",
            'dominant_pollutant_description': "Ozone",
            'dominant_pollutant_text': {
                'main': "At the moment, O3 is the main pollutant in the air.",
                'effects': "Ozone can irritate the airways causing coughing, a burning sensation, wheezing and shortness of breath. Children, people with respiratory or lung and heart diseases, elderly and those who exercise outdoors are particularly vulnerable to ozone exposure.",
                'causes': "Ozone is created in a chemical reaction between atmospheric oxygen, nitrogen oxides, organic compounds and sunlight."
            },
        }
        data['lastWeek'] = {
            'datetime': "07/01/15",
            'breezometer_aqi': 75,
            'breezometer_description': "Excellent Air Quality",
            'breezometer_color': "#00E400",
            'random_recommendations': {
                'children': "No reason to panic, but pay attention to changes in air quality and any signals of breathing problems in your children",
                'sport': "You can exercise outdoors - but make sure to stay alert to our notifications",
                'health': "There is no real danger for people with health sensitivities. Just keep an eye out for changes in air quality for the next few hours",
                'inside': "The amount of pollutants in the air is noticeable, but still there is no danger to your health - It is recommended to continue monitoring changes in the coming hours",
                'outside': "You can go out, but please pay attention for changes in air quality",
            },
            'dominant_pollutant_canonical_name': "o3",
            'dominant_pollutant_description': "Ozone",
            'dominant_pollutant_text': {
                'main': "At the moment, O3 is the main pollutant in the air.",
                'effects': "Ozone can irritate the airways causing coughing, a burning sensation, wheezing and shortness of breath. Children, people with respiratory or lung and heart diseases, elderly and those who exercise outdoors are particularly vulnerable to ozone exposure.",
                'causes': "Ozone is created in a chemical reaction between atmospheric oxygen, nitrogen oxides, organic compounds and sunlight."
            },
        }
        return data

    def __init__(self, thisWeek, lastWeek, **kwargs):
        PropertyEmail.__init__(self, **kwargs)
        self.lastWeek = lastWeek
        self.thisWeek = thisWeek

    def getSubject(self):
        diff = self.thisWeek['breezometer_aqi'] - self.lastWeek['breezometer_aqi']
        return "New %s Alert: %s Point Air Quality Change Vs Last Week" % (
            self.property.shortName,
            diff,
        )

    def getTemplateContext(self):
        context = PropertyEmail.getTemplateContext(self)
        context['thisWeek'] = self.thisWeek
        context['lastWeek'] = self.lastWeek
        return context

class AlertForValue(PropertyEmail):

    template = 'email/pricingAlerts.jinja2'

    @classmethod
    def getTestData(cls):
        from rentenna3.models import ObiAvmResponse, ObiSale
        data = PropertyEmail.getTestData()
        data['avm'] = ObiAvmResponse(
            highValue=200000,
            lowValue=100000,
            indicatedValue=150000,
            confidence=100,
            bedrooms=1,
            bathrooms=1,
            area=100,
            yearBuilt=1999,
            sqft=100,
            lotSize=50,
            numberFloors=2,
            propertyId="10",
            propertyType="apartment",
            apn="1000",
            unitValue=None,
        )
        return data

    def __init__(self, avm, **kwargs):
        PropertyEmail.__init__(self, **kwargs)
        self.avm = avm

    def getSubject(self):
        alert = "Value Estimate Updated"
        return "New %s Alert: %s" % (
            self.property.shortName,
            alert,
        )

    def getTemplateContext(self):
        context = PropertyEmail.getTemplateContext(self)
        context['avm'] = self.avm
        return context

class AlertForNearbySales(PropertyEmail):

    #preview = True
    template = 'email/homesalesAlerts.jinja2'

    @classmethod
    def getTestData(cls):
        from rentenna3.models import ObiSale
        data = PropertyEmail.getTestData()
        data['sales'] = [
            ObiSale(dict(
                unit="4A",
                city="New York",
                state="NY",
                zip="10003",
                distance=0.1,
                propertyType="apartment",
                bedrooms=3,
                bathrooms=2,
                closePrice=100000,
                closeDate=datetime.datetime.now(),
                addedDate=datetime.datetime.now(),
                yearBuilt="1999",
                sqft=100,
                lotSize=1000,
                floorCount=2,
                propertyId="10",
                street="123 Fake St",
            )),
            ObiSale(dict(
                unit="5A",
                city="New York",
                state="NY",
                zip="10003",
                distance=0.1,
                propertyType="apartment",
                bedrooms=3,
                bathrooms=2,
                closePrice=100000,
                closeDate=datetime.datetime.now(),
                addedDate=datetime.datetime.now(),
                yearBuilt="1999",
                sqft=100,
                lotSize=1000,
                floorCount=2,
                propertyId="10",
                street="128 Fake St",
            ))
        ]
        return data

    def __init__(self, sales, **kwargs):
        PropertyEmail.__init__(self, **kwargs)
        self.sales = sales

    def getSubject(self):
        alert = "%s Nearby" % rutil.plural(len(self.sales), "Property Sale")
        return "New %s Alert: %s" % (
            self.property.shortName,
            alert,
        )

    def getTemplateContext(self):
        context = PropertyEmail.getTemplateContext(self)
        context['sales'] = self.sales
        return context

class AlertForRecentBusiness(PropertyEmail):

    preview = True
    template = 'email/recentBusinessAlerts.jinja2'

    @classmethod
    def getTestData(cls):
        from rentenna3.models import RecentPoi
        data = PropertyEmail.getTestData()
        data['recentPois'] = {
            'total' : 2,
            'region' : 'neighborhood',
            'name' : 'West Valley',
            'pois' : [
                RecentPoi(
                    **{
                        "STATENAME" : "CALIFORNIA",
                        "OBID" : "16612602",
                        "LINEOFBUS" : "SPAS - BEAUTY",
                        "STREET" : "5257 Prospect Rd",
                        "PHONE" : "408-873-9286",
                        "CPGEOIDS" : [
                            "CS0692830",
                            "PL0668000"
                        ],
                        "location" : {
                            "type" : "Point",
                            "coordinates" : [
                                -121.994758,
                                37.292289
                            ]
                        },
                        "COUNTY3" : "085",
                        "BUSNAME" : "Emily's Nail Salon",
                        "ZIP" : "95129",
                        "NHGEOIDS" : [
                            "NH00060189",
                            "NH00001969"
                        ],
                        "LONGITUDE" : -121.994758,
                        "ZIPGEOIDS" : [
                            "ZI95129"
                        ],
                        "COUNTY" : "06085",
                        "LATITUDE" : 37.292289,
                        "STATE" : "06",
                        "GEO_MATCH_CODE_TEXT" : "ADDRESS MATCH",
                        "CATEGORY" : "PERSONAL SERVICES",
                        "CITY" : "San Jose",
                        "SIC" : "723102",
                        "COUNTYNAME" : "Santa Clara County",
                        "INDUSTRY" : "MANICURING",
                        "PRIMARY" : "PRIMARY",
                        "FRANCHISE" : "",
                        "OPEN_DATE" : "12/15/2016",
                        "geoIds" : [
                            "NH00060189",
                            "NH00001969",
                            "CS0692830",
                            "PL0668000",
                            "ZI95129"
                        ]
                    }
                ),
                RecentPoi(
                    **{
                        "STATENAME" : "CALIFORNIA",
                        "OBID" : "16612604",
                        "LINEOFBUS" : "RESTAURANTS",
                        "STREET" : "4233 Moorpark Ave",
                        "PHONE" : "408-253-4900",
                        "CPGEOIDS" : [
                            "CS0692830",
                            "PL0668000"
                        ],
                        "location" : {
                            "type" : "Point",
                            "coordinates" : [
                                -121.977158,
                                37.316055
                            ]
                        },
                        "COUNTY3" : "085",
                        "BUSNAME" : "Lyons Restaurant",
                        "ZIP" : "95129",
                        "NHGEOIDS" : [
                            "NH00060189",
                            "NH00001969"
                        ],
                        "LONGITUDE" : -121.977158,
                        "ZIPGEOIDS" : [
                            "ZI95129"
                        ],
                        "COUNTY" : "06085",
                        "LATITUDE" : 37.316055,
                        "STATE" : "06",
                        "GEO_MATCH_CODE_TEXT" : "ADDRESS MATCH",
                        "CATEGORY" : "EATING - DRINKING",
                        "CITY" : "San Jose",
                        "SIC" : "581208",
                        "COUNTYNAME" : "Santa Clara County",
                        "INDUSTRY" : "RESTAURANTS",
                        "PRIMARY" : "PRIMARY",
                        "FRANCHISE" : "",
                        "OPEN_DATE" : "12/15/2016",
                        "geoIds" : [
                            "NH00060189",
                            "NH00001969",
                            "CS0692830",
                            "PL0668000",
                            "ZI95129"
                        ]
                    }
                )
            ]
        }
        
        return data

    def __init__(self, recentPois, **kwargs):
        PropertyEmail.__init__(self, **kwargs)
        self.recentPois = recentPois

    def getSubject(self):
        #alert = "%s Nearby" % rutil.plural(len(self.sales), "Property Sale")
        alert = "Recent opened businesses "
        return "New %s Alert: %s" % (
            self.property.shortName,
            alert,
        )

    def getTemplateContext(self):
        context = PropertyEmail.getTemplateContext(self)
        context['recentPois'] = self.recentPois
        return context

class PartnerPerformanceSummary(BasePartnerEmail):

    preview = True
    template = 'email/partnerPerformanceSummary.jinja2'

    @classmethod
    def getTestData(cls):
        data = BasePartnerEmail.getTestData()
        return data

    def __init__(self, **kwargs):
        BasePartnerEmail.__init__(self, **kwargs)

    def getTemplateContext(self):
        context = BasePartnerEmail.getTemplateContext(self)
        partner = self.partner

        inputData = {
            "api_key": partner.apiKey,
            "api_secret": partner.apiSecret,
            "dateRange" : "lasttwoweeks",
            "interval" : "weekly"
        }

        dateRange = util.parseDateRange('lastweek')
        start = dateRange['start']
        end = dateRange['end']

        from rentenna3.apiViews import AnalyticApis
        api = AnalyticApis()

        aggs = api.internalPartnerAggs(inputData=inputData)

        import logging
        logging.info(aggs)

        thisWeek = None
        lastWeek = None
        if aggs and aggs['status'] == 'succeed' and aggs['result']:
            result = aggs['result']

            if len(result) >= 2:
                thisWeek = result[0]
                lastWeek = result[1]
            else:
                one = result[0]
                dateRanges = [util.getYMD(datetime.datetime.strptime(date, '%Y-%m-%d')) for date in one['dateRange']]
                isThisWeek = True
                for date in dateRanges:
                    if date < start:
                        isThisWeek = False
                        break

                if isThisWeek:
                    thisWeek = one
                else:
                    lastWeek = one

        thisValues = self.getWeekValues(thisWeek, "current")
        lastValues = self.getWeekValues(lastWeek, "previous")

        context.update(thisValues)
        context.update(lastValues)

        na = 'N/A'
        reportChange = na
        reportViewsTrend = na

        if thisWeek and lastWeek:
            views = context['currentReportViews']
            lastViews = context['previousReportViews']
            if views != na and lastViews != na:
                viewsVal = float(views)
                lastViewsVal = float(lastViews)

                reportChange = round(
                    100 * math.fabs( (viewsVal-lastViewsVal) / lastViewsVal )
                )

                # reportChange = "{0:.0f}%".format(reportChange)

                reportChange = '%s' % int(reportChange)

                if viewsVal > lastViews:
                    reportViewsTrend  = 'up'
                elif viewsVal < lastViews:
                    reportViewsTrend = 'down'

        openRateTrend = na
        clickRateTrend = na
        deliveredTrend = na
        leadsTrend = na
        usersTrend = na
        subscribersTrend = na

        if thisWeek and lastWeek:
            openRateTrend = self.calculateChangeTrend(context, 'OpenRate', na)
            clickRateTrend = self.calculateChangeTrend(context, 'ClickRate', na)
            deliveredTrend = self.calculateChangeTrend(context, 'Delivered', na)
            leadsTrend = self.calculateChangeTrend(context, 'Leads', na)
            usersTrend = self.calculateChangeTrend(context, 'Users', na)
            subscribersTrend = self.calculateChangeTrend(context, 'Subscribers', na)
        
        context.update(
            {
                'reportViewsChange' : reportChange,
                'reportViewsTrend' : reportViewsTrend,
                'openRateTrend' : openRateTrend,
                'clickRateTrend' : clickRateTrend,
                'deliveredTrend' : deliveredTrend,
                'leadsTrend' : leadsTrend,
                'usersTrend' : usersTrend,
                'subscribersTrend' : subscribersTrend,
                'dateStart' : util.getYMDStr(start, '%m/%d/%Y'),
                'dateEnd' : util.getYMDStr(end, '%m/%d/%Y'),
            }
        )

        from rentenna3.models import User
        from rentenna3.adminViews import UserAdmin
        users = User.latestUsers(start, end, partner=partner.key, limit=20)

        context['latestUsers'] = users
        return context

    def getWeekValues(self, week, prefix):
        na = 'N/A'
        if week:
            views = week['reportViews'] or na
            delivered = week['delivered'] or na
            openRate = week['openRate'] or na
            clickRate = week['clickRate'] or na
            users = week['user'] or na
            subscribers = week['subscriber'] or na
            leads = users
        else:
            views = na
            delivered = na
            openRate = na
            clickRate = na
            users = na
            subscribers = na
            leads = na

        result = {}
        result[prefix + 'ReportViews'] = views
        result[prefix + 'Delivered'] = delivered
        result[prefix + 'OpenRate'] = self.integerRateStr(openRate)
        result[prefix + 'ClickRate'] = self.integerRateStr(clickRate)
        result[prefix + 'Users'] = users
        result[prefix + 'Subscribers'] = subscribers
        result[prefix + 'Leads'] = leads


        return result

    def integerRateStr(self, rate):
        if rate and rate != 'N/A':
            rate = float(rate.strip('%'))
            return '%s' % int(round(rate))
        return rate

    def calculateChangeTrend(self, context, fieldName, na):
        curr = context['current' + fieldName]
        prev = context['previous' + fieldName]
        trend = na
        if curr != na and prev != na:
            curr = float(curr)
            prev = float(prev)
            if curr > prev:
                trend = 'up'
            elif curr < prev:
                trend = 'down'
        return trend

    def getSubject(self):
        return "AddressReport Partner Performance Summary"

    def _isEmailSuppressedByPartner(self):
        return not self.partner.needNotification()

    def _getEmail(self):
        return self.partner.getSetting("notificationEmail")

class LeadEmailHelper(object):
    @classmethod
    def init(cls, obj, user, partner, **kwargs):
        obj.user = user
        obj.reportUrl = kwargs.get('reportUrl', None)
        obj.addressRelationship = kwargs.get('addressRelationship', '')
        obj.address = kwargs.get('address', '')
        obj.ownerInterest = kwargs.get('ownerInterest', '')
        obj.renterInterest = kwargs.get('renterInterest', '')
        obj.timeline = kwargs.get('timeline', '')
        obj.contentInterest = kwargs.get('contentInterest', '')
        obj.userBuyingBudget = kwargs.get('buyingBudget', '')
        obj.userRentingBudget = kwargs.get('rentingBudget', '')
        obj.subjectSuffix = kwargs.get('subjectSuffix', None)

    @classmethod
    def updateContext(cls, obj, user, partner, context):
        address = obj.address
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

            address = ''
            if parts:
                address = ", ".join(parts)

        landingUrl = ''
        referringUrl = ''
        leadSource = ''
        if user.tracker:
            tracker = user.tracker.get()
            if tracker: # sometimes local tracker object is gone in dev environment
                if tracker.landingUrl:
                    landingUrl = tracker.landingUrl
                if tracker.referringUrl:
                    referringUrl = tracker.referringUrl
                if tracker.utmSource:
                    leadSource = tracker.utmSource

        timeline = obj.timeline
        if not timeline:
            timeline = cls.getStr(user.moveDateString)

        context.update({
            'userName' : '%s %s' % ( cls.getStr(user.firstName), cls.getStr(user.lastName) ),
            'userPhone' : cls.getStr(user.phone),
            'userEmail' : cls.getStr(user.email),
            'userId' : cls.getStr(user.contactId),
            'userAddress' : address,
            'userAddressRelation' :  obj.addressRelationship,
            'userOwnerInterest' : obj.ownerInterest,
            'userBuyingBudget' : obj.userBuyingBudget,
            'userRenterInterest' : obj.renterInterest,
            'userRentingBudget' : obj.userRentingBudget,
            'userMoveStatus' : cls.getStr(user.moveStatus),
            'userTimeline' : timeline,
            'userContentInterest' : obj.contentInterest,
            'userLeadSource' : cls.getStr(leadSource),
            'userLandingPage' : cls.getStr(landingUrl),
            'userEmailLink' : '',
            'userReportLink' : cls.getStr(obj.reportUrl),
            'userReferrer' : cls.getStr(referringUrl),
            'userRegisteredDate' : user.registered,
        })

    @classmethod
    def quizInfo(cls, quizAnswerKey=None, subjectSuffix=None):
        quizInfo = {}
        if quizAnswerKey:
            from google.appengine.ext import ndb
            quizAnswer = ndb.Key(urlsafe=quizAnswerKey).get()
            if quizAnswer:
                answer = quizAnswer.answers
                if answer:
                    try:
                        util.inheritIfPresent('address-relationship', answer, quizInfo, 'addressRelationship')
                        util.inheritIfPresent('home-interest', answer, quizInfo, 'ownerInterest')
                        util.inheritIfPresent('renting-interest', answer, quizInfo, 'renterInterest')
                        util.inheritIfPresent('time-line', answer, quizInfo, 'timeline')
                        if not quizInfo.get('timeline', None):
                            util.inheritIfPresent('timeline', answer, quizInfo, 'timeline')

                        util.inheritIfPresent('interested-section', answer, quizInfo, 'contentInterest')
                        util.inheritIfPresent('buying-budget', answer, quizInfo, 'buyingBudget')
                        util.inheritIfPresent('rental-budget', answer, quizInfo, 'rentingBudget')

                        if 'address' in answer:
                            address = answer.get('address')
                            address = json.loads(address)
                            if 'name' in address:
                                quizInfo['address'] = address['name']

                    except Exception, e:
                        pass
        if subjectSuffix:
            quizInfo['contentInterest'] = 'Home Valuation'
        return quizInfo

    @classmethod
    def getStr(cls, str):
        if str:
            return str
        return ''

class PartnerNewLead(BasePartnerEmail):

    #preview = True
    template = 'email/partnerNewLead.jinja2'

    @classmethod
    def getTestData(cls):
        data = BasePartnerEmail.getTestData()
        return data

    @classmethod
    def sendAsNeeded(cls, user, reportUrl=None, quizAnswerKey=None, subjectSuffix=None):
                    
        quizInfo = LeadEmailHelper.quizInfo(quizAnswerKey=quizAnswerKey, subjectSuffix=subjectSuffix)
        partner = user.getPartner()
        if partner and partner.needSendLead():
            cls.send(
                partner,
                user=user,
                reportUrl=reportUrl,
                subjectSuffix=subjectSuffix,
                **quizInfo
            )
            return True
        else:
            ArNewLead.sendAsNeeded(user, partner, reportUrl, quizAnswerKey, subjectSuffix)
        return False

    def __init__(self, partner, user, **kwargs):
        BasePartnerEmail.__init__(self, partner, **kwargs)
        LeadEmailHelper.init(self, user, partner, **kwargs)

    def getTemplateContext(self):
        context = BasePartnerEmail.getTemplateContext(self)
        LeadEmailHelper.updateContext(self, self.user, self.partner, context)
        return context

    def getSubject(self):
        subject = "New Lead Notification"
        if self.subjectSuffix:
            return "%s - %s" % (subject, self.subjectSuffix)
        return subject

    def _isEmailSuppressedByPartner(self):
        return not self.partner.needSendLead()

    def _getEmail(self):
        return self.partner.getSetting("leadEmail")

class PartnerFreeTrial(BasePartnerEmail):

    preview = False
    template = 'email/partnerFreeTrial.jinja2'

    @classmethod
    def getTestData(cls):
        data = BasePartnerEmail.getTestData()
        return data

    @classmethod
    def sendAsNeeded(cls):
        pass

    def __init__(self, partner, **kwargs):
        BasePartnerEmail.__init__(self, partner, **kwargs)
        
    def getTemplateContext(self):
        context = BasePartnerEmail.getTemplateContext(self)
        partner = self.partner
        from web import config
        shard=config.CONFIG['EMAIL']['shard']

        urlKey = partner.key.urlsafe()
        domain = "http://ar"

        if shard == 'qa':
            domain = "https://qa-dot-rentenna3.appspot.com"
        if shard == 'staging':
            domain = "https://staging-dot-rentenna3.appspot.com"
        if shard == "production":
            domain = "https://www.addressreport.com"
        url = "%s/free-trial/%s/#external" % (domain, urlKey)
        context.update(
            {
                'freeTrialUrl' : url,
            }
        )
        return context

    def getSubject(self):
        return "AddressReport FREE TRIAL"

    def _isEmailSuppressedByPartner(self):
        return False

    def _getEmail(self):
        return self.partner.getSetting("contact.email")

class ArNewLead(BaseArEmail):

    #preview = True
    template = 'email/partnerNewLead.jinja2'

    @classmethod
    def getTestData(cls):
        data = BaseArEmail.getTestData()
        return data

    @classmethod
    def sendAsNeeded(cls, user, partner, reportUrl=None, quizAnswerKey=None, subjectSuffix=None):
        quizInfo = LeadEmailHelper.quizInfo(quizAnswerKey=quizAnswerKey,subjectSuffix=subjectSuffix)
        cls.send(
            partner=partner,
            user=user,
            reportUrl=reportUrl,
            subjectSuffix=subjectSuffix,
            **quizInfo
        )

    def __init__(self, partner, user, **kwargs):
        BaseArEmail.__init__(self, partner, **kwargs)
        LeadEmailHelper.init(self, user, partner, **kwargs)
       
    def getTemplate(self):
        return self.template

    def getTemplateContext(self):
        context = BaseArEmail.getTemplateContext(self)
        LeadEmailHelper.updateContext(self, self.user, self.partner, context)
       
        return context

    def getSubject(self):
        subject = "New Lead Notification"
        if self.subjectSuffix:
            return "%s - %s" % (subject, self.subjectSuffix)
        return subject

class InvalidPropertyAlertSubscription(BaseEmail):

    template = 'email/quizWithInvalidAddress.jinja2'

    def getSubject(self):
        return "Can you help us finish your address report?"

class RegisteredEmail(BaseEmail):

    template = 'email/welcomeTemplate.jinja2'

    def getSubject(self):
        return "Welcome to AddressReport - the unbiased truth about any address."

class ReportGenerated(BaseEmail):

    template = 'email/reportGenerated.jinja2'

    @classmethod
    def getTestData(cls):
        from rentenna3.models import Property, ndb
        data = BaseEmail.getTestData()
        data['commonName'] = "Test Property"
        data['target'] = "http://www.google.com"
        data['type'] = "property"
        return data

    def __init__(self, commonName, target, type, **kwargs):
        BaseEmail.__init__(self, **kwargs)
        self.commonName = commonName
        self.target = target
        self.type = type

    def getSubject(self):
        return "Your report for %s is ready to view" % (
            self.commonName,
        )

    def getTags(self):
        tags = BaseEmail.getTags(self)
        tags += [
            'type:%s' % self.type,
        ]
        return tags

    def getTemplateContext(self):
        context = BaseEmail.getTemplateContext(self)
        context['commonName'] = self.commonName
        context['target'] = self.target
        context['type'] = self.type
        return context

class ResetPassword(BaseEmail):

    template = 'email/requestedPasswordReset.jinja2'

    @classmethod
    def getTestData(cls):
        data = BaseEmail.getTestData()
        data['token'] = "1234"
        return data

    def __init__(self, token, **kwargs):
        BaseEmail.__init__(self, **kwargs)
        self.token = token

    def getTemplateContext(self):
        context = BaseEmail.getTemplateContext(self)
        context['token'] = self.token
        return context

    def getSubject(self):
        return "Requested Password Reset"

class SubscribeForAlerts(PropertyEmail):

    template = 'email/alertConfirmation.jinja2'

    def getSubject(self):
        return "RESPONSE REQUIRED: Confirm your alert request for %s" % (
            self.property.shortName,
        )

class ReportInvitation(ReportGenerated):

    template = 'email/invitationNotification.jinja2'

    @classmethod
    def getTestData(cls):
        from rentenna3.models import Property, ndb
        data = BaseEmail.getTestData()
        data['commonName'] = "Test Property"
        data['target'] = "http://www.google.com"
        data['type'] = "property"
        return data

    def __init__(self, commonName, target, type, **kwargs):
        BaseEmail.__init__(self, **kwargs)
        self.commonName = commonName
        self.target = target
        self.type = type

    def getSubject(self):
        return "Your report invitation for %s" % (
            self.commonName,
        )

    def getTags(self):
        tags = BaseEmail.getTags(self)
        tags += [
            'type:%s' % self.type,
        ]
        return tags

    def getTemplateContext(self):
        context = BaseEmail.getTemplateContext(self)
        context['commonName'] = self.commonName
        context['target'] = self.target
        context['type'] = self.type
        return context
