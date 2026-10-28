from typing import Literal, Annotated
import re
from pydantic import BaseModel, Field, ConfigDict, model_validator

SceneType = Literal['title_card','labeled_diagram','code_walkthrough','flow_diagram','graph_animation','timeline','comparison','animated_illustration']

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

class LessonRequest(StrictModel):
    topic: str = Field(min_length=1,max_length=600)
    level: Literal['beginner','intermediate'] = 'beginner'
    language: Literal['en','hi','kn','ta','te','ml','mr','bn','gu','pa','or'] = 'en'
    targetDuration: int = Field(default=60,ge=30,le=90)
    videoEngine: Literal['animated','ltx'] = 'animated'
    cpuOnly: bool = False
    reuseSaved: bool = True
    speechSpeed: float = Field(default=1.0,ge=.75,le=1.3)
    voice: Literal['basic','female','male','online-female','online-male'] = 'female'
    accent: Literal['indian','british','american'] = 'indian'

class LearningObjective(StrictModel):
    text: str = Field(min_length=3,max_length=240)

class DiagramNode(StrictModel):
    id: str = Field(min_length=1,max_length=32)
    label: str = Field(min_length=1,max_length=90)

class DiagramEdge(StrictModel):
    source: str
    target: str
    label: str = Field(default='',max_length=60)

class DataPoint(StrictModel):
    label: str = Field(max_length=40)
    value: float = Field(ge=-100000,le=100000,allow_inf_nan=False)

class TimelineItem(StrictModel):
    date: str = Field(max_length=30)
    text: str = Field(max_length=110)

class ComparisonRow(StrictModel):
    label: str = Field(max_length=45)
    left: str = Field(max_length=110)
    right: str = Field(max_length=110)

class CodeTraceStep(StrictModel):
    label: str = Field(max_length=50)
    value: str = Field(max_length=80)
    output: str = Field(max_length=200)
    line: int = Field(ge=1,le=12)

class VisualConfiguration(StrictModel):
    damping: float = Field(default=0,ge=0,le=.3)
    trace: list[CodeTraceStep] = Field(default_factory=list,max_length=8)
    layout: Literal['linear','cycle','branch','hub'] = 'linear'
    motion: Literal['none','orbit','collision','diffusion','pendulum','wave','transfer'] = 'none'
    shape: Literal['sphere','drop','leaf','block'] = 'sphere'
    nodes: list[DiagramNode] = Field(default_factory=list,max_length=6)
    edges: list[DiagramEdge] = Field(default_factory=list,max_length=8)
    code: str = Field(default='',max_length=900)
    highlightLines: list[Annotated[int,Field(ge=1)]] = Field(default_factory=list,max_length=12)
    points: list[DataPoint] = Field(default_factory=list,max_length=7)
    xLabel: str = Field(default='',max_length=45)
    yLabel: str = Field(default='',max_length=45)
    items: list[TimelineItem] = Field(default_factory=list,max_length=5)
    leftTitle: str = Field(default='',max_length=45)
    rightTitle: str = Field(default='',max_length=45)
    rows: list[ComparisonRow] = Field(default_factory=list,max_length=4)
    keywords: list[str] = Field(default_factory=list,max_length=4)
    animation: Literal['progressive_reveal','trace_flow','highlight_sequence'] = 'progressive_reveal'

