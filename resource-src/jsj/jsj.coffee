class AR.ExplosionMap extends WEB.BaseView

    cssClass: "explosion-map"

    MONTHS: [
        'January',
        'February',
        'March',
        'April',
        'May',
        'June',
        'July',
        'August',
        'September',
        'October',
        'November',
        'December'
    ]

    constructor: (@options) ->
        super(@options)
        @focus = @getJson('focus')
        @createMap()
        @dots = @getJson('data')
        @size = @getJson('size') or 3
        @speed = @getJson('speed') or 1
        @renderDots()

    attachHandlers: () =>
        @$('.reset').click(@renderDots)

    createMap: () =>
        # TODO: also bounds
        @map = new AR.GoogleMap
            $el: @$('.map')
            zoom: 13
        bounds = new google.maps.LatLngBounds(
            new google.maps.LatLng(@focus[1], @focus[0]),
            new google.maps.LatLng(@focus[3], @focus[2])
        )
        console.log bounds
        @map.gmap.fitBounds(bounds)
        window.MAP = @map

    renderDots: () =>
        if AR.isPhone()
            targetDps = 5
        else
            targetDps = 30

        @$('.reset').removeClass('visible')
        @start = @dots[0].d
        @end = @dots[@dots.length-1].d
        @duration = @end-@start

        delay = 0

        avgDps = @dots.length / @duration
        multiplier = targetDps / 1000 / avgDps
        
        for dot in @dots
            delay = (dot.d - @start) / multiplier
            @renderDot(dot, delay)
        WEB.delay delay, =>
            @$('.reset').addClass('visible')

    renderDot: (dot, delay) =>
        WEB.delay delay, =>
            location = new google.maps.LatLng(
                dot.l[1],
                dot.l[0],
            )
            gdot = new AR.GoogleMapDot(location, dot.c)
            gdot.setMap(@map.gmap)
            gdot.addClass("explode-#{ @size }")
            date = new Date(dot.d * 1000)
            @$('.current').text(date.getYear()+1900)

            progress = (dot.d - @start) / (@duration)
            @$('.now').css('width', "#{ progress * 100 }%")

class AR.Jsj extends WEB.BaseView

    cssClass: 'jsj'

    constructor: (options) ->
        super(options)
        AR.log 'Viewed a JSJ page',
            'Jsj Slug': @getJson('jsjSlug')