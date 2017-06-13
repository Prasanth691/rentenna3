import flask
import json

from google.appengine.ext.blobstore import blobstore

from web.base import BaseView, Route
from web import validate

from rentenna3.models import *

class JavascriptJournalism(BaseView):

    @Route('/data-lab/<slug>/')
    def index(self, slug):
        jsj = JsjArticle.forSlug(slug)
        blob = blobstore.get(jsj.data)
        data = json.loads(blob.open().read())
        if jsj.template == 'explosion-map':
            return self.explosionMap(jsj, data)
        return "OK"

    def explosionMap(self, jsj, data):
        city = City.forSlug(data['city'])
        return flask.render_template('jsj/explosionMap.jinja2',
            data=data,
            city=city,
            jsj=jsj,
        )