# abstract views

class AR.BaseDrilldown extends WEB.BaseView
    ###
        This is an abstract base class for attached views
        that need to automatically subscribe to expand and
        collapse events, which will just call the appropriate
        methods when invoked.
    ###

    __abstract__: true

    attachHandlers: () =>
        @$el.on('expand', @expand)
        @$el.on('collapse', @collapse)

    collapse: () =>

    expand: () =>

class AR.BaseMultiDrilldown extends AR.BaseDrilldown
    ###
        Abstract base class for multidrilldowns, which contain
        a menu to select a stat, which can then be rendered
    ###

    __abstract__: true
    vizType: 'div'

    constructor: (@options) ->
        super(@options)
        @stats = @getJson('stats')

    createContainer: () =>
        if AR.isMobile()
            navType = 'select'
        else
            navType = 'div'

        @$el.append("""
            <div class="multi-drilldown-stats-container">
                <#{ navType } class="stats-nav"></#{ navType }>
                <#{ @vizType } class="stats-viz" style="overflow: auto;"></#{ @vizType }>
            </div>
        """)

    collapse: () =>
        super()
        @$('.multi-drilldown-stats-container').remove()

    expand: () =>
        super()
        if AR.isMobile()
            @expandMobile()
        else
            @expandDesktop()

    expandDesktop: () =>
        @createContainer()
        @$('.stats-viz').css
            width: "700px"
            height: "445px"

        for statsName in @getStatsNames()
            do (statsName) =>
                $navItem = $("""<div class="nav-item"></div>""")
                $navItem
                    .attr('name', statsName)
                    .text(statsName)
                    .appendTo(@$('.stats-nav'))
                $navItem.click =>
                    @$('.nav-item').removeClass('active')
                    $navItem.addClass('active')
                    @$('.stats-viz').empty()
                    @renderStats(statsName, @$('.stats-viz'))

        @$('.nav-item').slice(0, 1).click()

    expandMobile: () =>
        @createContainer()

        @$('.stats-viz').css
            width: "500px"
            height: "445px"

        for statsName in @getStatsNames()
            do (statsName) =>
                $navItem = $("""
                    <option class="nav-item"></option>""")
                $navItem
                    .attr('name', statsName)
                    .text(statsName)
                    .appendTo(@$('.stats-nav'))

        @$('.stats-nav').change (event) =>
            @$('.stats-viz').empty()
            @renderStats($(event.currentTarget).val(), @$('.stats-viz'))

        @renderStats(@$(".nav-item").first().val(), @$('.stats-viz'))

    onItemSelect: ($navItem, statsName) =>

    getStatsNames: () =>
        # subclasses should return a list of reports to visualize
        return []

    renderStats: (name, $viz) =>

class AR.BaseMultiDrilldownSvg extends AR.BaseMultiDrilldown

    vizType: 'svg'

class AR.PinsMap extends AR.GoogleMap

    ###
        Subclass that does the loading & drawing of pins
        on a map for you. Requires a url for the fetching
        of pin-formation ;)
    ###

    initialLoad: true
    LAT_DITHER: 0.00072278371
    HALF_LAT_DITHER: 0.00072278371 / 2
    LNG_DITHER: 0.00124140446
    HALF_LNG_DITHER:  0.00124140446 / 2
    COLOR_MAP: {}
    TYPE_FIELD: 'type'

    constructor: (@options) ->
        if not @options.zoomControl?
            @options.zoomControl = false
        if not @options.disableDoubleClickZoom?
            @options.disableDoubleClickZoom = true
        if not @options.hasDither?
            @options.hasDither = true

        super(@options)

        @pins = {}
        @showLoadingMessage()
        @$el.addClass('zoom-level-' + @gmap.getZoom())

        if @options.url?
            @url = @options.url
        if @options.COLOR_MAP?
            @COLOR_MAP = @options.COLOR_MAP
        if @options.TYPE_FIELD?
            @TYPE_FIELD = @options.TYPE_FIELD

    drawPin: (item, id, coords) =>
        if not @pins[id]
            delay = Math.random() * 500
            WEB.delay delay, =>
                if @options.hasDither
                    coords[0] = coords[0] + Math.random() * @LNG_DITHER - @HALF_LNG_DITHER
                    coords[1] = coords[1] + Math.random() * @LAT_DITHER - @HALF_LAT_DITHER
                point = new AR.GoogleMapDot(
                    new google.maps.LatLng(coords[1], coords[0]),
                    @getColor(item)
                )
                point.setMap(@gmap)
                @pins[id] = true

    drawPins: (data) =>
        for item, idx in data.results
            @drawPin(
                item,
                item.key,
                item.location.coordinates,
            )
        @hideLoadingMessage()

    getColor: (item) =>
        return @COLOR_MAP[item[@TYPE_FIELD]]

    loadPins: () =>
        bounds = @gmap.getBounds()
        ne = bounds.getNorthEast()
        sw = bounds.getSouthWest()
        $.ajax
            url: @url
            success: @drawPins
            data:
                north: ne.lat()
                south: sw.lat()
                east: ne.lng()
                west: sw.lng()

    onBoundsChange: () =>
        @loadPins()

    onZoomChange: () =>
        for cl in @$el.get(0).classList
            if cl.indexOf('zoom-level-') > -1
                @$el.removeClass(cl)
        @$el.addClass('zoom-level-' + @gmap.getZoom())

    showLoadingMessage: () =>
        if @initialLoad
            super()
            @initialLoad = false

class AR.BaseMapDrilldown extends AR.BaseDrilldown

    mapClass: AR.PinsMap
    defaultOptions: {
        zoom: 18
    }

    collapse: () =>
        super()
        @$('.map-canvas').remove()

    expand: () =>
        super()
        @$el.append("""<div class="map-canvas"/>""")
        location = @getJson('location')
        $mapCanvas = @$('.map-canvas')

        options = {}
        _.extend(options, @defaultOptions, @options)
        options.center = location
        options.$el = $mapCanvas
        @map = new @mapClass(options)
        @map.addMarker(location)

# non-abstract views

class AR.AddressFlowLanding extends WEB.BaseView

    cssClass: 'address-flow-landing'

    constructor: (options) ->
        super(options)
        @mode = @getJson('mode')
        if @mode == 'alert'
            AR.log "Viewed the Alerts Landing Page"
        else
            AR.log "Viewed the Address Lookup Landing Page"

    attachHandlers: () =>
        @$('button.cta').click =>
            @$('.address-autocomplete').trigger('search:requested')

class AR.AlertCta extends WEB.BaseView

    context: 'alert-cta'
    cssClass: 'alert-cta'

    constructor: (@options) ->
        super(@options)
        if not @getJson('hideSubscribe')
            if @getJson('isSubscribed')
                @renderSubscribed()
            else
                @renderUnsubscribed()

    attachHandlers: () =>
        @$el.on('click', '.subscribe', @subscribe)
        @$el.on('click', '.unsubscribe', @unsubscribe)

    renderSubscribed: () =>
        $button = @$('button')
        $button.html("""
            <span class="check">
                <span class="fa fa-check" />
            </span>
            Subscribed for Alerts
        """)
        $button.removeClass('subscribe')
        $button.addClass('unsubscribe')

    renderUnsubscribed: () =>
        $button = @$('button')
        $button.html("""
            Get Alerts When This Report Changes
        """)
        $button.addClass('subscribe')
        $button.removeClass('unsubscribe')

    actuallyUnsubscribe: () =>
        property = WEB.getJson('propertySlug')
        AR.log 'Unsubscribed for alerts',
            context: @context
            property: property
        @renderUnsubscribed()
        $.ajax
            url: '/service/subscribe-alerts/'
            data:
                property: property
                subscribe: false

    subscribe: () =>
        AR.requireMembership
            context: @context
            success: =>
                @renderSubscribed()
                AR.signupForAlerts
                    context: @context

    unsubscribe: () =>
        new AR.UnsubscriptionModal
            unsubscribeMethod: @actuallyUnsubscribe

class AR.AlertTableView extends WEB.BaseView

    cssClass: 'property-alert-table-page'

    constructor: (options) ->
        super(options)
        AR.log "Viewed Alert Table",
            topic: WEB.getJson('topic')

class AR.BarChart extends WEB.BaseView

    constructor: (@options) ->
        super(@options)

        #sweird
        className = @$el.attr('class')
        @$el.attr('class', "#{ className } bar-chart")

        totalWidth = @$el.width()
        totalHeight = @$el.height()
        paddedHeight = totalHeight - 60

        chart = d3.select(@$el[0])

        chart.append('text')
            .attr('class', 'unit-label x-axis')
            .attr('y', totalHeight - 15)
            .attr('x', totalWidth / 2)
            .text(options.xUnitLabel)

        chart.append('text')
            .attr('class', 'unit-label y-axis')
            .attr('y', totalHeight / 2)
            .attr('x', 15)
            .attr('transform', "rotate(270 15 #{ totalHeight / 2 })")
            .text(options.yUnitLabel)

        chart.append('text')
            .attr('class', 'chart-title')
            .attr('y', 15)
            .attr('x', totalWidth / 2)
            .text(options.title)

        data = options.data[0] # for now, only one group

        x = d3.scale.ordinal()
            .domain(options.labels)
            .rangeBands([60, totalWidth-15])

        y = d3.scale.linear()
            .domain([0, d3.max(data)])
            .range([paddedHeight, 45])

        barWidth = x(options.labels[1]) - x(options.labels[0]) - 1

        bar = chart.selectAll('g')
                .data(data)
            .enter().append('g')
                .attr('transform', (d,i) -> "translate(#{ x(options.labels[i])+2 }, 0)")

        bar.append('rect')
            .attr('class', 'bar')
            .attr('y', (d) -> y(d))
            .attr('height', (d) -> paddedHeight - y(d))
            .attr('width', barWidth - 1)

        xAxis = d3.svg.axis()
            .scale(x)
            .orient("bottom")

        chart.append("g")
            .attr("class", "axis x-axis")
            .attr("transform", "translate(0, #{ paddedHeight })")
            .call(xAxis)

        yAxis = d3.svg.axis()
            .scale(y)
            .orient("left")

        chart.append("g")
            .attr("class", "y axis")
            .attr("transform", "translate(60, 0)")
            .call(yAxis)

class AR.BarChartDrilldown extends AR.BaseDrilldown
    ###
        This can act as a base class to do a simple bar chart
        drilldown, in which case you'll want to implement the
        various get methods.

        By default, however, it's going to look for some
        json-payload options:
            - data: list of [label, value] tuples
            - xUnitLabel
            - yUnitLabel
    ###

    cssClass: 'bar-chart-drilldown'

    constructor: (@options) ->
        super(@options)
        @data = @getJson('data')
        @title = @getJson('title')
        @xUnitLabel = @getJson('xUnitLabel')
        @yUnitLabel = @getJson('yUnitLabel')

    collapse: () =>
        super()
        @$('.bar-chart-drilldown-viz').remove()

    expand: () =>
        super()
        height = 435
        width = 960
        if AR.isMobile()
            width = 500

        # TODO: Do we re-render on page resize?
        @$el.append("""
            <div class="bar-chart-drilldown-viz">
                <svg class="bar-chart-drilldown-viz-canvas" width="#{width}" height="#{height}"></svg>
            </div>
        """)
        $viz = @$('.bar-chart-drilldown-viz-canvas')
        new AR.BarChart
            $el: $viz
            mode: 'normal'
            labels: @getLabels()
            data: @getDataGroups()
            title: @getTitle()
            xUnitLabel: @getXUnitLabel()
            yUnitLabel: @getYUnitLabel()

    getLabels: () =>
        return (datum[0] for datum in @data)

    getDataGroups: () =>
        # currently just one group
        return [(datum[1] for datum in @data)]

    getTitle: () =>
        return @title

    getXUnitLabel: () =>
        return @xUnitLabel

    getYUnitLabel: () =>
        return @yUnitLabel

