import flask
import logging
import traceback
import urllib

from web import rutil

from rentenna3 import util
from rentenna3.base import ReportSection, subsection

class AreasForCitySection(ReportSection):

    name = "Neighborhoods"
    priority = 2000
    key = 'areas-for-city'
    template = 'client/areasForCityReportSection.jinja2'
    supports = 'city'

    @subsection('areas')
    def areas(self):
        data = {}

        util.inheritIfTruthy('areas', self.stats, data)

        if data:
            return data

class BuildingReportSection(ReportSection):

    name = "Building"
    priority = 150
    key = 'building'
    template = 'client/buildingReportSection.jinja2'
    supports = 'property'

    @subsection('buildingInfo', 'Building Info')
    def buildingInfoSubsection(self):
        data = {}

        util.inheritIfTruthy('buildingType', self.stats, data)
        util.inheritIfTruthy('buildingTypeShort', self.stats, data)
        util.inheritIfTruthy('bedCount', self.stats, data)
        util.inheritIfTruthy('unitCount', self.stats, data)
        util.inheritIfTruthy('floorCount', self.stats, data)
        util.inheritIfTruthy('buildingSqft', self.stats, data)
        util.inheritIfTruthy('buildYear', self.stats, data)
        util.inheritIfTruthy('buildingCondition', self.stats, data)
        util.inheritIfTruthy('isInsurent', self.stats, data)

        elevators = self.stats.get('elevators')
        if elevators:
            data['numberElevators'] = len(elevators)

        if data:
            return data

    @subsection('elevators')
    def elevatorSubsection(self):
        data = {}

        util.inheritIfTruthy('elevatorWaitTimeUp', self.stats, data)
        util.inheritIfTruthy('elevatorWaitTimeDown', self.stats, data)
        util.inheritIfTruthy('elevatorTravelTimeUp', self.stats, data)
        util.inheritIfTruthy('elevatorTravelTimeDown', self.stats, data)
        util.inheritIfTruthy('elevatorTimeUpByFloor', self.stats, data)
        util.inheritIfTruthy('elevatorTimeDownByFloor', self.stats, data)

        if data:
            return data

    @subsection('complaints')
    def complaintSubsection(self):
        data = {}
        
        if self.stats.get('complaintsExist'):
            complaints = self.stats.get('complaints')
            violations = self.stats.get('violations')

            if complaints:
                data['complaints'] = complaints

            if violations:
                data['violations'] = violations

            data['totalProblems'] = self.stats.get('totalProblems')
            data['totalOpenProblems'] = self.stats.get('totalOpenProblems')
            data['totalViolations'] = self.stats.get('totalViolations')
            data['totalOpenViolations'] = self.stats.get('totalOpenViolations')

        if data:
            return data

# class CrimeReportSectionCity(ReportSection):

#     name = "Crime"
#     priority = 400
#     key = 'crime'
#     template = 'client/cityCrimeReportSection.jinja2'
#     supports = 'city'

#     @subsection('risks')
#     def risks(self):
#         if self.stats.get('crimeRisks'):
#             return self.stats.get('crimeRisks')

class CrimeReportSectionProperty(ReportSection):

    name = "Crime"
    priority = 400
    key = 'crime'
    template = 'client/crimeReportSection.jinja2'
    supports = 'property'

    @subsection('quickStats')
    def quickStatsSubsection(self):
        data = {}
        util.inheritIfPresent('policePrecinctName', self.stats, data)
        util.inheritIfPresent('nypdCrimes', self.stats, data)
        util.inheritIfPresent('policePrecinctGeo', self.stats, data)
        if data:
            return None #TODO: need to remove this once we have latest nypd crime data
            #return data

    @subsection('risks')
    def risks(self):
        if self.stats.get('crimeRisks'):
            return self.stats.get('crimeRisks')

class CrimeReportSectionRegion(ReportSection):

    name = "Crime"
    priority = 400
    key = 'crime'
    template = 'client/cityCrimeReportSection.jinja2'
    supports = [
        'city',
        'neighborhood',
        'zipcode',
    ]

    @subsection('risks')
    def risks(self):
        if self.stats.get('crimeRisks'):
            return self.stats.get('crimeRisks')

class ConstructionSectionProperty(ReportSection):

    name = "Construction"
    priority = 300
    key = 'construction'
    template = 'client/constructionReportSection.jinja2'
    supports = 'property'

    @subsection('construction', 'Construction')
    def constructionSubsection(self):
        data = {}

        util.inheritIfPresent('scaffolds', self.stats, data)
        util.inheritIfPresent('demolitions', self.stats, data)
        util.inheritIfPresent('newBuildings', self.stats, data)
        util.inheritIfPresent('buildingJobs', self.stats, data)
        if data.get('buildingJobs') is not None:
            data['buildingJobsCount'] = len(data.get('buildingJobs', []))

        if data:
            return data

