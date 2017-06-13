window.AR = {}

class AR.AddressAutocomplete extends WEB.BaseView

    cssClass: "address-autocomplete"
    template: 'addressAutocomplete'

    constructor: (@options) ->
        super(@options)
        @types = @options?.types or @getJson('types') or null
        @action = @options?.action or @getJson('action') or 'report'
        
        @$('input').typeahead({
            minLength: 2
            highlight: true
        }, {
            display: 'name'
            source: @search
            templates:
                suggestion: @renderResult
        })

        @xhrs = []

    attachHandlers: () =>
        @$el.on('typeahead:select', @onSelect)
        @$el.keypress(@onKeypress)

    onKeypress: (event) =>
        if event.which == 13 # enter key
            console.log "ENTER"
            console.log @results
            if @results? and @results.length > 0
                @onSelect(null, @results[0])
            else
                if @action == 'report'
                    params = {
                        query: @$('.tt-input').val(),
                        types: JSON.stringify(@types),
                        bias: JSON.stringify(WEB.getJson('bias'))
                    }
                    WEB.navigate("/find/#{ WEB.stringifyHash(params) }")

    onSelect: (event, value) =>
        if @action == 'report'
            WEB.navigate(value.reportUrl)
        else if (@action == 'alert-block') or (@action == 'report-block')
            params = {
                query: value.name,
                callback: @action,
            }
            console.log params
            console.log WEB.stringifyHash(params)
            WEB.navigate("/find-address/#{ WEB.stringifyHash(params) }")
        else if @action == 'dom-event'
            @$el.trigger('autocomplete-selected', value)

    renderResult: (value) =>
        if value.type == 'address'
            return """
                <div class="autocomplete-result">
                    #{ value.name }
                    <span class="type">
                        Address
                    </span>
                </div>
            """
        else if value.type == 'area'
            return """
                <div class="autocomplete-result">
                    #{ value.name }
                    <span class="type">
                        Neighborhood
                        <span class="detail">
                            in #{ value.cityName }, #{ value.cityState }
                        </span>
                    </span>
                </div>
            """
        else if value.type == 'city'
            return """
                <div class="autocomplete-result">
                    #{ value.name }
                    <span class="type">
                        City
                        <span class="detail">
                            in #{ value.cityState }
                        </span>
                    </span>
                </div>
            """
        else if value.type == 'zip'
            return """
                <div class="autocomplete-result">
                    #{ value.slug }
                    <span class="type">
                        Zip-code
                        <span class="detail">
                            in #{ value.cityName }, #{ value.cityState }
                        </span>
                </div>
            """

    search: (query, syncResults, asyncResults) =>
        for xhr in @xhrs
            xhr.abort()
        @xhrs = []

        xhr = $.ajax
            url: '/service/autocomplete/'
            data:
                query: query
                types: JSON.stringify(@types)
                bias: JSON.stringify(WEB.getJson('bias'))
            success: (data) =>
                @results = data.results
                asyncResults(data.results)
        @xhrs.push(xhr)

