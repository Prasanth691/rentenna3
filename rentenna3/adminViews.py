import cloudstorage
import copy
import json
import flask
import re
import urllib
import uuid
import bson
import datetime
import base64
import datetime
import hashlib

from bson import json_util
from zipfile import ZipFile

import cloudstorage as gcs
from google.appengine.ext.blobstore import blobstore
from google.appengine.ext.blobstore import BlobInfo
from google.appengine.datastore.datastore_query import Cursor
from google.appengine.ext.ndb import KindError

from web import validate
from web.base import BaseView, SubView, Route
from web.admin import requireRole
from web.models import *
from web.adminUser.models import *
from web.data.leadRestrictions import LeadRestriction
from web.data.emailSuppressions import EmailSuppression
from web import taskqueue
from web import config
from web import memcache
from web import rtime
from web.pager import NdbSimplePager, MongoTimePager
from web.mongoAggs import PartnerSummaryAggregate, PartnerSummaryAggsPipeline

from rentenna3 import util
from rentenna3.models import *

import rentenna3.base

class Admin(BaseView):

    @Route('/admin/')
    def get(self):
        user = AdminUser.get()
        if user is None:
            return flask.redirect('/web-admin/login/')
        else:
            requireRole('admin')
            return flask.render_template('admin/root.jinja2')

class BlogAdmin(BaseView):

    @Route('/admin/blog/')
    def list(self):
        requireRole('admin')
        posts = BlogPost.recent().fetch()
        return flask.render_template('admin/blogList.jinja2',
            posts=posts
        )

    @Route('/admin/blog/edit-post/')
    def edit(self):
        requireRole('admin')
        postSlug = flask.request.values.get('post')
        if postSlug == 'new':
            post = {
                'slug': 'new',
                'date': datetime.datetime.now()
            }
        else:
            post = BlogPost.forSlug(postSlug)

        return flask.render_template('admin/blogPost.jinja2',
            post=post,
        )

    @Route('/admin/blog/edit-post/', methods=['POST'])
    def save(self):
        requireRole('admin')
        postSlug = validate.get('post')

        if postSlug == 'new':
            post = BlogPost.new()
        else:
            post = BlogPost.forSlug(postSlug)


        post.title = validate.get('title', validate.Required())
        post.slug = validate.get('slug', validate.Required())
        post.seoTitle = validate.get('seoTitle')
        post.date = validate.get('date',
            validate.ParseDate(),
            validate.Required())
        post.status = validate.get('status', validate.Required())
        post.content = validate.get('content')
        post.put()

        return flask.redirect(post.getAdminUrl(), code=301)

class EmailAdmin(BaseView):

    @Route('/admin/email-log/')
    def emailLog(self):

        query = {'shard': config.CONFIG['EMAIL']['shard']}

        pager = MongoTimePager(
            modelCls=EmailSendLog, 
            query=query, 
            pageSize=50, 
            url='/admin/email-log/',
            dateField='date'

        )

        if pager.redirectUrl():
            return flask.redirect(pager.redirectUrl())

        return flask.render_template('admin/listEmails.jinja2',
            emails=pager.items(),
            page=pager.page(),
            hasNext=pager.hasNext(),
        )

    @Route('/admin/email-log/<emailId>/')
    def emailView(self, emailId):
        emailId = MongoModel.fromUrlsafe(emailId)
        log = email = EmailSendLog.queryFirst({'_id': emailId})
        email = EmailSendLogContent.queryFirst({'_id': emailId})
        logging.info(log['tags'])
        return email['html']

    @Route('/admin/preview-emails/')
    def previewEmails(self):
        emails = rentenna3.base._emails
        return flask.render_template(
            'admin/previewEmails.jinja2',
            emails=sorted(emails.keys()),
        )

    @Route('/admin/preview-emails/<template>/')
    def previewEmail(self, template):
        emailCls = rentenna3.base._emails[template]
        testData = emailCls.getTestData()
        emailer = emailCls(**testData)
        emailData = emailer.renderEmail()
        # TODO: PREVIEW MAIL CLIENT
        return emailData['html']

    @Route('/admin/partner-free-trial/email-log/')
    def partnerFreeTrialEmailLog(self):

        query = {'shard': config.CONFIG['EMAIL']['shard'], 'template': 'PartnerFreeTrial'}

        pager = MongoTimePager(
            modelCls=PartnerEmailSendLog, 
            query=query, 
            pageSize=50, 
            url='/admin/partner-free-trial/email-log/',
            dateField='date'
        )

        if pager.redirectUrl():
            return flask.redirect(pager.redirectUrl())

        return flask.render_template('admin/listPartnerEmails.jinja2',
            emails=pager.items(),
            page=pager.page(),
            hasNext=pager.hasNext(),
            title="Recent Free Trial Emails"
        )

    @Route('/admin/partner-email-log/<emailId>/')
    def partnerEmailView(self, emailId):
        emailId = MongoModel.fromUrlsafe(emailId)
        #log = email = PartnerEmailSendLog.queryFirst({'_id': emailId})
        email = PartnerEmailSendLogContent.queryFirst({'_id': emailId})
        return email['html']

    @Route('/admin/ar-email/email-log/')
    def arEmailLog(self):

        query = {'shard': config.CONFIG['EMAIL']['shard']}

        pager = MongoTimePager(
            modelCls=ArEmailSendLog, 
            query=query, 
            pageSize=50, 
            url='/admin/ar-email/email-log/',
            dateField='date'
        )

        if pager.redirectUrl():
            return flask.redirect(pager.redirectUrl())

        return flask.render_template('admin/listPartnerEmails.jinja2',
            emails=pager.items(),
            page=pager.page(),
            hasNext=pager.hasNext(),
            title="Recent Emails sent to Address Report"
        )

    @Route('/admin/ar-email-log/<emailId>/')
    def arEmailView(self, emailId):
        emailId = MongoModel.fromUrlsafe(emailId)
        email = ArEmailSendLogContent.queryFirst({'_id': emailId})
        return email['html']

class ImageUploadEndpoint(BaseView):

    @Route('/admin/upload-image/', methods=['POST'])
    def upload(self):
        requireRole('admin')

        data = flask.request.values.get('data')

        # strip the data: marker
        data = data[5:]
        [meta, data] = data.split(",", 1)
        [mimetype, encoding] = meta.split(";")

        if encoding != 'base64':
            flask.abort(400)

        if not mimetype.startswith('image/'):
            flask.abort(400)

        image = Image()
        image.data = base64.b64decode(data)
        image.mimetype = mimetype
        image.put()

        return flask.jsonify({
            'status': "OK",
            'id': image.key.id(),
        })

    @Route('/image/<int:id>')
    def server(self, id):
        image = Image.get_by_id(id)
        # TODO: any kind of resizing gobblegook?
        return flask.Response(image.data, mimetype=image.mimetype)

class JsjArticleAdmin(BaseView):

    @Route('/admin/jsj/')
    def list(self):
        requireRole('admin')
        posts = JsjArticle.query().order(-JsjArticle.date).fetch()
        return flask.render_template('admin/jsjList.jinja2',
            posts=posts
        )

    @Route('/admin/jsj/edit-post/')
    def edit(self):
        requireRole('admin')
        postSlug = flask.request.values.get('post')
        if postSlug == 'new':
            post = {
                'slug': 'new',
                'date': datetime.datetime.now()
            }
        else:
            post = JsjArticle.forSlug(postSlug)

        uploadUrl = blobstore.create_upload_url(
            success_path='/admin/jsj/edit-post/?post=%s' % postSlug,
        )

        return flask.render_template('admin/jsjPost.jinja2',
            post=post,
            uploadUrl=uploadUrl,
        )

    @Route('/admin/jsj/edit-post/', methods=['POST'])
    def save(self):
        requireRole('admin')
        postSlug = validate.get('post')

        if postSlug == 'new':
            post = JsjArticle.new()
        else:
            post = JsjArticle.forSlug(postSlug)

        fileResponse = util.handleUpload('file')
        if fileResponse:
            file, key = fileResponse
            post.data = blobstore.BlobKey(key)

        post.title = validate.get('title', validate.Required())
        post.slug = validate.get('slug', validate.Required())
        post.date = validate.get('date',
            validate.ParseDate(),
            validate.Required())
        post.status = validate.get('status', validate.Required())
        post.template = validate.get('template', validate.Required())
        post.description = validate.get('description')
        post.put()

        return flask.redirect(post.getAdminUrl(), code=301)

