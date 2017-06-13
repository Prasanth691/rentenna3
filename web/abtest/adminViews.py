import datetime
import flask
import json
import uuid
import urlparse

from google.appengine.api import memcache
from google.appengine.api import users

from web.admin import requireRole
from web.base import BaseView, Route
from web.models import *
from web import validate

from web.abtest.models import *

class ExperimentView(BaseView):

    @Route('/web-admin/abtest/experiments/<experimentKey>/')
    def get(self, experimentKey):
        requireRole('admin')
        if experimentKey == 'new':
            experiment = {
                'status': "Pending",
                'new': True,
            }
            variations = [{
                'name': "Control",
                'weight': 1.0,
            }]
        else:
            experiment = ndb.Key(urlsafe=experimentKey).get()
            variations = [
                variant.json() 
                for variant 
                in experiment.activeVariants()
            ]

        return flask.render_template('abtest/experimentView.jinja2',
            experiment=experiment,
            variations=variations,
            experimentKey=experimentKey,
        )

    @Route('/web-admin/abtest/experiments/<experimentKey>/', methods=['POST'])
    def post(self, experimentKey):
        requireRole('admin')

        if experimentKey == 'new':
            experiment = AbtestExperiment()
        else:
            experiment = ndb.Key(urlsafe=experimentKey).get()

        experiment.name = flask.request.values.get('name')
        experiment.status = flask.request.values.get('status')
        experiment.defaultPage = flask.request.values.get('defaultPage')

        existingVariants = list(experiment.variants)
        for variant in existingVariants:
            variant.active = False

        variations = validate.get('variations', validate.ParseJson())
        for variation in variations:
            variant = None
            if variation.get('id'):
               for existing in existingVariants:
                   if existing.id == variation.get('id'):
                       variant = existing
            if variant is None:
               variant = AbtestVariant(id=str(uuid.uuid4()))
               experiment.variants.append(variant)

            variant.active = not variation.get('deleted', False)
            variant.name = variation.get('name')
            variant.weight = variation.get('weight')
            variant.js = variation.get('js')
            variant.css = variation.get('css')

        experiment.put()
        return flask.redirect(experiment.getUrl())

class AbtestRootView(BaseView):

    @Route('/web-admin/abtest/')
    def get(self):
        requireRole('admin')
        experiments = AbtestExperiment.query().fetch()
        return flask.render_template('abtest/rootView.jinja2',
            experiments=experiments,
        )