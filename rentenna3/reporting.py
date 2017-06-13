from web.pipelines import *

from rentenna3.models import *
from rentenna3.adminViews import UserAdmin

# Pipeline

class QuizExportPipeline(ChunkedTaskletExporterPipeline):

    header = [
        'Submission ID',
        'Entry Date',
        'Quiz Slug',
        'Partner',
        'Street',
        'City',
        'State',
        'Zip Code',
        'Address Relationship',
        'Interested Section',
        'Buying Budget',
        'Rental Budget',
        'Timeline',
        'Home Interest',
        'Renting Interest',
        'Email Address',
        'Phone Number',
        'First Name',
        'Last Name',
        'Found Financing',
        'Credit Score',
        'Veteran',
        'Looking at Moving',
        'Considering Refinancing',
        'Current Loan Type',
        'Current Loan Term',
        'Phone',
        'Solar Interest',
        'Monthly Bill',
        'Electricity Provider',
        'Roof Shade',
        'Dish Offer',
        'Dish Contact',
        'Moving Interest',
        'IP Address',
        'UTM_SOURCE',
        'UTM_CAMPAIGN',
        'UTM_CONTENT',
        'UTM_MEDIUM',
        'UTM_KEYWORD',
        'UTM_TERM',
        'Landing Page',
        'Referring Url',
        'New User',
        'Finished',
        'Full Address',
    ]

    def getQuery(self, startDate, endDate, **kwargs):
        query = QuizAnswers.query()
        query = query.filter(QuizAnswers.entryDate >= startDate)
        query = query.filter(QuizAnswers.entryDate < endDate)
        return query.order(QuizAnswers.entryDate)

    @ndb.tasklet
    def export(self, quizAnswer):

        streetNumber = quizAnswer.answers.get('streetNumber') or ''
        street = quizAnswer.answers.get('street') or ''
        city = quizAnswer.answers.get('city') or ''
        state = quizAnswer.answers.get('state') or ''
        zipcode = quizAnswer.answers.get('zip') or ''

        fullAddress = None
        geoAddr = quizAnswer.geocodedAddress
        if geoAddr:
            street = geoAddr.get('street', '')
            city = geoAddr.get('city', '')
            state = geoAddr.get('state', '')
            zipcode = geoAddr.get('zipcode', '')
            fullAddress = geoAddr.get('fullAddress', '')
        else:
            street = ' '.join([streetNumber, street]).strip()
            address = quizAnswer.answers.get('address', None)
            if address:
                addressInfo = json.loads(address)
                if addressInfo:
                    fullAddress = addressInfo.get('name', None)

            if not fullAddress:
                if street or city or state or zipcode:
                    stateZip = ' '.join([state, zipcode]).strip()
                    fullAddress = ','.join([street, city, stateZip]).strip().strip(',')

        partnerName = ''
        if quizAnswer.user:
            user = yield quizAnswer.user.get_async()
            if user.partner:
                partner = yield user.partner.get_async()
                if partner:
                    partnerName = yield Partner.topBottomName_async(partner)

        if not partnerName:
            partnerName = quizAnswer.answers.get('partner') or ''

        row = [
            quizAnswer.key.id(),
            quizAnswer.entryDate,
            quizAnswer.slug,
            partnerName,
            street,
            city,
            state,
            zipcode,
            quizAnswer.answers.get('address-relationship'),
            quizAnswer.answers.get('interested-section'),
            quizAnswer.answers.get('buying-budget'),
            quizAnswer.answers.get('rental-budget'),
            quizAnswer.answers.get('timeline'),
            quizAnswer.answers.get('home-interest'),
            quizAnswer.answers.get('renting-interest'),
            quizAnswer.answers.get('email'),
            quizAnswer.answers.get('phoneNumber'),
            quizAnswer.answers.get('firstName'),
            quizAnswer.answers.get('lastName'),
            quizAnswer.answers.get('found-financing'),
            quizAnswer.answers.get('credit-score'),
            quizAnswer.answers.get('veteran'),
            quizAnswer.answers.get('looking-at-moving'),
            quizAnswer.answers.get('considering-refinancing'),
            quizAnswer.answers.get('current-loan-type'),
            quizAnswer.answers.get('current-loan-term'),
            quizAnswer.answers.get('phone'),
            quizAnswer.answers.get('solar-interest'),
            quizAnswer.answers.get('monthly-bill'),
            quizAnswer.answers.get('electricity-provider'),
            quizAnswer.answers.get('roof-shade'),
            quizAnswer.answers.get('dish-offer'),
            quizAnswer.answers.get('dish-contact'),
            quizAnswer.answers.get('moving-interest'),
        ]

        if quizAnswer.tracker:
            tracker = (yield quizAnswer.tracker.get_async())
            row += [
                tracker.ipAddress,
                tracker.utmSource,
                tracker.utmCampaign,
                tracker.utmContent,
                tracker.utmMedium,
                tracker.utmKeyword,
                tracker.utmTerm,
                tracker.landingUrl,
            ]
        else:
            row += ['', '', '', '', '', '', '', '']

        row += [
            quizAnswer.referringUrl or '',
            quizAnswer.isNewUser,
            quizAnswer.finished,
            fullAddress or '',
        ]

        raise ndb.Return(row)