class AR.GoogleMap
    ###
        Light wrapper around a Google Map, providing simpler
        access to some of their features. In particular, you
        would generally use GeoJson to specify shapes and points
        rather than their nonsense.
    ###

    constructor: (options) ->
        if not options?
            options = {}

        $el = options.$el
        @$el = $el

        # defaults -- (should we just use extend?)
        if not options.zoom?
            options.zoom = 13
        if not options.scrollwheel?
            options.scrollwheel = false
        if not options.panControl?
            options.panControl = false
        if not options.streetViewControl?
            options.streetViewControl = false
        if not options.zoomControlOptions?
            options.zoomControlOptions = {
                position: google.maps.ControlPosition.LEFT_CENTER
            }

        # convert center
        if options.center?
            options.center = @convertGeoJson(options.center)[0] # assume point?

        @gmap = new google.maps.Map($el[0], options)
        @gmap.data.setStyle (feature) ->
            style = feature.getProperty('style')
            return style

        # event handlerz
        google.maps.event.addListener(@gmap, 'idle', @onBoundsChange)
        google.maps.event.addListener(@gmap, 'zoom_changed', @onZoomChange)

    addMarker: (location, options) =>
        if not options?
            options = {}

        options.position = @convertGeoJson(location)[0]
        options.map = @gmap
        return new google.maps.Marker(options)

    addCircle: (options) =>
        options.center = @convertGeoJson(options.center)[0]
        circle = new google.maps.Circle(options)
        circle.setMap(@gmap)

    addInfoWindow: (content, marker) =>
        info = new google.maps.InfoWindow({
            content: content
        })
        google.maps.event.addListener(
            marker,
            'click',
            () =>
                info.open(@gmap, marker)
        )
        return info

    addShape: (geoJson, properties) =>
        if not properties?
            properties = []
        if not properties.style?
            properties.style = {
                strokeColor: '#3a99d8'
                strokeOpacity: 0.8
                strokeWeight: 2
                fillColor: '#3a99d8'
                fillOpacity: 0.35
            }

        features = @gmap.data.addGeoJson
            type: 'Feature'
            geometry: geoJson
            properties: properties
        return features[0]

    convertGeoJson: (geoJson) =>
        # already converted
        if geoJson instanceof google.maps.LatLng
            return [geoJson]
        else if geoJson instanceof google.maps.Polygon
            return [geoJson]

        if geoJson.type == 'Point'
            coordinates = geoJson.coordinates
            return [new google.maps.LatLng(coordinates[1], coordinates[0])]
        else if geoJson.type == 'Polygon'
            # TODO: this is the exterior only... what if there are holes?
            convertedPoints = []
            for point in geoJson.coordinates[0]
                convertedPoints.push(new google.maps.LatLng(point[1], point[0]))
            return [new google.maps.Polygon({paths: convertedPoints})]
        else if geoJson.type == 'MultiPolygon'
            polygons = []
            for coordSet in geoJson.coordinates
                subshapes = @convertGeoJson
                    type: 'Polygon'
                    coordinates: coordSet
                for subshape in subshapes
                    polygons.push(subshape)
            return polygons
        else if geoJson.type == 'GeometryCollection'
            polygons = []
            for geometry in geoJson.geometries
                if geometry.type == 'Polygon'
                    for subshape in @convertGeoJson(geometry)
                        polygons.push(subshape)
            return polygons

    getBoundsOfShape: (shape) =>
        shapes = @convertGeoJson(shape)
        console.log shapes
        bounds = new google.maps.LatLngBounds()
        for shape in shapes
            paths = shape.getPaths()
            for i in [0...paths.getLength()]
                path = paths.getAt(i)
                for ii in [0...path.getLength()]
                    bounds.extend(path.getAt(ii))
        return bounds

    hideLoadingMessage: () =>
        els = @$el.find(".loading-popup, .loading-overlay")
        els.hide()

        WEB.delay 500, =>
            els.remove()

    offsetByPixels: (x, y) =>
        center = @gmap.getCenter()
        pixelCenter = @gmap.getProjection().fromLatLngToPoint(center)
        pixelOffset = new google.maps.Point(
            pixelCenter.x + x / Math.pow(2, @gmap.getZoom()),
            pixelCenter.y + y / Math.pow(2, @gmap.getZoom())
        )
        latLonOffset = @gmap.getProjection().fromPointToLatLng(pixelOffset)
        @gmap.setCenter(latLonOffset)

    onBoundsChange: () =>
        # whatever you want, man!

    onZoomChange: () =>
        # your call, bro!

    showLoadingMessage: () =>
        @$el.append($(
            """
                <div class="loading-popup">
                    <div class="loading-message">
                        <img src="#{ WEB.resource('/image/loading-256-dark-on-white.gif') }" />
                    </div>
                </div>
                <div class="loading-overlay"></div>
            """
        ))

    zoomTo: (shape) =>
        @gmap.fitBounds(@getBoundsOfShape(shape))

class AR.GoogleMapDot extends google.maps.OverlayView

    constructor: (@location, @color, @text) ->
        @div = document.createElement('div')

    addClass: (cssClass) =>
        if @div.className
            cssClass = " " + cssClass
        @div.className += cssClass

    onAdd: () =>
        @addClass('map-dot')
        @div.style.backgroundColor = @color

        if @text?
            textNode = document.createTextNode(@text)
            @div.appendChild(textNode)

        panes = @getPanes()
        panes.overlayLayer.appendChild(@div)

    draw: () =>
        overlayProjection = @getProjection()
        loc = overlayProjection.fromLatLngToDivPixel(@location)
        @div.style.left = (loc.x) + 'px'
        @div.style.top = (loc.y) + 'px'
        WEB.later =>
            @addClass('visible')

class AR.HeaderView extends WEB.BaseView

    cssClass: "header"

    ###
        Expandable Header
    ###
    attachHandlers: () ->
        @$('.expand').click(@toggle)
        @$('.close img').click(@toggle)

    expand: () =>
        @$('.nav').addClass('visible')
        @$('.expand').hide()
        @$('.close').first().show()

        # move the search input to the nav
        if AR.isMobile()
            @$('.address-autocomplete')
                .show()
                .prependTo(@$('.nav'))

    collapse: () =>
        @$('.nav').removeClass('visible')
        @$('.expand').show()
        @$('.close').first().hide()
        # put the address-autocomplete in the right place
        @$('.nav .address-autocomplete')
            .hide()
            .insertAfter('.expand')

    toggle: () =>
        if @$('.nav').hasClass('visible')
            @collapse()
        else
            @expand()

