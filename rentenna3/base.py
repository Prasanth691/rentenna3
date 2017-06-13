import datetime
import inspect
import uuid
import logging
import urllib
import traceback
import re
import flask
import premailer
import jinja2

from web import config
from web import rutil
from web import api as rapi

# class directories

_alertReporters = {}
_hybridAlertReporters = {}
_partnerAlertReporters = {}
_badges = {}
_emails = {}
_orderedReporters = {}
_quickReporters = {}
_reportCustomizers = {}
_reportDescriptors = {}
_reportSections = {}
_reporters = {}

# classes

class AlertReporter(object):

    cities = None
    schedule = None
    supports = None
    template = None
    isHybrid = False

    @classmethod
    def isDataReady(cls):
        return True

    def __init__(self, subscription, address):
        self.subscription = subscription
        self.address = address

    def report(self, **kwargs):
        raise NotImplemented

class AppCustomizer(object):

    def allowAlerts(self):
        raise NotImplemented

    def allowUsers(self):
        raise NotImplemented

    def allowedStates(self):
        raise NotImplemented

    def allowPromotion(self):
        raise NotImplemented

    def brandingPosition(self):
        raise NotImplemented

    def cobranding(self):
        raise NotImplemented

    def decorateUrl(self, url):
        raise NotImplemented

    def getContactInfo(self):
        raise NotImplemented

    def headerStyle(self):
        raise NotImplemented

    def displayHeader(self):
        raise NotImplemented

    def lookupOnlyRoot(self):
        raise NotImplemented

    def partnerSilo(self):
        raise NotImplemented

    def partnerApiKey(self):
        raise NotImplemented

    def partnerLogo(self):
        raise NotImplemented

    def renderFullReports(self):
        raise NotImplemented

    def settings(self):
        raise NotImplemented

    def skipAlertConfirmation(self):
        raise NotImplemented

    def suppressArLinks(self):
        raise NotImplemented

    def suppressBreadcrumbs(self):
        raise NotImplemented

    def suppressNav(self):
        raise NotImplemented

    def urlBase(self):
        raise NotImplemented

class BaseQuickReporter(object):

    __abstract__ = True

    supports = None

    @classmethod
    def augmentStats(cls, reportType, target, stats):
        for reporterCls in _quickReporters.get(reportType, {}).values():
            reporterInstance = reporterCls(target, stats)
            reporterInstance.report()
            stats.update(reporterInstance.getStats())

    def __init__(self, target, stats):
        self.target = target
        self.stats = stats
        self._stats = {}

    def report(self):
        pass

    def getStats(self):
        return self._stats

    def putStat(self, key, value):
        self._stats[key] = value

class BaseReportDescriptor(object):

    priority = None
    supports = None

    @classmethod
    def generateDescriptors(cls, type, target, stats):
        descriptors = _reportDescriptors[type].values()
        lines = []
        for descriptor in sorted(descriptors, key=lambda x: x.priority):
            try:
                line = descriptor(type, target, stats).generate()
            except:
                logging.error(traceback.format_exc())
                line = None
            if line:
                lines.append(line)
        return lines

    def __init__(self, type, target, stats):
        self.type = type
        self.target = target
        self.stats = stats

    def getAreaName(self):
        if self.type == 'property':
            return "around %s" % self.target.getCommonName(self.stats)
        elif self.type == 'city':
            return "in the city"
        elif self.type == 'zipcode':
            return "in this zipcode"
        elif self.type == 'neighborhood':
            return "in the neighborhood"

    def generate(self):
        raise NotImplemented

