import copy
import json
import httpx
import pytest
from pydantic import ValidationError
from backend.schemas import LessonRequest
from backend.planner import _diagram_visual,_post_chat,_translation_max_length,normalize,output_schema
from backend.app import caption_segments,timestamp

def plan():
    return {'intent':'educational','message':'A lesson about repetition.','lesson':{'title':'Repeating instructions','level':'beginner','language':'en','objectives':['Understand repetition'], 'scenes':[
        {'id':'intro','type':'title_card','heading':'Repetition','narration':'Loops repeat instructions over a sequence of values.','visual':{'keywords':['Repetition']}},
        {'id':'code','type':'code_walkthrough','heading':'Read a loop','narration':'This loop prints each value from zero up to two.','visual':{'code':'for i in range(3):\n    print(i)','highlightLines':[1,2]}},
        {'id':'flow','type':'flow_diagram','heading':'Follow the values','narration':'After the last value, the loop finishes its work.','visual':{'nodes':['Start','Repeat','Finish']}}
    ],'quiz':[{'id':'q1','sceneId':'code','question':'Which value is printed first?','options':['Zero','One','Two'],'answer':'Zero','explanation':'The range starts at zero, so zero is the first value.'}],'followUps':['How do while loops work?']}}

def test_normalization_preserves_answer_identity_and_links():
    out=normalize(plan(),LessonRequest(topic='loops'),'lesson1').lesson
    assert out.quiz[0].correctOptionId=='option_0'
    assert out.quiz[0].lessonId=='lesson1'
    assert out.scenes[2].visual.edges[0].source=='n1'

@pytest.mark.parametrize('mutation',[
    lambda p:p['lesson']['quiz'][0].update(sceneId='missing'),
    lambda p:p['lesson']['quiz'][0].update(correctOptionId='invented'),
    lambda p:p['lesson']['scenes'][2]['visual'].update(edges=[{'source':'missing','target':'n2'}]),
    lambda p:p['lesson']['scenes'][1].update(type='run_arbitrary_javascript'),
    lambda p:p['lesson']['scenes'][1].update(script='fetch("https://example.com")'),
    lambda p:p['lesson']['scenes'][1].update(narration=''),
    lambda p:p['lesson']['scenes'][1].update(narration='![diagram](https://example.com/picture.png)'),
    lambda p:p['lesson']['scenes'][1].update(heading='Repetition'),
])
def test_invalid_plans_rejected(mutation):
    payload=plan();mutation(payload)
    with pytest.raises((ValidationError,ValueError)):normalize(payload,LessonRequest(topic='loops'),'x')

def test_greeting_has_no_lesson():
    out=normalize({'intent':'conversation','message':'Hello! What would you like to learn?','lesson':None},LessonRequest(topic='Hi'),'hi')
    assert out.lesson is None

def test_out_of_bounds_display_hints_do_not_break_a_valid_lesson():
    raw=plan();raw['lesson']['scenes'][1]['visual']['highlightLines']=[0,1,2,50]
    assert normalize(raw,LessonRequest(topic='loops'),'x').lesson.scenes[1].visual.highlightLines==[1,2]

def test_self_labeled_endpoint_is_recovered_without_guessing_a_label():
    raw=plan();raw['lesson']['scenes'][2]['visual']={'nodes':[{'id':'1912','label':'1912'},{'id':'1940','label':'1940'}],'edges':[{'source':'1940','target':'1954'}]}
    scene=normalize(raw,LessonRequest(topic='timeline'),'x').lesson.scenes[2]
    assert scene.visual.nodes[-1].id==scene.visual.nodes[-1].label=='1954'

def test_diagram_drops_links_to_missing_labels_without_rejecting_the_lesson():
    visual=_diagram_visual(
        {'layout':'linear','links':[
            {'source':0,'target':1,'label':'creates a prediction'},
            {'source':1,'target':2,'label':'combines results'},
        ]},
        ['Decision trees','Random forest'],
    )
    assert visual['edges']==[{'source':'n1','target':'n2','label':'creates a prediction'}]

def test_diagram_repairs_missing_links_with_a_labeled_connection():
    visual=_diagram_visual({'layout':'linear','links':[]},['Input','Result'])
    assert visual['edges']==[{'source':'n1','target':'n2','label':'relates to'}]

def test_ollama_server_error_retries_once_with_smaller_context():
    contexts=[]
    def respond(request):
        context=json.loads(request.content)['options']['num_ctx']
        contexts.append(context)
        if len(contexts)==1:return httpx.Response(500,text='GPU memory unavailable',request=request)
        return httpx.Response(200,json={'message':{'content':'{}'}},request=request)
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        response=_post_chat(client,{'options':{'num_ctx':8192}})
    assert response.json()['message']['content']=='{}'
    assert contexts==[8192,4096]

def test_ollama_error_includes_local_server_detail():
    def respond(request):
        return httpx.Response(500,text='runner allocation failed',request=request)
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(httpx.HTTPStatusError,match='runner allocation failed'):
            _post_chat(client,{'options':{'num_ctx':4096}})

