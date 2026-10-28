from pathlib import Path
import urllib.request,json,concurrent.futures
root=Path(__file__).resolve().parent.parent/'voices'/'mms';root.mkdir(parents=True,exist_ok=True)
codes={'hi':'hin','kn':'kan','ta':'tam','te':'tel','ml':'mal','mr':'mar','bn':'ben','gu':'guj','pa':'pan','or':'ory'}
def download(item):
 lang,code=item;repo='facebook/mms-tts-'+code;dest=root/lang;dest.mkdir(exist_ok=True)
 data=json.load(urllib.request.urlopen('https://huggingface.co/api/models/'+repo,timeout=60));names={x['rfilename'] for x in data['siblings']}
 files=[n for n in ['config.json','tokenizer_config.json','special_tokens_map.json','vocab.json','README.md'] if n in names]
 files.append('model.safetensors' if 'model.safetensors' in names else 'pytorch_model.bin')
 for name in files:
  p=dest/name
  if not p.exists():
   for attempt in range(3):
    try:urllib.request.urlretrieve('https://huggingface.co/'+repo+'/resolve/main/'+name,str(p)+'.part');Path(str(p)+'.part').replace(p);break
    except Exception:
     if attempt==2:raise
 print(lang+' ready',flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 for result in pool.map(download,codes.items()):pass
