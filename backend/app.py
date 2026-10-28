import base64, binascii, hashlib, json, math, os, re, sqlite3, subprocess, time, uuid, wave, threading, shutil, tempfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
import httpx
from .voices import voices as installed_voices, synthesize, CACHE as SPEECH_CACHE
from .asr import ready as asr_ready, transcribe as transcribe_audio
import imageio_ffmpeg
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from .schemas import LessonRequest, LessonPlan
from .planner import generate, normalize, MODEL, OLLAMA
from . import library
from .timing import fit_narration, TimingMismatch
from .quality import audit,VERSION as QUALITY_VERSION
from .ltx_video_service import (
    generate_scene_clips,
    require_runtime as require_ltx_runtime,
    unload_ollama_model,
)

ROOT=Path(__file__).resolve().parent.parent
OUTPUT=ROOT/'output'/'lessons';OUTPUT.mkdir(parents=True,exist_ok=True)
RUNTIME=ROOT/'output'/'runtime';RUNTIME.mkdir(parents=True,exist_ok=True)
DB=OUTPUT/'jobs.sqlite3'; VERSION='offline-teaching-5'
executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='lesson')
def connection():
    db=sqlite3.connect(DB,timeout=30);db.row_factory=sqlite3.Row;return db
with connection() as db:
    db.execute('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, cache_key TEXT, request TEXT, status TEXT, stage TEXT, progress INTEGER, message TEXT, result TEXT, created REAL)')

def register_packaged_samples():
    for folder in (ROOT/'examples').glob('fallback-*'):
        if not (folder/'lesson.json').is_file() or not (folder/'lesson.mp4').is_file():continue
        try:
            payload=json.loads((folder/'lesson.json').read_text(encoding='utf-8'));plan=payload['lesson']
            request=LessonRequest(topic='Built-in reviewed Python-loop sample',language=plan['language'],level=plan['level'],targetDuration=60)
            ident=folder.name;dest=OUTPUT/ident;dest.mkdir(exist_ok=True)
            for name in ('lesson.mp4','lesson.json','captions.vtt'):
                if (folder/name).is_file() and not (dest/name).exists():shutil.copyfile(folder/name,dest/name)
            with connection() as db:db.execute('INSERT OR IGNORE INTO jobs VALUES (?,?,?,?,?,?,?,?,?)',(ident,ident,request.model_dump_json(),'completed','ready',100,'Reviewed offline sample',json.dumps(payload,ensure_ascii=False),time.time()))
        except (ValueError,KeyError,OSError):continue

def recover_interrupted_jobs():
    with connection() as db:db.execute("UPDATE jobs SET status='failed',stage='interrupted',message='The engine restarted before this lesson finished. Please retry.' WHERE status IN ('queued','running')")

@asynccontextmanager
async def lifespan(app):
    register_packaged_samples()
    recover_interrupted_jobs()
    with connection() as db:library.rebuild(db,OUTPUT)
    yield

app=FastAPI(title='Biryani local lesson engine',lifespan=lifespan)

def update(job_id,**fields):
    with connection() as db:db.execute('UPDATE jobs SET '+','.join(k+'=?' for k in fields)+' WHERE id=?',(*fields.values(),job_id))
def job(job_id):
    with connection() as db:row=db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
    if row is None:raise HTTPException(404,'Lesson not found')
    return dict(row)
def model_info():
    with httpx.Client(trust_env=False,timeout=10) as client:
        r=client.get(OLLAMA+'/api/tags');r.raise_for_status()
        found=next((m for m in r.json().get('models',[]) if m['name'] in (MODEL,MODEL+':latest')),None)
        if not found:raise ValueError('The selected local model was not found in Ollama. Run SETUP-LOCAL-MODELS.cmd before using the studio.')
        return found
def caption_segments(text,duration):
    # Phrase-aligned estimates within measured speech, not claimed forced alignment.
    words=text.split();chunks=[];line=[]
    for word in words:
        if line and (len(line)>=11 or len(' '.join(line+[word]))>95):chunks.append(' '.join(line));line=[]
        line.append(word)
    if line:chunks.append(' '.join(line))
    weights=[len(c.split()) for c in chunks];total=sum(weights);elapsed=0;out=[]
    for chunk,weight in zip(chunks,weights):
        end=elapsed+duration*weight/total;out.append({'text':chunk,'start':elapsed,'end':end});elapsed=end
    return out
