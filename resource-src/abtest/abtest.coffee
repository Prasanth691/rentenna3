ABT = {}

class ABT.ExperimentView extends WEB.BaseView

    cssClass: 'client-experiments'

    constructor: (options) ->

        @experimentId = @getJson('experimentId')
        @experimentUrl = @getJson('experimentUrl')

        @variations = []
        
        super(options)

        @jsEditor = CodeMirror.fromTextArea @$('#js-editor')[0],
            theme: 'blackboard'
            lineNumbers: true
            mode: "text/javascript"
        @cssEditor = CodeMirror.fromTextArea @$('#css-editor')[0],
            theme: 'blackboard'
            lineNumbers: true
            mode: "text/css"

        for variation in @getJson('variations')
            @addVariation(variation)
        
        if @variations[0]?
            @edit(@variations[0])
            $('.variation').slice(0, 1).addClass('active')

    addVariation: (variation) =>
        if not variation?
            variation = {}
        @variations.push(variation)
        variationView = new ABT.VariationView
            variation: variation
            experimentId: @experimentId
            experimentUrl: @experimentUrl
        @$('.variations').append(variationView.$el)
        @edit(variation)

    attachHandlers: () =>
        @$el.on('edit-request', (event, variation) => @edit(variation))
        @$el.on('preview-request', (event, variation) => @preview(variation))
        @$el.on('click', '.option.js', => @showEditor('js'))
        @$el.on('click', '.option.css', => @showEditor('css'))
        @$el.submit(@updateVariations)
        @$el.on 'click', '.add-variation', (event) => 
            event.preventDefault()
            @addVariation({weight: 1.0})

    edit: (variation) =>
        @saveEditors()
        @activeVariation = variation
        @jsEditor.setValue(variation.js or "")
        @cssEditor.setValue(variation.css or "")

    saveEditors: () =>
        if @activeVariation?
            @activeVariation.js = @jsEditor.getValue()
            @activeVariation.css = @cssEditor.getValue()

    updateVariations: (event) =>
        @saveEditors()
        @$('input[name=variations]').val(JSON.stringify(@variations))

    showEditor: (which) =>
        @$('.editor-container').hide()
        @$(".#{ which }-editor").show()
        @$('.option').removeClass('active')
        @$(".option.#{ which }").addClass('active')
        WEB.later =>
            @cssEditor.refresh()
            @jsEditor.refresh()

class ABT.VariationView extends WEB.BaseView

    template: 'variationView'

    constructor: (@options) ->
        super(@options)
        @variation = @options.variation

    attachHandlers: () =>
        @$('.edit').click(@edit)
        @$('.delete').click(@delete)
        @$('.name').change(@update)
        @$('.weight').change(@update)

    delete: (event) =>
        event.preventDefault()
        @$el.fadeOut()
        @variation.deleted = true

    edit: (event) =>
        event.preventDefault()
        $('.variation').removeClass('active')
        @$el.addClass('active')
        @$el.trigger('edit-request', @variation)

    update: () =>
        @variation.name = @$('.name').val()
        @variation.weight = parseFloat(@$('.weight').val())

WEB.makeApp(ABT)