class AR.ModalView extends WEB.BaseView

    destroyOnCollapse: true

    constructor: (@options) ->
        super(@options)
        @inject()
        @expand()

        if @options.disableClose
            @$('.modal-close').hide()

    attachHandlers: () =>
        @$el.on('expand', @expand)
        @$el.on('collapse', @collapse)

        if !@options.disableClose
            @$('.modal-cover').click(@close)
            @$('.modal-close').click(@close)

    expand: () =>
        $('.modal').not(@$el).trigger('collapse')
        @$el.show()

        if not AR.isMobile()
            @$el.addClass('enter')
            WEB.delay 500, =>
                @$el.removeClass('enter')

    close: () =>
        @$el.trigger('close')
        @collapse()

    collapse: () =>
        @$el.addClass('exit')
        destroy = () =>
            if @destroyOnCollapse
                @$el.remove()
            else
                @$el.removeClass('exit')
                @$el.hide()

        if AR.isMobile()
            destroy()
        else
            WEB.delay(500, destroy)

    shake: () =>
        @$el.addClass('shake')
        WEB.delay 500, =>
            @$el.removeClass('shake')

class AR.PaginatedTable extends WEB.BaseView

    cssClass: 'paginated-table'
    pageButtonsToShow: 11 # should be odd...

    constructor: (@options) ->
        super(@options)
        @perPage = 20
        total = @$('tbody tr').length
        @pages = Math.ceil(total / @perPage)
        @renderPageButtons()
        @currentPage = 1
        @renderPage()

    goToPage: (page) =>
        @currentPage = page
        @renderPage()

    renderPage: () =>
        if @pages > 1
            start = @perPage * (@currentPage - 1)
            $rows = @$('tbody tr')
            $rows.hide()
            $rows.slice(start, start+@perPage).show()
            @$pager.find('.page').removeClass('active')
            @$pager.find('.page').slice(@currentPage-1, @currentPage).addClass('active')

            if @pages > @pageButtonsToShow
                perSide = (@pageButtonsToShow - 3) / 2
                start = @currentPage - perSide
                end = @currentPage + perSide
                if start <= 1
                    start = 2
                    end = start + 2 * perSide
                else if end >= @pages
                    end = @pages - 1
                    start = end - 2 * perSide

                @$pager.find('.page').addClass('hidden')
                @$pager.find('.page').first().removeClass('hidden')
                @$pager.find('.page').last().removeClass('hidden')
                @$pager.find('.page').slice(start-1, end).removeClass('hidden')

    renderPageButtons: () =>
        if @pages > 1
            @$pager = $("""<div class="pager"></div>""").insertAfter(@$el)
            for page in [1..@pages]
                do (page) =>
                    $page = $("""<div class="page">#{ page }</div>""").appendTo(@$pager)
                    $page.click => @goToPage(page)

class AR.TextModal extends AR.ModalView
    ###
        options:
            name: heading
            text: body text
    ###

    template: 'textModal'

AR.browserDetect = () ->
    userAgent = navigator.userAgent

    if userAgent.indexOf("Chrome") > -1
        return "Chrome"
    else if userAgent.indexOf("Safari") > -1
        return "Safari"
    else if userAgent.indexOf("Opera") > -1
        return "Opera"
    else if userAgent.indexOf("Firefox") > -1
        return "Firefox"
    else if userAgent.indexOf("MSIE") > -1
        return "Internet Explorer"

AR.isMobile = () ->
    return $(window).width() < 980

AR.isPhone = () ->
    isAndroid = /Android/i.test(navigator.userAgent)
    isIos = /iPhone|iPad|iPod/i.test(navigator.userAgent)
    return (isAndroid or isIos)

AR.log = (event, fields) ->
    console.log(event)
    console.log(fields)
    _kmq.push(['record', event, fields])

AR.logIdentity = (id, email) ->
    if email?
        _kmq.push(['identify', email])
        _kmq.push(['alias', id, email])
    else
        _kmq.push(['identify', id])

AR.logSet = (fields) ->
    _kmq.push(['set', fields])

AR.COLORS = [
    '#9a5cb4',
    '#f1c93c',
    '#3a99d8',
    '#35495d',
    '#39ca74',
    '#e54d42',
    '#e47e30',
]

$ ->
    WEB.STATIC_URL = WEB.getJson('staticUrl')

    WEB.ClassUtil::setClassNames(AR)
    WEB.BaseView::attach(AR)
    AR.CLIENT_STATE = WEB.getJson('clientState', $('body'))

    # browser detect / mobile
    AR.logSet
        'Mobile Display': AR.isMobile()
        'Using a Phone': AR.isPhone()
        'Browser': AR.browserDetect()
