import math
import wave
import pytest
from backend.timing import fit_narration, seconds, TimingMismatch
from backend.app import caption_segments
from backend.schemas import LessonRequest


def tone(path,duration):
    import array
    samples=array.array('h',(int(8000*math.sin(i*2*math.pi*220/16000)) for i in range(round(duration*16000))))
    with wave.open(str(path),'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(16000);out.writeframes(samples.tobytes())


@pytest.mark.parametrize('target',[30,60,90])
def test_exact_length_without_truncated_speech(tmp_path,target):
    paths=[tmp_path/f'{i}.wav' for i in range(3)]
    for path in paths:tone(path,(target-2)/3)
    result,factor=fit_narration(paths,target,100)
    assert sum(round(duration*15) for _,_,duration in result)==target*15
    assert all(seconds(path)<=duration for path,_,duration in result)
    assert .8<=factor<=1.3


def test_short_explanation_requests_more_content_instead_of_silent_padding(tmp_path):
    path=tmp_path/'short.wav';tone(path,5)
    with pytest.raises(TimingMismatch) as failure:fit_narration([path],60,15)
    assert failure.value.word_budget>100


@pytest.mark.parametrize('language,text',[
    ('hi','पानी गर्म होने पर भाप बनता है। ठंडी हवा में भाप बूंदों में बदलती है।'),
    ('ta','நீர் சூடாகும்போது ஆவியாகிறது. குளிர்ந்த காற்றில் நீராவி துளிகளாக மாறுகிறது.'),
    ('te','నీరు వేడెక్కినప్పుడు ఆవిరవుతుంది. చల్లని గాలిలో ఆవిరి నీటి బిందువులుగా మారుతుంది.'),
    ('bn','জল গরম হলে বাষ্প হয়। ঠান্ডা বাতাসে বাষ্প জলের ফোঁটায় পরিণত হয়।'),
    ('mr','पाणी गरम झाल्यावर वाफ होते. थंड हवेत वाफेचे पाण्याच्या थेंबांत रूपांतर होते.')])
def test_five_indian_language_captions_preserve_narration(language,text):
    request=LessonRequest(topic='water cycle',language=language)
    assert request.language==language
    captions=caption_segments(text,12)
    assert ' '.join(c['text'] for c in captions)==text
    assert captions[-1]['end']==pytest.approx(12)


def test_default_generator_is_local_animation_and_ltx_is_explicit():
    assert LessonRequest(topic='water cycle').videoEngine=='animated'
    assert LessonRequest(topic='water cycle',videoEngine='ltx').videoEngine=='ltx'


def test_water_cycle_rejects_boiling_misconception_in_hindi():
    from backend.samples import sample
    from backend.quality import audit
    request=LessonRequest(topic='How does the water cycle work?',language='hi',targetDuration=30)
    plan=sample(request,'test').lesson
    plan.scenes[0].narration='सूरज की गर्मी से समुद्र का पानी उबलकर वायु में बदल जाता है। यह जल चक्र की शुरुआत है।'
    with pytest.raises(ValueError,match='Evaporation is not boiling'):audit(plan,request)


def test_english_water_cycle_requires_explicit_water_vapor_and_nonboiling_explanation():
    from backend.samples import sample
    from backend.quality import audit
    request=LessonRequest(topic='How does the water cycle work?',targetDuration=30)
    plan=sample(request,'test').lesson
    with pytest.raises(ValueError,match='Explicitly identify the gas as water vapor'):
        audit(plan,request)
    plan.scenes[0].narration='Sunlight warms surface water, and some liquid becomes water vapor without boiling. This happens at the surface during ordinary warm conditions.'
    plan.scenes[1].narration='This evaporation occurs below the boiling point as water molecules escape from the surface. The ocean does not need to reach its boiling temperature.'
    plan.scenes[2].narration='Water vapor rises, cools, and condenses into droplets that can form clouds. Later, droplets may become large enough to fall back as rain.'
    for edge in plan.scenes[2].visual.edges:edge.label='continues the process'
    assert audit(plan,request)['passed']


def test_schema_endpoint_exposes_validated_input_and_scene_contract():
    from fastapi.testclient import TestClient
    from backend.app import app
    reply=TestClient(app).get('/api/lessons/schema')
    assert reply.status_code==200
    data=reply.json()
    assert data['input']['properties']['videoEngine']['default']=='animated'
    assert 'scenes' in data['planner']['required']
    assert 'narration' in data['planner']['$defs']['Scene']['required']


def test_mixed_script_hybrid_words_are_not_sent_to_native_tts():
    from backend.samples import sample
    from backend.quality import audit
    request=LessonRequest(topic='Evaporation',language='hi',targetDuration=30)
    plan=sample(request,'test').lesson
    plan.scenes[0].narration='पानी गर्म होकर वाष्पisation में बदलता है। यह एक प्राकृतिक प्रक्रिया है।'
    with pytest.raises(ValueError,match='hybrid'):audit(plan,request)