class ConstructionReportSectionRegion(ReportSection):

    name = "Construction"
    priority = 800
    key = 'construction'
    template = 'client/regionConstructionReportSection.jinja2'
    supports = [
        'neighborhood',
        'zipcode',
    ]

    @subsection('quickStats')
    def complaintsSubsection(self):
        data = {}

        util.inheritIfPresent('demolitions', self.stats, data)
        util.inheritIfPresent('newBuildings', self.stats, data)
        util.inheritIfPresent('scaffolds', self.stats, data)

        if data:
            return data

class DemographicsReportSection(ReportSection):

    name = "Demographics"
    key = 'demographics'
    template = 'client/demographicsReportSection.jinja2'
    priority = 500
    supports = [
        'city',
    ]

    @subsection('quickStats')
    def quickstatsSubsection(self):
        data = {}

        maritalStatusPercent = self.stats.get('maritalStatusPercent')
        if maritalStatusPercent is not None:
            data['maritalStatusPercent'] = maritalStatusPercent

        childrenPercent = self.stats.get('childrenPercent')
        if childrenPercent is not None:
            data['childrenPercent'] = childrenPercent
            householdStats = self.computeHouseholdStats()
            if householdStats:
                data['householdStats'] = householdStats

        medianAgeBySex = self.stats.get('acsMedianAgeBySex')
        if medianAgeBySex:
            total = medianAgeBySex.get('Total')
            if total:
                data['medianAge'] = total
                populationStats = self.computePopulationStats()
                if populationStats:
                    data['populationStats'] = populationStats

        workStats = self.computeWorkStats()
        if workStats:
            data['workStats'] = workStats
            if workStats.get('education'):
                education = workStats['education']
                mostCommon = sorted(education, key=lambda x: x[1])[-1]
                data['mostCommonEducation'] = mostCommon[0]

        if data:
            return data

    def computeHouseholdStats(self):
        householdStats = {}

        householdSizeByType = self.stats.get('censusHouseholdSizeByType')
        if householdSizeByType:
            householdStats['householdSizeByType'] = {
                'Family': [["1", 0]] + householdSizeByType.getAll('Total', 'Family'),
                'Nonfamily': householdSizeByType.getAll('Total', 'Nonfamily')
            }

        martialStatus = self.stats.get('acsMaritalStatusBySexAndAge')
        if martialStatus:
            householdStats['maritalStatusByAge'] = {
                'Unmarried': martialStatus.zipSum(
                    ['Total', 'Male', 'Never Married'],
                    ['Total', 'Male', 'Widowed'],
                    ['Total', 'Male', 'Divorced'],
                    ['Total', 'Female', 'Never Married'],
                    ['Total', 'Female', 'Widowed'],
                    ['Total', 'Female', 'Divorced'],
                ),
                'Married': martialStatus.zipSum(
                    ['Total', 'Male', 'Married, Spouse Present', 'Currently Married'],
                    ['Total', 'Male', 'Married, Spouse Absent', 'Seperated'],
                    ['Total', 'Male', 'Married, Spouse Absent', 'Other'],
                    ['Total', 'Female', 'Married, Spouse Present', 'Currently Married'],
                    ['Total', 'Female', 'Married, Spouse Absent', 'Seperated'],
                    ['Total', 'Female', 'Married, Spouse Absent', 'Other'],
                )
            }

            householdStats['maritalStatusBySex'] = {
                'Male': [
                    ('Never Married', martialStatus.get('Total', 'Male', 'Never Married')),
                    ('Currently Married', martialStatus.get('Total', 'Male', 'Married, Spouse Present', 'Currently Married')),
                    ('Seperated', martialStatus.get('Total', 'Male', 'Married, Spouse Absent', 'Seperated')),
                    ('Divorced', martialStatus.get('Total', 'Male', 'Divorced')),
                    ('Widowed', martialStatus.get('Total', 'Male', 'Widowed')),
                    ('Other', martialStatus.get('Total', 'Male', 'Married, Spouse Absent', 'Other')),
                ],
                'Female': [
                    ('Never Married', martialStatus.get('Total', 'Female', 'Never Married')),
                    ('Currently Married', martialStatus.get('Total', 'Female', 'Married, Spouse Present', 'Currently Married')),
                    ('Seperated', martialStatus.get('Total', 'Female', 'Married, Spouse Absent', 'Seperated')),
                    ('Divorced', martialStatus.get('Total', 'Female', 'Divorced')),
                    ('Widowed', martialStatus.get('Total', 'Female', 'Widowed')),
                    ('Other', martialStatus.get('Total', 'Female', 'Married, Spouse Absent', 'Other')),
                ],
            }

        householdIncome = self.stats.get('acsHouseholdIncome')
        if householdIncome:
            householdStats['householdIncome'] = householdIncome.getAll('Total')

        if householdStats:
            return householdStats

    def computePopulationStats(self):
        populationStats = {}

        ageBySex = self.stats.get('censusAgeBySex')
        if ageBySex:
            # much too granular, need to bucket to groups of 5
            mappings = [('0-5', ['0', '1', '2', '3', '4', '5'])]
            for start in range(6, 100, 5):
                mappings.append((
                    '%s-%s' % (start, start + 4), 
                    [str(x) for x in range(start, start+5)]
                ))
            mappings.append(('100+', ['100-104', '105-109', '110+']))
            
            populationStats['ageBySex'] = {
                'Male': ageBySex.rebucket(mappings, 'Total', 'Male'),
                'Female': ageBySex.rebucket(mappings, 'Total', 'Female'),
            }

        raceBySex = self.stats.get('acsRaceBySex')
        if raceBySex:
            populationStats['raceBySex'] = raceBySex

        placeOfBirth = self.stats.get('acsPlaceOfBirth')
        if placeOfBirth:
            populationStats['placeOfBirth'] = [
                ('This State', placeOfBirth.get('Total', 'Native', 'In this State')),
                ('U.S. Northeast', 
                    placeOfBirth.get('Total', 'Native', 'In Different State', 'Northeast')),
                ('U.S. Midwest', 
                    placeOfBirth.get('Total', 'Native', 'In Different State', 'Midwest')),
                ('U.S. South', 
                    placeOfBirth.get('Total', 'Native', 'In Different State', 'South')),
                ('U.S. West', 
                    placeOfBirth.get('Total', 'Native', 'In Different State', 'West')),
                ('Puerto Rico', 
                    placeOfBirth.get('Total', 'Outside of USA', 'Puerto Rico')),
                ('U.S. Island', 
                    placeOfBirth.get('Total', 'Outside of USA', 'U.S. Island')),
                ('Naturalized U.S. Citizen', 
                    placeOfBirth.get('Total', 'Foreign', 'Naturalized U.S. Citizen')),
                ('Not a U.S. Citizen',
                    placeOfBirth.get('Total', 'Foreign', 'Not a U.S. Citizen')),
            ]

        geographicMobility = self.stats.get('acsGeographicMobility')
        if geographicMobility:
            labels = [
                'Same house 1 year ago', 'Moved within same county',
                'Moved from same state', 'Moved from different state',
                'Moved from abroad'
            ]
            stats = [geographicMobility.getAll('Total', label) for label in labels]
            males = []
            females = []
            for label, stat in zip(labels, stats):
                males.append((label, stat[0][1]))
                females.append((label, stat[1][1]))
            populationStats['geographicMobility'] = {
                'Male': males,
                'Female': females,
            }

        return populationStats

    def computeWorkStats(self):
        workStats = {}

        education = self.stats.get('acsEducation')
        if education:
            mappings = [
                ('No Schooling', ['No Schooling']),
                ('Less than High School', [
                    'Nursery School', 'Kindergarten', '1st grade', '2nd grade', '3rd grade', 
                    '4th grade', '5th grade', '6th grade', '7th grade', '8th grade'
                ]),
                ('Some High School', [
                    '9th grade', '10th grade', '11th grade', '12th grade'
                ]),
                ('High School Diploma', ['High School Diploma']),
                ('GED', ['GED']),
                ('Some College', ['Under a Year of College', 'Some College, No Degree']),
                ('Associate\'s Degree', ['Associate\'s Degree']),
                ('Bachelor\'s Degree', ['Bachelor\'s Degree']),
                ('Master\'s Degree', ['Master\'s Degree']),
                ('Professional School Degree', ['Professional School Degree']),
                ('Doctorate Degree', ['Doctorate Degree']),

            ]
            workStats['education'] = education.rebucket(mappings, 'Total')

        timeLeavingForWork = self.stats.get('acsTimeLeavingForWork')
        if timeLeavingForWork:
            workStats['timeLeavingForWork'] = timeLeavingForWork.getAll('Total')

        commuteTimes = self.stats.get('acsCommuteTimes')
        if commuteTimes:
            workStats['commuteTimes'] = commuteTimes.getAll('Total')

        commuteMethods = self.stats.get('acsCommuteMethods')
        if commuteMethods:
            cars = commuteMethods.getAll('Total', 'Car')
            publics = commuteMethods.getAll('Total', 'Public Transportation')
            other = commuteMethods.getAll('Total')
            workStats['commuteMethods'] = cars + publics + other[2:]
            
        return workStats

