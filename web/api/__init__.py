import flask    
import json
import urllib
import uuid
import random

from google.appengine.api import urlfetch

from web.config import CONFIG
from web import rutil
from web import memcache

from web.api._mailchimp import mailchimp
from web.api._mandrill import sendEmail