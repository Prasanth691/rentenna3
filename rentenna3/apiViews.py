import flask
import logging
import random
import json
import re
import time
import uuid
import copy

from web import tracking
from web import validate
from web.base import BaseView, Route
from web.base import resource, ResponseException
from web import config
from web import rtime
from web import taskqueue
from web.mongo import MongoAggsModel
from web.mongoAggs import *

from rentenna3 import api
from rentenna3 import geocoder
from rentenna3 import util
from rentenna3.adminViews import UserAdmin, PartnerBasicExport
from rentenna3.models import *
from rentenna3.base import ReportSection
from rentenna3.base import Badge
from rentenna3.email import *
from rentenna3.backgroundViews import PartnerDailyAggregationHelper, PartnerDailyEmailTemplateAggregationHelper

from werkzeug.exceptions import BadRequest

class DeepLinks(BaseView):

    @Route('/api/0/property-report-query.redirect')
    def findAddress(self):
        partner = checkApiKey()
        require = util.getRequire()
        address, components = geocoder.geocode({
            'query': validate.get('query', validate.Required()),
            'type': 'address',
        })
        if address is None:
            url = '/find-anything/?%s' % urllib.urlencode({
                'type': "address",
                'callback': "report",
                'components': json.dumps(components),
                'require': require,
            })
        else:
            url = address.getUrl(require=require)

        return self.buildResponse(partner, url, require=require)

    @Route('/api/0/property-report.redirect')
    def findAddressByComponents(self):
        partner = checkApiKey()
        require = util.getRequire()
        address, components = geocoder.geocode({
            'streetNumber': validate.get('streetNumber'),
            'street': validate.get('street'),
            'city': validate.get('city'),
            'state': validate.get('state'),
            'zip': validate.get('zip'),
            'type': 'address',
        })
        if address is None:
            url = '/find-anything/?%s' % urllib.urlencode({
                'type': "address",
                'callback': "report",
                'components': json.dumps(components),
                'require': require,
            })
        else:
            url = address.getUrl(require=require)
        return self.buildResponse(partner, url, require=require)

    @Route('/api/0/city-report.redirect')
    def findCity(self):
        partner = checkApiKey()
        require = util.getRequire()
        city, components = geocoder.geocode({
            'city': validate.get('city'),
            'state': validate.get('state'),
            'zip': validate.get('zip'),
            'location': validate.get('location', validate.ParseJson()),
            'type': 'city',
        })
        if city is None:
            url = '/find-anything/?%s' % urllib.urlencode({
                'type': "city",
                'components': json.dumps(components),
                'require': require,
            })
        else:
            url = city.getUrl(require=require)
        return self.buildResponse(partner, url, require=require)

    @Route('/api/0/neighborhood-report.redirect')
    def findNeigborhood(self):
        partner = checkApiKey()
        require = util.getRequire()
        neighborhood, components = geocoder.geocode({
            'neighborhood': validate.get('neighborhood'),
            'city': validate.get('city'),
            'state': validate.get('state'),
            'zip': validate.get('zip'),
            'location': validate.get('location', validate.ParseJson()),
            'type': 'neighborhood',
        })
        if neighborhood is None:
            url = '/find-anything/?%s' % urllib.urlencode({
                'type': "neighborhood",
                'components': json.dumps(components),
                'require': require,
            })
        else:
            url = neighborhood.getUrl(require=require)
        return self.buildResponse(partner, url, require=require)

    @Route('/api/0/zipcode-report.redirect')
    def findZipcode(self):
        partner = checkApiKey()
        require = util.getRequire()
        area, components = geocoder.geocode({
            'zip': validate.get('zip', validate.Required()),
            'type': 'zip',
        })
        if area is None:
            url = '/find-anything/?%s' % urllib.urlencode({
                'type': "zipcode",
                'components': json.dumps(components),
                'require': require,
            })
        else:
            url = area.getUrl(require=require)
        return self.buildResponse(partner, url, require=require)

    def _hashTag(self):
        return validate.get('section')

    def buildResponse(self, partner, url, require=None):
        rst = flask.redirect(partner.decorateUrl(url, self._hashTag()))
        contactId = validate.get('contact_id')
        if require == 'subscribe':
            response = flask.make_response(rst)
            response.set_cookie(key='rsb', value='1')
            self.setContactIdCookie(contactId, partner.apiKey, response)
            return response

        if contactId:
            response = flask.make_response(rst)
            self.setContactIdCookie(contactId, partner.apiKey, response)
            return response

        return rst
    
    def setContactIdCookie(self, contactId, partnerApiKey, response):
        if contactId:
            expire = datetime.datetime.now()
            expire = expire + datetime.timedelta(seconds=60)
            response.set_cookie(key="contactId", value=contactId, expires=expire)
            response.set_cookie(key="contactIdPartnerApiKey", value=partnerApiKey, expires=expire)

