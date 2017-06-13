import urllib
import pipeline
import cloudstorage
import datetime
import importlib
import uuid

from web import api
from web import config
from web import validate
from web import rutil
from web.admin import requireRole
from web.base import BaseView, Route, RedirectException
from web.models import *
from web.adminUser.models import *
from web.pipelines import ReportGenerator

class ChangePassword(BaseView):

    @Route('/web-admin/change-password/')
    def start(self):
        requireRole()
        return flask.render_template('web-admin/changePassword.jinja2', 
            error=validate.get('error')
        )

    @Route('/web-admin/change-password/', methods=['POST'])
    def save(self):
        requireRole()
        oldPassword = validate.get('old', validate.Required())
        newPassword = validate.get('new', validate.Required())
        user = AdminUser.get()
        success = user.setPassword(oldPassword, newPassword)
        if not success:
            return flask.redirect('/web-admin/change-password/?error=true')
        else:
            return flask.redirect('/web-admin/')

class LoginView(BaseView):

    @Route('/web-admin/login/')
    def process(self):
        back = validate.get('back')
        if AdminUser.get() is not None:
            self.goBack(back)
        return flask.render_template('web-admin/loginView.jinja2',
            back=back,
        )

    @Route('/web-admin/login/', methods=['POST'])
    def login(self):
        username = validate.get('username', validate.Required())
        password = validate.get('password', validate.Required())
        back = validate.get('back')

        if AdminUser.loginWithPassword(username, password) is not None:
            return self.goBack(back)
        else:
            return flask.render_template('web-admin/loginView.jinja2',
                back=back,
                error=True,
                username=username,
                password=password
            )

    def goBack(self, back):
        if back:
            return flask.redirect(back)
        else:
            return flask.redirect('/web-admin/')

    @Route('/web-admin/logout/')
    def logout(self):
        back = validate.get('back') or '/web-admin/'
        AdminUser.logout()
        return flask.redirect('/web-admin/login/?%s' % urllib.urlencode({'back': back}))

class WebAdminRootView(BaseView):

    @Route('/web-admin/')
    def get(self):
        requireRole()
        return flask.render_template(
            'web-admin/root.jinja2',
        )

class UploadView(BaseView):

    @Route('/web-admin/upload/', methods=['POST'])
    def upload(self):
        file = flask.request.files['file']
        fileId = str(uuid.uuid4())
        bucket = config.CONFIG['WEB']['UPLOAD_BUCKET']
        gcsPath =  '/%s/%s' % (bucket, fileId)
        with cloudstorage.open(gcsPath, 'w', 
                content_type=file.mimetype, 
                options={'x-goog-acl': "public-read"}
            ) as outfile:
            file.save(outfile)
        urlBase = config.CONFIG['WEB'].get('UPLOAD_URL')
        if urlBase is None:
            urlBase = "https://storage.googleapis.com/%s/" % bucket
        url = urlBase + fileId
        return flask.jsonify({
            'link': url,
        })

    @Route('/web-admin/uploaded-file/<fileId>/')
    def get(self, fileId):
        bucket = config.CONFIG['WEB']['UPLOAD_BUCKET']
        gcsPath =  '/%s/%s' % (bucket, fileId)
    
        stat = cloudstorage.stat(gcsPath)
        mime = stat.content_type

        with cloudstorage.open(gcsPath, 'r') as outfile:
            return flask.Response(
                outfile.read(),
                mimetype=mime,
            )