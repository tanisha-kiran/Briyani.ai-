import copy
import pytest
from backend.schemas import LessonRequest, Scene
from backend.voices import synthesize

def test_default_voice_is_neural():
    assert LessonRequest(topic='water cycle').voice=='female'

@pytest.mark.parametrize('layout',['cycle','branch','hub'])
def test_relationship_topologies_keep_explicit_edges(layout):
    scene=Scene.model_validate({'id':'s','type':'flow_diagram','heading':'Water movement','narration':'Water moves between the surface and the atmosphere.','visual':{'layout':layout,'nodes':[{'id':'a','label':'Surface'},{'id':'b','label':'Cloud'},{'id':'c','label':'Rain'}],'edges':[{'source':'a','target':'b'},{'source':'b','target':'c'},{'source':'c','target':'a'}]}})
    assert len(scene.visual.edges)==3

def test_motion_requires_named_concepts():
    with pytest.raises(ValueError):
        Scene.model_validate({'id':'s','type':'animated_illustration','heading':'Motion','narration':'Objects transfer energy when they collide.','visual':{'motion':'collision'}})

def test_missing_neural_never_falls_back_to_robot(monkeypatch):
    import backend.voices as voices
    monkeypatch.setattr(voices,'local_ready',lambda code:False)
    monkeypatch.setattr(voices,'basic_audio',lambda *args:pytest.fail('Robotic fallback invoked'))
    with pytest.raises(ValueError,match='not installed'):
        synthesize('A unique missing neural voice test sentence.','en',1,'female')

def test_online_unsupported_language_is_explicit():
    import backend.voices as voices
    with pytest.raises(ValueError,match='local native'):
        voices.online_audio('A test.','or',1,'online-female','british')