class PartnerAdmin(BaseView):

    @Route('/admin/partners/<key>/reset/<setting>/' ,methods=['GET'])
    def resetSetting(self, key, setting):
        requireRole('admin')
        partner = ndb.Key(urlsafe=key).get()
        partner.settings[setting] = None
        partner.put()
        return "OK"

    @Route('/admin/partners/')
    def root(self):
        requireRole('admin')
        query = Partner.query()
        partners = query.filter(Partner.parentKey == None).fetch()
        return flask.render_template(
            'admin/partnerList.jinja2',
            partners=partners,
        )

    @Route('/admin/partners/<key>/bulk/', methods=['GET'])
    def bulkForm(self, key):
        partner = ndb.Key(urlsafe=key).get()
        bucket = config.CONFIG['WEB']['PARTNER_BULK_BUCKET']
        logs = None
        gcsFiles = [('', '--- select a zip file to load or remove ---')]
        if partner.parentKey is None:
            logs= map(
                lambda bulkLog: bulkLog.getLog(),
                PartnerBulkLog.forPartnerKey(partner.key, limit=10)
            )
            stats = gcs.listbucket( '/%s/%s/' % (bucket, partner.pid) )
            for stat in stats:
                gcsFiles.append( (stat.filename, stat.filename) )

        url = '/admin/partnerbulk/%s/%s/'
        loadUrl = url % ('load', key)
        removeUrl = url % ('remove', key)
        return flask.render_template(
            'admin/partnerBulk.jinja2',
            breadcrumbs=self.breadcrumbs(partner),
            gcsFiles=gcsFiles,
            logs=logs,
            loadUrl=loadUrl,
            removeUrl=removeUrl,
            partner=partner,
        )

    @Route('/admin/partner/<key>/dashboard/', methods=['GET'])
    def dashboardForm(self, key):
        requireRole('admin')

        if key == 'address-report':
            partner = None
            breadcrumbs={}
            apiKey = None
            apiSecret = None
        else:
            partner = ndb.Key(urlsafe=key).get()
            breadcrumbs=self.breadcrumbs(partner)
            apiKey = partner.apiKey
            apiSecret = partner.apiSecret

        analyticsUrl = '/api/0/analytics/partner-stats.json'

        return flask.render_template('admin/partnerDashboard.jinja2',
            breadcrumbs=breadcrumbs,
            analyticsUrl=analyticsUrl,
            apiKey=apiKey,
            apiSecret=apiSecret,
        )

    @Route('/admin/partner/address-report/free-trial/', methods=['GET'])
    def partnerFreeTrials(self):
        requireRole('admin')
        
        logs = PartnerFreeTrialLog.query()\
            .fetch()
        
        return flask.render_template('admin/partnerFreeTrialRoot.jinja2',
            logs=logs,
        )

    @Route('/admin/partners/<key>/export/', methods=['GET'])
    def exportForm(self, key):
        requireRole('admin')
        partner = ndb.Key(urlsafe=key).get()
        logs = None

        downloadUrl = None
        downloadCreated = None
        lastLog = self.getFirstExportLog(partner, 'partner-basic')
        if lastLog:
            downloadUrl = '/admin/partners/download/%s/' % lastLog.key.urlsafe()
            downloadCreated = lastLog.created

        billingDownloadUrl = None
        billingDownloadCreated = None
        lastBillingLog = self.getFirstExportLog(partner, 'partner-billing')
        if lastBillingLog:
            billingDownloadUrl = '/admin/partners/download/%s/' % lastBillingLog.key.urlsafe()
            billingDownloadCreated = lastBillingLog.created

        firstDayThisMonth = datetime.date.today().replace(day=1)
        lastDayPrevMonth = firstDayThisMonth - datetime.timedelta(days=1)
        firstDayPrevMonth = (firstDayThisMonth - datetime.timedelta(days=1)).replace(day=1)

        return flask.render_template('admin/partnerExport.jinja2',
            breadcrumbs=self.breadcrumbs(partner),
            exportPartnerUrl='/admin/partners/%s/export/run/' % partner.key.urlsafe(),
            downloadUrl=downloadUrl,
            downloadCreated=rtime.formatTime(downloadCreated),
            billingDownloadUrl=billingDownloadUrl,
            billingDownloadCreated=rtime.formatTime(billingDownloadCreated),
            billingStart=util.getYMDStr(firstDayPrevMonth),
            billingEnd=util.getYMDStr(lastDayPrevMonth),
            partner=partner,
        )

    def getFirstExportLog(self, partner, exportType):
        log = PartnerExportLog.query(PartnerExportLog.partnerKey == partner.key)\
            .filter(PartnerExportLog.exportType == exportType)\
            .filter(PartnerExportLog.isDone==True)\
            .order(-PartnerExportLog.created)\
            .get()
        return log

    @Route('/admin/partners/<key>/')
    def edit(self, key):
        return self.internalEditPartner(key)

    @Route('/admin/partners/<parentKey>/new/')
    def editSubPartner(self, parentKey):
        return self.internalEditPartner('new', parentKey)

    @Route('/admin/partners/<key>/', methods=['POST'])
    def save(self, key):
        return self.internalSavePartner(key)

    @Route('/admin/partners/<key>/new/', methods=['POST'])
    def saveSubPartner(self, key):
        return self.internalSavePartner("new")

    @Route('/admin/partner/<key>/free-trial/email/')
    def sendFreeTrialEmail(self, key):
        requireRole('admin')
        partner = ndb.Key(urlsafe=key).get()
        if not partner:
            return "no partner found"

        PartnerFreeTrial(partner=partner).send(partner)
        return "ok"


    def internalEditPartner(self, key, parentKey=None):
        requireRole('admin')

        isNew = False
        if key == "new":
            isNew = True
            partner = Partner()
        else:
            partner = ndb.Key(urlsafe=key).get()

        parentPartner = None
        if partner.parentKey is not None:
            parentPartner = partner.parentKey.get()
        elif parentKey is not None:
            parentPartner = ndb.Key(urlsafe=parentKey).get()

        if isNew and parentPartner is not None:
            partner.parentKey = parentPartner.key
            partner.ancestorKeys = parentPartner.ancestorKeys + [partner.parentKey]

        bulkUrl = ''
        exportUrl = ''
        dashboardUrl = ''
        urlKey = 'thisisadummyone'
        if partner.key:
            urlKey = partner.key.urlsafe()
            bulkUrl = '/admin/partners/%s/bulk/' % urlKey
            exportUrl = '/admin/partners/%s/export/' % urlKey
            dashboardUrl = '/admin/partner/%s/dashboard/' % urlKey

        enableFreeTrial = not isNew
        trailEmailHandlerUrl = '/admin/partner/%s/free-trial/email/' % urlKey

        return flask.render_template(
            'admin/partnerForm.jinja2',
            breadcrumbs=self.breadcrumbs(partner),
            bulkUrl=bulkUrl,
            dashboardUrl=dashboardUrl,
            exportUrl=exportUrl,
            descendantNameUrlPairs=self.getDescendantNameUrlPairs(partner),
            isNew=isNew,
            partner=partner,
            parentPartner=parentPartner,
            subsections=self.generateSubsections(),
            states=sorted(State.all(), key=lambda state: state.name),
            leadRestrictions=sorted(LeadRestriction.all(), key=lambda restriction:restriction.name),
            emailSuppressions=sorted(EmailSuppression.all(), key=lambda suppression:suppression.name),
            enableFreeTrial=enableFreeTrial,
            trailEmailHandlerUrl=trailEmailHandlerUrl,
        )

    def internalSavePartner(self, key):
        requireRole('admin')
        pid = validate.get('pid', validate.Required())
        if key == "new":
            parentPartner = None
            parentKey = validate.get('parentKey', validate.NdbKey())
            if parentKey is not None:
                parentPartner = parentKey.get()
            partner = Partner.create(parentPartner, pid)
        else:
            partner = ndb.Key(urlsafe=key).get()

        partner.domains = map( lambda domain: domain.strip(), validate.get('domains').split(",") )
        partner.name = validate.get('name')
        partner.pid = pid
        partner.status = validate.get('status')

        settings = dict((key, True) for key in validate.getMulti('section'))
        
        settings.update( dict(("state.%s" % key, True) for key in validate.getMulti('state')) )
        settings.update( dict(("lead.restriction.%s" % key, True) for key in validate.getMulti('leadRestriction')) )
        settings.update( dict(("email.suppression.%s" % key, True) for key in validate.getMulti('emailSuppression')) )

        settings['alerts'] = validate.get('alerts', validate.ParseBool())
        settings['enableBreadcrumbs'] = validate.get('enableBreadcrumbs', validate.ParseBool())
        settings['enableReplyTo'] = validate.get('enableReplyTo', validate.ParseBool())
        settings['createSubPartner'] = validate.get('createSubPartner', validate.ParseBool())
        settings['headerColor'] = validate.get('headerColor')
        settings['nav'] = validate.get('nav', validate.ParseBool())
        settings['renderFullReports'] = validate.get('renderFullReports', validate.ParseBool())
        settings['users'] = validate.get('users', validate.ParseBool())
        settings['leadDistribution'] = validate.get('leadDistribution', validate.ParseBool())
        settings['leadTargets'] = validate.get('leadTargets')
        settings['branding.position'] = validate.get('brandingPosition')
        settings['branding.cobranding'] = validate.get('cobranding', validate.ParseBool())
        settings['contact.firstname'] = validate.get('contact.firstname')
        settings['contact.lastname'] = validate.get('contact.lastname')
        settings['contact.email'] = validate.get('contact.email')
        settings['contact.phone'] = validate.get('contact.phone')
        settings['contact.license'] = validate.get('contact.license')
        settings['contact.company'] = validate.get('contact.company')
        settings['contact.office'] = validate.get('contact.office')
        settings['contact.website'] = validate.get('contact.website')
        settings['notificationEmail'] = validate.get('notificationEmail')
        settings['notificationRecipient'] = validate.get('notificationRecipient')
        settings['leadEmail'] = validate.get('leadEmail')
        settings['customLink'] = validate.get('customLink')
        settings['customLinkLabel'] = validate.get('customLinkLabel')
        settings['logoLink'] = validate.get('logoLink')
        settings['skipAlertConfirmation'] = validate.get('skipAlertConfirmation', validate.ParseBool())
        # settings['senderEmail'] = validate.get('senderEmail')
        # settings['senderName'] = validate.get('senderName')
        settings['replyToEmail'] = validate.get('replyToEmail')
        settings['trackingHeaderSection'] = validate.get('trackingHeaderSection')
        settings['trackingFooterSection'] = validate.get('trackingFooterSection')
        
        preferredDomain = validate.get("preferredDomain")
        if not preferredDomain and partner.domains:
            preferredDomain = partner.domains[0]
        settings['preferredDomain'] = preferredDomain

        logoFile = flask.request.files.get('file')
        self.assignImageSetting(partner, settings, 'logo', logoFile)

        contactLogoFile = flask.request.files.get('contact.photo')
        self.assignImageSetting(partner, settings, 'contact.photo', contactLogoFile)

        if partner.parentKey is not None:
            parentSettings = partner.parentKey.get().getSettings()
            settingKeys = list( key for key in parentSettings.keys() if key.startswith(('state.', 'suppression.', 'lead.restriction.', 'email.suppression.')) )

            for key in settingKeys:
                if settings.get(key) is None:
                    settings[key] = False

        for key, val in list( (key, val) for key, val in Partner.getDefaultSettings().items() if key.startswith('suppression.') ):
            if key not in settings and val:
                settings[key] = False
        partner.settings = settings
        partner.put()

        return flask.redirect(partner.getAdminUrl(), code=301)

    def assignImageSetting(self, partner, settings, name, file):
        if file and file.mimetype in ['image/gif', 'image/jpeg', 'image/png']:
            uid = str(uuid.uuid4())
            csfile = cloudstorage.open(
                '/%s/%s' % (
                    config.CONFIG['WEB']['UPLOAD_BUCKET'],
                    uid,
                ),
                'w',
                content_type=file.mimetype
            )
            file.save(csfile)
            settings[name] = "/subdomain-image/%s/" % uid

            csfile.close()
        else:
            settings[name] = partner.getLocalSettings().get(name)

    def breadcrumbs(self, partner):

        partnersUrl = "/admin/partners/"

        breadcrumbs = [
            {
                'url': partnersUrl,
                'title': "Partners",
            }
        ]

        if partner.ancestorKeys:
            ancestors = ndb.get_multi(partner.ancestorKeys)
            for ancestor in ancestors:
                breadcrumbs.append({
                    'url': "%s%s/" % (partnersUrl, ancestor.key.urlsafe()),
                    'title': ancestor.name
                })

        breadcrumbs.append({
            'title': partner.name
        })

        return breadcrumbs

    def getDescendantNameUrlPairs(self, partner):
        subPartners = []

        if partner.key is not None:
            subPartners = Partner\
                .query()\
                .filter(Partner.parentKey == partner.key)\
                .order(Partner.name)\
                .fetch(projection=[Partner.name])

        nameUrlPairs = map(lambda subPartner: ('/admin/partners/%s/' % subPartner.key.urlsafe(), subPartner.name), subPartners)
        nameUrlPairs.insert(0, ('', '--- select a sub partner to edit ---'))
        return nameUrlPairs

    def generateSubsections(self):
        subsections = []
        for type, sections in sorted(rentenna3.base._reportSections.items()):
            if type:
                currentType = []
                subsections.append((type, currentType))
                for key, section in sorted(sections.items()):
                    currentSection = []
                    currentType.append((key, currentSection))
                    for ss in sorted(section.subsectionMethods()):
                        currentSection.append({
                            "display": ss._displayName or ss.__name__,
                            "key": "suppression.%s.%s.%s" % (type, section.name, ss._name)
                        })
        return subsections

