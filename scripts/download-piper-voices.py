import urllib.request,concurrent.futures,json
from pathlib import Path
root=Path(__file__).resolve().parent.parent/'voices'/'piper';root.mkdir(parents=True,exist_ok=True)
def get(item):
 name,sub=item;folder=root/name;folder.mkdir(exist_ok=True)
 for file in (name+'.onnx',name+'.onnx.json','MODEL_CARD'):
  url='https://huggingface.co/rhasspy/piper-voices/resolve/main/'+sub+'/'+file
  if not (folder/file).exists():
   partial=folder/(file+'.part');urllib.request.urlretrieve(url,partial);partial.replace(folder/file)
 print(name,'ready',flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(get,[('en_US-arctic-medium','en/en_US/arctic/medium'),('en_US-lessac-medium','en/en_US/lessac/medium'),('en_GB-cori-high','en/en_GB/cori/high')]))
print(json.loads((root/'en_US-arctic-medium/en_US-arctic-medium.onnx.json').read_text())['speaker_id_map'],flush=True)
