import flask
import traceback
import yaml

from web import validate
from web.base import BaseView, Route
from web.quiz.quizModels import *

class QuizView(BaseView):

    @Route('/web-admin/quiz/')
    def get(self):
        quizzes = Quiz.query().fetch()
        return flask.render_template('quiz/quizAdminIndex.jinja2',
            quizzes=quizzes,
        )

    @Route('/web-admin/quiz/<key>/')
    def edit(self, key):
        if key == 'new':
            quiz = Quiz()
        else:
            quiz = ndb.Key(urlsafe=key).get()
        return flask.render_template('quiz/quizAdminEditor.jinja2',
            quiz=quiz,
        )

    @Route('/web-admin/quiz/<key>/', methods=['POST'])
    def save(self, key):
        if key == 'new':
            quiz = Quiz()
        else:
            quiz = ndb.Key(urlsafe=key).get()

        quiz.slug = validate.get('slug')
        quiz.thankyou = validate.get('thankyou')
        quiz.slidesYaml = validate.get('slides')
        quiz.embeddedThankYouUrl = validate.get('embeddedThankYouUrl')
        quiz.embeddedThankYouUrlText = validate.get('embeddedThankYouUrlText')

        try:
            slideData = yaml.safe_load(quiz.slidesYaml)
        except Exception as e:
            return flask.render_template('quiz/quizAdminEditor.jinja2',
                quiz=quiz,
                error=traceback.format_exc(),
            )

        try:
            quiz.slides = [
                QuizInstruction.parse(x)
                for x 
                in slideData
            ]
        except Exception as e:
            return flask.render_template('quiz/quizAdminEditor.jinja2',
                quiz=quiz,
                error=traceback.format_exc(),
            )

        quiz.put()

        return flask.redirect(quiz.getAdminUrl())