import jinja2
import logging

from web import rutil

_routes = []

class BaseView(object):
    """
        Base class for all views -- for now, these are just marker classes.
    """

    __abstract__ = True

    @classmethod
    def _viewFunc(cls, method):
        def _func(**kwargs):
            inst = cls()
            result = method(inst, **kwargs)
            return result
        return _func

class AppSubcomponent(object):

    __abstract__ = True
    adminLink = None # (url, name) tuple
    requires = []

    def augmentApp(self, app, appInfo):
        pass

    def augmentEnvironment(self, appInfo):
        pass

class SubView(object):
    """
        Base class for all subviews, must implement render returning html
    """

    __abstract__ = True

    @classmethod
    def inject(cls, **kwargs):
        instance = cls(**kwargs)
        return jinja2.Markup(instance.render())

    def render(self):
        return ""

class ResponseException(Exception):

    def __init__(self, response):
        self.response = response

class RedirectException(Exception):

    def __init__(self, location, type=302):
        self.location = location
        self.type = type

def Route(rule, **kwargs):
    # Decorator applied to view methods which sets up a route for that method
    # Accepts all the same kwargs as Flask.add_url_rule
    # If endpoint is not provided, it is auto-generated as ClassName.methodName
    def _func(method):
        if not hasattr(method, '_routes'):
            method._routes = []
        method._routes.append((rule, kwargs))
        return method
    return _func

def resource(path, external=False):
    from web import config
    if external:
        base = config.CONFIG['URL']['STATIC_EXTERNAL']
    else:
        base = config.CONFIG['URL']['STATIC']
    return base + path

def route(name, **kwargs):
    import flask
    if "." not in name:
        name += ".process"
    return flask.url_for(name, _external=False, **kwargs)