class PartnerExportBase(object):

    SUPPORTED_TYPE = None

    #@Route('/admin/partners/<key>/export/run/', methods=['POST'])
    def export(self, key, dateRange=None, activeOnly=True):

        partner = ndb.Key(urlsafe=key).get()
        bucket = self.getBucket()
        
        queueName = 'default'
        qry = self.getExportQuery(partner.key, dateRange=dateRange, activeOnly=activeOnly)

        delimiter = ','
        gcsName = self.createGcsName('partner')

        headers = self.getCsvHeader()

        from web.models import PartnerExportLog
        
        bucket = self.getBucket()
        gcsPath = self.getPath(bucket, gcsName)

        shard=config.CONFIG['EMAIL']['shard']

        log = PartnerExportLog(
            exportType=self.SUPPORTED_TYPE,
            fileType='csv',
            queryStr=repr(qry),
            gcsName=gcsName,
            gcsPath=gcsPath,
            segments=[],
            headers=headers,
            bucket=bucket,
            partnerKey=partner.key,
            dateRange=dateRange,
            shard=shard,
        )
        log.put()

        taskqueue.add(
            url='/background/partners/export/',
            params={
                'delimiter' : delimiter,
                'log' : pickle.dumps(log),
                'cursor' : None,
                'chunkSize' : 100,
                'queueName' : queueName,
                'bucket' : bucket,
                'segments' : pickle.dumps([]),
                'partnerKey' : pickle.dumps(partner.key),
                'query' : pickle.dumps(qry),
            },
            queue_name=queueName,
        )
        
        return log.key.urlsafe()

    #@Route('/admin/partners/export-status/<logKey>/')
    @classmethod
    def exportStatus(cls, logKey):
        log = ndb.Key(urlsafe=logKey).get()

        result = {
                'finished' : log.isDone,
                'url' : '/admin/partners/download/%s/' % logKey,
                'created' : rtime.formatTime(log.created),
            }

        result['display'] = '<p>Created at: %s  <a href="%s">Click here to download</a></p>'\
             % (result['created'], result['url'])

        return flask.jsonify(result)

    def getBucket(self):
        return config.CONFIG['WEB']['EXPORT_BUCKET']

    def getExportQuery(self, partnerKey, dateRange=None, activeOnly=True):
        raise NotImplemented("haha")

    def getPath(self, bucket, targetFilename):
        return "/%s/partner/%s" % (bucket, targetFilename)

    def getCsvHeader(self):
        raise NotImplemented("hehe")

    @classmethod
    def combineCsvs(cls, delimiter, headers, targetPath, sourcePaths):
        with cloudstorage.open(
                targetPath, 'w', 
                content_type='text/csv',
            ) as outfile:
            print >> outfile, str(delimiter.join(headers))
            for sourceFilepath in sourcePaths:
                with cloudstorage.open(sourceFilepath, 'r') as infile:
                    for line in infile:
                        outfile.write(line)
        return sourceFilepath

    def createGcsName(self, prefix):
        if not prefix:
            prefix = 'partners'
        return '%s-%s.csv' % ( prefix, str(uuid.uuid4()) )

    #@Route('/background/partners/export/', methods=['POST'])
    def batchExportPartners(self):
        delimiter = validate.get('delimiter')
        log = validate.get('log', validate.Unpickle())
        cursor = validate.get('cursor', validate.Unpickle())
        chunkSize = validate.get('chunkSize', validate.ParseInt())
        segments = validate.get('segments', validate.Unpickle())
        bucket = validate.get('bucket')
        queueName = validate.get('queueName')
        partnerKey = validate.get('partnerKey', validate.Unpickle())
        qry = validate.get('query', validate.Unpickle())

        partners, cursor, more = qry\
            .fetch_page (
                chunkSize,
                start_cursor=cursor,
            )

        simplePartners = self.getSimpledPartners(partners)

        simplePartners = self.extraFields(simplePartners, log)

        simplePartners = self.filterPartners(simplePartners)

        gcsName = self.createGcsName('segment-partners')
        gcsPath = self.getPath(bucket, gcsName)

        self.writeRows(simplePartners, gcsPath)

        segments.append(gcsPath)
        log.segments.append(gcsPath)

        if more:
            taskqueue.add(
                url='/background/partners/export/',
                params={
                    'delimiter' : delimiter,
                    'log' : pickle.dumps(log),
                    #'qry' : pickle.dumps(qry),
                    'cursor' : pickle.dumps(cursor),
                    'chunkSize' : chunkSize,
                    'queueName' : queueName,
                    'bucket' : bucket,
                    'segments' : pickle.dumps(segments),
                    'partnerKey' : pickle.dumps(partnerKey),
                    'query' : pickle.dumps(qry),
                },
                queue_name=queueName,
            )
        else:
            taskqueue.add(
                url='/background/partners/export-combine/',
                params={
                    'delimiter' : delimiter,
                    'log' : pickle.dumps(log),
                    'segments' : pickle.dumps(segments),
                },
                queue_name=queueName,
            )

        log.put()

        return "OK"

    def extraFields(self, simplePartners, log):
        return simplePartners

    def filterPartners(self, simplePartners):
        return simplePartners
        
    def getSimpledPartners(self, partners):
        futures = [self.simplePartner(partner) for partner in partners]
        for future in futures:
            yield future.get_result()

    @ndb.tasklet
    def simplePartner(self, partner):
        raise NotImplemented

    def writeRows(self, rows, targetPath):
        with cloudstorage.open(targetPath, 'w', 'text/csv') as outfile:
            for row in rows:
                if row is not None:
                    print >> outfile, self.cleanRow(row)

    def cleanRow(self, row):
        cleanRow = []
        for col in row:
            if isinstance(col, unicode):
                col = '"%s"' % col.replace('"', '')
            elif isinstance(col, datetime.datetime):
                col = rtime.formatTime(col)
            elif col is None:
                col = ""
            else:
                col = str(col)
            cleanRow.append(col)
        joinedRow = ",".join(cleanRow)
        return joinedRow.encode('utf-8')

    @classmethod
    def _generateRows(self, log):
        gcsPath = log.gcsPath
        with cloudstorage.open(gcsPath, 'r') as infile:
            for line in infile:
                yield line

    #@Route('/background/partners/export-combine/', methods=['POST'])
    @classmethod
    def combineExports(cls):
        delimiter = validate.get('delimiter')
        log = validate.get('log', validate.Unpickle())
        segments = validate.get('segments', validate.Unpickle())

        cls.combineCsvs(
            delimiter=delimiter, 
            headers=log.headers, 
            targetPath=log.gcsPath,
            sourcePaths=segments,
        )

        log.isDone = True
        log.put()

        return "OK"

    #@Route('/admin/partners/download/<logKey>/')
    @classmethod
    def reportDownload(cls, logKey):
        log = ndb.Key(urlsafe=logKey).get()
        rows = cls._generateRows(log)
        response = flask.Response(rows, mimetype='text/csv')
        response.headers['Content-Disposition'] = """attachment; filename="%s";""" % (log.gcsName)
        return response

