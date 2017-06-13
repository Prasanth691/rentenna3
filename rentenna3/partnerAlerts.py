from rentenna3.base import PartnerAlertReporter
from rentenna3.email import *
from rentenna3.models import *

class PerformanceSummaryAlertReporter(PartnerAlertReporter):

    schedule = 'Sunday'
    supports = 'partner' #TODO: need a better value once we add more partner email, such as weeklyperformance, userstats etc
    template = PartnerPerformanceSummary

    def report(self):
        partner = self.partner
        
        #TODO: moved real data calculation into partner email class to deal with demo partner in staging and production
        # we may consider to use fake test data instead of real one later, then we could move api calls into this method here.
        if partner.needNotification():
            return {
                "dummyField" : "dummy"
            }