import cloudstorage
import flask
import logging
import random
import re
import uuid
import math

from google.appengine.api import memcache
from google.appengine.ext import ndb

from web import rutil
from web import taskqueue
from web import tracking
from web import validate
from web import api as rapi
from web.api import mailchimp
from web.base import BaseView, Route
from web.base import resource, ResponseException
from web.quiz.quizModels import Quiz
from web import config

from rentenna3 import api
from rentenna3 import geocoder
from rentenna3 import util
from rentenna3.models import *
from rentenna3.base import ReportSection
from rentenna3.base import Badge
from rentenna3.email import *
from urllib2 import urlparse

class AboutView(BaseView):

    @Route('/about/')
    def get(self):
        response = flask.render_template('client/aboutView.jinja2',
            suppressInspectlet=True,
        )
        return response

class AlertTableView(BaseView):

    @Route('/report/property/<citySlug>/<addressSlug>/alert-table/filth/')
    def getPropertyFilthAlertTable(self, citySlug, addressSlug):

        stat, address = self.getNearbyComplaints(
            Nyc311CallModel.getNearestFilthComplaints,
            addressSlug,
            citySlug,
        )

        return flask.render_template('client/propertyAlertTableView.jinja2',
            address=address,
            stat=stat,
            topic= "Filth",
        )

    @Route('/report/property/<citySlug>/<addressSlug>/alert-table/noise/')
    def getPropertyNoiseAlertTable(self, citySlug, addressSlug):

        stat, address = self.getNearbyComplaints(
            Nyc311CallModel.getNearestNoiseComplaints,
            addressSlug,
            citySlug,
        )

        return flask.render_template('client/propertyAlertTableView.jinja2',
            address=address,
            stat=stat,
            topic= "Noise",
        )

    @Route('/report/property/<citySlug>/<addressSlug>/alert-table/rodent/')
    def getPropertyRodentAlertTable(self, citySlug, addressSlug):

        stat, address = self.getNearbyComplaints(
            Nyc311CallModel.getNearestRodentComplaints,
            addressSlug,
            citySlug,
        )

        return flask.render_template('client/propertyAlertTableView.jinja2',
            address=address,
            stat=stat,
            topic= "Rodent",
        )

    @Route('/report/property/<citySlug>/<addressSlug>/alert-table/street/')
    def getPropertyStreetAlertTable(self, citySlug, addressSlug):

        stat, address = self.getNearbyComplaints(
            Nyc311CallModel.getNearestStreetComplaints,
            addressSlug,
            citySlug,
        )

        return flask.render_template('client/propertyAlertTableView.jinja2',
            address=address,
            stat=stat,
            topic= "Street",
        )

    def getNearbyComplaints(self, complaintMethod, addressSlug, citySlug):
        address = Address.getBySlug(addressSlug)
        city = City.forSlug(citySlug)

        if city is None or city.isOther():
            city = address.getCity()

        distance = city.getDistance('area')['distance']

        stat = complaintMethod(
            address.location,
            distance,
            daysBack=30,
        )

        stat = sorted(stat, key=lambda x: x.created_date, reverse=True)

        return stat, address

class BingSiteAuth(BaseView):

    @Route('/BingSiteAuth.xml')
    def process(self):
        return """<?xml version="1.0"?>
            <users>
                <user>1BF3B33C9A0E891034AE91307EFE41DB</user>
            </users>
        """

class BlogView(BaseView):

    @Route('/blog/')
    def listPage(self):
        page = validate.get('page', validate.ParseInt(), validate.DefaultValue(1))
        blogEntryQuery = BlogPost.query()\
            .filter(BlogPost.postType == 'blog')\
            .filter(BlogPost.status == 'publish')\
            .filter(BlogPost.date <= datetime.datetime.now())\
            .order(-BlogPost.date)
        total = blogEntryQuery.count()
        pageInfo = rutil.ndbPaginate(page, 5, blogEntryQuery)
        return flask.render_template('client/blogList.jinja2',
            blogEntries=pageInfo['results'],
            pageInfo=pageInfo,
            title="AddressReport Blog Page %s" % page,
            suppressInspectlet=True,
        )

    @Route('/blog/<slug>/')
    def get(self, slug):
        blogEntry = BlogPost.forSlug(slug)
        if blogEntry is None:
            flask.abort(404)
        publicTitle = blogEntry.seoTitle or blogEntry.title
        return flask.render_template('client/blogPost.jinja2',
            blogEntry=blogEntry,
            title="%s - AddressReport Blog" % publicTitle,
            facebookShare=self.getFacebookShare(blogEntry),
            twitterShare=self.getTwitterShare(blogEntry),
            suppressInspectlet=True,
        )

    @Route('/blog/close.html')
    def closeModal(self):
        return """
            <script type='text/javascript'>
               window.open('','_self','');
               window.close();
               window.location = 'https://www.addressreport.com/';
            </script>
        """

    def getFacebookShare(self, post):
        params = {
            'app_id': "192306390814374",
            'title': "AddressReport",
            'redirect_uri': "https://www.addressreport.com/blog/close.html",
            'display': "popup",
            'link': "https://www.addressreport.com" + post.getLink(),
            'caption': "https://www.addressreport.com" + post.getLink(),
        }
        return "https://www.facebook.com/dialog/feed?%s" % urllib.urlencode(params)

    def getTwitterShare(self, post):
        params = {
            'via': "AddressReport",
            'url': "https://www.addressreport.com" + post.getLink(),
            'text': post.title,
        }
        return "https://twitter.com/intent/tweet?%s" % urllib.urlencode(params)

class CityJson(BaseView):

    @Route('/city-json/<city>.json')
    def process(self, city):
        from cloudstorage.errors import NotFoundError
        filepath = "/rentenna-data/cities3/%s.json" % city
        try:
            file = cloudstorage.open(filepath, 'r')
            return flask.Response(file, mimetype='text/json')
        except NotFoundError:
            flask.abort(404)

class ContactView(BaseView):

    @Route('/contact/')
    def get(self):
        return flask.render_template('client/contactView.jinja2',
            suppressInspectlet=True,
        )

class EmailView(BaseView):
    @Route('/email-log/<nonce>/')
    def emailView(self, nonce):
        email = EmailSendLogContent.queryFirst({'nonce': nonce})
        if email:
            return email['html']
        else:
            return "Can not find the email."

    @Route('/partner-email-log/<nonce>/')
    def partnerEmailView(self, nonce):
        email = PartnerEmailSendLogContent.queryFirst({'nonce': nonce})
        if email:
            return email['html']
        else:
            return "Can not find the email."

    @Route('/ar-email-log/<nonce>/')
    def arEmailView(self, nonce):
        email = ArEmailSendLogContent.queryFirst({'nonce': nonce})
        if email:
            return email['html']
        else:
            return "Can not find the email."

