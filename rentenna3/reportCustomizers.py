from rentenna3.base import ReportCustomizer

class AreaReportCustomizer(ReportCustomizer):

    supports = [
        'neighborhood',
        'zipcode',
    ]

    def allowAlerts(self):
        return False

    def atAGlanceName(self):
        return "This Area At A Glance"

    def breadCrumbs(self):
        breadcrumbs = [
            {
                'url': "/",
                'title': "AddressReport",
            }
        ]

        city = self.target.getCity()
        
        state = city.getState()
        if state:
            breadcrumbs.append({
                'url': state.getUrl(),
                'title': state.name,
            })

        if city:
            breadcrumbs.append({
                'url': city.getUrl(),
                'title': city.name,
            })
        
        breadcrumbs.append({
            'title': self.target.name,    
        })

        return breadcrumbs

    def heading(self):
        return self.target.name

    def title(self):
        city = self.target.getCity()
        if not city.isOther():
            location = '%s, %s' % (self.target.name, city.name)
        else:
            location = self.target.name

        return """
            %s Property Reviews, Complaints 
            & Public Records - AddressReport
        """ % (
            location
        )

class CityReportCustomizer(ReportCustomizer):

    supports = 'city'

    def allowAlerts(self):
        return False

    def atAGlanceName(self):
        return "This City At A Glance"

    def breadCrumbs(self):
        breadcrumbs = [
            {
                'url': "/",
                'title': "AddressReport",
            }
        ]

        state = self.target.getState()
        if state:
            breadcrumbs.append({
                'url': state.getUrl(),
                'title': state.name,
            })
        
        breadcrumbs.append({
            'title': self.target.name,    
        })

        return breadcrumbs

    def heading(self):
        return self.target.name

    def title(self):
        return """
            %s Property Reviews, Complaints 
            & Public Records - AddressReport
        """ % self.target.name

class PropertyReportCustomizer(ReportCustomizer):

    supports = 'property'

    def __init__(self, target, stats, queriedAddress, **kwargs):
        ReportCustomizer.__init__(self, target, stats, **kwargs)
        self.queriedAddress = queriedAddress

    def allowAlerts(self):
        return True

    def atAGlanceName(self):
        return "This Property At A Glance"

    def breadCrumbs(self):
        breadcrumbs = [
            {
                'url': "/",
                'title': "AddressReport",
            }
        ]

        state = self.target.getState()
        if state:
            breadcrumbs.append({
                'url': state.getUrl(),
                'title': state.name,
            })
        
        city = self.target.getCity()
        if not city.isOther():
            breadcrumbs.append({
                'url': city.getUrl(),
                'title': city.name,    
            })
        
        neighborhood = self.target.getArea()
        if neighborhood:
            breadcrumbs.append({
                'url': neighborhood.getUrl(),
                'title': neighborhood.name,    
            })
        
        commonName = self.target.getCommonName(self.stats)
        breadcrumbs.append({
            'title': commonName,    
        })

        return breadcrumbs

    def heading(self):
        buildingName = self.target.getBuildingName(self.stats)
        if buildingName:
            return buildingName
        else:
            return self.queriedAddress.getShortName()

    def jsonPayload(self):
        return {
            'property': self.target.getShortName(),
            'propertySlug': self.target.slug,
            'queriedName': self.queriedAddress.getShortName(),
            'currentPage': "property page",
        }

    def subheading(self):
        buildingName = self.target.getBuildingName(self.stats)
        if buildingName:
            return self.queriedAddress.getShortName()
        elif self.queriedAddress._id != self.target._id:
            return "Also known as %s" % self.target.getShortName()

    def title(self):
        fullName = self.target.getFullName(self.stats)
        return "%s Report: Reviews, Complaints & Public Records" % (
            fullName,
        )