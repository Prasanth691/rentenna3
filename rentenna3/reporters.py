import collections
import math
import time
import datetime
import random

from threading import Lock

from web import taskqueue
from web import rutil
from web.crawling import CrawlResponse

from rentenna3 import util
from rentenna3.base import BaseReporter
from rentenna3.data.cities import NEW_YORK_CITY_SLUGS_SET
from rentenna3.models import *
from rentenna3 import api

# abstract reporters

class GeoSimpleReporter(BaseReporter):

    __abstract__ = True
    supports = [
        'city',
        'neighborhood',
        'zipcode',
    ]

    def prepareArea(self, target):
        return target.getGeoSimple()

    def prepareCity(self, target):
        return target.getGeoSimple()

    def prepareZipCode(self, target):
        return target.getGeoSimple()

class MongoGeoReporter(BaseReporter):

    __abstract__ = True
    onDemand = True
    precompute = True
    supports = 'property' # todo: could
    version = 100

    countOnly = False
    limit = None
    modelCls = None
    statName = None

    # only relevant for properties
    distanceClass = 'area'

    # only relevant if processResults is not overridden
    putCount = True
    putNearest = True
    putResults = True

    def getFilter(self):
        return None

    def prepareArea(self, target):
        return self.prepareRegion(target)

    def prepareAddress(self, target):
        return {
            'target': target,
            'geo': target.location,
            'queryType': 'proximity',
        }

    def prepareCity(self, target):
        return self.prepareRegion(target)

    def prepareZipCode(self, target):
        return self.prepareRegion(target)

    def prepareRegion(self, target):
        return {
            'target': target,
            'geo': target.getGeoSimple(),
            'queryType': 'intersects',
        }

    def processResults(self, results, queryInfo):
        output = {}

        if self.putCount:
            if self.countOnly:
                output['count'] = results
            else:
                output['count'] = len(results)
        if self.putNearest and not self.countOnly:
            if results:
                output['nearest'] = results[0]
            else:
                output['nearest'] = None
        if self.putResults and not self.countOnly:
            output['results'] = results

        output.update(queryInfo)

        return output

    def report(self):
        if self.target['queryType'] == 'proximity':
            distPref = self.target['target'].getCity().getDistance(self.distanceClass)
            results = self.modelCls.getNearest(
                self.target['geo'],
                distPref['distance'],
                filter=self.getFilter(),
                limit=self.limit,
                count=self.countOnly,
            )
            queryInfo = {
                'distanceMeters': distPref['distance'],
                'distanceDescription': distPref['description'],
            }
        else:
            results = self.modelCls.queryGeoref(
                self.target['geo'],
                filter=self.getFilter(),
                limit=self.limit,
                count=self.countOnly,
            )
            queryInfo = {
                # TODO: something like, in Upper West Side?
            }
        output = self.processResults(results, queryInfo)
        self.putStat(self.statName, output)

# concrete reporters

class AcsSf1Reporter(BaseReporter):

    description = "Querying American Community Survey for demographic data"
    onDemand = True
    precompute = True
    supports = 'property'
    version = 4

    def report(self):
        tigers = TigerLineMongoModel.forAddress(self.target)
        tract = tigers.get('Tract')
        if tract:
            acs = tract.getAcsSf1()
            if acs:
                self.putStat('acsCommuteMethods', acs.getCommuteMethods())
                self.putStat('acsCommuteTimes', acs.getCommuteTimes())
                self.putStat('acsChildren', acs.getChildren())
                self.putStat('acsEarningsBySex', acs.getEarningsBySex())
                self.putStat('acsEducation', acs.getEducation())
                self.putStat('acsGeographicMobility', acs.getGeographicMobility())
                self.putStat('acsHouseholdIncome', acs.getHouseholdIncome())
                self.putStat('acsMaritalStatus', acs.getMaritalStatus())
                self.putStat('acsMaritalStatusBySexAndAge', acs.getMaritalStatusBySexAndAge())
                self.putStat('acsMedianAgeBySex', acs.getMedianAgeBySex())
                self.putStat('acsMedianHouseholdIncome', acs.getMedianHouseholdIncome())
                self.putStat('acsMedianIncomeStats', acs.getMedianIncomeStats())
                self.putStat('acsPlaceOfBirth', acs.getPlaceOfBirth())
                self.putStat('acsRaceBySex', acs.getRaceBySex())
                self.putStat('acsSample', tract.NAMELSAD10)
                self.putStat('acsSampleGeo', tract.geo)
                self.putStat('acsTimeLeavingForWork', acs.getTimeLeavingForWork())