class EmailTrack(BaseView):

    @Route('/email-track/click/')
    def click(self):
        nonce = validate.get('nonce') or validate.get('eid')
        target = validate.get('target') or config.CONFIG['URL']['BASE']

        if not self.isFromPreview():
            EmailSendLog.update(
                {
                    'nonce': nonce
                },
                {
                    '$push': {
                        'msgcl': {
                            'nonce': nonce,
                            'useragent': flask.request.user_agent.string,
                            'target': target,
                        }
                    },
                    '$inc': {
                        'msgclc': 1
                    },
                    '$set': {
                        'msgclb': True,
                    }
                }
            )

        return flask.redirect(target)

    @Route('/email-track/pixel/')
    def pixel(self):
        nonce = validate.get('nonce') or validate.get('eid')

        if not self.isFromPreview():
            EmailSendLog.update(
                {
                    'nonce': nonce
                },
                {
                    '$push': {
                        'msgop': {
                            'nonce': nonce,
                            'useragent': flask.request.user_agent.string
                        }
                    },
                    '$inc': {
                        'msgopc': 1
                    },
                    '$set': {
                        'msgopb': True,
                    }
                }
            )

        response = flask.Response(
            base64.b64decode("R0lGODdhAQABAIAAAPxqbAAAACwAAAAAAQABAAACAkQBADs="),
            status=200,
            mimetype="image/gif",
        )
        return response

    @Route('/email-track/unsubscribe/')
    def unsubscribe(self):
        now = datetime.datetime.now()

        nonce = validate.get('nonce') or validate.get('eid')
        sendLog = EmailSendLog.queryFirst({'nonce': nonce})
        sendLog.unsubscribed = now # TODO: atomic update?
        sendLog.put()

        user = sendLog.getUser()
        user.unsubscribed = now
        user.put()

        return flask.redirect("/unsubscribe/")

    def isFromPreview(self):
        referrer = flask.request.referrer
        if referrer:
            isPreview = ('/admin/email-log/' in referrer) or \
                ('/admin/partner-email-log/' in referrer) or \
                ('/dashboard/email-log/' in referrer) or \
                ('/dashboard/partner-email-log' in referrer) or \
                ('/ar-email-log/' in referrer)
            return isPreview

class PartnerEmailTrack(BaseView):

    @Route('/email-track/partner/click/')
    def click(self):
        nonce = validate.get('nonce') or validate.get('eid')
        target = validate.get('target') or config.CONFIG['URL']['BASE']

        if not self.isFromPreview():
            PartnerEmailSendLog.update(
                {
                    'nonce': nonce
                },
                {
                    '$push': {
                        'msgcl': {
                            'nonce': nonce,
                            'useragent': flask.request.user_agent.string,
                            'target': target,
                        }
                    },
                    '$inc': {
                        'msgclc': 1
                    },
                    '$set': {
                        'msgclb': True,
                    }
                }
            )

        return flask.redirect(target)

    @Route('/email-track/partner/pixel/')
    def pixel(self):
        nonce = validate.get('nonce') or validate.get('eid')

        if not self.isFromPreview():
            PartnerEmailSendLog.update(
                {
                    'nonce': nonce
                },
                {
                    '$push': {
                        'msgop': {
                            'nonce': nonce,
                            'useragent': flask.request.user_agent.string
                        }
                    },
                    '$inc': {
                        'msgopc': 1
                    },
                    '$set': {
                        'msgopb': True,
                    }
                }
            )

        response = flask.Response(
            base64.b64decode("R0lGODdhAQABAIAAAPxqbAAAACwAAAAAAQABAAACAkQBADs="),
            status=200,
            mimetype="image/gif",
        )
        return response

    @Route('/email-track/partner/unsubscribe/')
    def partnerUnsubscribe(self):
        now = datetime.datetime.now()

        nonce = validate.get('nonce') or validate.get('eid')
        sendLog = PartnerEmailSendLog.queryFirst({'nonce': nonce})
        sendLog.unsubscribed = now # TODO: atomic update?
        sendLog.put()

        partner = sendLog.getPartner()
        template = sendLog.template
        if template == 'PartnerPerformanceSummary':
            partner.settings.pop('notificationEmail', None)
            partner.put()
        elif template == 'PartnerNewLead':
            partner.settings.pop('leadEmail', None)
            partner.put()

        #TODO should be partner admin page?
        return flask.redirect("/unsubscribe/")

    def isFromPreview(self):
        referrer = flask.request.referrer
        if referrer:
            isPreview = ('/admin/email-log/' in referrer) or \
                ('/admin/partner-email-log/' in referrer) or \
                ('/dashboard/email-log/' in referrer) or \
                ('/dashboard/partner-email-log' in referrer)
            return isPreview

class FaqView(BaseView):

    @Route('/faq/')
    def get(self):
        return flask.render_template('client/faqView.jinja2')

class FaviconView(BaseView):

    @Route('/favicon.ico')
    def process(self):
        return flask.redirect(resource('/image/favicon.ico'), code=301)

