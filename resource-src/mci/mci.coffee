MCI = {}

class MCI.CommitProgress extends WEB.BaseView

    cssClass: 'commit-progress'

    constructor: (@options) ->
        super(@options)
        @commitId = @getJson('commitId')
        @poll()

    poll: () =>
        $.ajax
            url: "/web-admin/mci/commit-info/#{ @commitId }/"
            success: @pollSuccess

    pollSuccess: (data) =>
        $overall = @$('.progress-bar')
        $overallInfo = @$('.current-info')

        status = data.status.status
        progress = data.status.progress

        if (status == 'success') or (status == 'pushed')
            @markComplete($overallInfo, $overall)
        else if (status == 'failed-build') or (status == 'failed-push')
            @markFailed($overallInfo, $overall)
        else
            @markProgress($overallInfo, $overall, progress, data.status.state)
            
        WEB.delay(500, @poll)

    markComplete: ($info, $progress) =>
        $info.text('Complete')
        $progress.removeClass('active')
        $progress.removeClass('progress-bar-striped')
        $progress.removeClass('progress-bar-info')
        $progress.addClass('progress-bar-success')
        $progress.css('width', '100%')

    markFailed: ($info, $progress) =>
        $info.text('Failed')
        $progress.removeClass('active')
        $progress.removeClass('progress-bar-striped')
        $progress.removeClass('progress-bar-info')
        $progress.addClass('progress-bar-danger')
        $progress.css('width', '100%')

    markProgress: ($info, $progress, progress, state) =>
        if progress > 0
            width = progress * 100
            width = Math.ceil(width)
        else
            width = 1

        $progress.css('width', "#{ width }%")

        if state?
            $info.text(state)
        else
            $info.text('')

class MCI.YamlEditor extends WEB.BaseView

    cssClass: 'yaml-editor'

    constructor: (@options) ->
        super(@options)
        cm = CodeMirror.fromTextArea @$el[0],
            theme: 'blackboard'
            lineNumbers: true
            mode: "text/x-yaml"

$ ->
    WEB.ClassUtil::setClassNames(MCI)
    WEB.BaseView::attach(MCI)