class DemographicsReportSectionProperty(DemographicsReportSection):

    supports = 'property'

    @subsection('politics')
    def politicsSubsection(self):
        data = {}

        if self.stats.get('votersInBuildingPercent'):
            data['inBuilding'] = self.stats.get('votersInBuildingPercent')

        if self.stats.get('votersPercent'):
            data['nearby'] = self.stats.get('votersPercent')

        if data:
            return data

class DemographicsReportSectionRegion(DemographicsReportSection):

    supports = [
        'neighborhood',
        'zipcode',
    ]

    @subsection('politics')
    def politicsSubsection(self):
        data = {}

        if self.stats.get('votersPercent'):
            data['nearby'] = self.stats.get('votersPercent')

        if data:
            return data

class FinancialReportSection(ReportSection):

    name = "Financial"
    priority = 175
    key = 'financial'
    template = 'client/financialReportSection.jinja2'
    supports = [
        'city',
        'neighborhood',
        'zipcode',
    ]

    @subsection('expenses')
    def expensesSubsection(self):
        if self.stats.get('expenses'):
            return self.stats.get('expenses')

    @subsection('taxes')
    def taxes(self):
        if self.stats.get('obiCommunity'):
            community = self.stats.get('obiCommunity')
            data = {}
            if community.get('avg_prop_tax'):
                data['propertyTax'] = float(community.get('avg_prop_tax'))
            if community.get('salestaxrate'):
                data['salesTax'] = float(community.get('salestaxrate'))
            if data:
                return data

    @subsection('rentVsOwn')
    def rentVsOwn(self):
        if self.stats.get('rentVsOwn'):
            return self.stats.get('rentVsOwn')

    @subsection('incomes')
    def incomes(self):
        data = {}

        if self.stats.get('obiCommunity'):
            community = self.stats.get('obiCommunity')
            if community.get('inccymedd'):
                medianHouseholdIncome = float(community.get('inccymedd'))
                data['medianHouseholdIncome'] = medianHouseholdIncome
                if medianHouseholdIncome:
                    householdIncomeBreakdown = [
                        ['Under $10K', community.get('hincy00_10')],
                        ['$15,000', community.get('hincy10_15')],
                        ['$20,000', community.get('hincy15_20')],
                        ['$25,000', community.get('hincy20_25')],
                        ['$30,000', community.get('hincy25_30')],
                        ['$35,000', community.get('hincy30_35')],
                        ['$40,000', community.get('hincy35_40')],
                        ['$45,000', community.get('hincy40_45')],
                        ['$50,000', community.get('hincy45_50')],
                        ['$60,000', community.get('hincy50_60')],
                        ['$75,000', community.get('hincy60_75')],
                        ['$100,000', community.get('hincy75_100')],
                        ['$125,000', community.get('hincy100_125')],
                        ['$150,000', community.get('hincy125_150')],
                        ['$200,000', community.get('hincy150_200')],
                        ['$250,000', community.get('hincy200_250')],
                        ['$500,000', community.get('hincy250_500')],
                        ['Above $500K', community.get('hincygt_500')],
                    ]

                    totalIncomeBreakdownStats = 0
                    for householdIncome in householdIncomeBreakdown:
                        if householdIncome[1]:
                            householdIncome[1] = int(householdIncome[1])
                            totalIncomeBreakdownStats += householdIncome[1]
                        else:
                            householdIncome[1] = 0

                    if totalIncomeBreakdownStats:
                        data['householdIncomeBreakdown'] = householdIncomeBreakdown

        if self.stats.get('totalMedianIncome'):
            data['medianIndividualIncome'] = self.stats.get('totalMedianIncome')
            earningsBySex = self.stats.get('acsEarningsBySex')
            if earningsBySex:
                data['earningsBySex'] = [
                    earningsBySex.getAll('Total', 'Male'),
                    earningsBySex.getAll('Total', 'Female'),
                ]

        if data:
            return data

