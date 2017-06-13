import pprint

from google.appengine.ext import ndb

class Quiz(ndb.Model):

    slides = ndb.PickleProperty()
    slidesYaml = ndb.TextProperty()
    slug = ndb.StringProperty()
    thankyou = ndb.StringProperty()
    embeddedThankYouUrlText = ndb.StringProperty()
    embeddedThankYouUrl = ndb.StringProperty()

    @classmethod
    def applyProgress(cls, slides, start=0.0, end=1.0):
        if slides:
            naturalWeights = []
            current = 0
            for slide in slides:
                current += slide.getNaturalWeight()
                naturalWeights.append(current)
            totalNaturalWeight = naturalWeights[-1]
            weights = []
            for naturalWeight in naturalWeights:
                weights.append(naturalWeight / totalNaturalWeight)

            def map(x):
                width = end - start
                return start + (x * width)
            
            previous = 0.0
            for slide, next in zip(slides, weights):
                left = map(previous)
                right = map(next)
                slide.setProgress(left, right)
                previous = next

    @classmethod
    def getNaturalWeight(cls, slides):
        return sum([
            slide.getNaturalWeight()
            for slide 
            in slides
        ])

    def getAdminUrl(self):
        return '/web-admin/quiz/%s/' % self.key.urlsafe()

    def getJson(self):
        self.applyProgress(self.slides)
        jsonObject = [
            x.toJson()
            for x
            in (self.slides or [])
        ]
        return jsonObject

class QuizInstruction(object):

    __abstract__ = True

    @classmethod
    def parse(cls, obj):
        key = obj.keys()[0]
        return INSTRUCTION_MAP[key].parse(obj[key])

    def getNaturalWeight(self):
        return 1.0

    def setProgress(self, start, end):
        # TODO: should be midpoint or end?
        # self.progress = (start + end) / 2.0
        self.progress = end

    def toJson(self):
        raise NotImplemented

class QuizDeliver(QuizInstruction):

    @classmethod
    def parse(cls, obj):
        return QuizDeliver()

    def __init__(self):
        pass

    def toJson(self):
        return {
            'deliver': {},
        }

class QuizSlide(QuizInstruction):

    @classmethod
    def parse(cls, obj):
        return QuizSlide(
            cls=obj['cls'],
            params=obj.get('params') or {},
            name=obj.get('name') or obj['cls']
        )

    def __init__(self, cls, params, name):
        self.cls = cls
        self.params = params
        self.name = name

    def toJson(self):
        return {
            'slide': {
                'cls': self.cls,
                'params': self.params,
                'name': self.name,
                'progress': getattr(self, 'progress', 0),
            }
        }

class QuizSwitcher(QuizInstruction):

    @classmethod
    def parse(cls, obj):
        quizCases = []
        for case in obj['cases']:
            value = case['value']
            slides = [
                QuizInstruction.parse(x) 
                for x 
                in case['slides']
            ]
            quizCases.append({
                'value': value,
                'slides': slides,    
            })
        if obj.get('fallback'):
            fallback = [
                QuizInstruction.parse(x) 
                for x 
                in obj['fallback']
            ]
        else:
            fallback = []
        return QuizSwitcher(
            eval=obj['eval'],
            cases=quizCases,
            fallback=fallback,
            name=obj.get('name') or obj['eval'],
        )

    def __init__(self, eval, cases, fallback, name):
        self.eval = eval
        self.cases = cases
        self.fallback = fallback
        self.name = name

    def getBranches(self):
        branches = []
        for case in self.cases:
            branches.append(case['slides'])
        branches.append(self.fallback)
        return branches

    def getNaturalWeight(self):
        return max([
            Quiz.getNaturalWeight(branch)
            for branch 
            in self.getBranches()
        ])

    def setProgress(self, start, end):
        for branch in self.getBranches():
            Quiz.applyProgress(branch, start, end)

    def toJson(self):
        jsonCases = []
        for case in self.cases:
            jsonCase = {
                'value': case['value'],
                'slides': [
                    slide.toJson()
                    for slide
                    in case['slides']
                ]
            }
            jsonCases.append(jsonCase)
        jsonFallback = [
            slide.toJson() 
            for slide 
            in self.fallback
        ]
        return {
            'switch': {
                'eval': self.eval,
                'cases': jsonCases,
                'fallback': jsonFallback,
                'name': self.name,
            }
        }

INSTRUCTION_MAP = {
    'deliver': QuizDeliver,
    'slide': QuizSlide,
    'switch': QuizSwitcher,
}