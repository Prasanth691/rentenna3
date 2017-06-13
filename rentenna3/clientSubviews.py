import json
import math
import flask

from web import taskqueue
from web.base import SubView

from rentenna3 import util
from rentenna3.models import *

class AddressAutocomplete(SubView):

    def __init__(self, action='report'):
        self.action = action

    def render(self):
        return flask.render_template('client/addressAutocomplete.nunjucks',
            action=self.action,
        )

class FullBadge(SubView):

    def __init__(self, badge):
        self.badge = badge

    def render(self):
        return flask.render_template('client/fullBadge.jinja2',
            badge=self.badge,
        )

class PoiCompareToParentBox(SubView):

    def __init__(self, address, type, googlePlaceType, count, parentCount):
        self.address = address
        self.type = type
        self.googlePlaceType = googlePlaceType
        self.count = count
        self.parentCount = parentCount

    def render(self):
        context = {
            'address': self.address,
            'type': self.type,
            'count': self.count,
            'googlePlaceType': self.googlePlaceType
        }

        if self.parentCount:
            context['parentCount'] = self.parentCount
            diff = int(util.diffPercent(self.count, self.parentCount))
            context['difference'] = diff
            if diff == 0:
                context['valence'] = 'neutral'
            elif diff > 0:
                context['valence'] = 'positive'
            else:
                context['valence'] = 'negative'

        return flask.render_template('client/poiCompareToParentBox.jinja2', **context)

class StickyHeader(SubView):

    def __init__(self, sections):
        self.sections = sections

    def render(self):
        # TODO: how to determine the sections?
        return flask.render_template('client/stickyHeader.jinja2',
            sections=self.sections,
        )
