import urllib
import oauth2
import datetime
import logging
import json

from google.appengine.api import urlfetch

from web import config
from web import keyserver
from web import memcache
from web import rutil
from web import validate
from web.crawling import CrawlSelector

def breezometer(args, rawArgs=None):
    url = "http://api-beta.breezometer.com/baqi/"

    credentials = keyserver.get()
    args['key'] = credentials['BREEZOMETER']['API_KEY']

    url = "%s?%s" % (url, urllib.urlencode(args))
    if rawArgs is not None:
        for k, v in rawArgs.iteritems():
            url += '&' + k + '=' + v
    logging.info('Breezometer URL: ' + url)

    result = urlfetch.fetch(url, deadline=60)
    logging.info(result.status_code)
    logging.info(result.content)

    return json.loads(result.content)

def googleAutocomplete(input, bias=None):
    params = {
        'key': keyserver.get()['google']['client_key'],
        'components': "country:us",
        'types': "address",
        'input': input,
    }
    if bias:
        params['location'] = "%s,%s" % (
            bias['coordinates'][1],
            bias['coordinates'][0],
        )
        params['radius'] = 10000 # this is only a bias, not a restriction

    url = "https://maps.googleapis.com/maps/api/place/autocomplete/json?%s" % (
        urllib.urlencode(params)
    )
    response = urlfetch.fetch(url)
    return json.loads(response.content)

def googleGeocode(streetNumber, streetName, state, city, zipCode):
    from web import rtime
    quoteKey = 'google:geocoding:over_query_limit'
    overLimit = memcache.get(quoteKey)

    if overLimit:
        logging.warning('google geocoding over query limit')
        return None

    addressLine = ','.join(
            filter(
                None,
                [
                    ' '.join( filter(None, [streetNumber, streetName]) ),
                    ' '.join( filter(None, [city, state]) ),
                    zipCode
                ]
            )
        )

    params = {
        'key': keyserver.get()['google']['server_key'],
        'components': "country:US",
        'address': addressLine,
    }

    url = "https://maps.googleapis.com/maps/api/geocode/json?%s" % (
        urllib.urlencode(params)
    )

    response = urlfetch.fetch(url, deadline=60)
    gJson = json.loads(response.content)

    if gJson['status'] == 'OVER_QUERY_LIMIT':
        seconds = rtime.secondsToPacificMidnight()
        memcache.set(quoteKey, True, expires=seconds)
        return None

    results = gJson['results']
    if results:
        streetJson = next( 
            (result for result in results if 'street_address' in result['types']),
            None
        )

        if streetJson:
            components = streetJson['address_components']
            addressNumber = ''
            street = ''
            city = ''
            state = ''
            postcode = ''

            for component in components:
                types = component.get('types')
                shortName = component.get('short_name')
                if 'street_number' in types:
                    addressNumber = shortName
                elif 'route' in types:
                    street = shortName
                elif 'locality' in types:
                    city = shortName
                elif 'administrative_area_level_1' in types:
                    state = shortName
                elif 'postal_code' in types:
                    postcode = shortName

            location = streetJson['geometry']['location']

            return {
                "Result": 
                {
                    "HasMultiple": False,
                    "NumOfCandidates": 1,
                    "AddressNumber": addressNumber,
                    "CensusBlock": "",
                    "CensusTract": "",
                    "City": city,
                    "CountryCode": "US",
                    "CountyCode": "",
                    "GeoStatus": 134217728,
                    "Latitude": location['lat'],
                    "Longitude": location['lng'],
                    "MatchStatus": 33570816,
                    "Postcode": postcode,
                    "PostcodeExt": "",
                    "PostDir": "",
                    "PostDir2": "",
                    "PreDir": "",
                    "PreDir2": "",
                    "Prefix": "",
                    "Prefix2": "",
                    "State": None,
                    "StateAbbr": state,
                    "Street": street,
                    "Street2": "",
                    "Suffix": "",
                    "Suffix2": "",
                    "Unit": "",
                    "UnitValue": "",
                    "UnitDesc": "",
                    "MatchScore": 1000,
                    "GeoStatusString": "S5",
                    "ExtraStatus": "NSTTDDCSZ",
                    "IsCloseMatch": True,
                    "apiSource" : "google-geocoder",
                },
                "HasError": False,
                "ErrorMessage": None
            }

