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
from web import memcache
from web import tracking
from web.backups import BackedupNdbModel

class BlogPost(BackedupNdbModel):

    author = ndb.StringProperty()
    content = ndb.TextProperty()
    date = ndb.DateTimeProperty()
    excerpt = ndb.TextProperty()
    postType = ndb.StringProperty()
    status = ndb.StringProperty() # publish, draft
    slug = ndb.StringProperty()
    seoDescription = ndb.TextProperty()
    seoTitle = ndb.StringProperty()
    tags = ndb.StringProperty(repeated=True)
    title = ndb.StringProperty()

    @classmethod
    def _get_kind(cls):
        return 'WordprezzPost'

    @classmethod
    def forSlug(cls, slug):
        return BlogPost.query().filter(BlogPost.slug == slug).get()

    @classmethod
    def recent(cls, postType, limit=5, bypassCache=False):
        if bypassCache:
            posts = cls.queryRecentPosts(postType, limit)
        else:
            key = 'BlogPost:recent:1:%s:%s' % (postType, limit)
            posts = memcache.get(key)
            if posts is None:
                posts = cls.queryRecentPosts(postType, limit)
                memcache.set(key, posts, 600)
                
        return posts

    @classmethod
    def queryRecentPosts(cls, postType, limit):
        return BlogPost.query()\
            .filter(BlogPost.postType == postType)\
            .filter(BlogPost.status == 'publish')\
            .filter(BlogPost.date <= datetime.datetime.now())\
            .order(-BlogPost.date)\
            .fetch(limit)

    def getEditUrl(self):
        return '/web-admin/blog/%s/' % self.slug

    def getExcerpt(self):
        if self.excerpt:
            return self.excerpt
        else:
            return re.sub(r'<[^<]+?>', '', self.content)[0:300] + "..."

    def getImg(self):
        imgs = re.findall(r'<img[^<]+?>', self.content)
        if imgs:
            img = imgs[0]
            img = re.sub(r'width="[0-9]+"', '', img)
            img = re.sub(r'height="[0-9]+"', '', img)
            img = re.sub(r'style="[^"]+"', '', img)
            return img
        else:
            return ""

    def getLink(self):
        postTypes = config.CONFIG['BLOG']['POST_TYPES']
        for postType in postTypes:
            if postType['name'] == self.postType:
                return postType['url'] % self.slug

    def getNext(self):
        return BlogPost.query()\
            .filter(BlogPost.postType == self.postType)\
            .filter(BlogPost.status == 'publish')\
            .filter(BlogPost.date > self.date)\
            .order(BlogPost.date)\
            .get()

    def getPrevious(self):
        post = BlogPost.query()\
            .filter(BlogPost.postType == self.postType)\
            .filter(BlogPost.status == 'publish')\
            .filter(BlogPost.date < self.date)\
            .order(-BlogPost.date)\
            .get()
        return post