class FinancialReportSectionProperty(FinancialReportSection):

    supports = 'property'

    @subsection('nearbySales', 'Nearby Sales')
    def nearbySales(self):
        if self.stats.get('obiNearbySales'):
            return {'sales': self.stats.get('obiNearbySales')}

    @subsection('propertyValue', 'Property Value')
    def propertyValueSubsection(self):
        data = {}
        util.inheritIfPresent('preferredValueRange', self.stats, data)
        
        if data:
            return data

    @subsection('propertyValue-clickToSpeak', 'Property Value - Click To Speak')
    def propertyValueClickToSpeakFakeSubsection(self):
        return None

class NearbyPropertiesReportSection(ReportSection):

    name = "Nearby"
    priority = 99999
    key = 'nearby-properties'
    template = 'client/nearbyPropertiesReportSection.jinja2'
    supports = 'property'

    @subsection('nearby', 'Nearby Properties')
    def nearbySubsection(self):
        data = {}
        util.inheritIfPresent('nearbyProperties', self.stats, data)

        if data and len(data['nearbyProperties']) > 1:
            return data

class LifeReportSection(ReportSection):

    name = "Life"
    priority = 300
    key = 'life'
    template = 'client/lifeReportSection.jinja2'

    supports = [
        'city',
        'neighborhood',
        'property',
        'zipcode',
    ]

    @subsection('dailyLife', "Daily Life")
    def dailyLifeSubsection(self):
        types = []

        if self.stats.get('yelpBars'):
            types.append({
                'id': "drink",
                'name': "Drink",
                'results': self.stats['yelpBars'],    
            })
        if self.stats.get('yelpRestaurants'):
            types.append({
                'id': "eat",
                'name': "Dine",
                'results': self.stats['yelpRestaurants'],    
            })
        if self.stats.get('yelpGrocery'):
            types.append({
                'id': "shop",
                'name': "Shop",
                'results': self.stats['yelpGrocery'],    
            })
        if self.stats.get('yelpCoffee'):
            types.append({
                'id': "perk",
                'name': "Perk",
                'results': self.stats['yelpCoffee'],    
            })
        if self.stats.get('yelpGyms'):
            types.append({
                'id': "sweat",
                'name': "Sweat",
                'results': self.stats['yelpGyms'],
            })
        if self.stats.get('yelpBeauty'):
            types.append({
                'id': "groom",
                'name': "Groom",
                'results': self.stats['yelpBeauty'],    
            })
        if self.stats.get('yelpPets'):
            types.append({
                'id': "wag",
                'name': "Wag",
                'results': self.stats['yelpPets'],    
            })

        if self.type == 'property':
            yelpSearchLink = "http://www.yelp.com/search?%s" % urllib.urlencode({
                'find_loc': self.target.getFullAddress(),    
                'find_desc': "",
                'ns': "1",
            })
        else:
            yelpSearchLink = None

        if types:
            return {
                'types': types,
                'yelpSearchLink': yelpSearchLink,
            }