class FindView(BaseView):

    @Route('/find-anything/')
    def findAnything(self):
        type = validate.get('type')
        components = validate.get('components', validate.ParseJson()) or {}
        stateOptions = [["","Not Specified"]]
        for state in State.all():
            stateOptions.append([state.abbr, state.name.upper()])
        return flask.render_template('client/findAnything.jinja2',
            type=type,
            components=components,
            stateOptions=stateOptions,
            require=util.getRequire(),
        )

    @Route('/find/')
    def findSearch(self):
        types = validate.get('types', validate.ParseJson())\
            or ['address', 'neighborhood', 'city', 'zip']

        bias = validate.get('bias', validate.ParseJson())
        if not bias:
            locationFromHeader = flask.request.headers.get('X-AppEngine-CityLatLong')
            if locationFromHeader:
                latLong = locationFromHeader.split(",")
                bias = {
                    'type': "Point",
                    'coordinates': [
                        float(latLong[1]),
                        float(latLong[0]),
                    ]
                }

        for type in types:
            result, components = geocoder.geocode({
                'query': validate.get('query') or validate.get('textQuery'),
                'address': validate.get('address'),
                'streetNumber': validate.get('streetNumber'),
                'street': validate.get('street'),
                'neighborhood': validate.get('neighborhood'),
                'city': validate.get('city'),
                'state': validate.get('state'),
                'zip': validate.get('zip'),
                'location': validate.get('location', validate.ParseJson()),
                'bias': bias,
                'type': type,
            })
            if result:
                return flask.redirect(result.getUrl())
        else:
            flask.abort(404)

    @Route('/find-address/')
    def findAddress(self):
        require = util.getRequire()
        address, components = geocoder.geocode({
            'query': validate.get('query') or validate.get('textQuery'),
            'streetNumber': validate.get('streetNumber'),
            'street': validate.get('street'),
            'city': validate.get('city'),
            'state': validate.get('state'),
            'zip': validate.get('zip'),
            'type': 'address',
        })
        if address is None:
            return flask.redirect('/find-anything/?%s' % urllib.urlencode({
                'type': 'address',
                'components': json.dumps(components),
                'require': require,
            }))
        #return flask.redirect(address.getUrl(require=require))
        return self.buildResponse(address.getUrl(require=require), require=require)

    @Route('/find-city/')
    def findCity(self):
        require = util.getRequire()
        city, components = geocoder.geocode({
            'query': validate.get('query'),
            'city': validate.get('city'),
            'state': validate.get('state'),
            'zip': validate.get('zip'),
            'location': validate.get('location', validate.ParseJson()),
            'type': 'city',
        })
        if city is None:
            return flask.redirect('/find-anything/?%s' % urllib.urlencode({
                'type': 'city',
                'components': json.dumps(components),
                'require': require,
            }))
        #return flask.redirect(city.getUrl(require=require))
        return self.buildResponse(city.getUrl(require=require), require=require)

    @Route('/find-neighborhood/')
    def findNeigborhood(self):
        require = util.getRequire()
        neighborhood, components = geocoder.geocode({
            'query': validate.get('query'),
            'neighborhood': validate.get('neighborhood'),
            'city': validate.get('city'),
            'state': validate.get('state'),
            'zip': validate.get('zip'),
            'location': validate.get('location', validate.ParseJson()),
            'type': 'neighborhood',
        })
        if neighborhood is None:
            return flask.redirect('/find-anything/?%s' % urllib.urlencode({
                'type': 'neighborhood',
                'components': json.dumps(components),
                'require': require,
            }))
        #return flask.redirect(neighborhood.getUrl(require=require))
        return self.buildResponse(neighborhood.getUrl(require=require), require=require)

    @Route('/find-zipcode/')
    def findZipcode(self):
        require = util.getRequire()
        area, components = geocoder.geocode({
            'query': validate.get('query'),
            'zip': validate.get('zip'),
            'type': 'zip',
        })
        if area is None:
            return flask.redirect('/find-anything/?%s' % urllib.urlencode({
                'type': 'zipcode',
                'components': json.dumps(components),
                'require': require,
            }))
        #return flask.redirect(area.getUrl(require=require))
        return self.buildResponse(area.getUrl(require=require), require=require)

    def buildResponse(self, url, require=None):
        rst = flask.redirect(url)
        if require == 'subscribe':
            response = flask.make_response(rst)
            response.set_cookie(key='rsb', value='1')
            return response
        return rst
    
class GotoUrl(BaseView):

    @Route('/goto-url/')
    def go(self):
        apiKey = validate.get('api_key')
        if apiKey:
            flask.session['api_key'] = apiKey
        url = validate.get('url')
        hashTag = validate.get('hash_tag')
        if hashTag:
            url = '%s#%s' % (url, hashTag)
        return flask.redirect(url)

class LogoutView(BaseView):

    @Route('/log-out/')
    def logOut(self):
        User.logout()
        return flask.redirect('/')

class MovotoIframe(BaseView):

    @Route('/embed/movoto-iframe/')
    def get(self):
        return flask.render_template('embed/movotoIframe.jinja2')

    @Route('/embed/movoto-iframe/inject.js')
    def inject(self):
        return flask.Response("""
            (function() {
                var addressComponents = {};
                var match = document.querySelectorAll('[itemprop="streetAddress"]')[0];
                if(match != null) {
                    addressComponents.address = match.textContent;
                }
                var match = document.querySelectorAll('[itemprop="addressRegion"]')[0];
                if(match != null) {
                    addressComponents.state = match.textContent;
                }
                var match = document.querySelectorAll('[itemprop="addressLocality"]')[0];
                if(match != null) {
                    addressComponents.city = match.textContent;
                }
                var match = document.querySelectorAll('[itemprop="postalCode"]')[0];
                if(match != null) {
                    addressComponents.zip = match.textContent;
                }
                var link = document.getElementById('__address__report__link__');
                var iframe = document.createElement("IFRAME");
                iframe.setAttribute('src', "https://www.addressreport.com/embed/movoto-iframe/#" + JSON.stringify(addressComponents));
                iframe.setAttribute('width',"300");
                iframe.setAttribute('height',"250");
                iframe.setAttribute('frameborder', "0");
                link.parentNode.replaceChild(iframe, link);
            })();
        """, mimetype="text/javascript")

class NeighborhoodJson(BaseView):

    @Route('/nh-json/<city>.json')
    def process(self, slug):
        from cloudstorage.errors import NotFoundError
        filepath = "/rentenna-data/nh3/%s.json" % slug
        try:
            file = cloudstorage.open(filepath, 'r')
            return flask.Response(file, mimetype='text/json')
        except NotFoundError:
            flask.abort(404)

class ObiRedirector(BaseView):

    @Route('/obi/<obiId>/')
    def redirect(self, obiId):
        localType = None
        field = None

        # special case
        if obiId == 'PL3651000':
            return flask.redirect('/report/city/manhattan-ny/')

        field = 'obId'
        if obiId.startswith("NH"):
            localType = Area
            
        if obiId.startswith("ZI") or obiId.startswith('PZ'):
            localType = ZipcodeArea
            obiId = obiId.replace('PZ', 'ZI')

        if obiId.startswith("PL") or obiId.startswith("CS"):
            localType = City

        target = localType.queryFirst({field: obiId})
        if target:
            return flask.redirect(target.getUrl())

        apiResponse = api.obiCommunityById(obiId)
        if apiResponse:
            location = {
                'type': "Point",
                'coordinates': [
                    float(apiResponse.data['longitude']),
                    float(apiResponse.data['latitude']),
                ],
            }
            target = localType.queryGeoref(location)
            if target:
                return flask.redirect(target[0].getUrl())

        flask.abort(404)

class ProfileView(BaseView):

    @Route('/profile/')
    def process(self):
        return flask.render_template('client/profileView.jinja2',
            suppressInspectlet=True,
        )

    @Route('/profile/', methods=['POST'])
    def update(self):
        if validate.get('action') == 'password':
            user = User.get()
            if user.checkPassword(flask.request.values.get('current')):
                user.setPassword(flask.request.values.get('new'))
                user.put()
                return flask.render_template('client/profileView.jinja2',
                    passwordChanged=True
                )
            else:
                return flask.render_template('client/profileView.jinja2',
                    passwordWrong=True
                )
        else: # must be info
            user = User.get()
            email = flask.request.values.get('email').lower()
            if user.email != email:
                existing = User.forEmail(email)
                if existing:
                    return flask.render_template('client/profileView.jinja2',
                        emailExists=True
                    )
                else:
                    user.email = email
            user.put()
            return flask.render_template('client/profileView.jinja2',
                infoChanged=True
            )

