const {spawn}=require('node:child_process');
const path=require('node:path'); const fs=require('node:fs');
const root=path.resolve(__dirname,'..'); const python=path.join(root,'.venv','Scripts','python.exe');
function launch(name,command,args,env){
 const out=fs.openSync(path.join(root,`detached-${name}.log`),'a');const err=fs.openSync(path.join(root,`detached-${name}-error.log`),'a');
 const child=spawn(command,args,{cwd:root,env:{...process.env,...env},detached:true,stdio:['ignore',out,err],windowsHide:true}); child.unref();
}
launch('api',python,['-m','uvicorn','backend.app:app','--host','127.0.0.1','--port','53842','--no-access-log'],{BIRYANI_OLLAMA:'http://127.0.0.1:11435',BIRYANI_MODEL:'qwen3.5:4b',HF_HOME:path.join(root,'models','huggingface')});
launch('ui',process.execPath,['preview-server.cjs'],{});
console.log('Started local studio children.');