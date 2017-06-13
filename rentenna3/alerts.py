from rentenna3 import api
from rentenna3.base import AlertReporter
from rentenna3.data.cities import NEW_YORK_CITY_SLUGS_SET
from rentenna3.email import *
from rentenna3.models import *
from web import config

class AirQualityAlertReporter(AlertReporter):

    schedule = 'Monday'
    supports = 'property'
    template = AlertForAirQuality

    def report(self, **kwargs):
        alert = self.subscription
        address = self.address

        coordinates = address.location['coordinates']

        properties = {}
        lastWeek = self.getValidBreezometerDataForToday(
            coordinates, 
            datetime.datetime.now() - datetime.timedelta(days=7),
        )
        thisWeek = self.getValidBreezometerDataForToday(
            coordinates, 
            datetime.datetime.now(),
        )

        if lastWeek and thisWeek:
            lastWeek['datetime'] = self.normalDateFormat(lastWeek['datetime'])
            thisWeek['datetime'] = self.normalDateFormat(thisWeek['datetime'])

            if lastWeek['breezometer_aqi'] != thisWeek['breezometer_aqi']:
                return {
                    'thisWeek': thisWeek,
                    'lastWeek': lastWeek,
                }

    def normalDateFormat(self, dateTime):
        return datetime.datetime.strptime(dateTime, "%Y-%m-%dT%H:%M:%S").strftime("%m/%d/%y")

    def encodeBreezometerDateWithHour(self, datetime, hour):
        return datetime.replace(hour=hour).strftime("%Y-%m-%dT%H:%M:%S")

    def getValidBreezometerDataForToday(self, coordinates, dateTime):
        for hour in [12, 15]:
            breezometerData = api.breezometer(
                args = {
                    'lat': coordinates[1], 
                    'lon': coordinates[0],
                },
                rawArgs = {
                    'datetime': self.encodeBreezometerDateWithHour(dateTime, hour),
                },
            )

            if breezometerData.get('data_valid'):
                return breezometerData

class Nyc311AlertReporter(AlertReporter):

    cities = list(NEW_YORK_CITY_SLUGS_SET)
    schedule = 'Friday'
    supports = 'property'
    template = AlertFor311

    def report(self, **kwargs):
        alert = self.subscription
        address = self.address
        distancePreference = 'area'

        targetCities = list(NEW_YORK_CITY_SLUGS_SET)
        if address.city in targetCities:
            city = address.getCity()
            distance = city.getDistance(distancePreference)['distance']
            filth = Nyc311CallModel.getNearestFilthComplaints(
                address.location, 
                distance, 
                daysBack=7,
                count=True
            )
            noise = Nyc311CallModel.getNearestNoiseComplaints(
                address.location, 
                distance, 
                daysBack=7,
                count=True
            )
            street = Nyc311CallModel.getNearestStreetComplaints(
                address.location, 
                distance, 
                daysBack=7,
                count=True
            )
            rodent = Nyc311CallModel.getNearestRodentComplaints(
                address.location, 
                distance, 
                daysBack=7,
                count=True
            )
            if filth or noise or street or rodent:
                return {
                    'filth': filth,
                    'noise': noise,
                    'street': street,
                    'rodent': rodent,
                    'distance': city.getDistance(distancePreference)['description'],
                }

class ValueAlertReporter(AlertReporter):

    schedule = 'Wednesday'
    supports = 'property'
    template = AlertForValue

    def report(self, **kwargs):
        alert = self.subscription
        address = self.address

        obiAvm = api.obiAvm(
            address.addrStreet, 
            address.addrCity, 
            address.addrState, 
            address.addrZip,
            address.get('unitValue', None),
        )
        hasAvm = (obiAvm and obiAvm.indicatedValue)
        
        if hasAvm:
            return {
                'avm': obiAvm,
            }

class NearbySalesAlertReporter(AlertReporter):

    schedule = 'Thursday'
    supports = 'property'
    template = AlertForNearbySales

    def report(self, **kwargs):
        alert = self.subscription
        address = self.address
        
        obiSales = sorted(api.obiSales(
            address.getCity().getDistance('area')['distance'],
            address.location,
            7
        ))
        hasSales = (len(obiSales) > 0)
        
        if hasSales:
            return {
                'sales': obiSales,
            }