class PartnerApis(BaseView):

    @Route('/api/0/create-subpartner.json', methods=['POST'])
    def createSubpartner(self):
        apiKey, apiSecret, subId, subName, settings = self.getData()
        
        partner = self.checkPartner(apiKey, apiSecret)
        self.checkPermission(partner)
        self.checkUniqueSubid(partner, subId)

        subpartner = Partner.create(partner, subId)
        subpartner.pid = subId
        subpartner.name = subName

        self.removeAdminFields(settings)
        
        self.assignIfExists(subpartner, settings, 'domains', [])
        self.assignIfExists(subpartner, settings, 'status')
        msg = self.handleSettingImages(settings)

        subpartner.settings = settings

        subpartner.put()

        result = {
            "api_key" : apiKey,
            "subpartner_id" : subId,
            "subpartner" : {
                "subpartner_id" : subpartner.pid,
                "api_key" : subpartner.apiKey,
                "api_secret" : subpartner.apiSecret
            }
        }

        if msg:
            result['msg'] = msg

        return flask.jsonify(result)

    @Route('/api/0/update-subpartner.json', methods=['POST'])
    def updateSubpartner(self):
        apiKey, apiSecret, subId, subName, settings = self.getData()
        
        partner = self.checkPartner(apiKey, apiSecret)
        self.checkPermission(partner)

        subpartner = self.checkSubpartner(partner, subId)

        self.keepAdminFields(subpartner, settings)
        
        self.assignIfExists(subpartner, settings, 'domains', [])
        self.assignIfExists(subpartner, settings, 'status')
        
        msg = self.handleSettingImages(settings)

        if subName:
            subpartner.name = subName
        if settings:
            subpartner.settings.update(settings)

        subpartner.put()

        result = {
                "api_key" : apiKey,
                "subpartner_id" : subId
            }

        if msg:
            result['msg'] = msg

        return flask.jsonify(result)


    @Route('/api/0/deprecate-subpartner.json', methods=['POST'])
    def deprecateSubpartner(self):          
        apiKey, apiSecret, subId, subName, settings = self.getData()

        partner = self.checkPartner(apiKey, apiSecret)
        self.checkPermission(partner)

        subpartner = self.checkSubpartner(partner, subId)

        """
            note: only set status for the sub partner
            TODO: do we need a scheduled task to flag desendants of this sub partner?
        """
        if subpartner.status != 'inactive':
            subpartner.status = 'inactive'
            subpartner.put()

        return flask.jsonify({
                "api_key" : apiKey,
                "subpartner_id" : subId
            })

    @Route('/api/0/get-partner-settings.json', methods=['POST'])
    def getPartnerSettings(self):          
        
        inputData = getJsonData()

        apiKey = inputData.get("api_key")
        apiSecret = inputData.get("api_secret")

        infoScope = "basic"
        if inputData.get("infoScope") == "complete" :
            infoScope = "complete"

        if inputData.get("infoType") == "complete" :
            infoScope = "complete"

        partner = self.checkPartner(apiKey, apiSecret)

        targetPartnerApiKey = inputData.get("target_api_key")

        targetPartner = self.checkTargetPartner(partner, targetPartnerApiKey)

        settings = copy.deepcopy( targetPartner.getSettings() )
        localSettings = copy.deepcopy( targetPartner.settings )

        settings.pop('users', None)
        localSettings.pop('users', None)

        self.removeAdminFields(settings)
        self.removeAdminFields(localSettings)

        if infoScope == "basic":
            settings = self.getContactSettingsOnly(settings)
            localSettings = self.getContactSettingsOnly(localSettings)

        result = {
            "api_key" : apiKey,
            "settings" : settings,
            "localSettings" : localSettings,
        }

        result['api_key'] = targetPartner.apiKey
        result['pid'] = targetPartner.pid
        result['name'] = targetPartner.name
        result['status'] = targetPartner.status
        #result['domains'] = targetPartner.domains

        return flask.jsonify(result)

    @Route('/api/0/get-partner-info.json', methods=['POST'])
    def getPartnerInfos(self):          
        
        inputData = getJsonData()

        apiKey = inputData.get("api_key")
        apiSecret = inputData.get("api_secret")

        infoScope = "basic"
        if inputData.get("infoScope") == "complete" :
            infoScope = "complete"

        if inputData.get("infoType") == "complete" :
            infoScope = "complete"

        partner = self.checkPartner(apiKey, apiSecret)

        targetPartnerApiKey = inputData.get("target_api_key")

        targetPartner = self.checkTargetPartner(partner, targetPartnerApiKey)

        settings = copy.deepcopy( targetPartner.getSettings() )
        localSettings = copy.deepcopy( targetPartner.settings )

        settings.pop('users', None)
        localSettings.pop('users', None)

        self.removeAdminFields(settings)
        self.removeAdminFields(localSettings)

        if infoScope == "basic":
            settings = self.getContactSettingsOnly(settings)
            localSettings = self.getContactSettingsOnly(localSettings)

        result = {
            "api_key" : apiKey,
            "settings" : settings,
            "localSettings" : localSettings,
        }

        result['api_key'] = targetPartner.apiKey
        result['pid'] = targetPartner.pid
        result['name'] = targetPartner.name
        result['status'] = targetPartner.status

        activeCount = Partner.getPartnerCount(targetPartner.key, "active")
        inactiveCount = Partner.getPartnerCount(targetPartner.key, "inactive")

        result['subPartnerActiveCount'] = activeCount
        result['subPartnerInactiveCount'] = inactiveCount
        #result['domains'] = targetPartner.domains

        return flask.jsonify(result)

    @Route('/api/0/partner-urls.json', methods=['POST'])
    def partnerUrls(self):
        data = getJsonData()
        apiKey = required(data, 'api_key')

        partner = Partner.forApiKey(apiKey)

        if partner is None:
            abort("invalid api_key")

        base = partner.getPreferredDomain() or config.CONFIG['URL']['BASE']

        resBaseUrl = config.CONFIG['URL']['STATIC']
        if resBaseUrl.startswith('/'):
            resBaseUrl = urlparse.urljoin(base, resBaseUrl)

        formBaseUrl = base

        return flask.jsonify({
                "api_key" : apiKey,
                "resBaseUrl" : resBaseUrl,
                "formBaseUrl" : formBaseUrl,
            })

    @Route('/api/0/export-partners.json', methods=['POST'])
    def exportPartners(self):
        data = getJsonData()
        partner = verifyPartner(data)
        targetApiKey = data.get("target_api_key")

        targetPartner = partner
        if targetApiKey:
            targetPartner = Partner.forApiKey(targetApiKey)
            if not partner.key in targetPartner.ancestorKeys and partner.key != targetPartner.key:
                abort("access to target partner is denied")


        dateRange = util.parseDateRange(data.get("dateRange"), guardStartDate=False)

        logKey = PartnerBasicExport().export(
            targetPartner.key.urlsafe(),  
            dateRange=dateRange,
            activeOnly=False
        )

        return flask.jsonify({
                "url" : "/api/0/export-partners/status/%s.json" % logKey
            })

    @Route('/api/0/export-partners/status/<logKey>.json', methods=['GET', 'POST'])
    def exportStatus(self, logKey):

        log = ndb.Key(urlsafe=logKey).get()
        result = {
                'finished' : log.isDone,
                'url' : '/api/0/export-partners/download/%s/' % logKey,
                'created' : rtime.formatTime(log.created),
            }
        return flask.jsonify(result)

    @Route('/api/0/export-partners/download/<logKey>/', methods=['GET', 'POST'])
    def downloadPartners(self, logKey):
        log = ndb.Key(urlsafe=logKey).get()
        apiKey = validate.get('api_key')
        apiSecret = validate.get('api_secret')

        if apiKey and apiSecret:
            data = {
                'api_key' : apiKey,
                'api_secret' : apiSecret,
            }
        else:
            data = getJsonData()

        partner = verifyPartner(data)
        log = ndb.Key(urlsafe=logKey).get()
        exportedPartner = log.partnerKey.get()
        if log.partnerKey == partner.key or partner.key in exportedPartner.ancestorKeys:
            return PartnerBasicExport().reportDownload(logKey)
        else:
            abort("access is denied")

    def removeAdminFields(self, settings):
        return self._adjustAdminOnlyFields(None, settings, 'remove')

    def keepAdminFields(self, partner, settings):
        return self._adjustAdminOnlyFields(partner, settings, 'keep')

    def _adjustAdminOnlyFields(self, partner, settings, keepOrRemove):
        adminFields = Partner.adminOnlyFields()
        if keepOrRemove == 'keep':
            localSettings = partner.getLocalSettings()
            for field in adminFields:
                settings.pop(field, None)
                if localSettings.get(field):
                    settings[field] = localSettings.get(field)

        elif keepOrRemove == 'remove':
            for field in adminFields:
                settings.pop(field, None)

    def assignImageSetting(self, settings, name):
        url = settings.get(name)
        if url and url.strip():
            url = url.strip()
            uid = str(uuid.uuid4())
            gcsImageFile = '/%s/%s' % (
                config.CONFIG['WEB']['UPLOAD_BUCKET'],
                uid,
            )
            success, msg = util.saveImageToCloudstorage(url, gcsImageFile)
            if success:
                settings[name] = "/subdomain-image/%s/" % uid
            return msg
        return None

    def assignIfExists(self, partner, settings, key, default=None):
        if settings and key in settings:
            value = settings.get(key) or default
            setattr(partner, key, value)

    def checkPartner(self, apiKey, secretKey):
        partner = Partner.forApiKey(apiKey)
        if not partner:
            abort("api_key is invalid")
        if partner.apiSecret != secretKey:
            abort("api_secret is invalid")
        return partner

    def checkSubpartner(self, partner, subpartnerId):
        subpartner = partner.getSubpartnerById(subpartnerId, activeOnly=False)
        if subpartner is None:
            abort("sub partner does not exist")
        return subpartner

    def checkTargetPartner(self, partner, targetApiKey):
        targetPartner = partner
        if targetApiKey:
            targetPartner = Partner.forApiKey(targetApiKey, activeOnly=False)

            if not targetPartner:
                abort("invalid target_api_key")
            #if not partner.key in targetPartner.ancestorKeys and partner.key != targetPartner.key:
            if not partner.hasAccess(targetPartner):    
                abort("access to target partner is denied")

        return targetPartner

    def checkUniqueSubid(self, partner, subpartnerId):
        subPartner = partner.getSubpartnerById(subpartnerId, keysOnly=True)
        if subPartner is not None:
            abort("subpartner_id exists")

    def checkPermission(self, partner):
        if not partner.allowCreateSubpartner():
            abort("permission is denied")

    def getData(self):       
        data = getJsonData()

        apiKey = required(data, 'api_key')
        apiSecret = required(data, 'api_secret')
        settings = data.get('settings')
        subId = required(data, 'subpartner_id')
        subName = data.get('subpartner_name')
        return apiKey, apiSecret, subId, subName, settings

    def getContactSettingsOnly(self, settings):
        contacts = dict((rkey, val) for (rkey, val) in settings.items() if rkey.startswith('contact.') )
        return contacts

    def handleSettingImages(self, settings):

        if not settings:
            return None

        msg = '' 
        temp = self.assignImageSetting(settings, 'logo')

        if temp:
            msg = msg + temp

        temp = self.assignImageSetting(settings, 'contact.photo')
        if temp:
            msg = msg + temp

        if msg:
            return msg
        return None

    def required(self, data, key):
        value = data.get(key)
        if value in [None, '']:
            abort("%s is %s" % (key, value))
        return value