class AcsSf1CombinerReporter(GeoSimpleReporter):

    description = "Computing demographic data from ACS SF1"
    onDemand = False
    precompute = True
    version = 6

    def report(self):
        query = {
            'location': {
                '$geoIntersects': {
                    '$geometry': self.target,
                },
            },
            'SUMLEVEL': "080",
        }

        totalPopulation = 0
        householdsTotal = 1 # cheat divide-by-zero error
        householdsWithChildrenTotal = 0
        medianHouseholdIncomeTotal = 0
        medianHouseholdIncomeSamples = 1 # cheat divide-by-zero error
        medianAgeTotal = 0
        medianAgeSamples = 1 # cheat divide-by-zero error

        commuteMethods = Sf1TableSummer()
        commuteTimes = Sf1TableSummer()
        childrens = Sf1TableSummer()
        earningsBySexes = Sf1TableSummer()
        educations = Sf1TableSummer()
        geographicMobilities = Sf1TableSummer()
        householdIncomes = Sf1TableSummer()
        maritalStatuses = Sf1TableSummer()
        maritalStatusesBySexAndAge = Sf1TableSummer()
        medianAgeBySexes = Sf1TableSummer()
        medianHouseholdIncomes = Sf1TableSummer()
        medianIncomeStats = Sf1TableSummer()
        placeOfBirths = Sf1TableSummer()
        timeLeavingForWorks = Sf1TableSummer()

        for sample in AcsSf1MongoModel.queryIter(query):
            localPopulation = sample.getTotalPopulation().get('Total')

            totalPopulation += localPopulation
            children = sample.getChildren()
            householdsTotal += children.get('Total')
            householdsWithChildrenTotal += children.get(
                'Total',
                'Households with one or more people under 18 years',
            )

            localMedianHouseholdIncome = sample.getMedianHouseholdIncome().get('Total')
            if localMedianHouseholdIncome:
                medianHouseholdIncomeTotal += localPopulation * localMedianHouseholdIncome
                medianHouseholdIncomeSamples += localPopulation

            localMedianAge = sample.getMedianAgeBySex().get('Total')
            if localMedianAge:
                medianAgeTotal += localPopulation * localMedianAge
                medianAgeSamples += localPopulation

            commuteMethods.add(sample.getCommuteMethods())
            commuteTimes.add(sample.getCommuteTimes())
            childrens.add(sample.getChildren())
            earningsBySexes.add(sample.getEarningsBySex())
            educations.add(sample.getEducation())
            geographicMobilities.add(sample.getGeographicMobility())
            householdIncomes.add(sample.getHouseholdIncome())
            maritalStatuses.add(sample.getMaritalStatus())
            maritalStatusesBySexAndAge.add(sample.getMaritalStatusBySexAndAge())
            medianAgeBySexes.add(sample.getMedianAgeBySex())
            medianHouseholdIncomes.add(sample.getMedianHouseholdIncome())
            medianIncomeStats.add(sample.getMedianIncomeStats())
            placeOfBirths.add(sample.getPlaceOfBirth())
            timeLeavingForWorks.add(sample.getTimeLeavingForWork())

        self.putStat('totalPopulation', totalPopulation)
        self.putStat('householdsTotal', householdsTotal)
        self.putStat('householdsWithChildrenTotal', householdsWithChildrenTotal)
        self.putStat('householdsWithChildrenPercent',
            (householdsWithChildrenTotal / householdsTotal))
        self.putStat('medianHouseholdIncome',
            (medianHouseholdIncomeTotal / medianHouseholdIncomeSamples))
        self.putStat('medianAge', medianAgeTotal / medianAgeSamples)

        self.putStat('acsCommuteMethods', commuteMethods.crunch())
        self.putStat('acsCommuteTimes', commuteTimes.crunch())
        self.putStat('acsChildren', childrens.crunch())
        self.putStat('acsEarningsBySex', earningsBySexes.crunch())
        self.putStat('acsEducation', educations.crunch())
        self.putStat('acsGeographicMobility', geographicMobilities.crunch())
        self.putStat('acsHouseholdIncome', householdIncomes.crunch())
        self.putStat('acsMaritalStatus', maritalStatuses.crunch())
        self.putStat('acsMaritalStatusBySexAndAge', maritalStatusesBySexAndAge.crunch())
        self.putStat('acsPlaceOfBirth', placeOfBirths.crunch())
        self.putStat('acsTimeLeavingForWork', timeLeavingForWorks.crunch())
        self.putStat('acsMedianAgeBySex', medianAgeBySexes.crunch(True))
        self.putStat('acsMedianHouseholdIncome', medianHouseholdIncomes.crunch(True))
        self.putStat('acsMedianIncomeStats', medianIncomeStats.crunch(True))

class AreaReporter(GeoSimpleReporter):

    description = "Computing geographic area"
    onDemand = True
    precompute = True
    version = 4

    def report(self):
        geo = self.target
        sqMeters = self.getArea(geo)
        self.putStat('areaMeters', sqMeters)
        sqMiles = sqMeters / 2589990
        self.putStat('areaMiles', sqMiles)

    def getArea(self, geo):
        totalArea = 0.0
        if geo['type'] == 'MultiPolygon':
            for poly in geo['coordinates']:
                totalArea += self.getPolyArea(poly[0])
        elif geo['type'] == 'Polygon':
            totalArea += self.getPolyArea(geo['coordinates'][0])
        return totalArea

    def getPolyArea(self, poly):
        longitude, latitude = zip(*poly)
        x, y = self.reproject(latitude, longitude)
        return self.areaOfPolygon(x, y)

    def reproject(self, latitude, longitude):
        """Returns the x & y coordinates in meters using a sinusoidal projection"""
        from math import pi, cos, radians
        earth_radius = 6371009 # in meters
        lat_dist = pi * earth_radius / 180.0

        y = [lat * lat_dist for lat in latitude]
        x = [long * lat_dist * cos(radians(lat))
                    for lat, long in zip(latitude, longitude)]
        return x, y

    def areaOfPolygon(self, x, y):
        """Calculates the area of an arbitrary polygon given its verticies"""
        area = 0.0
        for i in xrange(-1, len(x)-1):
            area += x[i] * (y[i+1] - y[i-1])
        return abs(area) / 2.0

class BiswebReporter(BaseReporter):

    cities = list(NEW_YORK_CITY_SLUGS_SET)
    description = "Contacting NYC Department of Buildings for building data"
    expires = datetime.timedelta(days=31)
    onDemand = True
    precompute = True
    supports = 'property'
    version = 4

    def report(self):
        buildingInfo = _BiswebCrawler.getBuildingInfo(self.target)
        # TODO: if we aren't getting a result, maybe we need to store that so
        # we don't just keep trying...
        if buildingInfo:
            buildingTypePair = buildingInfo.getBuildingType()
            if buildingTypePair:
                (buildingTypeShort, buildingType) = buildingTypePair

                self.putStat('buildingType', buildingType)
                self.putStat('buildingTypeShort', buildingTypeShort)
                self.putStat('biswebLandmarkStatus', buildingInfo.get('LandmarkStatus'))

            elevators = []
            for elevator in reversed(buildingInfo.get('elevators', [])):
                if elevator.get('Device Status') == 'ACTIVE':
                    elevators.append({
                        'id': elevator.get('Device Number'),
                        'status': elevator.get('Device Status'),
                        'capacity': elevator.get('CapacityLbs'),
                        'speed': elevator.get('SpeedFPM'),
                        'floorFrom': elevator.get('FloorFrom'),
                        'floorTo': elevator.get('FloorTo'),
                    })
            self.putStat('elevators', elevators)

