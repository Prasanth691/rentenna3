from web.base import AppSubcomponent

class AdminUserSubcomponent(AppSubcomponent):

    adminLink = ('/web-admin/manage-users/', 'Manage admin users')
    requires = ['AdminSubcomponent']

    def augmentEnvironment(self, appInfo):
        import web.adminUser.adminViews
        import web.adminUser.models
        appInfo.viewModules.append(web.adminUser.adminViews)
        appInfo.modelModules.append(web.adminUser.models)