class BaseReporter(object):

    __abstract__ = True

    cities = None
    expires = None
    states = None
    requireReporters = []
    requireStats = []
    optionalStats = []
    supports = None
    version = 1
    precompute = True
    minimal = False

    @classmethod
    def getReporters(cls, reportType):
        if reportType not in _orderedReporters:
            reporters = _reporters[reportType]
            neededReporters = reporters.values()
            orderedReporters = []
            satisfiedReporters = set()
            lastRun = None
            while neededReporters:
                for reporter in list(neededReporters):
                    reporterName = reporter.__name__
                    allSatisfied = True
                    for requirement in reporter.requireReporters:
                        if requirement not in satisfiedReporters:
                            allSatisfied = False

                    if allSatisfied:
                        orderedReporters.append(reporter)
                        satisfiedReporters.add(reporterName)
                        neededReporters.remove(reporter)

                if len(neededReporters) == lastRun:
                    raise ValueError("UNSATISFIABLE: %s" % neededReporters)
                else:
                    lastRun = len(neededReporters)

            _orderedReporters[reportType] = orderedReporters
        return _orderedReporters[reportType]

    @classmethod
    def getJson(cls):
        return {
            'description': cls.description,
            'name': cls.__name__,
            'requires': cls.requireReporters,
        }

    def __init__(self, target):
        from rentenna3.models import Address, Area, City, ZipcodeArea
        if isinstance(target, Address):
            target = self.prepareAddress(target)
        elif isinstance(target, Area):
            target = self.prepareArea(target)
        elif isinstance(target, City):
            target = self.prepareCity(target)
        elif isinstance(target, ZipcodeArea):
            target = self.prepareZipCode(target)

        self.target = target
        self._stats = {}

    def report(self):
        pass

    def getStats(self):
        return self._stats

    def prepareAddress(self, target):
        return target

    def prepareArea(self, target):
        return target

    def prepareCity(self, target):
        return target

    def prepareZipCode(self, target):
        return target

    def putStat(self, key, value):
        self._stats[key] = value

