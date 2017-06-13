import math

from rentenna3 import text
from rentenna3.base import BaseReportDescriptor
from rentenna3.data.cities import NEW_YORK_CITY_SLUGS_SET

class ApartmentDescriptor(BaseReportDescriptor):

    priority = 100
    supports = 'property'

    def generate(self):
        address = self.target
        stats = self.stats
        commonName = self.target.getCommonName(self.stats)

        lines = []

        apartmentModifiers = []
        if stats.get('floorCount'):
            apartmentModifiers.append("%s-floor" % stats['floorCount'])
        if stats.get('unitCount'):
            apartmentModifiers.append("%s-unit" % stats['unitCount'])
        apartmentModifier = ", ".join(apartmentModifiers)
        if stats.get('buildingType'):
            apartmentModifier += " %s" % stats['buildingType']
        else:
            apartmentModifier += " building"

        city = address.getCity()
        if stats.get('neighborhood') and city:
            location = "%s's %s" % (city.name, stats['neighborhood'].name)
        elif stats.get('neighborhood'):
            location = stats['neighborhood'].name   
        elif city and city.isOther():
            location = city.name 
        else:
            location = address.addrCity

        if stats.get('intersection'):
            near = " near %s" % stats['intersection']['nearest'].getName()
        else:
            near = ""

        lines.append(
            """
                %(buildingName)s is a %(apartmentModifier)s in %(location)s%(near)s.
            """ % {
                'buildingName': commonName,
                'apartmentModifier': apartmentModifier,
                'location': location,
                'near': near,
            }
        )

        buildingComponents = []
        buildYear = self.stats.get('buildYear')
        if buildYear:
            buildingComponents.append("was built in %s" % buildYear)
        bedCount = self.stats.get('bedCount')
        if bedCount:
            buildingComponents.append("has %s" % text.plural(bedCount, 'bedroom'))
        sqft = self.stats.get('buildingSqft')
        if sqft:
            buildingComponents.append("has %s square feet of living space" % text.commaNumber(sqft))
        if buildingComponents:
            lines.append("The building %s." % text.commas(buildingComponents))

        return " ".join(lines)

class AreaDescriptor(BaseReportDescriptor):

    priority = 100
    supports = [
        'neighborhood',
        'zipcode'
    ]

    def generate(self):
        area = self.target
        stats = self.stats

        parts = [] 

        city = area.getCity()
        if city is not None:
            cityExistsStatement = " in %s" % city.name
        else:
            cityExistsStatement = ""

        totalPop = stats.get('totalPopulation')
        if totalPop:
            popStatement = " with a total population of %s" % text.commaNumber(totalPop)
        else:
            popStatement = ""

        parts.append("%s is a %s%s%s." % (
            area.name, 
            self.type,
            cityExistsStatement,
            popStatement,
        ))
        
        size = stats.get('areaMiles')
        if size:
            parts.append("It occupies approximately %.2f square miles." % (size))

        trees = stats.get('treeCountPerSqMile')
        if trees:
            parts.append("There are %s street trees per square mile." % text.commaNumber(trees))

        if parts:
            return " ".join(parts)

class ConstructionDescriptor(BaseReportDescriptor):

    priority = 300
    supports = 'property'

    def generate(self):
        address = self.target
        stats = self.stats
        commonName = self.target.getCommonName(self.stats)

        construction = []
        if stats.get('buildingJobs'):
            buildingJobsCount = text.plural(
                len(stats['buildingJobs']),
                "construction or renovation project"
            )
            construction.append("""
                Building records show 
                <a href="#construction">%(buildingJobsCount)s</a>
                at %(buildingName)s since 2003.
            """ % {
                'buildingJobsCount': buildingJobsCount,
                'buildingName': commonName,
            })

        if stats.get('demolitions') or stats.get('newBuildings'):
            changes = []
            if stats.get('demolitions'):
                changes.append(text.plural(
                    stats['demolitions']['count'], 
                    "demolition",
                ))
            if stats.get('newBuildings'):
                changes.append(text.plural(
                    stats['newBuildings']['count'], 
                    "new building development",
                ))
            changesText = text.commas(changes)
            construction.append("""
                As for neighborhood change, records show
                %s in the area within the past year.
            """ % changesText)

        return " ".join(construction)

