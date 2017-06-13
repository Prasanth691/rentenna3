import math
import json
import flask

from web.base import SubView
from rentenna3 import util
from rentenna3.models import *

class Pager(SubView):
    """
        pageInfo is {
            'total': ...,
            'page': ...,
            'pages': ...,
            'results': ...,
        }
    """

    def __init__(self, pageInfo):
        self.pageInfo = pageInfo

    def render(self):
        from web.templating import pageLink

        pageInfo = self.pageInfo

        topPage = pageInfo['pages']

        if topPage in (1, 0):
            pages = []
        else:
            pagesToShow = 9 # should be odd
            if topPage > pagesToShow:
                perSide = (pagesToShow - 3) / 2
                start = pageInfo['page'] - perSide
                end = pageInfo['page'] + perSide
                if start <= 1:
                    start = 2
                    end = start + 2 * perSide
                elif end >= topPage:
                    end = topPage - 1
                    start = end - 2 * perSide
            else:
                start = 2
                end = topPage - 1

            pages = [{
                'page': 1,
                'link': pageLink(1),
                'current': pageInfo['page'] == 1,
            }]

            for page in range(start-1, end):
                link = pageLink(page+1)
                pages.append({
                    'page': page + 1,
                    'link': link,
                    'current': page+1 == pageInfo['page']
                })

            link = pageLink(topPage)
            pages.append({
                'page': topPage,
                'link': link,
                'current': topPage == pageInfo['page']
            })
            
        return flask.render_template('base/pager.jinja2',
            pages=pages,
        )

class ProfileImage(SubView):

    def __init__(self, user):
        self.user = user

    def render(self):
        if self.user.image is None:
            return """
                <div class="profile-image empty">
                    <i class="fa fa-camera"></i>
                </div>
            """
        else:
            return """
                <div class="profile-image full" style="background-image: url('%s')">
                </div>
            """ % self.user.image