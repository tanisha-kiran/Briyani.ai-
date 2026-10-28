import importlib,json,sqlite3,concurrent.futures
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend import library
from backend.schemas import LessonRequest
from backend.quality import VERSION as QUALITY_VERSION
appmod=importlib.import_module('backend.app')

@pytest.fixture
def store(tmp_path,monkeypatch):
    dbfile=tmp_path/'jobs.sqlite3'
    def connection():
        db=sqlite3.connect(dbfile,timeout=10);db.row_factory=sqlite3.Row;return db
    with connection() as db:
        db.execute('CREATE TABLE jobs(id TEXT PRIMARY KEY,cache_key TEXT,request TEXT,status TEXT,stage TEXT,progress INTEGER,message TEXT,result TEXT,created REAL)')
        library.ensure_index(db)
    calls=[]
    class Executor:
        def submit(self,*args,**kwargs):calls.append((args,kwargs))
    monkeypatch.setattr(appmod,'connection',connection);monkeypatch.setattr(appmod,'OUTPUT',tmp_path);monkeypatch.setattr(appmod,'executor',Executor())
    monkeypatch.setattr(appmod,'installed_voices',lambda:[{'language':'en','localAvailable':True},{'language':'kn','localAvailable':True}])
    monkeypatch.setattr(appmod,'model_info',lambda:pytest.fail('Cache lookup must not call the model'))
    return connection,tmp_path,calls

def add(store,topic='How does photosynthesis work?',language='en',voice='female',ident='saved',status='completed'):
    connection,root,_=store;request=LessonRequest(topic=topic,language=language,voice=voice,targetDuration=60).model_dump()
    payload={'quality':{'version':QUALITY_VERSION,'passed':True},'videoModel':library.VIDEO_MODEL,'lesson':{'title':'Photosynthesis and plant energy','scenes':[{'heading':'Light and leaves','narration':'Plants use sunlight to make sugar from water and carbon dioxide.'}],'duration':60},'videoUrl':f'/api/lessons/{ident}/video','message':'A generated lesson'}
    folder=root/ident;folder.mkdir();(folder/'lesson.mp4').write_bytes(b'video fixture')
    with connection() as db:
        db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?)',(ident,'legacy-version-key',json.dumps(request),status,'ready',100,'ready',json.dumps(payload),1))
        library.rebuild(db,root)
    return request

def test_persistent_equivalent_lookup_before_model_and_no_regeneration(store):
    add(store)
    with store[0]() as db:library.rebuild(db,store[1])
    reply=TestClient(appmod.app).post('/api/lessons',json={'topic':'  Please explain Photosynthesis! ','targetDuration':60,'cpuOnly':True}).json()
    assert reply['cached'] and reply['id']=='saved' and reply['result']['lesson']['duration']==60
    assert not store[2]

def test_related_video_is_previewed_without_starting_a_job(store):
    add(store)
    reply=TestClient(appmod.app).post('/api/lessons',json={'topic':'Why do plants need sunlight?'}).json()
    assert reply['status']=='related' and reply['matches'][0]['id']=='saved'
    assert not store[2]

def test_language_and_voice_are_not_silently_changed(store):
    add(store)
    with store[0]() as db:
        assert library.lookup(db,store[1],LessonRequest(topic='Explain photosynthesis',language='kn').model_dump()) is None
        assert library.lookup(db,store[1],LessonRequest(topic='Explain photosynthesis',voice='online-female').model_dump())['status']=='related'

@pytest.mark.parametrize('query',['Explain range(4)','Explain why photosynthesis does not need sunlight'])
def test_numbers_and_negation_are_not_equivalent(store,query):
    add(store,topic='Explain range(3)' if 'range' in query else 'Explain why photosynthesis needs sunlight')
    with store[0]() as db:
        result=library.lookup(db,store[1],LessonRequest(topic=query).model_dump())
        assert result is None or result['status']=='related'

def test_missing_video_does_not_return_cache_hit(store):
    add(store);(store[1]/'saved/lesson.mp4').unlink()
    reply=TestClient(appmod.app).post('/api/lessons',json={'topic':'Explain photosynthesis'}).json()
    assert reply['status']=='queued' and not reply['cached'] and len(store[2])==1

def test_force_new_is_explicit(store):
    add(store)
    reply=TestClient(appmod.app).post('/api/lessons',json={'topic':'Explain photosynthesis','reuseSaved':False}).json()
    assert not reply['cached'] and len(store[2])==1

def test_simultaneous_duplicate_requests_share_one_job(store):
    client=TestClient(appmod.app)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        replies=list(pool.map(lambda _:client.post('/api/lessons',json={'topic':'Explain volcanoes'}).json(),range(4)))
    assert len({r['id'] for r in replies})==1 and len(store[2])==1

def test_unrelated_fallback_is_not_indexed(store):
    add(store)
    with store[0]() as db:
        db.execute('DELETE FROM video_library')
        row=db.execute('SELECT result FROM jobs').fetchone();payload=json.loads(row['result']);payload['message']='Reviewed demo, not a generated answer to your question.'
        db.execute('UPDATE jobs SET result=?',(json.dumps(payload),));library.rebuild(db,store[1])
        assert db.execute('SELECT COUNT(*) FROM video_library').fetchone()[0]==0


def test_reviewed_fallback_is_never_reused_as_generated_answer(store):
    add(store,ident='fallback-en')
    with store[0]() as db:assert db.execute('SELECT COUNT(*) FROM video_library').fetchone()[0]==0

def test_pre_ltx_videos_are_not_reused_or_suggested(store):
    add(store)
    with store[0]() as db:
        row=db.execute('SELECT result FROM jobs').fetchone()
        payload=json.loads(row['result']);payload.pop('videoModel')
        db.execute('UPDATE jobs SET result=?',(json.dumps(payload),))
        library.rebuild(db,store[1])
        assert db.execute('SELECT COUNT(*) FROM video_library').fetchone()[0]==0
        assert library.lookup(db,store[1],LessonRequest(topic='Explain photosynthesis').model_dump()) is None


@pytest.mark.parametrize('original,query',[
    ('Explain range(3)','Explain range(-3)'),
    ('Explain x < 3','Explain x > 3'),
    ('Explain x == 3','Explain x != 3'),
    ('Explain 1.5','Explain 1,5'),
])
def test_operators_are_not_equivalent(store,original,query):
    add(store,topic=original)
    with store[0]() as db:
        result=library.lookup(db,store[1],LessonRequest(topic=query).model_dump())
        assert result is None or result['status']=='related'


def test_requested_length_is_part_of_video_memory(store):
    add(store)
    with store[0]() as db:
        hit=library.lookup(db,store[1],LessonRequest(topic='Explain photosynthesis',targetDuration=60).model_dump())
        other=library.lookup(db,store[1],LessonRequest(topic='Explain photosynthesis',targetDuration=90).model_dump())
        assert hit['match']=='equivalent'
        assert other is None or other['status']=='related'
        assert library.request_key(LessonRequest(topic='loops',targetDuration=30).model_dump()) != library.request_key(LessonRequest(topic='loops',targetDuration=90).model_dump())


def test_animated_history_is_never_labeled_as_ltx(store):
    add(store)
    with store[0]() as db:
        assert library.lookup(db,store[1],LessonRequest(topic='Explain photosynthesis',videoEngine='ltx').model_dump()) is None
