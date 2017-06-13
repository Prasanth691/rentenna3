import flask
import pipeline
import hashlib
import datetime
import re
import hashlib
import base64

from pipeline import PipelineStatusError
from google.appengine.ext import ndb

from web import config
from web import api
from web import memcache

class AdminUser(ndb.Model):

    login = ndb.StringProperty()
    passwordHash = ndb.StringProperty()
    roles = ndb.StringProperty(repeated=True)

    @classmethod
    def _get_kind(cls):
        return 'AdminUserItem'

    @classmethod
    def get(cls):
        if not hasattr(flask.request, 'adminUser'):
            userToken = flask.session.get('userToken')
            flask.request.adminUser = None
            if userToken is not None: 
                userModel = ndb.Key(urlsafe=userToken).get()
                if userModel:
                    flask.request.adminUser = userModel
        return flask.request.adminUser

    @classmethod 
    def hash(cls, login, password):
        return hashlib.sha224(login + password).hexdigest()

    @classmethod
    def loginWithPassword(cls, username, password):
        user = ndb.Key('AdminUserItem', username).get()
        passwordHash = cls.hash(username, password)
        if user:
            if passwordHash == user.passwordHash:
                flask.session['userToken'] = user.key.urlsafe()
                return user

    @classmethod
    def logout(cls):
        flask.session['userToken'] = None

    def hasRole(self, roleName):
        if 'super' in self.roles:
            return True
        else:
            prefix = config.CONFIG['WEB']['SITE_PREFIX']
            if ("%s-super" % prefix) in self.roles:
                return True
            if ("*-%s" % roleName) in self.roles:
                return True
            return ("%s-%s" % (prefix, roleName)) in self.roles

    def isSuper(self):
        return self.hasRole('super')

    def setPassword(self, oldPassword, newPassword):
        loggedIn = self.loginWithPassword(self.login, oldPassword)
        if loggedIn:
            loggedIn._updatePassword(newPassword)
            return True
        else:
            return False

    def _updatePassword(self, newPassword):
        self.passwordHash = hashlib.sha224(self.login + newPassword).hexdigest()