class ContactApis(BaseView):

    GeocodingTypeMapping = {
        'property': 'address',
        'city': 'city',
        'neighborhood': 'neighborhood',
        'zip': 'zip',
    }

    @Route('/api/0/create-contact.json', methods=['POST'])
    def createContact(self):
        return self.createContactOrSubscribe(createOnly=True)

    @Route('/api/0/create-contact-or-subscribe.json', methods=['POST'])
    def createContactOrSubscribe(self, createOnly=False):
        data = getJsonData()
        partner = verifyPartner(data)
        email = required(data, 'email').lower()
    
        user = None
        if createOnly:
            self.verifyNoUser(email, partner)
        else:
            user = self.getUser(email, partner)

        isNewUser = False
        if user is None:
            self.verifyNoUserByContactId( data.get('contactId'), partner )

            isNewUser = True
            currentAddress = data.get("address") or {}
            user = User.simpleUser(
                None,
                email,
                context='api-creation', 
                sendEmail=False,
                partner=partner.key,
                bcc=data.get('bcc'),
                contactId=data.get('contactId'),
                firstName=data.get('firstName'),
                lastName=data.get('lastName'),
                moveDateString=data.get('moveDateString'),
                moveStatus=data.get('moveStatus'),
                street=currentAddress.get('street'),
                city=currentAddress.get('city'),
                state=currentAddress.get('state'),
                zipcode=currentAddress.get('zipcode'),
                addressStatus='api'
            )

        warning = None
        reportUrl = None
        emailReport, registerAlerts, sendInvite = self.getSubscribeActions(data)
        if partner.allowAlerts() and registerAlerts:
            reportUrl, warning = self.subscribeAlerts(partner, user, data)
        elif emailReport:
            reportUrl, warning = self.emailReport(user, data)
        elif sendInvite:
            reportUrl, warning = self.sendInvite(user, data)

        if isNewUser:
            PartnerNewLead.sendAsNeeded(
                user=user,
                reportUrl=reportUrl,
            )

        result = {
            'status': 'OK',
            'user': { 
                'email' : email,
                'partnerId': partner.pid,
                'contactId': user.contactId,
            }
        }

        self.addWarning(result, warning)

        return flask.jsonify(result)

    @Route('/api/0/update-contact.json', methods=['POST'])
    def updateContact(self):
        data = getJsonData()
        partner = verifyPartner(data)

        user, idType = self.checkUser(partner, data)
        # email = required(data, 'email').lower()
        # user = self.verifyUser(email, partner)

        if idType == 'contactId':
            email = data.get('email', None)
            if email and email != user.email:
                self.verifyNoUser(email, partner)
        elif idType == 'email':
            contactId = data.get('contactId', None)
            if contactId and contactId != user.contactId:
                self.verifyNoUserByContactId(contactId, partner)

        util.setAttrIfPresent('email', data, user)
        util.setAttrIfPresent('bcc', data, user)
        util.setAttrIfPresent('contactId', data, user)
        util.setAttrIfPresent('firstName', data, user)
        util.setAttrIfPresent('lastName', data, user)
        util.setAttrIfPresent('moveStatus', data, user)
        util.setAttrIfPresent('moveDateString', data, user)

        if self.isAddressChanged(data):
            user.addressStatus = 'api'
            util.setAttrIfPresent('street', data, user)
            util.setAttrIfPresent('city', data, user)
            util.setAttrIfPresent('state', data, user)
            util.setAttrIfPresent('zipcode', data, user)

        user.put()

        return flask.jsonify({
            'status': 'OK',
            'user': {
                'email' : user.email,
                'partnerId' : partner.pid,
                'contactId' : user.contactId,
            }
        })

    @Route('/api/0/update-contact-branding.json', methods=['POST'])
    def updateContactBranding(self):
        data = getJsonData()
        partner = verifyPartner(data)

        prevApiKey = data.get("current_api_key")
        newApiKey = data.get("new_api_key")

        prevPartner = self.verifyTargetPartner(partner, prevApiKey, isNewTargetApiKey=False)
        newPartner = self.verifyTargetPartner(partner, newApiKey, isNewTargetApiKey=True)

        user, idType = self.checkUser(prevPartner, data)

        newContactId = data.get("new_contactId")
        if not newContactId:
            newContactId = user.contactId

        if newContactId:
            self.verifyNoUserByContactId(newContactId, newPartner)

        self.verifyNoUser(user.email, newPartner)

        user.partner = newPartner.key
        user.contactId = newContactId
        user.brandingDate = datetime.datetime.now()
        user.put()

        return flask.jsonify({
            'status': 'OK',
            'user': {
                'contactId' : user.contactId,
                'email' : user.email,
                'partnerId' : newPartner.pid,
            }
        })

    @Route('/api/0/contact-subscribe.json', methods=['POST'])
    def contactSubscribe(self):
        data = getJsonData()
        partner = verifyPartner(data)

        user, idType = self.checkUser(partner, data)

        warning = None
        reportUrl = None
        emailReport, registerAlerts, sendInvite = self.getSubscribeActions(data)
        if partner.allowAlerts() and registerAlerts:
            reportUrl, warning = self.subscribeAlerts(partner, user, data)
        elif emailReport:
            reportUrl, warning = self.emailReport(user, data)
        elif sendInvite:
            reportUrl, warning = self.sendInvite(user, data)

        result = {
            'status': 'OK',
            'user': {
                'email' : user.email,
                'partnerId' : partner.pid,
                'contactId' : user.contactId,
            }
        }

        self.addWarning(result, warning)

        return flask.jsonify( result )

    @Route('/api/0/export-contacts.json', methods=['POST'])
    def exportContacts(self):
        data = getJsonData()
        partner = verifyPartner(data)
        targetApiKey = data.get("target_api_key")

        targetPartner = partner
        if targetApiKey:
            targetPartner = Partner.forApiKey(targetApiKey)
            if not partner.key in targetPartner.ancestorKeys and partner.key != targetPartner.key:
                abort("access to target partner is denied")

        dateRange = util.parseDateRange(data.get("dateRange"), guardStartDate=False)

        userAdmin = UserAdmin()
        
        logUrl = userAdmin.export(dateRange=dateRange, isAR=False, partner=partner, targetPartner=targetPartner)

        return flask.jsonify({
                "url" : "/api/0/export-contacts/status/%s.json" % logUrl
            })

    @Route('/api/0/export-contacts/status/<logKey>.json', methods=['GET', 'POST'])
    def exportContactsStatus(self, logKey):
        log = ndb.Key(urlsafe=logKey).get()

        result = {
                'finished' : log.isDone,
                'url' : '/api/0/export-contacts/download/%s/' % logKey,
                'created' : rtime.formatTime(log.created),
            }

        return flask.jsonify(result)

    @Route('/api/0/export-contacts/download/<logKey>/', methods=['GET', 'POST'])
    def contactsDownload(self, logKey):

        apiKey = validate.get('api_key')
        apiSecret = validate.get('api_secret')

        if apiKey and apiSecret:
            data = {
                'api_key' : apiKey,
                'api_secret' : apiSecret,
            }
        else:
            data = getJsonData()

        partner = verifyPartner(data)

        log = ndb.Key(urlsafe=logKey).get()

        if log.partnerApiKey == partner.apiKey or log.targetPartnerApiKey == partner.apiKey:
            userAdmin = UserAdmin()
            return userAdmin.handleDownload(logKey)
        else:
            abort("access is denied")

    @Route('/api/0/contact-info.json', methods=['POST'])
    def getContactInfo(self):
        data = getJsonData()
        partner = verifyPartner(data)

        user, idType = self.checkUser(partner, data)

        userAdmin = UserAdmin()
        userJson = userAdmin.simpleUserJson(user)
       
        result = {
            'status': 'OK',
            'user' : userJson,
        }
                
        return flask.jsonify( result )

    # note: this is only supported in dev and staging for easy testing purpose.
    # TODO: may delete this method in the future.
    # @Route('/api/0/deprecate-contact.json', methods=['POST'])
    # def deprecateContact(self):
    #     

    #     if not tempEndpoint:
    #         abort("not supported")

    #     data = getJsonData()
    #     email = required(data, 'email')

    #     partner = self.verifyPartner(data)
    #     user = self.verifyUser(email, partner)

    #     AlertSubscription.unsubscribeAll(user.key)
        
    #     user.key.delete()

    #     return flask.jsonify({
    #         'status': "OK",
    #         'user': {
    #             'email' : email,
    #             'partnerId' : partner.pid,
    #         },
    #     })
    def addWarning(self, result, warning):
        if warning:
            result['message'] = warning

    def getSubscribeActions(self, data):
        action = data.get('action')    
        emailReport = None
        registerAlerts = None
        sendInvite = None
        if action:
            emailReport = action == 'email-report'
            registerAlerts = action == 'register-alerts'
            sendInvite = action == 'send-invite'
        return emailReport, registerAlerts, sendInvite

    def isAddressChanged(self, data):
        return data.get('street') or data.get('city') or data.get('state') or data.get('zipcode')

    # def verifyPartner(self, data):

    #     apiKey = required(data, 'api_key')
    #     apiSecret = required(data, 'api_secret')

    #     partner = Partner.forApiKey(apiKey)
    #     if not partner:
    #         abort("api_key is invalid")
    #     if partner.apiSecret != apiSecret:
    #         abort("api_secret is invalid")
    #     return partner

    def verifyTargetPartner(self, partner, targetApiKey, isNewTargetApiKey=False):
        targetPartner = None
        if targetApiKey:
            targetPartner = Partner.forApiKey(targetApiKey, activeOnly=False)
            if not targetPartner:
                abort("invalid %s_target_api_key" % "new_" if isNewTargetApiKey else "")
            #if not partner.key in targetPartner.ancestorKeys and partner.key != targetPartner.key:
            if not partner.hasAccess(targetPartner):    
                abort("access to %starget partner is denied" % "new " if isNewTargetApiKey else "")

        if not targetPartner:
            abort("Can not find the partner specified by the %s api key: %s" % ("new" if isNewTargetApiKey else "current", targetApiKey) )
        return targetPartner

    def verifyNoUser(self, email, partner):
        if email and self.getUser(email, partner) is not None:
            abort("user exists for the email %s in %s" % (email, self.displayPartner(partner)) )

    def verifyUser(self, email, partner):
        user = self.getUser(email, partner)
        if user is None:
            abort("user dose not exist for the email %s in %s" % (email, self.displayPartner(partner)) )
        return user

    def verifyUserByContactId(self, contactId, partner):
        user = self.getUserByContactId(contactId, partner)
        if user is None:
            abort("user dose not exist for the contactId %s in %s" % (contactId, self.displayPartner(partner)) )
        return user

    def verifyNoUserByContactId(self, contactId, partner):
        if contactId:
            user = self.getUserByContactId(contactId, partner)
            if user is not None:
                abort("user exists for the contactId %s in %s" % (contactId, self.displayPartner(partner)) )

    def getUser(self, email, partner):
        return User.forEmail(email, partner.key)

    def getUserByContactId(self, contactId, partner):
        return User.forContactId(contactId, partner.key)

    def checkUser(self, partner, data):
        contactId = data.get('contactId', None)
        email = data.get('email', None)
        idType = data.get('idType', None)

        if email: 
            email = email.lower()

        user = None

        if idType:
            if idType == 'contactId':
                user = self.getUserByContactId(contactId, partner)
            elif idType == 'email':
                user = self.getUser(email, partner)
        else:
            if contactId:
                user = self.getUserByContactId(contactId, partner)
                idType = 'contactId'
            if user is None:
                user = self.getUser(email, partner)
                idType = 'email'

        if user is None:
            abort("can not identify the contact by contactId or email")

        return (user, idType)

    def displayPartner(self, partner):
        if not partner:
            return ""

        if partner.name:
            return partner.name
        if partner.pid:
            return partner.pid
        return partner.apiKey

    def _emailReportOrSendInvite(self, user, data, emailCls):
        loc = None
        warning = None
        reportUrl = None
        locType, components = self.getLocationInfo(data)
        if locType and components:
            loc, components = geocoder.geocode(components)

        if loc is None:
            warning = 'Can not locate the target'
            return reportUrl, warning

        if locType == 'property':
            property = loc.getProperty()
            if property:
                reportUrl = loc.getUrl(domain=True)
                emailCls.send(
                    user=user,
                    target=reportUrl,
                    commonName=loc.getShortName(),
                    type=locType,
                )
            else:
                warning = 'Can not get property from the located target'
        elif locType == 'city' or \
            locType == 'neighborhood' or \
            locType == 'zip':
            reportUrl = loc.getUrl(domain=True)
            emailCls.send(
                    user=user,
                    target=reportUrl,
                    commonName=loc.name,
                    type=locType,
                )
        return reportUrl, warning

    def emailReport(self, user, data):
        return self._emailReportOrSendInvite(user, data, ReportGenerated)

    def sendInvite(self, user, data):
        return self._emailReportOrSendInvite(user, data, ReportInvitation)

    def subscribeAlerts(self, partner, user, data):
        loc = None
        warning = None
        reportUrl = None
        locType, components = self.getLocationInfo(data)
        if locType and components:
            loc, components = geocoder.geocode(components)

        if loc is None:
            warning = 'Can not locate the target'
            return reportUrl, warning

        if locType == 'property':
            property = loc.getProperty()
            if property:
                skipConfirmation = data.get('skipAlertConfirmation', None)
                if skipConfirmation is None:
                    skipConfirmation = partner.getSetting('skipAlertConfirmation')

                reportUrl = loc.getUrl(domain=True)
                AlertSubscription.subscribe(
                    propertyKey=property.key,
                    user=user,
                    skipConfirmationEmail=skipConfirmation,
                )
            else:
                warning = 'Can not get property from the located target'
        elif locType == 'city':
            pass
        elif locType == 'neighborhood':
            pass
        elif locType == 'zip':
            pass

        return reportUrl, warning

    def getLocationInfo(self, data):
        locType = data.get('locationType')
        if not locType:
            locType = 'property'

        components = copy.deepcopy(data.get(locType))
        if components:
            components['type'] = self.GeocodingTypeMapping.get(locType)
        return locType, components