class BaseEmail(object):

    __abstract__ = True

    preview = False
    template = None
    isAlert = False

    def __init__(self, user):
        from appCustomizers import AddressReportCustomizer, DefaultPartnerAppCustomizer
        self.user = user
        self.nonce = str(uuid.uuid4())
        partner = self.user.getPartner()
        if partner:
            self.partner = partner
            self.appCustomizer = DefaultPartnerAppCustomizer(self.partner)
        else:
            self.partner = None
            self.appCustomizer = AddressReportCustomizer()

    @classmethod
    def getTestData(cls):
        from rentenna3.models import ndb, User, Partner
        user = User(
            key=ndb.Key(User, 'test'),
            created=datetime.datetime.now(),
            email="test@test.com",
            partner=None,
            firstName='John',
            lastName ='Doe',
        )

        shard=config.CONFIG['EMAIL']['shard']

        partner = Partner(
            apiKey="c26d4cd6-d876-44ba-88ba-3dafa25792ae",
            settings={
                'logo': "/subdomain-image/63c91957-2dd3-44fe-afdf-fdecb8fd161d/",
                'preferredDomain': "https://demopartner-dot-staging-dot-rentenna3.appspot.com/",
                'contact.firstname': "Sally",
                'contact.lastname': "Samson",
                'contact.email': "sally@ardemo.com",
                'contact.phone': "1-555-555-5555",
                'contact.license': "AF289936HYY",
                'contact.website': "http://onboardinformatics.com/",
                'contact.company': "#1 Realty",
                'contact.photo': "/subdomain-image/30d35d9c-ecb9-46fc-afe3-3da10b49e2a7/"
            }
        )

        if shard == 'production':
            partner = Partner.forApiKey("c4619846-82d5-4015-b627-a5e285cf8c8b")
        elif shard == 'staging':
            partner = Partner.forApiKey("e0d73422-27c2-4604-b28a-02bd9b9468ff")
        elif shard == 'qa':
            partner = Partner.forApiKey("a55e6392-faed-4568-96ec-96aa9fe7b423")

        user._partner = partner

        return {
            'user': user,
        }

    @classmethod
    def send(cls, user=None, **kwargs):
        # TODO: probably schedule to occur in bg?
        from rentenna3.models import User
        if user is None:
            user = User.get()
        environment = {
            'user': user,
        }
        environment.update(**kwargs)
        inst = cls(**environment)
        inst._sendEmail()

    def getTags(self):
        tags = []
        tags += self.appCustomizer.getTags()
        # TODO: user tags, like client-id, etc.
        return tags

    def getTemplateContext(self):
        return {
            'user': self.user,
            'otuLink': self._otuLink,
            'appCustomizer': self.appCustomizer,
            'emailUrl': "/email-log/%s/" % self.nonce,
            'unsubscribe': "%s/email-track/unsubscribe/?eid=%s" % (
                config.CONFIG['URL']['BASE'],
                self.nonce,
            )
        }

    def getSubject(self):
        return "A message from AddressReport"

    def renderEmail(self):
        subject = self.getSubject()

        template = self.template
        templateContext = self.getTemplateContext()

        html = flask.render_template(template, **templateContext)

        links = re.findall(r'href=([\'"][^\'" >]+[\'"])', html)
        linkMap = {}
        linkId = 0
        for link in links:
            if '/unsubscribe/' not in link:
                newLink = "\"%s\"" % self._makeLink(re.sub(r'[\'"]', '', link))
                linkId += 1
                linkKey = "\"----LINK%s----\"" % linkId
                linkMap[linkKey] = newLink
                html = html.replace(link, linkKey)

        # inline the css
        html = premailer.transform(html)

        for linkKey, newLink in linkMap.items():
            html = html.replace(linkKey, newLink)

        html += """<img src="%s/email-track/pixel/?eid=%s" />""" % (
            config.CONFIG['URL']['BASE'],
            self.nonce,
        )

        return {
            'html': html,
            'subject': subject,
        }

    def _sendEmail(self):

        if self._isEmailSuppressedByPartner():
            return

        from rentenna3.models import EmailSendLog

        fromEmail = "team@addressreport.com"
        fromName = "AddressReport Team"
        replyTo = None

        if self.partner and self.partner.getSetting("enableReplyTo"):
            replyToEmail = self.partner.getSetting("replyToEmail") or self.partner.getSetting('contact.email')
            if replyToEmail and '@' in replyToEmail:
                replyTo = replyToEmail

        emailFields = self.renderEmail()
        emailFields['fromEmail'] = fromEmail
        emailFields['fromName'] = fromName
        emailFields['toEmail'] = self.user.email
        emailFields['toBcc'] = self.user.bcc
        emailFields['nonce'] = self.nonce

        # TODO: check subscription status
        unsubscribed = (self.user.unsubscribed is not None)
        emailBad = (not self.user.isBriteverifyOk())

        suppressed = emailBad or self.preview
        if self.__class__.isAlert:
            suppressed = suppressed or unsubscribed

        if not suppressed:
            rapi.sendEmail(
                html=emailFields['html'],
                subject=emailFields['subject'],
                fromEmail=emailFields['fromEmail'],
                toEmail=emailFields['toEmail'],
                fromName=emailFields['fromName'],
                toBcc=emailFields['toBcc'],
                replyTo=replyTo,
            )

        EmailSendLog.make(
            nonce=self.nonce,
            suppressed=suppressed,
            userKey=self.user.key,
            emailFields=emailFields,
            template=self.__class__.__name__,
            tags=self.getTags(),
        )

    def _makeLink(self, target):
        if 'mailto:' in target:
            return target

        if '#external' not in target:
            target = self.appCustomizer.decorateUrl(target)

        params = {
            'target': target,
            'eid': self.nonce,
        }
        url = "%s/email-track/click/?%s" % (
            config.CONFIG['URL']['BASE'],
            urllib.urlencode(params),
        )
        return url

    def _otuLink(self, target, duration=72, **data):
        from rentenna3.models import OtuToken, MongoModel
        data['user'] = {
            'key': self.user.key.urlsafe(),
        }
        token = OtuToken(
            data=data,
            expires=datetime.datetime.now() + datetime.timedelta(hours=duration),
        )
        token.put()
        oid = MongoModel.urlsafe(token._id)
        url = rutil.augmentUrl(target, {'otu': oid})
        return jinja2.Markup(url)

    def _isEmailSuppressedByPartner(self):
        if self.user.partner:
            partner = self.user.partner.get()
            if partner and partner.isEmailSuppressed(self.__class__.__name__):
                return True
        return False

