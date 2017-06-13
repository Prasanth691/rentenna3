import json
from web import config
from web import rutil
from web import keyserver

from google.appengine.api import urlfetch

def sendEmail(
        html, 
        subject, 
        fromEmail, 
        toEmail, 
        fromName=None, 
        toName=None,
        autoText=True,
        trackClicks=False,
        trackOpens=False,
        inlineCss=False,
        toBcc=None,
        attachments=None,
        replyTo=None
    ):
    url = "https://mandrillapp.com/api/1.0/messages/send.json"

    toArray = [ {'email': toEmail, 'name': toName} ]

    if toBcc:
        toArray.append( {'email' : toBcc, 'name' : toName, 'type' : 'bcc'} )

    headers = {}

    if replyTo:
        headers['Reply-To'] = replyTo

    payload = {
        'async': True,
        'message': {
            'html': html,
            'subject': subject,
            'from_email': fromEmail,
            'from_name': fromName,
            'to': toArray,
            'auto_text': autoText,
            'track_clicks': trackClicks,
            'track_opens': trackOpens,
            'inline_css': inlineCss,
            'attachments': attachments,
            'headers' : headers,
        }
    }
    if rutil.safeAccess(config.CONFIG, 'MANDRILL', 'MOCK'):
        print "WOULD  POST"
        print url
        print payload
    else:
        # TODO: eliminate config version once rolled out to all sites
        credentials = keyserver.get()
        mandrillCredentials = credentials['MANDRILL']

        payload['key'] = mandrillCredentials['API_KEY']
        urlfetch.fetch(url, method='POST', payload=json.dumps(payload))