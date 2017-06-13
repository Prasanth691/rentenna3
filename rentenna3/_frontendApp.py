import flask

import web

import web.admin
import web.adminUser
import web.commonSubviews
import web.config
import web.templating
import web.tracking
import web.abtest
import web.reporting
import web.keyserver
import web.blog
import web.quiz

import rentenna3.adminViews
import rentenna3.apiViews
import rentenna3.clientViews
import rentenna3.clientServices
import rentenna3.jsjViews
import rentenna3.templating
import rentenna3.models
import rentenna3.baseSubviews
import rentenna3.clientSubviews
import rentenna3.data.redirects
import rentenna3.ndbMongoModels

from urlparse import urlparse, parse_qs
import  web.ndbToMongo
APP = web.makeApp(
    'rentenna3.frontend',
    viewModules=[
        rentenna3.adminViews,
        rentenna3.apiViews,
        rentenna3.clientViews,
        rentenna3.jsjViews,
        rentenna3.clientServices,
        rentenna3.backgroundViews,
        web.backups,
        web.ndbToMongo,
    ],
    modelModules=[
        rentenna3.models,
        web.tracking,
    ],
    ndbMongoModelModules=[
        rentenna3.ndbMongoModels,
    ],
    templatingModules=[
        web.templating,
        rentenna3.templating,
    ],
    subviewModules=[
        web.commonSubviews,
        rentenna3.baseSubviews,
        rentenna3.clientSubviews,
        rentenna3.adminViews,
    ],
    templateDirs=[
        'templates',
        'resource-src',
    ],
    redirectModule=rentenna3.data.redirects,
    notFoundHandler=(lambda: (flask.render_template('client/404.jinja2', suppressInspectlet=True), 404)),
    subcomponents=[
        web.admin.AdminSubcomponent(),
        web.adminUser.AdminUserSubcomponent(),
        web.tracking.TrackingSubcomponent(),
        web.abtest.AbTestSubcomponent(),
        web.ForceSslSubcomponent(),
        web.counters.CounterSubcomponent(),
        web.blog.BlogSubcomponent(),
        web.reporting.ReportingSubcomponent(),
        web.quiz.QuizSubcomponent(),
        web.keyserver.KeyserverSubcomponent(),
    ],
)

import rentenna3.alerts
rentenna3.base.applyAlerts(rentenna3.alerts)

import rentenna3.hybridAlerts
rentenna3.base.applyHybridAlerts(rentenna3.hybridAlerts)

import rentenna3.partnerAlerts
rentenna3.base.applyPartnerAlerts(rentenna3.partnerAlerts)

import rentenna3.badges
rentenna3.base.applyBadges(rentenna3.badges)

import rentenna3.email
rentenna3.base.applyEmails(rentenna3.email)

import rentenna3.reporters
rentenna3.base.applyReporters(rentenna3.reporters)

import rentenna3.reportSections
rentenna3.base.applyReportSections(rentenna3.reportSections)

import rentenna3.reportCustomizers
rentenna3.base.applyReportCustomizers(rentenna3.reportCustomizers)

import rentenna3.reportDescriptors
rentenna3.base.applyReportDescriptors(rentenna3.reportDescriptors)

import rentenna3.quickReporters
rentenna3.base.applyQuickReporters(rentenna3.quickReporters)

@APP.before_request
def setDatastoreNamespace():
    from google.appengine.api import namespace_manager
    from web import config
    namespace = config.CONFIG['datastore_namespace']
    if namespace:
        namespace_manager.set_namespace(namespace)

@APP.before_request
def checkUserFacing():
    if flask.request.path.startswith('/background/'):
        flask.request.userFacing = False
    else:
        flask.request.userFacing = True

@APP.before_request
def getAppCustomizer():
    if flask.request.path.startswith('/background/'):
        return

    import urlparse
    from web.config import CONFIG
    from rentenna3.appCustomizers import AddressReportCustomizer, DefaultPartnerAppCustomizer
    from rentenna3.models import Partner
    parts = urlparse.urlparse(flask.request.url)
    domain = parts.netloc
    appCustomizer = None
    partner = None

    apiKey = flask.session.get('api_key')
    partner = Partner.forApiKey(apiKey)
    if partner is not None:
        flask.session['api_key'] = apiKey
        appCustomizer = DefaultPartnerAppCustomizer(partner)

        # note: comment out below code for now because weichart is going to always use same subdomain.
        # if flask.session.get('user_branding_changed'):
        #     preferredParts = urlparse.urlparse(partner.getPreferredDomain())
        #     if domain != preferredParts.netloc:
                
        #         newParts = urlparse.ParseResult(
        #             scheme=parts.scheme,
        #             netloc=preferredParts.netloc,
        #             path=parts.path,
        #             params=parts.params,
        #             query=parts.query,
        #             fragment=parts.fragment,
        #         )
        #         return flask.redirect( urlparse.urlunparse(newParts) )
    else:
        flask.session['api_key'] = None
        if CONFIG['URL']['DOMAIN'] == domain:
            appCustomizer = AddressReportCustomizer()
        else:
            partner = Partner.get(domain)
            if partner is not None:
                flask.session['api_key'] = partner.apiKey
                appCustomizer = DefaultPartnerAppCustomizer(partner)

    if appCustomizer is None:
        # TODO: possibly weak...
        newUrl = flask.request.url.replace(domain, CONFIG['URL']['DOMAIN'])
        return flask.redirect(newUrl)
    else:
        flask.request.appCustomizer = appCustomizer

@APP.before_request
def setDefaultDeadline():
    from google.appengine.api import urlfetch
    urlfetch.set_default_fetch_deadline(60)