class DemographicDescriptor(BaseReportDescriptor):

    priority = 500
    supports = [
        'city',
        'neighborhood',
        'property',
        'zipcode',
    ]

    def generate(self):
        address = self.target
        stats = self.stats

        demographics = []

        # First Sentence
        demographicCounts = []
        if stats.get('acsMedianAgeBySex'):
            totalAge = stats.get('acsMedianAgeBySex').get('Total')
            if totalAge:
                demographicCounts.append("""
                    the median age is %s
                """ % int(totalAge))
        
        maritalStatusPercent = stats.get('maritalStatusPercent')
        if maritalStatusPercent is not None:
            demographicCounts.append("""
                %s%% of residents are married
            """ % format(int(maritalStatusPercent * 100), '.0f'))

        childrenPercent = stats.get('childrenPercent')
        if childrenPercent:
            demographicCounts.append("""
                %s%% of residents have at least one child
            """ % format(int(childrenPercent * 100), '.0f'))

        if demographicCounts:
            demographics.append("""
                As for the <a href="#demographics">demographics %(areaName)s</a>, %(demographicCounts)s.
            """ % {
                'areaName': self.getAreaName(),
                'demographicCounts': text.commas(demographicCounts)
            })

        # Second Sentence
        incomeParts = []
        totalMedianIncome = stats.get('totalMedianIncome')
        if totalMedianIncome:
            income = '{:20,.0f}'.format(totalMedianIncome)
            incomeParts.append("""
                the median individual full-time income is about $%s
            """ % income.strip())

        if stats.get('acsEducation'):
            education = stats.get('acsEducation')
            totalEducation = education.get('Total')
            bachelors = education.get('Total', 'Bachelor\'s Degree')

            if bachelors and totalEducation:
                collegePct = bachelors / totalEducation
                incomeParts.append("""
                    about %s%% of adults here have a bachelor's degree or higher
                """ % format(collegePct * 100, '.0f'))

        if incomeParts:
            demographics.append(text.capitalize(text.commas(incomeParts)) + ".")

        # Third Sentence
        if stats.get('votersInBuildingPercent'):
            demographics.append("""
                Registered voters in this building are %(percent)s%% %(type)s.
            """ % {
                'percent': format(stats.get('votersInBuildingPercent').get('maxPercent') * 100, '.0f'),
                'type': stats.get('votersInBuildingPercent').get('maxKey'),
            })
        elif stats.get('votersPercent'):
            demographics.append("""
                Voters in this area are %(percent)s%% %(type)s.
            """ % {
                'percent': format(stats.get('votersPercent').get('maxPercent') * 100, '.0f'),
                'type': stats.get('votersPercent').get('maxKey'),
            })

        return " ".join(demographics)

class FinancialDescriptor(BaseReportDescriptor):

    priority = 200
    supports = [
        'city',
        'neighborhood',
        'zipcode',
    ]

    def generate(self):
        stats = self.stats
        lines = []

        expenses = stats.get('expenses')
        if expenses and expenses['total'] and expenses['total']['difference']:
            lines.append("""
                Overall, 
                <a href="#financial">expenses in %s</a> 
                are %s %s than the National Average.
            """ % (
                self.target.name,
                text.percent(expenses['total']['difference'], True),
                expenses['total']['direction'],
            ))

        rentVsOwn = stats.get('rentVsOwn')
        if rentVsOwn:
            if rentVsOwn['rent'] > 0.5:
                most = (
                    self.getAreaName(), 
                    "rent", 
                    text.percent(rentVsOwn['rent']), 
                    'renters',
                )
            else:
                most = (
                    self.getAreaName(),
                    "own", 
                    text.percent(rentVsOwn['own']), 
                    'owners',
                )

            lines.append("""
                Most people %s %s their home, with %s 
                of households being occupied by %s.
            """ % most)

        if lines:
            return " ".join(lines)

class GenericCityDescriptor(BaseReportDescriptor):

    priority = 100
    supports = 'city'

    def generate(self):
        city = self.target
        return "%s is a city in %s." % (city.name, city.getState().name)

class LocalQualityDescriptor(BaseReportDescriptor):

    priority = 200
    supports = 'property'

    def generate(self):
        address = self.target
        stats = self.stats
        commonName = self.target.getCommonName(self.stats)

        negativity = []
        if stats.get('complaintsExist'):
            complaintStatement = """
                If you live at or are thinking of moving to %s, you'll
            """ % commonName
            total = stats.get('totalProblems', 0) + stats.get('totalViolations', 0)
            if total:
                complaintStatement += """
                    want to carefully examine the <a href="#complaints">
                    %(count)s problems and violations</a> we've detected 
                    in this property's records.
                """ % {'count': total}
            else:
                complaintStatement += """
                    be happy to learn we haven't found any 
                    problems or violations reported in 
                    this property's records.
                """
            negativity.append(complaintStatement)
        crimeCounts = []
        if stats.get('nypdCrimes'):
            pass #TODO: github #393 this is temp solution to disable crime descriptor for a property
            # crimeCounts.append(text.plural(
            #     int(stats['nypdCrimes']['count']), 
            #     "felony crime"
            # ))
            
        if crimeCounts:
            negativity.append("""
                As for safety, there were <a href="#crime">%(count)s</a> 
                reported near %(buildingName)s over the past year.
            """ % {
                'count': text.commas(crimeCounts),
                'buildingName': commonName,
            })
        localQualityCounts = []
        if stats.get('noiseComplaints'):
            localQualityCounts.append(text.plural(
                int(stats['noiseComplaints']['count']), 
                "noise complaint"
            ))
        if stats.get('filthComplaints'):
            localQualityCounts.append(text.plural(
                int(stats['filthComplaints']['count']), 
                "filth complaint",
            ))
        if stats.get('streetComplaints'):
            localQualityCounts.append(text.plural(
                int(stats['streetComplaints']['count']), 
                "street quality complaint",
            ))
        if localQualityCounts:
            negativity.append("""
                In addition, residents filed <a href="#local-quality">%(count)s</a>.
            """ % {
                'count': text.commas(localQualityCounts)
            })

        return " ".join(negativity)

