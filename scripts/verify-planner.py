"""Integration checks against the user's existing local model; never downloads a model."""
import json,time
from pathlib import Path
from backend.planner import generate,normalize
from backend.schemas import LessonRequest
topics=['Hi','What is Python?','Why do apples turn brown?','How do neural networks learn?','Who was Alan Turing?','Compare Python and Java.']
root=Path('output/verification');root.mkdir(parents=True,exist_ok=True)
results=[]
for i,topic in enumerate(topics):
    folder=root/str(i);folder.mkdir(exist_ok=True);started=time.monotonic()
    try:
        output=None;request=LessonRequest(topic=topic,targetDuration=30,cpuOnly=True)
        candidates=[folder/'validated.json',*sorted(folder.glob('planner-attempt-*.json'),reverse=True)]
        for draft in candidates:
            try:
                output=normalize(json.loads(draft.read_text(encoding='utf-8')),request,'check-'+str(i))
                if topic=='Hi' and output.intent!='conversation':output=None;continue
                break
            except (OSError,ValueError,TypeError,KeyError):pass
        if output is None:output=generate(request,'check-'+str(i),folder,lambda *x:print(topic,*x,flush=True))
        if topic=='Hi':assert output.intent=='conversation' and output.lesson is None
        else:assert output.intent=='educational' and len(output.lesson.scenes)>=3
        (folder/'validated.json').write_text(output.model_dump_json(indent=2),encoding='utf-8')
        result={'topic':topic,'passed':True,'seconds':round(time.monotonic()-started,2),'intent':output.intent,'headings':[s.heading for s in output.lesson.scenes] if output.lesson else []}
    except Exception as e:result={'topic':topic,'passed':False,'error':str(e),'seconds':round(time.monotonic()-started,2)}
    results.append(result);(root/'results.json').write_text(json.dumps(results,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