class LocalQualityReportSectionRegion(ReportSection):

    name = "Local Quality"
    priority = 275
    key = 'local-quality'
    template = 'client/regionLocalQualityReportSection.jinja2'
    supports = [
        'neighborhood',
        'zipcode',
    ]

    RODENT_CITY_AVERAGES = {
        'manhattan-ny': 18,
        'queens-ny': 4,
        'brooklyn-ny': 7,
        'bronx-ny': 11,
        'staten-island-ny': 2,    
    }

    TREE_CITY_AVERAGES = {
        'manhattan-ny': 77,
        'queens-ny': 7,
        'brooklyn-ny': 75,
        'bronx-ny': 63,
    }

    @subsection('complaints')
    def complaintsSubsection(self):
        data = {}

        util.inheritIfPresent('noiseComplaintsPerCapita', self.stats, data)
        util.inheritIfPresent('filthComplaintsPerCapita', self.stats, data)
        util.inheritIfPresent('streetComplaintsPerCapita', self.stats, data)

        if data:
            return data

    @subsection('trees')
    def treeSubsection(self):
        # TODO: FIX ME
        treeCount = self.stats.get('treeCountPerSqMile')
        treeCountCity = self.stats.get('treeCountPerSqMileRank')
        if treeCount is not None and treeCountCity is not None and len(treeCountCity) == 3:
            treeCountCity = treeCountCity[2]
            return {
                'area': treeCount,
                'city': treeCountCity,
                'areaPercent': 100 * min(treeCount / (2.5 * treeCountCity), 1.0),
                'cityPercent': 40,
            }

    @subsection('rats')
    def ratsSubsection(self):
        # TODO: FIX ME
        rodentCount = self.stats.get('rodentComplaintsPerCapita')
        rodentCountCity = self.stats.get('rodentPerCapitaRank')
        if rodentCount is not None and rodentCountCity is not None and len(rodentCountCity) == 3:
            rodentCountCity = rodentCountCity[2]
            return {
                'area': rodentCount,
                'city': rodentCountCity,
                'areaPercent': 100 * min(rodentCount / (2.5 * rodentCountCity), 1.0),
                'cityPercent': 40,
            }

