from web.base import AppSubcomponent

class QuizSubcomponent(AppSubcomponent):

    adminLink = ('/web-admin/quiz/', 'Quizzes')
    requires = [
        'AdminSubcomponent',
    ]

    # client-side requires: quiz, quiz-admin, codemirror
    # include quiz.sass, quiz-admin.sass

    def augmentEnvironment(self, appInfo):
        import web.quiz.quizAdminViews
        import web.quiz.quizModels
        appInfo.viewModules.append(web.quiz.quizAdminViews)
        appInfo.modelModules.append(web.quiz.quizModels)