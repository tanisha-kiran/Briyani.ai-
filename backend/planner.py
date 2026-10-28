import json, re, os
from pathlib import Path
import httpx
from .schemas import IntentResponse, LessonRequest, LessonPlan
from .quality import audit,code_trace
from .router import route, REGISTRY, rule_scores

OLLAMA=os.environ.get('BIRYANI_OLLAMA','http://127.0.0.1:11434')
MODEL=os.environ.get('BIRYANI_MODEL','qwen3.5:4b')
ALIASES={'diagram':'labeled_diagram','flow':'flow_diagram','process_flow':'flow_diagram','graph':'graph_animation','code':'code_walkthrough','title':'title_card'}

def _post_chat(client,payload):
    endpoint=OLLAMA+'/api/chat'
    response=client.post(endpoint,json=payload)
    if response.status_code>=500:
        retry=dict(payload)
        options=dict(payload.get('options',{}))
        context=options.get('num_ctx',4096)
        options['num_ctx']=max(2048,context//2) if isinstance(context,int) and not isinstance(context,bool) else 2048
        retry['options']=options
        response=client.post(endpoint,json=retry)
    if response.is_error:
        detail=response.text.strip()[:500]
        message=f'Local Ollama chat failed with HTTP {response.status_code}'
        if detail:message+=f': {detail}'
        raise httpx.HTTPStatusError(message,request=response.request,response=response)
    return response

def output_schema(request=None):
    # Full renderer schema for validation tools. The local planner below uses
    # a smaller JSON contract and adapts it through trusted Python code.
    schema=LessonPlan.model_json_schema();count=3 if not request or request.targetDuration<=60 else 4 if request.targetDuration<=70 else 5
    schema['properties']['scenes'].update(minItems=count,maxItems=count)
    schema['properties']['quiz'].update(minItems=1,maxItems=1 if count==3 else 2)
    schema['properties']['followUps'].update(minItems=2,maxItems=2)
    if request:
        schema['properties']['level']={'type':'string','enum':[request.level]}
        schema['properties']['language']={'type':'string','enum':[request.language]}
    schema['$defs']['Scene']['properties']['narration'].pop('pattern',None)
    schema['$defs']['Scene']['properties']['narration']['maxLength']=320 if count==3 else 400
    visual=schema['$defs']['VisualConfiguration']
    visual['required']=['leftTitle','rightTitle']
    # Each template has its own small visual shape. A code scene cannot omit code,
    # and a diagram cannot be padded with irrelevant code or fabricated chart data.
    import copy
    base=copy.deepcopy(schema['$defs']['Scene'])
    fields={'title_card':['keywords'],'labeled_diagram':['nodes','edges'],'flow_diagram':['nodes','edges'],
            'code_walkthrough':['code','highlightLines'],'graph_animation':['points','xLabel','yLabel'],
            'timeline':['items'],'comparison':['leftTitle','rightTitle','rows'],'animated_illustration':['nodes','motion','shape']}
    variants=[]
    for kind,names in fields.items():
        variant=copy.deepcopy(base)
        variant['properties']['type']={'type':'string','enum':[kind]}
        properties={name:copy.deepcopy(visual['properties'][name]) for name in names}
        for name in ('nodes','points','items','keywords'):
            if name in properties:properties[name]['minItems']=2
        if 'code' in properties:properties['code']['minLength']=1
        if 'rows' in properties:properties['rows']['minItems']=1
        variant['properties']['visual']={'type':'object','properties':properties,'required':names,'additionalProperties':False}
        variants.append(variant)
    schema['$defs']['Scene']={'anyOf':variants}
    for name in ['rows','keywords']:visual['properties'][name]['maxItems']=3 if count==3 else 4
    schema['$defs']['QuizQuestion']['properties'].pop('misconceptionTag',None)
    def compact(value,properties=False):
        if isinstance(value,dict):return {k:compact(v,k=='properties') for k,v in value.items() if properties or k not in ('title','default')}
        if isinstance(value,list):return [compact(v) for v in value]
        return value
    schema=compact(schema)
    return schema

def normalize(raw: dict, request: LessonRequest, lesson_id: str) -> IntentResponse:
    if not isinstance(raw,dict): raise ValueError('Planner must return a JSON object.')
    data=dict(raw)
    if 'intent' not in data: data={'intent':'educational','message':'','lesson':data}
    data['intent']={'greeting':'conversation','chat':'conversation','lesson':'educational'}.get(data['intent'],data['intent'])
    data.setdefault('message','')
    if data['intent']!='educational': data['lesson']=None;return IntentResponse.model_validate(data)
    plan=dict(data.get('lesson') or {});plan.setdefault('level',request.level);plan.setdefault('language',request.language)
    plan['objectives']=[{'text':v} if isinstance(v,str) else v for v in plan.get('objectives',plan.pop('learning_objectives',[]))]
    plan['followUps']=plan.get('followUps',plan.pop('follow_up_questions',[]))
    scenes=[]
    for i,original in enumerate(plan.get('scenes',[])):
        s=dict(original);s.setdefault('id',f'scene_{i+1}');s['type']=ALIASES.get(s.get('type'),s.get('type'));s['heading']=s.get('heading',s.pop('title',''))
        # Never convert stage directions into narration: missing narration triggers correction.
        if 'narration_text' in s:s['narration']=s.pop('narration_text')
        narration=s.get('narration','').strip()
        if narration and narration[-1] not in '.!?।':
            ends=list(re.finditer(r'[.!?।](?=\s|$)',narration))
            if ends and ends[-1].end()>=15:s['narration']=narration[:ends[-1].end()]
        v=dict(s.get('visual') or {})
        if 'code' in s:v['code']=s.pop('code')
        if 'highlight_lines' in s:v['highlightLines']=s.pop('highlight_lines')
        if 'highlight_lines' in v:v['highlightLines']=v.pop('highlight_lines')
        highlights=v.get('highlightLines',[]);line_count=len(v.get('code','').splitlines())
        # Highlight indices are presentation hints, not lesson facts. Drop invalid
        # hints; the renderer safely walks actual code lines when the list is empty.
        if isinstance(highlights,list):v['highlightLines']=list(dict.fromkeys(n for n in highlights if isinstance(n,int) and 1<=n<=line_count))
        v['nodes']=[{'id':f'n{n+1}','label':node} if isinstance(node,str) else node for n,node in enumerate(v.get('nodes',[]))]
        # In self-labeled diagrams (e.g. year nodes), an edge endpoint already
        # supplies its own visible label. Restore a bounded omitted endpoint;
        # never guess a label for an opaque ID in a normally labeled diagram.
        nodes=v['nodes']
        if nodes and all(n.get('id')==n.get('label') for n in nodes):
            known={n['id'] for n in nodes}
            missing=list(dict.fromkeys(ref for edge in v.get('edges',[]) for ref in [edge.get('source'),edge.get('target')] if ref not in known))
            if len(nodes)+len(missing)<=6 and all(isinstance(ref,str) and 0<len(ref)<=32 for ref in missing):nodes.extend({'id':ref,'label':ref} for ref in missing)
        if s['type']=='flow_diagram' and not v.get('edges') and len(v['nodes'])>=2:
            v['edges']=[{'source':a['id'],'target':b['id'],'label':''} for a,b in zip(v['nodes'],v['nodes'][1:])]
        if s['type']=='code_walkthrough':
            v['trace']=code_trace(v.get('code',''))
            word={'hi':'चक्र','ta':'சுற்று','kn':'ಸುತ್ತು','te':'పునరావృతం','bn':'পুনরাবৃত্তি','mr':'पुनरावृत्ती','ml':'ആവർത്തനം','gu':'પુનરાવર્તન','pa':'ਦੁਹਰਾਓ','or':'ପୁନରାବୃତ୍ତି'}.get(request.language,'Iteration')
            for j,step in enumerate(v['trace']):step['label']=f'{word} {j+1}'
        s['visual']=v;scenes.append(s)
    plan['scenes']=scenes
    quiz=[]
    for i,original in enumerate(plan.get('quiz',plan.pop('mcqs',[]))):
        q=dict(original);q.setdefault('id',f'q{i+1}');q['lessonId']=lesson_id;q.setdefault('language',request.language)
        if 'relatedSceneId' in q:q['sceneId']=q.pop('relatedSceneId')
        q['options']=[{'id':f'option_{n}','text':o} if isinstance(o,str) else o for n,o in enumerate(q.get('options',[]))]
        answer=q.pop('answer',q.pop('correctAnswerId',None))
        if 'correctOptionId' not in q and answer is not None:
            match=next((o for o in q['options'] if o['id']==answer or o['text']==answer),None)
            if match:q['correctOptionId']=match['id']
        ids={scene['id'] for scene in scenes}
        if q.get('sceneId') not in ids:
            # Some responses put a template type in sceneId. Resolve only an
            # unambiguous type, or a unique scene with explicit question phrases.
            candidates=[scene for scene in scenes if scene['type']==q.get('sceneId')]
            if len(candidates)==1:q['sceneId']=candidates[0]['id']
            elif candidates:
                tokens=re.findall(r'\w+',q.get('question','').casefold())
                phrases={a+' '+b for a,b in zip(tokens,tokens[1:]) if len(a)>3 and len(b)>3 and a not in {'which','what','does','language'} and b not in {'which','what','does','language'}}
                scored=[(sum(phrase in (scene['narration']+' '+json.dumps(scene['visual'],ensure_ascii=False)).casefold() for phrase in phrases),scene['id']) for scene in candidates]
                best=max(score for score,_ in scored)
                matches=[ident for score,ident in scored if score==best]
                if best>=2 and len(matches)==1:q['sceneId']=matches[0]
        quiz.append(q)
    plan['quiz']=quiz;data['lesson']=plan
    result=IntentResponse.model_validate(data)
    if result.lesson.language!=request.language or any(q.language!=request.language for q in result.lesson.quiz):raise ValueError('Model changed requested language.')
    if result.lesson.level!=request.level:raise ValueError('Model changed requested learner level.')
    return result

def _translation_items(plan):
    data=plan.model_dump()
    items=[]
    def add(path,value):
        if isinstance(value,str) and value.strip():items.append((path,value))
    add('title',data['title'])
    for i,objective in enumerate(data['objectives']):add(f'objectives.{i}.text',objective['text'])
    for i,scene in enumerate(data['scenes']):
        root=f'scenes.{i}'
        add(f'{root}.heading',scene['heading'])
        add(f'{root}.narration',scene['narration'])
        visual=scene['visual']
        for field in ('leftTitle','rightTitle','xLabel','yLabel'):add(f'{root}.visual.{field}',visual.get(field,''))
        for field in ('keywords',):
            for j,value in enumerate(visual.get(field,[])):add(f'{root}.visual.{field}.{j}',value)
        for field in ('nodes','edges','points','items','rows','trace'):
            for j,item in enumerate(visual.get(field,[])):
                for key in ('label','date','text','left','right'):
                    if key in item:add(f'{root}.visual.{field}.{j}.{key}',item[key])
    for i,question in enumerate(data['quiz']):
        root=f'quiz.{i}'
        for field in ('question','explanation'):add(f'{root}.{field}',question[field])
        for j,option in enumerate(question['options']):add(f'{root}.options.{j}.text',option['text'])
    for i,value in enumerate(data['followUps']):add(f'followUps.{i}',value)
    return data,items

def _set_translation(data,path,value):
    parts=path.split('.')
    target=data
    for part in parts[:-1]:target=target[int(part)] if isinstance(target,list) else target[part]
    key=parts[-1]
    if isinstance(target,list):target[int(key)]=value
    else:target[key]=value

def _translation_batches(items):
    batches=[];batch=[];characters=0
    for item in items:
        size=len(item[1])
        if batch and (len(batch)>=5 or characters+size>900):
            batches.append(batch);batch=[];characters=0
        batch.append(item);characters+=size
    if batch:batches.append(batch)
    return batches

def _translation_max_length(path):
    parts=path.split('.')
    if path=='title':return 120
    if parts[0]=='objectives':return 240
    if parts[0]=='followUps':return 240
    if parts[0]=='quiz':
        return 260 if parts[2]=='question' else 500 if parts[2]=='explanation' else 180
    if parts[0]=='scenes':
        if parts[2]=='heading':return 100
        if parts[2]=='narration':return 600
        field=parts[3]
        if field in ('leftTitle','rightTitle','xLabel','yLabel'):return 45
        if field=='keywords':return 80
        item_field=parts[5]
        limits={
            ('nodes','label'):90,('edges','label'):60,('points','label'):40,
            ('items','date'):30,('items','text'):110,
            ('rows','label'):45,('rows','left'):110,('rows','right'):110,
            ('trace','label'):50,('trace','value'):80,('trace','output'):200,
        }
        return limits[(field,item_field)]
    raise ValueError(f'No translation length limit is defined for {path}.')

def _translate_lesson(plan,request,client,progress,output,correction=None,revision=1):
    names={'ta':'Tamil','te':'Telugu','kn':'Kannada','ml':'Malayalam'}
    scripts={'ta':'Tamil script','te':'Telugu script','kn':'Kannada script','ml':'Malayalam script'}
    terms={
        'ta':'Water-cycle glossary: ஆவியாதல்=evaporation, நீராவி=water vapor, ஒடுக்கம்=condensation, மேகம்=cloud, நீர்த்துளி=droplet, மழை=rain, புவியீர்ப்பு=gravity.',
        'te':'Water-cycle glossary: ఆవిరైపోవడం=evaporation, నీటి ఆవిరి=water vapor, ఘనీభవనం=condensation, మేఘం=cloud, నీటి బిందువు=droplet, వర్షం=rain, గురుత్వాకర్షణ=gravity.',
        'kn':'Water-cycle glossary: ಆವಿಯಾಗುವಿಕೆ=evaporation, ನೀರಾವಿ=water vapor, ಘನೀಕರಣ=condensation, ಮೋಡ=cloud, ನೀರಿನ ಹನಿ=droplet, ಮಳೆ=rain, ಗುರುತ್ವಾಕರ್ಷಣೆ=gravity.',
        'ml':'Water-cycle glossary: ബാഷ്പീകരണം=evaporation, ജലബാഷ്പം=water vapor, സംഘനനം=condensation, മേഘം=cloud, ജലത്തുള്ളി=droplet, മഴ=rain, ഗുരുത്വാകർഷണം=gravity.',
    }
    data,items=_translation_items(plan)
    batches=_translation_batches(items)
    language=names[request.language]
    for index,batch in enumerate(batches):
        properties={key:{'type':'string','minLength':1,'maxLength':_translation_max_length(key)} for key,_ in batch}
        schema={'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}
        source={key:value for key,value in batch}
        messages=[
            {'role':'system','content':f'You are an expert {language} educational translator. Translate source text faithfully into natural, clear {language} in {scripts[request.language]}. Return only the required JSON object. Preserve every fact, number, name, relationship, and uncertainty. Do not summarize, add examples, explain, omit details, or invent content. Avoid English sentences, romanized {language}, and mixed English/native-script word endings. Keep code identifiers and mathematical expressions exactly as written. Keep diagram labels and arrow relationships concise phrases, not sentences, within the field character limits. Make the result suitable for spoken narration and captions.'},
            {'role':'user','content':f'Translate each value independently, preserving its meaning and all details. {terms[request.language]} When translating a water-cycle lesson: Scene 1 must say solar energy causes liquid water to evaporate into water vapor and that this is not boiling; Scene 2 must say condensation forms tiny liquid droplets and clouds; Scene 3 must say droplets fall as rain because of gravity. Use the glossary terms in the narration, not only in diagram labels. Keep every key exactly unchanged. {f"Correct these validation issues from the previous translation: {correction}" if correction else ""} Source JSON: {json.dumps(source,ensure_ascii=False)}'},
        ]
        last_error=''
        for attempt in range(2):
            progress(13+round(7*((revision-1)*len(batches)+index)/max(1,2*len(batches)-1)),'translating',f'Translating into {language} ({index+1}/{len(batches)}, revision {revision}/2)')
            response=_post_chat(client,{
                'model':MODEL,'messages':messages,'stream':False,'think':False,'format':schema,
                'options':{'temperature':.1,'num_ctx':4096 if request.cpuOnly else 8192,'num_predict':800,**({'num_gpu':0,'num_thread':4} if request.cpuOnly else {})},
                'keep_alive':'30m',
            })
            content=response.json()['message']['content']
            (output/f'translation-revision-{revision}-batch-{index+1}-attempt-{attempt+1}.json').write_text(content,encoding='utf-8')
            try:
                translated=json.loads(content)
                expected={key for key,_ in batch}
                if not isinstance(translated,dict) or set(translated)!=expected:
                    raise ValueError('Translation must return exactly the requested keys.')
                for key,value in translated.items():
                    if not isinstance(value,str) or not value.strip():raise ValueError(f'Translation for {key} is empty.')
                    if len(value)>_translation_max_length(key):raise ValueError(f'Translation for {key} exceeds {_translation_max_length(key)} characters.')
                    _set_translation(data,key,value.strip())
                break
            except (ValueError,TypeError) as error:
                last_error=str(error)[:500]
                messages.extend([
                    {'role':'assistant','content':content},
                    {'role':'user','content':'Correct the translation JSON. Return every required key exactly once, with a non-empty translated string for each. Do not add or remove keys. '+last_error},
                ])
        else:
            raise ValueError(f'{language} translation failed validation: {last_error}')
    data['language']=request.language
    for question in data['quiz']:question['language']=request.language
    return LessonPlan.model_validate(data)

def _review_lesson(source_plan,translated_plan,request,client,progress,output,revision):
    names={'ta':'Tamil','te':'Telugu','kn':'Kannada','ml':'Malayalam'}
    _,source_items=_translation_items(source_plan)
    _,translated_items=_translation_items(translated_plan)
    if [key for key,_ in source_items]!=[key for key,_ in translated_items]:
        raise ValueError('Translation review could not align the source and translated lesson fields.')
    batches=_translation_batches(source_items)
    translated_values=dict(translated_items)
    issues=[]
    schema={
        'type':'object',
        'properties':{
            'passed':{'type':'boolean'},
            'issues':{'type':'array','items':{'type':'string','maxLength':160},'maxItems':4},
        },
        'required':['passed','issues'],'additionalProperties':False,
    }
    for index,batch in enumerate(batches):
        pairs=[{'field':key,'english':source,'translation':translated_values[key]} for key,source in batch]
        language=names[request.language]
        prompt=f'Review these English-to-{language} educational translations. For each pair, verify the target text is fluent, grammatical, in natural {language}, in the correct script, and preserves every fact, relationship, qualifier, and negation without adding or omitting information. Check that the translation actually says what its English source says; similar-looking words are not enough. For science, reject changed mechanisms or concepts. If uncertain, fail. Return passed=true only if every pair is correct and natural. Otherwise passed=false and give at most four short issues (each under 120 characters), prefixed by field key. Pairs: {json.dumps(pairs,ensure_ascii=False)}'
        progress(20,'reviewing_translation',f'Checking {language} translation ({index+1}/{len(batches)}, revision {revision}/2)')
        response=_post_chat(client,{
            'model':MODEL,'messages':[{'role':'system','content':'Act as a strict bilingual language editor, not a helpful paraphraser. Identify semantic changes, omissions, additions, unnatural phrasing, and mixed-language errors.'},{'role':'user','content':prompt}],
            'stream':False,'think':False,'format':schema,
            'options':{'temperature':0,'num_ctx':4096 if request.cpuOnly else 8192,'num_predict':700,**({'num_gpu':0,'num_thread':4} if request.cpuOnly else {})},
            'keep_alive':'30m',
        })
        content=response.json()['message']['content']
        (output/f'translation-review-revision-{revision}-batch-{index+1}.json').write_text(content,encoding='utf-8')
        try:review=json.loads(content)
        except json.JSONDecodeError as error:raise ValueError(f'{language} translation review returned invalid JSON.') from error
        if not isinstance(review,dict) or not isinstance(review.get('passed'),bool) or not isinstance(review.get('issues'),list):
            raise ValueError(f'{language} translation review returned an invalid result.')
        if review['passed'] and review['issues']:raise ValueError(f'{language} translation review gave a contradictory result.')
        if not review['passed']:
            issues.extend(str(issue)[:240] for issue in review['issues'] if isinstance(issue,str) and issue.strip())
            if not review['issues']:issues.append(f'{language} reviewer could not verify batch {index+1}.')
    if issues:raise ValueError(f'{names[request.language]} translation review failed: '+'; '.join(issues[:10]))
    return {'version':'local-bilingual-review-v1','passed':True,'batches':len(batches)}

def _visual_strategy(topic:str, programming:bool) -> tuple[str,str]:
    """Choose relationship visuals only where the lesson meaning needs them."""
    text=topic.casefold()
    if re.search(r'\b(types?|kinds?|categories|classification|classified|classes|taxonomy|based on)\b',text): return 'flow_diagram','branch'
    if re.search(r'\b(cycle|loop|repeats?|recurring|circular)\b',text) and not programming: return 'flow_diagram','cycle'
    if re.search(r'\b(parts?|components?|fundamental concepts?|fields|areas|branches|systems?)\b',text): return 'flow_diagram','hub'
    if programming or re.search(r'\b(how (?:does|do)|process|stages?|steps?|mechanism|transform)\b',text): return 'flow_diagram','linear'
    return 'labeled_diagram','linear'
def _diagram_visual(item,labels):
    layout=item.get('layout','linear')
    nodes=[{'id':f'n{index+1}','label':label} for index,label in enumerate(labels)]
    raw_links=item.get('links',[])
    links=raw_links if isinstance(raw_links,list) else []
    links=[
        edge for edge in links
        if isinstance(edge,dict)
        and type(edge.get('source')) is int
        and type(edge.get('target')) is int
        and 0<=edge['source']<len(nodes)
        and 0<=edge['target']<len(nodes)
        and edge['source']!=edge['target']
        and isinstance(edge.get('label'),str)
        and edge['label'].strip()
    ]
    if not links:
        pairs=[(0,index) for index in range(1,len(nodes))] if layout in ('branch','hub') else [(index,index+1) for index in range(len(nodes)-1)]
        if layout=='cycle' and len(nodes)>=3:pairs.append((len(nodes)-1,0))
        links=[{'source':source,'target':target,'label':'relates to'} for source,target in pairs]
    return {
        'nodes':nodes,
        'layout':layout,
        'edges':[{'source':nodes[edge['source']]['id'],'target':nodes[edge['target']]['id'],'label':edge['label'].strip()} for edge in links],
    }

def generate(request: LessonRequest, lesson_id: str, output: Path, progress, spoken_word_budget=None) -> IntentResponse:
    # Keep the local model focused on teaching. Adapt compact data to the richer
    # renderer schema in trusted code; never execute generated code.
    if re.fullmatch(r'(hi|hello|hey|thanks|thank you)[!. ]*',request.topic.strip(),re.I):
        return IntentResponse(intent='conversation',message='Hello! What would you like to understand?',lesson=None)
    # Native-script planning is one local Qwen pass for normal lessons. The old
    # translation-and-review chain is retained only for deliberate audit runs; it
    # made a short Telugu lesson wait through ten separate model requests.
    full_translation_review=os.environ.get('BIRYANI_FULL_TRANSLATION_REVIEW')=='1'
    planning_request=request.model_copy(update={'language':'en'}) if full_translation_review and request.language in ('ta','te','kn','ml') else request
    if full_translation_review and request.language in ('ta','te','kn','ml'):
        progress(5,'planning','Planning an English source for explicit translation audit')
    count=3 if request.targetDuration<=60 else 4 if request.targetDuration<=70 else 5
    references=[]
    topic=request.topic.casefold()
    programming=any(t in topic for t in ('python','programming','for loop','while loop','range('))
    if 'loop' in topic or 'range(' in topic:
        references.append('Verified Python facts: range(3) yields 0, 1, 2, never 1, 2, 3. The upper limit is excluded. for i in range(3): followed by an indented print(i) prints 0, then 1, then 2 on separate lines. A for loop visits each item in a sequence. Do not claim that it starts at one.')
    if 'water cycle' in topic or 'evaporation' in topic:
        references.append('Verified water-cycle facts: solar energy enables liquid water at the surface to evaporate into water vapor, which is water in its gas state, NOT air. Oceans do NOT boil during evaporation. Evaporation occurs below boiling temperature. Moist air rises and cools; water vapor condenses into tiny liquid droplets (or ice crystals) that form clouds. Clouds are NOT invisible water vapor. Droplets grow by joining; sufficiently large drops fall as rain under gravity. Runoff and infiltration return water to rivers, ground and oceans. Everyday example: a wet cloth dries without boiling; water droplets on the OUTSIDE of a cold glass come from water vapor in surrounding air, not water leaking through glass. Translate evaporation correctly into the requested language; never replace it with boiling.')
    if 'apple' in topic and ('brown' in topic or 'oxid' in topic):
        references.append('Verified food-science facts: cutting damages cells and brings phenolic compounds and the enzyme polyphenol oxidase into contact with oxygen. The enzyme catalyses oxidation to quinones, which react to form brown pigments. Lemon juice slows browning: acidity reduces enzyme activity, and ascorbic acid reduces quinones back to phenolic compounds. It delays browning; it does not permanently stop it. Do not say ascorbic acid inhibits the enzyme or that oxygen is an enzyme activator; oxygen is a reactant. Browning alone is not proof of spoilage.')
    language={'en':'English','hi':'Hindi in Devanagari script','ta':'Tamil in Tamil script','te':'Telugu in Telugu script','kn':'Kannada in Kannada script','ml':'Malayalam in Malayalam script','mr':'Marathi in Devanagari script','bn':'Bengali in Bengali script','gu':'Gujarati in Gujarati script','pa':'Punjabi in Gurmukhi script','or':'Odia in Odia script'}[planning_request.language]
    if 'water cycle' in topic or 'evaporation' in topic:
        terminology={'hi':'Use जलवाष्प (water vapor), वाष्पीकरण (evaporation), संघनन (condensation), वर्षा (rainfall).','ta':'Use நீராவி (water vapor), ஆவியாதல் (evaporation), ஒடுக்கம் (condensation), மழை (rainfall).','te':'Use నీటి ఆవిరి (water vapor), ఆవిరి కావడం (evaporation), ఘనీభవనం (condensation), వర్షం (rainfall).','bn':'Use জলীয় বাষ্প (water vapor), বাষ্পীভবন (evaporation), ঘনীভবন (condensation), বৃষ্টি (rainfall).','mr':'Use पाण्याची वाफ (water vapor), बाष्पीभवन (evaporation), संघनन (condensation), पाऊस (rainfall).'}
        references.append(terminology.get(planning_request.language,''))
    # Keep the per-scene instruction consistent with the total cap. The old
    # numbers forced a correction pass for a 30-second, three-scene lesson.
    words=max(18,round(request.targetDuration*1.75/count))
    word_budget=max(round(request.targetDuration*1.9),count*words)
    if spoken_word_budget is not None:
        word_budget=min(220,round(request.targetDuration*(2.65 if planning_request.language=='en' else 3.0)),spoken_word_budget)
        words=max(8,round(word_budget/count))
    if 'pendulum' in topic:references.append('A pendulum swings about a fixed pivot. Gravity has a component toward its lowest position. At each turning point its speed is momentarily zero and gravitational potential energy is greatest. At the bottom its speed and kinetic energy are greatest. Gravity always acts downward. Inertia carries the bob upward on the other side while gravity slows it. Kinetic energy changes into gravitational potential energy as the bob rises, and back into kinetic energy as it falls. Even an ideal frictionless pendulum is momentarily still at each turning point. The pivot is the joint where the rod or string turns; friction occurs in that support or bearing. The hanging bob does not rub against the pivot. Air resistance on the bob and friction at the pivot transfer mechanical energy to the surroundings, reducing successive heights.')
    prompt=f"""Teach {request.topic} to a {request.level} student in {language}. Write every non-code field naturally in the requested language and its native script, including every narration sentence, heading, label and followUp. Do not mix in English sentences or romanized regional-language text. Never join English suffixes to native-script words; use complete natural words in the chosen language. Keep displayed Python code unchanged.
Write exactly {count} scenes with {words} to {words+5} words per scene; each scene must contain two or three complete teaching sentences and approximately {word_budget} spoken words TOTAL. A 30-second lesson gives the core mechanism, one worked example and the result. A 60-second lesson explains the mechanism and example in more depth, including why the steps work and a common mistake. A 90-second lesson adds a second application or comparison and a misconception check. Each extra scene must add new information. Use the learner level to choose depth and vocabulary. No greetings, filler, promises about the next scene, or repeated summaries. Start directly, explain a concrete mechanism and result, avoid repetition. Put the actual spoken explanation in narration. Use plain specific headings, such as Range stops before the limit, not abstract headings such as Output Verification Result. Never use Scene numbers. Labels must be DISTINCT concrete concepts or values explained by that scene. Never copy the heading into a label. Never repeat the same label. At least one label must be a short word or phrase copied EXACTLY from its narration. Only code scenes contain the code field. Code is display-only Python.
Each narration must meet its per-scene word minimum; do not omit a worked example or the result to make the answer shorter. Labels must be natural-language phrases, never snake_case or joined by underscores.
For a programming question, at least one scene MUST be code_walkthrough with complete, short code. Explain each line, variable changes, and the resulting output. Never use a physical animation for programming; use code_walkthrough for a second example if useful. Only the first scene is title_card. Other scenes explain specific details. For other scenes choose flow_diagram, code_walkthrough, or animated_illustration.
Every flow_diagram needs links, each an object with source and target label indices (zero based) and a brief relationship label, such as "supplies a value". Use flow_diagram ONLY when the explanation has a real direction, hierarchy, cycle, or relationship to trace. Use labeled_diagram for a set of facts that does not need arrows. Diagram layout: linear for steps, cycle for repeating processes, branch for classifications or alternatives, hub for components around a central idea. Do not use a flow diagram as decoration. Only animated_illustration scenes contain motion, and it must directly explain the spoken facts. Use pendulum for swinging about a pivot, orbit for orbital motion, collision for impact, diffusion for spreading particles, wave for oscillations, transfer for an explicitly described transfer. Never use orbital motion for a swinging pendulum. Use at most one animated illustration.
Reference facts: {' '.join(references)}
Return the complete required JSON. Do not omit narration or followUp. Never invent measurements or dates."""
    string={'type':'string'}
    fields={'heading':{'type':'string','minLength':2,'maxLength':100},'type':{'type':'string','enum':['title_card','flow_diagram','code_walkthrough'] if programming else ['title_card','flow_diagram','animated_illustration']},'narration':{'type':'string','minLength':max(40,words*5),'maxLength':600},'labels':{'type':'array','items':{'type':'string','minLength':2,'maxLength':35},'minItems':2,'maxItems':6,'uniqueItems':True},'code':{'type':'string','maxLength':900},'layout':{'type':'string','enum':['linear','cycle','branch','hub']},'motion':{'type':'string','enum':['none','pendulum','orbit','collision','diffusion','wave','transfer']}}
    fields['links']={'type':'array','maxItems':8,'items':{'type':'object','properties':{'source':{'type':'integer','minimum':0,'maximum':5},'target':{'type':'integer','minimum':0,'maximum':5},'label':{'type':'string','minLength':2,'maxLength':40}},'required':['source','target','label'],'additionalProperties':False}}
    variants=[]
    diagram_kind,preferred_layout=_visual_strategy(request.topic,programming)
    kinds=['title_card','flow_diagram','labeled_diagram','code_walkthrough'] if programming else ['title_card','flow_diagram','labeled_diagram','animated_illustration']
    extras={'title_card':[],'flow_diagram':['layout','links'],'labeled_diagram':[],'code_walkthrough':['code'],'animated_illustration':['motion']}
    for kind in kinds:
        names=['heading','type','narration','labels']+extras[kind]
        props={k:fields[k] for k in names};props['type']={'type':'string','enum':[kind]}
        variants.append({'type':'object','properties':props,'required':names,'additionalProperties':False})
    # Require the explanatory template instead of hoping a small model selects it.
    by_kind={v['properties']['type']['enum'][0]:v for v in variants}
    physical=any(word in topic for word in ('pendulum','collision','diffusion','wave','orbit'))
    middle=by_kind['code_walkthrough'] if programming else by_kind['animated_illustration'] if physical else by_kind[diagram_kind]
    remaining_kind='flow_diagram' if diagram_kind=='flow_diagram' else 'labeled_diagram'
    scene_contract=[by_kind['title_card'],middle,*([by_kind[remaining_kind]]*(count-2))]
    compact_schema={'type':'object','properties':{'title':string,'objective':string,'scenes':{'type':'array','minItems':count,'maxItems':count,'items':scene_contract},'followUp':{'type':'string','minLength':8,'maxLength':240}},'required':['title','objective','scenes','followUp'],'additionalProperties':False}
    if programming:
        prompt=re.sub(r'Only animated_illustration scenes contain motion.*?Use at most one animated illustration\.', '', prompt, flags=re.S)
        prompt=prompt.replace('For other scenes choose flow_diagram, code_walkthrough, or animated_illustration.', 'For other scenes choose flow_diagram or code_walkthrough.')
    if programming:prompt+=' For example, a useful code scene explains: The variable i takes each number in turn. The indented print(i) runs once per value. For range(3), the values are 0, 1, and 2; 3 is excluded. Diagram nodes name values or actions, for example i = 0, i = 1, i = 2, with arrows labeled next iteration. Never use abstract headings as nodes.'
    if 'water cycle' in topic or 'evaporation' in topic:prompt+=' In scene 1 explicitly say solar energy changes liquid water into water vapor, not air, and that evaporation is not boiling and can occur below the boiling point. In scene 2 explain condensation into tiny liquid droplets that form clouds. In scene 3 explain that droplets fall as rain under gravity.'
    messages=[{'role':'system','content':'You are a precise teacher. Produce compact lesson data. Use the verified facts when supplied. Keep internal planning brief; focus on a complete, concrete explanation. Never invent dates, statistics, code output, or scientific mechanisms.'},{'role':'user','content':prompt}]
    last_error=''
    with httpx.Client(timeout=httpx.Timeout(900 if request.cpuOnly else 75,connect=10),trust_env=False) as client:
        def classify_locally(question,schema):
            response=_post_chat(client,{'model':MODEL,'messages':[{'role':'system','content':'You classify educational visual teaching needs. Return only the constrained JSON.'},{'role':'user','content':question}],'stream':False,'think':False,'format':schema,'options':{'temperature':0,'num_ctx':2048,'num_predict':72,**({'num_gpu':0,'num_thread':4} if request.cpuOnly else {'num_gpu':99})},'keep_alive':'30m'})
            return response.json()['message']['content']
        # A 30-second lesson prioritizes first-frame latency. Its visual plan is
        # already constrained, so it skips a second model call; longer lessons
        # still use the semantic local classifier when rules are ambiguous.
        quick=rule_scores(request.topic)
        decisive=max(quick,key=quick.get) if quick and max(quick.values()) else None
        archetype,confidence=(decisive,.9) if decisive and request.targetDuration<=30 else route(request.topic,classify_locally)
        routing={'archetype':archetype,'confidence':confidence,'instruction':REGISTRY[archetype].visual_instruction,'diagramKind':diagram_kind,'preferredLayout':preferred_layout}
        (output/'routing.json').write_text(json.dumps(routing,ensure_ascii=False,indent=2),encoding='utf-8')
        prompt += '\nVisual teaching strategy selected from the question meaning: '+routing['instruction']+' Do not force a linear diagram when this strategy calls for a different structure.'
        messages[-1]['content']=prompt
        attempts=2 if request.cpuOnly else 1
        for attempt in range(attempts):
            progress(8+attempt*3,'planning',f'Planning locally ({"CPU only" if request.cpuOnly else "NVIDIA GPU"}, attempt {attempt+1}/{attempts})')
            response=_post_chat(client,{'model':MODEL,'messages':messages,'stream':False,'think':False,'format':compact_schema,'options':{'temperature':.2,'presence_penalty':0,'num_ctx':4096,'num_predict':max(700,220*count),**({'num_gpu':0,'num_thread':4} if request.cpuOnly else {'num_gpu':99})},'keep_alive':'30m'})
            content=response.json()['message']['content'];(output/f'model-metrics-{attempt+1}.json').write_text(json.dumps({k:v for k,v in response.json().items() if k!='message'},ensure_ascii=False),encoding='utf-8');(output/f'compact-attempt-{attempt+1}.json').write_text(content,encoding='utf-8')
            try:
                raw=json.loads(content);scenes=[]
                if len(raw['scenes'])!=count:raise ValueError(f'Provide exactly {count} scenes.')
                for i,item in enumerate(raw['scenes']):
                    kind='title_card' if i==0 else item['type']
                    labels=[label.replace('_',' ').strip() for label in item['labels'][:6]]
                    item['labels']=labels
                    if i>0 and any(t in topic for t in ('python','programming','for loop','while loop')) and item.get('code','').strip() and not any(s['type']=='code_walkthrough' for s in scenes):kind='code_walkthrough'
                    if kind=='animated_illustration' and 'pendulum' in topic:item['motion']='pendulum'
                    if kind=='animated_illustration' and item.get('motion')=='none':kind='flow_diagram'
                    if kind=='title_card':visual={'keywords':labels}
                    elif kind=='code_walkthrough':visual={'code':item['code'],'highlightLines':list(range(1,len(item['code'].splitlines())+1))}
                    elif kind=='comparison':visual={k:item[k] for k in ('leftTitle','rightTitle','rows')}
                    elif kind=='timeline':visual={'items':item['items']}
                    elif kind=='animated_illustration':visual={'nodes':labels,'motion':item['motion'],'shape':item.get('shape','sphere'),'damping':.12 if item['motion']=='pendulum' and any(t in topic for t in ('slow','stop','friction','damp')) else 0}
                    elif kind=='labeled_diagram':visual={'nodes':[{'id':f'n{index+1}','label':label} for index,label in enumerate(labels)],'edges':[],'layout':'linear'}
                    else:
                        item['layout']=preferred_layout
                        visual=_diagram_visual(item,labels)
                    scenes.append({'id':f'scene_{i+1}','type':kind,'heading':item['heading'],'narration':item['narration'],'visual':visual})
                if raw['title'].strip().casefold() in ('topic','title','lesson'):raw['title']=request.topic[:120]
                # Recognized range examples have a reliable, trusted visual model.
                # Replace vague model diagrams with their actual values; no generated
                # code is executed. Other topics retain the model's validated visuals.
                example=next((item.get('code','') for item in raw['scenes'] if code_trace(item.get('code',''))),'')
                if example:
                    import ast
                    values=code_trace(example);call=ast.parse(example).body[0].iter
                    stop=call.args[0].value if len(call.args)==1 else call.args[1].value
                    labels_by_language={'en':('Produced values','Excluded stop','Output','Stop value'),'hi':('मिलने वाले मान','सीमा शामिल नहीं','आउटपुट','सीमा'),'ta':('கிடைக்கும் மதிப்புகள்','சேராத வரம்பு','வெளியீடு','வரம்பு'),'kn':('ಬರುವ ಮೌಲ್ಯಗಳು','ಸೇರದ ಮಿತಿ','ಫಲಿತಾಂಶ','ಮಿತಿ')}
                    labels_by_language.update({'te':('వచ్చే విలువలు','చివరి హద్దు మినహాయింపు','ఫలితం','హద్దు'),'bn':('প্রাপ্ত মান','শেষ সীমা বাদ','ফলাফল','সীমা'),'mr':('मिळणारी मूल्ये','शेवटची मर्यादा वगळली','निष्पत्ती','मर्यादा'),'ml':('ലഭിക്കുന്ന മൂല്യങ്ങൾ','അവസാന പരിധി ഒഴിവാക്കി','ഫലം','പരിധി'),'gu':('મળતાં મૂલ્યો','છેલ્લી મર્યાદા બાકાત','પરિણામ','મર્યાદા'),'pa':('ਮਿਲਣ ਵਾਲੇ ਮੁੱਲ','ਆਖਰੀ ਹੱਦ ਬਾਹਰ','ਨਤੀਜਾ','ਹੱਦ'),'or':('ମିଳୁଥିବା ମୂଲ୍ୟ','ଶେଷ ସୀମା ବାହାରେ','ଫଳାଫଳ','ସୀମା')})
                    titles=labels_by_language.get(planning_request.language,labels_by_language['en'])
                    for scene in scenes:
                        if scene['type']=='flow_diagram':
                            scene['type']='comparison'
                            scene['visual']={'leftTitle':titles[0],'rightTitle':titles[1],'rows':[{'label':titles[2],'left':', '.join(v['value'].split(' = ')[1] for v in values),'right':str(stop)}]}
                # A cloze question is tied to exact scene wording, avoiding a second
                # model-generated answer key that can contradict the lesson.
                candidates=[]
                for i,(scene,item) in enumerate(zip(scenes,raw['scenes'])):
                    for label in item['labels']:
                        if len(label)>2 and label.casefold() in scene['narration'].casefold():candidates.append((i,label))
                if not candidates:
                    # Ground the cloze in an actual shared content word when the
                    # model paraphrases a label. This is text matching, not a fact guess.
                    for i,(scene,item) in enumerate(zip(scenes,raw['scenes'])):
                        tokens=sorted({t.strip('.,!?;:') for t in ' '.join(item['labels']).split()},key=len,reverse=True)
                        answer=next((t for t in tokens if len(t)>=4 and t.casefold() not in {'before','after','with','from','this','that','each','value','first','then'} and re.search(r'(?<!\w)'+re.escape(t)+r'(?!\w)',scene['narration'],re.I)),None)
                        if answer:candidates.append((i,answer))
                # A recognized code example uses the trace-grounded quiz below.
                if not candidates and example and planning_request.language in ('en','hi','ta','kn'):candidates=[(0,str(values[0]['value'].split(' = ')[1]))]
                if not candidates:raise ValueError('Use one short label exactly as it appears in narration.')
                scene_index,answer=candidates[-1]
                phrase=scenes[scene_index]['narration']
                pieces=re.split(r'(?<=[.!?।])\s+',phrase)
                phrase=next((part for part in pieces if answer.casefold() in part.casefold()),phrase)
                blank=re.sub(re.escape(answer),'____',phrase,count=1,flags=re.I)
                distractors=list(dict.fromkeys(label for item in raw['scenes'] for label in item['labels'] if label.casefold()!=answer.casefold() and label.casefold() not in phrase.casefold()))[:2]
                extras={'en':['Always zero','Never changes'],'hi':['हमेशा शून्य','कभी नहीं बदलता'],'ta':['எப்போதும் பூஜ்ஜியம்','மாறாது']}.get(planning_request.language,['0','100'])
                for item in extras:
                    if len(distractors)<2 and item not in distractors and item!=answer:distractors.append(item)
                prefixes={'en':'Complete the explanation: ','hi':'वाक्य पूरा करें: ','ta':'வாக்கியத்தை நிறைவு செய்: '}
                question=(prefixes.get(planning_request.language,'____: ')+blank)[:260]
                plan={'title':raw['title'],'level':request.level,'language':planning_request.language,'objectives':[raw['objective']],
                    'scenes':scenes,'quiz':[{'id':'q1','sceneId':scenes[scene_index]['id'],'question':question,'options':[answer,*distractors],'answer':answer,'explanation':phrase[:500]}],'followUps':[raw['followUp']]}
                if example and planning_request.language in ('en','hi','ta','kn'):
                    first=int(values[0]['value'].split(' = ')[1])
                    questions={'en':('Which value is printed first?',f'The range in this code supplies {first} first. The print statement displays that value.'),'hi':('सबसे पहले कौन सा मान दिखता है?',f'इस कोड में रेंज का पहला मान {first} है। प्रिंट निर्देश वही मान दिखाता है।'),'ta':('முதலில் எந்த மதிப்பு வெளியாகும்?',f'இந்த நிரலில் ரேஞ்ச் தரும் முதல் மதிப்பு {first}. பிரிண்ட் அதையே வெளியிடுகிறது.'),'kn':('ಮೊದಲು ಯಾವ ಮೌಲ್ಯ ಮುದ್ರಿಸಲಾಗುತ್ತದೆ?',f'ಈ ಕೋಡ್‌ನಲ್ಲಿ ರೇಂಜ್ ನೀಡುವ ಮೊದಲ ಮೌಲ್ಯ {first}. ಪ್ರಿಂಟ್ ಅದನ್ನು ತೋರಿಸುತ್ತದೆ.')}
                    question,explanation=questions[planning_request.language]
                    code_scene=next(s for s in scenes if s['type']=='code_walkthrough' and s['visual']['code']==example)
                    plan['quiz']=[{'id':'q1','sceneId':code_scene['id'],'question':question,'options':[str(first),str(first+1),str(first-1)],'answer':str(first),'explanation':explanation}]
                result=normalize(plan,planning_request,lesson_id)
                quality=audit(result.lesson,planning_request)
                if full_translation_review and request.language in ('ta','te','kn','ml'):
                    source_plan=result.lesson
                    correction=None
                    for revision in range(1,3):
                        translated_plan=_translate_lesson(source_plan,request,client,progress,output,correction,revision)
                        try:
                            quality=audit(translated_plan,request)
                            translation_review=_review_lesson(source_plan,translated_plan,request,client,progress,output,revision)
                        except ValueError as error:
                            correction=str(error)
                            if revision==2:raise ValueError(f'{language} lesson failed translation checks after correction: {correction}') from error
                        else:
                            result.lesson=translated_plan
                            quality['translationReview']=translation_review
                            (output/'translation-validated.json').write_text(result.lesson.model_dump_json(indent=2),encoding='utf-8')
                            break
                (output/'quality.json').write_text(json.dumps(quality,indent=2),encoding='utf-8')
                if planning_request.language=='en' and 'apple' in topic and any(term in ' '.join(s.narration.lower() for s in result.lesson.scenes) for term in ('stopping the browning','prevents browning completely','activated by oxygen')):raise ValueError('Oxygen is a reactant, not an enzyme activator. Lemon juice slows browning; it does not stop it permanently. Acidity reduces enzyme activity; ascorbic acid reduces quinones.')
                if planning_request.language=='en' and ('loop' in topic or 'range(' in topic):
                    spoken=' '.join(sentence for s in result.lesson.scenes for sentence in re.split(r'(?<=[.!?])\s+',s.narration.lower()) if not re.search(r'\b(mistak\w*|incorrect\w*|wrong\w*)\b',sentence))
                    if re.search(r'range\s*\(?3\)?.{0,35}(?:starts? (?:at|with) (?:1|one)|from (?:1|one) to (?:3|three))',spoken):
                        raise ValueError('Incorrect range(3) explanation: it begins at zero and excludes three.')
                (output/'planner-validated.json').write_text(result.model_dump_json(indent=2),encoding='utf-8')
                result.message='A locally generated lesson. Review the explanation in Audio refinery before sharing.'
                return result
            except (ValueError,TypeError,KeyError,IndexError) as error:
                last_error=str(error)[:1400]
                (output/f'planner-attempt-{attempt+1}-error.txt').write_text(last_error,encoding='utf-8')
                messages += [
                    {'role':'assistant','content':'My previous lesson did not satisfy the required JSON contract.'},
                    {'role':'user','content':'Redraft the complete lesson. Fix this validation error, keep the JSON compact, and finish every field: '+last_error},
                ]
    raise ValueError('Planner output did not validate within the speed limit: '+last_error)
