"""Offline neural speech: Piper English, Kokoro Hindi, and native MMS regional voices."""
import ctypes as C
import hashlib, json, threading, wave, tempfile, os, asyncio, subprocess, re, uuid
from pathlib import Path
import numpy as np
import espeakng_loader
ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / 'output' / 'speech'
CACHE.mkdir(parents=True, exist_ok=True)
RUNTIME=ROOT/'output'/'runtime';RUNTIME.mkdir(parents=True,exist_ok=True)
tempfile.tempdir=str(RUNTIME)
LOCK = threading.RLock()
ONLINE_LOCKS=[threading.RLock() for _ in range(64)]
LANGUAGES = {'en':'English','hi':'Hindi','ta':'Tamil','te':'Telugu','kn':'Kannada','ml':'Malayalam','mr':'Marathi','bn':'Bengali','gu':'Gujarati','pa':'Punjabi','or':'Odia'}
_kokoro = None
_espeak = None
_piper = None
_piper_name = None

def neural_ready():
    return all((ROOT/'voices'/f).is_file() for f in ('kokoro-v1.0.int8.onnx','voices-v1.0.bin'))

MMS_CODES={'hi':'hin','kn':'kan','ta':'tam','te':'tel','ml':'mal','mr':'mar','bn':'ben','gu':'guj','pa':'pan','or':'ory'}
_mms=None
_mms_language=None
ONLINE={'en':('en-GB-SoniaNeural','en-GB-RyanNeural'),'hi':('hi-IN-SwaraNeural','hi-IN-MadhurNeural'),'kn':('kn-IN-SapnaNeural','kn-IN-GaganNeural'),'ta':('ta-IN-PallaviNeural','ta-IN-ValluvarNeural'),'te':('te-IN-ShrutiNeural','te-IN-MohanNeural'),'ml':('ml-IN-SobhanaNeural','ml-IN-MidhunNeural'),'mr':('mr-IN-AarohiNeural','mr-IN-ManoharNeural'),'bn':('bn-IN-TanishaaNeural','bn-IN-BashkarNeural'),'gu':('gu-IN-DhwaniNeural','gu-IN-NiranjanNeural')}
def local_ready(code):
    folder=ROOT/'voices'/'mms'/code
    return (ROOT/'voices/piper/en_US-arctic-medium/en_US-arctic-medium.onnx').is_file() if code=='en' else (neural_ready() or (folder/'config.json').is_file()) if code=='hi' else (folder/'config.json').exists() and any((folder/name).exists() for name in ('model.safetensors','pytorch_model.bin'))
def voices():
    return [{'name':('Piper' if code=='en' else 'MMS native')+' · '+name,'language':code,'gender':'Native voice','quality':'neural','neuralAvailable':local_ready(code),'localAvailable':local_ready(code),'onlineAvailable':False} for code,name in LANGUAGES.items()]

def piper_audio(text,accent,speed):
    global _piper,_piper_name
    if not local_ready('en'):raise ValueError('The local English neural voice is not installed. Run SETUP-LOCAL-MODELS.cmd.')
    from piper.voice import PiperVoice
    from piper.config import PiperConfig,SynthesisConfig
    import onnxruntime as rt
    name={'indian':'en_US-arctic-medium','british':'en_GB-cori-high','american':'en_US-lessac-medium'}[accent]
    folder=ROOT/'voices'/'piper'/name
    if _piper_name!=name:
        _piper=None
        options=rt.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
        session=rt.InferenceSession(str(folder/(name+'.onnx')),sess_options=options,providers=['CPUExecutionProvider'])
        config=PiperConfig.from_dict(json.loads((folder/(name+'.onnx.json')).read_text(encoding='utf-8')))
        _piper=PiperVoice(session=session,config=config,download_dir=RUNTIME)
        _piper_name=name
    config=SynthesisConfig(speaker_id=3 if accent=='indian' else None,length_scale=1.15/speed)
    chunks=list(_piper.synthesize(text,syn_config=config))
    return np.concatenate([c.audio_float_array for c in chunks]),_piper.config.sample_rate

def mms_audio(text,language,speed):
    global _mms,_mms_language
    if not local_ready(language):raise ValueError('Install the local neural '+LANGUAGES[language]+' voice using SETUP-NATIVE-VOICES.cmd, then restart the studio.')
    import torch
    from transformers import VitsModel, AutoTokenizer
    torch.set_num_threads(2)
    if _mms_language!=language:
        _mms=None
        folder=str(ROOT/'voices'/'mms'/language)
        _mms=(VitsModel.from_pretrained(folder,local_files_only=True).eval(),AutoTokenizer.from_pretrained(folder,local_files_only=True))
        _mms_language=language
    model,tokenizer=_mms;model.speaking_rate=speed
    # Short sentence chunks keep prosody and memory predictable.
    chunks=[]
    for sentence in re.split(r'(?<=[.!?।])\s+',text):
        if not sentence.strip():continue
        inputs=tokenizer(sentence,return_tensors='pt')
        if inputs.input_ids.numel()<2:raise ValueError('Enter narration in the selected language script.')
        torch.manual_seed(42)
        with torch.inference_mode():audio=model(**inputs).waveform[0].cpu().numpy()
        chunks.extend([audio,np.zeros(int(model.config.sampling_rate*.18),dtype=np.float32)])
    return np.concatenate(chunks),model.config.sampling_rate

