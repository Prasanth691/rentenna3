from web.base import AppSubcomponent
from web.base import BaseView, Route
from web.blog.blogModels import *

class BlogSubcomponent(AppSubcomponent):

    adminLink = ('/web-admin/blog/', 'Blog')
    requires = [
        'AdminSubcomponent',
    ]

    def augmentEnvironment(self, appInfo):
        import web.blog.blogModels
        import web.blog.blogViews
        appInfo.modelModules.append(web.blog.blogModels)
        appInfo.viewModules.append(web.blog.blogViews)


def generateSitemap(self, postTypes):
    sites = []
    posts = BlogPost.query()\
        .filter(BlogPost.status == 'publish')\
        .filter(BlogPost.postType.IN(postTypes))
    for post in posts:
        url = post.getLink()
        sites.append(url)

    sitemap = flask.Response(flask.render_template('common/siteMapView.jinja2', **{
            'sites': sites,
            'domain' : flask.request.url_root[:-1]
        }))
    response = flask.make_response(sitemap)
    response.headers["Content-Type"] = "application/xml"

    return response
