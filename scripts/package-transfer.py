"""Package source and the existing model without starting any application service."""
from pathlib import Path
import hashlib,json,zipfile,datetime,ast

ROOT=Path(__file__).resolve().parent.parent
DEST=ROOT/'transfer';DEST.mkdir(exist_ok=True)
MODEL=Path.home()/'.ollama'/'models'
manifest_rel=Path('manifests/registry.ollama.ai/library/biryani-planner/latest')
manifest=MODEL/manifest_rel
SKIP={'node_modules','.venv','__pycache__','.pytest_cache','.git','dist','output','transfer'}

def unique(name):
    result=DEST/name
    if result.exists():result=result.with_stem(result.stem+'-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
    return result

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()

ast.parse((ROOT/'scripts/restore-model.py').read_text(encoding='utf-8'))
app_zip=unique('BiryaniAI-Application.zip')
with zipfile.ZipFile(app_zip,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=5) as z:
    roots=['backend','blu-companion','docs','public','renderer','scripts','src','tests']
    files=[ROOT/name for name in ['.gitignore','index.html','package.json','package-lock.json','preview-server.cjs','README.md','tsconfig.json','START-HERE-GPU.md','SETUP-WINDOWS.cmd','START-STUDIO.cmd']]
    for folder in roots:files.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and not p.is_symlink() and not any(part in SKIP for part in p.relative_to(ROOT).parts))
    for file in sorted(set(files)):z.write(file,'BiryaniAI/'+file.relative_to(ROOT).as_posix())
    examples={'python-loop':'160f6e35552c4a61ad1a8c3f2f6ea18d','apple-browning':'67ec7925a6044992b42d7c5a2e9fcefb'}
    for label,ident in examples.items():
        for filename in ['lesson.mp4','lesson.json','captions.vtt']:
            file=ROOT/'output'/'lessons'/ident/filename
            if file.is_file():z.write(file,f'BiryaniAI/examples/{label}/{filename}')
with zipfile.ZipFile(app_zip) as z:
    assert z.testzip() is None
    assert 'BiryaniAI/index.html' in z.namelist()
    assert not any('/node_modules/' in n or '/.venv/' in n or n.endswith('jobs.sqlite3') for n in z.namelist())
print('Application ZIP:',app_zip,app_zip.stat().st_size,flush=True)

data=json.loads(manifest.read_text(encoding='utf-8'));entries=[data['config'],*data['layers']]
for entry in entries:
    file=MODEL/'blobs'/entry['digest'].replace(':','-')
    assert file.stat().st_size==entry['size']
    assert sha(file)==entry['digest'].split(':')[1],f'Model digest mismatch: {file.name}'
print('Existing model: all six blob sizes and SHA-256 digests verified.',flush=True)
model_zip=unique('BiryaniAI-Existing-Model.zip')
with zipfile.ZipFile(model_zip,'x',compression=zipfile.ZIP_STORED,allowZip64=True) as z:
    prefix='BiryaniAI-Existing-Model/'
    z.write(manifest,prefix+'models/'+manifest_rel.as_posix())
    for entry in entries:
        file=MODEL/'blobs'/entry['digest'].replace(':','-');z.write(file,prefix+'models/blobs/'+file.name)
    z.write(ROOT/'scripts/restore-model.py',prefix+'restore-model.py')
    z.write(ROOT/'START-HERE-GPU.md',prefix+'START-HERE-GPU.md')
with zipfile.ZipFile(model_zip) as z:assert z.testzip() is None
checksums={p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in [app_zip,model_zip]}
(DEST/'SHA256SUMS.json').write_text(json.dumps(checksums,indent=2),encoding='utf-8')
print(json.dumps(checksums,indent=2),flush=True)
