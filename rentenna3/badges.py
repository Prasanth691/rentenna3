import flask
import logging

from rentenna3 import util
from rentenna3 import text
from rentenna3.base import Badge
class BuildingTypeBadge(Badge):

    icon = 'building'
    requires = ['buildingType']
    supports = 'property'

    def badge(self, buildingType):
        if buildingType:
            return {
                'id': "building-type:%s" % buildingType,
                'name': "%s" % buildingType,
                'description': """
                    This is %s.
                """ % (
                    text.indefiniteArticle(buildingType),
                )
            }

class CrimeBadge(Badge):

    icon = 'shield'
    requires = ['crimePerCapitaRank', 'crimePerCapita']
    supports = [
        'neighborhood',
        'zipcode',
    ]

    def badge(self, crimePerCapita, crimePerCapitaRank):
        if crimePerCapitaRank:
            return {
                'id': "crime",
                'name': "Crime in %s" % self.target.name,
                'description': """
                    %s is the %s dangerous %s
                    in %s with %s major felonies per
                    capita annually.
                """ % (
                    self.target.name,
                    text.rank(crimePerCapitaRank, above='most', below='least'),
                    self.supports,
                    self.target.getCity().name,
                    int(crimePerCapita),
                )
            }

class DemographicBadge(Badge):

    icon = 'pieChart'
    requires = ['totalPopulation', 'obiCommunity']
    supports = [
        'neighborhood',
        'zipcode',
    ]

    def badge(self, totalPopulation, obiCommunity):
        if totalPopulation and obiCommunity:
            income = float(obiCommunity.get('inccymedd'))
            return {
                'id': "demographics",
                'name': "Who lives in %s?" % self.target.name,
                'description': """
                    %s people live in %s. The median household
                    income is $%s.
                """ % (
                    text.commaNumber(totalPopulation),
                    self.target.name,
                    text.commaNumber(income),
                )
            }

class NeighborhoodBadge(Badge):

    icon = 'map'
    requires = ['neighborhood']
    supports = 'property'

    def badge(self, neighborhood):
        city = self.target.getCity()
        if neighborhood:
            return {
                'id': 'neighborhood:%s' % neighborhood.slug,
                'name': "In %s" % neighborhood.name,
                'description': """
                    %(name)s is located in %(neighborhood)s, 
                    a neighborhood in %(city)s.
                """ % {
                    'name': self.target.getShortName(),
                    'neighborhood': neighborhood.name,
                    'city': neighborhood.getCity().name
                }
            }
        elif city and city.isOther(): 
            return {
                'id': 'neighborhood:%s' % city.slug,
                'name': "In %s" % city.name,
                'description': """
                    %(name)s is located in %(city)s, 
                    a city in the USA.
                """ % {
                    'name': self.target.getShortName(),
                    'city': city.name,
                }
            }
        else:
            return {
                'id': 'neighborhood:other',
                'name': "In %s" % self.target.addrCity,
                'description': """
                    %(name)s is located in %(city)s, 
                    a city in the USA.
                """ % {
                    'name': self.target.getShortName(),
                    'city': self.target.addrCity,
                }
            }

class PoliticsBadge(Badge):

    icon = 'compass'
    requires = ['votersPercent']
    supports = [
        'neighborhood',
        'zipcode',
    ]

    def badge(self, votersPercent):
        if votersPercent:
            return {
                'id': "politics-%s",
                'name': "%s %s" % (
                    votersPercent['maxKey'],
                    self.type.capitalize()
                ),
                'description': """
                    %s is %s registered %s.
                """ % (
                    self.target.name,
                    text.percent(votersPercent['maxPercent']),
                    votersPercent['maxKey'],              
                )
            }

class StateBadge(Badge):

    icon = 'map'
    supports = 'city'

    def badge(self):
        return {
            'id': "state",
            'name': "In %s" % self.target.getState().name,
            'description': """
                %s is a city in the state of %s.
            """ % (
                self.target.name,
                self.target.getState().name,
            )
        }

class TreeCountBadge(Badge):

    icon = 'tree'
    requires = ['streetTrees']
    supports = 'property'

    def badge(self, streetTrees):
        if streetTrees['count'] > 50:
            return {
                'id': 'tree-lined-streets',
                'name': "Tree-Lined Streets",
                'description': """
                    There are %(count)s street trees within 
                    a block of %(name)s.
                """ % {
                    'name': self.target.getShortName(),
                    'count': streetTrees['count'],
                }
            }

class WealthyAreaBadge(Badge):

    icon = 'money'
    requires = ['totalMedianIncome']
    supports = 'property'

    def badge(self, totalMedianIncome):
        '''
            Initially set median income to household income as a fallback.
            Set to median individual income if it exists.
        '''
        logging.info("totalMedianIncome: " + str(totalMedianIncome))
        if totalMedianIncome:
            if totalMedianIncome > 75000:
                money = '${:0,.0f}'.format(totalMedianIncome)
                return {
                    'id': "wealthy-area",
                    'name': "Wealthy Area",
                    'description': """
                        The median income in this area is 
                        %s, which is higher than typical
                        for %s.
                    """ % (money, self.target.getCity().name)
                }
