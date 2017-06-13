import flask
import re
import string

from unittest import TestCase

from web import rutil
from web import memcache
from rentenna3 import api
from rentenna3 import util
from rentenna3.models import *

ADDRESS_COMPONENT_REGEXES = [
    r'^(?P<streetNumber>[0-9\-]+[A-Z]*) +(?P<street>[^,]+), *(?P<city>[^,]+), *(?P<state>[A-Z]{2}),? *(?P<zip>[0-9]{5})(\-(?P<plus4>[0-9]{4}))?(, *(?P<country>.+))?$',
    r'^(?P<streetNumber>[0-9\-]+[A-Z]*) +(?P<street>[^,]+), *(?P<zip>[0-9]{5})(\-(?P<plus4>[0-9]{4}))?(, *(?P<country>.+))?$',
    r'^(?P<streetNumber>[0-9\-]+[A-Z]*) +(?P<street>[^,]+), *(?P<city>[^,]+), *(?P<state>[A-Z]{2})(, *(?P<country>.+))?$',
    r'^(?P<streetNumber>[0-9\-]+[A-Z]*) +(?P<street>[^,]+), *(?P<state>[A-Z]{2})$',
    r'^(?P<streetNumber>[0-9\-]+[A-Z]*) +(?P<street>[^,]+), *(?P<city>[^,]+)$',
    r'^(?P<streetNumber>[0-9\-]+[A-Z]*) +(?P<street>[^,]+)$',
]

CITY_COMPONENT_REGEXES = [
    r'^(?P<zip>[0-9]{5})(\-(?P<plus4>[0-9]{4}))?$',
    r'^(?P<city>[^,]+), *(?P<state>[A-Z]{2}),? *(?P<zip>[0-9]{5})(\-(?P<plus4>[0-9]{4}))?(, *(?P<country>.+))?$',
    r'^(?P<city>[^,]+), *(?P<state>[A-Z]{2})(, *(?P<country>.+))?$',
    r'^(?P<city>[^,]+)$',
]

NEIGHBORHOOD_COMPONENT_REGEXES = [
    r'^(?P<neighborhood>[^,]+), *(?P<zip>[0-9]{5})(\-(?P<plus4>[0-9]{4}))?$',
    r'^(?P<neighborhood>[^,]+), *(?P<city>[^,]+), *(?P<state>[A-Z]{2}),? *(?P<zip>[0-9]{5})(\-(?P<plus4>[0-9]{4}))?(, *(?P<country>.+))?$',
    r'^(?P<neighborhood>[^,]+), *(?P<city>[^,]+), *(?P<state>[A-Z]{2})(, *(?P<country>.+))?$',
    r'^(?P<neighborhood>[^,]+), *(?P<state>[A-Z]{2})$',
    r'^(?P<neighborhood>[^,]+), *(?P<city>[^,]+)$',
    r'^(?P<neighborhood>[^,]+)$',
]

ZIP_COMPONENT_REGEXES = [
    r'^(?P<zip>[0-9]{5})(\-(?P<plus4>[0-9]{4}))?$',
]

def extractComponents(type, fullText):
    fullText = fullText.upper().strip()
    originalUnitSign =  None
    if '#' in fullText:
        originalUnitSign = '#'
    fullText = fullText.replace('#', 'UNIT ')
    fullText = re.sub(r'[^0-9A-Z \-,]', '', fullText)
    fullText = re.sub(r' +', ' ', fullText)
    if type == 'address':
        return scanRegexes(ADDRESS_COMPONENT_REGEXES, fullText, originalUnitSign)
    elif type == 'city':
        return scanRegexes(CITY_COMPONENT_REGEXES, fullText)
    elif type == 'neighborhood':
        return scanRegexes(NEIGHBORHOOD_COMPONENT_REGEXES, fullText)
    elif type == 'zip':
        return scanRegexes(ZIP_COMPONENT_REGEXES, fullText)
    else:
        return {}

def geocode(components):
    from rentenna3.models import City, State

    if components.get('query'):
        queryComponents = extractComponents(components['type'], components['query'])
        components.update(queryComponents)

    if components['type'] == 'address':
        return getAddress(components), components
    elif components['type'] == 'city':
        return getCity(components), components
    elif components['type'] == 'neighborhood':
        return getNeighborhood(components), components
    elif components['type'] == 'zip':
        return getZip(components), components
    else:
        return None, components

def geocodeText(fullText):
    components = extractComponents('address', fullText)
    components['type'] = "address"
    return geocode(components)

