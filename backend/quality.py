"""Teaching checks and a safe trace for a small built-in Python range template."""
import ast,re,json,unicodedata
from difflib import SequenceMatcher
VERSION='teaching-v6'

def code_trace(code):
    # Parse display data; never compile, eval, exec or import model-written code.
    try:
        module=ast.parse(code)
        if len(module.body)!=1:return []
        loop=module.body[0]
        if not isinstance(loop,ast.For) or not isinstance(loop.target,ast.Name) or loop.orelse or len(loop.body)!=1:return []
        call=loop.iter
        if not isinstance(call,ast.Call) or not isinstance(call.func,ast.Name) or call.func.id!='range' or call.keywords or not 1<=len(call.args)<=3:return []
        if any(not isinstance(n,ast.Constant) or type(n.value)!=int or abs(n.value)>100 for n in call.args):return []
        expression=loop.body[0]
        if not isinstance(expression,ast.Expr):return []
        output=expression.value
        if not isinstance(output,ast.Call) or not isinstance(output.func,ast.Name) or output.func.id!='print' or output.keywords or len(output.args)!=1 or not isinstance(output.args[0],ast.Name) or output.args[0].id!=loop.target.id:return []
        values=list(range(*(n.value for n in call.args)))
        if not 1<=len(values)<=8:return []
        return [{'label':f'Iteration {i+1}','value':f'{loop.target.id} = {value}','output':'\n'.join(str(n) for n in values[:i+1]),'line':expression.lineno} for i,value in enumerate(values)]
    except (SyntaxError,ValueError,TypeError):return []