class BasePartnerEmail(object):

    __abstract__ = True

    preview = False
    template = None

    def __init__(self, partner, **kwargs):
        from rentenna3.models import Partner
        from appCustomizers import AddressReportCustomizer, DefaultPartnerAppCustomizer
        self.nonce = str(uuid.uuid4())
        self.partner = partner
        self.appCustomizer = DefaultPartnerAppCustomizer(self.partner)
        self.email = self._getEmail()
        self.bcc = None

        if not self.email:
            self.email = kwargs.get('partnerEmail') or ''

    @classmethod
    def getTestData(cls):
        from rentenna3.models import ndb, Partner
        shard=config.CONFIG['EMAIL']['shard']

        partner = Partner(
            # apiKey="c26d4cd6-d876-44ba-88ba-3dafa25792ae",
            settings={
                'logo': "/subdomain-image/63c91957-2dd3-44fe-afdf-fdecb8fd161d/",
                'preferredDomain': "https://demopartner-dot-staging-dot-rentenna3.appspot.com/",
                'contact.firstname': "Sally",
                'contact.lastname': "Samson",
                'contact.email': "sally@ardemo.com",
                'contact.phone': "1-555-555-5555",
                'contact.license': "AF289936HYY",
                'contact.website': "http://onboardinformatics.com/",
                'contact.company': "#1 Realty",
                'contact.photo': "/subdomain-image/30d35d9c-ecb9-46fc-afe3-3da10b49e2a7/"
            },
            key=ndb.Key("SubdomainProperty_V2", "dummyid"),
            name="DemoPartner",
        )

        if shard == 'production':
            partner = Partner.forApiKey("c4619846-82d5-4015-b627-a5e285cf8c8b")
        elif shard == 'staging':
            partner = Partner.forApiKey("e0d73422-27c2-4604-b28a-02bd9b9468ff")
        elif shard == 'qa':
            partner = Partner.forApiKey("a55e6392-faed-4568-96ec-96aa9fe7b423")


        from rentenna3.models import User
        return {
            'partner': partner,
            'user' : User.get(),
            'partnerEmail' : 'arteam@addressreport.com',
        }

    @classmethod
    def send(cls, partner, **kwargs):
        from rentenna3.models import Partner
        environment = {
            'partner': partner,
        }
        environment.update(**kwargs)
        inst = cls(**environment)
        inst._sendEmail()

    def getTemplateContext(self):
        return {
            'appCustomizer': self.appCustomizer,
            'emailUrl': "/partner-email-log/%s/" % self.nonce,
            'otuLink': self._otuLink,
            'partner': self.partner,
            'partnerEmail' : self.email,
            'unsubscribe': "%s/email-track/partner/unsubscribe/?eid=%s" % (
                config.CONFIG['URL']['BASE'],
                self.nonce,
            )
        }

    def getTags(self):
        return [
            'partner:address-report',
            'partner_direct:address-report',
        ]

    def getSubject(self):
        return "A message from AddressReport"

    def renderEmail(self):
        subject = self.getSubject()

        template = self.template
        templateContext = self.getTemplateContext()

        html = flask.render_template(template, **templateContext)

        links = re.findall(r'href=([\'"][^\'" >]+[\'"])', html)
        linkMap = {}
        linkId = 0
        for link in links:
            #if '/unsubscribe/' not in link and '/free-trial/' not in link:
            if '/unsubscribe/' not in link:
                newLink = "\"%s\"" % self._makeLink(re.sub(r'[\'"]', '', link))
                linkId += 1
                linkKey = "\"----LINK%s----\"" % linkId
                linkMap[linkKey] = newLink
                html = html.replace(link, linkKey)

        # inline the css
        html = premailer.transform(html)

        for linkKey, newLink in linkMap.items():
            html = html.replace(linkKey, newLink)

        html += """<img src="%s/email-track/partner/pixel/?eid=%s" />""" % (
            config.CONFIG['URL']['BASE'],
            self.nonce,
        )

        return {
            'html': html,
            'subject': subject,
        }

    def _sendEmail(self):

        if self._isEmailSuppressedByPartner():
            return

        from rentenna3.models import PartnerEmailSendLog

        emailFields = self.renderEmail()
        emailFields['fromEmail'] = "team@addressreport.com"
        emailFields['fromName'] = "AddressReport Team"
        emailFields['toEmail'] = self.email
        emailFields['toBcc'] = self.bcc
        emailFields['nonce'] = self.nonce

        suppressed = self.preview

        if not suppressed:
            rapi.sendEmail(
                html=emailFields['html'],
                subject=emailFields['subject'],
                fromEmail=emailFields['fromEmail'],
                toEmail=emailFields['toEmail'],
                fromName=emailFields['fromName'],
                toBcc=emailFields['toBcc'],
            )

        PartnerEmailSendLog.make(
            nonce=self.nonce,
            suppressed=suppressed,
            partnerKey=self.partner.key,
            emailFields=emailFields,
            template=self.__class__.__name__,
            tags=self.getTags(),
        )

    def _makeLink(self, target):
        if 'mailto:' in target:
            return target

        if '#external' not in target:
            target = self.appCustomizer.decorateUrl(target)

        params = {
            'target': target,
            'eid': self.nonce,
        }
        url = "%s/email-track/partner/click/?%s" % (
            config.CONFIG['URL']['BASE'],
            urllib.urlencode(params),
        )
        return url

    def _otuLink(self, target, duration=72, **data):
        from rentenna3.models import OtuToken, MongoModel
        data['partner'] = {
            'key': self.partner.key.urlsafe(),
        }
        token = OtuToken(
            data=data,
            expires=datetime.datetime.now() + datetime.timedelta(hours=duration),
        )
        token.put()
        oid = MongoModel.urlsafe(token._id)
        url = rutil.augmentUrl(target, {'otu': oid})
        return jinja2.Markup(url)

    def _isEmailSuppressedByPartner(self):
        raise NotImplemented

    def _getEmail(self):
        raise NotImplemented

