import random
import hashlib
import uuid
import flask
import json

from google.appengine.ext import ndb

class AbtestVariant(ndb.Model):

    active = ndb.BooleanProperty()
    id = ndb.StringProperty()
    name = ndb.StringProperty()
    css = ndb.TextProperty()
    js = ndb.TextProperty()
    weight = ndb.FloatProperty()

    def getManipulations(self):
        manipulations = []

        if self.js:
            manipulations.append("""
                try { 
                    %s 
                }
                catch(err) {}
            """ % self.js)

        if self.css:
            manipulations.append("""
                var css = %s;
                var style = document.createElement('style');
                style.type = 'text/css';
                if(style.styleSheet) {
                    style.styleSheet.cssText = css;
                }
                else {
                    style.appendChild(document.createTextNode(css));
                }
                var head = document.head || document.getElementsByTagName('head')[0];
                head.appendChild(style);
            """ % json.dumps(self.css))

        return manipulations

    def json(self):
        return {
            'active': self.active,
            'name': self.name,
            'js': self.js,
            'css': self.css,
            'weight': self.weight,
            'id': self.id,
            'manipulations': self.getManipulations(),
        }

class AbtestExperiment(ndb.Model):

    defaultPage = ndb.StringProperty()
    name = ndb.StringProperty()
    variants = ndb.LocalStructuredProperty(AbtestVariant, repeated=True)
    status = ndb.StringProperty()

    def activeVariants(self):
        return [variant for variant in self.variants if variant.active]

    def randomVariant(self, userUuid):
        # TODO: this seems slow...
        activeVariants = self.activeVariants()
        cumulative = 0
        for variant in activeVariants:
            cumulative += variant.weight
            variant.cutoff = cumulative

        rando = random.Random()
        rando.seed("%s/%s" % (userUuid, self.key.id()))
        randomValue = rando.random() * cumulative
        for variant in activeVariants:
            if randomValue <= variant.cutoff:
                return variant
    
    def variantById(self, id, userUuid):
        activeVariants = self.activeVariants()
        for variant in activeVariants:
            if variant.id == id:
                return variant

        return self.randomVariant(userUuid)

    def json(self):
        return {
            'name': self.name,
            'variants': [
                variant.json() 
                for variant 
                in self.activeVariants()
            ],
            'status': self.status,
            'id': str(self.key.id()),
        }

    def getUrl(self):
        return '/web-admin/abtest/experiments/%s/' % (self.key.urlsafe())