window.WEB = {}

class WEB.BaseView
    
    cssClass: null
    template: null # nunjucks path
    
    attach: (namespace, $context) ->
        if not $context?
            $context = $('html')
        for key, cls of namespace
            if WEB.ClassUtil::isSubclass(cls, WEB.BaseView)
                cssClass = cls::cssClass
                if cssClass?
                    try
                        $context.find(".#{ cssClass }").each (i, el) ->
                            if (not el[key]?) and (not el.dynamic)
                                view = new cls
                                    $el: $(el)
                                    attachment: true
                                el[key] = view
                                cls.V = view # only useful for singletons, should we mark that?
                    catch e
                        console.error e.stack
    
    constructor: (@options) ->
        if not @options?
            @options = {}

        if @options.$el?
            @$el = @options.$el
        else
            @$el = @render()

        @postRender()

        @attachHandlers()

        if not @options.attachment
            @$el[0].dynamic = true

    $: (selector) =>
        return @$el.find(selector)

    attachHandlers: () =>
        # do whatever you want, it's all you bro

    getJson: (name) =>
        return WEB.getJson(name, @$el)

    getTemplateContext: () ->
        context = {
            self: @
        }
        $.extend(context, @options)
        return context

    inject: (parent) =>
        if not parent?
            parent = $('body')

        if parent instanceof WEB.BaseView
            parent = parent.$el

        parent.append(@$el)

    postRender: () =>

    render: () =>
        if @template 
            context = @getTemplateContext()
            return WEB.renderTemplate(@template, context)
        else
            return $("""<div class="#{ @cssClass }"></div>""")

class WEB.ClassUtil
    ###
        Some prototype methods for managing classes more naturally
    ###
    isSubclass: (subClass, superClass) ->
        # checks if one class is a subclass of another, using coffee inheritance chains
        if subClass?
            while subClass.__super__?
                if subClass.__super__ is superClass::
                    return true
                subClass = subClass.__super__.constructor
        return false

    setClassNames: (namespace) ->
        # sets the name property for all classes
        for key, value of namespace
            if value?
                value.__name__ = key

class WEB.Model

    constructor: (data) ->
        for key, value of data
            @[key] = value

class WEB.OnceFunction

    constructor: (@cb) ->
        @hasRun = false

    run: () =>
        if not @hasRun
            @hasRun = true
            @cb?()

WEB.OnceFunction.make = (cb) ->
    func = new WEB.OnceFunction(cb)
    return func.run

WEB.UA = 
    
    isAndroid: () ->
        return /Android/i.test(navigator.userAgent)

    isCrawler: () ->
        return /aol/i.test(navigator.userAgent) or\ 
            /ask/i.test(navigator.userAgent) or\ 
            /google/i.test(navigator.userAgent) or\ 
            /yahoo/i.test(navigator.userAgent) or\ 
            /bing/i.test(navigator.userAgent) or\
            /msn/i.test(navigator.userAgent) or\
            /adidx/i.test(navigator.userAgent) or\
            /baidu/i.test(navigator.userAgent)
    
    isIe : () ->
        return /msie/i.test(navigator.userAgent) or\ 
            /rv:11\.0/i.test(navigator.userAgent)

    isIframe: () ->
        return window.self != window.top
    
    isIphone: () ->
        return /iPhone/i.test(navigator.userAgent) or\
            /iPod/i.test(navigator.userAgent)

    isIos: () ->
        return /iPhone/i.test(navigator.userAgent) or\
            /iPod/i.test(navigator.userAgent) or\
            /iPad/i.test(navigator.userAgent)

    isPhone: () ->
        return WEB.UA.isAndroid() or WEB.UA.isIphone()

WEB.attachExitIntent = (options) ->
    cb = options.cb
    namespace = options.namespace or 'exitIntent'
    tokenName = options.tokenName or 'exitIntentViewed'

    $(window).on "mouseleave.#{namespace}", (ev) =>
        if ev.clientY < 20 && !sessionStorage.getItem(tokenName) && !WEB.UA.isIframe() && !WEB.UA.isPhone()
            $(window).trigger('exit-intent-fired')
            sessionStorage["#{tokenName}"] = true
            cb()
            $(window).off("mouseleave.#{namespace}")

