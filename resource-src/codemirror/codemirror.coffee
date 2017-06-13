window.CODEMIRROR = {}

class CODEMIRROR.CodeMirrorWrapper extends WEB.BaseView
    ###
        Mimetypes:
            - text/x-yaml
    ###

    cssClass: 'code-mirror'

    constructor: (options) ->
        super(options)
        @mode = @getJson('mode')
        @name = @getJson('name')
        @src = @getJson('src')
        @$textarea = $("""<textarea name="#{ @name }"></textarea>""")
        @$textarea.text(@src)
        @$el.append(@$textarea)

        @cm = CodeMirror.fromTextArea @$textarea[0],
            theme: 'blackboard'
            lineNumbers: true
            mode: @mode

$ ->
    WEB.ClassUtil::setClassNames(CODEMIRROR)
    WEB.BaseView::attach(CODEMIRROR)