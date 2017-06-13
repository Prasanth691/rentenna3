from web.base import AppSubcomponent

class ReportingSubcomponent(AppSubcomponent):

    adminLink = ('/web-admin/reports/', 'Reporting')
    requires = [
        'AdminSubcomponent',
    ]

    def augmentEnvironment(self, appInfo):
        import web.reporting.reportingModels
        import web.reporting.reportingViews
        appInfo.modelModules.append(web.reporting.reportingModels)
        appInfo.viewModules.append(web.reporting.reportingViews)

        # TODO: configure reporting modules here...