def test_translation_limits_match_diagram_and_quiz_schema():
    assert _translation_max_length('scenes.1.visual.edges.0.label')==60
    assert _translation_max_length('scenes.1.visual.nodes.0.label')==90
    assert _translation_max_length('quiz.0.options.2.text')==180

def test_unambiguous_template_reference_resolves_to_scene_id():
    raw=plan();raw['lesson']['quiz'][0]['sceneId']='code_walkthrough'
    assert normalize(raw,LessonRequest(topic='loops'),'x').lesson.quiz[0].sceneId=='code'

def test_truncated_tail_keeps_complete_spoken_explanation():
    raw=plan();raw['lesson']['scenes'][1]['narration']='This loop prints each value. Its final partial'
    assert normalize(raw,LessonRequest(topic='loops'),'x').lesson.scenes[1].narration=='This loop prints each value.'

def test_comparison_schema_forces_headers():
    required=output_schema()['$defs']['VisualConfiguration']['required']
    assert all(name in required for name in ['leftTitle','rightTitle'])
    assert output_schema()['properties']['scenes']['maxItems']==3
    assert 'title' in output_schema()['properties']

def test_caption_timing_covers_measured_audio_without_gaps():
    words=' '.join('word'+str(i) for i in range(35));captions=caption_segments(words,12.75)
    assert captions[0]['start']==0
    assert captions[-1]['end']==pytest.approx(12.75)
    assert all(a['end']==b['start'] for a,b in zip(captions,captions[1:]))
    assert ' '.join(c['text'] for c in captions)==words
    assert timestamp(65.125)=='00:01:05.125'

@pytest.mark.parametrize(('language','text'),[
    ('hi','यह वाक्य हिंदी में लिखा गया है।'),
    ('kn','ಈ ವಾಕ್ಯ ಕನ್ನಡದಲ್ಲಿ ಬರೆಯಲಾಗಿದೆ.'),
    ('te','ఈ వాక్యం తెలుగులో వ్రాయబడింది.'),
])
def test_caption_segments_preserve_requested_language_text(language,text):
    captions=caption_segments(text,4.0)
    assert ''.join(caption['text'] for caption in captions)==text