class AnalyticApis(BaseView):
    # EmailSentCollection = 'msgsnd'
    # ReportViewsCollection = 'reportViews'
    # PartnerDailyAggsCollection = 'partnerDailyAggs'

    # EMAIL_AGGS = set(('total', 'delivery', 'open', 'click', 'unsub'))
    # REPORT_VIEW_AGGS = set( ('reportview',) )
    AGG_TYPES = ['total', 'delivery', 'open', 'click', 'unsub', 'reportview']

    @Route('/api/0/analytics/partner-stats.json', methods=['POST'])
    def partnerAggs(self):
        return flask.jsonify(self.internalPartnerAggs())

    def internalPartnerAggs(self, inputData=None):
        params = self.getParams(inputData)
        partnerTag = params['partnerTag']
        partnerName = params['partnerName']
        dateRange = params.get('dateRange')
        start = dateRange['start']
        end = dateRange['end']

        shard=config.CONFIG['EMAIL']['shard']
        #shard = "production"

        interval = params.get('interval')
        templates = params['templates']

        result = None
        if templates:
            aggs = PartnerDailyEmailTemplateAggs.getAggs(partnerTag, templates, shard, start, end)

            result = {
                    "partner" : partnerName,
                    "dateRange" : {
                        "start" : util.getYMDStr(start),
                        "end" : util.getYMDStr(end),
                    },
                    "interval" : interval,
                    "status": "succeed",
                    "templates" : templates,
                    "result" : {}
                }
            for template in templates:
                aggsTmp = [agg for agg in aggs if agg['template'] == template]
                #aggsTmp = self.fillAggs(partnerTag, aggsTmp, start, end, template=template)
                aggsTmp = self.getPartnerIntervalAggs(interval, aggsTmp, start, end)

                result['result'][template] = aggsTmp

        else:
            aggs = PartnerDailyAggs.getAggs(partnerTag, shard, start, end)
            aggs = self.fillAggs(partnerTag, aggs, start, end)
            aggs = self.getPartnerIntervalAggs(interval, aggs, start, end)
           
            result = {
                    "partner" : partnerName,
                    "dateRange" : {
                        "start" : util.getYMDStr(start),
                        "end" : util.getYMDStr(end),
                    },
                    "interval" : interval,
                    "result" : aggs,
                    "status": "succeed",
                }

        return result
                 
    @Route('/api/0/analytics/user-stats.json', methods=['POST'])
    def userAggs(self):
        params = self.getParams()
        partnerTag = params['partnerTag']
        dateRange = params.get('dateRange')
        start = dateRange['start']
        end = dateRange['end']
        shard=config.CONFIG['EMAIL']['shard']
        userKeyStr = params.get("user")

        if not userKeyStr:
            abort("can not find the specified user")

        aggsLog = UserAggsTaskLog(
            user=userKeyStr,
            params=params,
        )

        templates = params.get('templates')

        for aggType in self.AGG_TYPES:
            log = aggsLog.createAggLog(aggType)

            url = '/background/user-daily-agg/'
            if templates:
                url = '/background/user-daily-email-template-agg/'
            taskqueue.add(
                url=url,
                params={
                    'aggTypes' : pickle.dumps([aggType]),
                    'partnerTags' : pickle.dumps([partnerTag]),
                    'shard' : shard,
                    'startDate' : util.getYMDStr(start),
                    'user' : userKeyStr,
                    'logKey' : log.key.urlsafe(),
                    'templates' : pickle.dumps(templates),
                },
                queue_name='mongoaggs'
            )
        aggsLog.put()

        timeout = False

        async = params.get('async')
        if async:
            result = self.createBasicUserResult(params)
            result.update(
                {
                    'status' : 'waiting',
                    'resultUrl' : '/api/0/analytics/user-stats-result/%s/' % aggsLog.key.urlsafe(),
                }
            )
            return flask.jsonify(result)

        else:
            count = 0
            while True:
                count += 1
                if count > 8:
                    timeout = True
                    break
                if aggsLog.isDone():
                    break
                time.sleep(1)
                
            return flask.jsonify(
                self.queryUserStats(
                    params=params,
                    userKeyStr=userKeyStr, 
                    logKey=aggsLog.key.urlsafe(), 
                    timeout=timeout
                )
            )

    @Route('/api/0/analytics/user-stats-result/<keyStr>/', methods=['GET'])
    def userStatus(self, keyStr):
        logKey = ndb.Key(urlsafe=keyStr)
        if not logKey:
            abort("incorrect url")

        log = logKey.get()
        if log.isDone():
            result = self.queryUserStats(
                params=log.params,
                userKeyStr=log.user,
                logKey=keyStr, 
                timeout=False
            )
            return flask.jsonify(result)
        else:
            result = self.createBasicUserResult(log.params)
            result.update(
                {
                    'status' : 'waiting',
                    'resultUrl' : '/api/0/analytics/user-stats-result/%s/' % keyStr,
                }
            )
            return flask.jsonify(result)

    def createBasicUserResult(self, params):
        dateRange = params.get('dateRange')
        start = dateRange.get('start')
        end = dateRange.get('end')
        return {
            "partner" : params.get('partnerName'),
            "contactId" : params.get("contactId"),
            "email" : params.get("email"),
            "dateRange" : {
                "start" : util.getYMDStr(start),
                "end" : util.getYMDStr(end),
            },
            "interval" : params.get('interval'),
            "result" : None,
        }

    def queryUserStats(self, params, userKeyStr, logKey,timeout):
        partnerTag = params.get('partnerTag')
        dateRange = params.get('dateRange')
        start = dateRange.get('start')
        end = dateRange.get('end')
        interval = params.get('interval')

        fields = {
                '_id' : 0,
                'tag' : 0,
                'date': 0,
            }
        sort=[ ('dayDate', -1), ]

        templates = params.get('templates')
        if templates:
            aggs = UserDailyEmailTemplateAggs.queryEx(
                query={
                    'user' : userKeyStr,
                    'tag' : partnerTag,
                    'dayDate' : {
                        '$gte' : start,
                        '$lte' : end,
                    },
                    'template' : {'$in' : templates}
                },
                fields=fields,
                sort=sort
            )
        else:
            aggs = UserDailyAggs.queryEx(
                query={
                    'user' : userKeyStr,
                    'tag' : partnerTag,
                    'dayDate' : {
                        '$gte' : start,
                        '$lte' : end,
                    },
                },
                fields=fields,
                sort=sort
            )

        result = self.createBasicUserResult(params)

        if not aggs and timeout:
            result.update(
                {
                    'status' : 'waiting',
                    'resultUrl' : '/api/0/analytics/user-stats-result/%s/' % logKey,
                    'msg' : 'Please use async query or use resultUrl to get your result'
                }
            )
            return result;

        if templates:
            result['templates'] = templates
            result['result'] = {}
            for template in templates:
                aggsTmp = [agg for agg in aggs if agg['template'] == template]
                #aggsTmp = self.fillAggs(partnerTag, aggsTmp, start, end, template=template)
                aggsTmp = self.getUserIntervalAggs(interval, aggsTmp, start, end)
                result['result'][template] = aggsTmp
                result.update({'status': 'succeed'})

        else:
            aggs = self.fillAggs(partnerTag, aggs, start, end)
            aggs = self.getUserIntervalAggs(interval, aggs, start, end)

            result.update({'result' : aggs, 'status': 'succeed'})

        rContactInfo = params.get("contactInfo")
        if rContactInfo:
            userAdmin = UserAdmin()
            userJson = userAdmin.simpleUserJson(userKeyStr, isKey=True)
            result['contactInfo'] = userJson

        return result

    def getPartnerIntervalAggs(self, interval, aggs, start, end):
        return self._getIntervalAggs(True, interval, aggs, start, end)

    def getUserIntervalAggs(self, interval, aggs, start, end):
        return self._getIntervalAggs(False, interval, aggs, start, end)

    def _getIntervalAggs(self, isPartner, interval, aggs, start, end):
        if interval == 'daily':
            if isPartner:
                return list(DailyAggEx(agg).toJson() for agg in aggs)
            return list(DailyAgg(agg).toJson() for agg in aggs)

        days = None
        if interval == 'weekly':
            days = 7
        elif interval == 'monthly':
            days = 30

        multiAggCls = MultiDaysAgg
        if isPartner:
            multiAggCls = MultiDaysAggEx
        # if days:
        #     buff = []
        #     count = len(aggs)
        #     startIndex = 0
        #     endIndex = 0
        #     loop = 0
        #     while endIndex < count:
        #         startIndex = loop * days
        #         endIndex = (loop + 1) * days
        #         pieces = aggs[startIndex:endIndex]

        #         if len(pieces) > 0:
        #             daysAgg = multiAggCls(pieces)
        #             buff.append(daysAgg)
        #         loop += 1

        #     return list(agg.toJson() for agg in buff)
        
        start = util.getYMD(start)
        end = util.getYMD(end)
        if days:
            buff = []
            pieces = []
            intervalEnd = end
            intervalStart = end - datetime.timedelta(days=days)
            for agg in aggs:
                dayDate = util.getYMD(agg.dayDate)
                if dayDate <= intervalEnd and dayDate > intervalStart:
                    pieces.append(agg)
                else:

                    if pieces:
                        daysAgg = multiAggCls( 
                            pieces, 
                            self.buildDateRangeStr(intervalStart, intervalEnd) 
                        )

                        buff.append(daysAgg)

                    pieces = []
                    intervalStart, intervalEnd = self.findIntervalStartEnd(
                        agg.dayDate, 
                        intervalStart, 
                        days, 
                        start
                    )

                    if intervalStart is not None:
                        pieces.append(agg)
                    else:
                        break
            if pieces:
                daysAgg = multiAggCls( 
                    pieces, 
                    self.buildDateRangeStr(intervalStart, intervalEnd) 
                )
                buff.append(daysAgg)

            return list(agg.toJson() for agg in buff)
        return None

    def buildDateRangeStr(self, intervalStart, intervalEnd):
        low = intervalStart + datetime.timedelta(days=1)
        high = intervalEnd

        return [
            util.getYMDStr(low),
            util.getYMDStr(high),
        ]

    def findIntervalStartEnd(self, dayDate, prevStart, days, minDate):
        intervalEnd = prevStart
        intervalStart = intervalEnd - datetime.timedelta(days=days)

        if dayDate <= intervalStart:
            if dayDate > minDate:
                return self.findIntervalStartEnd(dayDate, intervalStart, days, minDate)
            else:
                return (None, None)
        else:
            return (intervalStart, intervalEnd)

    def addEmptyAgg(self, tag, date, buff, rangeObj, template=None):
        for days in rangeObj:
            if template:
                emptyAgg = PartnerDailyEmailTemplateAggs.createEmpty(
                        tag=tag,
                        dayDate=(date - datetime.timedelta(days=days)),
                        template=template,
                    )
            else:
                emptyAgg = PartnerDailyAggs.createEmpty(
                        tag=tag,
                        dayDate=(date - datetime.timedelta(days=days)),
                    )
            buff.append(emptyAgg)

    def fillAggs(self, tag, aggs, start, end, template=None):
        buff = []
        prevDate = None
        currDate = None
        for agg in aggs:
            currDate = agg.dayDate
            if prevDate:
                firstDate = prevDate
                secondDate == currDate
            else:
                firstDate = end
                secondDate = agg.dayDate

            daysDelta = (util.getYMD(firstDate) - util.getYMD(secondDate)).days
            self.addEmptyAgg(tag, end, buff, range(1, daysDelta), template=template)
            buff.append(agg)

            prevDate = currDate

        # if currDate is None:
        #     daysDelta = (self.getYMD(end) - self.getYMD(start)).days
        #     self.addEmptyAgg(tag, end, buff, range(0, daysDelta))
        # else:
        #     daysDelta = (self.getYMD(currDate) - self.getYMD(start)).days
        #     self.addEmptyAgg(tag, currDate, buff, range(1, daysDelta))
        return buff

    def getParams(self, inputData=None):

        if inputData:
            data = inputData
        else:
            data = getJsonData()

        partner = verifyPartner(data, allowAR=True)

        hasSubPartner = False
        if partner is None:
            partnerKey = 'address-report'
            partnerName = "AddressReport"
            apiKey = ''
        else:
            hasSubPartner = partner.hasSubpartner()
            partnerKey = partner.key.urlsafe()
            partnerName = partner.name
            apiKey = partner.apiKey

        dateRange = util.parseDateRange( data.get('dateRange') )
        if dateRange is None:
            dateRange = util.parseDateRange('lastweek')
        contactId = data.get("contactId")
        email = data.get("email")
        eventType = data.get("eventType")
        user = None
        userKey = None
        if contactId and partner:
            user = User.forContactId(contactId, partner.key)

        if user is None and email and partner:
            user = User.forEmail(email=email, partner=partner.key)

        if user:
            userKey = user.key.urlsafe()
            if email is None:
                email = user.email

        ignoreDate = data.get('ignoreDate')
        if ignoreDate == 'nihaodongfanghong':
            ignoreDate = True
        else:
            ignoreDate = False

        contactInfo = data.get("contactInfo")

        showEventCount = data.get("showEventCount") or False
        params = {
            "partnerKey" : partnerKey,
            "partnerName" : partnerName,
            "partnerTag" : "partner:%s" % partnerKey,
            "apiKey" : apiKey,
            "dateRange" : dateRange,
            "interval" : util.getAggregationInterval(data),
            "contactId" : contactId,
            "user" : userKey,
            "email" : email,
            "async" : data.get("async", False),
            "templates" : data.get("templates", None),
            "eventType" : eventType,
            "contactInfo" : contactInfo,
            "ignoreDate" : ignoreDate,
            "hasSubPartner" : hasSubPartner,
            "showEventCount" : showEventCount,
        }

        return params

    def checkDrilldownDateRange(self, dateRange, hasSubPartner=False):
        if dateRange:
            delta = dateRange['end'] - dateRange['start']
            if hasSubPartner:
                if delta.days in range(7):
                    return
            else:
                if delta.days in range(30):
                    return

        if hasSubPartner:
            abort("date range start and end should be within 7 days")
        else:
            abort("date range start and end should be within 30 days")

    def eventTypeError(self):
        #keys = ', '.join(IntervalAgg.DRILLDOWN_AGGTYPE_LOOKUP.keys())
        return 'Unsupported eventType'

    @Route('/api/0/analytics/partner-stats/drilldown-users.json', methods=['POST'])
    def partnerDrilldownUsers(self):
        params = self.getParams()

        dateRange = params.get('dateRange')
        if not params.get('ignoreDate'):
            self.checkDrilldownDateRange(dateRange, hasSubPartner=params.get('hasSubPartner'))

        templates = params['templates']
        templates = rutil.listify(templates)

        eventType = params['eventType']
        aggType = None
        if eventType in IntervalAgg.DRILLDOWN_AGGTYPE_LOOKUP:
            aggType = IntervalAgg.DRILLDOWN_AGGTYPE_LOOKUP[eventType]
        else:
            abort(self.eventTypeError())

        helperCls = PartnerDailyAggregationHelper
        if templates:
            helperCls = PartnerDailyEmailTemplateAggregationHelper
            
        if aggType not in helperCls.AGG_TYPES:
            abort(self.eventTypeError())

        helper = helperCls(taskUrl=None)
        pipelineCls = helper.getUserDrilldownMongoPipelineCls(aggType)
        modelCls = helper.aggregateCls(aggType)
        
        if pipelineCls is None or modelCls is None:
            abort(self.eventTypeError())

        start = dateRange['start']
        end = dateRange['end']
        partnerTag = params['partnerTag']
        partnerName = params['partnerName']
        interval = params['interval']
        # templates = params['templates']

        shard=config.CONFIG['EMAIL']['shard']    

        options = {
            'aggType' : aggType,
            'tags' : [partnerTag],
            'dateRange' : dateRange,
            'shard' : shard,
            'templates' : templates,
            'collectionName' : modelCls.collectionName,
        }
 
        userAdmin = UserAdmin()
        header = userAdmin.getCsvHeader()
        showEventCount = params.get("showEventCount")
        if showEventCount:
            header.append("_eventCount")
            pipeline = pipelineCls(**options).buildPipelines()
            countAggs = modelCls.query(pipeline)
            users = []
            if countAggs and countAggs['result']:
                aggResult = countAggs['result']
                userLookup = dict( (item['user'], item['val']) for item in aggResult if item['user'])
                userKeyStrs = userLookup.keys()
                userItems = userAdmin.getSimpledUsers(userKeyStrs, isKey=True, lookup=userLookup)
                users = [dict(zip(header, item)) for item in userItems if item]
        else:
            preMatch = pipelineCls(**options).preMatchStage()
            query = preMatch['$match']

            userField = MongoCollectionUserHelper.userField(modelCls.collectionName)
            userKeyStrs = modelCls.distinct(query, userField)
            userItems = userAdmin.getSimpledUsers(userKeyStrs, isKey=True)
            users = [dict(zip(header, item)) for item in userItems if item]

        result = {
            "partner" : partnerName,
            "dateRange" : {
                "start" : util.getYMDStr(start),
                "end" : util.getYMDStr(end),
            },
            # "interval" : interval,
            "status": "succeed",
            #{}"templates" : templates,
            "result" : users
        }

        if templates:
            result['templates'] = templates

        return flask.jsonify(result)