class QuizView(BaseView):

    @Route('/quiz/')
    def getBaseQuiz(self):
        creativeID = validate.get('creative_id')
        url = '/quiz/standard/'
        if creativeID:
            url = '%s?creative_id=%s' % (url, creativeID)
        return flask.redirect(url)

    @Route('/quiz/<slug>/')
    def getQuiz(self, slug):
        creativeID = validate.get('creative_id')

        hasCreative = False
        creativeUrl = None
        if creativeID:
            hasCreative = True
            baseUrl = 'https://storage.googleapis.com/rentenna-creative'
            creativeUrl = '%s/%s.%s' % (baseUrl, creativeID, 'png')
            if '.' in creativeID:
                creativeUrl = '%s/%s' % (baseUrl, creativeID)
        
        extraParamsStr = urllib.urlencode({
            'source' : validate.get('source') or '',
            'reference' : validate.get('reference') or '',
        })

        if extraParamsStr:
            extraParamsStr = '?%s' % extraParamsStr

        quiz = Quiz.query().filter(Quiz.slug == slug).get()
        thankyouUrl = '/quiz-thank-you/'
        isArThankyou = True
        if quiz.thankyou and quiz.thankyou.strip():
            thankyouUrl = quiz.thankyou
            isArThankyou = False

        flask.session['quizReferrer'] = flask.request.referrer
        return flask.render_template('client/quiz.jinja2',
            quiz=quiz,
            hasCreative=hasCreative,
            creativeUrl=creativeUrl,
            headerOptions={
                'suppressAddressAutocomplete' : True,
                'suppressLogoLink' : True,
                'suppressNav' : True,
            },
            endpoint='/submit-quiz-answers/%s' % extraParamsStr,
            thankyouUrl=thankyouUrl,
            isArThankyou=isArThankyou
        )

    @Route('/quiz-thank-you/')
    def quizThankYou(self):
        sessionId = validate.get('sessionId')
        quizAnswers = QuizAnswers.get_by_id(sessionId)
        quiz = Quiz.query().filter(Quiz.slug == quizAnswers.slug).get()
        return flask.render_template('client/quizThankYou.jinja2',
            addressRelationship=quizAnswers.answers.get('address-relationship'),
            title="Check Your Email For Your Address Report",
            embeddedThankYouUrl=util.strip(quiz.embeddedThankYouUrl),
            embeddedThankYouUrlText = util.strip(quiz.embeddedThankYouUrlText),
            headerOptions={
                'suppressAddressAutocomplete' : True,
                'suppressLogoLink' : True,
                'suppressNav' : True,
            }
        )

    @Route('/submit-quiz-answers/', methods=['POST'])
    def submitQuizAnswers(self):
        answers = validate.get('answers', validate.ParseJson())
        slug = validate.get('slug')
        firstName = answers.get('firstName')
        lastName = answers.get('lastName')
        phoneNumber = answers.get('phoneNumber')
        email = answers.get('email')
        sessionId = answers.get('sessionId')
        alertSignup = answers.get('alertSignup')
        tracker = tracking.get().key
        address = None
        user = None
        final = validate.get('final', validate.ParseBool())
        deliver = validate.get('deliver', validate.ParseBool())
        source = validate.get('source')
        reference = validate.get('reference')

        quizAnswers = QuizAnswers.get_by_id(sessionId)
        if not quizAnswers:
            quizAnswers = QuizAnswers(
                id=sessionId,
                tracker=tracker,
                slug=slug,
            )

        referr = flask.session.get('quizReferrer', None)
        if referr:
            quizAnswers.referringUrl = referr
            flask.session.pop('quizReferrer')

        quizDataMerge = {}
        if not firstName and not lastName:
            name = answers.get('name')
            if name:
                nameParts = re.split('\s+', name)
                num = len(nameParts)
                if num == 1:
                    firstName = name
                else:
                    firstName = nameParts.pop(0)
                    lastName = " ".join(nameParts)

        if not phoneNumber:
            phoneNumber = answers.get('phone')

        isNewUser = False
        reportUrl = None
        addressSlug = None
        userKey = None
        geocodedAddress = None
        if email:
            user = User.forEmail(email)
            if not user:
                savedAnswers = quizAnswers.answers
                if not firstName:
                    firstName = savedAnswers.get('firstName', '')
                if not lastName:
                    lastName = savedAnswers.get('lastName', '')
                if not phoneNumber:
                    phoneNumber = savedAnswers.get('phoneNumber', '')

                isNewUser = True
                #user = User.getOrRegisterEmailOnly(email)
                user = User.get()
                user = User.simpleUser(
                    user, 
                    email, 
                    context='quiz', 
                    sendEmail=True,
                    firstName=firstName,
                    lastName=lastName,
                    phone=phoneNumber
                )

            userKey = user.key
            userKeyUrlSafe = user.key.urlsafe()

            if not alertSignup:
                quizDataMerge['alertSignup'] = True
                address = answers.get('address')
                if not address and quizAnswers.answers:
                    address = quizAnswers.answers.get('address')

                if address:
                    addressInfo = json.loads(address)
                    address, components = geocoder.geocodeText(addressInfo['name'])
                    if address:
                        addressObj = Address.getBySlug(address['slug'])
                        canonicalAddress = addressObj.getCanonicalAddress()
                        propertyKey = ndb.Key(Property, canonicalAddress['slug'])
                        AlertSubscription.subscribe(
                            propertyKey,
                            mode='report-generated',
                            user=user,
                            quizSlug=slug,
                            quiz=True,
                        )
                        addressSlug = addressObj.slug
                        reportUrl = addressObj.getUrl(domain=True)
                        geocodedAddress = Address.simpleForm(addressObj)
                        
                        if not user.street:
                            user.setAddressInfo(address, addressFrom='quiz')
                            user.put()
                    else:
                        InvalidPropertyAlertSubscription.send()
                else:
                    InvalidPropertyAlertSubscription.send()
        else:
            userKey = None
            userKeyUrlSafe = None

        if phoneNumber or firstName or lastName:
            answers = answers or quizAnswers.answers
            if phoneNumber:
                answers['phoneNumber'] = phoneNumber
            if firstName:
                answers['firstName'] = firstName
            if lastName:
                answers['lastName'] = lastName

            if user and not isNewUser:
                if phoneNumber:
                    user.phone = phoneNumber
                if firstName:
                    user.firstName = firstName
                if lastName:
                    user.lastName = lastName
                user.put()

        if addressSlug:
            answers['addressSlug'] = addressSlug

        if reportUrl:
            answers['reportUrl'] = reportUrl

        if geocodedAddress:
            quizAnswers.geocodedAddress = geocodedAddress

        quizAnswers.answers = answers

        if userKey:
            quizAnswers.user = userKey

        if isNewUser:
            quizAnswers.isNewUser = True
        if source:
            quizAnswers.source = source
        if reference:
            quizAnswers.reference = reference
        if final:
            quizAnswers.finished = True

        quizAnswers.put()

        if isNewUser:
            PartnerNewLead.sendAsNeeded(
                user=user,
                reportUrl=reportUrl,
                quizAnswerKey = quizAnswers.key.urlsafe(),
            )

        response = {'quizDataMerge': quizDataMerge}
        if user:
            response['user'] = user.private()

        if deliver:
            taskqueue.add(
                '/background/deliver-lead/',
                params={
                    'quizAnswers': quizAnswers.key.urlsafe(),
                }
            )

        return flask.jsonify(response)

