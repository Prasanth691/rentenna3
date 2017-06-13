# taskqueue wrapper to set the target to the dispatched module, 
# with the version of the caller

import os
import yaml
import logging
import re
import urllib

from google.appengine.api import taskqueue
from google.appengine.api.taskqueue import TaskTooLargeError

def add(url, params=None, swallow=False, **kwargs):
    if 'target' not in kwargs:
        kwargs['target'] = _getTarget(url)
    try:
        try:
            taskqueue.add(
                url=url, 
                params=params, 
                **kwargs
            )
        except TaskTooLargeError:
            from web.models import TaskPayload
            payload = TaskPayload(payload=params).put()
            taskqueue.add(
                url=url, 
                params={
                    '__task_payload__': payload.urlsafe(),
                }, 
                **kwargs
            )
    except:
        if not swallow:
             raise

def _getDispatch():
    if not hasattr(_getDispatch, 'dispatch'):
        if os.path.exists('./dispatch.yaml'):
            with open('./dispatch.yaml') as disp:
                dispatch = yaml.load(disp.read())
                rules = []
                for rule in dispatch['dispatch']:
                    regex = re.compile(rule['url'].replace('*', '.*'))
                    rules.append({
                        'regex': regex,
                        'module': rule['module']    
                    })
                _getDispatch.dispatch = rules
        else:
            _getDispatch.dispatch = []
    return _getDispatch.dispatch

def _getTarget(url):
    for rule in _getDispatch():
        if rule['regex'].match(url):
            targetVersion = os.environ['CURRENT_VERSION_ID'].split(".")[0]
            targetModule = rule['module']
            return "%s.%s" % (targetVersion, targetModule)
    return 'default'