WEB.augmentLinkWithTracking = ($link, eventName, eventData) ->
    $link.on 'click', (ev) ->
        target = ev.currentTarget
        url = target.href
        ev.preventDefault()
        if not target._isNavRunning
            target._isNavRunning = true
            WEB.track eventName, eventData, ->
                WEB.navigate(url)

WEB.augmentUrl = (update) ->
    current = WEB.getUrlHash()
    $.extend(current, update)
    stringified = WEB.stringifyHash(current)
    path = window.location.pathname
    return path + stringified

WEB.commas = (number) ->
    return number.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",")

WEB.deepochify = (dt) ->
    return new Date(dt * 1000)

WEB.delay = (time, cb) ->
    setTimeout(cb, time)

WEB.epochify = (date) ->
    return Math.round(date.getTime() / 1000)

WEB.fireGtmEvent = (eventName, eventProperties) ->
    payload = {
        event: eventName
    }

    if eventProperties?
        $.extend(payload, eventProperties)
    
    console.log "Fire GTM: #{ eventName }"
    console.log eventProperties
    
    window.dataLayer.push(payload)

WEB.later = (cb) ->
    setTimeout(cb, 100)

WEB.getJson = (name, $parent) ->
    if not $parent?
        $parent = $('body')
    json = $parent.find("""script[name="#{name}"]""").text()
    if json
        return JSON.parse(json)

WEB.getUrlHash = (url) ->
    qs = {}
    search = window.location.search

    if search != ""
        params = search.replace('?', '').split('&')

        for param in params
            if param != ""
                param = param.split('=')
                value = param[1]?.replace(/\+/g, '%20')
                qs[param[0]] = decodeURIComponent(value)
    return qs

WEB.getUrlParameter = (name) ->
    re = RegExp("[?|&]#{ name }=(.+?)(&|$)")
    match = re.exec(location.search)
    if match?
        value = match[1].replace(/\+/g, '%20')
        return decodeURIComponent(value)

WEB.makeApp = (module) ->
    $ ->
        WEB.ClassUtil::setClassNames(module)
        WEB.BaseView::attach(module)

WEB.money = (amount, useCents) ->
    formatted = amount.toFixed(2)
    [dollars, cents] = formatted.split(".")
    dollars = WEB.commas(dollars)
    if useCents
        return "#{ dollars }.#{ cents }"
    else
        return "#{ dollars }"

WEB.navigatePost = (url, params) ->
    $form = $("""<form action="#{ url }" method="POST"></form>""")
    for key, value of params
        $input = $("""<input type="hidden" name="#{ key }" />""")
        $input.val(value)
        $form.append($input)
    $('body').append($form)
    $form.submit()

WEB.navigate = (url) ->
    # This method is a replacement for window.open which
    # creates a dummy link and clicks it, because IE
    # does not preserve referrer
    if WEB.UA.isIe()
        referLink = document.createElement('a')
        referLink.href = url
        document.body.appendChild(referLink)
        referLink.click()
    else
        window.open(url, '_self')

WEB.resource = (path) ->
    return WEB.STATIC_URL + path

WEB.setJson = (name, value, $parent) ->
    if not $parent?
        $parent = $('body')
    $target = $parent.find("script[name=#{ name }]")
    $target.text(JSON.stringify(value))

WEB.stringifyHash = (qsObj) ->
    return "?#{ $.param(qsObj) }"

WEB.renderTemplate = (name, context) ->
    if not context?
        context = {}
    $.extend(context, WEB.TEMPLATE_GLOBALS)
    html = window.nunjucks.render(name, context)
    return $(html)

WEB.track = (name, data, cb) ->
    console.log("TRACK: #{name}")
    console.log(data)
    ocb = WEB.OnceFunction.make(cb)
    _kmq.push(['record', name, data, ocb])

WEB.INIT = (namespace) ->
    WEB.ClassUtil::setClassNames(namespace)
    WEB.BaseView::attach(namespace)

# this can be modified by the app
WEB.TEMPLATE_GLOBALS = {
    commas: WEB.commas
    money: WEB.money
    resource: WEB.resource
}

# this can be modified by the app
WEB.STATIC_URL = "/resource" 

window.console = window.console || {
    log: () -> # nothing
    error: () -> # again, nothing
}

$ -> 
    WEB.ClassUtil::setClassNames(WEB)
    WEB.BaseView::attach(WEB)