@pytest.mark.parametrize(('language','script','narrations'),[
    ('te','తెలుగు',[
        'ఒక క్రమంలోని ప్రతి విలువ కోసం లూప్ సూచనను అమలు చేసి ఒకే పనిని మళ్లీ రాయాల్సిన అవసరాన్ని తగ్గిస్తుంది ఇది ప్రక్రియను సులభం చేస్తుంది',
        'ఈ ఉదాహరణలో చరరాశి ప్రతి సంఖ్యను వరుసగా స్వీకరిస్తుంది లోపలి ముద్రణ సూచన ఆ విలువను తెరపై చూపిస్తుంది',
        'చివరగా విలువలు క్రమంగా బయటకు వస్తాయి పై పరిమితి చేరదు కాబట్టి లూప్ సరైన సంఖ్యలో పునరావృతమై ముగుస్తుంది']),
    ('ta','தமிழ்',[
        'ஒரு தொடரின் ஒவ்வொரு மதிப்பிற்கும் சுழற்சி கட்டளையை இயக்கி ஒரே வேலையை மீண்டும் எழுத வேண்டிய தேவையைக் குறைக்கிறது இது செயல்முறையை எளிதாக்குகிறது',
        'இந்த எடுத்துக்காட்டில் மாறி ஒவ்வொரு எண்ணையும் வரிசையாகப் பெறுகிறது உள்ளிருக்கும் அச்சிடும் கட்டளை அந்த மதிப்பைத் திரையில் காட்டுகிறது',
        'இறுதியில் மதிப்புகள் வரிசையாக வெளிவந்து மேலெல்லை சேர்க்கப்படாது அதனால் சுழற்சி சரியான எண்ணிக்கையில் முடிவடைகிறது']),
    ('kn','ಕನ್ನಡ',[
        'ಒಂದು ಸರಣಿಯ ಪ್ರತಿಯೊಂದು ಮೌಲ್ಯಕ್ಕೆ ಲೂಪ್ ಸೂಚನೆಯನ್ನು ನಡೆಸಿ ಅದೇ ಕೆಲಸವನ್ನು ಮತ್ತೆ ಬರೆಯುವ ಅಗತ್ಯವನ್ನು ಕಡಿಮೆ ಮಾಡುತ್ತದೆ ಇದು ಕ್ರಮವನ್ನು ಸರಳಗೊಳಿಸುತ್ತದೆ',
        'ಈ ಉದಾಹರಣೆಯಲ್ಲಿ ಚರವು ಪ್ರತಿಯೊಂದು ಸಂಖ್ಯೆಯನ್ನು ಕ್ರಮವಾಗಿ ಸ್ವೀಕರಿಸುತ್ತದೆ ಒಳಗಿನ ಮುದ್ರಣ ಸೂಚನೆ ಆ ಮೌಲ್ಯವನ್ನು ಪರದೆಯಲ್ಲಿ ತೋರಿಸುತ್ತದೆ',
        'ಕೊನೆಯಲ್ಲಿ ಮೌಲ್ಯಗಳು ಕ್ರಮವಾಗಿ ಹೊರಬರುತ್ತವೆ ಮೇಲಿನ ಮಿತಿ ಸೇರುವುದಿಲ್ಲ ಆದ್ದರಿಂದ ಲೂಪ್ ಸರಿಯಾದ ಸಂಖ್ಯೆಯ ಪುನರಾವರ್ತನೆಯ ನಂತರ ಮುಗಿಯುತ್ತದೆ']),
    ('ml','മലയാളം',[
        'ഒരു നിരയിലെ ഓരോ മൂല്യത്തിനും ലൂപ്പ് നിർദ്ദേശം പ്രവർത്തിപ്പിച്ച് ഒരേ ജോലി വീണ്ടും എഴുതേണ്ട ആവശ്യം കുറയ്ക്കുന്നു ഇത് പ്രക്രിയ ലളിതമാക്കുന്നു',
        'ഈ ഉദാഹരണത്തിൽ ചരത്തിന് ഓരോ സംഖ്യയും ക്രമമായി ലഭിക്കുന്നു ഉള്ളിലെ അച്ചടി നിർദ്ദേശം ആ മൂല്യം സ്ക്രീനിൽ കാണിക്കുന്നു',
        'അവസാനം മൂല്യങ്ങൾ ക്രമമായി പുറത്തുവരുന്നു മുകളിലെ പരിധി ഉൾപ്പെടുന്നില്ല അതിനാൽ ലൂപ്പ് ശരിയായ എണ്ണം ആവർത്തിച്ച ശേഷം അവസാനിക്കുന്നു']),
])
def test_regional_translation_uses_english_source_and_preserves_visual_code(monkeypatch,tmp_path,language,script,narrations):
    import json
    from pathlib import Path
    import backend.planner as planner
    raw=json.loads((Path(__file__).parent/'fixtures/loop-plan.json').read_text(encoding='utf-8'))
    calls=[];translated_count=0

    class Response:
        status_code=200
        is_error=False
        text=''
        def __init__(self,content):self.content=content
        def raise_for_status(self):pass
        def json(self):return {'message':{'content':self.content}}

    class Client:
        def __init__(self,*args,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,*args,**kwargs):
            nonlocal translated_count
            payload=kwargs['json'];calls.append(payload)
            schema=payload['format']
            if 'scenes' in schema.get('properties',{}):
                return Response(json.dumps(raw))
            if set(schema.get('properties',{}))=={'passed','issues'}:
                return Response(json.dumps({'passed':True,'issues':[]}))
            translated={}
            for key in schema['properties']:
                translated_count+=1
                if key.startswith('scenes.') and key.endswith('.narration'):
                    translated[key]=narrations[int(key.split('.')[1])]
                else:
                    suffix=translated_count
                    translated[key]=f'{script} சொல் {suffix}' if language=='ta' else f'{script} ಪದ {suffix}' if language=='kn' else f'{script} పదం {suffix}' if language=='te' else f'{script} വാക്ക് {suffix}'
            return Response(json.dumps(translated,ensure_ascii=False))

    monkeypatch.setattr(planner.httpx,'Client',Client)
    request=LessonRequest(topic='Python for loops',language=language,targetDuration=50)
    result=planner.generate(request,'regional-test',tmp_path,lambda *args:None)
    assert 'in English' in calls[0]['messages'][1]['content']
    assert all(call['model']=='qwen3.5:4b' for call in calls)
    assert result.lesson.language==language
    assert all(question.language==language for question in result.lesson.quiz)
    original_code=next(scene['code'] for scene in raw['scenes'] if 'code' in scene)
    localized_code=next(scene.visual.code for scene in result.lesson.scenes if scene.type=='code_walkthrough')
    assert localized_code==original_code
    assert result.lesson.scenes[1].narration==narrations[1]
    assert len(calls)>1


def test_local_translation_review_rejects_mistranslated_content(tmp_path):
    import json
    import backend.planner as planner
    source_request=LessonRequest(topic='Python loops',targetDuration=30)
    source=normalize(plan(),source_request,'review-test').lesson
    localized_data=source.model_dump()
    localized_data['language']='te'
    localized_data['scenes'][0]['narration']='ఈ వాక్యం తెలుగులో ఉంది.'
    localized=type(source).model_validate(localized_data)

    class Response:
        status_code=200
        is_error=False
        text=''
        def raise_for_status(self):pass
        def json(self):return {'message':{'content':json.dumps({'passed':False,'issues':['scenes.0.narration: meaning changed']})}}

    class Client:
        def post(self,*args,**kwargs):return Response()

    with pytest.raises(ValueError,match='meaning changed'):
        planner._review_lesson(source,localized,source_request.model_copy(update={'language':'te'}),Client(),lambda *args:None,tmp_path,1)