class ReportBlock(BaseView):

    @Route('/send-me/city/<citySlug>/')
    def cityBlock(self, citySlug):
        city = City.forSlug(citySlug)

        #TODO: remove it at what time?
        #TODO: do we need this at all since /send-me/ is triggered by wizard or thirdparty link. 
        # we don't have client for it yet.
        if city is None:
            citySlug = _getNewCitySlug(citySlug)
            if citySlug is not None:
                return flask.redirect('/send-me/city/%s/' % citySlug, code=301)

        if (city is None):
            flask.abort(404)
        return flask.render_template(
            'client/mockProcessing.jinja2',
            target=city.getUrl(domain=True),
            commonName=city.name,
            type='city',
        )

    @Route('/send-me/neighborhood/<citySlug>/<areaSlug>/')
    def neighborhoodBlock(self, citySlug, areaSlug):
        neighborhood = Area.forSlug(areaSlug)
        if (neighborhood is None):
            flask.abort(404)
        return flask.render_template(
            'client/mockProcessing.jinja2',
            target=neighborhood.getUrl(domain=True),
            commonName=neighborhood.name,
            type='neighborhood',
        )

    @Route('/send-me/property/<citySlug>/<addressSlug>/')
    def propertyBlock(self, citySlug, addressSlug):
        address = Address.getBySlug(addressSlug)
        if address is None:
            address = geocoder.getAddressBySlugWorkaround(addressSlug)
        if (address is None):
            flask.abort(404)
        return flask.render_template(
            'client/mockProcessing.jinja2',
            target=address.getUrl(domain=True),
            commonName=address.getShortName(),
            type='property',
        )

    @Route('/send-me/zip/<citySlug>/<areaSlug>/')
    def zipBlock(self, citySlug, areaSlug):
        area = ZipcodeArea.forSlug(areaSlug)
        if area is None:
            flask.abort(404)
        return flask.render_template(
            'client/mockProcessing.jinja2',
            target=area.getUrl(domain=True),
            commonName=area.slug,
            type='zipcode',
        )

    @Route('/send-me-report-subscribe/', methods=['POST'])
    def sendMeReport(self):
        email = validate.get('email')
        user = User.getOrRegisterEmailOnly(email, context='report-block')
        ReportGenerated.send(
            user=user,
            target=validate.get('target'),
            commonName=validate.get('commonName'),
            type=validate.get('type'),
        )
        return "OK"

