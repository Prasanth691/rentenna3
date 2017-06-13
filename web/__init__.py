import os
import sys

from web.base import AppSubcomponent

class AppInfo(object):

    def __init__(self,
            viewModules=None,
            modelModules=None,
            ndbMongoModelModules=None,
            templatingModules=None,
            subviewModules=None,
            templateDirs=None,
            **kwargs
        ):
        self.viewModules = viewModules or []
        self.modelModules = modelModules or []
        self.ndbMongoModelModules = ndbMongoModelModules or []
        self.templatingModules = templatingModules or []
        self.subviewModules = subviewModules or []
        self.templateDirs = templateDirs or []
        for key, value in kwargs.iteritems():
            setattr(self, key, value)

def makeApp(
        appName,
        viewModules=None,
        modelModules=None,
        ndbMongoModelModules=None,
        templatingModules=None,
        subviewModules=None,
        templateDirs=None,
        forceSsl=False,
        redirectModule=None,
        notFoundHandler=None,
        subcomponents=None,
        **kwargs
    ):
    appInfo = AppInfo(
        appName=appName,
        viewModules=viewModules,
        modelModules=modelModules,
        ndbMongoModelModules=ndbMongoModelModules,
        templatingModules=templatingModules,
        subviewModules=subviewModules,
        templateDirs=templateDirs,
        **kwargs
    )
    from web.config import CONFIG

    # reconcile requirements
    orderedSubcomponents = []
    satisfied = set()
    while subcomponents:
        startSize = len(subcomponents)
        for subcomponent in list(subcomponents):
            isSatisfied = True
            for requires in subcomponent.requires:
                if requires not in satisfied:
                    isSatisfied = False
            if isSatisfied:
                satisfied.add(subcomponent.__class__.__name__)
                subcomponents.remove(subcomponent)
                orderedSubcomponents.append(subcomponent)

        endSize = len(subcomponents)
        if startSize == endSize:
            print "Missing Dependencies!!"
            for subcomponent in subcomponents:
                print "%s Requires: %s" % (subcomponent, subcomponent.requires)
            return None

    for subcomponent in orderedSubcomponents:
        subcomponent.augmentEnvironment(appInfo)

    import flask

    APP = flask.Flask(appName)

    APP.subcomponents = orderedSubcomponents

    APP.config.update(**CONFIG)
    if 'SECRET_KEY' in CONFIG:
        APP.secret_key = CONFIG['SECRET_KEY']

    applySubviews(APP, appInfo.subviewModules)
    applyTemplating(APP, templatingModules, appInfo.templateDirs)
    applyViews(APP, appInfo.viewModules)
    applyModels(APP, appInfo.modelModules)
    applyNdbMongoModels(APP, appInfo.ndbMongoModelModules)

    if redirectModule:
        applyRedirects(APP, redirectModule, notFoundHandler)

    applyExplicitRedirectHandler(APP)
    applyExplicitResponseHandler(APP)

    applyDataPreserver(APP)
    applyOsAugmentor(APP)
    applyTaskPayloadAugmentor(APP)

    for subcomponent in orderedSubcomponents:
        subcomponent.augmentApp(APP, appInfo)

    return APP

def applyDataPreserver(app):
    @app.before_request
    def augment():
        import flask
        flask.request.rawData = flask.request.get_data()
        # TODO: when will this bite us in the ass?

def applyExplicitRedirectHandler(app):
    import flask
    from web.base import RedirectException
    @app.errorhandler(RedirectException)
    def explicitRedirect(error):
        return flask.redirect(error.location, error.type)

def applyExplicitResponseHandler(app):
    import flask
    from web.base import ResponseException
    @app.errorhandler(ResponseException)
    def explicitRedirect(error):
        return error.response

def applyModels(app, modelModules):
    from google.appengine.ext import ndb
    from web import rutil

    if modelModules is None:
        modelModules = []

    app.modelModules = modelModules

    app.ndbModels = {}
    for module in modelModules:
        for cls in rutil.getSubclasses(module, ndb.Model):
            app.ndbModels[cls.__name__] = cls

