class WEB.ReportInfo extends WEB.BaseView

    cssClass: 'report-info'

    constructor: (options) ->
        super(options)
        @reportKey = @getJson('reportKey')
        @poll()

    poll: () =>
        $.ajax 
            url: "/web-admin/reports/status/#{ @reportKey }/"
            success: @pollSuccess

    pollSuccess: (data) =>
        console.log(data)
        if data.status == 'done'
            @$('.progress-bar').width("100%")
            @$('.progress-bar').removeClass('progress-bar-striped')
            @$('.progress-bar').removeClass('active')
            @$('.progress-bar').addClass('progress-bar-success')
            @$('.btn').removeAttr('disabled')
        else if data.status == 'aborted'
            @$('.progress-bar').width("100%")
            @$('.progress-bar').removeClass('progress-bar-striped')
            @$('.progress-bar').removeClass('active')
            @$('.progress-bar').addClass('progress-bar-danger')
        else
            @$('.progress-bar').width("#{ 100 * data.percent }%")
            WEB.delay(1000, @poll)

class WEB.BlogList extends WEB.BaseView

    cssClass: 'blog-list' 

    attachHandlers: () =>
        @$('.post-type-select').change(@changePostType)

    changePostType: () =>
        postType = @$('.post-type-select').val()
        window.location = "/web-admin/blog/?postType=#{ postType }"

class WEB.BlogPost extends WEB.BaseView

    cssClass: 'blog-post'

    constructor: (options) ->
        super(options)
        @$('.post-content').editable
            inlineMode: false
            imageUploadURL: '/web-admin/upload/'
            noFollow: false
            defaultImageWidth: 0
        @isNew = @getJson('isNew')

    attachHandlers: () =>
        @$('.save').click(@makeTextarea)
        @$('input[name=title]').keyup(@setSlug)

    makeTextarea: () =>
        html = $(".post-content").editable("getHTML")
        @$('input[name=content]').val(html)

    setSlug: () =>
        if @isNew
            title = @$('input[name=title]').val()
            slug = title.toLowerCase()
            slug = slug.replace(/( )+/g, '-')
            slug = slug.replace(/[^0-9a-z\-]/g, '')
            @$('input[name=slug]').val(slug)