class ReportView(BaseView):

    @Route('/sample-report/')
    def getSample(self):
        sampleAddress = Address.getBySlug("1982-lexington-ave-10035")

        return self._renderReport(
            type='property',
            city=sampleAddress.getCity(),
            key=sampleAddress.getReportStatKey(),
            target=sampleAddress,
            queriedAddress=sampleAddress,
            canonicalUrl=sampleAddress.getUrl(),
            previewMode=True,
        )

    @Route('/report/city/<citySlug>/')
    def getCity(self, citySlug):
        if (citySlug == 'other'):
            return flask.redirect('/')

        city = City.forSlug(citySlug)

        #TODO: remove it at what time?
        if city is None or city.isOther():
            newSlug = _getNewCitySlug(citySlug)
            if newSlug is not None:
                return flask.redirect('/report/city/%s/' % newSlug, code=301)

        if (city is None):
            flask.abort(404)
        elif city.isOther():
            return flask.redirect('/')

        page = validate.get('page', validate.ParseInt(), validate.DefaultValue(1))
        if page != 1:
            query = Property.query()\
                .filter(Property.city == citySlug)\
                .order(-Property.rank)
            pageInfo = rutil.ndbPaginate(page, 20, query, countLimit=10000)
            return flask.render_template(
                'client/propertyDirectory.jinja2',
                title="Properties in %s" % city.name,
                pageInfo=pageInfo,
                reportUrl=city.getUrl(),
            )
        else:
            return self._renderReport(
                type='city',
                target=city,
                city=city,
                key=city.getReportStatKey(),
                bias=city.center,
            )

    @Route('/report/neighborhood/<citySlug>/<areaSlug>/')
    def getNeighborhood(self, citySlug, areaSlug):
        area = Area.forSlug(areaSlug)

        # redirect in the case of old areaSlug being passed in
        #TODO: remove it at what time?
        if area is None:
            newCitySlug, newAreaSlug = _getNewCityAreaSlugs(areaSlug)
            if newAreaSlug is not None:
                return flask.redirect('/report/neighborhood/%s/%s/' % (newCitySlug, newAreaSlug), code=301)

        if area is None:
            flask.abort(404)

        city = area.getCity()

        page = validate.get('page', validate.ParseInt(), validate.DefaultValue(1))
        if page != 1:
            query = Property.query()\
                .filter(Property.lists == ("area:%s" % area.slug))\
                .order(-Property.rank)
            pageInfo = rutil.ndbPaginate(page, 20, query, countLimit=10000)
            return flask.render_template(
                'client/propertyDirectory.jinja2',
                title="Properties in %s" % area.name,
                pageInfo=pageInfo,
                reportUrl=area.getUrl(),
            )
        else:
            return self._renderReport(
                type='neighborhood',
                city=city,
                key=area.getReportStatKey(),
                target=area,
                bias=area.center,
            )

    @Route('/report/property/<citySlug>/<addressSlug>/')
    def getProperty(self, citySlug, addressSlug):
        # 301 to city if missing
        queriedAddress = Address.getBySlug(addressSlug)
        if not queriedAddress:
            queriedAddress = geocoder.getAddressBySlugWorkaround(addressSlug)
        if queriedAddress is None:
            return flask.redirect('/report/city/%s/' % citySlug, code=301)

        # 301 if city mismatch
        city = City.forSlug(citySlug)
        if queriedAddress.city != citySlug:
            return flask.redirect("/report/property/%s/%s/" % (
                queriedAddress.city,
                queriedAddress.slug,
            ), code=301)

        # find canonical and get the propertyKey
        address = queriedAddress.getCanonicalAddress()
        propertyKey = ndb.Key(Property, address.slug)
        property = Property.get(propertyKey, address=address)

        # TODO: better computation of these
        commonName = address.getShortName()
        fullName = address.getFullAddress()

        return self._renderReport(
            type='property',
            city=city,
            key=propertyKey,
            target=address,
            queriedAddress=queriedAddress,
            canonicalUrl=address.getUrl(),
            isSubscribed=AlertSubscription.isSubscribed(property.key),
            bias=address.location,
        )

    @Route('/report/zip/<citySlug>/<areaSlug>/')
    def getZip(self, citySlug, areaSlug):
        area = ZipcodeArea.forSlug(areaSlug)

        if area is None:
            flask.abort(404)

        city = area.getCity()

        page = validate.get('page', validate.ParseInt(), validate.DefaultValue(1))
        if page != 1:
            query = Property.query()\
                .filter(Property.lists == ("zip:%s" % area.slug))\
                .order(-Property.rank)
            pageInfo = rutil.ndbPaginate(page, 20, query, countLimit=10000)
            return flask.render_template(
                'client/propertyDirectory.jinja2',
                title="Properties in %s" % area.name,
                pageInfo=pageInfo,
                reportUrl=area.getUrl(),
            )
        else:
            return self._renderReport(
                type='zipcode',
                city=city,
                key=area.getReportStatKey(),
                target=area,
                bias=area.center,
            )

    @Route('/apartments/<slug>/')
    def redirectLegacyApartments(self, slug):
        return self._redirectLegacyAddress(slug)

    @Route('/building/<slug>/')
    def redirectLegacyBuilding(self, slug):
        return self._redirectLegacyAddress(slug)

    @Route('/neighborhood/<neighborhoodSlug>/')
    def redirectLegacyNeighborhood(self, neighborhoodSlug):
        area = Area.forSlug(neighborhoodSlug)

        # redirect in the case of old areaSlug being passed in
        #TODO: remove it at what time?
        if area is None:
            newCitySlug, newAreaSlug = _getNewCityAreaSlugs(neighborhoodSlug)
            if newAreaSlug is not None:
                return flask.redirect('/report/neighborhood/%s/%s/' % (newCitySlug, newAreaSlug), code=301)

        if area is None:
            flask.abort(404)
        else:
            return flask.redirect(area.getUrl(), code=301)

    @Route('/no-fee-apartments/<slug>/')
    def redirectLegacyNoFeeApartments(self, slug):
        return self._redirectLegacyAddress(slug)

    @Route('/region/<neighborhoodSlug>/')
    def redirectLegacyRegion(self, neighborhoodSlug):
        return self.redirectLegacy(neighborhoodSlug)

    def _redirectLegacyAddress(self, slug):
        queriedBuilding = BuildingMongoModel.getBySlug(slug)
        if queriedBuilding is None:
            flask.abort(404)
        return flask.redirect("/report/property/%s/%s/" % (
            queriedBuilding.get('city') or 'other',
            queriedBuilding['id']['slug'],
        ), code=301)

    def _renderReport(self,
            type,
            city,
            key,
            target,
            **kwargs
        ):
        forceRecompute = validate.get('force', validate.ParseBool())

        checkState(
            city.state or \
            rutil.safeAccess(target, 'addrState') or \
            rutil.safeAccess(target, 'state')
        )

        userKeyStr = ''
        user = User.get()
        if user.key is not None:
            userKeyStr = user.key.urlsafe()

        ReportViewed(
            type=type,
            city=city.slug,
            slug=key.id(),
            tags=flask.request.appCustomizer.getTags(),
            viewed=datetime.datetime.now(),
            user=userKeyStr,
            shard=config.CONFIG['EMAIL']['shard'],
            #TODO move shard to its own config
        ).put()

        report = Report(
            type=type,
            city=city,
            key=key,
            target=target,
            forceRecompute=forceRecompute,
            isPrecompute=False,
            doMinimal=True,
        )

        pendingReporters = report.getPendingReporters()
        showLoading = True
        if validate.get('display', validate.ParseBool()):
            showLoading = False
        if not pendingReporters:
            showLoading = False

        description = report.produceDescriptors()
        reportSections = report.produceReportSections(
            settings=flask.request.appCustomizer.settings(),
        )
        badges = report.produceBadges()

        kwargs.update(report.produceCustomizerKwargs(**kwargs))

        isMember = user.status != 'guest'
        appFullReports = flask.request.appCustomizer.renderFullReports()
        previewMode = kwargs.get('previewMode')
        renderFullReport = isMember or appFullReports or previewMode

        return flask.render_template(
            'client/reportView.jinja2',
            badges=badges,
            city=report.city,
            completedReporters=report.getCompletedReporters(),
            description=description,
            metaDescription=" ".join(description),
            pendingReporters=pendingReporters,
            renderFullReport=renderFullReport,
            sections=reportSections,
            showLoading=showLoading,
            report=report,
            **kwargs
        )

class ResetPasswordView(BaseView):

    @Route('/reset-password/')
    def start(self):
        return flask.render_template('client/resetPasswordView.jinja2')

    @Route('/reset-password/', methods=['POST'])
    def finish(self):
        token = PasswordResetToken.query().filter(
            PasswordResetToken.uid == flask.request.values.get('token')
        ).get()
        # TODO: expires?
        user = token.user.get()
        user.setPassword(flask.request.values.get('new'))
        user.login()
        user.put()
        return flask.render_template('client/profileView.jinja2',
            passwordChanged=True
        )

class RobotsTxtView(BaseView):

    @Route('/robots.txt')
    def process(self):
        host = flask.request.headers.get('Host')
        if host == 'www.addressreport.com':
            txt = "Sitemap: https://www.addressreport.com/sitemap.xml"
            txt += "\nUser-agent: *"
            txt += "\nDisallow: /service/"
            txt += "\nDisallow: /address-lookup-landing/"
            txt += "\nDisallow: /address-alerts/"
        else:
            txt = "Sitemap: https://www.addressreport.com/sitemap.xml"
            txt += "\nUser-agent: *"
            txt += "\nDisallow: /"
        return flask.Response(txt, mimetype="text/plain")