class IntervalAgg(object):
    DRILLDOWN_AGGTYPE_LOOKUP = {
        'opens' : 'open',
        'clicks' : 'click',
        'reportViews' : 'reportview',
        'unsubscribes' : 'unsub',
        'user' : 'user',
        'subscriber' : 'subscriber',
        'sent' : 'total',
        'delivered' : 'delivery',
        'unopened' : 'unopen',
    }

    def toJson(self):
        return None

    def addRates(self, doc):
        doc['deliveryRate'] = util.rateStr(doc['delivered'], doc['sent'])
        doc['openRate'] = util.rateStr(doc['opens'], doc['delivered'])
        doc['clickRate'] = util.rateStr(doc['clicks'], doc['delivered'])
        doc['unopenRate'] = util.rateStr(doc['unopened'], doc['delivered'])

    def buildDescDateRange(self, aggOrAggs):
        if isinstance(aggOrAggs, list) or isinstance(aggOrAggs, tuple):
            end = aggOrAggs[0]
            start = aggOrAggs[len(aggOrAggs) - 1]
            return [start.day, end.day]
        else:
            return [aggOrAggs.day]
            
class DailyAgg(IntervalAgg):
    def __init__(self, agg):
        self.agg = agg

    def toJson(self):
        agg = self.agg
        doc = {
            'dateRange' : self.buildDescDateRange(self.agg),
            'sent' : agg.getTotalCount(),
            'delivered' : agg.getDeliveryCount(),
            'opens' : agg.getOpenCount(),
            'clicks' : agg.getClickCount(),
            'reportViews' : agg.getReportViewCount(),
            'unopened' : agg.getUnopenCount(),
            'unsubscribes' : agg.getUnsubscribeCount(),
        }

        self.addRates(doc)
        return doc