def getAddress(components, skipCheck=False):
    if not skipCheck:
        if components.get('address'):
            addressParts = components.get('address').split(" ", 1)
            components['streetNumber'] = addressParts[0]
            components['street'] = addressParts[-1]

        # assign city if missing
        if (not components.get('city')) and (not components.get('state')) and (not components.get('zip')):
            region = flask.request.headers.get('X-Appengine-Region')
            city = flask.request.headers.get('X-Appengine-City')
            state = State.forAbbr(region)
            if state and city:
                components['city'] = city.upper()
                components['state'] = state.abbr
            else:
                components['city'] = "NEW YORK"
                components['state'] = "NY"

        # required components
        if not components.get('streetNumber'):
            return None
        if not components.get('street'):
            return None

    streetNumber = components['streetNumber']
    street = components['street']
    city = components.get('city')
    state = components.get('state')
    zipCode=components.get('zip')
    geocoderResult = api.obiGeocode(
        streetNumber=streetNumber,
        streetName=street,
        state=state,
        city=city,
        zipCode=zipCode,
    )

    result = geocoderResult.get('Result')
    
    if result is None \
        and streetNumber \
        and street \
        and city \
        and state \
        and any(char.isdigit() for char in streetNumber):
        
        addressId = ':'.join(
            filter(
                None,
                [
                    streetNumber,
                    street,
                    city,
                    state,
                    zipCode,
                ]
            )
        )

        addressId = rutil.keyify(addressId)
        memKey = 'google-geocoding:result:v1:%s' % addressId

        result = memcache.get(memKey)
        if not result:
            ndbResult = GoogleGeocodedResult.forAddressId(addressId)
            if ndbResult:
                result = ndbResult.result
                memcache.set(memKey, result, expires=60*60*24*2)
            else:
                geocoderResult = api.googleGeocode(
                    streetNumber=streetNumber,
                    streetName=street,
                    state=state,
                    city=city,
                    zipCode=zipCode,
                )
                if geocoderResult:
                    result = geocoderResult.get('Result')
                    result['isBadResult'] = False
                else:
                    result = { 'isBadResult' : True }

                memcache.set(memKey, result, expires=60*60*24*2)
                GoogleGeocodedResult.create(
                    addressId=addressId,
                    addressComponents=components,
                    result=result,
                )

    if result is None or result.get('isBadResult'):
        result = {}

    required = ['AddressNumber', 'Street', 'Postcode']
    if all([result.get(req) for req in required]):

        if result.get('UnitValue', None):
            addrId = "/".join([
                result.get('AddressNumber', ''),
                result.get('PreDir', ''),
                result.get('Prefix', ''),
                result.get('Street', ''),
                result.get('Suffix', ''),
                result.get('PostDir', ''),
                result.get('UnitValue', ''),
                result.get('Postcode', ''),
            ])
        else:
            addrId = "/".join([
                result.get('AddressNumber', ''),
                result.get('PreDir', ''),
                result.get('Prefix', ''),
                result.get('Street', ''),
                result.get('Suffix', ''),
                result.get('PostDir', ''),
                result.get('Postcode', ''),
            ])

        existing = Address.getByAddr(addrId)
        if not existing:
            return persistAddress(addrId, components, result)
        else:
            return existing

def getAddressBySlugWorkaround(slug):
    addr = None
    if slug:
        #special handling here to deal with missing slug either being deleted or missed from address migration
        parts = slug.split('-')
        if len(parts) > 2 and util.containDigit(parts[0]):
            zipcode = None
            unitVal = None
            if util.possibleZipcode(parts[-1]):
                zipcode = parts.pop(-1)
                if len(parts) > 2:
                    if util.containDigit(parts[-1]):
                        unitVal = parts.pop(-1)
                street = ' '.join(parts)

                if zipcode:
                    if unitVal:
                        street = '%s unit %s' % (street, unitVal)
                    components = {
                        'street' : street,
                        'zip' : zipcode,
                        'streetNumber' : '',
                        'city' : '',
                        'state' : '',
                        'type' : 'address',
                    }
                    addr = getAddress(components, skipCheck=True)
    return addr

def getCity(components):
    # city, state, and location match
    if components.get('city') and components.get('state'):
        result = queryWithBias(
            City,
            {
                'uname': components['city'].upper(),
                'state': components['state'].upper(),
            },
            components,
        )
        if result:
            return result
    elif components.get('city'):
        result = queryWithBias(
            City,
            {
                'uname': components['city'].upper(),
            },
            components,
    )
        if result:
            return result

    if components.get('zip'):
        zip = ZipcodeArea.forSlug(components['zip'])
        if zip:
            return zip.getCity()

    if components.get('location'):
        return util.first(City.queryGeoref(components['location']))

