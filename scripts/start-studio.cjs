const {spawn,spawnSync}=require('node:child_process');const path=require('node:path');const fs=require('node:fs');const http=require('node:http');
const desiredModel=process.env.BIRYANI_MODEL||'qwen3.5:4b';const root=path.resolve(__dirname,'..');const children=[];
const ollama=process.env.BIRYANI_OLLAMA_EXE||path.join(process.env.USERPROFILE,'AppData','Local','Programs','Ollama','ollama.exe');
function child(exe,args,env=process.env,required=true){const c=spawn(exe,args,{cwd:root,stdio:['ignore',fs.openSync(path.join(root,path.basename(exe)+'.log'),'a'),fs.openSync(path.join(root,path.basename(exe)+'-error.log'),'a')],windowsHide:true,env});children.push(c);c.on('error',e=>{console.error(e.message);if(required){close();process.exitCode=1}});c.on('exit',code=>{if(!closing&&required){console.error('Service exited:',path.basename(exe),code);close();process.exitCode=code||1}});return c;}
let closing=false;function close(){if(closing)return;closing=true;children.forEach(c=>{if(!c.pid||c.exitCode!==null)return;if(process.platform==='win32')spawnSync('taskkill',['/PID',String(c.pid),'/T','/F'],{windowsHide:true,stdio:'ignore'});else c.kill()})}
const ready=url=>new Promise(resolve=>{const req=http.get(url+'/api/tags',r=>{let body='';r.on('data',c=>body+=c);r.on('end',()=>{try{resolve(r.statusCode===200&&JSON.parse(body).models?.some(m=>m.name===desiredModel||m.name===desiredModel+':latest'))}catch{resolve(false)}})});req.on('error',()=>resolve(false));req.setTimeout(5000,()=>{req.destroy();resolve(false)})});
const reachable=url=>new Promise(resolve=>{const req=http.get(url+'/api/tags',r=>{r.resume();resolve(true)});req.on('error',()=>resolve(false));req.setTimeout(2000,()=>{req.destroy();resolve(false)})});
const apiReachable=()=>new Promise(resolve=>{const req=http.get('http://127.0.0.1:53842/api/health',r=>{r.resume();resolve(r.statusCode===200)});req.on('error',()=>resolve(false));req.setTimeout(2000,()=>{req.destroy();resolve(false)})});
async function main(){
 let endpoint=process.env.BIRYANI_OLLAMA||'http://127.0.0.1:11434';
 if(!await ready(endpoint)){
   endpoint='http://127.0.0.1:11435';
   // Another local studio can already own Ollama. Reuse its listener instead
   // of treating Windows' EADDRINUSE as a fatal studio-startup failure.
   if(!await ready(endpoint) && !await reachable(endpoint)){
     if(!fs.existsSync(ollama))throw Error('Install Ollama or set BIRYANI_OLLAMA_EXE to ollama.exe.');
     child(ollama,['serve'],{...process.env,OLLAMA_HOST:'127.0.0.1:11435',OLLAMA_MODELS:process.env.OLLAMA_MODELS||path.join(process.env.USERPROFILE,'.ollama','models'),OLLAMA_NO_CLOUD:'1',OLLAMA_NUM_PARALLEL:'1',OLLAMA_MAX_LOADED_MODELS:'1'},false);
     let ok=false;for(let i=0;i<120;i++){if(await ready(endpoint)){ok=true;break}await new Promise(r=>setTimeout(r,1000))}if(!ok)throw Error('Planner did not start. See ollama.exe-error.log.');
   }
 }
 if(!await apiReachable()) child(path.join(root,'.venv','Scripts','python.exe'),['-m','uvicorn','backend.app:app','--host','127.0.0.1','--port','53842','--no-access-log'],{...process.env,BIRYANI_OLLAMA:endpoint,BIRYANI_MODEL:desiredModel,HF_HOME:path.join(root,'models','huggingface')}); else console.log('Reusing local lesson engine on port 53842.');
 child(process.execPath,[path.join(root,'preview-server.cjs')],process.env,false);
 console.log('Open http://127.0.0.1:53841/ — offline teaching studio.');
}
main().catch(e=>{console.error(e);close();process.exitCode=1});process.on('SIGINT',close);process.on('SIGTERM',close);
