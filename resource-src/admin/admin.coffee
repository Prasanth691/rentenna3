
class AR.BlogEditor extends WEB.BaseView

    cssClass: 'blog-editor'

    constructor: (@options) ->
        super(@options)
        @slug = @getJson('slug')

    attachHandlers: () =>
        @$('input[name=title]').on('keyup change', @updateSlug)

    updateSlug: () =>
        if @slug == 'new'
            title = @$('input[name=title]').val()
            slug = title.toLowerCase()
            slug = slug.replace(/( )+/g, '-')
            slug = slug.replace(/[^0-9a-z\-]/g, '')
            @$('input[name=slug]').val(slug)

class AR.CollectionDescriptionEditor extends WEB.BaseView

    template: 'collectionDescriptionEditor'

    getTemplateContext: () =>
        return {
            description: window.PAYLOAD.meta.description,
        }

class AR.DataViewer extends WEB.BaseView

    cssClass: "data-viewer"

    attachHandlers: () ->
        @$('.view-embedded').click =>
            dataId = @$el.attr('data-embedded')
            expanded = new AR.DataViewerExpanded(dataId)
            expanded.inject()
            return false

class AR.DataViewerExpanded extends WEB.BaseView

    constructor: (dataId) ->
        pretty = JSON.stringify(window[dataId], undefined, 2)
        @$el = $("""
            <div class="data-viewer-expanded">
                <pre></pre>
                <div class="close">
                    Close <span class="fa fa-times"/>
                </div>
            </div>
        """)
        @$('pre').text(pretty)
        super(@$el)

    attachHandlers: () ->
        @$('.close').click => @$el.remove()

class AR.ImageUploader extends AR.ModalView
    ###
        Options are:
            success: callback(url)
            cancel: callback()
    ###

    template: 'imageUploader'

    constructor: (@options) ->
        super(@options)

    attachHandlers: () =>
        super()
        @$('button').click(@upload)
        @$el.on('close', @options.cancel)

    onFileLoad: (event) =>
        data = event.target.result
        $.ajax
            url: '/admin/upload-image/'
            type: 'POST'
            data:
                data: data
            success: @onUploadComplete
            error: @onUploadError

    onUploadComplete: (data) =>
        console.log data
        host = window.location.host
        imageUrl = "http://#{ host }/image/#{ data.id }"
        @collapse()
        @options.success(imageUrl)

    onUploadError: () =>
        @$('.loading').hide()
        @$('.form-field').show()

    upload: () =>
        files = @$('input[name=file]')[0].files
        file = files[0]

        # TODO: show error if failed?
        if file.type.match('image.*')
            @$('.loading').show()
            @$('.form-field').hide()
            reader = new FileReader()
            reader.onload = @onFileLoad
            reader.readAsDataURL(file)

class AR.RichTextEditor extends WEB.BaseView

    cssClass: 'rich-text-editor'

    constructor: (@$el) ->
        super(@$el)
        @id = _.uniqueId('editor-')
        @$el.attr('id', @id)
        tinymce.init
            file_browser_callback: @fileBrowse
            height: 800
            menubar: false
            selector: "##{ @id }"
            plugins: "image link",
            toolbar: "alignleft aligncenter alignright | bold italic | styleselect | link image | bullist numlist outdent indent"

    fileBrowse: (fieldName) =>
        $('.mce-floatpanel').hide()
        $('#mce-modal-block').hide()
        new AR.ImageUploader
            cancel: =>
                $('.mce-floatpanel').show()
                $('#mce-modal-block').show()
            success: (imageUrl) =>
                $('.mce-floatpanel').show()
                $('#mce-modal-block').show()
                $("##{ fieldName }").val(imageUrl)