class AR.BlockStarter extends WEB.BaseView

    cssClass: 'client'

    constructor: (options) ->
        super(options)

        memberBlock = WEB.getUrlParameter('memberBlock')
        if memberBlock
            WEB.delay 2500, =>
                if AR.USER.status == 'guest'
                    AR.requireMembership
                        context: '?memberBlock'
                        success: @success
                        
        subscribeBlock = WEB.getUrlParameter('subscribeBlock')

        if not subscribeBlock
            rsb = @getCookie('rsb')
            if rsb == '1'
                subscribeBlock = true

        if subscribeBlock
            disableBlock = false
            try
                disableBlock = localStorage.getItem('disableSubscribeBlock')
            catch e
                console.error e

            if !disableBlock
                WEB.delay 2500, =>
                    if AR.USER.status == 'guest'
                        AR.requireMembership
                            context: '?subscribeBlock'
                            subscribeTitle: 'Get alerts for this address'
                            mode: 'subscribe'

    alertSuccess: () =>
        AR.signupForAlerts(
            ->
                window.location.reload()
        )

    success: () =>
        window.location.reload()

    getCookie: (key) =>
        keyValue = document.cookie.match('(^|;) ?' + key + '=([^;]*)(;|$)')
        keyValue = keyValue?[2]
        return keyValue

class AR.BlogEntry extends WEB.BaseView

    cssClass: 'blog-entry'

    constructor: (@options) ->
        super(@options)

        $content = @$('.blog-content')
        if $content.hasClass('truncated')
            $content.children().slice(2).hide()

class AR.BlogList extends WEB.BaseView

    cssClass: 'blog-list'

    constructor: (@options) ->
        super(@options)
        AR.log('Viewed the Blog List')

class AR.BlogPost extends WEB.BaseView

    cssClass: 'blog-post'

    constructor: (@options) ->
        super(@options)
        AR.log 'Viewed a Blog Post',
            slug: @getJson('slug')

class AR.CitibikeMap extends AR.BaseMapDrilldown

    cssClass: "citibike-map"
    defaultOptions: {
        zoom: 17
        hasDither: false
        url: '/service/load-citibike-stations/'
    }

class AR.CityMap extends WEB.BaseView

    cssClass: 'city-map'

    constructor: (@options) ->
        super(@options)

        @neighborhood = @getJson('neighborhood')
        @city = WEB.getJson('currentCity', $('body'))
        @location = @city.center
        @areaType = @getJson('areaType')

        @map = new AR.GoogleMap
            $el: @$el
            center: @location
            zoom: 12

        url = "/city-json/#{ @city.slug }.json"
        if @areaType == 'zipcode'
            url = "/zip-json/#{ @neighborhood }.json"

        $.ajax
            url: url
            success: (data) => @drawAreas(data)

        @lookup = {}
        data = @map.gmap.data
        data.addListener 'mouseover', (event) =>
            data.revertStyle()
            data.overrideStyle event.feature,
                fillOpacity: 0.8

            feature = event.feature
            center = feature.getProperty('center')
            lat = center.coordinates[1]
            lng = center.coordinates[0]
            
            slug = feature.getProperty('slug')
            text = feature.getProperty('name')
            if @areaType == 'zipcode'
                text = slug

            mapLabel = @lookup[slug]
            if not mapLabel
                mapLabel = new MapLabel({
                    position: new google.maps.LatLng(lat, lng),
                    map: @map.gmap
                    text: text
                } );
                @lookup[slug] = mapLabel

        data.addListener 'mouseout', (event) =>
            data.revertStyle()
            slug = event.feature.getProperty('slug')
            mapLabel = @lookup[slug]
            if mapLabel
                mapLabel.setMap(null)
                delete @lookup[slug]

        data.addListener 'click', (event) =>
            if event.feature.getProperty('clickable')
                slug = event.feature.getProperty('slug')
                url = "/report/neighborhood/#{ @city.slug }/#{ slug }/"
                if @areaType == 'zipcode'
                    url = "/report/zip/#{ @city.slug }/#{ slug }/"
                
                WEB.navigate(url)

    drawAreas: (areas, colorIndex=0) =>
        for area in areas
            color = AR.COLORS[colorIndex % AR.COLORS.length]
            colorIndex += 1
            style = {
                strokeColor: '#2d3e4f'
                strokeOpacity: 1
                strokeWeight: 0.5
                fillOpacity: 0.1
                fillColor: color
            }
            if area.slug == @neighborhood
                style.fillOpacity = 0.8
                @map.zoomTo(area.geo)
            shape = @map.addShape area.geo,
                name: area.name
                slug: area.slug
                clickable : area.clickable
                geoName: area.geoName
                areaType : area.areaType
                center : area.center
                style: style
            @drawAreas(area.children, colorIndex)

class AR.CommuteMethodsStats extends AR.BaseMultiDrilldownSvg

    cssClass: 'commute-methods-stats'

    getStatsNames: () =>
        options = []
        options.push('Commute Methods')
        return options

    renderStats: (statsName, $viz) =>
        if statsName == "Commute Methods"
            new AR.Histogram
                $el: $viz
                mode: 'simple'
                data: @stats
                unitLabel: "Commute Methods"
                labelSpace: 130

class AR.CommuteOptimizer extends WEB.BaseView

    cssClass: 'commute-optimizer'

    constructor: (@options) ->
        super(@options)

        @address = @getJson('address')

        @autocomplete = new google.maps.places.Autocomplete(@$('.address input')[0])

        @cache = {}
        storedPlaces = localStorage.commuteOptimizerDestinations
        if storedPlaces?
            @places = JSON.parse(storedPlaces)
        else
            @places = []

        @renderAllDestinations()

    attachHandlers: () =>
        @$('.edit-locations').click(@editLocations)
        @$('.new-location .save').click(@saveNewLocation)
        @$('.new-location .cancel').click(@cancelNewLocation)
        @$('.travel-mode').click(@changeTravelMode)

    cancelNewLocation: () =>
        @clearForm()

    changeTravelMode: (event) =>
        @$('.travel-mode').removeClass('active')
        $(event.currentTarget).addClass('active')

    clearForm: () =>
        @$('.name input').val("")
        @$('.address input').val("")
        @$('.edit-locations').show()
        @$('.new-location').hide()
        @$('.remove').addClass('hidden')

    editLocations: () =>
        @$('.edit-locations').hide()
        @$('.new-location').show()
        @$('.new-location .name input').focus()
        @$('.remove').removeClass('hidden')

    renderAllDestinations: () =>
        @$('.destinations').empty()
        @delay = -15000
        for place in @places
            @renderDestination(place)

    renderDestination: (place) =>
        if not place.travelMode
            place.travelMode = 'TRANSIT'
        $destinations = @$('.destinations')
        $destination = $("""
            <div class="destination">
                <div class="nickname">
                    <div class="remove hidden">
                        <span class="fa fa-times"></span>
                    </div>
                    #{ place.nickname }
                </div>
                <div class="steps"></div>
                <div class="time"></div>
                <div class="loading">
                    <div class="progress progress-striped active">
                        <div class="progress-bar">
                        </div>
                    </div>
                </div>
            </div>
        """)
        $destination.find('.remove').click =>
            @places = _.filter @places, (otherPlace) ->
                otherPlace != place
            @sync()
            @renderAllDestinations()
            @$('.remove').removeClass('hidden')
        $destinations.append($destination)
        if @cache[@getCacheId(place)]?
            @renderDirections(@cache[@getCacheId(place)], $destination, place.travelMode)
        else
            # let's make the progress bar move hahahah
            delay = @delay
            @delay += 10000
            for i in [0..100]
                do (i) ->
                    percent = 1 * i
                    WEB.delay (i * (delay + 1000) / 100), ->
                        $destination.find('.progress-bar').css({'width': "#{ percent }%"})

            WEB.delay Math.max(delay, 0), =>
                date = new Date()
                date.setHours(9)
                date.setMinutes(0)
                dow = date.getDay()
                if dow < 1 # sunday, set to tomorrow
                    date.setDate(date.getDate() + 1)
                else if dow > 5 # saturday, set to yesterday
                    date.setDate(date.getDate() - 1)

                directionsService = new google.maps.DirectionsService()
                
                request = {
                    origin: @address
                    destination: place.address
                    travelMode: @getTravelMode(place) # different for different cities  DRIVING, WALKING
                    transitOptions: {
                        arrivalTime: date
                    },
                }
                directionsService.route request, (result, status) =>
                    if status == 'OK'
                        directions = result.routes[0].legs[0]
                        @cache[@getCacheId(place)] = directions
                        @renderDirections(directions, $destination, request.travelMode)
                    else
                        console.error status
                        $destination.find('.loading').remove()
                        $destination.find('.time').text("No public transport routes found.")

    getTravelMode: (place) ->
        travelMode = google.maps.TravelMode.TRANSIT
        if place.travelMode == 'DRIVING'
            travelMode = google.maps.TravelMode.DRIVING
        else if place.travelMode == 'WALKING'
            travelMode = google.maps.TravelMode.WALKING
        return travelMode
    getCacheId: (place) ->
        mode = @getTravelMode place
        return mode + ':' + place.address

    renderDirections: (directions, $destination, travelMode) ->
        $destination.find('.loading').remove()

        duration = directions.duration.text
        $destination.find('.time').text(duration)

        # travel_modes: {WALKING, DRIVING, BICYCLE, TRANSIT}
        # vehicle.types: {RAIL, METRO_RAIL, SUBWAY, TRAM, MONORAIL, HEAVY_RAIL,
        #   COMMUTER_TRAIN, HIGH_SPEED_TRAIN, BUS, INTERCITY_BUS, TROLLEYBUS,
        #   SHARE_TAXI, FERRY, CABLE_CAR, GONDOLA_LIFT, FUNICULAR, OTHER}

        $steps = $destination.find('.steps')
        for step in directions.steps
            if step.duration.value > (60 * 60)
                hours = Math.round(step.duration.value/60/60)
                if hours != 1
                    plural = "s"
                duration = "#{ hours } hour#{ plural }"
            else
                duration = step.duration.text

            if travelMode == 'TRANSIT'
                $step = $("""<div class="step"/>""").appendTo($steps)
                if step.travel_mode == 'WALKING'
                    $step.append("""
                        <img src="#{ WEB.resource('/image/noun-project/walking.svg') }" class="bus">
                    """)
                else if step.travel_mode == 'TRANSIT'
                    type = step.transit.line.vehicle.type
                    agency = step.transit.line.agencies[0].name
                    if agency == 'MTA New York City Transit' and type == 'SUBWAY'
                        name = step.transit.line.short_name[0]
                        $step.append("""
                            <div class="subway-line" line="#{ name }" city="manhattan-ny">
                                #{ name }
                            </div>
                        """)
                    else if type == 'BUS'
                        $step.append("""
                            <img src="#{ WEB.resource('/image/noun-project/bus.svg') }" class="bus">
                        """)
                    else
                        $step.append("""
                            <img src="#{ WEB.resource('/image/noun-project/train.svg') }" class="train">
                        """)

                $step.append("""<div class="step-time">#{ duration }</div>""")
        
        if travelMode == 'DRIVING'
            $step = $("""<div class="step"/>""").appendTo($steps)
            $step.append("""
                <img src="#{ WEB.resource('/image/noun-project/driving.svg') }" class="bus">
            """)
        if travelMode == 'WALKING'
            $step = $("""<div class="step"/>""").appendTo($steps)
            $step.append("""
                        <img src="#{ WEB.resource('/image/noun-project/walking.svg') }" class="bus">
                    """)

    saveNewLocation: () =>
        place = @autocomplete.getPlace()
        nickname = @$('.name input').val()
        travelMode = @$('.travel-mode.active').attr('data-mode')
        @places.push({
            nickname: nickname
            address: place.formatted_address
            travelMode: travelMode
        })
        @clearForm()
        @renderAllDestinations()
        @sync()

    sync: () =>
        localStorage.commuteOptimizerDestinations = JSON.stringify(@places)

