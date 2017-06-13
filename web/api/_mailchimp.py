import flask    
import json
import urllib
import uuid
import random

from google.appengine.api import urlfetch

from web.config import CONFIG
from web import rutil
from web import memcache
from web import keyserver

def mailchimp(method, data, keyName='KEY'):
    if rutil.safeAccess(CONFIG, 'MAILCHIMP', 'MOCK'):
        print "MOCK MAILCHIMP CALL"
        print method
        print data
    else:
        # TODO: eliminate config version once rolled out to all sites
        credentials = keyserver.get()
        if 'MAILCHIMP' in credentials:
            mailchimpCredentials = credentials['MAILCHIMP']
        else:
            mailchimpCredentials = CONFIG['MAILCHIMP']
        
        datacenter = mailchimpCredentials[keyName].split('-')[1]
        url = "https://%(datacenter)s.api.mailchimp.com/2.0/%(method)s.json" % {
            'method': method,
            'datacenter': datacenter,
        }
        payload = {
            'apikey': mailchimpCredentials[keyName],
        }
        payload.update(data)
        result = urlfetch.fetch(
            url=url,
            payload=json.dumps(payload),
            method='POST',
        )

        if result.status_code == 200:
            return json.loads(result.content)
        else:
            print "ERROR"
            print result.content