class SafetyDescriptor(BaseReportDescriptor):

    priority = 600
    supports = ['city', 'neighborhood', 'zipcode']

    def generate(self):
        city = self.target
        stats = self.stats
        lines = []

        crimeRisks = stats.get('crimeRisks')
        if crimeRisks:
            lines.append("""
                The overall 
                <a href="#crime">risk of crime</a> 
                in %s is %s %s than the National Average.
            """ % (
                city.name,
                text.percent(crimeRisks['total']['percent'], True),
                crimeRisks['total']['direction'],
            ))

        community = self.stats.get('obiCommunity')
        if community:
            winter = community.get('tmpavejan')
            summer = community.get('tmpavejul')
            if winter and summer:
                lines.append("""
                    As for 
                    <a href="#weather">weather,</a> 
                    the average summer temperature is %.1f&#176;F, 
                    while the average winter temperature is
                    %.1f&#176;F.
                """ % (float(summer), float(winter)))

        if lines:
            return " ".join(lines)

class SchoolDescriptor(BaseReportDescriptor):

    priority = 600
    supports = 'property'

    def generate(self):
        address = self.target
        stats = self.stats
        commonName = self.target.getCommonName(self.stats)

        schoolParts = []
        schoolDistricts = stats.get('schoolDistricts')
        if schoolDistricts:
            isFirst = True
            for schoolDistrict in schoolDistricts:
                schoolParts.extend( self.buildSchoolDistrictStatement(schoolDistrict, isFirst) )
                isFirst = False

        elementarySchools = stats.get('elementarySchools')
        middleSchools = stats.get('middleSchools')
        highSchools = stats.get('highSchools')

        bestElementarySchool = self.getBestSchoolName(elementarySchools)
        bestMiddeSchool = self.getBestSchoolName(middleSchools, [bestElementarySchool])
        bestHighSchool = self.getBestSchoolName(highSchools, [bestElementarySchool, bestMiddeSchool])
        bestSchools = []
        if bestElementarySchool:
            bestSchools.append(bestElementarySchool)
        if bestMiddeSchool:
            bestSchools.append(bestMiddeSchool)
        if bestHighSchool:
            bestSchools.append(bestHighSchool)

        if bestSchools:
            individualSchoolsStatement = """
                You can see individual <a href="#school">ratings and
                program information on nearby schools</a> like %s
                in the report below.
            """ % text.commas(bestSchools)

            schoolParts.append(individualSchoolsStatement)

        return ".".join(schoolParts)

    def buildSchoolDistrictStatement(self, schoolDistrict, isFirst):
        schoolParts = []
        if schoolDistrict:
            also = "" if isFirst else "also " 
            schoolDistrictStatement = """This address is %szoned for %s""" % (also, text.capitalizeEveryWord(schoolDistrict.name))

            rating = schoolDistrict.get('EDUCATIONAL_CLIMATE_INDEX')
            if rating:
                schoolDistrictStatement += """, which is rated %s overall""" % rating.lower()

            schoolParts.append(schoolDistrictStatement)
        return schoolParts

    def getBestSchoolName(self, schoolList, currentSchoolNames=None):
        if not(schoolList):
            return None

        if currentSchoolNames:
            bestSchool = None
            for school in schoolList:
                if school.getName() not in currentSchoolNames:
                    if bestSchool is None or bestSchool.GS_TEST_RATING < school.GS_TEST_RATING:
                        bestSchool = school

            if bestSchool:
                return text.capitalizeEveryWord(bestSchool.getName())
            else:
                return bestSchool
        else:
            bestSchool = max(schoolList, key=lambda school: school.GS_TEST_RATING)
            return text.capitalizeEveryWord(bestSchool.getName())