class AR.CompareToParentBox extends WEB.BaseView

    cssClass: 'compare-to-parent-box'

    attachHandlers: () =>
        @$('.child').click =>
            @$('.drilldown-button').click()

class AR.ContactPage extends WEB.BaseView

    cssClass: "contactMap"

    constructor: (@options) ->
        super(@options)
        # 10px top border
        @$el.height($(window).height() - $(".client").outerHeight() - 10)
        @createMap()

    createMap: () =>
        @location =
            type: 'Point'
            coordinates: [-74.0110917,40.7039915]
        @map = new AR.GoogleMap
            $el: @$el
            center: @location,
            zoom: 15
        marker = @map.addMarker(@location)
        info = @map.addInfoWindow(
            """
            <div class="info">
                <strong>AddressReport Home</strong>
                <p>85 Broad Street, 29th Floor<p>
                <p>New York, NY 10004</p>
                <div class="divider"></div>
                <p>team@addressreport.com</p>
            </div>
            """
            marker
        )
        info.open(@gmap, marker)

class AR.Credibility extends WEB.BaseView

    cssClass: "credibility"

    attachHandlers: () =>
        @$('.logo img').on('click', @moveCallout)

    moveCallout: (event) =>
        @$('.quote-callout')
            .removeClass('nyt verge tnw gizmodo')
            .addClass($(event.currentTarget).attr("data-company"))

class AR.CrimeMap extends AR.PinsMap

    COLOR_MAP: {
        'GRAND LARCENY': "#9a5cb4"
        'ROBBERY': "#35495d"
        'FELONY ASSAULT': "#3a99d8"
        'BURGLARY': "#f1c93c"
        'GRAND LARCENY OF MOTOR VEHICLE': "#39ca74"
        'RAPE': "#e47e30"
        'MURDER': "#e54d42"
    }
    TYPE_FIELD: 'crime'

    url: '/service/load-crime-pins/'

    drawPins: (data) =>
        for crime in data.results
            coords = crime.geo.coordinates
            for i in [0...crime.count]
                @drawPin(
                    crime,
                    "#{ coords }-#{ crime.gxId }-#{ i }",
                    crime.geo.coordinates,
                )
        @hideLoadingMessage()

class AR.CrimeMapDrilldown extends AR.BaseMapDrilldown

    cssClass: "crime-map"
    mapClass: AR.CrimeMap

class AR.DistrictMap extends AR.BaseMapDrilldown

    cssClass: 'district-map'
    mapClass: AR.GoogleMap

    expand: () =>
        super()
        @map.showLoadingMessage()
        $.ajax
            url: '/service/load-district-boundary/'
            data:
                id: @getJson('id')
            success: @boundaryLoaded

    boundaryLoaded: (data) =>
        @map.addShape(data.geo)
        @map.zoomTo(data.geo)
        @map.hideLoadingMessage()

class AR.DemolitionMap extends AR.BaseMapDrilldown

    cssClass: "demolition-map"
    defaultOptions: {
        zoom: 16
        hasDither: false
        url: '/service/load-demolitions/'
    }

class AR.DomainRedirectNotification extends AR.ModalView

    template: "domainRedirectNotification"

    attachHandlers: () =>
        super()
        @$('button').click(@collapse)

class AR.DrillableTable extends WEB.BaseView

    cssClass: 'drillable-table'

    constructor: (@options) ->
        super(@options)
        @appendDrill()
        @$el.find(".drill").click (ev) => @drilldown(ev)

    appendDrill: () =>
        @$el.find("thead tr").append("""
            <th class="drill-col"></th>
        """)
        @$el.find("tbody tr:not(.sub-row)").append(
            """
                <td class="drill-col drill expand">
                    <button class="normal small">
                        Show Details
                    </button
                </td>
            """
        )

    drilldown: (ev) =>
        drill = $(ev.currentTarget)
        row = drill.closest(".row")

        if drill.hasClass("expand")
            row.next(".sub-row").show()
            drill.removeClass("expand").addClass("subtract")
            drill.find('button').text('Hide Details')
        else
            row.next(".sub-row").hide()
            drill.removeClass("subtract").addClass("expand")
            drill.find('button').text('Show Details')

class AR.Drilldown extends WEB.BaseView

    cssClass: 'drilldown'

    constructor: (@options) ->
        super(@options)

        # move the visualization below the row, so we can keep the
        # source templates nice and neat
        $row = @$el.closest('.subsection-row')
        # if $row.length == 0
            # throw "Drilldowns must be contained inside a subsection-row"
        if $row.length != 0
            $drilldownArea = $("""<div class="drilldown-area" />""")
            $row.after($drilldownArea)
            @$el.appendTo($drilldownArea)
            $drilldownArea.append("""<img class="drilldown-close" src="/resource/image/modalClose.png" />""")

            @$el.closest('.drilldown-area').on('click', '.drilldown-close', AR.DrilldownButton::collapseAll)

class AR.DrilldownButton extends WEB.BaseView

    cssClass: 'drilldown-button'

    constructor: (@options) ->
        super(@options)
        @expanded = false

    attachHandlers: () =>
        @$el.on('collapse', @collapseMe)
        @$el.on('click', @toggle)

    collapseAll: () =>
        $(".drilldown.expanded").removeClass('expanded').trigger('collapse')
        $('.drilldown-button').trigger('collapse')

    collapseMe: () =>
        target = @$el.attr('target')
        $targetEl = $("##{ target }")
        @$el.removeClass('expanded')
        @expanded = false
        $("window,html,body").removeClass("scrollbar-disabled")
        $targetEl.closest(".drilldown-area").hide()

    expandMe: () =>
        target = @$el.attr('target')
        currentPage = WEB.getJson('currentPage')
        AR.log 'Drilldown button clicked',
            target: target
            currentPage: currentPage

        $targetEl = $("##{ target }")

        if not WEB.getJson('renderFullReport')
            AR.requireMembership
                context: 'Property Page'
                success: ->
                    new AR.ThanksForUpgradingModal(arguments[0])
        else
            $(".drilldown").removeClass('expanded')
            $targetEl.closest(".drilldown-area").show()
            $targetEl.addClass('expanded').trigger('expand')
            @$el.addClass('expanded')
            @expanded = true
            if AR.isMobile() and ($targetEl.attr('inline') != 'true')
                $("window,html,body").addClass("scrollbar-disabled")

    toggle: () =>
        if not @$el.hasClass('disable-drilldown')
            if @expanded
                @collapseAll()
            else
                @collapseAll()
                @expandMe()

class AR.ElevatorTimeByFloor extends AR.BarChartDrilldown

    cssClass: 'elevator-time-by-floor'

    constructor: (@options) ->
        super(@options)
        @times = @getJson('times')
        @mode = @getJson('mode')
        @title = @getJson('title')

    getLabels: () =>
        labels = [1..@times.length]
        labels.shift()
        return labels

    getDataGroups: () =>
        if @mode == 'wait'
            data = (d[0] for d in @times)
        else
            data = (d[1] for d in @times)
        data.shift()
        return [data]

    getXUnitLabel: () =>
        return "Floor"

    getYUnitLabel: () =>
        if @mode == 'wait'
            return "Wait Time (in seconds)"
        else
            return "Travel Time (in seconds)"

class AR.FilthMapDrilldown extends AR.BaseMapDrilldown

    cssClass: "filth-complaint-map"
    defaultOptions: {
        zoom: 18
        url: '/service/load-filth-complaints/'
        COLOR_MAP: {
            'Sewer': "#9a5cb4"
            'Graffiti': "#35495d"
            'Air Quality': "#3a99d8"
            'Urinating in Public': "#f1c93c"
            'Hazardous Materials': "#39ca74"
            'Sanitation Condition': "#e47e30" # -> Street Filth
            'Dirty Conditions': "#e54d42" # -> Litter / Clutter
            'Industrial Waste' : "#29bb9c"
        }
    }

class AR.FindAnApartmentModal extends AR.ModalView

    template: 'findAnApartmentModal'

    constructor: (@options) ->
        super(@options)
        address = new AR.AddressAutocomplete()
        @$('.address').append(address.$el)

class AR.FindAnythingView extends WEB.BaseView

    cssClass: 'find-anything'

    attachHandlers: () =>
        @$('.finder-type button').click(@onFinderClick)

    onFinderClick: (ev) =>
        $target = $(ev.currentTarget)
        type = $target.data('type')
        @$el.removeClass('selected-address selected-city selected-neighborhood selected-zipcode')
        @$el.addClass("selected-#{type}")

class AR.ForgotPasswordModal extends AR.ModalView

    template: 'forgotPasswordModal'

    attachHandlers: () =>
        super()
        @$('form').submit(@reset)

    reset: (event) =>
        event.preventDefault()
        $.ajax
            url: "/service/user/reset-password/"
            data:
                email: @$('input[name=email]').val()
            type: 'POST'
        @collapse()
        new AR.TextModal
            name: "Email Sent"
            text: """
                We've just emailed you instructions to reset your password.
                If it doesn't show up in the next few minutes, make sure to
                check your spam folder.
            """

class AR.FourOFourPage extends WEB.BaseView

    cssClass: '404'

    constructor: (@options) ->

        AR.log 'Viewed the 404 page',
            path: document.location.pathname