def wav_seconds(path):
    with wave.open(str(path),'rb') as wav:return wav.getnframes()/wav.getframerate()
def speech(text,language,path,speed=1.0,voice='female',accent='british'):
    source=synthesize(text,language,speed,voice,accent)
    path.write_bytes(source.read_bytes())
    return wav_seconds(path)

def write_preview(out, job_id, lesson, ready_scenes, state):
    """Persist only the validated data needed by the progressive SVG player."""
    payload={
        'id':job_id, 'state':state, 'title':lesson['title'],
        'language':lesson['language'], 'objectives':lesson.get('objectives',[]),
        'readyScenes':ready_scenes, 'sceneCount':len(lesson['scenes']),
    }
    temporary=out/'preview.tmp.json'
    temporary.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8')
    temporary.replace(out/'preview.json')

def extract_ltx_background_frames(clip,folder,index):
    # Decode every source frame once; fps resampling can discard the final
    # frame at the MP4 end timestamp. Never pad a short clip to look complete.
    for stale in folder.glob(f'background-{index}-*.png'):
        stale.unlink()
    pattern=folder/f'background-{index}-%02d.png'
    subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-y',
            '-i',str(clip),'-vf',
            'scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720',
            '-fps_mode','passthrough','-start_number','0',str(pattern),
        ],
        check=True,capture_output=True,text=True,timeout=120,
    )
    frames=sorted(folder.glob(f'background-{index}-*.png'))
    if len(frames)!=17:
        raise ValueError(f'LTX scene {index+1} produced {len(frames)} usable background frames; expected 17.')
    return frames

def timestamp(seconds):
    ms=round(seconds*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02}.{ms%1000:03}'
