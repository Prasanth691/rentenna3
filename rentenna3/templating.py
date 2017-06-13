import math
import jinja2
import uuid

from web.templating import jinjaGlobal
from rentenna3.models import Partner


from rentenna3 import text

@jinjaGlobal
def abtest():
    from rentenna3 import api
    return api.abtest()

@jinjaGlobal
def app():
    import flask
    return flask.request.appCustomizer

@jinjaGlobal
def cities():
    from rentenna3.models import City
    return City.important()

@jinjaGlobal
def clientState():
    from rentenna3.models import User
    from web import config
    user = User.get()
    context = {
        'user': user.private(),
    }
    return context
@jinjaGlobal
def comma(value):
    if value is None or value == 'N/A':
        return value
    return "{0:,}".format(value)

@jinjaGlobal
def trendColorClass(trend):
    if trend == 'up':
        return 'green'
    elif trend == 'down':
        return 'orange'
    else:
        return 'blue'
@jinjaGlobal
def oddEvenClass(num):
    cssClass = 'odd'
    if num % 2 == 0:
        cssClass = 'even'
    return cssClass

@jinjaGlobal
def config():
    from web import config
    return config.CONFIG

@jinjaGlobal
def date(value, format="%c"):
    if value is None:
        return ''
    from rentenna3 import util
    value = util.localToEst(value)
    return value.strftime(format)

@jinjaGlobal
def kissmetricsKey():
    from web import keyserver
    credentials = keyserver.get()
    return credentials['kissmetrics']['apikey']

@jinjaGlobal
def markdown(value):
    if value is not None:
        import markdown as markdowner
        html = markdowner.markdown(value)
        return jinja2.Markup(html)

@jinjaGlobal
def partnerTopBottomName(partner):
    return Partner.topBottomName(partner)

@jinjaGlobal
def partnerEmailGreeting(partner):
    if not partner:
        return ''
    name = partner.getSetting('contact.firstname') or ''
    name = name.strip().title()
    return name or partner.name or ''

@jinjaGlobal
def user():
    from rentenna3.models import User
    return User.get()

@jinjaGlobal
def getDistance(distance):
    miles = distance / 1609.34
    return "%.1f mile" % miles

@jinjaGlobal
def getWalkingDistance(distance):
    # estimate ~120 meters per minute
    time = int(math.ceil(distance / 120))
    return "%s min" % time