class BreezometerReporter(BaseReporter):

    description = "Checking on air quality..."
    expires = datetime.timedelta(days=31)
    onDemand = True
    precompute = False
    supports = 'property'
    version = 1

    def report(self):
        coordinates = self.target.location['coordinates']
        response = api.breezometer({ 'lat': coordinates[1], 'lon': coordinates[0] })
        self.putStat('breezometer', response)

class CensusSf1Reporter(BaseReporter):

    description = "Querying census for demographic data"
    onDemand = True
    precompute = True
    supports = 'property'
    version = 1

    def report(self):
        tigers = TigerLineMongoModel.forAddress(self.target)
        tract = tigers.get('Tract')
        if tract:
            census = tract.getCensusSf1()

            if census:
                self.putStat('censusSample', tract.NAME10)

                population = int(census.data['POP100'])
                self.putStat('censusPopulation', population)

                areaLand = float(census.data['AREALAND']) # squaremeters
                areaLandMiles = areaLand / 2589990. # squaremiles
                if areaLand:
                    self.putStat('censusPopulationDensity', population / areaLandMiles)

                self.putStat('censusHouseholdSizeByType', census.getHouseholdSizeByType())
                self.putStat('censusAgeBySex', census.getAgeBySex())

class CensusSf1CombinerReporter(GeoSimpleReporter):

    description = "Querying census for demographic data"
    onDemand = False
    precompute = True
    version = 1

    def report(self):
        query = {
            'location': {
                '$geoIntersects': {
                    '$geometry': self.target,
                },
            },
            'SUMLEV': "080",
        }

        householdSizeByTypes = Sf1TableSummer()
        agesBySexes = Sf1TableSummer()

        for sample in CensusSf1MongoModel.queryIter(query):
            householdSizeByTypes.add(sample.getHouseholdSizeByType())
            agesBySexes.add(sample.getAgeBySex())

        self.putStat('censusHouseholdSizeByType', householdSizeByTypes.crunch())
        self.putStat('censusAgeBySex', agesBySexes.crunch())

class ChicagoFootprintReporter(BaseReporter):

    #cities = ['chicago-il']
    cities = ['chicago-cook-county-il']
    description = "Fetching property info from the city of Chicago"
    onDemand = True
    precompute = True
    supports = 'property'
    version = 2

    def report(self):
        buildingInfo = ChicagoBuildingFootprint\
            .queryFirst({'addr': self.target.addr})

        if buildingInfo:
            floorCount = buildingInfo['STORIES']
            sqft = buildingInfo['BLDGSQFO']
            buildYear = buildingInfo['YEARBUILT']
            footprint = buildingInfo['geo']
            unitCount = buildingInfo['NOOFUNIT']
            condition = buildingInfo.get('BLDGCONDI')

            if floorCount != '0':
                self.putStat('floorCount', int(floorCount))
            if buildYear != '0':
                self.putStat('buildYear', int(buildYear))
            if unitCount != '0':
                self.putStat('unitCount', int(unitCount))
            if sqft != '0':
                self.putStat('buildingSqft', int(float(sqft)))
            if condition:
                self.putStat('buildingCondition', condition)
            self.putStat('buildingFootprint', footprint)

class CitibikeReporter(MongoGeoReporter):

    cities = ['manhattan-ny', 'brooklyn-ny']
    description = "Checking for citibike stations"
    supports = 'property'

    distanceClass = 'area'
    modelCls = CitibikeStation
    putCount = True
    putNearest = True
    putResults = False
    statName = 'citibike'

class CityAreasReporter(BaseReporter):

    description = "Checking for local neighborhoods"
    onDemand = True
    supports = 'city'
    version = 21

    def report(self):
        self.putStat('areas', Area.forCity(self.target.slug))

class CityPropertiesReporter(BaseReporter):

    description = "Checking for properties in city"
    expires = datetime.timedelta(days=7)
    onDemand = True
    supports = 'city'
    version = 22

    def report(self):
        query = Property.query()\
            .filter(Property.city == self.target.slug)\
            .order(-Property.rank)
        pageInfo = rutil.ndbPaginate(1, 20, query, countLimit=10000)
        self.putStat('properties', pageInfo)

class ComplaintReporter(BaseReporter):

    cities = list(NEW_YORK_CITY_SLUGS_SET)
    description = 'Fetching complaints from the HPD'
    expires = datetime.timedelta(days=10)
    onDemand = True
    precompute = True
    supports = 'property'
    version = 1

    def report(self):
        # if hpdId exists, complaints can exist
        hpdId = NycHpdId.forCaddr(self.target.caddr)
        canExist = hpdId is not None

        self.putStat('complaintsExist', canExist)
        if canExist:
            # fetch complaints
            complaints = NycHpdComplaintModel.forHpdId(hpdId)
            complaints = sorted(complaints, key=lambda x: x.ReceivedDate, reverse=True)

            # fetch violations
            violations = NycHpdViolationModel.forHpdId(hpdId)
            violations = sorted(violations, key=lambda x: x.InspectionDate, reverse=True)

            # get total number of problems & unresolved problems
            totalProblems = 0
            totalOpenProblems = 0
            if complaints:
                for complaint in complaints:
                    totalProblems += complaint.getProblemCount()
                    totalOpenProblems += complaint.getOpenProblemCount()

            # get total number of violations & unresolved violations
            totalViolations = len(violations)
            totalOpenViolations = 0
            if violations:
                for violation in violations:
                    if violation.getStatus() == "Open":
                        totalOpenViolations += 1

            self.putStat('complaints', complaints)
            self.putStat('totalProblems', totalProblems)
            self.putStat('totalOpenProblems', totalOpenProblems)
            self.putStat('violations', violations)
            self.putStat('totalViolations', totalViolations)
            self.putStat('totalOpenViolations', totalOpenViolations)

