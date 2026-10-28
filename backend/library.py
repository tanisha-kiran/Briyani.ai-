"""Persistent local video lookup. No LLM or network work on a cache hit."""
import hashlib,json,re,unicodedata,math
from collections import Counter
from .quality import VERSION as QUALITY_VERSION

LTX_MODEL='Lightricks/LTX-Video ltxv-2b-0.9.8-distilled-fp8'
VIDEO_MODEL='Biryani local animated lessons v6'

def video_model(request):
    return LTX_MODEL if request.get('videoEngine','animated')=='ltx' else VIDEO_MODEL

def words(text):
    text=unicodedata.normalize('NFKC',text).casefold()
    return ''.join(c if unicodedata.category(c)[0] in 'LMN' or c=='_' else ' ' for c in text).split()

def signature(text):
    text=unicodedata.normalize('NFKC',text).casefold()
    # Preserve operators and numeric punctuation: range(-3) is not range(3).
    chars=[]
    for i,c in enumerate(text):
        if unicodedata.category(c)[0] in 'LMN' or c=='_':chars.append(c)
        elif c in '+-*/<>=%^()[]{}' or (c=='!' and text[i+1:i+2]=='=') or (c in '.,' and i>0 and text[i-1].isdigit() and text[i+1:i+2].isdigit()):chars.append(' '+c+' ')
        else:chars.append(' ')
    text=' '.join(''.join(chars).split())
    text=re.sub(r'^(?:please |can you |could you )+','',text)
    text=re.sub(r'^(?:explain|describe|tell me about|what is|what are)\s+','',text)
    if text.startswith('how does ') and text.endswith(' work'):text=text[9:-5]
    text=re.sub(r'\b(?:a|an|the)\b',' ',text)
    return ' '.join(text.split())

def settings(request):
    # Reuse only the same requested length, language, level, voice and engine.
    keys=('language','level','voice','speechSpeed','targetDuration')
    defaults={'language':'en','level':'beginner','voice':'basic','speechSpeed':1.0,'targetDuration':60}
    result={k:request.get(k,defaults[k]) for k in keys}
    result['videoModel']=video_model(request)
    if result['language']=='en':result['accent']=request.get('accent','british')
    return result

def request_key(request):
    return hashlib.sha256(json.dumps([signature(request['topic']),settings(request)],sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def ensure_index(db):
    db.execute('CREATE TABLE IF NOT EXISTS video_library(id TEXT PRIMARY KEY, signature TEXT NOT NULL, settings TEXT NOT NULL, title TEXT NOT NULL, document TEXT NOT NULL, request TEXT NOT NULL, created REAL NOT NULL)')
    db.execute('CREATE INDEX IF NOT EXISTS video_signature ON video_library(signature)')
    db.execute('CREATE INDEX IF NOT EXISTS job_cache_status ON jobs(cache_key,status)')

def index_record(db,row,output):
    try:
        if row['id'].startswith(('fallback-','demo-')):return
        payload=json.loads(row['result'] or '{}');lesson=payload.get('lesson');request=json.loads(row['request'])
        media=output/row['id']/'lesson.mp4'
        if payload.get('isFallback') or payload.get('videoModel')!=video_model(request) or payload.get('quality',{}).get('version')!=QUALITY_VERSION or not payload.get('quality',{}).get('passed'):return
        if request.get('voice','basic').startswith('online-'):return
        if row['status']!='completed' or not lesson or not media.is_file() or media.stat().st_size==0:return
        if 'not a generated answer' in payload.get('message','').casefold():return
        text=' '.join([request['topic'],lesson['title'],*(s['heading']+' '+s['narration'] for s in lesson['scenes'])])
        db.execute('INSERT OR REPLACE INTO video_library VALUES (?,?,?,?,?,?,?)',(row['id'],signature(request['topic']),json.dumps(settings(request),sort_keys=True),lesson['title'],text,row['request'],row['created']))
    except (ValueError,KeyError,TypeError,OSError):return

def rebuild(db,output):
    ensure_index(db)
    db.execute('DELETE FROM video_library')
    for row in db.execute("SELECT * FROM jobs WHERE status='completed'").fetchall():index_record(db,row,output)

STOP=set('a an the is are was were does do how what why when where which explain describe tell me about please can could you to of for in on and it its work works'.split())
ALIASES={'loops':'loop','swinging':'swing','swings':'swing','pendulums':'pendulum','browning':'brown','apples':'apple','plants':'plant','rises':'rise','rising':'rise','falls':'fall','falling':'fall','slowing':'slow','slows':'slow','stopping':'stop','stops':'stop'}
def terms(text):return [ALIASES.get(t,t) for t in words(text) if t not in STOP]

def lookup(db,output,request):
    q=signature(request['topic']);desired=json.dumps(settings(request),sort_keys=True)
    rows=db.execute("SELECT v.*,j.result FROM video_library v JOIN jobs j ON j.id=v.id WHERE j.status='completed' ORDER BY v.created DESC").fetchall()
    valid=[]
    for row in rows:
        media=output/row['id']/'lesson.mp4'
        if not media.is_file() or media.stat().st_size==0:
            db.execute('DELETE FROM video_library WHERE id=?',(row['id'],));continue
        source=json.loads(row['request'])
        if json.loads(row['result'] or '{}').get('videoModel')!=video_model(request):continue
        if source.get('language')!=request.get('language') or source.get('level','beginner')!=request.get('level','beginner'):continue
        if row['signature']==q and row['settings']==desired:
            return {'id':row['id'],'status':'completed','cached':True,'match':'equivalent','result':json.loads(row['result']),'savedRequest':source}
        valid.append((row,source))
    query=set(terms(request['topic']))
    if not query:return None
    documents=[set(terms(row['document'])) for row,_ in valid]
    weights={t:1+math.log((len(documents)+1)/(1+sum(t in d for d in documents))) for t in query}
    matches=[]
    for (row,source),document in zip(valid,documents):
        overlap=query&document
        coverage=sum(weights[t] for t in overlap)/sum(weights.values())
        title=set(terms(row['title']+' '+source['topic']));anchor=query&title
        # Related results are suggestions, never silently treated as equivalent.
        distinctive_anchor=any(weights[t]>=1.6 for t in anchor)
        if (coverage>=.48 and anchor) or (coverage>=.12 and distinctive_anchor) or (coverage>=.2 and (len(anchor)>=2 or any(len(t)>=5 for t in anchor))) or row['signature']==q:
            score=coverage*.7+len(query&title)/max(1,len(query))*.3
            matches.append({'id':row['id'],'title':row['title'],'score':round(score,3),'result':json.loads(row['result']),'savedRequest':source})
    matches.sort(key=lambda item:item['score'],reverse=True)
    return {'status':'related','cached':False,'matches':matches[:3]} if matches else None
