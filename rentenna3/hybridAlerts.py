import logging
from google.appengine.api import datastore_errors
from rentenna3 import api
from rentenna3.base import AlertReporter
from rentenna3.data.cities import NEW_YORK_CITY_SLUGS_SET
from rentenna3.email import *
from rentenna3.models import *
from web import config
from web import memcache

class RecentBusinessAlertReporter(AlertReporter):
    schedule = 'Tuesday'
    supports = 'property'
    template = AlertForRecentBusiness
    isHybrid = True

    @classmethod
    def isDataReady(cls):
        ready = False
        shard = config.CONFIG['EMAIL']['shard']

        if shard in ['qa', 'development-kevin']:
            ready = True

        if ready:
            poiCtrl = ArDataControl.forName('RecentPoi')
            if poiCtrl.getEmailed():
                ready = False

        return ready

    @classmethod
    def getMetadata(cls):
        poiCtrl = ArDataControl.forName('RecentPoi')
        if not poiCtrl:
            return {}
        
        return {
            'collectionName' : poiCtrl.getLiveCollection(),
            'batchId' : poiCtrl.getBatchId()
        }

    def report(self, **kwargs):
        alert = self.subscription
        address = self.address

        if not alert.user:
            return None

        user = alert.user.get()
        if not user:
            logging.warning("user is None for the key: %s" % alert.user)
            return None

        batchId = kwargs['batchId'] or None
        collectionName = kwargs['collectionName'] or None

        if batchId is None or collectionName is None:
            logging.error("batchId or collectionName is None")
            return None

        email = user.email
        alertType = self.template.__name__
        
        params = {
            'user' : alert.user,
            'email' : email,
            'batchId' : batchId,
            'alertType' : alertType,
        }

        pois = None
        continueProcess = True
        area = address.getArea(skipGeo=True)
        if area and area.obId:
            (pois, continueProcess) = self.generateData(collectionName, params, area.obId, 'neighboorhood', area.name)
            
        if continueProcess and address.addrZip:
            (pois, continueProcess) = self.generateData(collectionName, params, 'ZI%s' % address.addrZip, 'zip', 'zip %s' % address.addrZip)

        if continueProcess:
            city = address.getCity(skipGeo=True)
            if city and city.obId:
                (pois, continueProcess) = self.generateData(collectionName, params, city.obId, 'city', city.name)
        
        return pois

    # returns (pois, continueProcess)
    def generateData(self, collectionName, params, obId, regionType, regionName):
        if self.exists(params, obId):
            return (None, False)
        else:
            pois = self.getPois(collectionName, params, obId, regionType, regionName)
            if pois:
                if self.createLog(params, obId):
                    return (pois, False)
                else:
                    return (None, False)
        return (None, True)
        
    def getPois(self, collectionName, params, geoId, region, name):
        memKey = '%s:%s:%s' % (collectionName, geoId, params['batchId'])
        pois = memcache.get(memKey)
        if pois is None:
            pois = RecentPoi.forGeoId(collectionName=collectionName, geoId=geoId)
            memcache.set(memKey, pois, 3600)

        if pois:
            return {
                'recentPois' : {
                    'pois' : pois,
                    'region' : region,
                    'name' : name,
                }
            }

    def exists(self, params, obId):
        return HybridAlertLog.exists(
            params['user'], 
            params['email'], 
            params['batchId'],
            params['alertType'], 
            obId
        )

    def createLog(self, params, obId):
        try:
            HybridAlertLog.create(
                params['user'], 
                params['email'], 
                params['batchId'],
                params['alertType'], 
                obId
            )
            
        except datastore_errors.TransactionFailedError, de:
            return False
        except Exception, e:
            logging.error(e)
            return False
        return True