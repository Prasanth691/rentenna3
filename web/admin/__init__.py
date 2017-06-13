from web.base import AppSubcomponent

class AdminSubcomponent(AppSubcomponent):

    """
        resource-src requirements:
        - web-admin
        roles:
        - manage-users
    """

    def augmentEnvironment(self, appInfo):
        import web.admin.adminViews
        appInfo.viewModules.append(web.admin.adminViews)
        appInfo.templateDirs.append('lib/web-admin/templates')

def requireRole(*roles):
    import flask
    import urllib
    from web.base import RedirectException
    from web.adminUser.models import AdminUser
    user = AdminUser.get()
    if user is None:
        raise RedirectException('/web-admin/login/?%s' % urllib.urlencode({
            'back': flask.request.url,    
        }))
    for role in roles:
        if not user.hasRole(role):
            return flask.Response(
                "You don't have the role: %s" % role,
                status=401,
            )
    return user