class PartnerBasicExport(PartnerExportBase):
    SUPPORTED_TYPE = 'partner-basic'

    def getExportQuery(self, partnerKey, dateRange=None, activeOnly=True):

        qry = Partner.query()\
            .filter(Partner.ancestorKeys == partnerKey)
        if activeOnly:
            qry = qry.filter(Partner.status == 'active')
        if dateRange:
            qry = qry.filter(Partner.created >= dateRange['start'])\
                .filter(Partner.created <= dateRange['end'])
        qry.order(Partner.status, -Partner.created, Partner.key)

        return qry

    def getCsvHeader(self):
        return [
            'partner_id', 
            'id', 
            'preferredDomain', 
            'api_key', 
            'api_secret',
        ]

    @ndb.tasklet
    def simplePartner(self, partner):
        parts = []
        parentId = ''
        if partner.parentKey is not None:
            pPartner = yield partner.parentKey.get_async()
            parentId = pPartner.pid

        if partner.ancestorKeys:
            ancestors = yield ndb.get_multi_async(partner.ancestorKeys)
            partner.setAncestors(ancestors)

        parts.append(parentId)
        parts.append(partner.pid)
        parts.append(partner.getPreferredDomain())
        parts.append(partner.apiKey)
        parts.append(partner.apiSecret)
        raise ndb.Return(parts)

