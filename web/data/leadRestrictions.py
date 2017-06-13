import collections
import logging

RESTRICTIONS = collections.OrderedDict([
    ('real-estate', {
        'name': "Real Estate",
        'code': "real-estate",
    }),
    ('mortgage', {
        'name': "Mortgage",
        'code': "mortgage",
    }),
    ('insurance', {
        'name': "Insurance",
        'code': "insurance",
    }),
    ('home-services', {
        'name': "Home Services",
        'code': "home-services",
    }),
    ('title', {
        'name': "Title",
        'code': "title",
    }),
    ('legal', {
        'name': "Legal",
        'code': "legal",
    }),
])

class LeadRestriction(object):

    @classmethod
    def all(cls):
        if '_restrictions' not in cls.__dict__:
            cls._restrictions = []
            for (id, (slug, restriction)) in enumerate(RESTRICTIONS.items()):
                cls._restrictions.append(cls(
                    slug=slug,
                    abbr=restriction['code'],
                    name=restriction['name'],
                    id=id,
                ))
        return cls._restrictions

    @classmethod
    def forAbbr(cls, abbr):
        if abbr:
            abbr = abbr.upper()
            restrictions = cls.all()
            for restriction in restrictions:
                if restriction.abbr == abbr:
                    return restriction

    @classmethod
    def forName(cls, name):
        restrictions = cls.all()
        for restriction in restrictions:
            if restriction.name.upper() == name.upper():
                return restriction

    def __init__(self, slug, abbr, name, id):
        self.slug = slug
        self.abbr = abbr
        self.name = name