class BaseArEmail(object):

    __abstract__ = True

    preview = False
    #template = None

    def __init__(self, partner, **kwargs):
        from rentenna3.models import Partner
        from appCustomizers import AddressReportCustomizer, DefaultPartnerAppCustomizer
        self.nonce = str(uuid.uuid4())

        if partner:
            self.appCustomizer = DefaultPartnerAppCustomizer(partner)
        else:
            self.appCustomizer = AddressReportCustomizer()
        self.partner = partner
        self.email = self._getEmail()
        self.bcc = None

    @classmethod
    def getTestData(cls):
        return BasePartnerEmail.getTestData()

    @classmethod
    def send(cls, **kwargs):
        from rentenna3.models import Partner
        environment = {}
        environment.update(**kwargs)
        inst = cls(**environment)
        inst._sendEmail()

    def getTemplate(self):
        raise NotImplemented

    def getTemplateContext(self):
        return {
            'appCustomizer': self.appCustomizer,
            'emailUrl': "/ar-email-log/%s/" % self.nonce,
            'email' : self.email,
        }

    def getTags(self):
        return self.appCustomizer.getTags()

    def getSubject(self):
        return "A message from AddressReport"

    def renderEmail(self):
        subject = self.getSubject()

        template = self.getTemplate()
        templateContext = self.getTemplateContext()

        html = flask.render_template(template, **templateContext)

        # inline the css
        html = premailer.transform(html)

        return {
            'html': html,
            'subject': subject,
        }

    def _sendEmail(self):

        from rentenna3.models import ArEmailSendLog

        emailFields = self.renderEmail()
        emailFields['fromEmail'] = "team@addressreport.com"
        emailFields['fromName'] = "AddressReport Team"
        emailFields['toEmail'] = self.email
        emailFields['toBcc'] = self.bcc
        emailFields['nonce'] = self.nonce

        suppressed = self.preview

        if not suppressed:
            rapi.sendEmail(
                html=emailFields['html'],
                subject=emailFields['subject'],
                fromEmail=emailFields['fromEmail'],
                toEmail=emailFields['toEmail'],
                fromName=emailFields['fromName'],
                toBcc=emailFields['toBcc'],
            )

        partnerKey = None
        if self.partner:
            partnerKey = self.partner.key

        ArEmailSendLog.make(
            nonce=self.nonce,
            suppressed=suppressed,
            partnerKey=partnerKey,
            emailFields=emailFields,
            template=self.__class__.__name__,
            tags=self.getTags(),
        )

    def _getEmail(self):
        return 'team@addressreport.com'