class LocalQualityReportSectionProperty(ReportSection):

    name = "Local Quality"
    priority = 275
    key = 'local-quality'
    template = 'client/localQualityReportSection.jinja2'
    supports = 'property'

    RODENT_CITY_AVERAGES = {
        'manhattan-ny': 18,
        'queens-ny': 4,
        'brooklyn-ny': 7,
        'bronx-ny': 11,
        'staten-island-ny': 2,    
    }

    TREE_CITY_AVERAGES = {
        'manhattan-ny': 77,
        'queens-ny': 7,
        'brooklyn-ny': 75,
        'bronx-ny': 63,
    }

    @subsection('complaints', 'Complaints')
    def complaintsSubsection(self):
        data = {}

        util.inheritIfPresent('noiseComplaints', self.stats, data)
        util.inheritIfPresent('filthComplaints', self.stats, data)
        util.inheritIfPresent('streetComplaints', self.stats, data)

        if data:
            return data

    @subsection('rats', 'Rats')
    def ratsSubsection(self):
        rodentComplaints = self.stats.get('rodentComplaints')
        rodentAvg = self.RODENT_CITY_AVERAGES.get(self.target.city)
        if rodentComplaints is not None and rodentAvg is not None:
            maximum = 2.5 * rodentAvg
            return {
                'building': rodentComplaints['count'],
                'city': rodentAvg,
                'buildingPercent': 100 * min(rodentComplaints['count'] / maximum, 1.0),
                'cityPercent': 100 * min(rodentAvg / maximum, 1.0),
            }

    @subsection('trees', 'Trees')
    def treesSubsection(self):
        streetTrees = self.stats.get('streetTrees')
        streetTreeAvg = self.TREE_CITY_AVERAGES.get(self.target.city)
        if streetTrees is not None and streetTreeAvg is not None:
            maximum = 2.5 * streetTreeAvg
            return {
                'streetTreeCount': streetTrees['count'],
                'streetTreePercent': 100 * min(streetTrees['count'] / maximum, 1.0),
                'cityCount': streetTreeAvg,
                'cityPercent': 100 * min(streetTreeAvg / maximum, 1.0),
            }

class LocationReportSectionCity(ReportSection):

    name = "Location"
    priority = 100
    key = 'location'
    template = 'client/cityLocationReportSection.jinja2'
    supports = 'city'

    @subsection('map')
    def mapSubsection(self):
        return {
            'city': self.target.slug,
        }

class LocationReportSectionProperty(ReportSection):

    name = "Location"
    priority = 100
    key = 'location'
    template = 'client/locationReportSection.jinja2'
    supports = 'property'

    @subsection('map', "Map")
    def mapSubsection(self):
        data = {}
        if 'location' in self.stats:
            data['location'] = self.stats['location']
        if 'buildingFootprint' in self.stats:
            data['footprint'] = self.stats['buildingFootprint']
        return data

class LocationReportRegion(ReportSection):

    name = "Location"
    priority = 100
    key = 'location'
    template = 'client/regionLocationReportSection.jinja2'
    supports = [
        'neighborhood',
        'zipcode',
    ]

    @subsection('map')
    def mapSubsection(self):
        return {
            'neighborhood': self.target.slug,
            'areaType': self.type,
        }

class PropertiesSection(ReportSection):

    name = "Properties"
    priority = 2100
    key = 'properties'
    template = 'client/propertiesReportSection.jinja2'
    supports = [
        'city',
        'neighborhood',
    ]

    @subsection('properties')
    def properties(self):
        if rutil.safeAccess(self.stats, 'properties', 'results'):
            return {
                'properties': self.stats['properties'],
            }

