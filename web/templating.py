import math
import jinja2
import datetime

from urllib2 import urlparse
from web import rutil
from rentenna3 import util

def sniffGlobals(templatingModules):
    jinjaGlobals = {}
    for module in templatingModules:
        for key in dir(module):
            if not key.startswith('_'):
                method = getattr(module, key)
                if getattr(method, '_jinjaGlobal', False):
                    jinjaGlobals[key] = method
        if hasattr(module, 'JINJA_GLOBALS'):
            jinjaGlobals.update(module.JINJA_GLOBALS)
    return jinjaGlobals

def jinjaGlobal(func):
    # decorator to apply to something that 
    # should be added to the globals dict
    func._jinjaGlobal = True
    return func

JINJA_GLOBALS = {
    'abs': abs,
    'now': datetime.datetime.now,
    'plural': rutil.plural,
    'pluralName': rutil.pluralName,
    'sorted': sorted,
    'reversed': reversed,
}

@jinjaGlobal
def adminUser():
    from web.adminUser.models import AdminUser
    return AdminUser.get()

@jinjaGlobal
def appId():
    if not hasattr(appId, '_id'):
        import uuid
        appId._id = str(uuid.uuid4())
    return appId._id

@jinjaGlobal
def ceil(number):
    import math
    return int(math.ceil(number))

@jinjaGlobal
def commas(number, limitDecimals=0):
    if isinstance(number, basestring):
        try:
            number = float(number)
        except ValueError:
            return None
    fmt = "{0:,.%sf}" % limitDecimals
    return fmt.format(number)

@jinjaGlobal
def computerDate(value):
    if value is None:
        return None

    import datetime
    from web import rtime
    if isinstance(value, datetime.datetime):
        value = rtime.toTarget(value)
    if value.year > 1900:
        return value.strftime("%Y-%m-%d")
    else:
        return "ANCIENT HISTORY"

@jinjaGlobal
def computerDatetime(value):
    if value is None:
        return None

    import datetime
    from web import rtime
    if isinstance(value, datetime.datetime):
        value = rtime.toTarget(value)
    return value.strftime("%Y-%m-%dT%H:%M")

@jinjaGlobal
def config():
    from web.config import CONFIG
    return CONFIG

@jinjaGlobal
def humanDate(value, convertToTarget=True, brief=False):
    if value is None:
        return ""
    else:
        if isinstance(value, datetime.datetime) and convertToTarget:
            from web import rtime
            value = rtime.toTarget(value)
        if brief:
            return value.strftime("%m/%d/%y")
        else:
            return value.strftime("%A, %B %d %Y")

@jinjaGlobal
def humanDateTime(value, convertToTarget=True, brief=False, pattern=None):
    if value is None:
        return ""
    else:
        if isinstance(value, datetime.datetime) and convertToTarget:
            from web import rtime
            value = rtime.toTarget(value)
        if brief:
            pattern = pattern or "%m/%d/%y %I:%M%p"
        else:
            pattern = pattern or "%A, %B %d %Y %I:%M%p"
        
        return value.strftime(pattern)

@jinjaGlobal
def iff(eval, value, elseValue=""):
    if eval:
        return value
    else:
        return elseValue

@jinjaGlobal
def isAddress(value):
    from rentenna3.models import Address
    return (value is None) or isinstance(value, Address)

@jinjaGlobal
def isMissing(value):
    return (value is None) or isinstance(value, jinja2.Undefined)

@jinjaGlobal
def jsonify(object):
    import json
    return jinja2.Markup(json.dumps(object))

@jinjaGlobal
def money(value, cents=True, inPennies=False):
    if isMissing(value): 
        return ""
    
    if isinstance(value, basestring):
        value = float(value)

    if inPennies:
        value = float(value)/100
        
    if cents:
        return '${:0,.2f}'.format(value)
    else:
        return '${:0,.0f}'.format(value)

@jinjaGlobal
def pageLink(page):
    import flask
    import urllib
    args = flask.request.args.to_dict()
    path = flask.request.path
    if page == 1:
        if 'page' in args:
            del args['page']
    else:
        args['page'] = page
    queryString = urllib.urlencode(args)
    if queryString:
        return "%s?%s" % (
            path,
            queryString,
        )
    else:
        return path

@jinjaGlobal
def percent(value, alreadyBase100=False, decimal=False):
    if value is not None:
        if not alreadyBase100:
            value = 100 * value
        if not decimal:
            value = int(value)
        return "%s%%" % value

@jinjaGlobal
def phone(value):
    if value is None:
        return None
    else:
        return "(%s) %s-%s" % (value[0:3], value[3:6], value[6:])

@jinjaGlobal
def photoServingUrl(filepath, size=None):
    if not filepath:
        return None

    url = filepath
    lower = filepath.lower()
    if '/subdomain-image/' in lower or '/partner-image/' in lower:
        parts = filepath.split("/")
        uid = parts[-1]
        if not uid:
            uid = parts[-2]
        gsFilePath = '/%s/%s' % (
                config()['WEB']['UPLOAD_BUCKET'],
                uid,
            )

        url = util.getPhotoServingUrl(gsFilePath, size=size)
    return url

@jinjaGlobal
def resource(path):
    from web.base import resource
    return resource(path)

@jinjaGlobal
def route(name, **kwargs):
    from web.base import route
    return route(name, **kwargs)

@jinjaGlobal
def safeLen(obj):
    if obj is None:
        return 0
    else:
        return len(obj)

@jinjaGlobal
def storage(bytes):
    if bytes is not None:
        kilobytes = bytes/1024
        if kilobytes < 10:
            return "%s B" % commas(int(bytes))
        megabytes = bytes/1024/1024
        if megabytes < 10:
            return "%s KB" % commas(int(kilobytes))
        gigabytes = bytes/1024/1024/1024
        if gigabytes < 10:
            return "%s MB" % commas(int(megabytes))
        return "%s GB" % commas(int(gigabytes))

@jinjaGlobal
def tracker():
    from web import tracking
    return tracking.get()

@jinjaGlobal
def uniqueId(prefix):
    uniqueId._uniqueCounter += 1
    return "%s_%s" % (prefix, uniqueId._uniqueCounter)
uniqueId._uniqueCounter = 0

@jinjaGlobal
def urlJoin(base, url):
    return urlparse.urljoin(base, url)

@jinjaGlobal
def versioned(file):
    return resource("%s?version=%s" % (file, versionId()))

@jinjaGlobal
def versionId():
    from web.config import CONFIG
    return CONFIG['tag']['hash']

def nullable(val):
    if val is None:
        return ""
    else:
        return val