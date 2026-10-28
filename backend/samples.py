"""Reviewed demo, explicitly labeled when the local planner fails."""
from .planner import normalize
TEXT={
'en': ['Python loops: a worked example','One instruction, three values','Read the two lines','Follow the output',
'A for loop repeats an instruction for each value in a sequence. Instead of writing the same instruction three times, we write it once inside a loop. Let us follow a small example.',
'In this code, range of three supplies zero, one, and two. The variable i takes one value at a time. The indented print statement runs once for each value. Indentation places the statement inside the loop.',
'The output is zero, then one, then two, each on its own line. Three is excluded because range stops before its upper limit. After two, there are no values left, so the loop ends.',
'Which value is printed first?','Zero','One','Three','Range starts at zero and stops before three.','How does a while loop work?'],
'hi':['पायथन लूप: एक उदाहरण','एक निर्देश, तीन मान','कोड की दो पंक्तियाँ','आउटपुट देखें',
'फॉर लूप किसी क्रम के हर मान के लिए एक निर्देश दोहराता है। एक ही निर्देश को तीन बार लिखने के बजाय, हम उसे लूप के अंदर एक बार लिखते हैं। एक छोटा उदाहरण समझते हैं।',
'इस कोड में रेंज तीन से शून्य, एक और दो मिलते हैं। हर बार आई में अगला मान आता है। अंदर लिखा प्रिंट निर्देश उस मान को दिखाता है। खाली जगह बताती है कि निर्देश लूप के अंदर है।',
'आउटपुट में पहले शून्य, फिर एक, फिर दो आते हैं। हर मान अलग पंक्ति पर दिखता है। तीन शामिल नहीं है, क्योंकि रेंज ऊपरी सीमा से पहले रुकती है। दो के बाद कोई मान नहीं बचता और लूप समाप्त होता है।',
'सबसे पहले कौन सा मान दिखता है?','शून्य','एक','तीन','रेंज शून्य से शुरू होती है और तीन से पहले रुकती है।','वाइल लूप कैसे काम करता है?'],
 'ta':['பைதான் சுழற்சி: ஓர் எடுத்துக்காட்டு','ஒரு செயல், மூன்று மதிப்புகள்','இரண்டு வரி நிரல்','வெளியீட்டைப் பார்ப்போம்',
'ஒரு வரிசையில் உள்ள ஒவ்வொரு மதிப்புக்கும் ஒரே செயலைச் செய்ய சுழற்சி உதவுகிறது. ஒரே கட்டளையை மூன்று முறை எழுத வேண்டியதில்லை. சுழற்சிக்குள் ஒருமுறை எழுதினால் போதும். இப்போது ஒரு சிறிய நிரலைப் படிப்படியாகப் பார்ப்போம்.',
'இந்த நிரலில் ரேஞ்ச் மூன்று என்பது பூஜ்ஜியம், ஒன்று, இரண்டு ஆகிய மதிப்புகளைத் தருகிறது. ஒவ்வொரு முறையும் ஐ என்ற மாறிக்கு அடுத்த மதிப்பு கிடைக்கிறது. உள்ளே உள்ள பிரிண்ட் கட்டளை அந்த மதிப்பை வெளியிடுகிறது. வரியின் தொடக்க இடைவெளி முக்கியமானது.',
'முதலில் பூஜ்ஜியம், பிறகு ஒன்று, அதன் பிறகு இரண்டு வெளியாகும். ஒவ்வொரு மதிப்பும் தனித்தனி வரியில் இருக்கும். மூன்று இதில் சேராது. ரேஞ்ச் அதன் மேல் வரம்புக்கு முன்பே நிற்கும். இரண்டு முடிந்ததும் அடுத்த மதிப்பு இல்லை. எனவே சுழற்சி முடிகிறது.',
'முதலில் எந்த மதிப்பு வெளியாகும்?','பூஜ்ஜியம்','ஒன்று','மூன்று','ரேஞ்ச் பூஜ்ஜியத்தில் தொடங்கி மூன்றுக்கு முன்பே நிற்கிறது.','வைல் சுழற்சி எப்படி வேலை செய்கிறது?']}

def sample(request, ident):
    if request.language not in TEXT:raise ValueError('Planner unavailable. The offline demonstration is available in English, Hindi and Tamil; retry or choose one of these languages.')
    t=TEXT[request.language]
    data={'title':t[0],'level':request.level,'language':request.language,'objectives':[t[1]],'scenes':[
        {'id':'intro','type':'title_card','heading':t[1],'narration':t[4],'visual':{'keywords':['for','range(3)','0 → 1 → 2']}},
        {'id':'code','type':'code_walkthrough','heading':t[2],'narration':t[5],'visual':{'code':'for i in range(3):\n    print(i)','highlightLines':[1,2]}},
        {'id':'flow','type':'flow_diagram','heading':t[3],'narration':t[6],'visual':{'nodes':['i = 0 → print(0)','i = 1 → print(1)','i = 2 → print(2)']}}],
        'quiz':[{'id':'q1','sceneId':'code','language':request.language,'question':t[7],'options':t[8:11],'answer':t[8],'explanation':t[11]}],'followUps':[t[12]]}
    data['scenes'][2]['visual']['edges']=[{'source':'n1','target':'n2','label':{'en':'next value','hi':'अगला मान','ta':'அடுத்த மதிப்பு'}[request.language]},{'source':'n2','target':'n3','label':{'en':'next value','hi':'अगला मान','ta':'அடுத்த மதிப்பு'}[request.language]}]
    result=normalize(data,request,ident)
    result.message='The local planner was unavailable or returned invalid data. This is a reviewed Python-loop demonstration, not a generated answer to your requested topic.'
    return result