class RegistrationExportPipeline(ChunkedTaskletExporterPipeline):

    header = UserAdmin.CSV_HEADERS

    def getQuery(self, startDate, endDate, **kwargs):
        query = User.query()
        query = query.filter(User.registered >= startDate)
        query = query.filter(User.registered < endDate)
        return query.order(User.registered)

    @ndb.tasklet
    def export(self, user):
        userAdmin = UserAdmin()
        future = userAdmin.simpleUser(user)
        row = yield future
        raise ndb.Return(row)

class SourcePipeline(BasePipeline):

    def run(self, startDate, endDate, outputFile, useCampaign):
        segments = []
        for subStart, subEnd in self.segmentInterval(startDate, endDate):
            segments.append((yield SourceAnalyzeSegmentPipeline(
                startDate=subStart,
                endDate=subEnd,
                useCampaign=useCampaign,
            )))
        yield SourceCombineSegmentsPipeline(outputFile, useCampaign, *segments)

class SourceAnalyzeSegmentPipeline(BasePipeline):

    def run(self, startDate, endDate, useCampaign):
        results = {}

        query = User.query()\
            .filter(User.registered >= startDate)\
            .filter(User.registered < endDate)
    
        for users in rutil.ndbIterateChunked(query):
            futures = [self.crunch(user, useCampaign) for user in users if user.tracker]
            for future in futures:
                self.collectResults(future.get_result(), results)

        preparedOutput = []
        for key, value in results.iteritems():
            value['t'] = self.countTrackers(
                startDate, 
                endDate,
                key, 
                useCampaign,
            )
            preparedOutput.append([
                key,
                value
            ])
        for key, value in preparedOutput:
            value['t'] = value['t'].get_result()
        
        return preparedOutput

    @ndb.tasklet
    def crunch(self, user, useCampaign):
        chargeFutures = ndb.get_multi_async(user.chargeKeys)
        (charges, tracker) = (yield (chargeFutures, user.tracker.get_async()))

        source = tracker.utmSource
        campaign = tracker.utmCampaign
        if useCampaign:
            key = (source, campaign)
        else:
            key = (source,)

        raise ndb.Return({
            'k': key,
            'c': len(charges),
            'r': sum([charge.price/100 for charge in charges]),
        })

    def collectResults(self, item, results):
        key = item['k']

        if key not in results:
            results[key] = {
               'u': 0,
               'c': 0,
               'r': 0.0,
            }
        result = results[key]

        result['u'] += 1
        result['c'] += item['c']
        result['r'] += item['r']

    def countTrackers(self, startDate, endDate, key, useCampaign):
        query = Tracker.query()
        query = query.filter(Tracker.entryDate >= startDate)
        query = query.filter(Tracker.entryDate < endDate)
        query = query.filter(Tracker.utmSource == key[0])
        if useCampaign:
            query = query.filter(Tracker.utmCampaign == key[1])
        return query.count_async()

class SourceCombineSegmentsPipeline(BasePipeline):

    def run(self, outputFile, useCampaign, *segments):
        if useCampaign:
            key = ['UTM_SOURCE', 'UTM_CAMPAIGN']
            sorter = (lambda x: (x[0], x[1]))
        else:
            key = ['UTM_SOURCE']
            sorter = (lambda x: (x[0]))

        header = key + [
            'Total',
            'Registrations',
            'Charges',
            'Revenue',
        ]
        rows = list(self.getRows(segments))
        rows = sorted(rows, key=sorter)
        self.writeRows(([header] + rows), outputFile)

    def getRows(self, segments):
        crunched = {}

        for segment in segments:
            for [key, value] in segment:
                key = tuple(key)
                if key not in crunched:
                    crunched[key] = {
                        't': 0,
                        'u': 0,
                        'c': 0,
                        'r': 0.0,
                    }
                result = crunched[key]
                result['t'] += value['t']
                result['u'] += value['u']
                result['c'] += value['c']
                result['r'] += value['r']
                
        for key, value in crunched.iteritems():
            yield list(key) + [
                value['t'],
                value['u'],
                value['c'],
                value['r'],
            ]

# Reports

class RegistrationExportReport(StartEndReportGenerator):

    reportName = 'RegistrationExport'
    description = "Export registrations for a particular time period."
    pipelineCls = RegistrationExportPipeline

class SourceReport(StartEndReportGenerator):

    reportName = 'source'
    description = "Analyze registrations and payments by source for a particular time period."

    @classmethod
    def getParameters(cls):
        params = StartEndReportGenerator.getParameters()
        params.append({
            'field': "useCampaign",
            'type': "bool",
            'name': "Break down by campaign?",    
        })
        return params

    def __init__(self, reportId, startDate, endDate, useCampaign):
        StartEndReportGenerator.__init__(self, reportId, startDate, endDate)
        self.useCampaign = useCampaign

    def getInfo(self):
        return "%s Report from %s to %s" % (
            "Source" if not self.useCampaign else "Source/Campaign",
            self.startDateTarget.strftime('%Y-%m-%d'),
            self.endDateTarget.strftime('%Y-%m-%d'),
        )

    def getPipeline(self):
        return SourcePipeline(
            startDate=self.startDate,
            endDate=self.endDate,
            outputFile=self.reportId,
            useCampaign=self.useCampaign,
        )

class QuizAnswersReport(StartEndReportGenerator):

    reportName = 'Quiz Data'
    description = "Quiz answers and user"
    pipelineCls = QuizExportPipeline
