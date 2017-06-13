import base64
import datetime
import json
import pickle
import re
import logging
import yaml

class Validator(object):
    """
        Validate and/or manipulate a single value.
    """

    @classmethod
    def applyValidators(cls, value, validators):
        for validator in validators:
            value = validator.validate(value)
        return value

    def transform(self, value):
        """
            Default behavior:
                validate `value` using `self.verify`,
                return `value` unmodified.

            Override `transform` to change the return value.
            This method will never receive None values.
        """
        self.verify(value)
        return value

    def validate(self, value):
        """
            Validate `value`, possibly modifying the result via `transform`

            Always accepts None values -- if you want to handle None values, you must override this method.
        """
        if value is None: return None
        else: return self.transform(value)

    def verify(self, value):
        """
            Subclasses can implement this method to determine whether or not input is valid. They should raise
            a ValueError in the event the value is bad.

            This method will not receive nulls.
        """
        pass

class B64Decode(Validator):

    def transform(self, value):
        return base64.b64decode(value)

class DefaultValue(Validator):

    def __init__(self, default):
        self.default = default

    def validate(self, value):
        if value is None: return self.default
        else: return value

class Deepochify(Validator):

    def transform(self, value):
        if value == "": 
            return None

        try: 
            value = int(value)
        except: 
            raise ValueError('must be an integer.')
        
        from web import rtime
        return rtime.deepochify(value)

class Email(Validator):
    """Verify that the value is an email."""

    def verify(self, value):
        if not re.match(r'[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,10}$', value.upper()):
            raise ValueError("Must be an email")

class InListValidator(Validator):

    def __init__(self, *values):
        self.values = values

    def verify(self, value):
        if value not in self.values:
            raise ValueError('not one of %s' % ",".join(self.values))

class Length(Validator):
    """Verify that the value is within a range of lengths."""

    def __init__(self, min=None, max=None):
        self.min = min
        self.max = max

    def verify(self, value):
        if self.min is not None:
            if len(value) < self.min:
                raise ValueError("Must be >= %s" % self.min)
        if self.max is not None:
            if len(value) > self.max:
                raise ValueError("Must be <= %s" % self.max)

class NdbCursor(Validator):

    def transform(self, value):
        from google.appengine.ext import ndb
        return ndb.Cursor(urlsafe=value)

class NdbKey(Validator):

    def transform(self, value):
        if value == '': return None
        from google.appengine.ext import ndb
        return ndb.Key(urlsafe=value)

class ParseBool(Validator):
    """
        Parse the value, using parser.parseInt
    """
    def __init__(self, nullable=False):
        self.nullable = nullable


    def validate(self, value):
        if self.nullable:
            if value in ("true", "True"):
                return True
            elif value in ('', "None", None):
                return None
            else:
                return False
        else:
            return value not in ("false", "False", "0", None)

class ParseDate(Validator):

    def __init__(self, format="%Y-%m-%dT%H:%M", convertFromEst=True):
        self.format = format
        self.convertFromEst = convertFromEst

    def transform(self, value):
        if not value: 
            return None
        else:
            try:
                date = datetime.datetime.strptime(value, self.format)
                if self.convertFromEst:
                    from web import rtime
                    date = rtime.toLocal(date).replace(tzinfo=None)
                return date
            except:
                raise ValueError("Must be date in %s" % self.format)

class ParseDateField(ParseDate):

    def __init__(self, convertFromEst=True):
        ParseDate.__init__(self, "%Y-%m-%d", convertFromEst)

class ParseDatetimeField(ParseDate):

    def __init__(self, convertFromEst=True):
        ParseDate.__init__(self, "%Y-%m-%dT%H:%M", convertFromEst)

class ParseFloat(Validator):
    """
        Parse the value, using parser.parseFloat
    """

    def transform(self, value):
        if value == "": return None
        try: return float(value)
        except: raise ValueError('must be a float.')

class ParseInt(Validator):
    """
        Parse the value, using parser.parseInt
    """

    def transform(self, value):
        if value == '' or value == 'None': return None
        try: return int(value)
        except: raise ValueError('must be an integer')

class ParseJson(Validator):

    def transform(self, value):
        if value == "": return None
        try: return json.loads(value)
        except: raise ValueError('must be a json')

class ParseYaml(Validator):

    def transform(self, value):
        if value == "": return None
        try: return yaml.safe_load(value)
        except: raise ValueError('must be a yaml')

class Phone(Validator):

    def transform(self, value):
        value = re.sub(r'[^0-9]', '', value)
        if len(value) != 10:
            raise ValueError
        else:
            return value

class Required(Validator):
    """
        Fails if input is None.
    """

    def validate(self, value):
        if value in [None, '']: 
            raise ValueError("required")
        else: 
            return value

class StringValidator(Validator):
    """
        Fails if input is not a string.
        Can optionall preform certain transformations
    """

    def __init__(self, emptyToNone=True, strip=True, force=False):
        self.emptyToNone = emptyToNone
        self.strip = strip
        self.force = force

    def transform(self, value):
        if not isinstance(value, basestring):
            if self.force: value = str(value)
            else: raise ValueError("must be a string")

        if self.strip:
            value = value.strip()

        if self.emptyToNone and value == '':
            value = None

        return value

class Unpickle(Validator):

    def __init__(self, b64=False):
        self.b64 = b64

    def transform(self, value):
        if value == "": 
            return None
        if self.b64:
            value = base64.b64decode(value)
        return pickle.loads(value)

def get(key, *validators):
    """
        Get a validated result from the flask request.
    """
    import flask
    value = flask.request.values.get(key)
    if value == 'None':
        value = None 
    try:
        return Validator.applyValidators(value, validators)
    except:
        logging.error("400: %s: '%s'" % (key, value))
        flask.abort(400)

def getMulti(key, *validators):
    import flask
    values = flask.request.values.getlist(key)
    try:
        return [
            Validator.applyValidators(value, validators)
            for value
            in values
        ]
    except:
        logging.error("400: %s: '%s'" % (key, value))
        flask.abort(400)

def decorateGet(handler):
    # return a get method whose errors are handled by the passed handler
    # handler should return an exception
    def decoratedGet(key, *validators):
        import flask
        value = flask.request.values.get(key)
        try:
            return Validator.applyValidators(value, validators)
        except Exception as error:
            logging.error("400: %s: '%s'" % (key, value))
            raise handler(key, value, error)

    return decoratedGet