class SchoolReportSection(ReportSection):

    name = "School"
    priority = 280
    key = 'school'
    template = 'client/schoolReportSection.jinja2'
    supports = [
        'city',
        'neighborhood',
        'zipcode',
    ]
    locationType = "area"

    @subsection('district')
    def district(self):

        result = []
        sds = self.stats.get('schoolDistricts')
        if sds:
            for sd in sds:
                data = self.populateSDData(sd)
                if data:
                    result.append(data)

            if result:
                return result

    def populateSDData(self, district):
        data = {}

        data['id'] = district.get('obId')

        websiteUrl = district.get('WEBSITE_URL')
        if websiteUrl and websiteUrl != '':
            if not websiteUrl.lower().startswith('http'):
                websiteUrl = "http://%s" % websiteUrl
            data['website'] = websiteUrl
        else:
            data['website'] = None

        name = district.get('name') or district.get('DISTRICT_NAME')
        if name:
            data['name'] = name

        elem = district.get('COUNT_ELEMENTARY')
        mid = district.get('COUNT_MIDDLE')
        high = district.get('COUNT_HIGH')

        if elem or mid or high:
            elem = int(elem or '0')
            mid = int(mid or '0')
            high = int(high or '0')
            total = elem + mid + high
            data['counts'] = {
                'total': total,
            }
            data['schoolBreakdownByLevel'] = [
                ('Elementary', elem),
                ('Middle', mid),
                ('High', high),
            ]

        breakdownByGrade = [
            ('K', int(district.get('ENROLLMENT_BY_GRADE_KGTN') or 0)),
            ('1', int(district.get('ENROLLMENT_BY_GRADE_ONE') or 0)),
            ('2', int(district.get('ENROLLMENT_BY_GRADE_TWO') or 0)),
            ('3', int(district.get('ENROLLMENT_BY_GRADE_THREE') or 0)),
            ('4', int(district.get('ENROLLMENT_BY_GRADE_FOUR') or 0)),
            ('5', int(district.get('ENROLLMENT_BY_GRADE_FIVE') or 0)),
            ('6', int(district.get('ENROLLMENT_BY_GRADE_SIX') or 0)),
            ('7', int(district.get('ENROLLMENT_BY_GRADE_SEVEN') or 0)),
            ('8', int(district.get('ENROLLMENT_BY_GRADE_EIGHT') or 0)),
            ('9', int(district.get('ENROLLMENT_BY_GRADE_NINE') or 0)),
            ('10', int(district.get('ENROLLMENT_BY_GRADE_TEN') or 0)),
            ('11', int(district.get('ENROLLMENT_BY_GRADE_ELEVEN') or 0)),
            ('12', int(district.get('ENROLLMENT_BY_GRADE_TWELVE') or 0)),
        ]
        if sum([x[1] for x in breakdownByGrade]) > 0:
            data['breakdownByGrade'] = breakdownByGrade

        if district.get('STUDENTS_NUMBER_OF'):
            totalStudents = int(district.get('STUDENTS_NUMBER_OF') or '0')
            data['totalStudents'] = totalStudents

        if district.get('EDUCATIONAL_CLIMATE_INDEX'):
            data['rating'] = district['EDUCATIONAL_CLIMATE_INDEX']

        if data:
            data['locationType'] = self.locationType
            return data 

class SchoolReportSectionProperty(SchoolReportSection):

    supports = 'property'
    locationType = 'property'

    @subsection('schools')
    def schools(self):
        data = {}

        util.inheritIfPresent('elementarySchools', self.stats, data)
        util.inheritIfPresent('middleSchools', self.stats, data)
        util.inheritIfPresent('highSchools', self.stats, data)

        if data:
            return data

class SocialReportSectionProperty(ReportSection):

    name = "Social Buzz"
    priority = 285
    key = "socialbuzz"
    template = 'client/socialbuzzReportSection.jinja2'
    supports = ['property', 'neighborhood', 'city']

    @subsection('socialPhotos', 'Local Photos')
    def socialPhotos(self):
        return None #temp disable it
        # data = {}
        # util.inheritIfPresent('socialPhotoSlug', self.stats, data)
        # util.inheritIfPresent('socialPhotoDomain', self.stats, data)
        # if data and data.get('socialPhotoSlug', None):
        #     data['socialPhotoDomain'] = data.get('socialPhotoDomain', None)
        #     return data

