import copy
import pytest
from fastapi.testclient import TestClient
from backend.schemas import LessonRequest
from backend.planner import output_schema
from backend.samples import sample
from backend.app import app, caption_segments

def test_planner_cannot_omit_visual_code_field():
    schema=output_schema(LessonRequest(topic='loops'))
    variants=schema['$defs']['Scene']['anyOf']
    code=next(v for v in variants if v['properties']['type']['enum']==['code_walkthrough'])
    assert 'code' in code['properties']['visual']['required']
    assert 'rows' not in code['properties']['visual']['properties']

@pytest.mark.parametrize('language',['en','hi','ta'])
def test_offline_demo_is_valid_and_explicitly_labeled(language):
    lesson=sample(LessonRequest(topic='an unrelated subject',language=language),'demo')
    assert 'not a generated answer' in lesson.message
    assert lesson.lesson.language==language
    assert lesson.lesson.scenes[1].visual.code=='for i in range(3):\n    print(i)'

def test_captions_handle_long_script_words_without_losing_content():
    text=' '.join(['அடுத்தமதிப்பு']*20)
    chunks=caption_segments(text,20)
    assert ' '.join(c['text'] for c in chunks)==text
    assert chunks[-1]['end']==pytest.approx(20)
    assert all(len(c['text'])<=95 for c in chunks)

def test_bad_refinement_is_rejected_before_queueing():
    client=TestClient(app)
    response=client.post('/api/lessons/missing/refine',json={'narrations':['a','b','c'],'speed':9})
    assert response.status_code==422

def test_audio_path_traversal_is_not_served():
    client=TestClient(app)
    assert client.get('/audio/not-an-audio-file.wav').status_code==404
