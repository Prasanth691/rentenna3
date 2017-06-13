import flask
import pipeline
import hashlib
import datetime
import re
import hashlib
import uuid
import pickle
import base64

from pipeline import PipelineStatusError
from google.appengine.ext import ndb

from web import config
from web import api
from web import memcache
from web import tracking

class ReportLog(ndb.Model):

    pipelineId = ndb.StringProperty()
    reportId = ndb.StringProperty()
    reportName = ndb.StringProperty()
    reportInfo = ndb.StringProperty()
    run = ndb.DateTimeProperty(auto_now_add=True)

    @classmethod
    def putHeader(cls, reportId, header):
        from web.models import LongTermCache
        LongTermCache.putKey(
            'ReportLog:header:%s' % reportId,
            header,
        )

    def getCloudstoragePath(self):
        bucket = config.CONFIG['PIPELINE']['BUCKET']
        return '/%s/%s' % (bucket, self.reportId)

    def getDownloadUrl(self):
        return "/web-admin/reports/download/%s/" % self.key.urlsafe()

    def getHeader(self):
        from web.models import LongTermCache
        header = LongTermCache.getKey(
            'ReportLog:header:%s' % self.reportId,
        )
        return header

    def getInfoUrl(self):
        return "/web-admin/reports/%s/" % self.key.urlsafe()

    def getPreviewUrl(self):
        return "/web-admin/reports/preview/%s/" % self.key.urlsafe()

    def getStatusUrl(self):
        return "/web-admin/reports/status/%s/" % self.key.urlsafe()

    def getStatus(self):
        try:
            tree = pipeline.get_status_tree(self.pipelineId)
        except PipelineStatusError:
            return {
                'total': 0,
                'finalizing': 0,
                'done': 0,
                'status': 'run',
                'percent': 0,
            }

        # statuses: finalizing, run, waiting, done
        statuses = [p['status'] for p in tree['pipelines'].itervalues()]
        total = len(statuses)
        finalizing = len([status for status in statuses if status == 'finalizing'])
        done = len([status for status in statuses if status == 'done'])
        rootStatus = tree['pipelines'][self.pipelineId]['status']
        percent = ((0.5 * finalizing) + (1.0 * done)) / (1.0 * total)
        return {
            'total': total,
            'finalizing': finalizing,
            'done': done,
            'status': rootStatus,
            'percent': percent,
        }