class AR.FloodZoneMap extends WEB.BaseView

    cssClass: "flood-zone-map"

    #color dictionary for the different zones
    COLOR_MAP:
        6: '#f1c93c'
        5: '#efb53d'
        4: '#ec9a3e'
        3: '#e97b40'
        2: '#e65f41'
        1: '#e54d42'
        0: '#39ca74'
        X: '#39ca74'

    constructor: (@options) ->
        super(@options)
        zone = @getJson('floodZone')
        location = @getJson('location')
        building = @getJson('building')
        @zones = {}

        if zone == 'X' or zone == '0'
            zoneName = "Low Risk"
        else
            zoneName = "Zone #{ zone }"

        if zone == '1'
            description = """
                #{ building } falls within Evacuation Zone 1
                (out of 6 total zones). Residents here are considered
                to face the most serious threat level for coastal
                flooding resulting from a hurricane storm surge.
            """
        else if zone == '2'
            description = """
                #{ building } falls within Evacuation Zone 2
                (out of 6 total zones). Residents here are
                considered to face the second-most serious threat
                level for coastal flooding resulting from a
                hurricane storm surge.
            """
        else if zone == '3'
            description = """
                #{ building } falls within Evacuation Zone 3 (out
                of 6 total zones). Residents here are considered
                to face the third-most serious threat level for
                coastal flooding resulting from a hurricane
                storm surge.
            """
        else if zone == '4'
            description = """
                #{ building } falls within Evacuation Zone 4 (out
                of 6 total zones). Residents here are considered
                to face a significant threat level for coastal
                flooding resulting from a hurricane storm surge.
            """
        else if zone == '5'
            description = """
                #{ building } falls within Evacuation Zone 5 (out
                of 6 total zones). Residents here are considered
                to face the second-lowest threat level for coastal
                flooding resulting from a hurricane storm surge
                among properties within the 6 evacuation zones.
            """
        else if zone == '6'
            description = """
                #{ building } falls within Evacuation Zone 6 (out
                of 6 total zones). Residents here are considered
                to face a relatively low threat level for coastal
                flooding resulting from a hurricane storm surge
                among properties within the 6 evacuation zones.
            """
        else
            description = """
                #{ building } is not assigned to any of the
                city’s six evacuation zones, meaning that
                its residents are considered to face a low
                risk of encountering coastal flooding
                resulting from a hurricane storm surge.
            """
        zoneInfo = """
            <div class="zone-info">
                <div class="zone" style="background-color: #{ @COLOR_MAP[zone] }">
                    #{ zoneName }
                </div>
                <div class="zone-description">
                    <p>
                        #{ description }
                    </p>
                </div>
            </div>
        """

        if AR.isMobile()
            @$el.append(zoneInfo)
        else
            @$el.append("""<div class="map-canvas"/>""")
            @map = new AR.GoogleMap
                $el: @$('.map-canvas')
                center: location
                zoomControl: false
                zoom: 17
            google.maps.event.addListener(@map.gmap, 'idle', _.once(@readied))

            marker = @map.addMarker(location)

            # add hover that explains the current zone
            info = @map.addInfoWindow(
                zoneInfo
                marker
            )
            info.open(@map.gmap, marker)

    drawZone: (coordinates, zone, id) =>
        if not @zones[id]
            @zones[id] = true

            delay = Math.random() * 500
            WEB.delay delay, =>
                @map.addShape coordinates,
                    style:
                        strokeColor: @COLOR_MAP[zone]
                        strokeOpacity: 0.8
                        strokeWeight: 0
                        fillColor: @COLOR_MAP[zone]
                        fillOpacity: 0.55

    drawZones: (data) =>
        for zone in data.results
            @drawZone(zone.geo.geometries[1], zone.zone, zone.id)

    loadZones: () =>
        bounds = @map.gmap.getBounds()
        ne = bounds.getNorthEast()
        sw = bounds.getSouthWest()
        $.ajax
            url: '/service/load-adjacent-flood-zones/'
            success: @drawZones
            data:
                north: ne.lat()
                south: sw.lat()
                east: ne.lng()
                west: sw.lng()

    onBoundsChange: () =>
        @loadZones()

    readied: () =>
        @map.offsetByPixels(0, -100)
        google.maps.event.addListener(@map.gmap, 'idle', @onBoundsChange)

class AR.GenericModal extends AR.ModalView

    # options are
    #    title
    #    body
    #    buton

    template: 'genericModal'

    attachHandlers: () =>
        super()
        @$el.on('click', 'button', @collapse)

class AR.Header extends WEB.BaseView

    cssClass: 'header'

    attachHandlers: () =>
        @$('.contact-photo').click(@toggleContactDetails)
        @$('.contact-details-toggle').click(@toggleContactDetails)

    toggleContactDetails: () =>
        @$('.contact-details').toggleClass('expanded')

class AR.Histogram extends WEB.BaseView

    constructor: (@options) ->
        super(@options)

        #sweird
        className = @$el.attr('class')
        @$el.attr('class', "#{ className } histogram")

        totalWidth = @$el.width()
        totalHeight = @$el.height()
        paddedHeight = totalHeight - 30
        paddedWidth = totalWidth - 20
        labelSpace = options.labelSpace or 80

        chart = d3.select(@$el[0])

        # bottom axis

        chart.append('path')
            .attr('d', "M 0 #{ paddedHeight } H #{ paddedWidth }")
            .attr('class', "axis")

        if options.mode == 'bisected'
            maxGroup1 = d3.max((x[1] for x in options.data[0]))
            maxGroup2 = d3.max((x[1] for x in options.data[1]))

            bucketLabels = (x[0] for x in options.data[0])

            xScale = d3.scale.linear()
                .domain([-maxGroup1, maxGroup2])
                .range([labelSpace + 10, paddedWidth - 10])

            yScale = d3.scale.linear()
                .domain([0, bucketLabels.length])
                .range([70, paddedHeight])

            # bisection group headings

            chart.append('text')
                .attr('class', 'bisection heading group-1')
                .attr('y', 50)
                .attr('x', xScale(0) - 10)
                .text(options.dataLabels[0])

            chart.append('text')
                .attr('class', 'bisection heading group-2')
                .attr('y', 50)
                .attr('x', xScale(0) + 10)
                .text(options.dataLabels[1])

            bucketData = []
            for [data1, data2] in _.zip(options.data[0], options.data[1])
                bucketData.push([
                    [-data1[1], 0, 'group-1'],
                    [0, data2[1], 'group-2']
                ])

        else
            maxData = d3.max((x[1] for x in options.data))

            bucketLabels = (x[0] for x in options.data)

            xScale = d3.scale.linear()
                .domain([0, maxData])
                .range([labelSpace + 10, paddedWidth - 10])

            yScale = d3.scale.linear()
                .domain([0, bucketLabels.length])
                .range([40, paddedHeight])

            bucketData = []
            for data in options.data
                bucketData.push([
                    [0, data[1], 'group-1'],
                ])

        # units heading

        chart.append('text')
            .attr('class', 'heading major')
            .attr('y', 223)
            .attr('x', 15)
            .attr('transform', 'rotate(270 15 223)')
            .text(options.unitLabel)

        # dashed lines for buckets

        chart.selectAll('.subaxis')
                .data(bucketLabels)
            .enter().append('path')
                .attr('d', (d, i) -> "M #{ labelSpace } #{ yScale(i + 0.5) } H #{ paddedWidth }")
                .attr('class', "subaxis")

        # bucket headings

        chart.selectAll('.subheading')
                .data(bucketLabels)
            .enter().append('text')
                .attr('class', 'heading subheading')
                .attr('x', labelSpace - 10)
                .attr('y', (d, i) -> yScale(i + 0.5) + 4)
                .text((d) -> d)

        # zero bar

        chart.append('path')
            .attr('d', "M #{ xScale(0) } 30 V #{ paddedHeight }")
            .attr('class', "axis")

        # and finally, the bars

        barHeight = yScale(1) - yScale(0) - 2

        chart.selectAll('g')
                .data(bucketData)
            .enter().append('g')
                .attr('transform', (d, i) -> "translate(0, #{ yScale(i) })")
                .selectAll('rect')
                        .data((d) -> d)
                    .enter().append('rect')
                        .attr('class', (d) -> "bar #{ d[2] }")
                        .attr('height', barHeight)
                        .attr('width', (d) -> xScale(d[1]) - xScale(d[0]))
                        .attr('x', (d) -> xScale(d[0]))

class AR.HouseholdStatsDrilldown extends AR.BaseMultiDrilldownSvg

    cssClass: 'census-household-stats'

    getStatsNames: () =>
        options = []

        if @stats.householdSizeByType?
            options.push('Household Size')
        if @stats.maritalStatusByAge?
            options.push('Marital Status by Age')
        if @stats.maritalStatusBySex?
            options.push('Marital Status by Sex')

        return options

    renderStats: (statsName, $viz) =>
        if statsName == "Household Size"
            data = @stats.householdSizeByType
            new AR.Histogram
                $el: $viz
                mode: 'bisected'
                data: [data['Family'], data['Nonfamily']]
                dataLabels: ['Families', 'Nonfamilies']
                unitLabel: "Number of People in Household"
                labelSpace: 50
        else if statsName == "Marital Status by Age"
            data = @stats.maritalStatusByAge
            new AR.Histogram
                $el: $viz
                mode: 'bisected'
                data: [data['Unmarried'], data['Married']]
                dataLabels: ['Unmarried', 'Married']
                unitLabel: "Age"
                labelSpace: 70
        else if statsName == "Marital Status by Sex"
            data = @stats.maritalStatusBySex
            new AR.Histogram
                $el: $viz
                mode: 'bisected'
                data: [data['Male'], data['Female']]
                dataLabels: ['Male', 'Female']
                unitLabel: "Marital Status"
                labelSpace: 140

class AR.InsurentCheck extends WEB.BaseView

    cssClass: "insurent-check"

    attachHandlers: () =>
        @$el.on('click', '.explain', @onExplainClick)

    onExplainClick: () =>
        new AR.TextModal
            name: "What is Insurent?"
            text: """
                If a renter doesn’t meet the credit and income requirements for
                #{ WEB.getJson('property', $('body')) } on their own,
                <a target='_blank' href="http://www.insurent.com/?utm_source=rentenna.com">
                    Insurent Lease Guaranty
                </a>
                can help them qualify immediately by serving as the tenant's guarantor.
            """

class AR.LifeBrowser extends WEB.BaseView

    cssClass: 'life-browser'

    constructor: (options) ->
        super(options)
        @current = null
        WEB.later =>
            @setActive('eat')
            @jig()
            @$("#eat").addClass('active')

    attachHandlers: () =>
        @$('.category').hover(@onCategoryHover)
        @$('.category').click(@onCategoryClick)
        @$('.result').click(@onResultClick)

    jig: () =>
        if not AR.isMobile()
            width = @$('.results').width()
            perRow = Math.floor(width / 300)
            newWidth = width / perRow
            @$('.result').width(newWidth)

    onCategoryHover: (event) =>
        target = $(event.currentTarget).attr('target')
        @setActive(target)

    onCategoryClick: (event) =>
        if not @current?
            target = $(event.currentTarget).attr('target')
            @setCurrent(target)
        else
            @setCurrent(null)

    onResultClick: (event) =>
        href = $(event.currentTarget).attr('href')
        AR.log "Clicked Yelp Link",
            "Yelp Link": href
        if not AR.isMobile()
            window.open(href)


    setActive: (target) =>
        if not @current?
            @$('.category').removeClass('active')

            $target = @$(".category[target=#{target}]")
            $target.addClass('active')

            location = $target.position()
            @$('h3').css('top', "#{location.top+62}px")

    setCurrent: (target) =>
        @current = target
        if @current?
            AR.log "Viewed Life Section Verb",
                "Verb Viewed": target

            @$(".category:not([target=#{target}])").addClass('hidden')

            $target = @$(".category[target=#{target}]")
            $target.addClass('active')
            location = $target.position()
            $target.find(".go-back-text").removeClass('hidden')

            @$('h3').css('top', "2px")
            @$('.category-list').css('top', "#{-location.top}px")

            @$('.category-selector').removeClass('expanded')
            @$('.results').removeClass('active')
            @$("##{target}").addClass('active')
        else
            @$(".category").removeClass('hidden')
            $active = @$(".category.active")
            $active.find(".go-back-text").addClass('hidden')
            location = $active.position()
            @$('h3').css('top', "#{location.top+62}px")
            @$('.category-list').css('top', "60px")
            @$('.category-selector').addClass('expanded')