def applyNdbMongoModels(app, ndbMongoModelModules):
    from google.appengine.ext import ndb
    from web import rutil
    from web.mongo import NdbMongoModel

    if ndbMongoModelModules is None:
        ndbMongoModelModules = []

    app.ndbMongoModelModules = ndbMongoModelModules

    app.ndbMongoModels = {}
    for module in ndbMongoModelModules:
        for cls in rutil.getSubclasses(module, NdbMongoModel):
            app.ndbMongoModels[cls.__name__] = cls

def applyOsAugmentor(app):
    @app.before_request
    def augmentOs():
        from web import config
        config.augmentOs()

def applyViews(app, viewModules):
    from web.base import BaseView
    if viewModules is None:
        viewModules = []

    alreadyApplied = []
    app.viewModules = viewModules
    for module in viewModules:
        # Call this method to add all routes for all view classes in the module
        for cls in rutil.getSubclasses(module, BaseView):
            for method in cls.__dict__.values():
                if hasattr(method, '_routes'):
                    if (cls, method) not in alreadyApplied:
                        for (rule, kwargs) in method._routes:
                            if 'endpoint' not in kwargs:
                                kwargs['endpoint'] = "%s.%s" % (cls.__name__, method.__name__)
                            kwargs['view_func'] = cls._viewFunc(method)
                            app.add_url_rule(rule, **kwargs)
                        alreadyApplied.append((cls, method))

def applyRedirects(app, redirectModule, notFoundHandler=None):

    @app.errorhandler(404)
    def notFound(error):
        import flask
        import re
        path = flask.request.path
        qs = flask.request.query_string
        for redirect in redirectModule.REDIRECTS:
            if re.match(redirect[0], path):
                newPath = re.sub(redirect[0], redirect[1], path)
                if qs:
                    newPath += "?" + qs
                return flask.redirect(newPath, code=301)

        if notFoundHandler:
            return notFoundHandler()
        else:
            return 'Not Found', 404

def applySubviews(app, subviewModules):
    app.subviewModules = subviewModules

    from web import rutil
    from web.base import SubView
    app.subviews = {}
    for module in subviewModules:
        for cls in rutil.getSubclasses(module, SubView):
            app.subviews[cls.__name__] = cls

def applyTaskPayloadAugmentor(app):
    @app.before_request
    def augment():
        import flask
        if '__task_payload__' in flask.request.values:
            from web.models import TaskPayload
            from google.appengine.ext import ndb
            from werkzeug.datastructures import MultiDict
            # feels like this could be a potential place to inject some bullshit...
            payload = ndb.Key(urlsafe=flask.request.values['__task_payload__']).get()
            flask.request.values = MultiDict(payload.payload)

def applyTemplating(app, templatingModules, templateDirs):
    if not templateDirs:
        templateDirs = ['templates', 'lib/web/templates']

    app.templatingModules = templatingModules
    app.templateDirs = set(templateDirs)

    from web import templating
    jinjaGlobals = templating.sniffGlobals(templatingModules)

    for key, subviewCls in app.subviews.iteritems():
        jinjaGlobals[key] = subviewCls.inject

    app.jinja_env.globals.update(jinjaGlobals)
    app.jinja_env.finalize = templating.nullable
    app.jinja_env.autoescape = True

    from jinja2 import FileSystemLoader
    app.jinja_env.loader = FileSystemLoader(templateDirs)

class ForceSslSubcomponent(AppSubcomponent):

    def augmentApp(self, app, appInfo):

        @app.before_request
        def redirectNonSSl():
            import flask
            from web import rutil

            isDev = rutil.isDev()
            isSecure = flask.request.is_secure
            isTaskQueue = "+http://code.google.com/appengine" in flask.request.user_agent.string
            if (not isDev) and (not isSecure) and (not isTaskQueue):
                return flask.redirect(
                    flask.request.url.replace("http://", "https://"),
                    code=301,
                )

        @app.after_request
        def setHstsPolicy(response):
            import flask
            from web import rutil
            if not rutil.isDev():
                if isinstance(response, flask.Response):
                    response.headers['Strict-Transport-Security'] = "max-age=31536000"
            return response
