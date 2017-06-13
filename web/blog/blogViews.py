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
from web.pipelines import ReportGenerator
from web.blog.blogModels import *

class BlodViews(BaseView):

    @Route('/web-admin/blog/')
    def list(self):
        requireRole('admin')
        page = validate.get('page', validate.ParseInt(), validate.DefaultValue(1))
        postType = validate.get('postType')
        query = BlogPost.query()
        if postType:
            query = query.filter(BlogPost.postType == postType)
        query = query.order(-BlogPost.date)
        posts = rutil.ndbPaginate(page, 20, query)

        if postType and postType != 'all':
            baseUrl = '/web-admin/blog/?postType=%s&' % postType
        else:
            baseUrl = '/web-admin/blog/?'

        postTypes = [x['name'] for x in config.CONFIG.get('BLOG', {}).get('POST_TYPES', [])]

        return flask.render_template(
            'web-admin/blogList.jinja2', 
            posts=posts,
            baseUrl=baseUrl,
            postTypes=postTypes,
        )

    @Route('/web-admin/blog/<slug>/')
    def edit(self, slug):
        requireRole('admin')
        if slug == 'new':
            post = {
                'date': datetime.datetime.now(),
                'status': "draft",
                'new': True,
                'slug': None,
            }
        else:
            post = BlogPost.forSlug(slug)
        postTypes = [(x['name'], x['name']) for x in config.CONFIG.get('BLOG', {}).get('POST_TYPES', [])]
        return flask.render_template(
            'web-admin/blogPost.jinja2',
            post=post,
            postTypes=postTypes,
        )

    @Route('/web-admin/blog/<slug>/', methods=['POST'])
    def save(self, slug):
        requireRole('admin')
        if slug == 'new':
            post = BlogPost(slug=validate.get('slug'))
        else:
            post = BlogPost.forSlug(slug)

        post.title = validate.get('title', validate.Required())
        post.slug = validate.get('slug', validate.Required())
        post.content = validate.get('content')
        post.author = validate.get('author')
        post.date = validate.get('date', validate.ParseDate(format='%Y-%m-%dT%H:%M'))
        post.status = validate.get('status', validate.Required())
        post.excerpt = validate.get('excerpt')
        post.seoTitle = validate.get('seoTitle')
        post.seoDescription = validate.get('seoDescription')
        post.postType = validate.get('postType', validate.Required())

        tags = validate.get('tags', validate.StringValidator(), validate.DefaultValue(""))
        post.tags = [str(tag).strip() for tag in tags.split(',')]

        post.put()

        return flask.redirect(post.getEditUrl())