class AR.LocationReportMap extends WEB.BaseView

    cssClass: "location-report-map"

    constructor: (@options) ->
        super(@options)
        @location = @getJson('location')
        @footprint = @getJson('footprint')

        if AR.isMobile()
            @createStaticMap()
        else
            @createGoogleMap()

    attachHandlers: () =>
        @$el.on('click', '.static-map', @onStaticMapClick)

    createGoogleMap: () =>
        @map = new AR.GoogleMap
            $el: @$el
            center: @location
            zoom: 16

        if @footprint?
            @map.addShape @footprint,
                style:
                    strokeColor: '#3a99d8'
                    strokeOpacity: 0.8
                    strokeWeight: 2
                    fillColor: '#3a99d8'
                    fillOpacity: 0.35
        else
            @map.addMarker(@location)

    createStaticMap: () =>
        coords = AR.GoogleMap.prototype.convertGeoJson(@location)[0].toString().replace(/\(|\)/g,"")
        @$el.append(
            """
            <img class="static-map" src="https://maps.googleapis.com/maps/api/staticmap?center=#{coords}&zoom=14&size=500x200&sensor=false&markers=#{coords}&key=AIzaSyAhawPqvIdOnYG3WiSigohxF0axQecZ1Jo" />
            """
        )

    onStaticMapClick: () =>
        $close = $("""<img class="drilldown-close" src="#{ WEB.resource('/image/modalClose.png') }" />""")
        @$el.addClass('mobile-expand')
        @$el.parent()
            .append($close)
        $close.on 'click', =>
            @$el.empty().removeClass('mobile-expand')
            $close.remove()
            @createStaticMap()
        @createGoogleMap()

class AR.LoginRegisterHandler extends WEB.BaseView

    cssClass: 'client'

    attachHandlers: () =>
        @$el.on('click', '.login-button', @login)
        @$el.on('click', '.register-button', @register)

    login: (event) =>
        event.preventDefault()
        new AR.LoginRegisterModal
            mode: 'login'

    register: (event) =>
        event.preventDefault()
        new AR.LoginRegisterModal
            mode: 'register'

class AR.LoginRegisterModal extends AR.ModalView
    ###
        options:
            mode: 'login' or 'register'
            success: cb(user) to call on success
                if not provided, will reload current page

        TODO: update AR.USER!
    ###

    template: 'loginRegisterModal'

    constructor: (@options) ->
        # set title & buttonText before we call super
        if @options.mode == 'login'
            @options.title = @options.loginTitle
        else if @options.mode == 'subscribe'
            @options.title = @options.subscribeTitle
        else
            @options.title = @options.registerTitle

        if not @options.emailOnly?
            @options.emailOnly = true

        super(@options)
        if not AR.isMobile()
            @$('input[name=email]').focus()

        AR.log "Viewed the #{@options.mode} modal",
            context: @options.context
            emailOnly: @options.emailOnly

        @propertyRegistrationContext = WEB.getJson('propertyRegistrationContext')

    attachHandlers: () =>
        super()
        @$('form').submit(@login)
        @$el.on('click', '.forgot', @forgot)
        @$el.on('change', '.status', @onStatusChange)
        @$el.on 'click', '.login-alt', (event) => @alt(event, 'login')
        @$el.on 'click', '.register-alt', (event) => @alt(event, 'register')

    alt: (event, mode) =>
        event.preventDefault()
        new AR.LoginRegisterModal
            buttonText: @options.buttonText
            context: @options.context
            disableClose: @options.disableClose
            emailOnly: @options.emailOnly
            loginTitle: @options.loginTitle
            mode: mode
            registerTitle: @options.registerTitle
            subscribeTitle: @options.subscribeTitle
            success: @options.success

    close: (event) =>
        @recordBlockResult()
        super(event)

    login: (event) =>
        # TODO: maybe it should be separate methods for login/register
        event.preventDefault()
        @$el.addClass('disabled')
        $.ajax
            url: "/service/user/#{ @options.mode }/"
            data:
                email: @$('input[name=email]').val()
                emailOnly: if @options.mode == 'register' then @options.emailOnly else false
                password: @$('input[name=password]').val()
                moveDate: @$('input[name=move-date]').val()
                moveStatus: @$('select[name=status]').val()
                propertySlug: @propertyRegistrationContext
                context: @options.context
            success: @complete
            type: 'POST'
            error: @error

    complete: (data) =>
        if data.status == 'OK' or data.status == 'LOGIN-REGISTER'
            AR.USER = new AR.User(data.user)
            AR.USER.identify()

            if @options.mode == 'login' or data.status == 'LOGIN-REGISTER'
                AR.log 'Login Completed',
                    context: @options.context
            else if @options.mode == 'subscribe' and data.status == 'OK'
                @recordBlockResult()
                AR.log 'Subscribe Completed',
                    context: @options.context
                    emailOnly: @options.emailOnly
                    moveDate: @$('input[name=move-date]').val()
                    moveStatus: @$('select[name=status]').val()

                AR.logGa('subscribe', 'email')
                WEB.fireGtmEvent('Subscribe Completed')
            else
                AR.log 'Registration Completed',
                    context: @options.context
                    emailOnly: @options.emailOnly
                    moveDate: @$('input[name=move-date]').val()
                    moveStatus: @$('select[name=status]').val()

                AR.logGa('registration', 'email')
                WEB.fireGtmEvent('Registration Completed')

            @collapse()

            if @options.success?
                @options.success(AR.USER)
            else
                window.location.reload()

            $('.alert-cta .subscribe').trigger('click')
        else
            @$el.removeClass('disabled')
            @$('.error').hide()
            @shake()
            if data.status == 'WRONG-PASSWORD'
                @$('.error.wrong-password').show()
            else if data.status == 'NO-EMAIL'
                @$('.error.no-email').show()
            else if data.status == 'IN-USE'
                @$('.error.in-use').show()
            else
                @$('.error.unknown').show()

    recordBlockResult: () =>
        if @options.mode == 'subscribe'
            try
                localStorage.setItem('disableSubscribeBlock', true)
            catch e
                console.error e

    error: () =>
        @complete({'status': "ERROR"})

    forgot: (event) =>
        event.preventDefault()
        @collapse()
        new AR.ForgotPasswordModal()

    onStatusChange: () =>
        status = @$('select[name=status]').val()
        needDate = [
            'looking-to-move',
            'visited-property',
            'application-submitted',
            'papers-signed'
        ]
        if _.contains(needDate, status)
            @$('.move-date').fadeIn()
        else
            @$('.move-date').fadeOut()

class AR.MultiplanOverlay extends WEB.BaseView

    template: 'multiplanOverlay'

    constructor: (@options) ->
        super(@options)
        @inject()
        AR.log "Viewed Multiplan Overlay"

    attachHandlers: () =>
        @$('.modal-close').click(@collapse)
        @$('.plan').click(@choosePlan)

    choosePlan: (event) =>
        $target = $(event.currentTarget)
        plan = $target.attr('data-plan')
        new AR.ChargePlanModal
            plan: AR.PLANS[plan]
            success: @success

    collapse: () =>
        @$el.remove()

    success: () =>
        @collapse()
        @options.success()

class AR.NarrativeBoxContainer extends WEB.BaseView

    cssClass: 'narrative-box-container'

    attachHandlers: () =>
        @$('.narrative-box').click =>
            @$('.drilldown-button').click()

class AR.NewBuildingMap extends AR.BaseMapDrilldown

    cssClass: "new-building-map"
    defaultOptions: {
        zoom: 16
        hasDither: false
        url: '/service/load-new-buildings/'
    }

class AR.NoiseMap extends AR.PinsMap

    # For more descriptive classifications, we're classifying most sounds by descriptor (with the exception of Helicopter)
    DESCRIPTOR_MAP: {
        # Alarm
        'Noise: Alarms (NR3)': "Alarm",
        # Car / Truck
        '21 Collection Truck Noise': "Car / Truck",
        'Car/Truck Horn': "Car / Truck",
        'Car/Truck Music': "Car / Truck",
        'Engine Idling': "Car / Truck",
        'Horn Honking Sign Requested (NR9)': "Car / Truck",
        'Noise, Ice Cream Truck (NR4)': "Car / Truck",
        'Noise: Vehicle (NR2)': "Car / Truck",
        # Construction
        'Noise: Construction Before/After Hours (NM1)': "Construction",
        'Noise: Construction Equipment (NC1)': "Construction",
        'Noise: Jack Hammering (NC2)': "Construction",
        # Dog Barking
        'Noise, Barking Dog (NR5)': "Dog Barking",
        # Industrial / Machinery
        'Noise:  lawn care equipment (NCL)': "Dog Barking",
        'Noise: Air Condition/Ventilation Equip, Commercial (NJ2)': "Dog Barking",
        'Noise: Air Condition/Ventilation Equip, Residential (NJ1)': "Dog Barking",
        'Noise: air condition/ventilation equipment (NV1)': "Dog Barking",
        'Noise: lawn care equipment (NCL)': "Dog Barking",
        'Noise: Manufacturing Noise (NK1)': "Dog Barking",
        # Loud Music / Party
        'Loud Music/Party': "Loud Music / Party",
        'Noise: Loud Music/Daytime (Mark Date And Time) (NN1)': "Loud Music / Party",
        'Noise: Loud Music/Nighttime(Mark Date And Time) (NP1)': "Loud Music / Party",
        # Loud Talking / Yelling
        'Loud Talking': "Loud Talking / Yelling",
        'People Created Noise': "Loud Talking / Yelling",
        # Other
        'Banging/Pounding': "Other",
        'Loud Television': "Other",
        'N/A': "Other",
        'Noise, Other Animals (NR6)': "Other",
        'Noise: Boat(Engine,Music,Etc) (NR10)': "Other",
        'Noise: Other Noise Sources (Use Comments) (NZZ)': "Other",
        'Noise: Private Carting Noise (NQ1)': "Other",
    }

    COLOR_MAP: {
        'Loud Music / Party': "#9a5cb4"
        'Construction': "#35495d"
        'Loud Talking / Yelling': "#3a99d8"
        'Car / Truck': "#f1c93c"
        'Dog Barking': "#39ca74"
        'Industrial / Machinery': "#e47e30"
        'Alarm': "#e54d42"
        'Other' : "#29bb9c"
        'Helicopter': "#e88b2c"
    }

    url: '/service/load-noise-complaints/'

    getColor: (item) =>
        if item.type == "Noise - Helicopter"
            color = @COLOR_MAP[item.type]
        else
            color = @COLOR_MAP[@DESCRIPTOR_MAP[item.descriptor]]
        return color

class AR.NoiseMapDrilldown extends AR.BaseMapDrilldown

    cssClass: "noise-complaint-map"
    mapClass: AR.NoiseMap
    defaultOptions: {
        zoom: 18
    }

class AR.ObiAnnouncement extends WEB.BaseView

    cssClass: 'client'

    constructor: (@options) ->
        super(@options)


        begin = new Date(1453287300000)
        now = new Date()
        allowPromotion = WEB.getJson('allowPromotion')
        #console.log WEB.getJson('partnerSlug')
        if allowPromotion and window.location.href.indexOf('admin') < 0
            @show()

    show: () =>
        if AR.isMobile()
            @$el.prepend("""
                <div class="hellobar">
                    Learn about
                    <a href="http://landing.onboardinformatics.com/onboard-and-addressreport"
                            target="_blank">
                        Onboard's AddressReport solution
                    </a>
                </div>
            """)
        else
            @$el.prepend("""
                <div class="hellobar">
                    Industry pros, learn about
                    <a href="http://landing.onboardinformatics.com/onboard-and-addressreport"
                            target="_blank">
                        Onboard's solution using AddressReport technology.
                    </a>
                </div>
            """)