def audit(plan,request):
    issues=[];scenes=plan.scenes
    words=sum(len(s.narration.split()) for s in scenes)
    scripts={'hi':(0x0900,0x097F),'mr':(0x0900,0x097F),'ta':(0x0B80,0x0BFF),'kn':(0x0C80,0x0CFF),'te':(0x0C00,0x0C7F),'ml':(0x0D00,0x0D7F),'bn':(0x0980,0x09FF),'gu':(0x0A80,0x0AFF),'pa':(0x0A00,0x0A7F),'or':(0x0B00,0x0B7F)}
    regional_texts=[plan.title,*[o.text for o in plan.objectives],*plan.followUps]
    for scene in scenes:
        regional_texts.extend((scene.heading,scene.narration))
        visual=scene.visual
        regional_texts.extend(visual.keywords)
        regional_texts.extend(n.label for n in visual.nodes)
        regional_texts.extend(e.label for e in visual.edges if e.label)
        regional_texts.extend(p.label for p in visual.points if p.label)
        regional_texts.extend(label for item in visual.items for label in (item.date,item.text) if label)
        regional_texts.extend(label for row in visual.rows for label in (row.label,row.left,row.right) if label)
        regional_texts.extend(label for step in visual.trace for label in (step.label,) if label)
        regional_texts.extend((visual.leftTitle,visual.rightTitle,visual.xLabel,visual.yLabel))
    for question in plan.quiz:
        regional_texts.extend((question.question,question.explanation,*[o.text for o in question.options]))
    if request.language in scripts:
        lo,hi=scripts[request.language]
        for text in regional_texts:
            letters=[c for c in text if unicodedata.category(c).startswith('L')]
            if len(letters)>=4 and sum(lo<=ord(c)<=hi for c in letters)/len(letters)<.55:
                issues.append('Lesson text must use the selected language and its native script, not English or romanized text.')
            for token in text.split():
                if any(lo<=ord(c)<=hi for c in token) and re.search('[A-Za-z]',token):
                    issues.append('Use complete native-language words, not hybrid native/English words such as वाष्पisation. Keep code identifiers separate from translated prose.')
        for scene in scenes:
            for sentence in re.split(r'(?<=[.!?।])\s+',scene.narration):
                letters=[c for c in sentence if unicodedata.category(c).startswith('L')]
                if len(letters)>=12 and sum(lo<=ord(c)<=hi for c in letters)/len(letters)<.55:
                    issues.append('Every narration sentence and its captions must use the selected native script; no English sentence fallback.')

    maximum=min(220,round(request.targetDuration*(2.65 if request.language=='en' else 3.0)))
    if words>maximum:issues.append(f'Narration is too long ({words} words). Use at most {maximum} words in the entire lesson, not per scene.')
    minimum_words=max(30,round(request.targetDuration*(1.4 if request.language=='en' else .8)))
    if words<minimum_words:issues.append(f'Narration is too short ({words} words; at least {minimum_words} required). Explain the mechanism, a worked example, and the result.')
    if any(re.fullmatch(r'(?:scene|step|title|scene card|title card)(?:\s*\d+)?',s.heading.strip(),re.I) for s in scenes):issues.append('Replace placeholder headings such as Scene 1 with the actual idea being taught.')
    for i,a in enumerate(scenes):
        for b in scenes[i+1:]:
            if SequenceMatcher(None,a.narration.casefold(),b.narration.casefold()).ratio()>.72:issues.append('Scenes repeat the same narration. Each must teach a distinct step, example, or consequence.')
            if a.type==b.type=='flow_diagram' and a.visual.model_dump()==b.visual.model_dump():issues.append('Do not repeat the same diagram in different scenes.')
    for scene in scenes:
        labels=[n.label.casefold() for n in scene.visual.nodes] or [k.casefold() for k in scene.visual.keywords]
        if len(labels)!=len(set(labels)):issues.append('Visual labels must be distinct concepts or values, not repeated headings.')
    topic=request.topic.casefold()
    if 'water cycle' in topic or 'evaporation' in topic:
        spoken=' '.join(s.narration for s in scenes)
        if request.language=='en':
            if not re.search(r'\bwater vapou?r\b',spoken,re.I):
                issues.append('Explicitly identify the gas as water vapor; do not call it only vapor or air.')
            if not re.search(r'\b(?:not|never|without|below|under|does not|doesn.t).{0,35}\bboil(?:ing)?\b|\bboil(?:ing)?\b.{0,35}\b(?:not|never|without|below|under)\b',spoken,re.I):
                issues.append('Explicitly explain that evaporation is not boiling and can happen below the boiling point.')
        if request.language in ('ta','te','kn','ml'):
            spoken=' '.join(s.heading+' '+s.narration for s in scenes)
            terms={
                'ta':{
                    'evaporation':r'ஆவியாதல்|ஆவியாகு','vapor':r'நீராவி',
                    'boiling':r'கொதிநிலை|கொதிக்க','not_boiling':r'அல்ல|இல்லை|இன்றி|கொதிக்காமல்|கீழ்',
                    'condensation':r'ஒடுக்கம்|திரவமாகு','cloud':r'மேகம்','droplet':r'துளி',
                    'rain':r'மழை','gravity':r'புவியீர்ப்பு|ஈர்ப்பு விசை',
                },
                'te':{
                    'evaporation':r'ఆవిరైపోవడం|ఆవిరి కావడం|ఆవిరీకరణ','vapor':r'నీటి ఆవిరి',
                    'boiling':r'మరిగే|మరుగ','not_boiling':r'కాదు|లేదు|కాకుండా|మరిగించకుండా|తక్కువ',
                    'condensation':r'ఘనీభవనం|సంఘననం','cloud':r'మేఘం','droplet':r'చుక్క|బిందు',
                    'rain':r'వర్షం','gravity':r'గురుత్వాకర్షణ',
                },
                'kn':{
                    'evaporation':r'ಆವಿಯಾಗುವಿಕೆ|ಆವಿಯಾಗುವುದು|ಆವಿಯಾಗು','vapor':r'ನೀರಾವಿ|ನೀರಿನ ಆವಿ',
                    'boiling':r'ಕುದಿಯುವ|ಕುದಿ','not_boiling':r'ಅಲ್ಲ|ಇಲ್ಲ|ಕುದಿಯದೆ|ಕಡಿಮೆ',
                    'condensation':r'ಘನೀಕರಣ|ಘನೀಭವನ|ದ್ರವವಾಗಿ','cloud':r'ಮೋಡ','droplet':r'ಹನಿ',
                    'rain':r'ಮಳೆ','gravity':r'ಗುರುತ್ವಾಕರ್ಷಣೆ',
                },
                'ml':{
                    'evaporation':r'ബാഷ്പീകരണം|ആവിയാകൽ|ആവിയാകുന്നു','vapor':r'ജലബാഷ്പം|നീരാവി',
                    'boiling':r'തിളയ്ക്ക|തിളച്ച','not_boiling':r'അല്ല|ഇല്ല|തിളയ്ക്കാതെ|താഴെ',
                    'condensation':r'സംഘനനം|ദ്രവീകരണം|ദ്രവമായി','cloud':r'മേഘം','droplet':r'തുള്ളി',
                    'rain':r'മഴ','gravity':r'ഗുരുത്വാകർഷണം',
                },
            }[request.language]
            first=scenes[0].heading+' '+scenes[0].narration
            middle=' '.join(s.heading+' '+s.narration for s in scenes[1:-1])
            final=' '.join(s.heading+' '+s.narration for s in scenes[2:])
            if not re.search(terms['evaporation'],first):issues.append('Scene 1 must explain evaporation with the standard term in the selected language.')
            if not re.search(terms['vapor'],first):issues.append('Scene 1 must explicitly say that evaporation produces water vapor in the selected language.')
            if not re.search(terms['boiling'],first):issues.append('Scene 1 must explicitly distinguish evaporation from boiling in the selected language.')
            if not re.search(terms['not_boiling'],first):issues.append('Scene 1 must say evaporation is not boiling or happens below boiling temperature.')
            if len(scenes)>2:
                if not re.search(terms['condensation'],middle):issues.append('Scene 2 must explain condensation with the standard term in the selected language.')
                if not re.search(terms['cloud'],middle):issues.append('Scene 2 must explain that condensation forms clouds in the selected language.')
                if not re.search(terms['droplet'],middle):issues.append('Scene 2 must describe the liquid droplets that form clouds.')
                if not re.search(terms['rain'],final):issues.append('Scene 3 must explain that droplets fall as rain.')
                if not re.search(terms['gravity'],final):issues.append('Scene 3 must explain that gravity pulls rain downward.')
            for sentence in re.split(r'(?<=[.!?।])\s+',spoken):
                if re.search(terms['boiling'],sentence) and not re.search(terms['not_boiling'],sentence):
                    issues.append('Evaporation is not boiling: explain the distinction in the selected language.')
        for scene in scenes:
            for sentence in re.split(r'(?<=[.!?।])\s+',scene.heading+'. '+scene.narration):
                if re.search(r'boil|उबल|उकळ|கொதி|మరుగ|ফুট',sentence,re.I) and not re.search(r'not|never|below|without|doesn.t|नहीं|नाही|இல்லை|அல்ல|కాదు|లేదు|নয়|না',sentence,re.I):
                    issues.append('Evaporation is not boiling: water changes to water vapor below its boiling point. Correct the heading and narration in the selected language.')
                if re.search(r'वायु में बदल|हवा में बदल',sentence):
                    issues.append('Water evaporates into water vapor, not into air. Use जलवाष्प for gaseous water.')
    if any(t in topic for t in ('python','programming','for loop','while loop')) and not any(s.type=='code_walkthrough' for s in scenes):issues.append('A programming lesson must contain an actual code walkthrough, not a row of keywords.')
    if any(s.type=='flow_diagram' and not any(e.label.strip() for e in s.visual.edges) for s in scenes):issues.append('Explain diagram relationships with meaningful arrow labels; disconnected keywords are not a process.')
    if any(t in topic for t in ('python','programming','for loop','while loop','range(')) and any(s.type=='animated_illustration' for s in scenes):issues.append('Physical animations do not explain code execution. Use code and a trace of the actual values.')
    if request.language=='en':
        for scene in scenes:
            if scene.type=='flow_diagram' and any(e.label.casefold() in {n.label.casefold() for n in scene.visual.nodes} for e in scene.visual.edges):issues.append('Arrow labels must explain a relationship, not copy a node label. Use a relationship such as transfers energy or opposes motion.')
        cues={'collision':('collid','collision','impact','bounce'),'pendulum':('pendulum','swing','pivot'),'orbit':('orbit','revolv'),'diffusion':('diffus','spread','concentrat'),'wave':('wave','oscillat','vibrat'),'transfer':('transfer','flow','moves from')}
        for scene in scenes:
            if scene.type=='animated_illustration' and not any(c in (topic+' '+scene.narration.casefold()) for c in cues.get(scene.visual.motion,())):issues.append('Animation must directly explain the named physical process in its narration.')
    if request.language=='en' and 'pendulum' in topic:
        spoken=' '.join(s.narration.casefold() for s in scenes)
        if any(re.search(r'gravity.{0,35}(?:upward|pulls? (?:it |the bob )?up)',sentence) and not re.search(r'not|never',sentence) for sentence in re.split(r'[.!?;]',spoken)):issues.append('Gravity acts downward, not upward. Inertia carries the bob upward while kinetic energy changes into potential energy.')
        if re.search(r'bob.{0,20}rubs.{0,30}pivot',spoken):issues.append('The bob does not rub against the pivot. Pivot friction occurs in the joint or bearing where the rod or string turns.')
        if re.search(r'(?:speed|velocity).{0,25}zero.{0,70}(?:because|due to).{0,60}(?:air|friction|lost)',spoken):issues.append('A pendulum is momentarily still at a turning point even without friction. Do not attribute that instant of zero speed only to air resistance.')
        if any(re.search(r'(?:lowest|bottom).{0,60}(?:stops|speed is zero)|stops? (?:at|in) (?:the )?(?:bottom|lowest)',sentence) for sentence in re.split(r'[.!?;]',spoken)):issues.append('A pendulum is fastest at the bottom and momentarily stops at a turning point, not at the bottom.')
    if issues:raise ValueError(' '.join(dict.fromkeys(issues)))
    return {'version':VERSION,'passed':True,'wordCount':words,'checks':['length budget','distinct scenes','specific headings','appropriate visuals','labeled relationships','native-script lesson text','selected misconception checks']}
