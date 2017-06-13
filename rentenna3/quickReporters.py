from rentenna3.base import BaseQuickReporter

class AcsMedianIncomeReporter(BaseQuickReporter):

    supports = 'property'

    def report(self):
        acsMedianIncomeStats = self.stats.get('acsMedianIncomeStats')
        if acsMedianIncomeStats:
            male = acsMedianIncomeStats.get('Total', 'Male', 'Worked Full-Time')
            female = acsMedianIncomeStats.get('Total', 'Female', 'Worked Full-Time')
            total = None

            if male and female:
                total = (male + female) / 2
            elif male:
                total = male
            elif female:
                total = female

            if total:
                self.putStat('totalMedianIncome', total)

class AcsPercentages(BaseQuickReporter):

    supports = [
        'neighborhood',
        'zipcode',
    ]

    def report(self):
        maritalStatus = self.stats.get('acsMaritalStatusBySexAndAge')
        if maritalStatus and maritalStatus.get('Total'):
            self.putStat('maritalStatusPercent', (
                (
                    maritalStatus.get('Total', 'Male', 'Married, Spouse Present')
                    + 
                    maritalStatus.get('Total', 'Female', 'Married, Spouse Present')
                )
                /
                maritalStatus.get('Total')
            ))
        
        children = self.stats.get('acsChildren')
        if children and children.get('Total'):
            self.putStat('childrenPercent', (
                children.get('Total', 'Households with one or more people under 18 years')
                /
                children.get('Total')
            ))

class BreezometerOverrideReporter(BaseQuickReporter):

    supports = 'property'

    def report(self):
        from flask import request
        emailAqi = request.args.get('aqi')
        if emailAqi and self.stats.get('breezometer'):
            self.stats.get('breezometer')['breezometer_aqi'] = int(emailAqi)

class CrimePerCapitaReporter(BaseQuickReporter):

    supports = [
        'neighborhood',
        'zipcode',
    ]

    def report(self):
        nypdCrimes = self.stats.get('nypdCrimes')
        totalPopulation = self.stats.get('totalPopulation')
        if nypdCrimes and totalPopulation:
            self.putStat('crimePerCapita', 
                1000 * nypdCrimes['count'] / totalPopulation
            )

class CrimeRisksHelper(object):
    @classmethod
    def risks(cls, community):
        risks = {
            'murder': community.get('crmcymurd'),
            'rape': community.get('crmcyrape'),
            'robbery': community.get('crmcyrobb'),
            'assault': community.get('crmcyasst'),
            'burglary': community.get('crmcyburg'),
            'gta': community.get('crmcymveh'),
            'total': community.get('crmcytotc'),
        }
        for risk, value in risks.items():
            value = float(value)
            normal = 100
            difference = 100 * (value - normal) / float(normal)
            if value > normal:
                # it just seems wrong...
                difference /= 3
            risks[risk] = {
                'difference': abs(value - normal),
                'percent': min(99, abs(difference)),
                'direction': "higher" if value > normal else "lower"
            }

        return risks

class CrimeRisks(BaseQuickReporter):

    supports = ['city','neighborhood', 'zipcode']

    def report(self):
        if self.stats.get('obiCommunity'):
            community = self.stats.get('obiCommunity')
            risks = CrimeRisksHelper.risks(community)
            self.putStat('crimeRisks', risks)

#This class is copied from CrimeRisks (the one supports region), need remove it 
class CrimeRisksForProperty(BaseQuickReporter):

    supports = 'property'

    def report(self):
        if self.stats.get('obiCommunityForAddrZip'):
            community = self.stats.get('obiCommunityForAddrZip')
            risks = CrimeRisksHelper.risks(community)
            self.putStat('crimeRisks', risks)

class ExpensePercentages(BaseQuickReporter):

    supports = [
        'city',
        'neighborhood',
        'property',
        'zipcode',
    ]

    def report(self):
        if self.stats.get('obiCommunity'):
            community = self.stats.get('obiCommunity')
            expenses = {
                'total': community.get('idxexptotal'),
                'contributions': community.get('expcontrib'),
                'personalInsurance': community.get('expinsur'),
                'apparel': community.get('expappar'),
                'education': community.get('expeduc'),
                'entertainment': community.get('expent'),
                'foodAndBeverage': community.get('expfoodbev'),
                'healthCare': community.get('exphealth'),
                'furnishings': community.get('exphhfurn'),
                'shelter': community.get('exphh'),
                'householdOperations': community.get('exphhops'),
                'miscellaneous': community.get('expmisc'),
                'personalCare': community.get('exppers'),
                'reading': community.get('expread'),
                'tobacco': community.get('exptob'),
                'transportation': community.get('exptransport'),
                'utilities': community.get('exputil'),
                'gifts': community.get('expgift'),
            }
            for expense, value in expenses.items():
                value = float(value)
                if value:
                    expenses[expense] = {
                        'difference': abs(value - 100),
                        'percent': min(100, value / 2),
                        'direction': "higher" if value > 100 else "lower"
                    }
                else:
                    del expenses[expense]
            self.putStat('expenses', expenses)

