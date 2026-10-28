"""Offline question transcription with a locally stored Faster-Whisper model."""
import threading
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
MODEL_DIR=ROOT/'models'/'asr'/'faster-whisper-tiny'
LOCK=threading.RLock()
_MODEL=None
LANGUAGE_HINTS={'en':'en','hi':'hi','ta':'ta','te':'te','kn':'kn','ml':'ml','mr':'mr','bn':'bn','gu':'gu','pa':'pa','or':'or'}

def ready():
    return (MODEL_DIR/'model.bin').is_file() and (MODEL_DIR/'tokenizer.json').is_file()

def transcribe(path:Path, language:str='en') -> str:
    if not ready():
        raise ValueError('The local speech-to-text model is not installed. Run SETUP-SPEECH-TO-TEXT.cmd while online once.')
    global _MODEL
    with LOCK:
        if _MODEL is None:
            from faster_whisper import WhisperModel
            _MODEL=WhisperModel(str(MODEL_DIR),device='cpu',compute_type='int8',local_files_only=True,cpu_threads=4,num_workers=1)
        segments,_=_MODEL.transcribe(str(path),language=LANGUAGE_HINTS.get(language),task='transcribe',beam_size=3,temperature=0,condition_on_previous_text=False,vad_filter=True)
        text=' '.join(segment.text.strip() for segment in segments).strip()
    if not text:raise ValueError('I could not hear a clear question. Please try again or type it.')
    return text[:600]