def obiAvm(street, city=None, state=None, zip=None, unitValue=None):
    from rentenna3.models import ObiAvmResponse
    url = "http://107.178.217.77/xml-onboardservices-net/avm/index.aspx"
    credentials = keyserver.get()
    params = {
        'AID': credentials['OBI']['AID'],
        'RequestTypeId': 1,
        'street': street,
        'city': city or "",
        'state': state or "",
        'zip': zip or "",
        'county5': "",
    }
    requestUrl = "%s?%s" % (url, urllib.urlencode(params))
    result = urlfetch.fetch(requestUrl)
    logging.info(result.status_code)
    if result.status_code == 200:
        logging.info(result.content)
        selector = CrawlSelector(
            xml=result.content.encode('utf-8'),
            namespaces={
                'XAVM': "http://xml.onboardservices.net/AVM/AVM.xsd",
            },
        )
        return ObiAvmResponse(
            highValue = selector.first(
                '//XAVM:HIGH_VALUE/text()',
                validate.ParseInt(),
            ),
            lowValue = selector.first(
                '//XAVM:LOW_VALUE/text()',
                validate.ParseInt(),
            ),
            indicatedValue = selector.first(
                '//XAVM:INDICATED_VALUE/text()',
                validate.ParseInt(),
            ),
            confidence = selector.first(
                '//XAVM:CONFIDENCE_SCORE/text()',
                validate.ParseInt(),
            ),
            bedrooms = selector.first(
                '//XAVM:BEDROOMS/text()',
                validate.ParseInt(),
            ),
            bathrooms = selector.first(
                '//XAVM:BATH_TOTAL/text()',
                validate.ParseInt(),
            ),
            area = selector.first(
                '//XAVM:AREA/text()',
                validate.ParseInt(),
            ),
            yearBuilt = selector.first(
                '//XAVM:YEAR_BUILT/text()',
                validate.ParseInt(),
            ),
            sqft = selector.first(
                '//XAVM:LIVING_SQFT/text()',
                validate.ParseInt(),
            ),
            lotSize = selector.first(
                '//XAVM:LOT_SIZE/text()',
                validate.ParseInt(),
            ),
            numberFloors = selector.first(
                '//XAVM:NUMBER_STORIES/text()',
                validate.ParseInt(),
            ),
            propertyId = selector.first(
                '//XAVM:PROPERTY_ID/text()',
            ),
            propertyType = selector.first(
                '//XAVM:PROPERTY_TYPE/text()',
            ),
            apn = selector.first(
                '//XAVM:APN/text()',
            ),
            unitValue = unitValue,
        )

def obiCommunity(location):
    # get the access token
    accessToken = obiAccessToken()

    # lookup the geo key
    requestUrl = "http://107.178.217.77/api-ist_prod-obiwebservices-com/Area/Hierarchy/Lookup/"
    params = {
        'WKTString': "POINT(%s %s)" % (location['coordinates'][0], location['coordinates'][1]),
        'AccessToken': accessToken,
        'mime': "json",
    }
    requestUrl += "?%s" % urllib.urlencode(params)
    result = urlfetch.fetch(requestUrl)
    response = json.loads(result.content)
    smallestItem = response['response']['result']['package']['item'][0]
    geoKey = smallestItem['geo_key']
    return obiCommunityById(geoKey, accessToken)

def obiCommunityById(geoKey, accessToken=None):
    from rentenna3.models import ObiCommunityResponse

    if accessToken is None:
        accessToken = obiAccessToken()

    # request the community info
    requestUrl = "http://107.178.217.77/api-ist_prod-obiwebservices-com/Community/Area/Full"
    params = {
        'AccessToken': accessToken,
        'mime': "json",
        'AreaId': geoKey,
    }
    requestUrl += "?%s" % urllib.urlencode(params)
    result = urlfetch.fetch(requestUrl)
    response = json.loads(result.content)
    item = rutil.safeAccess(response, 'response', 'result', 'package', 'item', 0)
    if item:
        return ObiCommunityResponse(item)
    else:
        return None

def obiGeocode(streetNumber, streetName, state, city, zipCode):
    endpoint = "https://search.onboard-apis.com/Onboard/AlteryxGeocoderHandler.ashx?%s" % urllib.urlencode({
        'StreetNumber': streetNumber,
        'Street': streetName,
        'CountrySubdivision': state,
        'Municipality': city,
        'PostalCode': zipCode,
        'output': "json",
    })
    key = keyserver.get()['OBI']['APIKEY']
    result = urlfetch.fetch(
        endpoint,
        headers={
            'APIKey': key,
        },
        deadline=60,
    )
    if result.status_code == 200:
        return json.loads(result.content)