class AR.PartnerBulkOps extends WEB.BaseView
    cssClass: "partner-bulk"

    constructor: (@options) ->
        super(@options)
        @populateLogs()
        @loadUrl = @getJson('loadUrl')
        @removeUrl = @getJson('removeUrl')

    attachHandlers: () =>
        @$(".load").click(@onLoad)
        @$(".remove").click(@onRemove)

    appendLog: (log) =>
        logs = @$(".logs")
        logs.append(@logSummary log)
        logs.append('<pre>' + JSON.stringify(log, null, 4) + '</pre>')

    logResult: (log) =>
        logs = @$(".logs")
        logs.prepend('<pre>' + JSON.stringify(log, null, 4) + '</pre>')
        summary = @logSummary log
        logs.prepend(summary)
        @$(".result").html(summary).show()

    logSummary: (log) =>
        status = if log.finished is true then "finished" else "processing"
        "<strong>Action: #{log.action}, 
        status: #{status}, 
        total partners processed: #{log.total}, 
        total lines read: #{log.totalLines}</strong>"

    populateLogs: () =>
        data = @getJson('logs')
        for item in data
            @appendLog(item)

    onLoad:(evt) =>
        @send(@loadUrl, @onSuccess, @onError)

    onRemove:(evt) =>
        @send(@removeUrl, @onSuccess, @onError)

    onSuccess:(data) =>
        @pullingUrl =  data.url
        WEB.delay 1000, => 
            @pulling(data.url)

    onError:(xhr, textStatus, error) =>
        @$(".progress").hide()
        msg = ''
        if xhr.responseJSON
            msg = xhr.responseJSON.error
        else
            msg = xhr.responseText
        @$(".warning").html(msg)

    onPullSuccess: (data) =>
        if data.finished
            @$(".progress").hide()
            @logResult(data)
        else
            WEB.delay 3000, =>
                @pulling()

    onPullError: (xhr, textStatus, error) =>
        @onError(xhr, textStatus, error)

    pulling:(url) =>
        if not url
            url = @pullingUrl
        $.ajax
            url: url
            type: 'GET'
            success: @onPullSuccess
            error: @onPullError

    send:(url, onSuccess, onError) =>
        path = @$("select").find("option:selected").val()
        if _.isEmpty(path)
            return
        @$(".progress").show()
        @$(".warning").empty()
        @$(".result").empty()
        $.ajax
            url: url
            type: 'POST'
            contentType: 'application/json'
            data:
                JSON.stringify({
                    "filePath" : path
                })
            success: onSuccess
            error: onError

class AR.SubPartnerSelect extends WEB.BaseView

    cssClass: "editSubPartner"

    attachHandlers: () =>
        @$el.change(@onChange)
            
    onChange:() =>
        url = @$el.find("option:selected").val()
        if url?.length > 0
            WEB.navigate(url)

class AR.CheckStates extends WEB.BaseView
    cssClass: "form-states"

    constructor: (@options) ->
        super(@options)
        @flagCheckAll()

    attachHandlers: () =>   
        @$('input[name=allStates]').click(@onCheckAllClick)
        @$('input[name=state]').click(@onStateClick)

    onCheckAllClick:(evt) =>
        checked = @$('input[name=allStates]').is(":checked")
        @$('input[name=state]').prop("checked", checked)

    onStateClick:(evt) =>
        @flagCheckAll()

    flagCheckAll:() =>
        checked = @$('input:checked[name=state]').length == @$('input[name=state]').length
        @$('input[name=allStates]').prop("checked", checked)

class AR.WarehouseCollection extends WEB.BaseView

    cssClass: "warehouse-collection"

    attachHandlers: () =>
        @$('.edit-description').click(@editDescription)
        @$('.save-tmp-collection').click(@saveTmpCollection)

    editDescription: () =>
        editor = new AR.CollectionDescriptionEditor()
        editor.inject(@$('.description').empty())

    saveTmpCollection: () =>
        window.location = "/admin/warehouse/save-collection/#{ window.PAYLOAD.collection }/"

