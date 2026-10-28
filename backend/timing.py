"""Audio-led duration fitting without truncating speech or long silent padding."""
import math
import subprocess
import wave
from pathlib import Path
import imageio_ffmpeg

FPS = 15

class TimingMismatch(ValueError):
    def __init__(self, measured, target, word_count):
        self.word_budget = max(24, round(word_count * (target - 1.5) / measured))
        super().__init__(f'Narration takes {measured:.1f}s for a {target}s lesson. Redraft to about {self.word_budget} spoken words; do not truncate speech.')

def seconds(path):
    with wave.open(str(path), 'rb') as audio:
        return audio.getnframes() / audio.getframerate()

def fit_narration(paths, target, word_count):
    lengths = [seconds(path) for path in paths]
    total = sum(lengths)
    factor = total / (target - .4 * len(paths))
    if not .80 <= factor <= 1.30:
        raise TimingMismatch(total, target, word_count)
    adjusted=[]
    for path in paths:
        fitted=path.with_name(path.stem+'-timed.wav')
        result=subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-y','-i',str(path),'-af',f'atempo={factor:.8f}','-c:a','pcm_s16le',str(fitted)],capture_output=True,text=True,timeout=120)
        if result.returncode:
            raise RuntimeError('Narration timing failed: '+result.stderr[-1200:])
        adjusted.append((fitted,seconds(fitted)))
    # Allocate whole video frames. Their sum is exactly the requested length.
    frames=[math.ceil((duration+.1)*FPS) for _,duration in adjusted]
    remainder=round(target*FPS)-sum(frames)
    if remainder<0:
        raise ValueError('Timed speech does not fit the requested video; no words were cut.')
    for i in range(remainder):frames[i%len(frames)]+=1
    return [(path,duration,frame_count/FPS) for (path,duration),frame_count in zip(adjusted,frames)],factor