class ElevatorSimulationReporter(BaseReporter):

    cities = list(NEW_YORK_CITY_SLUGS_SET)
    description = "Checking public records for elevator data"
    onDemand = True
    precompute = True
    requireReporters = ['HpdReporter', 'BiswebReporter']
    requireStats = ['elevators', 'floorCount', 'unitCount']
    supports = 'property'
    version = 1

    def report(self, elevators, floorCount, unitCount):
        if elevators:
            from rentenna3 import elevatorSimulator
            stats = elevatorSimulator.getElevatorTimes(
                floorCount, 500, unitCount, len(elevators)
            )

            upByFloor = stats['up']
            downByFloor = stats['down']
            self.putStat('elevatorTimeUpByFloor', upByFloor)
            self.putStat('elevatorTimeDownByFloor', downByFloor)

            self.putStat('elevatorWaitTimeUp',
                sum(s[0] for s in upByFloor) / len(upByFloor)
            )
            self.putStat('elevatorWaitTimeDown',
                sum(s[0] for s in downByFloor) / len(downByFloor)
            )
            self.putStat('elevatorTravelTimeUp',
                sum(s[1] for s in upByFloor) / len(upByFloor)
            )
            self.putStat('elevatorTravelTimeDown',
                sum(s[1] for s in downByFloor) / len(downByFloor)
            )
        else:
            self.putStat('elevatorWaitTimeUp', None)
            self.putStat('elevatorWaitTimeDown', None)
            self.putStat('elevatorTravelTimeUp', None)
            self.putStat('elevatorTravelTimeDown', None)
            self.putStat('elevatorTimeUpByFloor', None)
            self.putStat('elevatorTimeDownByFloor', None)

class FloodZoneReporter(BaseReporter):

    cities = list(NEW_YORK_CITY_SLUGS_SET)
    description = "Computing flood zone"
    onDemand = True
    precompute = True
    supports = 'property'
    version = 2

    def report(self):
        floodZone = FloodZoneMongoModel.forAddress(self.target)
        if floodZone:
            self.putStat('floodZoneName', floodZone.Zone)

class HpdReporter(BaseReporter):

    cities = list(NEW_YORK_CITY_SLUGS_SET)
    description = "Contacting NYC Housing Department for building info"
    onDemand = True
    precompute = True
    supports = 'property'
    version = 1

    def report(self):
        buildingInfo = None
        hpdId = NycHpdId.forCaddr(self.target.caddr)
        if hpdId:
            buildingInfo = NycHpdBuildingInfo.queryFirst({'BuildingID': hpdId})
            unitCount = 0
            classAUnits = buildingInfo.get('LegalClassA')
            if classAUnits:
                unitCount += int(classAUnits)
            classBUnits = buildingInfo.get('LegalClassB')
            if classBUnits:
                unitCount += int(classBUnits)
            if unitCount > 0:
                self.putStat('unitCount', unitCount)

            floorCount = buildingInfo.get('LegalStories')
            if floorCount:
                self.putStat('floorCount', int(floorCount))

class InsurentBuildingReporter(BaseReporter):

    cities = list(NEW_YORK_CITY_SLUGS_SET) + ['northern-nj', 'chicago-il', 'boston-ma']
    description = "Checking the Insurent Database"
    onDemand = True
    precompute = True
    supports = 'property'
    version = 167 #for fun ;)

    def report(self):
        record = InsurentBuildingModel.forAddress(self.target)
        self.putStat('isInsurent', record is not None)

class NearbyPropertyReporter(MongoGeoReporter):

    description = "Finding nearby buildings"
    supports = 'property'

    distanceClass = 'area'
    limit = 100
    modelCls = Address
    statName = 'nearbyProperties'

    def getFilter(self):
        return {
            'isPreferred': True,
        }

    def processResults(self, results, queryInfo):
        properties = [
            property
            for property
            in results
            if property.slug != self.target['target'].slug
        ]
        if len(properties) > 16:
            nearby = random.sample(properties, 16)
        else:
            nearby = properties

        return nearby

class NearestIntersectionReporter(MongoGeoReporter):

    cities = ['manhattan-ny']
    description = "Checking for nearest intersection"
    onDemand = True
    precompute = True
    supports = 'property'

    distanceClass = 'area'
    limit = 1
    modelCls = Intersection
    putCount = False
    putNearest = True
    putResults = False
    statName = 'intersection'

class NeighbhorhoodReporter(BaseReporter):

    description = "Locating Neighborhood"
    onDemand = True
    precompute = True
    supports = 'property'
    version = 5

    def report(self):
        areas = list(self.target.getAreas())
        self.putStat('neighborhoods', areas)
        if areas:
            bestArea = max(areas, key=lambda x: x.getDepth())
            self.putStat('neighborhood', bestArea)
        else:
            self.putStat('neighborhood', None)

class NeighbhorhoodPropertiesReporter(BaseReporter):

    description = "Checking for properties in neighborhood"
    expires = datetime.timedelta(days=7)
    onDemand = True
    supports = 'neighborhood'
    version = 22

    def report(self):
        query = Property.query()\
            .filter(Property.lists == ("area:%s" % self.target.slug))\
            .order(-Property.rank)
        pageInfo = rutil.ndbPaginate(1, 20, query, countLimit=10000)
        self.putStat('properties', pageInfo)

class Nyc311Reporter(MongoGeoReporter):

    __abstract__ = True

    cities = list(NEW_YORK_CITY_SLUGS_SET)
    expires = datetime.timedelta(days=10)
    onDemand = True
    precompute = True
    supports = [
        'neighborhood',
        'property',
        'zipcode',
    ]
    version = 100

    countOnly = True
    complaintTypes = None
    distanceClass = 'nearby'
    modelCls = Nyc311CallModel
    statName = None

    def getFilter(self):
        lastPeriod = datetime.datetime.now() - datetime.timedelta(days=365)
        return {
            'complaint_type': {
                '$in': self.complaintTypes
            },
            'created_date': {
                '$gte': lastPeriod
            }
        }

class Nyc311FilthReporter(Nyc311Reporter):

    complaintTypes = Nyc311CallModel.FILTH_TYPES
    description = "Checking for nearby filth complaints"
    statName = "filthComplaints"

class Nyc311NoiseReporter(Nyc311Reporter):

    complaintTypes = Nyc311CallModel.NOISE_TYPES
    description = "Checking for nearby noise complaints"
    statName = "noiseComplaints"

class Nyc311RodentReporter(Nyc311Reporter):

    complaintTypes = ['Rodent']
    description = "Checking for nearby rodent complaints"
    statName = "rodentComplaints"

