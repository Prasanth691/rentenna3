class AR.ARQuizStack extends QUIZ.QuizStack

    cssClass: 'ar-quiz-stack'

    onPostSubmit: (data) =>
        if data.user?
            AR.USER = new AR.User(data.user)
            AR.USER.identify()

class AR.QuizSlideAddressLookup extends QUIZ.QuizSlideView

    template: 'quizSlideAddressLookup'

    constructor: (options) ->
        super(options)
        address = new AR.AddressAutocomplete
            types: ['address']
            action: 'dom-event'
        @$('.address').append(address.$el)
        @$el.off('submit:valid', @goNext)

    attachHandlers: () =>
        @$el.on('autocomplete-selected', @nextSlide)

    nextSlide: (ev, target) =>
        @$el.trigger('next-slide', {address: JSON.stringify(target)})

class AR.QuizSlideEmail extends QUIZ.QuizSlideView

    template: 'quizSlideEmail'

    constructor: (options) ->
        super(options)

    getTemplateContext: () ->
        return {
            quizData: @options.quizData,
            email: AR.USER.email,
        }

    processData: () =>
        @email = @$(".email input").val()
        return {email: @email}

class AR.QuizSlidePhone extends QUIZ.QuizSlideView

    template: 'quizSlidePhone'

    constructor: (options) ->
        super(options)

    processData: () =>
        phone = @$(".phone input").val()
        return {phone: phone}

class AR.QuizSlideProcessing extends QUIZ.QuizSlideView

    template: 'quizSlideProcessing'

    constructor: (options) ->
        super(options)
        processing = new AR.MockProgressBar({quiz:true, delay:3000})
        @$('.slide-content').append(processing.$el)

    attachHandlers: () =>
        @$el.on('progressbar-complete', @progressComplete)

    progressComplete: () =>
        @$el.trigger('next-slide')

class AR.QuizAutoSlideText extends QUIZ.QuizSlideView

    template: 'quizAutoSlideText'

    constructor: (options) ->
        super(options)
        @$('.text-message').append(options.text)
        @delay = options.delay || 3000
        WEB.delay(
            @delay,
            @finishAutoText
        )

    finishAutoText: () =>
        @$el.trigger('autotext-complete')

    attachHandlers: () =>
        @$el.on('autotext-complete', @progressComplete)

    progressComplete: () =>
        @$el.trigger('next-slide')

class AR.CreditScoreSlide extends QUIZ.QuizSlideSimpleSelect

    template: 'quizSlideCreditScore'

class AR.QuizThankYou extends WEB.BaseView

    cssClass: 'quiz-thank-you'

    constructor: (options) ->
        super(options)
        AR.log "Completed Quiz"
        WEB.fireGtmEvent("Completed Quiz")

class AR.Quiz extends WEB.BaseView

    cssClass: 'quiz-landing-page'

    attachHandlers: () =>
        super()
        @$el.on('loading', @renderLoading)

    renderLoading: () =>
        @$('.progress').addClass('progress-striped active')
