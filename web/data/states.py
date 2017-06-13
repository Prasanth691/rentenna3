import collections
import logging

STATES = collections.OrderedDict([
    ('alabama', {
        'name': "Alabama",
        'code': "AL",
    }),
    ('alaska', {
        'name': "Alaska",
        'code': "AK",
    }),
    ('arizona', {
        'name': "Arizona",
        'code': "AZ",
    }),
    ('arkansas', {
        'name': "Arkansas",
        'code': "AR",
    }),
    ('california', {
        'name': "California",
        'code': "CA",
    }),
    ('colorado', {
        'name': "Colorado",
        'code': "CO",
    }),
    ('connecticut', {
        'name': "Connecticut",
        'code': "CT",
    }),
    ('delaware', {
        'name': "Delaware",
        'code': "DE",
    }),
    ('district-of-columbia', {
        'name': "District of Columbia",
        'code': "DC",
    }),
    ('florida', {
        'name': "Florida",
        'code': "FL",
    }),
    ('georgia', {
        'name': "Georgia",
        'code': "GA",
    }),
    ('hawaii', {
        'name': "Hawaii",
        'code': "HI",
    }),
    ('idaho', {
        'name': "Idaho",
        'code': "ID",
    }),
    ('illinois', {
        'name': "Illinois",
        'code': "IL",
    }),
    ('indiana', {
        'name': "Indiana",
        'code': "IN",
    }),
    ('iowa', {
        'name': "Iowa",
        'code': "IA",
    }),
    ('kansas', {
        'name': "Kansas",
        'code': "KS",
    }),
    ('kentucky', {
        'name': "Kentucky",
        'code': "KY",
    }),
    ('louisiana', {
        'name': "Louisiana",
        'code': "LA",
    }),
    ('maine', {
        'name': "Maine",
        'code': "ME",
    }),
    ('maryland', {
        'name': "Maryland",
        'code': "MD",
    }),
    ('massachusetts', {
        'name': "Massachusetts",
        'code': "MA",
    }),
    ('michigan', {
        'name': "Michigan",
        'code': "MI",
    }),
    ('minnesota', {
        'name': "Minnesota",
        'code': "MN",
    }),
    ('mississippi', {
        'name': "Mississippi",
        'code': "MS",
    }),
    ('missouri', {
        'name': "Missouri",
        'code': "MO",
    }),
    ('montana', {
        'name': "Montana",
        'code': "MT",
    }),
    ('nebraska', {
        'name': "Nebraska",
        'code': "NE",
    }),
    ('nevada', {
        'name': "Nevada",
        'code': "NV",
    }),
    ('new-hampshire', {
        'name': "New Hampshire",
        'code': "NH",
    }),
    ('new-jersey', {
        'name': "New Jersey",
        'code': "NJ",
    }),
    ('new-mexico', {
        'name': "New Mexico",
        'code': "NM",
    }),
    ('new-york', {
        'name': "New York",
        'code': "NY",
    }),
    ('north-carolina', {
        'name': "North Carolina",
        'code': "NC",
    }),
    ('north-dakota', {
        'name': "North Dakota",
        'code': "ND",
    }),
    ('ohio', {
        'name': "Ohio",
        'code': "OH",
    }),
    ('oklahoma', {
        'name': "Oklahoma",
        'code': "OK",
    }),
    ('oregon', {
        'name': "Oregon",
        'code': "OR",
    }),
    ('pennsylvania', {
        'name': "Pennsylvania",
        'code': "PA",
    }),
    ('puerto-rico', {
        'name': "Puerto Rico",
        'code': "PR",
    }),
    ('rhode-island', {
        'name': "Rhode Island",
        'code': "RI",
    }),
    ('south-carolina', {
        'name': "South Carolina",
        'code': "SC",
    }),
    ('south-dakota', {
        'name': "South Dakota",
        'code': "SD",
    }),
    ('tennessee', {
        'name': "Tennessee",
        'code': "TN",
    }),
    ('texas', {
        'name': "Texas",
        'code': "TX",
    }),
    ('utah', {
        'name': "Utah",
        'code': "UT",
    }),
    ('vermont', {
        'name': "Vermont",
        'code': "VT",
    }),
    ('virginia', {
        'name': "Virginia",
        'code': "VA",
    }),
    ('washington', {
        'name': "Washington",
        'code': "WA",
    }),
    ('west-virginia', {
        'name': "West Virginia",
        'code': "WV",
    }),
    ('wisconsin', {
        'name': "Wisconsin",
        'code': "WI",
    }),
    ('wyoming', {
        'name': "Wyoming",
        'code': "WY",
    }),
])

class State(object):

    @classmethod
    def all(cls):
        if '_states' not in cls.__dict__:
            cls._states = []
            for (id, (slug, state)) in enumerate(STATES.items()):
                cls._states.append(cls(
                    slug=slug,
                    abbr=state['code'],
                    name=state['name'],
                    id=id,
                ))
        return cls._states

    @classmethod
    def currentState(cls):
        import flask

        request = flask.request

        if request.values.get('_zip'):
            from web.data.zips import Zip
            zipInfo = Zip.forZip(request.values.get('_zip'))
            if zipInfo:
                request._state = zipInfo.getState()
        
        if not hasattr(request, '_state'):
            request._state = None

            forcedState = request.values.get('_state')
            if forcedState:
                request._state = cls.forSlug(forcedState)
            else:
                if 'X-Appengine-Region' in request.headers:
                    state = request.headers['X-Appengine-Region']
                    request._state = cls.forAbbr(state)

            if request._state is None:
                request._state = cls.forAbbr('NY')

        return request._state

    @classmethod
    def forAbbr(cls, abbr):
        if abbr:
            abbr = abbr.upper()
            states = cls.all()
            for state in states:
                if state.abbr == abbr:
                    return state

    @classmethod
    def forId(cls, id):
        all = cls.all()
        if (id >= 0) and (id < len(all)):
            return all[id]

    @classmethod
    def forName(cls, name):
        states = cls.all()
        for state in states:
            if state.name.upper() == name.upper():
                return state

    @classmethod
    def forSlug(cls, slug):
        states = cls.all()
        for state in states:
            if state.slug == slug:
                return state

    @classmethod
    def getOptions(self):
        states = [(state.slug, state.name) for state in cls.all()]
        return states

    def __init__(self, slug, abbr, name, id):
        self.slug = slug
        self.abbr = abbr
        self.name = name
        self.id = id
