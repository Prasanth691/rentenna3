import collections
import logging
                                
SUPPRESSIONS = collections.OrderedDict([
    ('AlertFor311', {
        'name': "Complaints",
        'code': "AlertFor311",
    }),
    ('AlertForValue', {
        'name': "Value Estimate",
        'code': "AlertForValue",
    }),
    ('AlertForNearbySales', {
        'name': "Home Sales",
        'code': "AlertForNearbySales",
    }),
    ('AlertForAirQuality', {
        'name': "Air Quality",
        'code': "AlertForAirQuality",
    }),
    # ('SubscribeForAlerts', {
    #     'name': "Subscription Confirmation",
    #     'code': "SubscribeForAlerts",
    # }),
])

class EmailSuppression(object):

    @classmethod
    def all(cls):
        if '_suppresions' not in cls.__dict__:
            cls._suppresions = []
            for (id, (slug, suppression)) in enumerate(SUPPRESSIONS.items()):
                cls._suppresions.append(cls(
                    slug=slug,
                    abbr=suppression['code'],
                    name=suppression['name'],
                    id=id,
                ))
        return cls._suppresions

    @classmethod
    def forAbbr(cls, abbr):
        if abbr:
            abbr = abbr.upper()
            suppressions = cls.all()
            for suppression in suppressions:
                if suppression.abbr == abbr:
                    return suppression

    @classmethod
    def forName(cls, name):
        suppressions = cls.all()
        for suppression in suppressions:
            if suppression.name.upper() == name.upper():
                return suppression

    def __init__(self, slug, abbr, name, id):
        self.slug = slug
        self.abbr = abbr
        self.name = name