class Badge(object):
    """
        Base class for badges.
    """

    __abstract__ = True

    icon = None
    requires = None
    supports = None

    @classmethod
    def produceBadges(cls, type, target, stats):
        badges = []
        badgesForType = _badges.get(type, []).values()
        for badgeCls in badgesForType:
            args = {}
            satisfies = True
            for requirement in (badgeCls.requires or []):
                if requirement in stats:
                    args[requirement] = stats[requirement]
                else:
                    satisfies = False
            if satisfies:
                badger = badgeCls(
                    type=type,
                    target=target
                )
                badge = badger.badge(**args)
                if badge:
                    badge['icon'] = badger.icon
                    badges.append(badge)
        return badges

    def __init__(self, type, target):
        self.type = type
        self.target = target

    def badge(self, stat):
        raise NotImplemented

class PartnerAlertReporter(object):
    schedule = None
    supports = None
    template = None

    def __init__(self, partner):
        self.partner = partner

    def report(self):
        raise NotImplemented

class ReportCustomizer(object):

    supports = None

    @classmethod
    def generateKwargs(self, type, target, stats, **kwargs):
        customizerCls = (_reportCustomizers.get(type) or {'': None}).values()[0] # yuck
        customizer = customizerCls(target, stats, **kwargs)
        return {
            'allowAlerts': customizer.allowAlerts(),
            'atAGlanceName': customizer.atAGlanceName(),
            'breadcrumbs': customizer.breadCrumbs(),
            'heading': customizer.heading(),
            'jsonPayload': customizer.jsonPayload(),
            'subheading': customizer.subheading(),
            'title': customizer.title(),
        }

    def __init__(self, target, stats, **kwargs):
        self.target = target
        self.stats = stats

    def allowAlerts(self):
        return False

    def atAGlanceName(self):
        return None

    def breadCrumbs(self):
        return []

    def heading(self):
        return None

    def jsonPayload(self):
        return {}

    def subheading(self):
        return None

    def title(self):
        return None