class PartnerBasicAnalyticExport(PartnerExportBase):
    SUPPORTED_TYPE = 'partner-billing'

    def getExportQuery(self, partnerKey, dateRange=None, activeOnly=True):
        qry = Partner.query()\
            .filter(Partner.ancestorKeys == partnerKey)
        if activeOnly:
            qry = qry.filter(Partner.status == 'active')
        if dateRange:
            qry = qry.filter(Partner.created >= dateRange['start'])\
                .filter(Partner.created <= dateRange['end'])
        qry.order(Partner.status, -Partner.created, Partner.key)
        return qry

    def getCsvHeader(self):
        return [
            'partner_id', 
            'id', 
            'preferredDomain',
            'hasSubpartner',
            'sent',
            'delivered',
            'reportViews',
        ]

    def extraFields(self, simplePartners, log):

        lookup = {}
        tags = []
        partners = []

        for simplePartner in simplePartners:
            tag = simplePartner.pop()
            tags.append(tag)
            partners.append(simplePartner)
            lookup[tag] = simplePartner
            simplePartner.append(0) #sent
            simplePartner.append(0) #delived
            simplePartner.append(0) #reportViews

        options = {
            'tags' : tags,
            'dateRange' : copy.deepcopy(log.dateRange),
            'shard' : log.shard,
        }

        #print "----- options: %s" % options

        pipelines = PartnerSummaryAggsPipeline(**options).getPipelines()
        aggs = PartnerSummaryAggregate.query(pipelines)
        if aggs and aggs.result:
            for result in aggs.result:
                tag = result.get('tag')
                simplePartner = lookup.get(tag)
                if simplePartner:
                    simplePartner[-1] = result.get('reportViews', 0)
                    simplePartner[-2] = result.get('delivered', 0)
                    simplePartner[-3] = result.get('sent', 0)
 
        return partners

    def filterPartners(self, simplePartners):
        return [simplePartner for simplePartner in simplePartners if simplePartner[-1] != 0]

    @ndb.tasklet
    def simplePartner(self, partner):
        parts = []
        parentId = ''
        if partner.parentKey is not None:
            pPartner = yield partner.parentKey.get_async()
            parentId = pPartner.pid

        parts.append(parentId)
        parts.append(partner.pid)
        parts.append(partner.getPreferredDomain())

        tempPartner = yield Partner.query()\
            .filter(Partner.parentKey == partner.key)\
            .get_async()

        hasSubpartner = 'false'
        if tempPartner:
            hasSubpartner = 'true'

        parts.append(hasSubpartner)

        parts.append('partner:%s' % partner.key.urlsafe())

        raise ndb.Return(parts)


class PartnerExport(BaseView):

    @Route('/admin/partners/<key>/export/run/', methods=['POST'])
    def export(self, key):
        requireRole('admin')
        data = getJsonData()
        exportType = data.get("type") or "partner-basic"
        logKey = self.getExportObject(exportType).export(key, self.getDateRange())
        return flask.jsonify({
                "url" : "/admin/partners/export-status/%s/" % logKey
            })

    @Route('/admin/partners/export-status/<logKey>/')
    def exportStatus(self, logKey):
        requireRole('admin')
        return PartnerExportBase.exportStatus(logKey)

    @Route('/background/partners/export/', methods=['POST'])
    def batchExportPartners(self):
        log = validate.get('log', validate.Unpickle())
        exportType = log.exportType
        return self.getExportObject(exportType).batchExportPartners()

    @Route('/background/partners/export-combine/', methods=['POST'])
    def combineExports(self):
        return PartnerExportBase.combineExports()

    @Route('/admin/partners/download/<logKey>/')
    def reportDownload(self, logKey):
        requireRole('admin')
        return PartnerExportBase.reportDownload(logKey)

    def getExportObject(self, exportType):
        if exportType is None or exportType == PartnerBasicExport.SUPPORTED_TYPE:
            return PartnerBasicExport()

        elif exportType == PartnerBasicAnalyticExport.SUPPORTED_TYPE:
            return PartnerBasicAnalyticExport()
        else: 
            return None

    def getDateRange(self):
        data = getJsonData()
        dateRange = util.parseDateRange( data.get('dateRange') )

        exportType = validate.get("type")

        if dateRange is None:
            if exportType == 'partner-billing':
                dateRange = util.parseDateRange('lastquarter')
        return dateRange

def abort(message):
    resp = flask.jsonify({
                "error" : message
            })
    resp.status_code = 400

    logging.error('error: %s' % message)
    flask.abort(resp)

def getJsonData():
    data = None
    try:
        data = flask.request.get_json()
    except BadRequest as e:
        data = None
    if data is None or not isinstance(data, dict):
        abort("invalid json data")
    return data

