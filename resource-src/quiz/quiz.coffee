window.QUIZ = {}

# TODO: delete QUIZ.QuizManager, QUIZ.QuizView once migration on all apps is complete

class QUIZ.QuizManager extends WEB.BaseView

    quizzes: [] # subclasses should define array dictionaries containing quiz module class and options

    constructor: (options) ->
        super(options)
        sessionId = Math.random().toString(36).substring(2) + Math.random().toString(36).substring(2)
        @quizData = {'sessionId' : sessionId }
        @quizIndex = 0
        @currentSlide = 0
        @maxSlides = @getMaxSlides()

    attachHandlers: () =>
        @$el.on('setProgress', @setProgress)
        @$el.on('nextQuiz', @nextQuizModule)
        @$el.on('quizDataProduced', @updateDataObjects)
        @$el.on('updateAnswers', @postType)

    getMaxSlides: () =>
        # get the max number of slides possible for the quiz

    nextQuizModule: () =>
        # logic to handle which quiz will come next

    postCurrentAnswers: () =>
        # post quiz answers each time user completes a question

    postType: (ev, moduleComplete) =>
        if moduleComplete and @quizIndex == @quizzes.length - 1
            @processQuiz()
        else
            @postCurrentAnswers()

    processQuiz: () =>
        # process quiz data and handle url params/redirects

    setProgress: (ev, step) =>
        if step == 'next'
            @currentSlide += 1
            @$(".back").show()
        else
            @currentSlide -= 1
        progress = @currentSlide/@maxSlides
        if progress > 1
            progress = 1
        @$('.meter-fill').css('width', "#{ progress*250 }px" )

    updateDataObjects: (ev, param) =>
        $.extend(@quizData, param)

    renderModule: (module) =>
        @$('.quizzes').empty()

        params = {}
        if module.params?
            $.extend(params, module.params)
        params.quizData = @quizData
        quiz = new module['cls'](params)
        @$('.quizzes').append(quiz.$el)

class QUIZ.QuizView extends WEB.BaseView

    slides: [] # subclasses should define array dictionaries containing slide class and options

    constructor: (options) ->
        super(options)
        @quizData = options.quizData
        @index = 0
        @renderSlide()
        @processing = false
        
    attachHandlers: () =>
        @$el.on('back', @goBack)
        @$el.on('next-slide', @goNext)

    goBack: (ev) =>
        @index = @index - 1
        @$el.trigger('setProgress', step='back')
        @renderSlide()

    goNext: (ev, param) => 
        currentSlide = $('.slide').data('slide')
        WEB.track("Completed #{ currentSlide }-slide")
        @$el.trigger('quizDataProduced', param)
        if @index + 1 == @slides.length
            @$el.trigger('setProgress', step='next')
            @$el.trigger('updateAnswers', moduleComplete=true)
            @$el.trigger('nextQuiz')
        else
            @index = @index + 1
            @$el.trigger('setProgress', step='next')
            @$el.trigger('updateAnswers')
            @renderSlide()

    renderSlide: () =>
        @$('.quiz-slides').empty()

        slideInfo = @slides[@index]

        params = {}
        if slideInfo.params?
            $.extend(params, slideInfo.params)
        params.quizData = @quizData

        slide = new slideInfo.cls(params)
        @$('.quiz-slides').append(slide.$el)

class QUIZ.QuizSlideView extends WEB.BaseView

    constructor: (options) ->
        super(options)
        @quizData = options.quizData
        @name = options.name

    attachHandlers: () =>
        @$el.on('submit:valid', @goNext)

    goNext: (ev) =>
        @$el.trigger('next-slide', @processData(ev))

    processData: () =>
        # return a hash to update the quiz data with
        return {}