class RootView(BaseView):

    @Route('/')
    def get(self):
        apiKey = validate.get("api_key")
        if apiKey:
            flask.session['api_key'] = apiKey
            return flask.redirect('/')

        lookupOnlyRoot = flask.request.appCustomizer.lookupOnlyRoot()
        if lookupOnlyRoot:
            return flask.render_template('client/lookupOnlyRootView.jinja2')
        else:
            return flask.render_template('client/rootView.jinja2',
                title="Property Reviews, Complaints & Public Records - AddressReport",
                metaDescription="""
                    AddressReport scans millions of public records to
                    reveal the unbiased truth about any address.
                """,
                states=ArState.all(),
            )

class SignUpView(BaseView):

    @Route('/sign-up/')
    def pageStart(self):
        return flask.render_template('client/signUpView.jinja2')

    @Route('/sign-up/last-step/')
    def pageLast(self):
        return flask.render_template('client/signUpLastStepView.jinja2')

    @Route('/free-trial/<key>/', methods=['GET'])
    def freeTrialSignup(self, key):
        partner = ndb.Key(urlsafe=key).get()
        return flask.render_template(
            'client/freeTrialView.jinja2',
            partner=partner,
        )

    @Route('/free-trial/<key>/', methods=['POST'])
    def freeTrialSave(self, key):
        partner = ndb.Key(urlsafe=key).get()

        apiKey = validate.get('api_key', validate.Required())
        apiSecret = validate.get('api_secret', validate.Required())
        leadEmail = validate.get('lead_email', validate.Required())

        if partner is None or partner.apiKey != apiKey or partner.apiSecret != apiSecret:
            return flask.redirect('/free-trial/%s/' % key)

        if leadEmail != partner.getSetting('leadEmail'):
            partner.settings.update({'leadEmail' : leadEmail})
            partner.put()

        log = PartnerFreeTrialLog.get(partner.key)

        if not log:
            log = PartnerFreeTrialLog.create(partner)
            log.put()

        if log.accepted:
            return flask.redirect('/free-trial/%s/widget/' % key)

        return flask.redirect('/free-trial/%s/agreement/' % key)

    @Route('/free-trial/<key>/agreement/', methods=['GET'])
    def freeTrialAgreement(self, key):
        partner = ndb.Key(urlsafe=key).get()
        if not partner:
            return "wrong url"

        log = PartnerFreeTrialLog.get(partner.key)
        if log and log.accepted:
            return flask.redirect('/free-trial/%s/widget/' % key)

        return flask.render_template('client/freeTrialAgreementView.jinja2')

    @Route('/free-trial/<key>/agreement/', methods=['POST'])
    def freeTrialAgreementSave(self, key):
        partner = ndb.Key(urlsafe=key).get()
        if not partner:
            return "wrong url"
        
        accepted = validate.get('accepted', validate.Required())

        if not accepted:
            return flask.redirect('/free-trial/%s/agreement/' % key)

        log = PartnerFreeTrialLog.get(partner.key)
        if log:
            if log.accepted:
                return flask.redirect('/free-trial/%s/widget/' % key)
        else:
            log = PartnerFreeTrialLog.create(partner)

        log.accepted = True
        log.acceptedDate = datetime.datetime.now()
        log.put()
        
        return flask.redirect('/free-trial/%s/widget/' % key)

    @Route('/free-trial/<key>/widget/')
    def freeTrialWidget(self, key):
        partner = ndb.Key(urlsafe=key).get()

        log = PartnerFreeTrialLog.get(partner.key)
        if log and log.accepted:
            return flask.render_template(
                'client/widgets.jinja2',
                apiKey=partner.apiKey,
                apiSecret=partner.apiSecret,
                apiKeyReadonly='readonly',
                apiSecretReadonly='readonly',
            )
        return flask.redirect('/free-trial/%s/' % key)

class SitemapView(BaseView):

    @Route('/sitemap/blog-sitemap.xml')
    def blogSitemap(self):
        posts = BlogPost.query().fetch(projection=[BlogPost.slug])
        urls = []
        for post in posts:
            urls.append("/blog/%s/" % post.slug)
        return self.render(urls)

    @Route('/sitemap/state-sitemap.xml')
    def stateSitemap(self):
        states = ArState.all()
        urls = []
        for state in states:
            urls.append(state.getUrl())
        return self.render(urls)

    @Route('/sitemap/rentenna-sitemaps/<uuid>.xml')
    def generatedSitemap(self, uuid):
        filepath = "/rentenna-sitemaps/%s" % uuid
        file = cloudstorage.open(filepath, 'r')
        urls = [line for line in file]
        return self.render(urls)

    @Route('/sitemap.xml')
    def sitemapIndex(self):
        sitemaps = [
            '/sitemap/static-sitemap.xml',
            '/sitemap/blog-sitemap.xml',
            '/sitemap/state-sitemap.xml',
        ]
        mostRecent = Sitemap.query().order(-Sitemap.generated).get()
        pages = SitemapPage.query().filter(SitemapPage.sitemap == mostRecent.key)
        for page in pages:
            sitemaps.append("/sitemap%s.xml" % page.gcsPath)
        data = flask.render_template(
            'client/sitemapIndex.jinja2',
            sitemaps=sitemaps,
            now=datetime.datetime.now(),
        )
        return flask.Response(data, mimetype="text/xml")

    @Route('/sitemap/static-sitemap.xml')
    def staticSitemap(self):
        urls = [
            "/",
            "/about/",
            "/blog/",
            "/contact/",
            "/terms/",
        ]
        return self.render(urls)

    def render(self, urls):
        data = flask.render_template(
            'client/sitemap.jinja2',
            urls=urls,
            now=datetime.datetime.now(),
        )
        return flask.Response(data, mimetype="text/xml")

class StateView(BaseView):

    @Route('/<stateSlug>-cities/')
    def process(self, stateSlug):
        state = ArState.forSlug(stateSlug)
        cities = City.forState(state)
        return flask.render_template('client/stateView.jinja2',
            state=state,
            citiesInState=cities,
        )

class StaticContentView(BaseView):

    @Route('/partners/')
    def get(self):
        return flask.render_template('client/partners.jinja2')

class SubdomainLogoImage(BaseView):

    @Route('/partner-image/<uid>/', endpoint='partnerImage')
    @Route('/subdomain-image/<uid>/', endpoint='subdomainImage')
    def process(self, uid):
        filepath = '/%s/%s' % (
            config.CONFIG['WEB']['UPLOAD_BUCKET'],
            uid,
        )
        # try:
        #     stat = cloudstorage.stat(filepath)
        #     file = cloudstorage.open(filepath, 'r')
        #     return flask.Response(file, mimetype=stat.content_type)
        # except:
        #     flask.abort(404)
        url = util.getPhotoServingUrl(filepath)
        if url:
            return flask.redirect(url)
        else:
            abort(404)



class TermsView(BaseView):

    @Route('/terms/')
    def get(self):
        return flask.render_template('client/termsView.jinja2',
            suppressInspectlet=True,
        )

