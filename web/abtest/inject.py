import flask    
import json
import urllib
import uuid
import random

from google.appengine.api import urlfetch

from web.config import CONFIG
from web import rutil
from web import memcache

def abtest():
    if not hasattr(flask.request, 'abtest'):
        flask.request.abtest = _abtestComputeData()
    return getattr(flask.request, 'abtest', None)

def _abtestComputeData():
    reset = flask.request.values.get('_ABTEST_RESET') is not None
    
    if 'ABTO' in flask.session:
        overrides = json.loads(flask.session['ABTO'])
    else:
        overrides = {}

    for (key, value) in flask.request.values.items():
        if key == '_ABTEST_FORCE':
            [experiment, variant] = value.split(":")
            overrides[experiment] = variant

    if overrides:
        flask.session['ABTO'] = json.dumps(overrides)

    if reset or ('_ABTEST_UUID' not in flask.session):
        flask.session['_ABTEST_UUID'] = str(uuid.uuid4())
    userId = flask.session['_ABTEST_UUID']
    
    siteInfo = _abtestSiteInfo(reset)
    assignments = {}
    assignmentNames = {}
    manipulations = [
        "window._kmq = window._kmq || [];"
    ]
    if siteInfo:
        for experiment in siteInfo['experiments']:
            if (experiment['status'] == 'running') or (experiment['id'] in overrides):
                variant = _abtestSelectVariant(userId, experiment, overrides)
                assignments[experiment['name']] = variant['name']
                assignments[experiment['id']] = variant['id']
                manipulations += variant['manipulations']

                assignmentNames["AB Test Group: " + experiment['name']] = variant['name']

        manipulations.append("_kmq.push(['set', %s])" % json.dumps(assignmentNames));
        return {
            'assignments': assignments, 
            'code': "\n".join(manipulations),
        }

def _abtestSiteInfo(reset):
    from web.abtest.models import AbtestExperiment
    key = 'api._abtestSiteInfo:'
    siteInfo = memcache.get(key)
    if (siteInfo is None) or reset:
        experiments = [
            experiment.json()
            for experiment 
            in AbtestExperiment.query().fetch()
            if experiment.status in ['running', 'pending']
        ]
        siteInfo = {'experiments': experiments}
        memcache.set(key, siteInfo, 3600)
    return siteInfo

def _abtestSelectVariant(userId, experiment, overrides):
    if experiment['id'] in overrides:
        overrideId = overrides[experiment['id']]
        matching = [
            variant 
            for variant 
            in experiment['variants'] 
            if variant['id'] == overrideId
        ]
        if matching:
            return matching[0]

    cumulative = 0
    for variant in experiment['variants']:
        cumulative += variant['weight']
        variant['cutoff'] = cumulative

    rando = random.Random()
    rando.seed("%s/%s" % (userId, experiment['id']))
    randomValue = rando.random() * cumulative
    for variant in experiment['variants']:
        if randomValue <= variant['cutoff']:
            return variant