def run(job_id,request,draft_id=None,prepared=None):
    out=OUTPUT/job_id;out.mkdir(exist_ok=True)
    started=time.perf_counter();stage_started=started;current_stage=None;timings={}
    def progress(value,stage,message):
        nonlocal stage_started,current_stage
        now=time.perf_counter()
        if current_stage!=stage:
            if current_stage:timings[current_stage]=timings.get(current_stage,0)+now-stage_started
            current_stage=stage;stage_started=now
        update(job_id,status='running',progress=value,stage=stage,message=message)
    temporary_frame_dir=None
    try:
        progress(3,'checking','Checking your local planner')
        result=prepared
        if draft_id:
            drafts=sorted((OUTPUT/draft_id).glob('planner-*.json'),reverse=True)
            for draft in drafts:
                try:
                    result=normalize(json.loads(draft.read_text(encoding='utf-8')),request,job_id)
                    (out/'planner-recovered.json').write_text(result.model_dump_json(indent=2),encoding='utf-8');break
                except (ValueError,TypeError,KeyError):pass
        if result is None:
            try:result=generate(request,job_id,out,progress)
            except (httpx.HTTPError,ValueError,TypeError,KeyError) as error:
                (out/'planner-error.txt').write_text(str(error),encoding='utf-8')
                raise ValueError(f'Local lesson planning failed: {str(error)[:900]}') from error
        payload=result.model_dump();payload['id']=job_id
        if result.intent!='educational':
            update(job_id,status='completed',stage='conversation',progress=100,message=payload['message'],result=json.dumps(payload,ensure_ascii=False));return
        voices=installed_voices()
        if not any(v['language'].split('-')[0]==request.language and v.get('localAvailable',False) for v in voices):raise ValueError(f'No offline narration voice is installed for {request.language}. Install the native neural voice. No English fallback video was substituted.')
        payload['quality']=audit(result.lesson,request)
        for timing_attempt in range(3):
            plan=payload['lesson'];paths=[];ready_scenes=[]
            write_preview(out,job_id,plan,ready_scenes,'narrating')
            for i,scene in enumerate(plan['scenes']):
                progress(23+round(18*i/len(plan['scenes'])),'narrating',f"Recording {request.language} narration {i+1} of {len(plan['scenes'])}")
                path=out/f'scene-{i}.wav'
                raw_duration=speech(scene['narration'],request.language,path,request.speechSpeed,request.voice,request.accent)
                paths.append(path)
                # The student can start this validated scene immediately; the
                # final timing pass and MP4 continue in the background.
                ready_scenes.append({'index':i,'id':scene['id'],'type':scene['type'],
                    'heading':scene['heading'],'narration':scene['narration'],
                    'visual':scene['visual'],'duration':raw_duration})
                write_preview(out,job_id,plan,ready_scenes,'narrating')
            word_count=sum(len(scene['narration'].split()) for scene in plan['scenes'])
            try:
                fitted,tempo=fit_narration(paths,request.targetDuration,word_count)
                break
            except TimingMismatch as mismatch:
                if prepared is not None or timing_attempt==2:raise
                progress(20,'adjusting_length',f'Refining the explanation to fit {request.targetDuration} seconds')
                retry_dir=out/f'timing-retry-{timing_attempt+1}';retry_dir.mkdir(exist_ok=True)
                result=generate(request,job_id,retry_dir,progress,spoken_word_budget=mismatch.word_budget)
                payload=result.model_dump();payload['id']=job_id
                payload['quality']=audit(result.lesson,request)
        scenes=[];offset=0;vtt=['WEBVTT','']
        for scene,(audio_path,audio_duration,duration) in zip(plan['scenes'],fitted):
            captions=caption_segments(scene['narration'],audio_duration)
            for c in captions:vtt.extend([f'{timestamp(offset+c["start"])} --> {timestamp(offset+c["end"])}',c['text'],''])
            scenes.append({**scene,'audioPath':str(audio_path),'audioDuration':audio_duration,'start':offset,'duration':duration,'captions':captions})
            offset+=duration
        write_preview(out,job_id,plan,[{k:v for k,v in scene.items() if k not in ('audioPath','ltxBackgroundFrames','captions','start')} | {'index':index} for index,scene in enumerate(scenes)],'rendering')
        if request.videoEngine=='ltx':
            progress(43,'checking_video','Checking CUDA and LTX FP8 kernels')
            require_ltx_runtime()
            progress(44,'releasing_planner','Releasing the local planner from GPU memory')
            unload_ollama_model(OLLAMA,MODEL)
            clips=generate_scene_clips(request.topic,scenes,out,progress)
            if len(clips)!=len(scenes):raise ValueError('LTX did not generate one clip for every lesson scene.')
            temporary_frame_dir=Path(tempfile.mkdtemp(prefix='ltx-frames-',dir=out))
            for i,(scene,clip) in enumerate(zip(scenes,clips)):
                scene['ltxBackgroundFrames']=[str(path) for path in extract_ltx_background_frames(clip,temporary_frame_dir,i)]
        manifest={'language':request.language,'output':str(out),'ffmpeg':imageio_ffmpeg.get_ffmpeg_exe(),'scenes':scenes,'cpuOnly':request.cpuOnly,'targetDuration':request.targetDuration};manifest_path=out/'render.json';manifest_path.write_text(json.dumps(manifest,ensure_ascii=False),encoding='utf-8')
        (out/'captions.vtt').write_text('\n'.join(vtt),encoding='utf-8')
        progress(70,'rendering','Rendering local teaching visuals, narration and captions' if request.videoEngine=='animated' else 'Compositing LTX backgrounds with teaching visuals')
        worker=ROOT/'renderer'/'dist'/'export.mjs'
        if not worker.exists():raise ValueError('Renderer is not built. Run npm run renderer:build first.')
        with (out/'renderer-error.log').open('w',encoding='utf-8') as error_log:
            process=subprocess.Popen(['node',str(worker),str(manifest_path)],cwd=ROOT,stdout=subprocess.PIPE,stderr=error_log,text=True,encoding='utf-8',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            def timeout_renderer():
                if os.name=='nt':subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
                else:process.kill()
            deadline=threading.Timer(900,timeout_renderer);deadline.daemon=True;deadline.start()
            try:
                for line in process.stdout:
                    try:event=json.loads(line);progress(70+round(event['progress']*.27),'rendering',event['message'])
                    except (ValueError,KeyError):pass
                if process.wait()!=0:
                    detail=(out/'renderer-error.log').read_text(encoding='utf-8')[-1200:]
                    raise ValueError('Local video renderer failed: '+detail)
            finally:
                deadline.cancel()
                if process.poll() is None:
                    timeout_renderer()
                    process.wait(timeout=30)
        if temporary_frame_dir is not None:
            shutil.rmtree(temporary_frame_dir)
            temporary_frame_dir=None
        probe=ROOT/'node_modules'/'@ffprobe-installer'/'win32-x64'/'ffprobe.exe'
        check=subprocess.run([str(probe),'-v','error','-show_streams','-show_format','-of','json',str(out/'lesson.mp4')],capture_output=True,text=True,check=True,timeout=30)
        media=json.loads(check.stdout);(out/'probe.json').write_text(json.dumps(media,indent=2),encoding='utf-8')
        video=next((s for s in media['streams'] if s['codec_type']=='video'),{});audio=next((s for s in media['streams'] if s['codec_type']=='audio'),{})
        if (video.get('width'),video.get('height'),video.get('codec_name'),audio.get('codec_name'))!=(1280,720,'h264','aac'):raise ValueError('Export did not pass video/audio validation.')
        if abs(float(media['format']['duration'])-request.targetDuration)>.3:raise ValueError('Export duration does not match the requested lesson length.')
        plan['scenes']=[{k:v for k,v in s.items() if k not in ('audioPath','ltxBackgroundFrames')} for s in scenes];plan['duration']=float(media['format']['duration']);plan['targetDuration']=request.targetDuration
        payload.update(videoUrl=f'/api/lessons/{job_id}/video',captionsUrl=f'/api/lessons/{job_id}/captions',timingNote='Narration is fitted to the requested length without cutting words. Captions use proportional phrase timing.',model=MODEL,videoModel=library.video_model(request.model_dump()),videoEngine=request.videoEngine,speechTempo=tempo,schemaVersion='lesson-v6',request=request.model_dump())
        (out/'lesson.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
        timings[current_stage]=timings.get(current_stage,0)+time.perf_counter()-stage_started
        timings['total']=time.perf_counter()-started
        (out/'timings.json').write_text(json.dumps(timings,indent=2),encoding='utf-8')
        update(job_id,status='completed',stage='ready',progress=100,message='Your narrated lesson is ready',result=json.dumps(payload,ensure_ascii=False))
        with connection() as db:
            library.ensure_index(db);library.index_record(db,db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone(),OUTPUT)
    except BaseException as error:
        # Interruptions must not leave a running/completed lesson record.
        (out/'error.txt').write_text(str(error),encoding='utf-8');update(job_id,status='failed',stage='error',message=(str(error) or type(error).__name__)[:1800],result=None)
        if not isinstance(error,Exception):raise
    finally:
        if temporary_frame_dir is not None and temporary_frame_dir.exists():
            try:shutil.rmtree(temporary_frame_dir)
            except OSError as cleanup_error:
                (out/'cleanup-error.txt').write_text(str(cleanup_error),encoding='utf-8')
                previous=job(job_id)['message']
                update(job_id,status='failed',stage='cleanup_error',result=None,message=f'{previous}; Temporary frame cleanup failed: {cleanup_error}'[:1800])

@app.get('/api/health')
def health():
    status={'model':MODEL,'rendererReady':(ROOT/'renderer/dist/export.mjs').exists(),'ffmpegReady':Path(imageio_ffmpeg.get_ffmpeg_exe()).exists(),'defaultVideoEngine':'animated','durationPresets':[30,60,90],'offline':True,'hackathonMode':True,'speechModes':['local'],'localProcessing':['planning','narration','animation','video export'],'onlineSpeechSends':'disabled: local speech only','progressivePreview':True,'visualRenderer':'React SVG plus browser SVG preview','speechToText':{'ready':asr_ready(),'engine':'local-faster-whisper-tiny'}}
    try:info=model_info();status.update(ollamaReady=True,modelDigest=info['digest'])
    except Exception as e:status.update(ollamaReady=False,error=str(e))
    try:status['voices']=installed_voices()
    except Exception:status['voices']=[]
    
    try:
        with httpx.Client(trust_env=False,timeout=3) as client:status['compute']=client.get(OLLAMA+'/api/ps').json().get('models',[])
    except Exception:status['compute']=[]
    status['ready']=status['ollamaReady'] and status['rendererReady'] and status['ffmpegReady'] and bool(status['voices']);return status

@app.get('/api/lessons')
def saved_lessons():
    with connection() as db:rows=db.execute("SELECT id,request,result FROM jobs WHERE status='completed' ORDER BY created DESC LIMIT 30").fetchall()
    return [{'id':row['id'],'request':json.loads(row['request']),'result':json.loads(row['result'])} for row in rows if (OUTPUT/row['id']/'lesson.mp4').exists()]

@app.post('/api/lessons',status_code=202)
def create(request:LessonRequest):
    if not request.topic.strip():raise HTTPException(422,'Please enter a question.')
    if request.voice.startswith('online-'):raise HTTPException(422,'Hackathon mode requires local voices.')
    started=time.perf_counter();data=request.model_dump();digest=library.request_key(data)
    with connection() as db:
        # Serialize lookup + insertion, so simultaneous repeated requests share one job.
        db.execute('BEGIN IMMEDIATE');library.ensure_index(db)
        if request.reuseSaved:
            found=library.lookup(db,OUTPUT,data)
            if found:return {**found,'lookupMs':round((time.perf_counter()-started)*1000,2)}
            for row in db.execute("SELECT * FROM jobs WHERE status IN ('running','queued') ORDER BY created DESC").fetchall():
                if library.request_key(json.loads(row['request']))==digest:return {'id':row['id'],'status':row['status'],'cached':True,'match':'in_progress','lookupMs':round((time.perf_counter()-started)*1000,2)}
        try:voices=installed_voices()
        except Exception:raise HTTPException(503,'The speech service is unavailable.')
        if not any(v['language']==request.language and v.get('localAvailable',False) for v in voices):raise HTTPException(422,'This narration language is unavailable.')
        previous=db.execute("SELECT id FROM jobs WHERE cache_key=? AND status='failed' ORDER BY created DESC LIMIT 1",(digest,)).fetchone()
        ident=uuid.uuid4().hex;db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?)',(ident,digest,request.model_dump_json(),'queued','queued',0,'Waiting for the local engine',None,time.time()))
    executor.submit(run,ident,request,previous['id'] if previous else None)
    return {'id':ident,'status':'queued','cached':False,'lookupMs':round((time.perf_counter()-started)*1000,2)}

@app.get('/api/lessons/schema')
def lesson_schema():
    return {'schemaVersion':'lesson-v6','input':LessonRequest.model_json_schema(),'planner':LessonPlan.model_json_schema()}

@app.get('/api/lessons/{ident}/status')
def status(ident:str):return {k:v for k,v in job(ident).items() if k not in ('result','cache_key','request')}
@app.get('/api/lessons/{ident}/preview')
def preview(ident:str):
    record=job(ident);path=OUTPUT/ident/'preview.json'
    if not path.exists():raise HTTPException(404,'The visual lesson is still being planned.')
    try:data=json.loads(path.read_text(encoding='utf-8'))
    except (OSError,json.JSONDecodeError):raise HTTPException(503,'The progressive lesson is updating. Please retry.')
    data['status']=record['status']
    for scene in data.get('readyScenes',[]):scene['audioUrl']=f"/api/lessons/{ident}/preview/audio/{scene['index']}"
    return data
@app.get('/api/lessons/{ident}/preview/audio/{index}')
def preview_audio(ident:str,index:int):
    record=job(ident)
    if index<0:raise HTTPException(404,'Scene audio was not found.')
    path=OUTPUT/ident/f'scene-{index}.wav'
    if not path.is_file():raise HTTPException(404,'This scene narration is not ready yet.')
    if record['status']=='failed':raise HTTPException(409,'The lesson did not complete.')
    return FileResponse(path,media_type='audio/wav',filename=f'biryani-scene-{index+1}.wav',content_disposition_type='inline')
@app.get('/api/lessons/{ident}')
def result(ident:str):
    record=job(ident)
    if record['status']!='completed':raise HTTPException(409,record['message'])
    return json.loads(record['result'])
@app.get('/api/lessons/{ident}/scenes')
def scenes(ident:str):return (result(ident).get('lesson') or {}).get('scenes',[])
@app.get('/api/lessons/{ident}/quiz')
def quiz(ident:str):return (result(ident).get('lesson') or {}).get('quiz',[])
@app.get('/api/lessons/{ident}/video')
def video(ident:str):
    result(ident);path=OUTPUT/ident/'lesson.mp4'
    if not path.exists():raise HTTPException(404,'This conversation has no video.')
    return FileResponse(path,media_type='video/mp4',filename='biryani-lesson.mp4',content_disposition_type='inline')
@app.get('/api/lessons/{ident}/captions')
def captions(ident:str):
    result(ident);path=OUTPUT/ident/'captions.vtt'
    if not path.exists():raise HTTPException(404,'No captions for this conversation.')
    return FileResponse(path,media_type='text/vtt')

class TranscriptionRequest(BaseModel):
    audio: str = Field(min_length=40,max_length=16_000_000)
    language: str = Field(default='en',min_length=2,max_length=5)

@app.post('/api/transcribe')
def transcribe_question(request:TranscriptionRequest):
    if not asr_ready():raise HTTPException(503,'The local speech-to-text model is not installed.')
    try:
        encoded=request.audio.split(',',1)[-1]
        source=base64.b64decode(encoded,validate=True)
    except (ValueError,binascii.Error):raise HTTPException(422,'The recorded question was invalid.')
    if not 400<len(source)<=12_000_000:raise HTTPException(422,'Record a question under two minutes.')
    fd,path=tempfile.mkstemp(suffix='.webm',dir=RUNTIME);os.close(fd);audio_path=Path(path)
    try:
        audio_path.write_bytes(source)
        return {'text':transcribe_audio(audio_path,request.language),'engine':'local-faster-whisper-tiny'}
    except ValueError as error:raise HTTPException(422,str(error))
    except Exception as error:raise HTTPException(500,'Local speech-to-text failed: '+str(error)[:300])
    finally:
        audio_path.unlink(missing_ok=True)
class SpeechRequest(BaseModel):
    text:str=Field(min_length=1,max_length=900)
    language:str='en'
    speed:float=Field(default=1,ge=.75,le=1.3)
    voice:Literal['basic','female','male','online-female','online-male']='female'
    accent:Literal['indian','british','american']='indian'

@app.get('/api/voices')
def voice_list():return installed_voices()

@app.post('/api/speech')
def speak(request:SpeechRequest):
    try:path=synthesize(request.text,request.language,request.speed,request.voice,request.accent)
    except (ValueError,RuntimeError) as e:raise HTTPException(422,str(e))
    return {'audioUrl':'/audio/'+path.name,'voice':request.language}

@app.get('/audio/{filename}')
def audio_file(filename:str):
    if not re.fullmatch(r'[a-f0-9]{64}\.wav',filename):raise HTTPException(404)
    path=SPEECH_CACHE/filename
    if not path.exists():raise HTTPException(404)
    return FileResponse(path,media_type='audio/wav')

class RefinementRequest(BaseModel):
    narrations:list[str]=Field(min_length=3,max_length=6)
    speed:float=Field(default=1,ge=.75,le=1.3)
    voice:str=Field(default='female',pattern='^(basic|female|male|online-female|online-male)$')
    accent:Literal['indian','british','american']='indian'

@app.post('/api/lessons/{ident}/refine',status_code=202)
def refine(ident:str, edit:RefinementRequest):
    if edit.voice.startswith('online-'):raise HTTPException(422,'Hackathon mode requires local voices.')
    source=result(ident)
    plan=source.get('lesson')
    if not plan:raise HTTPException(422,'This conversation has no lesson.')
    if len(edit.narrations)!=len(plan['scenes']):raise HTTPException(422,'Keep one narration per scene.')
    request=LessonRequest.model_validate_json(job(ident)['request']).model_copy(update={'speechSpeed':edit.speed,'voice':edit.voice,'accent':edit.accent})
    plan.pop('duration',None);plan.pop('targetDuration',None)
    for scene,text in zip(plan['scenes'],edit.narrations):
        for name in ('audioDuration','start','duration','captions'):scene.pop(name,None)
        scene['narration']=text
    new_id=uuid.uuid4().hex
    try:prepared=normalize({'intent':'educational','message':'Audio refined; visuals preserved.','lesson':plan},request,new_id)
    except ValueError as e:raise HTTPException(422,str(e))
    with connection() as db:
        db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?)',(new_id,new_id,request.model_dump_json(),'queued','queued',0,'Refining narration',None,time.time()))
    executor.submit(run,new_id,request,prepared=prepared)
    return {'id':new_id,'status':'queued','cached':False}