class SchoolDescriptorRegion(BaseReportDescriptor):

    priority = 700
    supports = [
        'city',
        'neighborhood',
        'zipcode',
    ]

    def generate(self):
        area = self.target
        stats = self.stats

        schoolParts = []
        schoolDistrictStatement = ""
        schoolDistricts = stats.get('schoolDistricts')
        if schoolDistricts:
            isFirst = True
            for schoolDistrict in schoolDistricts:
                schoolParts.extend( self.buildSchoolDistrictStatement(schoolDistrict, isFirst) )
                isFirst = False

        schoolParts.append("""To see detailed information on the schools
            near any individual property, look that property up by street address.""")

        return ". ".join(schoolParts)

    def buildSchoolDistrictStatement(self, schoolDistrict, isFirst):
        schoolParts = []
        if schoolDistrict:
            also = "" if isFirst else "also "
            schoolDistrictStatement = """This area is %szoned for <a href="#school">%s</a>""" % (also, text.capitalizeEveryWord(schoolDistrict.name))

            numStudents = schoolDistrict.get('STUDENTS_NUMBER_OF')
            if numStudents:
                schoolDistrictStatement += """, which has approximately %s students enrolled""" % text.commaNumber(numStudents)

                elem = schoolDistrict.get('COUNT_ELEMENTARY')
                mid = schoolDistrict.get('COUNT_MIDDLE')
                high = schoolDistrict.get('COUNT_HIGH') 

                numSchools = int(elem or '0') + int(mid or '0') + int(high or '0')
                if numSchools:
                    schoolDistrictStatement += """ across %s schools""" % numSchools

            ratingDescripton = schoolDistrict.get('EDUCATIONAL_CLIMATE_INDEX')
            if ratingDescripton:
                schoolDistrictStatement += """ and is rated %s overall based on student test scores""" % ratingDescripton.lower()

            schoolParts.append(schoolDistrictStatement)
        return schoolParts

#TODO: figure out how it is being used.
# class SocialCityDescriptor(BaseReportDescriptor):

#     priority = 285
#     supports = ['property', 'neighborhood']
#     cities = list(NEW_YORK_CITY_SLUGS_SET)

#     def generate(self):
#         address = self.target
#         stats = self.stats
#         #commonName = self.target.getCommonName(self.stats)

#         socialCityParts = ["Local Photos"]
#         return text.capitalize(text.commas(socialCityParts))

class TransportationDescriptor(BaseReportDescriptor):

    priority = 400
    supports = 'property'

    def generate(self):
        address = self.target
        stats = self.stats
        commonName = self.target.getCommonName(self.stats)

        transportationParts = []
        subwayEntrances = stats.get('subwayEntrances')
        if subwayEntrances and subwayEntrances.get('results'):
            subwayEntrances = subwayEntrances['results']
            closest = subwayEntrances[0]
            subwayLines = text.commas(closest.getLines()[:4])
            transportationParts.append("""
                the <a href="#transportation">closest subway access</a> includes 
                the %(lines)s at %(location)s
            """ % {
                'location': closest.getNiceName(),
                'lines': subwayLines,
            })

        if stats.get('citibike') is not None:
            transportationParts.append("""
                there are %s nearby
            """ % text.plural(
                stats['citibike']['count'], 
                "Citi Bike station"
            ))

        if stats.get('taxiWaitTime') is not None:
            waitTime = stats.get('taxiWaitTime')
            if waitTime <= 90:
                waitTime = str(waitTime) + " seconds"
            else:
                waitTime = format(math.ceil(waitTime / 60.0), '.0f') + " minutes"
            transportationParts.append("""
                the typical wait time for a taxi at %(buildingName)s is %(waitTime)s.
            """ % {
                'buildingName': commonName,
                'waitTime': waitTime,
            })

        return text.capitalize(text.commas(transportationParts))

class WeatherDescriptor(BaseReportDescriptor):

    priority = 900
    supports = [
        'city',
        'property',
        'neighborhood',
        'zipcode',
    ]

    def generate(self):
        lines = []

        community = self.stats.get('obiCommunity')
        if community:
            winter = community.get('tmpavejan')
            summer = community.get('tmpavejul')
            if winter and summer:
                lines.append("""
                    Regarding
                    <a href="#weather">weather,</a> 
                    the average summer temperature is %.1f&#176;F, 
                    while the average winter temperature is
                    %.1f&#176;F.
                """ % (float(summer), float(winter)))

            rain = community.get('preciprain')
            snow = community.get('precipsnow')
            if rain and snow:
                if snow == "0.00":
                    snowStatement = "there is generally no snow"
                else:
                    snowStatement = "the average annual snowfall is %.1f inches" % float(snow)
                lines.append("""
                    The average annual rainfall is %.1f inches
                    and %s.
                """ % (float(rain), snowStatement))

        if lines:
            return " ".join(lines)