class ReportSection(object):
    """
        Base class for report sections.
    """

    __abstract__ = True

    name = None
    priority = None
    key = None
    supports = None

    @classmethod
    def subsectionMethods(cls):
        if '_directory' not in cls.__dict__:
            directory = []
            for key in dir(cls):
                if not key.startswith("_"):
                    method = getattr(cls, key)
                    if getattr(method, '_isSubsection', False):
                        directory.append(method)
            cls._directory = directory
        return cls._directory

    @classmethod
    def produceSections(cls, type, target, stats, settings=None):
        if settings == None:
            settings = {}
        sections = []

        for sectionCls in _reportSections[type].values():
            section = sectionCls(type, target, stats)
            settingNamePrefix = 'suppression.%s.%s' % (type, section.name)
            if section.produceSubsections(settingNamePrefix=settingNamePrefix, settings=settings):
                sections.append(section)

        sections = sorted(sections, key=(lambda x: x.priority))
        return sections

    def __init__(self, type, target, stats):
        self.subsections = {}
        self.type = type
        self.target = target
        self.stats = stats

    def generateDescription(self):
        return None

    def produceSubsections(self, settingNamePrefix='', settings=None):
        if settings == None:
            settings = {}
        for subsectionMethod in self.subsectionMethods():
            try:
                context = subsectionMethod(self)
            except:
                logging.error(traceback.format_exc())
                context = None
            if (context) and (settings.get('%s.%s' % (settingNamePrefix, subsectionMethod._name), False) is not True):
                self.subsections[subsectionMethod._name] = context
        if self.subsections:
            return True

    def render(self, renderFullReport, **args):
        try:
            context = {
                'description': self.generateDescription(),
                'subsections': self.subsections,
                'renderFullReport': renderFullReport,
                'target': self.target,
            }
            return flask.render_template(self.template, **context)
        except Exception as e:
            logging.error("== REPORT SECTION ERROR ==")
            logging.error(traceback.format_exc())
            return ""

def subsection(name, displayName=""):

    def dec(method):
        method._isSubsection = True
        method._name = name
        method._displayName = displayName
        return method
    return dec

# application methods

def applySupportsObjects(module, subcls, dict):
    for cls in rutil.getSubclasses(module, subcls):
        for support in rutil.listify(cls.supports):
            forType = dict.setdefault(support, {})
            forType[cls.__name__] = cls

def applyAlerts(module):
    applySupportsObjects(module, AlertReporter, _alertReporters)

def applyHybridAlerts(module):
    applySupportsObjects(module, AlertReporter, _hybridAlertReporters)

def applyPartnerAlerts(module):
    applySupportsObjects(module, PartnerAlertReporter, _partnerAlertReporters)

def applyBadges(module):
    applySupportsObjects(module, Badge, _badges)

def applyEmails(module):
    # Call this method to add all reporters in the module
    for cls in rutil.getSubclasses(module, BaseEmail):
        _emails[cls.__name__] = cls

    for cls in rutil.getSubclasses(module, BasePartnerEmail):
        _emails[cls.__name__] = cls

def applyQuickReporters(module):
    applySupportsObjects(module, BaseQuickReporter, _quickReporters)

def applyReporters(module):
    applySupportsObjects(module, BaseReporter, _reporters)

def applyReportCustomizers(module):
    applySupportsObjects(module, ReportCustomizer, _reportCustomizers)

def applyReportDescriptors(module):
    applySupportsObjects(module, BaseReportDescriptor, _reportDescriptors)

def applyReportSections(module):
    applySupportsObjects(module, ReportSection, _reportSections)

# report mega-object