class Scene(StrictModel):
    id: str = Field(min_length=1,max_length=50)
    type: SceneType
    heading: str = Field(min_length=2,max_length=100)
    narration: str = Field(min_length=15,max_length=600,pattern=r'^[^<>\[\]`]+$')
    visual: VisualConfiguration

    @model_validator(mode='after')
    def valid_visual(self):
        v=self.visual
        if re.search(r'https?://|\b(?:show|display|insert) (?:a |an |the )?(?:diagram|image|animation)',self.narration,re.I):raise ValueError('Narration must be spoken explanation, not visual stage directions or links.')
        if self.type in ('labeled_diagram','flow_diagram'):
            if len(v.nodes)<2: raise ValueError('A diagram needs at least two labeled nodes.')
            ids={n.id for n in v.nodes}
            if len(ids)!=len(v.nodes): raise ValueError('Duplicate diagram node IDs.')
            if any(e.source not in ids or e.target not in ids for e in v.edges): raise ValueError('Diagram edge references missing node.')
        if self.type=='animated_illustration':
            if v.motion=='none' or not 2<=len(v.nodes)<=4:raise ValueError('Animated illustration requires a meaningful motion and 2–4 labels.')
        if self.type=='code_walkthrough':
            if not v.code.strip() or len(v.code.splitlines())>12: raise ValueError('Code scene requires 1–12 lines of display-only code.')
            if any(line<1 or line>len(v.code.splitlines()) for line in v.highlightLines): raise ValueError('Code highlight is out of range.')
        if self.type=='graph_animation' and len(v.points)<2: raise ValueError('Graph needs at least two numeric points.')
        if self.type=='timeline' and len(v.items)<2: raise ValueError('Timeline needs at least two entries.')
        if self.type=='comparison' and (not v.rows or not v.leftTitle or not v.rightTitle): raise ValueError('Comparison requires column headings and rows.')
        if any(len(k)>80 for k in v.keywords): raise ValueError('Keyword is too long.')
        return self

class QuizOption(StrictModel):
    id: str = Field(min_length=1,max_length=40)
    text: str = Field(min_length=1,max_length=180)

class QuizQuestion(StrictModel):
    id: str
    lessonId: str = ''
    sceneId: str
    language: str = 'en'
    question: str = Field(min_length=5,max_length=260)
    options: list[QuizOption] = Field(min_length=3,max_length=4)
    correctOptionId: str
    explanation: str = Field(min_length=10,max_length=500)
    misconceptionTag: str | None = None

    @model_validator(mode='after')
    def valid_answer(self):
        ids=[o.id for o in self.options]
        if len(set(ids))!=len(ids) or self.correctOptionId not in ids: raise ValueError('Invalid correct option or duplicate option IDs.')
        if len({o.text.strip().casefold() for o in self.options})!=len(ids): raise ValueError('Duplicate answer text.')
        return self

class LessonPlan(StrictModel):
    title: str = Field(min_length=3,max_length=120)
    level: Literal['beginner','intermediate']
    language: str
    objectives: list[LearningObjective] = Field(min_length=1,max_length=4)
    scenes: list[Scene] = Field(min_length=3,max_length=6)
    quiz: list[QuizQuestion] = Field(min_length=1,max_length=3)
    followUps: list[Annotated[str,Field(max_length=240)]] = Field(min_length=1,max_length=3)

    @model_validator(mode='after')
    def references(self):
        ids={s.id for s in self.scenes}
        if len(ids)!=len(self.scenes): raise ValueError('Duplicate scene IDs.')
        if len({s.heading.strip().casefold() for s in self.scenes})!=len(self.scenes): raise ValueError('Repeated scene headings: each scene must explain a distinct point.')
        if any(q.sceneId not in ids for q in self.quiz): raise ValueError('Question references a missing scene.')
        if len({q.id for q in self.quiz})!=len(self.quiz): raise ValueError('Duplicate quiz IDs.')
        if self.scenes[0].type!='title_card': raise ValueError('Start with a title card.')
        if all(s.type=='title_card' for s in self.scenes): raise ValueError('Lesson needs explanatory visuals, not only title cards.')
        if any(len(f)>240 for f in self.followUps): raise ValueError('Follow-up too long.')
        return self

class IntentResponse(StrictModel):
    intent: Literal['educational','conversation','clarification']
    message: str = Field(max_length=700)
    lesson: LessonPlan | None

    @model_validator(mode='after')
    def lesson_for_intent(self):
        if self.intent=='educational' and self.lesson is None: raise ValueError('Educational intent requires a lesson.')
        if self.intent!='educational' and self.lesson is not None: raise ValueError('Conversation must not create a video.')
        return self