def getNeighborhood(components):
    if components.get('city'):
        city = getCity(components)
        if city:
            components['city-slug'] = city['slug']
            components['state'] = city['state']
    else:
        city = None

    if city and components.get('neighborhood'):
        result = queryWithBias(
            Area,
            {
                'uname': components['neighborhood'].upper(),
                'city': city['slug'],
            },
            components,
        )
        if result:
            return result

    if components.get('neighborhood'):
        result = queryWithBias(
            Area,
            {
                'uname': components['neighborhood'].upper(),
            },
            components,
        )
        if result:
            return result

    if components.get('location'):
        return util.first(Area.queryGeoref(components['location']))

    if components.get('zip'):
        zip = ZipcodeArea.forSlug(components['zip'])
        if zip:
            intersecting = util.first(Area.queryGeoref(zip['geometry']))
            if intersecting:
                return intersecting

def getZip(components):
    # required components
    if not components.get('zip'):
        return None

    return ZipcodeArea.forSlug(components['zip'])

def persistAddress(addrId, components, result):
    slug = rutil.keyify(addrId)

    geo = {
        'type': "Point",
        'coordinates': [
            result['Longitude'],
            result['Latitude'],
        ],
    }

    cities = City.queryGeoref(
        geo,
        fields={'slug': 1, 'preferred': 1},
    )
    if len(cities) == 0:
        city = None
        allCities = []
    else:
        cities = sorted(cities, key=lambda x: (not x.get('preferred', False)))
        pickedCity = cities[0]
        geocodedCity = result['City']
        if not pickedCity.get('preferred', False) and geocodedCity:
            first = None
            second = None
            geocodedCity =geocodedCity.upper()
            for _city in cities:
                if first is None and _city['uname'] == geocodedCity:
                    first = _city
                    break
                if second is None and _city['uname'].startswith(geocodedCity):
                    second = _city

            if first:
                pickedCity = first
            elif second:
                pickedCity = second 

        city = pickedCity['slug']
        allCities = [_city['slug'] for _city in cities]

    areas = Area.queryGeoref(geo, fields={'slug': 1})
    areas = [area['slug'] for area in areas]

    # this is v. unlikely to exist
    caddr = CanonicalAddrs.queryFirst({
        'alt': addrId,
    })
    if caddr:
        caddrId = caddr['_id']
    else:
        caddrUpsertResult = CanonicalAddrs.update(
            {'preferred': addrId},
            {'preferred': addrId, 'alt': [addrId]},
            upsert=True,
            multi=False
        )
        if 'upserted' in caddrUpsertResult:
            caddrId = caddrUpsertResult['upserted']
        else:
            caddrId = CanonicalAddrs.queryFirst({'preferred': addrId})['_id']

    if result.get('UnitValue', None):
        unitDesc = result.get('UnitDesc', None)
        if not unitDesc:
            unitDesc = '#'
        elif components.get('originalUnitSign', None):
            unitDesc = components.get('originalUnitSign', None)

        addrStreet = " ".join([
            result.get('AddressNumber', ''),
            result.get('PreDir', ''),
            result.get('Prefix', ''),
            result.get('Street', ''),
            result.get('Suffix', ''),
            result.get('PostDir', ''),
            unitDesc,
            result.get('UnitValue', ''),
        ])
    else:
        addrStreet = " ".join([
            result.get('AddressNumber', ''),
            result.get('PreDir', ''),
            result.get('Prefix', ''),
            result.get('Street', ''),
            result.get('Suffix', ''),
            result.get('PostDir', ''),
        ])

    addrStreet = re.sub(r' +', ' ', addrStreet).strip()
    addrStreet = string.capwords(addrStreet)

    addressUpsertResult = Address.update(
        {'addr': addrId},
        {
            '$set': {
                'addr': addrId,
                'caddr': caddrId,
                'addrCity': result['City'],
                'addrState': result['StateAbbr'],
                'addrZip': result['Postcode'],
                'addrStreet': addrStreet,
                'city': city,
                'slug': slug,
                'location': geo,
                'isPreferred': True,
                'allCities': allCities,
                'areas': areas,
                '_raw': result,
                'unitValue' : result.get('UnitValue', None),
            },
        },
        upsert=True,
        multi=False
    )
    if 'upserted' in addressUpsertResult:
        id = addressUpsertResult['upserted']
        return Address.queryFirst({'_id': id})
    else:
        return Address.queryFirst({'addr': addrId})

def queryWithBias(cls, filter, components):
    bias = components.get('location') or components.get('bias')
    if bias:
        return util.first(cls.getNearest(
            bias,
            filter=filter,
            geoField='center',
        ))
    else:
        return cls.queryFirst(filter)

def scanRegexes(regexes, fullText, originalUnitSign=None):
    for regex in regexes:
        match = re.match(regex, fullText)
        if match:
            groupdict = match.groupdict()
            for key, value in groupdict.items():
                if value is None:
                    del groupdict[key]
            if originalUnitSign:
                groupdict['originalUnitSign'] = originalUnitSign
            return groupdict
    return {}
