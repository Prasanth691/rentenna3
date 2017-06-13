import flask
import json
import pickle
import urllib
import urlparse
import logging
import os

from google.appengine.ext import ndb

from web.backups import BackedupNdbModel
from web.base import AppSubcomponent

class TrackingSubcomponent(AppSubcomponent):

    def augmentApp(self, app, appInfo):

        @app.before_request
        def track():
            tracker = get()

        @app.after_request
        def setCookie(response):
            tracker = get()
            import flask
            if isinstance(response, flask.Response) and response.mimetype == 'text/html':
                response.set_cookie('tracker', urllib.quote(json.dumps({
                    'utm_source': tracker.utmSource,
                    'utm_campaign': tracker.utmCampaign,
                })))
            return response

class Tracker(BackedupNdbModel):

    browser = ndb.StringProperty()
    clickId = ndb.StringProperty()
    entryDate = ndb.DateTimeProperty(auto_now_add=True)
    landingUrl = ndb.TextProperty()
    parentId = ndb.KeyProperty(kind='Tracker')
    ipAddress = ndb.StringProperty()
    referringUrl = ndb.TextProperty()
    userAgent = ndb.StringProperty()
    utmCampaign = ndb.StringProperty()
    utmContent = ndb.StringProperty()
    utmKeyword = ndb.StringProperty()
    utmMedium = ndb.StringProperty()
    utmTerm = ndb.StringProperty()
    utmSource = ndb.StringProperty()

    def getJson(self):
        return {
            'browser': self.browser,
            'clickId': self.clickId,
            'entryDate': str(self.entryDate),
            'landingUrl': self.landingUrl,
            'ipAddress': self.ipAddress,
            'referringUrl': self.referringUrl,
            'userAgent': self.userAgent,
            'utmCampaign': self.utmCampaign,
            'utmContent': self.utmContent,
            'utmKeyword': self.utmKeyword,
            'utmMedium': self.utmMedium,
            'utmTerm': self.utmTerm,
            'utmSource': self.utmSource,
        }

    def isMobile(self):
        if self.userAgent:
            return (
                ('Android' in self.userAgent)
                or ('iPhone' in self.userAgent)
                or ('iPad' in self.userAgent)
                or ('iPod' in self.userAgent)
            )

    def isSearchEngine(self):
        if self.userAgent:
            from web.data.botUserAgents import PATTERNS
            for pattern in PATTERNS:
                if pattern in self.userAgent:
                    return True
        return False

def get():
    if flask.request:
        if not hasattr(flask.request, 'tracker'):
            flask.request.tracker = _track()
        return flask.request.tracker

def decorateIntersiteUrl(originalUrl):
    tracker = get()
    if tracker:
        parseUrl = urlparse.urlparse(originalUrl)
        parseDict = dict(urlparse.parse_qsl(parseUrl.query))
        parseDict['utm_campaign'] = parseDict.get('utm_campaign') or tracker.utmCampaign
        parseDict['utm_source'] = "%s/%s" % (os.environ['APPLICATION_ID'], parseDict.get('utm_source') or tracker.utmSource)
        parseDict['utm_content'] = parseDict.get('utm_content') or tracker.utmContent or ''
        parseDict['utm_keyword'] = parseDict.get('utm_keyword') or tracker.utmKeyword or ''
        parseDict['utm_medium'] = parseDict.get('utm_medium') or tracker.utmMedium or ''
        parseDict['utm_term'] = parseDict.get('utm_term') or tracker.utmTerm or ''
        if tracker.key:
            parseDict['utm_via'] = "%s@%s" % (tracker.key.urlsafe(), os.environ['APPLICATION_ID'])
        newUrlParams = urllib.urlencode(parseDict)
        newUrl = '%s://%s%s?%s' % (parseUrl.scheme, parseUrl.netloc, parseUrl.path, newUrlParams)
        return newUrl
    else:
        return originalUrl

def _track():
    ua = flask.request.user_agent

    current = flask.request.url
    referringUrl = flask.request.referrer

    existingPayload = flask.session.get('tracker')
    if existingPayload:
        try:
            existing = pickle.loads(existingPayload)
        except:
            existing = None
    else:
        existing = None

    currentParsed = urlparse.urlparse(current)
    currentParams = dict(urlparse.parse_qsl(currentParsed.query))

    tracker = Tracker(
        landingUrl=current,
        referringUrl=referringUrl,
        ipAddress=flask.request.remote_addr,
        userAgent=ua.string,
        browser=ua.browser,
    )

    _trackFromParams(tracker, currentParams)


    if tracker.utmSource == 'DIRECT':
        _trackSourceFromReferrer(tracker)

    if (existing is not None) \
        and (
            tracker.utmSource == existing.utmSource or \
            # utmSource would not change
            tracker.utmSource == 'INTERNAL' or \
            # followed an internal link
            (hasattr(flask.current_app, 'customTrackerCheck') and flask.current_app.customTrackerCheck(tracker))
            # custom tracker check has been implemented
        ):
        shouldKeepExistingTracker = True
    else:
        shouldKeepExistingTracker = False

    if shouldKeepExistingTracker:
        return existing
    else:
        if existing:
            tracker.parentId = existing.key

        # don't save if this is a bot
        if not tracker.isSearchEngine():
            tracker.put()
            flask.session['tracker'] = pickle.dumps(tracker)

        return tracker

def _trackFromParams(tracker, params):
    tracker.clickId = params.get('clk_id')
    tracker.utmContent = params.get('utm_content')
    tracker.utmMedium = params.get('utm_medium')
    tracker.utmKeyword = params.get('utm_keyword')
    tracker.utmTerm = params.get('utm_term')
    tracker.utmSource = params.get('utm_source') or 'DIRECT'
    tracker.utmCampaign = params.get('utm_campaign') or 'GLOBAL'

def _trackSourceFromReferrer(tracker):
    referrer = tracker.referringUrl

    searchSrc, searchQuery = _trackSearch(referrer)
    if searchSrc:
        tracker.utmSource = searchSrc
        tracker.utmMedium = "SEARCH"
        tracker.utmKeyword = "QUERY:%s" % searchQuery
        return searchSrc

    if referrer:
        parsedReferrer = urlparse.urlparse(referrer)
        parsedRequest = urlparse.urlparse(flask.request.url)
        if parsedRequest.netloc == parsedReferrer.netloc:
            tracker.utmSource = 'INTERNAL'
        else:
            tracker.utmContent = parsedReferrer.netloc
            tracker.utmSource = 'REFERRAL'
    else:
        tracker.utmSource = 'DIRECT'

def _trackSearch(referrer):
    src = None
    query = None

    if referrer:
        parsed = urlparse.urlparse(referrer)

        if 'google' in parsed.netloc:
            src = 'GOOGLE'
        elif 'search.yahoo' in parsed.netloc:
            src = 'YAHOO'
        elif 'bing' in parsed.netloc:
            src = 'BING'

        if parsed.query:
            params = dict(urlparse.parse_qsl(parsed.query))
            if src == 'YAHOO':
                query = params.get('p', None)
            else:
                query = params.get('q', None)

    return src, query
