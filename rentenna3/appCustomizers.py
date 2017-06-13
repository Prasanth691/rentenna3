import logging

from web import config

from rentenna3.base import AppCustomizer

class AddressReportCustomizer(AppCustomizer):

    def allowAlerts(self):
        return True

    def allowUsers(self):
        return True

    def allowedStates(self):
        return None

    def allowPromotion(self):
        return True

    def brandingPosition(self):
        return 'right'

    def cobranding(self):
        return True

    def decorateUrl(self, url):
        return url

    def getContactInfo(self):
        return None

    def getTags(self):
        return [
            'customizer:AddressReportCustomizer',
            'partner:address-report',
            'partner_direct:address-report',
        ]

    def headerStyle(self):
        return 'dark'

    def displayHeader(self):
        return True

    def lookupOnlyRoot(self):
        return False

    def partnerSilo(self):
        return None

    def partnerApiKey(self):
        return None

    def partnerLogo(self):
        return None

    def renderFullReports(self):
        return False

    def settings(self):
        return {}

    def skipAlertConfirmation(self):
        return False

    def suppressArLinks(self):
        return False

    def suppressBreadcrumbs(self):
        return False

    def suppressNav(self):
        return False

    def urlBase(self):
        return config.CONFIG['URL']['BASE']

class DefaultPartnerAppCustomizer(AppCustomizer):

    def __init__(self, partner):
        self.partner = partner

    def allowAlerts(self):
        return self.partner.getSetting('alerts')

    def allowUsers(self):
        return self.partner.getSetting('users')

    def allowedStates(self):
        return self.partner.getAllowedStates()

    def allowPromotion(self):
        return False

    def brandingPosition(self):
        return self.partner.getSetting("branding.position")

    def cobranding(self):
        return self.partner.getSetting("branding.cobranding")

    def decorateUrl(self, url):
        return self.partner.decorateUrl(url)

    def getContactInfo(self):
        # at minimum, we need a name and a logo
        settings = self.partner.getSettings()
        firstName = settings.get('contact.firstname') or ''
        lastName = settings.get('contact.lastname') or ''
        photo = settings.get('contact.photo')
        email = settings.get('contact.email')
        phone = settings.get('contact.phone')
        license = settings.get('contact.license')
        website = settings.get('contact.website')
        company = settings.get('contact.company')
        name = "%s %s" % (firstName, lastName)
        name = name.strip()

        if firstName or lastName or photo or email or phone or website or company:
            return {
                'name': name,
                'photo': photo,
                'email': email,
                'phone': phone,
                'license': license,
                'website': website,
                'company': company,
            }

    def getTags(self):
        return [
            'customizer:DefaultPartnerAppCustomizer',
        ] + self.partner.getTags()

    def headerStyle(self):
        return self.partner.getSetting('headerColor')

    def displayHeader(self):
        return True
        #return self.partner.getSetting('headerDisplay')

    def lookupOnlyRoot(self):
        return True

    def partnerApiKey(self):
        return self.partner.apiKey

    def partnerSilo(self):
        return self.partner.key

    def partnerLogo(self):
        return self.partner.getSetting('logo')

    def renderFullReports(self):
        return self.partner.getSetting('renderFullReports')

    def settings(self):
        return self.partner.getSettings()

    def skipAlertConfirmation(self):
        return self.partner.getSetting('skipAlertConfirmation')

    def suppressArLinks(self):
        return True

    def suppressBreadcrumbs(self):
        return not self.partner.getSetting('enableBreadcrumbs')

    def suppressNav(self):
        return not self.partner.getSetting('nav')

    def urlBase(self):
        return self.partner.getPreferredDomain() or config.CONFIG['URL']['BASE']