class PartnerBulk(BaseView):

    actionUrls = {
        'load' : '/background/load-partners/',
        'remove' : '/background/remove-partners/',
    }

    # @Route('/admin/preparepdevfile', methods=['GET', 'POST'])
    # def prepareDevFile(self):
    #     with open('/Users/binghan/sandbox/ar/rentenna3/cities3-manhattan-ny.json', 'r') as f:
    #         content = f.read()
    #         with gcs.open('/rentenna-data/cities3/manhattan-ny.json', 'w') as gcsFile:
    #             gcsFile.write(content)

    #     with open('/Users/binghan/sandbox/ar/rentenna3/cities3-troy-rensselaer-county-ny.json', 'r') as f:
    #         content = f.read()
    #         with gcs.open('/rentenna-data/cities3/troy-rensselaer-county-ny.json', 'w') as gcsFile:
    #             gcsFile.write(content)

    #     with open('/Users/binghan/sandbox/ar/rentenna3/citiesonly3-manhattan-ny.json', 'r') as f:
    #         content = f.read()
    #         with gcs.open('/rentenna-data/citiesonly3/manhattan-ny.json', 'w') as gcsFile:
    #             gcsFile.write(content)
    #     with open('/Users/binghan/sandbox/ar/rentenna3/citiesonly3-troy-rensselaer-county-ny.json', 'r') as f:
    #         content = f.read()
    #         with gcs.open('/rentenna-data/citiesonly3/troy-rensselaer-county-ny.json', 'w') as gcsFile:
    #             gcsFile.write(content)
 
    #     with open('/Users/binghan/sandbox/ar/rentenna3/zips3-12180.json', 'r') as f:
    #         content = f.read()
    #         with gcs.open('/rentenna-data/zips3/12180.json', 'w') as gcsFile:
    #             gcsFile.write(content)

    #     with open('/Users/binghan/sandbox/ar/rentenna3/zips3-10004.json', 'r') as f:
    #         content = f.read()
    #         with gcs.open('/rentenna-data/zips3/10004.json', 'w') as gcsFile:
    #             gcsFile.write(content)

    #     with open('/Users/binghan/sandbox/ar/rentenna3/nh3-soho-manhattan-ny.json', 'r') as f:
    #         content = f.read()
    #         with gcs.open('/rentenna-data/nh3/soho-manhattan-ny.json', 'w') as gcsFile:
    #             gcsFile.write(content)
 
    #     return "OK"
    
    @Route('/admin/partnerbulk/<action>/<key>/', methods=['POST'])
    def process(self, action, key):
        requireRole('admin')

        self.checkAction(action)

        data = flask.request.get_json()
        delimiter = '|'
        gcsName = data.get('filePath')
        isHigherLevel, isLowerLevel = self.getLevel(gcsName)

        partner = self.verifyPartner(key)
        bulkLog = self.createBulkLog(action, partner, gcsName)
        #with util.openFromCloudstorage(gcsName) as gcsFile:
        with gcs.open(gcsName, 'r') as gcsFile:
            files = self.iterFiles(gcsFile)
            for csvName, file in files:

                headerStr = file.readline()
                headers = [s.strip() for s in headerStr.split(delimiter)]
                csvLog = bulkLog.createCsvLog(csvName, headers)
                taskqueue.add(
                    url=self.actionUrls[action],
                    params={
                        'key' : key,
                        'headers' : pickle.dumps(headers),
                        'csvName' : csvName,
                        'delimiter' : delimiter,
                        'gcsName' : gcsName,
                        'logKey' : csvLog.key.urlsafe(),
                        'isLowerLevel' : isLowerLevel,
                        'isHigherLevel' : isHigherLevel,
                        'skiplines' : 1,
                        'size' : 100,
                    },
                    queue_name='default',
                )
        bulkLog.put()
        return flask.jsonify({
                "url" : "/admin/partnerbulk/status/%s/" % bulkLog.key.urlsafe()
            })

    @Route('/background/load-partners/', methods=['GET', 'POST'])
    def loadPartner(self):
        return self._processPartners('load')

    @Route('/background/remove-partners/', methods=['GET', 'POST'])
    def removePartner(self):
        return self._processPartners('remove')

    @Route('/admin/partnerbulk/status/<logKey>/', methods=['GET'])
    def bulkStatus(self, logKey):
        bulkLog = ndb.Key(urlsafe=logKey).get()
        return flask.jsonify(bulkLog.getLog())

    def _processPartners(self, action):
        params = self.InputParams()

        csvLog = params.fileLog
        partner = ndb.Key(urlsafe=params.key).get()
        with gcs.open(params.gcsName, 'r') as gcsFile:
            with self.openFile(gcsFile, params.csvName) as file:
                self.skiplines(file, params.skiplines)

                subpartners, lineCount, more = self.processLines(action, partner, file, params)
                csvLog.info['lineCount'] += lineCount
                if subpartners:
                    self.actionOnPartners(action, subpartners)
                    csvLog.info['count'] += len(subpartners)

                if more:
                    csvLog.put()
                    taskqueue.add(
                        url=self.actionUrls[action],
                        params=params.nextTaskParams(),
                        queue_name='default',
                    )
                else:
                    csvLog.info['status'] = 'finished'
                    csvLog.put()
        return "OK"

    def actionOnPartners(self, action, partners):
        if action == 'load':
            return ndb.put_multi(partners)
        if action == 'remove':
            list(map(self.deactive, partners))
            return ndb.put_multi(partners)

    def abort(self, message):
        resp = flask.jsonify({
                    "error" : message
                })
        resp.status_code = 400
        flask.abort(resp)

    def checkAction(self, action):
        if not action in self.actionUrls.keys():
            self.abort("action: %s is not supported" % action)

    def createBulkLog(self, action, partner, gcsName):
        bulkLog = PartnerBulkLog(
                action=action,
                gcsName=gcsName,
                partnerKey=partner.key,
            )

        user = AdminUser.get()
        bulkLog.user = user.login
        return bulkLog

    def deactive(self, partner):
        partner.status = 'inactive'

    def getLevel(self, gcsName):
        gcsName = gcsName.lower()
        isHigherLevel = '/broker/' in gcsName or '/level1/' in gcsName
        isLowerLevel = '/agent/' in gcsName or '/level2/' in gcsName
        if isHigherLevel is False and isLowerLevel is False:
            self.abort("*The file structure is incorrect, The file path should contain one of /broker/, /level1/, /agent/, /level2/")
        return isHigherLevel, isLowerLevel

    def iterFiles(self, gcsFile):
        zipFile = ZipFile(gcsFile)
        for subfile in zipFile.filelist:
            if subfile.filename.lower().endswith(".csv"):
                with zipFile.open(subfile.filename, 'r') as file:
                    yield subfile.filename, file

    def openFile(self, gcsFile, csvName):
        zipFile = ZipFile(gcsFile)
        for subfile in zipFile.filelist:
            if subfile.filename == csvName:
                return zipFile.open(subfile.filename, 'r')

    def skiplines(self, file, lines):
        count = 0
        while count < lines:
            file.readline()
            count += 1

    # return (partners, lineCount, more)
    def processLines(self, action, parentPartner, file, params):
        partners = []
        count = 0
        size = params.size
        while count < size:
            count += 1
            line = file.readline()
            if not line:
                return partners, count, False
            else:
                partner = self.preparePartner(action, parentPartner, line, params)
                if partner is not None:
                    partners.append(partner)
        return partners, size, True

    def preparePartner(self, action, parentPartner, line, params):
        if action == 'load':
            return self.createPartner(parentPartner, line, params)
        if action == 'remove':
            return self.getRemovablePartner(parentPartner, line, params)

    def getRemovablePartner(self, topPartner, line, params):
        if not line.strip():
            return None
        settings = self.buildSettings(line, params)
        dummy, partner = self.findPartner(topPartner, params, settings)
        if partner is not None and partner.hasSubpartner():
            return None
        return partner

    def createPartner(self, topPartner, line, params):

        if not line.strip():
            return None

        settings = self.buildSettings(line, params)

        parentPartner, partner = self.findPartner(topPartner, params, settings)
        if partner is not None or parentPartner is None:
            return None

        pid = settings.get('id')
        
        partner = Partner.create(parentPartner, pid)

        partner.name = settings.get('name')
        partner.status = settings.get('status') or 'active'

        domains = settings.get('domains')
        if domains:
            partner.domains = map( lambda domain: domain.strip(), domains.split(",") )

        preferredDomain = settings.get("preferredDomain")
        if not preferredDomain and partner.domains:
            preferredDomain = partner.domains[0]
            settings['preferredDomain'] = preferredDomain

        for k,v in settings.items():
            # remove empty k,v, so inheritance rule could apply
            if not v:
                del settings[k]
            else:
                # convert to boolean value
                if k in ['alerts', 'enableBreadcrumbs', 'createSubPartner', 'nav', 'users', 'leadDistribution'] or \
                    k.startswith('state.') or \
                    k.startswith('suppression.') or \
                    k.startswith('lead.restriction.') or \
                    k.startswith('email.suppression.') :

                    settings[k] = v.lower() == 'true'

        self.assignImageSetting(partner, params, settings, 'logo')
        self.assignImageSetting(partner, params, settings, 'contact.photo')

        partner.settings = settings
        return partner

    def buildSettings(self, line, params):
        values = [s.strip() for s in unicode(line, 'latin-1').replace('"','').strip().split(params.delimiter)]
        settings = dict(zip(params.headers, values))
        return settings

    # return parentPartner, currentPartner pair
    def findPartner(self, topPartner, params, settings):
        parentPartner = None
        parentPid = settings.get('partner_id')
        if params.isHigherLevel:
            parentPartner = topPartner

        if params.isLowerLevel:
            parentPartner = topPartner.getSubpartnerById(parentPid)

        pid = settings.get('id')
        if parentPartner is None:
            self.log(params, "missing parent Partner (id=%s) for the id: %s" % (parentPid, pid))
            return None, None
        return parentPartner, parentPartner.getSubpartnerById(pid)

    def verifyPartner(self, key):
        partner = ndb.Key(urlsafe=key).get()
        if partner is None:
            self.abort("can not find the partner")
        return partner

    def log(self, params, msg):
        params.fileLog.info["log"].append(msg)

    def assignImageSetting(self, partner, params, settings, name):
        url = settings.get(name)
        if url and url.strip():
            url = url.strip()
            uid = str(uuid.uuid4())
            gcsImageFile = '/%s/%s' % (
                config.CONFIG['WEB']['UPLOAD_BUCKET'],
                uid,
            )
            success, msg = util.saveImageToCloudstorage(url, gcsImageFile)
            if success:
                settings[name] = "/subdomain-image/%s/" % uid
            else:
                self.log(params, "partner id: %s %s" % (partner.pid, msg))

    class InputParams(object):
        mapping = {
                'csvName' : validate.Required(),
                'delimiter' : validate.Required(),
                'headers' : validate.Unpickle(),
                'gcsName' : validate.Required(),
                'key' : validate.Required(),
                'logKey' : validate.NdbKey(),
                'isLowerLevel' : validate.ParseBool(),
                'isHigherLevel' : validate.ParseBool(),
                'skiplines' : validate.ParseInt(),
                'size' : validate.ParseInt(),
            }

        def __init__(self):
            self.params = dict( (k, validate.get(k, validator)) for k,validator in self.mapping.items() )
            params = self.params
            self.csvName = params['csvName']
            self.delimiter = params['delimiter']
            self.headers = params['headers']
            self.gcsName = params['gcsName']
            self.key = params['key']
            self.logKey = params['logKey']
            self.isLowerLevel = params['isLowerLevel']
            self.isHigherLevel = params['isHigherLevel']
            self.skiplines = params['skiplines']
            self.size = params['size']
            self.fileLog = self.logKey.get()

        def nextTaskParams(self):
            params = copy.deepcopy(self.params)
            params['headers'] = pickle.dumps(params['headers'])
            params['skiplines'] += params['size']
            params['logKey'] = params['logKey'].urlsafe()
            return params