class AR.UserExport extends WEB.BaseView
    cssClass: "export-users"

    constructor: (@options) ->
        super(@options)
        @exportUrl = @getJson('exportUserUrl')

    attachHandlers: () =>
        @$("button.export").click(@onExport)

    logResult: (log) =>
        @$(".log").html(log.display)
        
    populateLogs: () =>
        data = @getJson('logs')
        for item in data
            @appendLog(item)

    onExport:(evt) =>
        @send(@exportUrl, @onSuccess, @onError)

    onSuccess:(data) =>
        @pullingUrl =  data.url
        WEB.delay 1000, => 
            @pulling(data.url)

    onError:(xhr, textStatus, error) =>
        @$(".progress").hide()
        msg = ''
        if xhr.responseJSON
            msg = xhr.responseJSON.error
        else
            msg = xhr.responseText
        @$(".warning").html(msg)

    onPullSuccess: (data) =>
        if data.finished
            @$(".progress").hide()
            @logResult(data)
        else
            WEB.delay 3000, =>
                @pulling()

    onPullError: (xhr, textStatus, error) =>
        @onError(xhr, textStatus, error)

    pulling:(url) =>
        if not url
            url = @pullingUrl
        $.ajax
            url: url
            type: 'GET'
            success: @onPullSuccess
            error: @onPullError

    send:(url, onSuccess, onError) =>
        @$(".progress").show()
        @$(".warning").empty()
        $.ajax
            url: url
            type: 'POST'
            contentType: 'application/json'
            data:
                JSON.stringify({})
            success: onSuccess
            error: onError

class AR.PartnerExport extends WEB.BaseView
    cssClass: "export-partners-basic"

    constructor: (@options) ->
        super(@options)
        @exportUrl = @getJson('exportPartnerUrl')

    attachHandlers: () =>
        @$("button.export").click(@onExport)

    logResult: (log) =>
        @$(".log").html(log.display)

    onExport:(evt) =>
        @send(@exportUrl, @onSuccess, @onError)

    onSuccess:(data) =>
        @pullingUrl =  data.url
        WEB.delay 1000, => 
            @pulling(data.url)

    onError:(xhr, textStatus, error) =>
        @$(".progress").hide()
        msg = ''
        if xhr.responseJSON
            msg = xhr.responseJSON.error
        else
            msg = xhr.responseText
        @$(".warning").html(msg)

    onPullSuccess: (data) =>
        if data.finished
            @$(".progress").hide()
            @logResult(data)
        else
            WEB.delay 3000, =>
                @pulling()

    onPullError: (xhr, textStatus, error) =>
        @onError(xhr, textStatus, error)

    pulling:(url) =>
        if not url
            url = @pullingUrl
        $.ajax
            url: url
            type: 'GET'
            success: @onPullSuccess
            error: @onPullError

    send:(url, onSuccess, onError) =>
        @$(".warning").empty()
        if !@validateInput()
            return

        @$(".progress").show()
        $.ajax
            url: url
            type: 'POST'
            contentType: 'application/json'
            data:
                JSON.stringify(@inputJsonData())
            success: onSuccess
            error: onError
    inputJsonData:() =>
        return {
            "type" : "partner-basic"
        }
    validateInput:() =>
        return true

class AR.PartnerExportBilling extends AR.PartnerExport
    cssClass : "export-partners-billing"

    inputJsonData:() =>
        return {
            "type" : "partner-billing",
            "dateRange" : {
                "start" : @$('.startDate input[type=date]').val(),
                "end" : @$('.endDate input[type=date]').val()
            }
        }

    validateInput:() =>
        if !@isDateStr(@getStartDateStr()) or !@isDateStr(@getEndDateStr())
            @$(".warning").html('Please provide valid date range.')
            return false
        return true

    isDateStr : (str) =>
        return /^\d{4}[\/\-](0?[1-9]|1[012])[\/\-](0?[1-9]|[12][0-9]|3[01])$/.test(str)
    getStartDateStr:() =>
        return @$('.startDate input[type=date]').val()
    getEndDateStr:() =>
        return @$('.endDate input[type=date]').val()