class AR.PoiMap extends AR.GoogleMap

    ###
        Subclass that fetches point of interest data from the Google
        Places Service, then draws pins and updates a list on the map
    ###

    constructor: (@options) ->
        super(@options)

        @firstLoad = true
        @showLoadingMessage()
        @$el.addClass('zoom-level-' + @gmap.getZoom())

    drawPin: (coords, color, name, index) =>
        cssClass = "dot-" + index
        point = new AR.GoogleMapDot(
            new google.maps.LatLng(coords[1], coords[0]),
            color,
            index
        )

        point.setMap(@gmap)
        point.addClass(cssClass)

        # update the results pane
        $result = $("""
            <div class="result" data-dot="#{ cssClass }">
                <div class="total">
                    <div class="number">#{ index }</div>
                </div>
                #{ name }
            </div>
        """)
        @$el.parent().find('.results').append($result)
        $result.on('mouseover', =>
            $result.addClass('highlight')
            @$el.find(".#{ $result.attr('data-dot') }").addClass('highlight')
        )
        $result.on('mouseout', =>
            $result.removeClass('highlight')
            @$el.find('.map-dot').removeClass('highlight')
        )

    drawPins: (data) =>
        @removePins()
        for item, idx in data.results
            @drawPin(
                [item.geometry.location.lng(),item.geometry.location.lat()],
                "#3a99d8",
                item.name,
                (idx + 1),
            )
        @hideLoadingMessage()

    loadPins: () =>
        service = new google.maps.places.PlacesService(@gmap)
        if @firstLoad
            # TODO: should accept radius?
            query = {
                location: @gmap.getCenter()
                radius: 400
                types: [@options.placeType]
            }
        else
            query = {
                bounds: @gmap.getBounds()
                types: [@options.placeType]
            }
        service.nearbySearch query, (response) =>
            @drawPins({'results': response})

    onBoundsChange: () =>
        @loadPins()

    removePins: () =>
        @$el.parent().find('.results').empty()
        @$el.find('.map-dot').remove()

class AR.PoiMapDrilldown extends AR.BaseDrilldown

    cssClass: "poi-map-drilldown"

    constructor: (@options) ->
        super(@options)
        @location = @getJson('location')
        @googlePlaceType = @getJson('googlePlaceType')

    collapse: () =>
        super()
        @$('.map-canvas').remove()

    expand: () =>
        super()
        @$el.append("""<div class="map-canvas"/>""")
        # TODO: zoom and radius should vary...
        @map = new AR.PoiMap
            $el: @$('.map-canvas')
            hasDither: false
            center: @location
            placeMap: true
            placeType: @googlePlaceType
            zoomControl: false
            zoom: 17
        marker = @map.addMarker(@location)

class AR.PopulationStatsDrilldown extends AR.BaseMultiDrilldownSvg

    cssClass: 'census-population-stats'

    getStatsNames: () =>
        options = []

        if @stats.ageBySex?
            options.push('Age by Sex')
        if @stats.raceBySex?
            options.push('Race')
        if @stats.placeOfBirth?
            options.push('Place of Birth')
        if @stats.geographicMobility?
            options.push('Geographic Mobility')

        return options

    renderStats: (statsName, $viz) =>
        if statsName == "Age by Sex"
            data = @stats.ageBySex
            new AR.Histogram
                $el: $viz
                mode: 'bisected'
                data: [data['Male'], data['Female']]
                dataLabels: ['Male', 'Female']
                unitLabel: "Age in Years"
                labelSpace: 80
        else if statsName == "Race"
            data = @stats.raceBySex
            new AR.Histogram
                $el: $viz
                mode: 'bisected'
                data: [data['Male'], data['Female']]
                dataLabels: ['Male', 'Female']
                unitLabel: "Race"
                labelSpace: 140
        else if statsName == "Place of Birth"
            new AR.Histogram
                $el: $viz
                mode: 'simple'
                data: @stats.placeOfBirth
                unitLabel: "Place of Birth / Citizenship Status"
                labelSpace: 180
        else if statsName == "Geographic Mobility"
            data = @stats.geographicMobility
            new AR.Histogram
                $el: $viz
                mode: 'bisected'
                data: [data['Male'], data['Female']]
                dataLabels: ['Male', 'Female']
                unitLabel: "Geographic Mobility in Last Year"
                labelSpace: 200

class AR.PreStitial extends WEB.BaseView

    cssClass: 'pre-stitial'

    constructor: (options) ->
        super(options)
        new AR.PreStitialModal()

class AR.PreStitialModal extends AR.ModalView

    template: 'preStitialModal'

    constructor: (options) ->
        super(options)
        @timer = 5
        @$('.countdown').text(@timer)
        AR.log "Viewed Pre-stitial",
            'partner': @$('img').data('partner')
            'ad': @$('img').data('campaign')
        @countdown()

    attachHandlers: () =>
        @$('img').on('click', @redirect)

    countdown: () =>
        if @timer > 1
            @timer -= 1
            @$('.countdown').text(@timer)
            WEB.delay(1000, @countdown)
        else
            @close()

    redirect: () =>
        WEB.track "Clicked Pre-stitial",
            'partner': @$('img').data('partner')
            'ad': @$('img').data('campaign')
        window.open('http://www.insurent.com/?utm_source=rentenna.com', '_blank')

class AR.MockProcessing extends WEB.BaseView

    cssClass: 'mock-processing'

    constructor: (@options) ->
        super(@options)
        AR.log 'Viewed the Mock Processing Page'

    attachHandlers: () =>
        @$('.email-form').submit(@submitEmailForm)
        @$el.on('progressbar-complete', @showSocialProof)

    showSocialProof: () =>
        @$('.loading-interim').hide()
        tweets = new AR.SocialProofView
        @$el.append(tweets.$el)
        @$('.email-block').show()
        if not AR.isMobile()
            @$('.email input').focus()

    submitEmailForm: (event) =>
        event.preventDefault()
        @$('.email-block').hide()
        @$('.dead-end').show()

        AR.log 'Submitted Email on the Mock Processing Page'

        AR.logGa('registration', 'email')
        WEB.fireGtmEvent('Submitted alert or report email form')

        email = @$('.email input').val()
        property = @getJson('property')
        $.ajax
            url: '/send-me-report-subscribe/'
            data:
                email: email
                target: @getJson('target')
                commonName: @getJson('commonName')
                type: @getJson('type')
            type: 'POST'
            success: (data) =>
                AR.USER = new AR.User(data.user)
                AR.USER.identify()

class AR.MockProgressBar extends WEB.BaseView

    cssClass: 'mock-loading'
    template: 'mockLoading'

    constructor: (options) ->
        super(options)
        @delay = options.delay or 2000
        @reporters = [
            "Computing Estimated Property Values...",
            "Analyzing Police Precinct Crime Reports...",
            "Tabulating Census Demographic Data...",
            "Finding Nearby Restaurants...",
        ]
        @reporter = 0
        @animateProgressBar()

    animateProgressBar: () =>
        reporter = @reporters[@reporter]
        if reporter?
            @$('.loading-message').text(reporter)
            @$('.progress-bar').css
                width: "#{ 100 * (1+@reporter) / @reporters.length }%"
            @reporter += 1
            WEB.delay(
                (@delay * Math.random()),
                @animateProgressBar
            )
        else
            @$el.trigger('progressbar-complete')

class AR.PropertyValue extends WEB.BaseView

    cssClass: 'property-value'

    attachHandlers: () =>
        super()
        @$('.speak-with-expert').click(@speakWithExpert)

    speakWithExpert: (ev) =>
        ev.preventDefault()

        AR.log "Requested to speak with an expert",
            'Property on which expert was requested': WEB.getJson('propertySlug')

        AR.requireMembership
            context: 'speak-with-expert'
            loginTitle: "Login To Speak With A Neighborhood Expert"
            registerTitle: "Register To Speak With A Neighborhood Expert"
            success: (data)=>
                new AR.TextModal
                    name: "A Neighborhood Expert Will Be With You Shortly"
                    text: """
                        Thank you for requesting to speak with a neighborhood expert.
                        Somebody will reach out to you shortly via email
                        who can provide you with a free, custom valuation
                        of this property.
                    """
                userStatus = 'new'
                if data == "ALREADY-REGISTERED"
                    userStatus = 'existing'
                $.ajax
                    url: '/service/speak-with-expert/'
                    data:
                        userStatus: userStatus
                        property: WEB.getJson('propertySlug')

class AR.PropertyView extends WEB.BaseView

    cssClass: 'property-report'

    constructor: (@options) ->
        super(@options)

        AR.log "Visited a Property Page",
            city: @getJson('city')
            property: @getJson('propertySlug')
        @storeAddress()

        if @getJson('previewMode')
            AR.log "Visited the Sample Report"

    attachHandlers: () =>
        @$el.on('click', '.upgrade-button', @upgrade)
        @$el.on('click', '.launch-notification-button', @upgradeLaunch)
        @$el.on('click', '.search-button', @search)
        @$el.on('click', '.aka .explain', @onExplainClick)
        @$('.sticky-footer .drilldown-close').on('click', @closeStickyFooter)
        if (not @getJson('previewMode')) and (not sessionStorage.getItem("scrollingTriggered"))
            window.addEventListener('scroll', @onScroll)

    closeStickyFooter: () =>
        @$('.sticky-footer').fadeOut()

    onExplainClick: () =>
        new AR.TextModal
            name: "Why do buildings have multiple addresses?"
            text: """
                    Buildings on cross-streets or spanning multiple physical
                    plots may have more than one address. In addition to the
                    "official" address of #{ @getJson('property') } recognized by the
                    city, we've listed all known alternate addresses for this
                    property.
                """

    onScroll: () =>
        if AR.USER.status == 'guest'
            if window.pageYOffset > 2000
                AR.log("Scrolled down property page")
                sessionStorage.setItem('scrollingTriggered', 'true')
                window.removeEventListener('scroll', @onScroll)

    search: (event) =>
        event.preventDefault()
        new AR.FindAnApartmentModal()

    storeAddress: () =>
        try
            storedAddresses = localStorage.recentPlaces
        catch error
            console.error error
            storedAddresses = null

        if storedAddresses?
            storedAddresses = JSON.parse(storedAddresses)
        else
            storedAddresses = {}

        if Object.keys(storedAddresses).length > 2
            oldest = Object.keys(storedAddresses)[0] # just guessin
            for stored in storedAddresses
                if new Date(storedAddresses[stored].date) < new Date(storedAddresses[oldest].date)
                    oldest = stored
            delete storedAddresses[oldest]

        storedAddresses[window.location.pathname] = {
            'address': @getJson('property')
            'date': new Date()
        }

        try
            localStorage.recentPlaces = JSON.stringify(storedAddresses)
        catch error
            console.error error

    upgrade: (event) =>
        event.preventDefault()
        $target = $(event.currentTarget)
        stat = $target.attr('stat')
        AR.log "Clicked Upgrade CTA",
            context: "Property Page"
            stat: stat
        AR.requireMembership
            context: 'Property Page'
            success: ->
                new AR.ThanksForUpgradingModal(arguments[0])

    upgradeLaunch: (event) =>
        event.preventDefault()
        $target = $(event.currentTarget)
        stat = $target.attr('stat')
        AR.log "Clicked Launch Notification CTA",
            context: "Property Page"
        AR.requireMembership
            context: 'Property Page'
            loginTitle: "Be the first to know when we launch in your city"
            registerTitle: "Be the first to know when we launch in your city"
            success: =>
                @closeStickyFooter()
                new AR.GenericModal
                    title: "We'll let you know as soon as we launch"
                    button: "Keep browsing"
                    body: """
                        We're always adding new cities, and this helps us to know
                        where people are interested in getting more data about
                        where they live. We'll let you know the moment we start
                        rolling out full reports here.
                    """