class UserAdmin(BaseView):

    CSV_HEADERS = [
        'contactId',
        'email',
        'emailStatus',
        'firstName',
        'lastName',
        'registered',
        'status',
        'unsubscribed',
        'moveStatus',
        'moveDateString',
        'partnerName',
        'partnerApiKey',
        'landingUrl',
        'utmSource',
        'subscribed',
        'street',
        'city',
        'state',
        'zipcode',
        'firstSeen',
        'phone',
    ]

    @Route('/admin/users/')
    def root(self):
        requireRole('admin')

        qry = self.getQuery()
        pageSize = 50
        
        pager = NdbSimplePager(
                query=qry,
                pageSize=pageSize, 
                url='/admin/users/',
            )

        if pager.redirectUrl():
            return flask.redirect(pager.redirectUrl())

        downloadUrl = None
        downloadCreated = None
        lastLog = self.getFirstExportLog(isAR=True)
        if lastLog:
            downloadUrl = '/admin/users/download/%s/' % lastLog.key.urlsafe()
            downloadCreated = lastLog.created

        return flask.render_template('admin/users.jinja2',
            users=pager.items(),
            page=pager.page(),
            hasNext=pager.hasNext(),
            exportUserUrl='/admin/users/export/',
            downloadUrl=downloadUrl,
            downloadCreated=rtime.formatTime(downloadCreated),
        )
    
    @Route('/admin/users/export/', methods=['GET', 'POST'])
    def adminExport(self):
        requireRole('admin')

        logUrl = self.export(dateRange=None, isAR=True)
        
        return flask.jsonify({
                "url" : "/admin/users/export-status/%s/" % logUrl
            })

    def getPartnerName(self, partner):
        if not partner:
            return ''
        return partner.name or partner.pid
        #return Partner.topBottomName(partner)

    def export(self, dateRange=None, isAR=False, partner=None, targetPartner=None):

        if partner is None:
            isAR = True

        if isAR:
            requireRole('admin')
            
        queueName = 'default'

        #data = flask.request.get_json()
        delimiter = ','
        gcsName = self.createGcsName('user')

        headers = self.getCsvHeader()

        from web.models import UserExportLog
        
        bucket = self.getBucket()
        gcsPath = self.getPath(bucket, gcsName)

        partnerName = "address-report"
        targetPartnerName = "all"
        partnerApiKey = None
        targetPartnerApiKey = None

        if partner:
            partnerName = self.getPartnerName(partner)
            partnerApiKey = partner.apiKey

        if not targetPartner:
            targetPartner = partner

        if targetPartner:
            targetPartnerName = self.getPartnerName(targetPartner)
            targetPartnerApiKey = targetPartner.apiKey

        qry = self.getQuery(dateRange, isAR, targetPartnerApiKey)

        log = UserExportLog(
            exportType='user-default',
            fileType='csv',
            queryStr=repr(qry),
            gcsName=gcsName,
            gcsPath=gcsPath,
            segments=[],
            headers=headers,
            bucket=bucket,
            isAR=isAR,
            partnerName=partnerName,
            partnerApiKey=partnerApiKey,
            targetPartnerName=targetPartnerName,
            targetPartnerApiKey=targetPartnerApiKey,
            dateRange=dateRange,
        )

        log.put()

        taskqueue.add(
            url='/background/users/export/',
            params={
                'delimiter' : delimiter,
                'log' : pickle.dumps(log),
                'cursor' : None,
                'chunkSize' : 500,
                'queueName' : queueName,
                'bucket' : bucket,
                'segments' : pickle.dumps([]),
                'isAR' : isAR,
                'targetPartnerApiKey' : targetPartnerApiKey,
                'dateRange' : pickle.dumps(dateRange),
            },
            queue_name=queueName,
        )
        
        return log.key.urlsafe()

    @Route('/admin/users/export-status/<logKey>/')
    def exportStatus(self, logKey):
        log = ndb.Key(urlsafe=logKey).get()

        result = {
                'finished' : log.isDone,
                'url' : '/admin/users/download/%s/' % logKey,
                'created' : rtime.formatTime(log.created),
            }

        result['display'] = '<p>Created at: %s  <a href="%s">Click here to download</a></p>'\
             % (result['created'], result['url'])

        return flask.jsonify(result)


    @Route('/background/users/export/', methods=['POST'])
    def batchExportUsers(self):
        delimiter = validate.get('delimiter')
        log = validate.get('log', validate.Unpickle())
        cursor = validate.get('cursor', validate.Unpickle())
        chunkSize = validate.get('chunkSize', validate.ParseInt())
        segments = validate.get('segments', validate.Unpickle())
        bucket = validate.get('bucket')
        queueName = validate.get('queueName')
        isAR = validate.get('isAR', validate.ParseBool())
        targetPartnerApiKey = validate.get('targetPartnerApiKey')
        dateRange = validate.get('dateRange', validate.Unpickle())

        qry = self.getQuery(dateRange, isAR, targetPartnerApiKey)

        users, cursor, more = qry\
            .fetch_page (
                chunkSize,
                start_cursor=cursor,
            )

        simpleUsers = self.getSimpledUsers(users)

        gcsName = self.createGcsName('segment-user')
        gcsPath = self.getPath(bucket, gcsName)

        self.writeRows(simpleUsers, gcsPath)

        segments.append(gcsPath)
        log.segments.append(gcsPath)

        if more:
            taskqueue.add(
                url='/background/users/export/',
                params={
                    'delimiter' : delimiter,
                    'log' : pickle.dumps(log),
                    #'qry' : pickle.dumps(qry),
                    'cursor' : pickle.dumps(cursor),
                    'chunkSize' : chunkSize,
                    'queueName' : queueName,
                    'bucket' : bucket,
                    'segments' : pickle.dumps(segments),
                    'isAR' : isAR,
                    'targetPartnerApiKey' : targetPartnerApiKey,
                    'dateRange' : dateRange,
                },
                queue_name=queueName,
            )
        else:
            taskqueue.add(
                url='/background/users/export-combine/',
                params={
                    'delimiter' : delimiter,
                    'log' : pickle.dumps(log),
                    'segments' : pickle.dumps(segments),
                },
                queue_name=queueName,
            )

        log.put()

        return "OK"

    @Route('/background/users/export-combine/', methods=['POST'])
    def combineExports(self):
        delimiter = validate.get('delimiter')
        log = validate.get('log', validate.Unpickle())
        segments = validate.get('segments', validate.Unpickle())

        self.combineCsvs(
            delimiter=delimiter, 
            headers=log.headers, 
            targetPath=log.gcsPath,
            sourcePaths=segments,
        )

        log.isDone = True
        log.put()

        return "OK"

    @Route('/admin/users/download/<logKey>/')
    def reportDownload(self, logKey):
        requireRole('admin')
        return self.handleDownload(logKey)

    def handleDownload(self, logKey):
        log = ndb.Key(urlsafe=logKey).get()
        rows = self._generateRows(log)
        response = flask.Response(rows, mimetype='text/csv')
        response.headers['Content-Disposition'] = """attachment; filename="%s";""" % (log.gcsName)
        return response

    @Route('/admin/users/find/')
    def find(self):
        requireRole('admin')
        email = validate.get('email')
        contactId = validate.get('contactId')

        searchByEmail = True
        if email:
            users = User.query()\
                .filter(User.email == email)\
                .fetch()
        elif contactId:
            searchByEmail = False
            users = User.query()\
                .filter(User.contactId == contactId)\
                .fetch()
        if len(users) == 1:
            return flask.redirect(users[0].getAdminLink())
        elif len(users) == 0:
            flask.abort(404)
        else:
            tableTitle = ''
            if searchByEmail:
                tableTitle = 'Search By Email: %s' % email
            else:
                tableTitle = 'Search By Contact Id: %s' % contactId
            return flask.render_template('admin/userRoot.jinja2',
                users=users,
                tableTitle=tableTitle,
            )

    @Route('/admin/users/get/')
    def get(self):
        requireRole('admin')
        user = validate.get('user', validate.NdbKey()).get()
        return flask.render_template('admin/user.jinja2',
            user=user,
        )

    @Route('/admin/users/login/')
    def log(self):
        requireRole('admin')
        email = validate.get('email')
        user = User.forEmail(email)
        user.login()
        return flask.redirect('/profile/')

    @Route('/admin/users/import-template/')
    def getImportTemplate(self):
        rows = [
            [
                'email',
                'contactId',
                'action',
                'firstName',
                'lastName',
                'moveDateString',
                'moveStatus',
                'locationType',
                'property.query',
                'property.address',
                'property.city',
                'property.state',
                'property.zip',
                'city.city',
                'city.state',
                'city.zip',
                'zip.zip',
                'neighborhood.city',
                'neighborhood.neighborhood',
                'neighborhood.state',
                'neighborhood.zip',
                'user.street',
                'user.city',
                'user.state',
                'user.zipcode',
            ]
            ,
            [
                'johndoe@addressreport.com',
                'an_unique_id_within_the_partner',
                'email-report or register-alerts',
                'John',
                'Doe',
                'May 1, 2016',
                'own-or-rent, looking-to-move, visited-property, application-submitted, papers-signed, broker-owner-manager',
                'property, city, neighborhood, zip',
                '45 wall st, new york, ny  -- use this one or use individual street part: property.address, property.city, property.state, property.zip',
                '45 wall st',
                'new york',
                'ny',
                '10005',
                'manhattan',
                'ny',
                '10005',
                '10005',
                'manhattan',
                'Chelsea',
                'ny',
                '',
                '10 main st',
                'ocean city',
                'md',
                '19970',
            ]
        ]

        cleanedRows = []

        for row in rows:
            cleanedRows.append(self.cleanRow(row, delimiter='|'))
        
        response = flask.Response("\n".join(cleanedRows), mimetype='text/plain')
        response.headers['Content-Disposition'] = """attachment; filename="%s";""" % "user-import-template.txt"
        return response


    def getQuery(self, dateRange=None, isAR=True, targetPartnerApiKey=None):

        qry = User.query()\
            .filter(User.status.IN(['member', 'pro']))\

        if not isAR:
            partner = Partner.forApiKey(targetPartnerApiKey)
            qry = qry.filter(User.partner == partner.key)

        if dateRange:
            start = dateRange.get('start')
            end = dateRange.get('end')
            if start:
                qry = qry.filter(User.registered >= start)
            if end:
                qry = qry.filter(User.registered <= end)

        qry = qry.order(-User.registered, User.key)
        
        return qry

    def combineCsvs(self, delimiter, headers, targetPath, sourcePaths):
        with cloudstorage.open(
                targetPath, 'w', 
                content_type='text/csv',
            ) as outfile:
            print >> outfile, str(delimiter.join(headers))
            for sourceFilepath in sourcePaths:
                with cloudstorage.open(sourceFilepath, 'r') as infile:
                    for line in infile:
                        outfile.write(line)
        return sourceFilepath

    def createGcsName(self, prefix):
        if not prefix:
            prefix = 'user'
        return '%s-%s.csv' % ( prefix, str(uuid.uuid4()) )

    def getFirstExportLog(self, isAR=False):

        qry = UserExportLog.query()\
            .filter(UserExportLog.isDone==True)\

        if isAR:
            qry = qry.filter(UserExportLog.isAR == True)

        log = qry.order(-UserExportLog.created)\
            .get()

        return log

    def queryId(self, qry, page):
        hsh = hashlib.md5()
        hsh.update(repr(qry))
        qryId = '%s:%s' % ( hsh.hexdigest(), page )
        return qryId

    def getBucket(self):
        return config.CONFIG['WEB']['EXPORT_BUCKET']
        
    def getPath(self, bucket, targetFilename):
        return "/%s/user/%s" % (bucket, targetFilename)

    def getCsvHeader(self):
        return UserAdmin.CSV_HEADERS

    def writeRows(self, rows, targetPath):
        with cloudstorage.open(targetPath, 'w', 'text/csv') as outfile:
            for row in rows:
                print >> outfile, self.cleanRow(row)

    def cleanRow(self, row, delimiter=','):
        cleanRow = []
        for col in row:
            if isinstance(col, unicode):
                col = '"%s"' % col.replace('"', '')
            elif isinstance(col, datetime.datetime):
                col = rtime.formatTime(col)
            elif col is None:
                col = ""
            else:
                col = str(col)
            cleanRow.append(col)
        joinedRow = delimiter.join(cleanRow)
        return joinedRow.encode('utf-8')
        
    def getSimpledUsers(self, users, isKey=False, lookup=None):
        futures = [self.simpleUser(user, isKey, lookup) for user in users]
        for future in futures:
            if future:
                yield future.get_result()

    @ndb.tasklet
    def simpleUser(self, user, isKey=False, lookup=None):
        if user and isKey:
            user = yield ndb.Key(urlsafe=user).get_async()
        partnerName = ''
        partnerApiKey = ''
        if not user:
            # unknownUser = ['' for item in range(14)]
            # unknownUser[1] = 'unknownuser@addressreport.com'
            # unknownUser[3] = 'unknownuser'
            # raise ndb.Return(unknownUser)
            raise ndb.Return(None)

        if user.partner:
            partner = yield user.partner.get_async()
            if partner:
                partnerName = yield Partner.topBottomName_async(partner)
                partnerApiKey = partner.apiKey
        
        landingUrl = ''
        utmSource = ''
        if user.tracker:
            #tracker = user.tracker.get()
            tracker = yield user.tracker.get_async()
            if tracker:
                landingUrl = tracker.landingUrl
                utmSource = tracker.utmSource

        unsubscribed = 0
        if user.unsubscribed:
            unsubscribed = 1

        subscribed = 1
        if unsubscribed == 1 or not user.firstSubDate:
            subscribed = 0

        parts = []
        parts.append(user.contactId)
        parts.append(user.email)
        parts.append(user.briteverifyStatus)
        parts.append(user.firstName)
        parts.append(user.lastName)
        parts.append(user.registered)
        parts.append(user.status)
        parts.append(unsubscribed)
        parts.append(user.moveStatus)
        parts.append(user.moveDateString)
        parts.append(partnerName)
        parts.append(partnerApiKey)
        parts.append(landingUrl)
        parts.append(utmSource)
        parts.append(subscribed)
        parts.append(user.street)
        parts.append(user.city)
        parts.append(user.state)
        parts.append(user.zipcode)
        parts.append(user.created)
        parts.append(user.phone)
        if lookup:
            extraInfo = lookup[user.key.urlsafe()]
            parts.append(extraInfo)

        raise ndb.Return(parts)

    def simpleUserJson(self, user, isKey=False):
        if not user:
            return None

        header = self.getCsvHeader()
        userItems = self.getSimpledUsers([user], isKey=isKey)
        users = [dict(zip(header, item)) for item in userItems if item]
        return users[0]

    def _generateRows(self, log):
        gcsPath = log.gcsPath
        with cloudstorage.open(gcsPath, 'r') as infile:
            for line in infile:
                yield line