class UnsubscribeConfirm(BaseView):

    @Route('/unsubscribe/')
    def get(self):
        return flask.render_template('client/unsubscribeView.jinja2')

    @Route('/unsubscribe-alert/')
    def unsubscribeAlert(self):
        return flask.render_template('client/unsubscribeAlertView.jinja2')

class DeveloperView(BaseView):

    @Route('/developer/')
    def developer(self):
        return flask.render_template(
            'client/developer.jinja2',
        )

    @Route('/developer/apis/')
    def devApis(self):
        return flask.render_template(
            'client/developerApis.jinja2',
        )

    @Route('/developer/socialcity/')
    def devSocialCity(self):
        return flask.render_template(
            'client/socialcity.jinja2',
        )


    @Route('/developer/widgets/')
    def widgets(self):
        return flask.render_template(
            'client/widgets.jinja2',
            apiKey='',
            apiSecret='',
            apiKeyReadonly='',
            apiSecretReadonly='',
        )

    @Route('/widget/contact-form/')
    def contactForm(self):
        return flask.render_template(
            'client/widgetContactForm.jinja2',
        )

    def _getResBaseUrl(self):
        resBaseUrl = config.CONFIG['URL']['STATIC']
        if resBaseUrl.startswith('/'):
            base = flask.request.appCustomizer.urlBase()
            resBaseUrl = urlparse.urljoin(base, resBaseUrl)
        return resBaseUrl

class WpContentView(BaseView):

    @Route('/blog/wp-content/<path:path>')
    def process(self, path):
        from cloudstorage.errors import NotFoundError
        filepath = "/rentenna-wp/%s" % path
        try:
            stat = cloudstorage.stat(filepath)
            file = cloudstorage.open(filepath, 'r')
            return flask.Response(file, mimetype=stat.content_type)
        except NotFoundError:
            flask.abort(404)

class ZipcodeJson(BaseView):

    @Route('/zip-json/<slug>.json')
    def process(self, slug):
        from cloudstorage.errors import NotFoundError
        filepath = "/rentenna-data/zips3/%s.json" % slug
        try:
            file = cloudstorage.open(filepath, 'r')
            return flask.Response(file, mimetype='text/json')
        except NotFoundError:
            flask.abort(404)

def checkState(state):
    allowedStates = flask.request.appCustomizer.allowedStates()
    if allowedStates:
        if state not in allowedStates:
            allowedStatesNames = []
            states = State.all()
            for state in states:
                if state.abbr in allowedStates:
                    allowedStatesNames.append(state.name)
            response = flask.render_template(
                'client/stateNotSupportedView.jinja2',
                allowedStates=allowedStatesNames
            )
            raise ResponseException(response)

from google.appengine.api import memcache
def _getCityCache(key):
    key = 'city:%s' % key
    return memcache.get(key)

def _setCityCache(key, value):
    key = 'city:%s' % key
    if not memcache.set(key, value):
        logging.error('could not save %s into memcache' % key)

def _getAreaCache(key):
    key = 'area:%s' % key
    return memcache.get(key)

def _setAreaCache(key, value):
    key = 'area:%s' % key
    if not memcache.set(key,value):
        logging.error('could not save %s into memcache' % key)

def _getNewCitySlug(citySlug):
    newCitySlug = _getCityCache(citySlug)
    if newCitySlug:
        if newCitySlug != citySlug:
            logging.info("findoldcitySlug3 from cache")
            return newCitySlug
        else:
            return None

    inputCitySlug = citySlug
    found = OldCity2.forSlugNoGeo(citySlug)
    if found:
        slug3 = found['slug3']
        if not found.isOther():
            _setCityCache(inputCitySlug, slug3)
            if slug3 != inputCitySlug:
                logging.info("level1findnewcitySlug3: %s for old %s and put into cache" % (slug3, inputCitySlug)) 
                return slug3
            else:
                return None
        else:
            found = None

    if not found:
        found = OldCity.forSlugNoGeo(citySlug)

    if found and not found.isOther():
        citySlug = util.keyify2(found.name)
        stateAbbr = found.getStateAbbr().lower()
        if stateAbbr:
            citySlug = '%s-%s' % (citySlug, stateAbbr)

        if inputCitySlug != citySlug:
            found = OldCity2.forSlugNoGeo(citySlug)
            if found and not found.isOther():
                slug3 = found['slug3']
                _setCityCache(inputCitySlug, slug3)
                logging.info("level2findnewcitySlug3: %s for old %s and put into cache" % (slug3, inputCitySlug)) 
                return slug3

    logging.warning("final: missing new city slug3 for the old one: %s" % inputCitySlug)
    _setCityCache(inputCitySlug, inputCitySlug)
    return None

def _getNewCityAreaSlugs(areaSlug):

    slugTuple = _getAreaCache(areaSlug)
    if slugTuple:
        if slugTuple[1] != areaSlug:
            logging.info("findoldareaSlug3 from cache")
            return slugTuple
        else:
            return None, None

    inputAreaSlug = areaSlug

    found = OldArea2.forSlugNoGeo(areaSlug)
    if found:
        areaSlug3 = found['slug3']
        citySlug3 = found['citySlug3']

        _setAreaCache(inputAreaSlug, (citySlug3, areaSlug3))
        if areaSlug3 != inputAreaSlug:
            logging.info("level1findnewareaSlug3: %s for old %s and put into cache" % (areaSlug3, inputAreaSlug))
            return citySlug3, areaSlug3
        else:
            return None, None

    oldArea = OldArea.forSlugNoGeo(areaSlug)
    if oldArea:
        city = OldCity.forSlugNoGeo(oldArea.city)
        if city and not city.isOther():
            citySlug = util.keyify2(city.name)
            stateAbbr = city.getStateAbbr().lower()
            if stateAbbr:
                citySlug = '%s-%s' % (citySlug, stateAbbr)
            areaSlug = '%s-%s' % (util.keyify2(oldArea.name), citySlug)
            if inputAreaSlug != areaSlug:
                found = OldArea2.forSlugNoGeo(areaSlug)
                if found:
                    areaSlug3 = found['slug3']
                    citySlug3 = found['citySlug3']

                    _setAreaCache(inputAreaSlug, (citySlug3, areaSlug3))
                    if areaSlug3 != inputAreaSlug:
                        logging.info("level2findnewareaSlug3: %s for old %s and put into cache" % (areaSlug3, inputAreaSlug))
                        return citySlug3, areaSlug3
                    else:
                        return None, None
        
    logging.warning("final: missing new area slug3 for the old one: %s" % inputAreaSlug)
    _setAreaCache(inputAreaSlug, ('', inputAreaSlug))
    return None, None
