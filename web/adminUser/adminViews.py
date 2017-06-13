import flask
import time

from web.base import BaseView, Route
from web.admin import requireRole
from web import validate
from web.adminUser.models import *

class UserAdminView(BaseView):

    @Route('/web-admin/manage-users/')
    def manage(self):
        requireRole('manage-users')
        users = AdminUser.query().fetch()
        return flask.render_template('web-admin/userAdmin.jinja2', users=users)

    @Route('/web-admin/manage-users/save-roles/', methods=['POST'])
    def saveRoles(self):
        requireRole('manage-users')
        users = AdminUser.query().fetch()
        for user in users:
            user.roles = validate.get('role-%s' % user.login).split(",")
            user.put()
        time.sleep(3)
        return flask.redirect('/web-admin/manage-users/')

    @Route('/web-admin/manage-users/add-user/', methods=['POST'])
    def addUser(self):
        requireRole('manage-users')
        login = validate.get('login', validate.Required())
        password = validate.get('password', validate.Required())
        user = AdminUser(
            key=ndb.Key(AdminUser, login),
            login=login
        )
        user._updatePassword(password)
        user.put()
        time.sleep(3)
        return flask.redirect('/web-admin/manage-users/')