class MultiDaysAgg(IntervalAgg):
    def __init__(self, aggs, dateRanges=None):
        self.aggs = aggs
        self.dateRanges = dateRanges

    def toJson(self):
        aggs = self.aggs
        dateRanges = self.dateRanges 
        if dateRanges is None:
            dateRanges = self.buildDescDateRange(self.aggs)

        doc = {
            'dateRange' : self.dateRanges,
            'sent' : sum(agg.getTotalCount() for agg in aggs),
            'delivered' : sum(agg.getDeliveryCount() for agg in aggs),
            'opens' : sum(agg.getOpenCount() for agg in aggs),
            'clicks' : sum(agg.getClickCount() for agg in aggs),
            'reportViews' : sum(agg.getReportViewCount() for agg in aggs),
            'unopened' : sum(agg.getUnopenCount() for agg in aggs),
            'unsubscribes' : sum(agg.getUnsubscribeCount() for agg in aggs),
        }
        self.addRates(doc)
        return doc

class DailyAggEx(DailyAgg):
    def toJson(self):
        doc = DailyAgg.toJson(self)
        doc['user'] = self.agg.getUserCount()
        doc['subscriber'] = self.agg.getSubscriberCount()
        return doc

class MultiDaysAggEx(MultiDaysAgg):
    def toJson(self):
        doc = MultiDaysAgg.toJson(self)
        doc['user'] = sum(agg.getUserCount() for agg in self.aggs)
        doc['subscriber'] = sum(agg.getSubscriberCount() for agg in self.aggs)
        return doc

def abort(message):
    resp = flask.jsonify({
                "error" : message
            })
    resp.status_code = 400

    logging.error('error: %s' % message)
    flask.abort(resp)

def checkApiKey():
    apiKey = validate.get('api_key')
    partner = Partner.forApiKey(apiKey)
    if partner is None:
        flask.abort(400)
    return partner

def verifyPartner(data, allowAR=False):
    #TODO: remove it, temp for using address-report.
    apiKey = data.get('api_key')
    if not apiKey:
        if allowAR:
            return None
        else:
            abort('api_key is missing')

    apiKey = required(data, 'api_key')
    apiSecret = required(data, 'api_secret')

    partner = Partner.forApiKey(apiKey)
    if not partner:
        abort("api_key is invalid")
    if partner.apiSecret != apiSecret:
        abort("api_secret is invalid")
    return partner

def required(data, key):
    value = data.get(key)
    if value in [None, '']:
        abort("%s is %s" % (key, value))
    return value

def getJsonData():
    data = None
    try:
        data = flask.request.get_json()
    except BadRequest as e:
        data = None
    if data is None or not isinstance(data, dict):
        abort("invalid json data")
    return data