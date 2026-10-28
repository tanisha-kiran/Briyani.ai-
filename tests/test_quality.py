import pytest
from backend.quality import code_trace,audit
from backend.samples import sample
from backend.schemas import LessonRequest
from backend.app import app
from fastapi.testclient import TestClient

def test_safe_range_trace_exposes_real_values_and_output():
    steps=code_trace('for i in range(3):\n    print(i)')
    assert [s['value'] for s in steps]==['i = 0','i = 1','i = 2']
    assert steps[-1]['output']=='0\n1\n2'

@pytest.mark.parametrize('code',[
    "import os\nos.system('anything')", "for i in range(3):\n    print(open('secret').read())",
    'for i in range(100):\n    print(i)','for i in range(0, 3, 0):\n    print(i)'])
def test_trace_never_executes_untrusted_code(code):
    assert code_trace(code)==[]

def test_quality_rejects_placeholder_and_repeated_keyword_diagrams():
    request=LessonRequest(topic='Python for loops',targetDuration=60)
    plan=sample(request,'test').lesson
    plan.scenes[1].heading='Scene 1'
    with pytest.raises(ValueError,match='placeholder'):audit(plan,request)

def test_quality_rejects_excessive_narration():
    request=LessonRequest(topic='Python for loops',targetDuration=30)
    plan=sample(request,'test').lesson
    plan.scenes[0].narration='A loop repeats instructions. '*40
    with pytest.raises(ValueError,match='too long'):audit(plan,request)

def test_regional_narration_must_primarily_use_the_selected_script():
    request=LessonRequest(topic='Python loops',language='te',targetDuration=60)
    plan=sample(LessonRequest(topic='Python loops',language='hi',targetDuration=60),'test').lesson
    plan.language='te'
    plan.scenes[0].narration='తెలుగు భాషలో ఇది ఒక చిన్న వివరణ.'
    plan.scenes[2].narration='ఈ ఉదాహరణ ఫలితాన్ని స్పష్టంగా చూపిస్తుంది.'
    plan.scenes[1].narration='This loop repeats each value and prints its output before moving to the next item.'
    with pytest.raises(ValueError,match='native script'):audit(plan,request)

@pytest.mark.parametrize('endpoint,payload',[
    ('/api/lessons',{'topic':'Python loops','voice':'online-female'}),
    ('/api/speech',{'text':'Hello','voice':'online-female'}),
    ('/api/lessons/missing/refine',{'narrations':['one','two','three'],'voice':'online-male'})])
def test_hackathon_mode_blocks_cloud_speech_before_work(endpoint,payload):
    assert TestClient(app).post(endpoint,json=payload).status_code==422


def test_planner_accepts_explicit_misconception_and_builds_grounded_visuals(tmp_path,monkeypatch):
    import json
    from pathlib import Path
    import backend.planner as planner
    raw=json.loads((Path(__file__).parent/'fixtures/loop-plan.json').read_text())
    raw['scenes'][2]['links']=[{'source':9,'target':8,'label':'bad model hint'}]
    calls=[]
    class Response:
        status_code=200
        is_error=False
        text=''
        def raise_for_status(self):pass
        def json(self):return {'message':{'content':json.dumps(raw)}}
    class Client:
        def __init__(self,*args,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,*args,**kwargs):calls.append(kwargs);return Response()
    monkeypatch.setattr(planner.httpx,'Client',Client)
    result=planner.generate(LessonRequest(topic='Python for loops with range(3)'), 'test',tmp_path,lambda *args:None)
    assert result.lesson.scenes[1].visual.trace[-1].output=='0\n1\n2'
    assert result.lesson.scenes[2].type=='comparison'
    assert result.lesson.scenes[2].visual.rows[0].left=='0, 1, 2'
    assert result.lesson.scenes[2].visual.rows[0].right=='3'
    assert calls[0]['json']['model']=='qwen3.5:4b'
    assert calls[0]['json']['options']['num_predict']==1800


def test_pendulum_cannot_stop_at_bottom_in_either_word_order():
    request=LessonRequest(topic='Why does a pendulum slow down?',targetDuration=60)
    plan=sample(request,'test').lesson
    for statement in ['Gravity pulls it until it stops at the bottom.','At the bottom its speed is zero.']:
        plan.scenes[0].narration=statement+' Friction transfers mechanical energy to the surroundings.'
        with pytest.raises(ValueError,match='fastest at the bottom'):audit(plan,request)


def test_regional_voice_never_receives_english_only_lesson():
    request=LessonRequest(topic='Python loops',language='hi',targetDuration=60)
    plan=sample(request,'test').lesson
    plan.scenes[1].narration='The loop prints each value in the sequence on a separate line.'
    with pytest.raises(ValueError,match='native script'):audit(plan,request)


def test_gravity_cannot_pull_a_pendulum_upward():
    request=LessonRequest(topic='Why does a pendulum slow down?',targetDuration=60)
    plan=sample(request,'test').lesson
    plan.scenes[0].narration='When the bob rises, gravity pulls it upward. Its potential energy increases.'
    with pytest.raises(ValueError,match='acts downward'):audit(plan,request)