class AR.PropertyListingsTable extends WEB.BaseView

    cssClass: 'property-listings'

    attachHandlers: () =>
        @$('.see-listings').click =>
            @$('.call').hide()
            @$('.listings').show()

class AR.ReportLoadingView extends WEB.BaseView

    cssClass: 'report-loading'
    template: 'reportLoadingView'

    constructor: (@options) ->
        super(@options)

        console.log(@options)

        @reporters = []
        @completed = (x.name for x in @options.completed)
        for reporter in @options.reporters
            @reporters.push({
                reporter: reporter
                status: 'pending'
            })

        @inject()

        reportSimultaneous = WEB.getJson('reportSimultaneous')
        for i in [0...reportSimultaneous]
            @popReporter()

    popReporter: () =>
        next = null
        for reporter in @reporters
            if reporter.status == 'pending'
                allRequirementsSatisfied = true
                for requirement in reporter.reporter.requires
                    if @completed.indexOf(requirement) < 0
                        console.info("#{ reporter.reporter } missing requirement #{ requirement }")
                        allRequirementsSatisfied = false
                if allRequirementsSatisfied
                    next = reporter
                    break

        if next?
            @$('.loading-message').text("#{ next.reporter.description }...")
            next.status = 'running'
            $.ajax
                url: '/service/compute-report-stats/'
                complete: => @reporterComplete(next)
                timeout: 8000
                data:
                    type: @options.type
                    target: @options.targetKey
                    reporter: next.reporter.name

    reporterComplete: (reporter) =>
        reporter.status = 'complete'

        @completed.push(reporter.reporter.name)

        completed = 0
        total = 0
        for reporter in @reporters
            total += 1
            if reporter.status == 'complete'
                completed += 1

        if completed == total
            @allComplete()
        else
            completion = 100 * (completed / total)
            @$('.progress-bar').css('width', "#{ completion }%")
            @popReporter()

    allComplete: () =>
        @$('.loading-message').text("Generating Report")
        WEB.delay 1000, ->
            query = WEB.getUrlHash()
            delete query.force
            query.display = 'true'

            window.location.replace(
                WEB.stringifyHash(query) + window.location.hash,
                '_self'
            )

class AR.ReportPage extends WEB.BaseView

    cssClass: 'report-page'

    constructor: (@options) ->
        super(@options)

        @$('.word-bubble p').hide().slice(0,3).show()
        if @$('.word-bubble p').length <= 3
            @$('.word-bubble .full-description').hide()

        if @getJson('showLoading') and (not WEB.UA.isCrawler())
            WEB.later =>
                new AR.ReportLoadingView
                    reporters: @getJson('pendingReporters')
                    completed: @getJson('completedReporters')
                    type: @getJson('reportType')
                    targetKey: @getJson('reportTargetKey')

    attachHandlers: () =>
        @$('.word-bubble a').on('click', @wordBubbleAnchorClick)
        @$('.word-bubble .full-description').on('click', @wordBubbleFullDescriptionClick)
        @$('.back-to-top').on('click', @backToTop)
        window.addEventListener('scroll', @onScroll)

    backToTop: () =>
        AR.log "Back To Top Button Clicked"
        $("html, body").animate({ scrollTop: 0 }, "slow")

    onScroll: () =>
        if window.scrollY == 0
            @$('.back-to-top').removeClass('stuck bottom').addClass('hidden')
        else if (window.scrollY + $(window).height()) < $('.footer').offset().top
            @$('.back-to-top').removeClass('hidden bottom').addClass('stuck')
        else
            @$('.back-to-top').removeClass('stuck hidden').addClass('bottom')

    wordBubbleAnchorClick: (ev) =>
        currentPage = WEB.getJson('currentPage')
        AR.log "Word Bubble Clicked",
            target: $(ev.currentTarget).attr("href").replace("#","")
            'Page in which word bubble was clicked': currentPage

    wordBubbleFullDescriptionClick: () =>
        AR.log "Word Bubble Full Description Clicked"
        @$('.word-bubble p').slideDown
            complete: =>
                @$('.word-bubble .full-description').fadeOut()

class AR.RodentMapDrilldown extends AR.BaseMapDrilldown

    cssClass: "rodent-complaint-map"
    defaultOptions: {
        url: '/service/load-rodent-complaints/'
        zoom: 18
        TYPE_FIELD: 'descriptor'
        COLOR_MAP: {
            'Condition Attracting Rodents': "#9a5cb4"
            'Rat Sighting': "#35495d"
            'Mouse Sighting': "#3a99d8"
            'Signs of Rodents': "#f1c93c"
            'Rodent Bite': "#39ca74"
        }
    }

class AR.RootView extends WEB.BaseView

    cssClass: 'root'

    constructor: (@options) ->
        super(@options)
        AR.log "Visited the Homepage"
        if WEB.UA.isPhone()
            @$('.banner .address-autocomplete').hide()
            @$('.banner .iphone-button').show()

    attachHandlers: () =>
        @$('.cta').click(@upgrade)

    upgrade: (event) =>
        $target = $(event.currentTarget)
        $parent = $target.closest('.blurb')
        heading = $parent.find('h3').text()
        AR.log "Clicked Get Started Now",
            context: "Homepage"
            heading: heading
        new AR.FindAnApartmentModal()

class AR.ScaffoldMap extends AR.BaseMapDrilldown

    cssClass: "scaffold-map"
    defaultOptions: {
        zoom: 17
        hasDither: false
        url: '/service/load-scaffolds/'
        COLOR_MAP: {
            'SH': "#9a5cb4"
            'SF': "#35495d"
        }
        TYPE_FIELD: 'subtype'
    }

class AR.SchoolInfoDrilldown extends AR.BaseMultiDrilldown

    cssClass: 'school-info-drilldown'

    constructor: (@options) ->
        super(@options)
        @school = @getJson('school')

    expand: () =>
        superClass = AR.SchoolInfoDrilldown.__super__

        $.ajax
            url: '/service/load-test-scores/'
            data:
                schoolId: @school.obId
            success: (data) =>
                @testScores = data.measures
                superClass.expand.apply @

    getStatsNames: () =>
        statNames = ["Key Stats", "Map"]

        if @school.programs? and @school.programs.length > 0
            statNames.push('Programs Offered')

        if @testScores? and @testScores.length > 0
            statNames.push('Test Score Details')

        for enroll in @getJson('enrollment')
            if enroll[1] > 0
                statNames.push("Enrollment by Grade")
                break

        return statNames

    renderEnrollment: ($viz) =>
        $viz.append("""<svg width="100%" height="100%"></svg>""")
        enrollment = @getJson('enrollment')
        x = (o[0] for o in enrollment)
        y = (o[1] for o in enrollment)
        new AR.BarChart
            $el: $viz.find('svg')
            xUnitLabel: "Grade"
            yUnitLabel: "Number of Students Enrolled"
            labels: x
            data: [y]

    renderKeyStats: ($viz) =>
        @$('.stats-viz').css({'background-color': 'white', 'overflow': 'auto'})
        $viz.css('background-color', 'white')
        div = $('<div style="padding: 20px;"></div>')
        $viz.append(div)

        if @school.GS_TEST_RATING != ''
            div.append("<h3>Overall Test Rating: #{ @school.GS_TEST_RATING }/5</h3>")
        if @school.STUDENTS_NUMBER_OF != ''
            div.append("<h3>Number Of Students: #{ @school.STUDENTS_NUMBER_OF }</h3>")
        if @school.TEACHERS_PROFESSIONAL_STAFF != ''
            div.append("<h3>Number Of Teachers: #{ @school.TEACHERS_PROFESSIONAL_STAFF }</h3>")
        if @school.STUDENT_TEACHER != ''
            div.append("<h3>Student-Teacher Ratio: #{ @school.STUDENT_TEACHER }</h3>")

        if @school.HIGH == 'Y'
            if @school.ADVANCED_PLACEMENT == 'Y'
                offersAP = 'Yes'
            else
                offersAP = 'No'

            div.append("<h3>Advanced Placement: #{ offersAP }</h3>")

            if @school.INTERNATIONAL_BACCALAUREATE == 'Y'
                offersIB = 'Yes'
            else
                offersIB = 'No'

            div.append("<h3>International Baccalaureate: #{ offersIB }</h3>")

            if @school.COLLEGE_BOUND != ''
                div.append("<h3>College Bound Seniors: #{ @school.COLLEGE_BOUND }%</h3>")

    renderMap: ($viz) =>
        $viz.addClass('map-canvas')
        location = @school.location
        map = new AR.GoogleMap
            $el: $viz
            center: location
        map.addMarker(location)
        map.showLoadingMessage()
        $.ajax
            url: '/service/load-school-boundary/'
            data:
                id: @school.obId
            success: (data) => @renderMapWithBounds(map, data)

    renderMapWithBounds: (map, data) =>
        map.hideLoadingMessage()
        if data.status == "OK"
            map.addShape(data.geo)
            map.zoomTo(data.geo)

    renderPrograms: ($viz) =>
        @$('.stats-viz').css({'background-color': 'white', 'overflow': 'auto'})
        programs = {}

        for program in @school.programs
            splitProgram = program.split(' - ')
            programCategory = splitProgram[0]
            programName = splitProgram[1]

            if programCategory of programs
                programs[programCategory].push(programName)
            else
                programs[programCategory] = [programName]

        div = $('<div style="padding: 20px;"></div>')
        $viz.append(div)
        for subjectName of programs
            div.append("""<h4 style="text-decoration: underline; font-size: 16px;">#{ subjectName }</h4>""")
            ul = $('<ul></ul>')
            div.append(ul)
            for program in programs[subjectName]
                if program?
                    ul.append("<li>#{ program }</li>")

    renderTestScores: ($viz) =>
        @$('.stats-viz').css({'background-color': 'white', 'overflow': 'auto'})
        div = $('<div style="padding: 20px;"></div>')
        $viz.append(div)

        for score in @testScores
            title = $("""<h4 style="text-decoration: underline; font-size: 16px;">#{ score['MEASURE_NAME'] }</h4>""")
            div.append(title)

            if score['MEASURE_ABBREV'] != ''
                title.append(" (#{ score['MEASURE_ABBREV'] }) ")
            if score['YEAR'] != ''
                title.append(" - #{score['YEAR'] }")

            if score['SUBJECT_NAME'] != ''
                div.append("<small>Subject: #{ score['SUBJECT_NAME'] }</small>")
            if score['GRADE'] != ''
                div.append("<p>Educational Grades: #{ score['GRADE'] }</p>")
            if score['MEASURE'] != ''
                p = $("<p>Score: #{ score['MEASURE'] }</p>")
                div.append(p)
                if score['MEASURE_UNITS'] != ''
                    p.append(" #{ score['MEASURE_UNITS'] }")
                if score['RESULT_TYPE'] != ''
                    p.append(" (#{ score['RESULT_TYPE'] })")

    renderStats: (name, $viz) =>
        if name == "Map"
            @renderMap($viz)
        else if name == "Enrollment by Grade"
            @renderEnrollment($viz)
        else if name == "Key Stats"
            @renderKeyStats($viz)
        else if name == "Programs Offered"
            @renderPrograms($viz)
        else if name == "Test Score Details"
            @renderTestScores($viz)