def obiSales(distance, location, daysBack=None, prioritizeTime=False):
    from rentenna3.models import ObiSale
    credentials = keyserver.get()
    params = {
        'AID': credentials['OBI']['AID'],
        'password': credentials['OBI']['PASSWORD'],
        'SearchType': '3',
        'searchLatitude': location['coordinates'][1],
        'searchLongitude': location['coordinates'][0],
        'lowValue': "",
        'highValue': "",
        'minSales': "",
        'maxSales': 10,
        'monthsBack': 6,
        'radiusOne': 0.5,
        'radiusTwo': distance,
        'propertyType': "1,2,3,4,5",
        'prioritization': 2,
        'excludeCentroid': 0,
        'CalendarDate': "",
        'AddedDate': "",
        'Min_Date': "",
        'Max_Date': "",
    }
    if daysBack:
        limit = datetime.datetime.now() - datetime.timedelta(days=daysBack)
        params['AddedDate'] = limit.strftime('%m/%d/%Y')
    if prioritizeTime:
        params['prioritization'] = 1

    url = "http://107.178.217.77/xml-onboardservices-net/prop_data/index.aspx?%s" % urllib.urlencode(params)
    result = urlfetch.fetch(url)
    response = CrawlSelector(
        xml=result.content.encode('utf-8'),
        namespaces={'XHSD': "http://xml.onboardservices.net/prop_data/OnBoard_HomeSales_Schema_Ver2.0.xsd"}
    )
    sales = []
    for result in response.select('//XHSD:PROPERTY'):
        data = {
            'unit': result.first('.//XHSD:UNIT/text()'),
            'city': result.first('.//XHSD:CITY/text()'),
            'state': result.first('.//XHSD:STATE_OR_PROVINCE/text()'),
            'zip': result.first('.//XHSD:POSTAL_CODE/text()'),
            'distance': result.first('.//XHSD:DISTANCE/text()', validate.ParseFloat()),
            'propertyType': result.first('.//XHSD:PROPERTY_TYPE/text()'),
            'bedrooms': result.first('.//XHSD:BEDROOMS/text()', validate.ParseInt()),
            'bathrooms': result.first('.//XHSD:BATH_TOTAL/text()', validate.ParseInt()),
            'closePrice': result.first('.//XHSD:CLOSE_PRICE/text()', validate.ParseInt()),
            'closeDate': result.first('.//XHSD:CLOSE_DATE/text()', validate.ParseDate('%m/%d/%Y')),
            'addedDate': result.first('.//XHSD:ADDED_DATE/text()', validate.ParseDate('%m/%d/%Y')),
            'yearBuilt': result.first('.//XHSD:YEAR_BUILT/text()', validate.ParseInt()),
            'sqft': result.first('.//XHSD:LIVING_SQFT/text()', validate.ParseInt()),
            'lotSize': result.first('.//XHSD:LOT_SIZE/text()', validate.ParseInt()),
            'floorCount': result.first('.//XHSD:NUMBER_STORIES/text()', validate.ParseInt()),
            'propertyId': result.first('.//XHSD:ONBOARD_ID/text()', validate.ParseInt()),
        }
        houseNumber = result.first('.//XHSD:HOUSE_NUMBER/text()')
        streetDirPrefix = result.first('.//XHSD:STREET_DIR_PREFIX/text()')
        streetName = result.first('.//XHSD:STREET_NAME/text()')
        streetDirSuffix = result.first('.//XHSD:STREET_DIR_SUFFIX/text()')
        streetSuffix = result.first('.//XHSD:STREET_SUFFIX/text()')
        unitValue = data['unit']
        unitType = None
        if unitValue:
            unitType = '#'
        data['street'] = " ".join([
            x
            for x
            in [
                houseNumber,
                streetDirPrefix,
                streetName,
                streetDirSuffix,
                streetSuffix,
                unitType,
                unitValue,
            ]
            if x
        ])
        sale = ObiSale(data)
        sales.append(sale)
    return sales

def obiAccessToken():
    accessToken = memcache.get('obiCommunity:accessToken:2')
    if accessToken is None:
        requestUrl = "http://107.178.217.77/api-ist_prod-obiwebservices-com/Security/AccessToken/Standard/"
        credentials = keyserver.get()
        params = {
            'AID': credentials['OBI']['AID'],
            'Uid': "property-reporters",
            'UidType': '1',
            'Domain': "www.addressreport.com",
            'TrackingToken': "addressreport",
            'mime': "json",
        }
        requestUrl += "?%s" % urllib.urlencode(params)
        result = urlfetch.fetch(requestUrl)
        logging.info(result)
        response = json.loads(result.content)
        accessToken = response['response']['result']['package']['item'][0]['access_token']
        memcache.set('obiCommunity:accessToken:2', accessToken, expires=3600)
    return accessToken

def yelp(endpoint, payload):
    parameters = urllib.urlencode(payload)
    url = "http://api.yelp.com/v2/%s?%s" % (endpoint, parameters)

    credentials = keyserver.get()

    consumer = oauth2.Consumer(
        credentials['yelp']['key'],
        credentials['yelp']['secret'],
    )
    request = oauth2.Request('GET', url, {})
    request.update({
        'oauth_nonce': oauth2.generate_nonce(),
        'oauth_timestamp': oauth2.generate_timestamp(),
        'oauth_token': credentials['yelp']['token'],
        'oauth_consumer_key': credentials['yelp']['key'],
    })
    token = oauth2.Token(
        credentials['yelp']['token'],
        credentials['yelp']['tokenSecret'],
    )
    request.sign_request(oauth2.SignatureMethod_HMAC_SHA1(), consumer, token)
    signedUrl = request.to_url()

    result = urlfetch.fetch(signedUrl)
    if result.status_code == 200:
        return json.loads(result.content)
    else:
        logging.error(result.content)
