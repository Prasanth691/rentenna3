import datetime
import json

from jinja2 import Undefined

from web.base import SubView

class JsonPayload(SubView):

    def __init__(self, **payload):
        self.payload = payload

    def render(self):
        response = []
        for key, value in self.payload.iteritems():
            if isinstance(value, Undefined):
                value = None
            response.append("""
                <script type="text/json" name="%s">
                    %s
                </script>
            """ % (key, json.dumps(value, cls=CustomEncoder)))
        return "".join(response)

class WebAdminLinks(SubView):

    def render(self):
        import flask 
        app = flask.current_app
        response = []
        response.append("""
            <li class="dropdown">
                <a href="#" class="dropdown-toggle" data-toggle="dropdown">
                    Admin <b class="caret"></b>
                </a>
                <ul class="dropdown-menu">
        """)
        for subcomponent in app.subcomponents:
            if subcomponent.adminLink:
                response.append("""
                    <li>
                        <a href="%s">
                            %s
                        </a>
                    </li>
                """ % subcomponent.adminLink)

        response.append("""
                </ul>
            </li>
        """)
        return "".join(response)

class CustomEncoder(json.JSONEncoder):

    def default(self, obj):
        from bson import ObjectId
        if isinstance(obj, datetime.datetime):
            return obj.strftime('%Y-%m-%dT%H:%M:%S')
        elif isinstance(obj, ObjectId):
            return str(obj)
        elif hasattr(obj, '__json__'):
            return obj.__json__()
        else:
            return json.JSONEncoder.default(self, obj)