class Nyc311StreetReporter(Nyc311Reporter):

    complaintTypes = Nyc311CallModel.STREET_TYPES
    description = "Checking for nearby street complaints"
    statName = "streetComplaints"

class NycDobBuildingJobs(BaseReporter):

    cities = list(NEW_YORK_CITY_SLUGS_SET)
    description = "Checking for construction history in this building"
    expires = datetime.timedelta(days=10)
    onDemand = True
    precompute = True
    supports = 'property'
    version = 100

    def report(self):
        jobs = NycDobJob.query({
            'caddr': self.target.caddr
        }, fields=[
            'Approved',
            'ExpirationDate',
            'FilingDate',
            'FullyPaid',
            'Job',
            'JobDescription',
            'JobStartDate',
            'JobStatus',
            'JobType',
            'PermitStatus',
            'PermitSubtype',
            'PermitType',

            'Boiler',
            'CurbCut',
            'FireAlarm',
            'FireSuppression',
            'FuelBurning',
            'FuelStorage',
            'HorizontalEnlrgmt',
            'Mechanical',
            'Plumbing',
            'Sprinkler',
            'Standpipe',
            'VerticalEnlrgmt',
        ])
        jobs = sorted(jobs, key=lambda x: x.getDate(), reverse=True)
        self.putStat('buildingJobs', jobs)

class NycDobNearbyJobReporter(MongoGeoReporter):

    __abstract__ = True

    cities = list(NEW_YORK_CITY_SLUGS_SET)
    expires = datetime.timedelta(days=10)
    onDemand = True
    precompute = True
    supports = [
        'neighborhood',
        'property',
        'zipcode',
    ]
    version = 15

    # countOnly = True
    distanceClass = 'reasonableTravel'
    days = 365
    limit = None
    modelCls = NycDobJob
    putCount = True
    putNearest = False
    putResults = False

    jobTypes = None

    def getFilter(self):
        lastYear = datetime.datetime.now() - datetime.timedelta(days=self.days)
        if len(self.jobTypes) == 1:
            jobTypeFilter = self.jobTypes[0]
        else:
            jobTypeFilter = {'$in': self.jobTypes}
        return {
            'JobType': jobTypeFilter,
            'FullyPaid': {'$gt': lastYear}
        }

class NycDobNearbyJobDemolitionReporter(NycDobNearbyJobReporter):

    description = "Searching for nearby scaffolds"
    jobTypes = ['DM']
    statName = "demolitions"

class NycDobNearbyJobNewBuildingReporter(NycDobNearbyJobReporter):

    description = "Searching for nearby scaffolds"
    jobTypes = ['NB']
    statName = "newBuildings"

class NycDobNearbyJobScaffoldReporter(NycDobNearbyJobReporter):

    description = "Searching for nearby scaffolds"
    jobTypes = ['SF', 'SH']
    statName = "scaffolds"
    days = 90

class NycSubwayEntrancesReporter(MongoGeoReporter):

    cities = list(NEW_YORK_CITY_SLUGS_SET)
    description = "Contacting MTA for nearby subway entrances"
    onDemand = True
    precompute = True
    supports = 'property'
    version = 78

    distanceClass = 'reasonableTravel'
    limit = None
    modelCls = NycSubwayEntranceMongoModel
    putCount = False
    putNearest = False
    putResults = True
    statName = 'subwayEntrances'

class NycTaxiReporter(BaseReporter):

    cities = list(NEW_YORK_CITY_SLUGS_SET)
    description = "Measuring taxi wait times"
    onDemand = True
    precompute = True
    supports = 'property'
    version = 111

    SAMPLE_PROPORTION = 3223086. / 13971118.
    SAMPLE_DAYS = 31.

    def report(self):
        nearby = NycTaxiIntersection.getNearest(
            self.target.location,
            self.target.getCity().getDistance('area')['distance'],
            limit=8
        )
        for intersection in nearby:
            intersection.distance = rutil.distance(
                self.target.location,
                intersection['geo'],
            )
            intersection.waitTime = self.getWaitTime(
                self.scaleSample(intersection.get('passEmpties', 0)) / 24,
                self.scaleSample(intersection.get('pickups', 0)) / 24,
            )
            # people walk at 2.682 meters per second?
            intersection.cost = 2.682 * intersection.distance + intersection.waitTime

        if nearby:
            best = sorted(nearby, key=lambda x: x['cost'])[0]

            pickups = self.scaleSample(best.get('pickups', 0)) / 24
            dropoffs = self.scaleSample(best.get('dropoffs', 0)) / 24
            passEmpties = self.scaleSample(best.get('passEmpties', 0)) / 24
            waitTime = self.getWaitTime(passEmpties, pickups)

            pickupsH = []
            dropoffsH = []
            passEmptiesH = []
            waitTimesH = []
            for i in range(0, 24):
                pickupsI = self.scaleSample(intersection.pickupsH.get('%02d' % i, 0))
                dropoffsI = self.scaleSample(intersection.dropoffsH.get('%02d' % i, 0))
                passEmptiesI = self.scaleSample(intersection.passEmptiesH.get('%02d' % i, 0))
                pickupsH.append(pickupsI)
                dropoffsH.append(dropoffsI)
                passEmptiesH.append(passEmptiesI)
                waitTimesH.append(self.getWaitTime(passEmptiesI, pickupsI))

            intersection = Intersection.queryFirst({'osm': best['osm']})

            self.putStat('taxiPickups', pickups)
            self.putStat('taxiDropoffs', dropoffs)
            self.putStat('taxiPassEmpties', passEmpties)
            self.putStat('taxiWaitTime', waitTime)
            self.putStat('taxiPickupsByHour', pickupsH)
            self.putStat('taxiDropoffsByHour', dropoffsH)
            self.putStat('taxiPassEmptiesByHour', passEmptiesH)
            self.putStat('taxiWaitTimeByHour', waitTimesH)
            self.putStat('taxiBestIntersection', intersection)

    def getWaitTime(self, passEmpties, pickups):
        # get the wait time, given the per-hour values
        opportunites = passEmpties
        if opportunites <= 1:
            opportunites = 1
        return 2 * min(
            int(math.ceil(60. * 60. / opportunites)),
            600,
        )

    def scaleSample(self, n):
        return int(math.ceil(n / self.SAMPLE_PROPORTION / self.SAMPLE_DAYS))