class LocationReporter(BaseQuickReporter):

    supports = 'property'

    def report(self):
        self.putStat('location', self.target.location)

class Nyc311PerCapitaReporter(BaseQuickReporter):

    supports = [
        'neighborhood',
        'zipcode',
    ]

    def report(self):
        totalPopulation = self.stats.get('totalPopulation')
        if totalPopulation:
            filthComplaints = self.stats.get('filthComplaints')
            if filthComplaints:
                self.putStat(
                    "filthComplaintsPerCapita", 
                    1000 * filthComplaints['count'] / totalPopulation
                )
            
            streetComplaints = self.stats.get('streetComplaints')
            if streetComplaints:
                self.putStat(
                    "streetComplaintsPerCapita", 
                    1000 * streetComplaints['count'] / totalPopulation
                )

            rodentComplaints = self.stats.get('rodentComplaints')
            if rodentComplaints:
                self.putStat(
                    "rodentComplaintsPerCapita", 
                    1000 * rodentComplaints['count'] / totalPopulation
                )

            noiseComplaints = self.stats.get('noiseComplaints')
            if noiseComplaints:
                self.putStat(
                    "noiseComplaintsPerCapita", 
                    1000 * noiseComplaints['count'] / totalPopulation
                )

class NycTreeCountPerSqMileReporter(BaseQuickReporter):

    supports = [
        'neighborhood',
        'zipcode',
    ]

    def report(self):
        areaMiles = self.stats.get('areaMiles')
        streetTrees = self.stats.get('streetTrees')
        if areaMiles and streetTrees:
            self.putStat('treeCountPerSqMile', streetTrees['count'] / areaMiles)

class ObiAvmReporter(BaseQuickReporter):

    supports = 'property'

    def report(self):
        if self.stats.get('obiAvm'):
            obiAvm = self.stats['obiAvm']
            if obiAvm.lowValue and obiAvm.highValue and obiAvm.indicatedValue:
                multiUnit = obiAvm.getBuildingType()[0] in [
                    "Condo", "Co-op",
                ]
                if (not multiUnit) or ( multiUnit and obiAvm.unitValue ):
                    data = {}
                    data['low'] = obiAvm.lowValue
                    data['high'] = obiAvm.highValue
                    data['indicated'] = obiAvm.indicatedValue
                    data['caveat'] = 'accuracy'

                    self.putStat('preferredValueRange', data)
                    return
        
        if self.stats.get('obiCommunity'):
            community = self.stats.get('obiCommunity')
            medianSale = community.get('medsaleprice')
            if medianSale:
                medianSale = float(medianSale)
                data = {}
                data['low'] = 0.6 * medianSale
                data['indicated'] = medianSale
                data['high'] = 1.4 * medianSale
                data['caveat'] = 'area'

                self.putStat('preferredValueRange', data)

class ObiAvmOverrideReporter(BaseQuickReporter):

    supports = 'property'

    def report(self):
        obiAvm = self.stats.get('obiAvm')
        if obiAvm:
            
            if not (self.stats.get('buildingType') or self.stats.get('buildingTypeShort')):
                buildingType = obiAvm.getBuildingType()
                if buildingType:
                    self.putStat('buildingType', buildingType[1])
                    self.putStat('buildingTypeShort', buildingType[0])

            if not self.stats.get('floorCount'):
                self.putStat('floorCount', obiAvm.numberFloors)

            if not self.stats.get('buildingSqft'):
                self.putStat('buildingSqft', obiAvm.sqft)

            if not self.stats.get('buildYear'):
                self.putStat('buildYear', obiAvm.yearBuilt)

            if not self.stats.get('bedCount'):
                self.putStat('bedCount', obiAvm.bedrooms)

class PropertyAcsPercentages(AcsPercentages):

    supports = 'property'

class RentOwnPercentages(BaseQuickReporter):

    supports = [
        'city',
        'neighborhood',
        'property',
        'zipcode',
    ]

    def report(self):
        if self.stats.get('obiCommunity'):
            community = self.stats.get('obiCommunity')
            rent = float(community.get('dwlrent'))
            own = float(community.get('dwlowned'))
            if rent and own:
                self.putStat('rentVsOwn', {
                    'rent': rent / (rent + own),
                    'own': own / (rent + own),
                })