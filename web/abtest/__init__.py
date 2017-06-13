from web.base import AppSubcomponent

class AbTestSubcomponent(AppSubcomponent):

    adminLink = ('/web-admin/abtest/', 'ABTE.ST')
    requires = [
        'AdminSubcomponent'
    ]

    # resource-src requirements:
    # - abtest
    # - codemirror

    def augmentEnvironment(self, appInfo):
        import web.abtest.adminViews
        import web.abtest.models
        appInfo.viewModules.append(web.abtest.adminViews)
        appInfo.modelModules.append(web.abtest.models)

    def augmentApp(self, app, appInfo):

        @app.after_request
        def setAbtest(response):
            import flask
            from web.abtest import inject
            if isinstance(response, flask.Response) and response.mimetype == 'text/html':
                abtestResponse = inject.abtest()
                if abtestResponse:
                    data = unicode(response.get_data(), 'utf-8')
                    abtestCode = abtestResponse['code']
                    data = data.replace("***ABTEST***", abtestCode)
                    response.set_data(data)
            return response

def get():
    from web.abtest.inject import abtest
    return abtest()