class AR.SingleStatsDrilldown extends AR.BaseMultiDrilldownSvg

    cssClass: 'single-stats-drilldown'

    constructor: (options) ->
        super(options)
        @title = @getJson('title')
        @stats = @getJson('stats')
        @mode = @getJson('mode')
        @dataLabels = @getJson('dataLabels')
        @unitLabel = @getJson('unitLabel')
        @labelSpace = @getJson('labelSpace') or 100

    getStatsNames: () =>
        options = []
        options.push(@title)
        return options

    renderStats: (statsName, $viz) =>
        data = @stats
        new AR.Histogram
            $el: $viz
            mode: @mode
            data: @stats
            dataLabels: @dataLabels
            unitLabel: @unitLabel
            labelSpace: @labelSpace

class AR.SocialProofView extends WEB.BaseView

    template: 'socialProof'
    cssClass: 'social-proof'

    constructor: (options) ->
        super(options)
        @tweetSet = 0
        @cycleTweets()

    cycleTweets: () =>
        @$('.social-proof').show()
        @$('.tweets').hide()
        current = @tweetSet % @$('.tweets').length
        @$('.tweets').slice(current, current+1).fadeIn(1000)
        WEB.delay 10000, =>
            @tweetSet += 1
            @cycleTweets()

class AR.SocialShare extends WEB.BaseView

    cssClass: 'social-share'

    attachHandlers: () =>
        @$el.click (event) =>
            event.preventDefault()
            target = @$el.attr('href')
            window.open(target, 'social', 'scrollbars=no,width=600,height=300')

class AR.StickyHeader extends WEB.BaseView

    cssClass: "sticky-header"

    constructor: (@options) ->
        super(@options)
        if not AR.isMobile()
            WEB.later => @distributeLinks()

    attachHandlers: () =>
        # TODO: is this cross-browser? using jquery makes scrolling pretty slow...
        if not AR.isMobile()
            window.addEventListener('scroll', @onScroll)
            @$('a').click(@onClickDesktop)
        else
            @$('a').click(@onClickMobile)

    distributeLinks: () =>
        # alternatively, it might be able to compute the optimal padding
        @$el.css('opacity', 0)
        @$links = @$('.report-sections')
        @startHeight = @$links.height()
        @distributingLinks = true
        for i in [10...128]
            @distributeLinksTrial(i)

    distributeLinksTrial: (padding) =>
        WEB.later =>
            if @distributingLinks
                padding += 1
                @$('a').css('padding', "24px #{ padding }px")

                newHeight = @$links.height()
                if (newHeight > @startHeight) or (padding >= 128)
                    @$('a').css('padding', "24px #{ padding-1 }px")
                    @$el.css('opacity', 1)
                    @distributingLinks = false

    onClickDesktop: (event) =>
        event.preventDefault()
        target = $(event.currentTarget).attr('href')
        location = $(target).offset().top - @$('.report-sections').height()
        $('html,body').animate({scrollTop: location})

    onClickMobile: (event) =>
        event.preventDefault()

    onScroll: (event) =>
        naturalLocation = @$el.offset().top
        if window.scrollY > naturalLocation
            if not @isBelow
                @$('.report-sections').addClass('sticky')
                @isBelow = true
        else
            if @isBelow
                @$('.report-sections').removeClass('sticky')
                @isBelow = false

        # find the curent section
        @active = null
        scroll = window.scrollY
        $('.report-section-container').each (i, el) =>
            $el = $(el)
            top = $el.offset().top
            if scroll + 250 > top
                @active = $el.attr('id')

        @$('a').removeClass('active')
        if @active?
            @$("a[href=##{ @active }]").addClass('active')

class AR.StreetMapDrilldown extends AR.BaseMapDrilldown

    cssClass: "street-complaint-map"
    defaultOptions: {
        zoom: 18
        url: '/service/load-street-complaints/'
        COLOR_MAP: {
            'Street Light Condition': "#9a5cb4"
            'Street Condition': "#35495d" # -> Road Condition
            'Scaffold Safety': "#3a99d8"
            'Dead Tree': "#f1c93c"
            'Sidewalk Condition': "#39ca74"
            'Broken Parking Meter': "#e47e30"
            'Broken Muni Meter': "#e47e30"
        }
    }

class AR.StreetTreeMap extends AR.BaseMapDrilldown

    cssClass: "street-tree-map"
    defaultOptions: {
        zoom: 18
        hasDither: false
        url: '/service/load-street-trees/'
        COLOR_MAP: {tree: "#39ca74"}
    }

class AR.TaxisByHour extends AR.BarChartDrilldown

    cssClass: 'taxis-by-hour'

    TIMES: [
        "12:00 AM",
        "1:00 AM",
        "2:00 AM",
        "3:00 AM",
        "4:00 AM",
        "5:00 AM",
        "6:00 AM",
        "7:00 AM",
        "8:00 AM",
        "9:00 AM",
        "10:00 AM",
        "11:00 AM",
        "12:00 PM",
        "1:00 PM",
        "2:00 PM",
        "3:00 PM",
        "4:00 PM",
        "5:00 PM",
        "6:00 PM",
        "7:00 PM",
        "8:00 PM",
        "9:00 PM",
        "10:00 PM",
        "11:00 PM",
    ]

    constructor: (@options) ->
        super(@options)
        @data = @getJson('data')
        @mode = @getJson('mode')
        @title = @getJson('title')

    getLabels: () =>
        if not AR.isMobile()
            return @TIMES
        else
            return (@TIMES[2*i] for i in [0...12])

    getDataGroups: () =>
        if not AR.isMobile()
            return [@data]
        else
            return [(@data[2*i] for i in [0...12])]

    getXUnitLabel: () =>
        return "Time of Day"

    getYUnitLabel: () =>
        if @mode == 'wait'
            return "Wait Time (in seconds)"
        else if @mode == 'taxis'
            return "Taxis"
        else if @mode == 'pickups'
            return "Pickups"
        else if @mode == 'dropoffs'
            return "Dropoffs"

class AR.TimeLeavingForWorkStats extends AR.BaseMultiDrilldownSvg

    cssClass: 'time-leaving-for-work-stats'

    constructor: (@options) ->
        super(@options)
        @timeLeavingForWork = @getJson('timeLeavingForWork')
        @commuteTimes = @getJson('commuteTimes')


    getStatsNames: () =>
        options = []
        options.push('Time Leaving for Work')
        options.push('Time Spent Commuting')
        return options

    renderStats: (statsName) =>
        $viz = @$('.stats-viz')
        if statsName == "Time Leaving for Work"
            new AR.Histogram
                $el: $viz
                mode: 'simple'
                data: @timeLeavingForWork
                unitLabel: "Time Leaving for Work"
                labelSpace: 160
        else if statsName == "Time Spent Commuting"
            new AR.Histogram
                $el: $viz
                mode: 'simple'
                data: @commuteTimes
                unitLabel: "Commute Time (in Minutes)"
                labelSpace: 100

class AR.ThanksForUpgradingModal extends AR.ModalView

    template: 'thanksForUpgradingModal'

    # CONSTRUCTOR: LOOK FOR STRING
    constructor: (type) ->
        super()
        if type == "ALREADY-REGISTERED"
            this.$("h2").text(
                """Successfully Logged In!"""
            )
            this.$("p").text(
                """Thanks for being a premium user. AddressReport loves you."""
            )
            this.$(".button").text(
                """Generate that AddressReport!"""
            )

class AR.Unsubscribe extends WEB.BaseView

    cssClass: 'unsubscribe-alert'

    constructor: (options) ->
        super(options)
        @unsubscribeAlert()

    unsubscribeAlert: () =>
        qs = WEB.getUrlHash()
        property = qs['property']
        if property
            $.ajax
                url: '/service/subscribe-alerts/'
                data:
                    property: property
                    subscribe: false

class AR.UnsubscriptionModal extends AR.ModalView

    template: 'confirmUnsubscriptionModal'

    constructor: (@options) ->
        super(@options)
        @unsubscribe = @options.unsubscribeMethod

    attachHandlers: () =>
        @$el.on('click', '.yes-unsubscribe', @unsubscribeAndClose)
        @$el.on('click', '.no-unsubscribe', @collapse)
        @$el.on('click', '.modal-close', @collapse)

    unsubscribeAndClose: () =>
        @unsubscribe()
        @collapse()

class AR.User extends WEB.Model

    constructor: (data) ->
        super(data)
        if @plan?
            @plan = new AR.UserPlan(@plan)

    identify: () ->
        AR.logIdentity(@id, @email)

class AR.UserPlan extends WEB.Model

    constructor: (data) ->
        super(data)
        @starts = new Date(@starts)
        @ends = new Date(@ends)

class AR.VideoLandingPage extends WEB.BaseView

    cssClass: 'video-landing-page'

    constructor: (options) ->
        super(options)

        if not AR.isMobile()
            @$('input').focus()
        else
            @$('input').attr('placeholder', 'Type any address...')

class AR.VoterStats extends AR.BaseMultiDrilldownSvg

    cssClass: 'voter-stats'

    getStatsNames: () =>
        options = []
        options.push('Voter Registrations')
        return options

    renderStats: (statsName, $viz) =>
        if statsName == "Voter Registrations"
            new AR.Histogram
                $el: $viz
                mode: 'simple'
                data: @stats
                unitLabel: "Registered Party"
                labelSpace: 130

class AR.WorkStatsDrilldown extends AR.BaseMultiDrilldownSvg

    cssClass: 'census-work-stats'

    getStatsNames: () =>
        options = []

        if @stats.education?
            options.push('Education')
        if @stats.timeLeavingForWork?
            options.push('Time Leaving For Work')
        if @stats.commuteTimes?
            options.push('Commute Times')
        if @stats.commuteMethods?
            options.push('Commute Methods')

        return options

    renderStats: (statsName, $viz) =>
        if statsName == "Education"
            new AR.Histogram
                $el: $viz
                mode: 'simple'
                data: @stats.education
                unitLabel: "Highest Level Achieved"
                labelSpace: 200
        else if statsName == "Time Leaving For Work"
            new AR.Histogram
                $el: $viz
                mode: 'simple'
                data: @stats.timeLeavingForWork
                unitLabel: "Time Leaving For Work"
                labelSpace: 160
        else if statsName == "Commute Times"
            new AR.Histogram
                $el: $viz
                mode: 'simple'
                data: @stats.commuteTimes
                unitLabel: "Commute Time in Minutes"
                labelSpace: 100
        else if statsName == "Commute Methods"
            new AR.Histogram
                $el: $viz
                mode: 'simple'
                data: @stats.commuteMethods
                unitLabel: "Primary Commute Method"
                labelSpace: 150

# Non-Class Stuf

AR.logGa = (category, action, label, value) ->
    if value?
        value = Math.ceil(value)
    console.log "GA: #{ category }:#{ action } #{ label } $#{ value }"
    window.ga('send', 'event', category, action, label, value)

AR.requireMembership = (options) ->
    if AR.USER.status == 'guest'
        new AR.LoginRegisterModal
            buttonText: options.buttonText
            context: options.context
            disableClose: options.disableClose
            emailOnly: options.emailOnly
            loginTitle: options.loginTitle
            mode: options.mode || 'register'
            registerTitle: options.registerTitle
            subscribeTitle: options.subscribeTitle
            success: options.success
    else
        options.success("ALREADY-REGISTERED")

AR.signupForAlerts = (success) ->
    property = WEB.getJson('propertySlug')
    AR.log 'Subscribed for alerts',
        property: property
    $.ajax
        url: '/service/subscribe-alerts/'
        data:
            property: property
            subscribe: true
            success: success

$ ->
    AR.USER = new AR.User(AR.CLIENT_STATE.user)
    AR.logSet({status: AR.USER.status})
    AR.USER.identify()