class Report(object):

    def __init__(
            self,
            type,
            city,
            key,
            target,
            forceRecompute=False,
            isPrecompute=False,
            doMinimal=False,
            limitReporter=None,
        ):
        self.type = type
        self.city = city
        self.key = key
        self.target = target
        self.forceRecompute = forceRecompute
        self.isPrecompute = isPrecompute
        self.doMinimal = doMinimal
        self.limitReporter = limitReporter

        self.reporters = self._getRelevantReporters()
        self.existingStatSets = self._getExistingStatSets()
        self.reportersByClass = self._classifyReporters()
        self.existingStatSets.update(self._runSynchronousReporters())

    def getCompletedReporters(self):
        return [
            reporter.getJson()
            for reporter
            in (
                self.reportersByClass['done']
                + self.reportersByClass['now']
            )
        ]

    def getPendingReporters(self):
        return [
            reporter.getJson()
            for reporter
            in self.reportersByClass['later']
        ]

    def getStats(self):
        if not hasattr(self, '_stats'):
            self._stats = self._getStats()
        return self._stats

    def produceBadges(self):
        return Badge.produceBadges(
            type=self.type,
            target=self.target,
            stats=self.getStats(),
        )

    def produceCustomizerKwargs(self, **kwargs):
        return ReportCustomizer.generateKwargs(
            type=self.type,
            target=self.target,
            stats=self.getStats(),
            **kwargs
        )

    def produceDescriptors(self):
        return BaseReportDescriptor.generateDescriptors(
            type=self.type,
            target=self.target,
            stats=self.getStats(),
        )

    def produceReportSections(self, settings):
        return ReportSection.produceSections(
            type=self.type,
            target=self.target,
            stats=self.getStats(),
            settings=settings,
        )

    def runReporter(self, name):
        reporter = _reporters[self.type].get(name)
        return self._runReporter(reporter)

    def _classifyReporters(self):
        reportersToRunNow = []
        reportersToRunLater = []
        completedReporters = []
        for reporter in self.reporters:
            stat = self.existingStatSets.get(reporter.__name__)
            if stat:
                completedReporters.append(reporter)
            elif reporter.minimal:
                reportersToRunNow.append(reporter)
            elif (self.isPrecompute == reporter.precompute):
                reportersToRunLater.append(reporter)
            elif (self.isPrecompute != reporter.onDemand):
                reportersToRunLater.append(reporter)

        if not self.doMinimal:
            reportersToRunLater += reportersToRunNow
            reportersToRunNow = []

        return {
            'done': completedReporters,
            'now': reportersToRunNow,
            'later': reportersToRunLater,
        }

    def _getExistingStatSets(self):
        from rentenna3.models import ReportStat

        if self.limitReporter:
            limitReporterClass = _reporters[self.type].get(self.limitReporter)
            reporterNames = limitReporterClass.requireReporters
        else:
            reporterNames = None

        stats = {}
        if not self.forceRecompute:
            now = datetime.datetime.now()
            existingReportStats = ReportStat.getExisting(
                self.type,
                self.key,
                reporterNames,
            )
            for reporter in self.reporters:
                stat = existingReportStats.get((
                    reporter.__name__,
                    reporter.version,
                ))
                if stat:
                    if (not reporter.expires) or (
                            reporter.expires > (now - stat.generated)):
                        stats[reporter.__name__] = stat

        return stats

    def _getRelevantReporters(self):
        reporters = BaseReporter.getReporters(self.type)
        reporters = [
            reporter
            for reporter
            in reporters
            if (
                ((reporter.cities is None) or (self.city.slug in reporter.cities))
                and ((reporter.states is None) or (self.city.state in reporter.states))
            )
        ]
        return reporters

    def _getStats(self):
        stats = {}
        for statSet in self.existingStatSets.values():
            stats.update(statSet.stats)
        BaseQuickReporter.augmentStats(self.type, self.target, stats)
        return stats

    def _runReporter(self, reporter):
        # TODO: what if we require other stats?
        kwargs = {}

        reporterInstance = reporter(self.target)

        hasAllRequiredStats = True
        existingStats = self._getStats()
        if reporterInstance.requireStats:
            for stat in reporterInstance.requireStats:
                if stat in existingStats:
                    kwargs[stat] = existingStats.get(stat)
                else:
                    hasAllRequiredStats = False

        if hasAllRequiredStats:
            reporterInstance.report(**kwargs)
            stats = reporterInstance.getStats()

            from rentenna3.models import ReportStat
            return ReportStat.create(
                self.type,
                self.key,
                reporter.__name__,
                reporter.version,
                stats,
            )

    def _runSynchronousReporters(self):
        results = {}
        for reporter in self.reportersByClass['now']:
            logging.info('running minimal reporter %s' % reporter.__name__)
            try:
                stats = self._runReporter(reporter)
                results[reporter.__name__] = stats
            except:
                logging.error(traceback.format_exc())
        return results