def online_audio(*args,**kwargs):
    raise ValueError('Cloud speech is disabled. Choose a local native voice.')

def basic_audio(text, language, speed):
    global _espeak
    if _espeak is None:
        _espeak = C.CDLL(espeakng_loader.get_library_path())
        _espeak.espeak_Initialize.argtypes = [C.c_int,C.c_int,C.c_char_p,C.c_int]
        _espeak.espeak_Initialize.restype = C.c_int
        _espeak.rate = _espeak.espeak_Initialize(2,0,str(espeakng_loader.get_data_path()).encode(),0)
        if _espeak.rate <= 0: raise RuntimeError('Offline speech could not initialize')
        _espeak.espeak_Synth.argtypes = [C.c_char_p,C.c_size_t,C.c_uint,C.c_int,C.c_uint,C.c_uint,C.c_void_p,C.c_void_p]
    chunks = []
    @C.CFUNCTYPE(C.c_int,C.POINTER(C.c_short),C.c_int,C.c_void_p)
    def callback(samples,count,events):
        if samples and count: chunks.append(C.string_at(samples,count*2))
        return 0
    _espeak.espeak_SetSynthCallback(callback)
    if _espeak.espeak_SetVoiceByName(language.encode()) != 0: raise ValueError('Voice not available: '+language)
    _espeak.espeak_SetParameter(1,round(155*speed),0)
    data=text.encode('utf-8')
    if _espeak.espeak_Synth(data,len(data)+1,0,1,0,1,None,None)!=0: raise RuntimeError('Offline synthesis failed')
    _espeak.espeak_Synchronize()
    pcm=b''.join(chunks)
    if not pcm: raise RuntimeError('Voice produced empty audio')
    return np.frombuffer(pcm,dtype=np.int16).astype(np.float32)/32768, _espeak.rate

def synthesize(text, language='en', speed=1.0, voice='female', accent='indian'):
    global _kokoro
    if voice.startswith('online-'):raise ValueError('Hackathon mode requires local voices. Choose a local neural voice.')
    if voice not in ('basic','female','male','online-female','online-male'):raise ValueError('Choose a supported voice')
    if language not in LANGUAGES: raise ValueError('Unsupported narration language')
    if not text.strip() or len(text)>900: raise ValueError('Narration must contain 1–900 characters')
    if not .75 <= speed <= 1.3: raise ValueError('Voice speed must be 0.75–1.30')
    ident=hashlib.sha256(json.dumps([text,language,speed,voice,accent,'speech-local-v6', 'mms-hi' if language=='hi' and voice!='male' else ''],ensure_ascii=False).encode()).hexdigest()
    path=CACHE/(ident+'.wav')
    with (ONLINE_LOCKS[int(ident[:2],16)%64] if voice.startswith('online-') else LOCK):
        if not path.exists():
            if voice.startswith('online-'):
                samples,rate=online_audio(text,language,speed,voice,accent)
            elif voice!='basic' and language=='en':
                samples,rate=piper_audio(text,accent,speed)
            elif voice!='basic' and language=='hi' and voice!='male' and (ROOT/'voices/mms/hi/model.safetensors').exists():
                samples,rate=mms_audio(text,language,speed)
            elif voice!='basic' and language=='hi' and neural_ready():
                from kokoro_onnx import Kokoro
                if _kokoro is None:
                    import onnxruntime as rt
                    options=rt.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
                    session=rt.InferenceSession(str(ROOT/'voices/kokoro-v1.0.int8.onnx'),sess_options=options,providers=['CPUExecutionProvider'])
                    _kokoro=Kokoro.from_session(session,str(ROOT/'voices/voices-v1.0.bin'))
                selected=('hm_omega' if voice=='male' else 'hf_alpha') if language=='hi' or accent=='indian' else ('bm_george' if voice=='male' else 'bf_emma')
                if language=='en' and accent=='american':selected='am_michael' if voice=='male' else 'af_heart'
                samples,rate=_kokoro.create(text,voice=selected,speed=speed,lang='hi' if language=='hi' else 'en-us' if accent in ('american','indian') else 'en-gb')
            elif voice=='basic': samples,rate=basic_audio(text,language,speed)
            elif language in MMS_CODES:samples,rate=mms_audio(text,language,speed)
            else:raise ValueError('The local neural voice is not installed. Install the local voice model.')
            pcm=(np.clip(samples,-1,1)*32767).astype('<i2')
            if len(pcm)<rate*.1: raise RuntimeError('Narration audio is too short')
            temporary=path.with_suffix('.tmp')
            with wave.open(str(temporary),'wb') as output:
                output.setnchannels(1);output.setsampwidth(2);output.setframerate(rate);output.writeframes(pcm.tobytes())
            temporary.replace(path)
    return path
