VALIDATE = {}
window.VALIDATE = VALIDATE

VALIDATE.isSafari = navigator.userAgent.indexOf("Safari") > -1

VALIDATE.invalidate = ($el, message, isHtml) ->
    $el.tooltip
        html: isHtml
        title: message
        placement: 'bottom'
        trigger: 'manual'
    $el.tooltip('show')
    $el.on "focus keydown", () ->
        $el.tooltip('destroy')

VALIDATE.uninvalidate = ($form) ->
    

VALIDATE.isValidEmail = (value) ->
    return value.toUpperCase().match(/^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,10}$/)

VALIDATE.invalidateEmail = ($el, value) ->
    if (not Modernizr.input.email) or VALIDATE.isSafari or window.OLD_WEBKIT
        if not VALIDATE.isValidEmail(value)
            VALIDATE.invalidate($el, 'Must be a valid email.')
            return true

VALIDATE.isValidHumanName = (value) ->
    fullName = $.trim(value.replace(/[^A-Za-z ]/g, ''))
    nameParts = fullName.split(" ")
    return nameParts.length >= 2

VALIDATE.invalidateHumanName = ($el, value) ->
    fullName = $.trim(value.replace(/[^A-Za-z ]/g, ''))
    nameParts = fullName.split(" ")
    $el.val(fullName)

    # no last name OR last name is less than 2 characters
    if nameParts.length < 2 or nameParts[nameParts.length - 1].length < 2
        VALIDATE.invalidate($el, "Must be your full first and last name")
        return true

VALIDATE.invalidateRequired = ($el, value) ->
    if (not Modernizr.input.email) or VALIDATE.isSafari or window.OLD_WEBKIT
        if value == ""
            VALIDATE.invalidate($el, 'This field is required a.')
            return true

VALIDATE.isValidTel = (value) ->
    phoneNumber = value.replace(/[^0-9]/g, '')
    return phoneNumber.length >= 10

VALIDATE.invalidateTel = ($el, value) ->
    if VALIDATE.isOptional($el)
        return false
    phoneNumber = value.replace(/[^0-9]/g, '')
    ######$el.val(phoneNumber)
    if phoneNumber.length < 10
        VALIDATE.invalidate($el, 'Must be at least 10-digit phone')
        return true

VALIDATE.isValidZip = (value) ->
    zip = value.replace(/[^0-9]/g, '')
    return zip.length == 5

VALIDATE.invalidateZip = ($el, value) ->
    if VALIDATE.isOptional($el)
        return false
    zip = value.replace(/[^0-9]/g, '')
    $el.val(zip)
    if zip.length != 5
        VALIDATE.invalidate($el, 'Must be a 5-digit zip')
        return true

VALIDATE.validateAll = ($els, invalidator) ->
    valid = true
    $els.each (i, el) ->
        $el = $(el)
        value = $el.val()
        if invalidator($el, value)
            valid = false
    return valid


VALIDATE.validateForm = (event, $form) ->
    VALIDATE.uninvalidate($form)
    valid = true
    valid and= VALIDATE.validateAll(
        $form.find('input[required]'), 
        VALIDATE.invalidateRequired
    )
    valid and= VALIDATE.validateAll(
        $form.find('input[type=email]'), 
        VALIDATE.invalidateEmail
    )
    valid and= VALIDATE.validateAll(
        $form.find('input[type="human-name"]'), 
        VALIDATE.invalidateHumanName
    )
    valid and= VALIDATE.validateAll(
        $form.find('input[type=tel]'), 
        VALIDATE.invalidateTel
    )
    valid and= VALIDATE.validateAll(
        $form.find('input[type=zip]'), 
        VALIDATE.invalidateZip
    )

    if not valid
        event.preventDefault()
        event.stopImmediatePropagation()
        $form.trigger('submit:invalid')
    else
        $form.trigger('submit:valid')

VALIDATE.isOptional = ($el) ->
    required = $el.attr('data-required')
    if required == 'false'
        return true
    return false
$ ->
    $('html').on 'submit', '[nosubmit]', (event) ->
        event.preventDefault()
    $('html').on 'submit', 'form', (event) ->
        VALIDATE.validateForm(event, $(event.currentTarget))