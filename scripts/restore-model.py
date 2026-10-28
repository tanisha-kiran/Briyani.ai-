"""Run from the extracted model transfer folder on the destination laptop."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil

def digest(path):
    result=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''):result.update(block)
    return result.hexdigest()

def restore():
    source=Path(__file__).resolve().parent/'models'
    manifest_rel=Path('manifests/registry.ollama.ai/library/biryani-planner/latest')
    manifest=source/manifest_rel
    if not manifest.is_file():raise SystemExit('Extract the complete model ZIP first; its models folder must be beside this script.')
    target=Path(os.environ.get('OLLAMA_MODELS') or Path.home()/'.ollama'/'models').expanduser().resolve()
    data=json.loads(manifest.read_text(encoding='utf-8'))
    entries=[data['config'],*data['layers']]
    existing=target/manifest_rel
    if existing.exists() and existing.read_bytes()!=manifest.read_bytes():raise SystemExit('A different biryani-planner:latest already exists. Nothing was overwritten. Back it up or choose a separate OLLAMA_MODELS directory.')
    pending=[]
    for entry in entries:
        name=entry['digest']
        if not re.fullmatch(r'sha256:[0-9a-f]{64}',name):raise SystemExit('Invalid digest in the model manifest.')
        filename=name.replace(':','-');src=source/'blobs'/filename;dst=target/'blobs'/filename
        print('Verifying',filename,flush=True)
        if not src.is_file() or src.stat().st_size!=entry['size'] or digest(src)!=name.split(':')[1]:raise SystemExit('Source model verification failed: '+filename)
        if dst.exists():
            if dst.stat().st_size!=entry['size'] or digest(dst)!=name.split(':')[1]:raise SystemExit('Existing destination blob failed verification; no overwrite performed: '+str(dst))
        else:pending.append((src,dst))
    for src,dst in pending:
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(src,dst)
        if digest(dst)!=dst.name.split('-',1)[1]:raise SystemExit('Copied blob verification failed. Model manifest was not installed.')
    existing.parent.mkdir(parents=True,exist_ok=True)
    if not existing.exists():shutil.copyfile(manifest,existing)
    print('Existing biryani-planner model restored to:',target)
    print('Start Ollama and run: ollama list')

if __name__=='__main__':restore()
