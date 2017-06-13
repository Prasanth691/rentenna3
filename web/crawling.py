import logging
import re
import StringIO
import urllib
import urllib2

from lxml import etree

from web import validate

def first(lst):
    """
        Safely retrieve the first element of a list, or None if it's not present.
    """
    if lst is None: return None
    elif len(lst) > 0: return lst[0]
    else: return None

class CrawlResponse(object):

    def __init__(self, url, params=None, method='GET', parseHtml=True, namespaces=None, deadline=60, useHttpLib=False):
        if params:
            payload = urllib.urlencode(params)
        else:
            payload = None

        if method == 'GET' and payload:
            url += "?" + payload
            payload = None

        if useHttpLib:
            logging.info("httplib: %s" % url)
            request = urllib2.Request(url)
            request.add_header(
                'User-Agent',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/33.0.1750.152 Safari/537.36'
            )
            opener = urllib2.build_opener()
            self.response = opener.open(request).read()
        else:
            logging.info("urlfetch: %s" % url)
            from google.appengine.api import urlfetch
            response = urlfetch.fetch(
                url,
                payload=payload,
                method=method,
                deadline=deadline,
            )
            self.response = response.content
            self.headers = response.headers

        if parseHtml:
            self.selector = CrawlSelector(html=self.response, namespaces=namespaces)

class CrawlSelector(object):

    def __init__(self, html=None, xml=None, root=None, namespaces=None):
        self.namespaces = namespaces
        if root is not None:
            self.root = root
        elif html is not None:
            parser = etree.HTMLParser()
            self.root = etree.parse(StringIO.StringIO(html), parser)
            self.html = html
        elif xml is not None:
            self.root = etree.fromstring(xml)
            self.xml = xml
        else:
            raise ValueError("Can't read any input")

    def extract(self):
        try:
            return etree.tostring(self.root, method='html', encoding=unicode, with_tail=False)
        except (AttributeError, TypeError):
            if self.root is True:
                return u'1'
            elif self.root is False:
                return u'0'
            else:
                string = self.root
                string = string.replace(u'\xa0', ' ')
                string = re.sub(r'[ \n\r\t]+', " ", string)
                string = string.strip()
                return string

    def extractAll(self, xpath):
        sels = self.select(xpath)
        return [sel.extract() for sel in sels]

    def first(self, xpath, *validators):
        firstMatch = first(self.select(xpath))
        if firstMatch:
            value = firstMatch.extract()
        else:
            value = None
        try:
            return validate.Validator.applyValidators(value, validators)
        except ValueError:
            return None

    def select(self, xpath):
        els = self.root.xpath(xpath, namespaces=self.namespaces)
        return [CrawlSelector(root=el, namespaces=self.namespaces) for el in els]