class TransportationReportSection(ReportSection):

    name = "Transportation"
    priority = 200
    key = 'transportation'
    template = 'client/transportationReportSection.jinja2'
    supports = 'property'

    @subsection('commuteOptimizer')
    def commuteOptimizer(self):
        return "OK"

    @subsection('commuteStats')
    def commuteStats(self):
        data = {}

        timeLeavingForWork = self.stats.get('acsTimeLeavingForWork')
        if timeLeavingForWork:
            data['timeLeavingForWork'] = timeLeavingForWork.getAll('Total')
            mode = max(data['timeLeavingForWork'], 
                key=lambda t: t[1])
            data['modeTimeLeavingForWork'] = mode[0]
            data['modeTimeLeavingForWorkPercent'] = util.safeDivide(mode[1], timeLeavingForWork.get('Total'))

        commuteTimes = self.stats.get('acsCommuteTimes')
        if commuteTimes:
            data['commuteTimes'] = commuteTimes.getAll('Total')
            mode = max(data['commuteTimes'], key=lambda t: t[1])
            data['modeCommuteTime'] = mode[0]
            data['modeCommuteTimePercent'] = util.safeDivide(mode[1], commuteTimes.get('Total'))

        commuteMethods = self.stats.get('acsCommuteMethods')
        if commuteMethods:
            cars = commuteMethods.getAll('Total', 'Car')
            publics = commuteMethods.getAll('Total', 'Public Transportation')
            other = commuteMethods.getAll('Total')
            data['commuteMethods'] = cars + publics + other[2:]
            mode = max(data['commuteMethods'], key=lambda t: t[1])
            data['modeCommuteMethod'] = mode[0]
            data['modeCommuteMethodPercent'] = util.safeDivide(mode[1], commuteMethods.get('Total'))
        
        citibike = self.stats.get('citibike')
        if citibike is not None:
            data['citibikeCount'] = citibike['count']

        obiCommunity = self.stats.get('obiCommunity')
        if obiCommunity:
            logging.info(obiCommunity)
            data['carsPercent'] = (
                float(obiCommunity.get('vph1'))
                + float(obiCommunity.get('vphgt1'))
            )

        if data:
            return data

    @subsection('nycSubway', "NYC Subway")
    def nycSubwaySubsection(self):
        if 'subwayEntrances' in self.stats:
            return {
                'subwayEntrances': self.stats['subwayEntrances']['results']
            }

    @subsection('nycTaxi')
    def nycTaxiStats(self):
        data = {}

        util.inheritIfPresent('taxiPickups', self.stats, data)
        util.inheritIfPresent('taxiDropoffs', self.stats, data)
        util.inheritIfPresent('taxiPassEmpties', self.stats, data)
        util.inheritIfPresent('taxiWaitTime', self.stats, data)
        util.inheritIfPresent('taxiPickupsByHour', self.stats, data)
        util.inheritIfPresent('taxiDropoffsByHour', self.stats, data)
        util.inheritIfPresent('taxiPassEmptiesByHour', self.stats, data)
        util.inheritIfPresent('taxiWaitTimeByHour', self.stats, data)
        util.inheritIfPresent('taxiBestIntersection', self.stats, data)

        if data:
            return data

class WeatherReportSection(ReportSection):

    name = "Weather"
    priority = 1100
    key = 'weather'
    template = 'client/weatherReportSection.jinja2'
    supports = [
        'city',
        'neighborhood',
        'zipcode',
    ]

    @subsection('disasters')
    def disasters(self):
        if self.stats.get('obiCommunity'):
            community = self.stats.get('obiCommunity')
            risks = {
                'earthquake': community.get('rskcyquak'),
                'storm': community.get('rskcyrisk'),
                'hail': community.get('rskcyhanx'),
                'hurricane': community.get('rskcyhunx'),
                'tornado': community.get('rskcytonx'),
                'wind': community.get('rskcywinx'),
            }
            for risk, value in risks.items():
                if value == '':
                    value = "low"
                else:
                    value = float(value)
                    if value < 50:
                        value = "low"
                    elif value < 120:
                        value = "mild"
                    elif value < 300:
                        value = "high"
                    else:
                        value = "severe"
                risks[risk] = value

            if 'floodZoneName' in self.stats:
                floodZone = self.stats['floodZoneName']
                if floodZone in ['1', '2']:
                    risks['hurricane'] = 'severe'
                elif floodZone in ['3', '4']:
                    risks['hurricane'] = 'high'

            return risks

    @subsection('weather')
    def weatherSubsection(self):
        if self.stats.get('obiCommunity'):
            community = self.stats.get('obiCommunity')
            data = {}
            data['winterTemperatures'] = {
                'average': community.get('tmpavejan'),
                'high': community.get('tmpmaxjan'),
                'low': community.get('tmpminjan'),
            }
            data['summerTemperatures'] = {
                'average': community.get('tmpavejul'),
                'high': community.get('tmpmaxjul'),
                'low': community.get('tmpminjul'),
            }
            data['annualRainfall'] = community.get('preciprain')
            data['annualSnow'] = community.get('precipsnow')
            return data

class WeatherReportSectionProperty(WeatherReportSection):

    supports = 'property'

    @subsection('breezometer')
    def breezometer(self):
        if self.stats.get('breezometer'):
            data = self.stats.get('breezometer')
            if data.get('breezometer_aqi'):
                aqi = data['breezometer_aqi']
                rotation = min((120 - 1.2 * aqi), 70)
                data['rotation'] = rotation
                return data

    @subsection('floodZone')
    def floodZoneSubsection(self):
        data = {}
        util.inheritIfPresent('floodZoneName', self.stats, data)
        if data:
            return data