@pytest.mark.parametrize(('language','script','evaporation','vapor','boiling','wrong_sentence'),[
    ('ta','தமிழ்','ஆவியாதல்','நீராவி','கொதிநிலை','ஆவியாதல் நீரை நீராவியாக்கி கொதிநிலையில் செய்கிறது.'),
    ('te','తెలుగు','ఆవిరైపోవడం','నీటి ఆవిరి','మరిగే','ఆవిరైపోవడం నీటిని నీటి ఆవిరిగా మార్చి మరిగే సమయంలో జరుగుతుంది.'),
    ('kn','ಕನ್ನಡ','ಆವಿಯಾಗುವಿಕೆ','ನೀರಾವಿ','ಕುದಿಯುವ','ಆವಿಯಾಗುವಿಕೆ ನೀರನ್ನು ನೀರಾವಿಯಾಗಿ ಬದಲಿಸಿ ಕುದಿಯುವಾಗ ನಡೆಯುತ್ತದೆ.'),
    ('ml','മലയാളം','ബാഷ്പീകരണം','ജലബാഷ്പം','തിളയ്ക്ക','ബാഷ്പീകരണം ജലത്തെ ജലബാഷ്പമാക്കി തിളയ്ക്കുമ്പോൾ നടക്കുന്നു.'),
])
def test_regional_water_cycle_audit_rejects_boiling_misconception(language,script,evaporation,vapor,boiling,wrong_sentence):
    request=LessonRequest(topic='How does the water cycle work?',language=language,targetDuration=30)
    plan=sample(LessonRequest(topic='Python loops',language='en',targetDuration=30),'test').lesson
    plan.language=language
    title_words={
        'ta':('கருத்து','விளக்கம்','அடுத்த','கேள்வி','பதில்','கூறு','உறவு','படி'),
        'te':('భావం','వివరణ','తదుపరి','ప్రశ్న','సమాధానం','భాగం','సంబంధం','దశ'),
        'kn':('ವಿಷಯ','ವಿವರಣೆ','ಮುಂದಿನ','ಪ್ರಶ್ನೆ','ಉತ್ತರ','ಅಂಶ','ಸಂಬಂಧ','ಹಂತ'),
        'ml':('ആശയം','വിശദീകരണം','അടുത്ത','ചോദ്യം','ഉത്തരം','ഘടകം','ബന്ധം','ഘട്ടം'),
    }[language]
    plan.title=f'{script} {title_words[0]}'
    plan.objectives[0].text=f'{script} {title_words[1]}'
    plan.followUps[0]=f'{script} {title_words[2]}'
    native_by_language={
        'ta':'நீரின் இயக்கம் மற்றும் மேகங்கள் உருவாகும் விதத்தை தெளிவாக விளக்குகிறது இயற்கையில் தொடர்ச்சியாக நடைபெறும் முக்கியமான செயல்முறை இதுவாகும்.',
        'te':'నీటి ప్రయాణం మేఘాలు ఏర్పడే విధానం ప్రకృతిలో నిరంతరం జరిగే ప్రక్రియను స్పష్టంగా వివరిస్తుంది ఇది జీవనానికి చాలా ముఖ్యమైనది.',
        'kn':'ನೀರಿನ ಚಲನೆ ಮತ್ತು ಮೋಡಗಳು ರೂಪುಗೊಳ್ಳುವ ವಿಧಾನವನ್ನು ಸ್ಪಷ್ಟವಾಗಿ ವಿವರಿಸುತ್ತದೆ ಪ್ರಕೃತಿಯಲ್ಲಿ ನಿರಂತರವಾಗಿ ನಡೆಯುವ ಈ ಪ್ರಕ್ರಿಯೆ ಬಹಳ ಮುಖ್ಯವಾಗಿದೆ.',
        'ml':'ജലത്തിന്റെ സഞ്ചാരവും മേഘങ്ങൾ രൂപപ്പെടുന്ന രീതിയും വ്യക്തമായി വിശദീകരിക്കുന്നു പ്രകൃതിയിൽ തുടർച്ചയായി നടക്കുന്ന ഈ പ്രക്രിയ വളരെ പ്രധാനമാണ്.',
    }[language]
    for index,scene in enumerate(plan.scenes):
        scene.heading=f'{evaporation} {index+1}'
        scene.narration=(wrong_sentence if index==0 else f'{evaporation} {vapor} {native_by_language}')+' '+native_by_language
        scene.visual.keywords=[f'{script} {title_words[5]} {index+1}'] if scene.type=='title_card' else scene.visual.keywords
        for node_index,node in enumerate(scene.visual.nodes):node.label=f'{script} {title_words[5]} {index+node_index+1}'
        for edge in scene.visual.edges:edge.label=f'{script} {title_words[6]}'
        for step in scene.visual.trace:step.label=f'{script} {title_words[7]}'
        if scene.visual.code:scene.visual.code=scene.visual.code
    plan.quiz[0].question=f'{script} {title_words[3]}?'
    plan.quiz[0].explanation=f'{script} {title_words[1]}'
    for index,option in enumerate(plan.quiz[0].options):option.text=f'{script} {title_words[4]} {index+1}'
    with pytest.raises(ValueError,match='Evaporation is not boiling'):
        audit(plan,request)