class NycTreeReporter(MongoGeoReporter):

    cities = list(NEW_YORK_CITY_SLUGS_SET)
    cities.remove('staten-island-ny')

    description = "Counting local street trees"
    onDemand = True
    precompute = True
    supports = [
        'neighborhood',
        'property',
        'zipcode',
    ]
    version = 10

    countOnly = True
    distanceClass = 'nearby'
    modelCls = StreetTree
    statName = 'streetTrees'

class NypdCrimeReporter(MongoGeoReporter):

    cities = list(NEW_YORK_CITY_SLUGS_SET)
    description = "Contacting NYPD for crime stats"
    expires = datetime.timedelta(days=10)
    onDemand = True
    precompute = True
    supports = ['neighborhood', 'zipcode']
    version = 8

    countOnly = True
    modelCls = NypdCrimeMongoModel
    statName = 'nypdCrimes'

    def getFilter(self):
        lastYear = datetime.datetime.now() - datetime.timedelta(days=365)
        return {
            'crime': {
                '$ne': "GRAND LARCENY",
            },
            'date': {
                '$gte': lastYear,
            }
        }

class NypdCrimeReporterWithBreakdown(NypdCrimeReporter):

    NYPD_FELONY_MAP = {
        # 'GRAND LARCENY': 'Grand Larceny',
        'BURGLARY': 'Burglary',
        'ROBBERY': 'Robbery',
        'FELONY ASSAULT': 'Assault',
        'GRAND LARCENY OF MOTOR VEHICLE': 'Grand Theft Auto',
        'RAPE': 'Rape',
        'MURDER': 'Murder',
    }

    supports = 'property'

    countOnly = False
    distanceClass = 'area'

    def processResults(self, results, queryInfo):
        output = {}

        output['count'] = len(results)

        typeCounter = collections.Counter()
        for crime in results:
            typeCounter[self.NYPD_FELONY_MAP[crime.crime]] += crime.count

        output['byType'] = sorted(
            typeCounter.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        return output

class NyVoterReporter(BaseReporter):

    description = "Checking Voter Registrations"
    onDemand = True
    precompute = True
    states = ['NY']
    supports = 'property'
    version = 13

    def report(self):
        votersInBuilding = self.countVoters(NyVoter.forAddress(self.target))
        self.putStat('votersInBuilding', votersInBuilding)
        self.putStat('votersInBuildingPercent', self.computePolitics(votersInBuilding))

        distance = self.target.getCity().getDistance('nearby')['distance']
        votersNearby = self.countVoters(
            NyVoter.getNearest(
                self.target.location,
                distance,
                fields=['ENR', 'OTH', 'S']
            )
        )
        self.putStat('voters', votersNearby)
        self.putStat('votersPercent', self.computePolitics(votersNearby))

    def computePolitics(self, voters):
        if voters:
            keys = sorted(voters.keys(), key=lambda x: voters[x])
            maxKey = keys[-1]
            total = sum(voters.values())
            return {
                'maxKey': maxKey,
                'maxPercent': voters[maxKey] / float(total),
                'breakdown': voters.items(),
            }

    def countVoters(self, voters):
        counter = collections.Counter()
        for voter in voters:
            if voter.S == 'ACTIVE' and voter.ENR != 'BLK':
                counter[voter.getParty()] += 1
        return dict(counter)

class NyVoterRegionReporter(NyVoterReporter):

    # TODO: could do on city level too

    supports = [
        'neighborhood',
        'zipcode',
    ]

    def report(self):
        voters = self.countVoters()
        if voters:
            politics = self.computePolitics(voters)
            self.putStat('voters', voters)
            self.putStat('votersPercent', politics)

    def prepareArea(self, target):
        return {
            'cls': AreaVoterCounts,
            'slug': target.slug,
        }

    def prepareZipCode(self, target):
        return {
            'cls': ZipcodeVoterCounts,
            'slug': target.slug,
        }

    def countVoters(self):
        counts = self.target['cls'].queryFirst({
            'area': self.target['slug'],
        })
        if counts:
            countsDict = counts.toDict()
            return countsDict

class ObiAvmReporter(BaseReporter):

    description = "Estimating property values"
    minimal = True
    onDemand = True
    precompute = True
    supports = 'property'
    version = 3

    def report(self):
        obiAvmResponse = api.obiAvm(
            self.target.addrStreet,
            self.target.addrCity,
            self.target.addrState,
            self.target.addrZip,
            self.target.get('unitValue', None),
        )
        
        logging.info(obiAvmResponse)
        if obiAvmResponse:
            logging.info(obiAvmResponse.highValue)
            self.putStat('obiAvm', obiAvmResponse)

class ObiCommunityReporter(BaseReporter):

    description = "Researching community information"
    minimal = True
    onDemand = True
    precompute = True
    supports = 'property'
    version = 2

    def report(self):
        obiCommunityResponse = api.obiCommunity(
            self.target.location,
        )

        zipcode = self.target['addrZip']
        if zipcode:
            obiCommunityResponseForZipcode = api.obiCommunityById(
                'ZI%s' % zipcode
            )
            self.putStat('obiCommunityForAddrZip', obiCommunityResponseForZipcode)
        if obiCommunityResponse:
            self.putStat('obiCommunity', obiCommunityResponse)

class ObiCommunityKnownIdReporter(BaseReporter):

    description = "Researching community information"
    minimal = True
    onDemand = True
    precompute = True
    supports = [
        'city',
        'neighborhood',
        'zipcode',
    ]
    version = 2

    def report(self):
        obiCommunityResponse = api.obiCommunityById(
            self.target,
        )
        self.putStat('obiCommunity', obiCommunityResponse)

    def prepareArea(self, target):
        return target['obId']

    def prepareCity(self, target):
        return target['obId']

    def prepareZipCode(self, target):
        return target['obId']

class ObiRecentSalesReporter(BaseReporter):

    description = "Check public records for recent sales"
    expires = datetime.timedelta(days=16)
    onDemand = True
    precompute = True
    supports = 'property'
    version = 13

    def report(self):
        city = self.target.getCity()
        if city:
            obiSales = sorted(api.obiSales(
                city.getDistance('area')['distance'],
                self.target.location,
            ), key=lambda x: x.get('distance'))
            self.putStat('obiNearbySales', obiSales)

class PolicePrecinctReporter(BaseReporter):

    cities = list(NEW_YORK_CITY_SLUGS_SET)
    description = "Contacting NYPD for police station locations"
    onDemand = True
    precompute = True
    supports = 'property'
    version = 1

    def report(self):
        nycPolicePrecinct = NycPolicePrecinctMongoModel.forAddress(self.target)
        if nycPolicePrecinct:
            self.putStat('policePrecinctName', nycPolicePrecinct.Precinct)
            self.putStat('policePrecinctGeo', nycPolicePrecinct.geo)

class SchoolDistrictReporter(BaseReporter):

    description = "Researching school district"
    onDemand = True
    precompute = True
    supports = [
        'city',
        'neighborhood',
        'property',
        'zipcode',
    ]
    version = 3

    def report(self):
        queryMethod = getattr(SchoolDistrict, self.target['method'])
        # schoolDistrict = queryMethod(self.target['target'])
        # if schoolDistrict:
        #     self.putStat('schoolDistrict', schoolDistrict)

        schoolDistricts = queryMethod(self.target['target'])
        if schoolDistricts:
            self.putStat('schoolDistricts', schoolDistricts)


    def prepareArea(self, target):
        return {
            'target': target,
            'method': 'forRegion',
        }

    def prepareAddress(self, target):
        return {
            'target': target,
            'method': 'forAddress',
        }

    def prepareCity(self, target):
        return {
            'target': target,
            'method': 'forCity',
        }


    def prepareZipCode(self, target):
        return {
            'target': target,
            'method': 'forRegion',
        }

class SchoolsReporter(BaseReporter):

    description = "Finding nearby schools"
    onDemand = True
    precompute = True
    requireReporters = ['SchoolDistrictReporter']
    requireStats = ['schoolDistricts']
    supports = 'property'
    version = 4

    def report(self, schoolDistricts):
        districtIds = [schoolDistrict.get('obId') for schoolDistrict in schoolDistricts]
        print districtIds
        elems = School.forAddress(self.target, districtIds, 'e', skipGeo=True)
        middles = School.forAddress(self.target, districtIds, 'm', skipGeo=True)
        highs = School.forAddress(self.target, districtIds, 'h', skipGeo=True)

        self.putStat('elementarySchools', elems)
        self.putStat('middleSchools', middles)
        self.putStat('highSchools', highs)

class SocialBuzzReporter(BaseReporter):

    description = "Social Buzz"
    onDemand = True
    precompute = False
    # requireReporters = None
    #requireStats = ['socialPhotoSlug']
    supports = [
        'property', 
        'neighborhood',
        'city',
    ]
    version = 1

    def report(self): 
        photoSlug = None
        photoDomain = None
        queryMethod = getattr(SocialCityPhoto, self.target['method'])
        if queryMethod:
            cityPhotos = queryMethod(self.target['target'])
            if cityPhotos:
                photoSlug = cityPhotos[0].slug
                photoDomain = cityPhotos[0].domain

        self.putStat('socialPhotoSlug', photoSlug)
        self.putStat('socialPhotoDomain', photoDomain)

    def prepareArea(self, target):
        return {
            'target': target,
            'method': 'forRegion',
        }

    def prepareAddress(self, target):
        return {
            'target': target,
            'method': 'forAddress',
        }

    def prepareCity(self, target):
        return {
            'target': target,
            'method': 'forCity',
        }


class StreeteasyBuildingNameLookup(BaseReporter):

    cities = list(NEW_YORK_CITY_SLUGS_SET)
    description = "Looking up building name"
    onDemand = True
    precompute = True
    supports = 'property'
    version = 2

    def report(self):
        streeteasyBuilding = StreeteasyBuilding.forAddress(self.target)
        if streeteasyBuilding:
            name = streeteasyBuilding['name']
            if not streeteasyBuilding['fullAddress'].startswith(name):
                self.putStat('buildingName', name)

class YelpReporter(BaseReporter):

    __abstract__ = True
    expires = datetime.timedelta(hours=48)
    onDemand = True
    precompute = False
    supports = [
        'city',
        'neighborhood',
        'property',
        'zipcode',
    ]
    version = 15

    statName = None
    yelpCategory = None

    def report(self):
        from rentenna3 import api

        query = {
            'category_filter': self.yelpCategory,
        }
        query.update(self.target['geo'])

        location = self.target['location']

        result = api.yelp('search', query)
        businesses = []
        for business in result['businesses']:
            item = {
                'name': business['name'],
                'id': business['id'],
                'rating': business['rating'],
                'review_count': business['review_count'],
                'rating_img_url_large': business['rating_img_url_large'].replace('http:', 'https:'),
            }
            image = business.get('image_url')
            if image:
                item['image_url'] = image.replace('ms.jpg', 'l.jpg').replace('http:', 'https:')

                if 'coordinate' in business['location']:
                    coordinates = business['location']['coordinate']
                    item['geo'] = {
                        'type': "Point",
                        'coordinates': [
                            coordinates['longitude'],
                            coordinates['latitude'],
                        ]
                    }
                    if location:
                        item['distance'] = rutil.distance(
                            item['geo'],
                            location,
                        )
                    businesses.append(item)

        self.putStat(self.statName, businesses)

    def prepareAddress(self, target):
        location = "%s,%s" % (
            target.location['coordinates'][1],
            target.location['coordinates'][0],
        )
        return {
            'location': target.location,
            'geo': {'ll': location},
        }

    def prepareArea(self, target):
        return self.prepareRegion(target)

    def prepareCity(self, target):
        return self.prepareRegion(target)

    def prepareZipCode(self, target):
        return self.prepareRegion(target)

    def prepareRegion(self, target):
        from rentenna3 import util
        geoSimple = target.getGeoSimple()
        bbox = util.getBbox(geoSimple)
        return {
            'location': None,
            'geo': {
                'bounds': "%s,%s|%s,%s" % (
                    bbox[2], bbox[0],
                    bbox[3], bbox[1],
                )
            },
        }

class YelpBarReporter(YelpReporter):

    yelpCategory = 'bars'
    statName = 'yelpBars'
    description = "Searching for local bars"

class YelpBeautyReporter(YelpReporter):

    yelpCategory = 'beautysvc'
    statName = 'yelpBeauty'
    description = "Searching for local beauty salons"

class YelpCoffeeReporter(YelpReporter):

    yelpCategory = 'coffee'
    statName = 'yelpCoffee'
    description = "Searching for local coffee shops"

class YelpGroceryReporter(YelpReporter):

    yelpCategory = 'grocery'
    statName = 'yelpGrocery'
    description = "Searching for local grocery stores"

class YelpGymReporter(YelpReporter):

    yelpCategory = 'gyms'
    statName = 'yelpGyms'
    description = "Searching for local gyms"

class YelpPetReporter(YelpReporter):

    yelpCategory = 'pets'
    statName = 'yelpPets'
    description = "Searching for local pet stores"

class YelpRestaurantReporter(YelpReporter):

    yelpCategory = 'restaurants'
    statName = 'yelpRestaurants'
    description = "Searching for local restaurants"

class ZipPropertiesReporter(BaseReporter):

    description = "Checking for properties in zip code"
    expires = datetime.timedelta(days=7)
    onDemand = True
    supports = 'zipcode'
    version = 22

    def report(self):
        query = Property.query()\
            .filter(Property.lists == ("zip:%s" % self.target.slug))\
            .order(-Property.rank)
        pageInfo = rutil.ndbPaginate(1, 20, query, countLimit=10000)
        self.putStat('properties', pageInfo)

class _BiswebCrawler(object):

    BASE_URL = "http://a810-bisweb.nyc.gov/bisweb/"

    BORO_MAP = {
        'manhattan': 1,
        'bronx': 2,
        'brooklyn': 3,
        'queens': 4,
        'staten-island': 5,
        'manhattan-ny': 1,
        'bronx-ny': 2,
        'brooklyn-ny': 3,
        'queens-ny': 4,
        'staten-island-ny': 5,
    }

    @classmethod
    def getBuildingInfo(cls, address):
        bin = NycDobBin.forCaddr(address.caddr)

        if bin:
            crawler = _BiswebCrawler(bin=bin)
        else:
            crawler = _BiswebCrawler(
                address=address.addrStreet,
                city=address.city,
            )

        buildingInfo = crawler.crawl()

        if buildingInfo.get('bin'):
            NycDobBin.update(
                {'caddr': address.caddr},
                {
                    '$set': {
                        'dobBin': buildingInfo['bin'],
                        'caddr': address.caddr,
                        'addr': address.addr,
                        'geo': address.location,
                    }
                }
            )

            NycBiswebBuilding.update(
                {'bin': buildingInfo['bin']},
                buildingInfo,
                upsert=True,
            )

            taskqueue.add(
                url='/background/merge-alternate-addresses/',
                params={
                    'bin': buildingInfo['bin'],
                },
                countdown=5,
                queue_name='default',
            )

            return NycBiswebBuilding(**buildingInfo)

    def __init__(self, bin=None, address=None, city=None):
        # prefer bin, but address is a dict from the mongo db
        if bin:
            self.query = {'bin': bin}
        else:
            streetNumber = address.split(" ")[0]
            streetName = " ".join(address.split(" ")[1:])
            self.query = {
                'houseno': streetNumber,
                'street': streetName,
                'boro': self.BORO_MAP[city]
            }

    def crawl(self):
        data = {}

        # read the root page

        root = CrawlResponse(
            self.BASE_URL + "PropertyProfileOverviewServlet",
            params=self.query
        ).selector
        if root.first("//td[contains(text(), 'NOT FOUND')]"):
            data['NotFound'] = True
        else:
            bin = root.first("//td[starts-with(text(), 'BIN#')]/text()")
            if bin is None:
                data['NotFound'] = True
            else:
                data['bin'] = bin.replace("BIN#", "").replace("&nbsp;", "").strip()
                data['address'] = root.first("//td[@class='maininfo'][1]/text()")

                address2 = root.first("//td[@class='maininfo'][2]/text()").split(" ")
                data['boro'] = " ".join(address2[:-1])
                data['zip'] = address2[-1]

                for kv in root.select("//td[@class='content']/b"):
                    key = kv.first("./text()")
                    if key:
                        value = kv.first("../following-sibling::td[1]/text()")
                        data[util.keyify(key)] = value

                # read the elevator pages

                data['elevators'] = []
                elevatorLink = root.first("//b[text()='Elevator Records']/../@href")
                if elevatorLink:
                    elevatorResponse = CrawlResponse(self.BASE_URL + elevatorLink).selector
                    devicesLinks = elevatorResponse.extractAll("//a[starts-with(@href, 'ElevatorDevicesForRecordServlet')]/@href")
                    for devicesLink in devicesLinks:
                        devicesResponse = CrawlResponse(self.BASE_URL + devicesLink).selector
                        for link in devicesResponse.select("//a[starts-with(@href, 'ElevatorDetailsForDeviceServlet')][text()!='']"):
                            data['elevators'].append({
                                'Device Status': link.first('./../following-sibling::td[1]/text()'),
                                'Device Number': link.first('./text()'),
                            })

                # read the alternate address pages

                data['altAddresses'] = []
                for row in root.select("//center/table[3]/tr[@valign='top']"):
                    street = row.first("./td[@class='content'][1]/text()")
                    numbers = row.first("./td[@class='content'][2]/text()")
                    if street and numbers:
                        addressRange = numbers.split(" - ")
                        if len(addressRange) == 2:
                            data['altAddresses'].append({
                                'low': addressRange[0],
                                'high': addressRange[1],
                                'street': street,
                            })

        return data

    def _grabHeading(self, elevator, response, name):
        el = response.first("//td[contains(text(), '%s: ')]/text()" % name)
        if el:
            elevator[name ] = el.replace("%s: " % name, "")