class QUIZ.QuizStack extends WEB.BaseView

    cssClass: 'quiz-stack'

    constructor: (options) ->
        super(options)
        
        @endpoint = @getJson('endpoint')
        @slug = @getJson('slug')
        @onComplete = @getJson('onComplete')
        @thankyouFromAr = @getJson('thankyouFromAr')
        quizSeed = @getJson('quizSeed') or {}
        
        @slides = []
        @pushSlides(@getJson('slides'))

        sessionId = Math.random().toString(36).substring(2) + Math.random().toString(36).substring(2)
        @quizData = {
            sessionId: sessionId
        }
        $.extend(@quizData, quizSeed)

        @$quizSlides = $("""<div class="quiz-content"></div>""")
        @$el.append(@$quizSlides)

        @nextSlide()

    attachHandlers: () =>
        @$el.on('next-slide', @nextSlide)

    nextSlide: (event, data) =>
        if @currentSlide?
            WEB.track "Quiz Slide Completed: #{ @slug } / #{ @currentSlide.name }", data
            deliver = @currentSlide.options.deliver
            @currentSlide = null

        if data?
            $.extend(@quizData, data)

        @$quizSlides.empty()

        nextSlide = @slides.pop()
        if nextSlide?
            if nextSlide.slide?
                slide = nextSlide.slide

                slideClsPath = slide.cls.split(".")
                current = window
                for pathItem in slideClsPath
                    current = current?[pathItem]

                params = slide.params
                params.quizData = @quizData
                params.name = slide.name
                slideView = new current(params)
                @$quizSlides.append(slideView.$el)
                @$('div[role=progressbar]').css
                    width: "#{ 100 * slide.progress }%"
                @postQuizData(false, deliver)
                @currentSlide = slideView
            else if nextSlide.switch?
                switcher = nextSlide.switch
                
                evaluator = switcher['eval']
                current = @quizData
                for pathItem in evaluator.split(".")
                    current = current?[pathItem]

                handled = false
                for caseItem in switcher.cases
                    if caseItem.value == current
                        handled = true
                        @pushSlides([{
                            endSwitch: {
                                name: switcher.name
                            }    
                        }])
                        @pushSlides(caseItem.slides)

                if (not handled) and switcher.fallback
                    @pushSlides([{
                        endSwitch: {
                            name: switcher.name
                        }    
                    }])
                    @pushSlides(switcher.fallback)
                
                @nextSlide()
            else if nextSlide.endSwitch?
                WEB.track "Quiz Switch Completed: #{ @slug } / #{ nextSlide.endSwitch.name }"
                @nextSlide()
        else
            @postQuizData(true, deliver)

    onPostSubmit: (data) =>

    pushSlides: (slides) =>
        copy = slides.slice()
        copy.reverse()
        @slides = @slides.concat(copy)

    postQuizData: (final, deliver) ->
        if final
            @$el.trigger('loading')
        $.ajax
            url: @endpoint
            data:
                answers: JSON.stringify(@quizData)
                slug: @slug
                final: final
                deliver: deliver
            type: "POST"
            success: (data) =>
                $.extend(@quizData, data.quizDataMerge)

                @onPostSubmit(data)

                if final
                    if @thankyouFromAr
                        WEB.navigate("""#{ @onComplete }?sessionId=#{ @quizData.sessionId }""")
                    else
                        WEB.navigate("""#{ @onComplete }""")

class QUIZ.QuizSlideDropdown extends QUIZ.QuizSlideView

    cssClass: 'dropdown-slide'
    template: 'dropdownSlide'

    constructor: (@options) ->
        super(@options)
        @fieldName = @options.field or @$el.data('slide')

    processData: () =>
        data = {}
        data[@fieldName] = @$('select').val()
        return data 

class QUIZ.QuizSlideFreeText extends QUIZ.QuizSlideView

    cssClass: 'free-text-slide'
    template: 'freeTextSlide'

    constructor: (@options) ->
        super(@options)
        @fieldName = @options.field or @$el.data('slide')

    processData: () =>
        data = {}
        data[@fieldName] = @$('input').val()
        return data

class QUIZ.QuizSlideSimpleSelect extends QUIZ.QuizSlideView

    cssClass: 'simple-select-slide'
    template: 'simpleSelectSlide'

    constructor: (@options) ->
        @options.flow = @options.flow or 'block'
        @options.box = @options.box or 'rectangle'

        super(@options)
        @fieldName = @options.field or @$el.data('slide')

    attachHandlers: () =>
        super()
        @$('.auto-next').on('click', @autoNext)

    autoNext: (event) =>
        output = {}
        output[@fieldName] = $(event.currentTarget).data('value')
        @$el.trigger('next-slide', output)

QUIZ.findSlidesByName = (slides, name) ->
    try
        results = []
        for slide in slides
            if slide.switch?
                for currentCase in slide.switch.cases
                    results = results.concat(QUIZ.findSlidesByName(currentCase.slides, name))
                if slide.switch.fallback?
                    results = results.concat(QUIZ.findSlidesByName(slide.switch.fallback, name))
            else if slide.slide?
                if slide.slide.name == name
                    results.push(slide.slide)
        return results
    catch e
        console.log e
    

$ ->
    WEB.ClassUtil::setClassNames(QUIZ)
    WEB.BaseView::attach(QUIZ)