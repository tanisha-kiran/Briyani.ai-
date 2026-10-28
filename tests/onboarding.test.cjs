const test=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const source=fs.readFileSync('src/companion-preview.js','utf8');
function load(storage={}){
 const window={BluVoice:{supported:['en','hi','ta','te','bn','mr'],setMuted(){},setPreference(){},speak(){},stop(){},enable(){}},addEventListener(){},dispatchEvent(){}};
 const context={window,localStorage:{getItem:k=>storage[k]||null,setItem:(k,v)=>storage[k]=v},document:{getElementById:()=>null},setTimeout,clearTimeout,CustomEvent:class{}};
 vm.runInNewContext(source,context);
 return window.BluPreview;
}
test('language is chosen once and persists across reloads',()=>{
 const storage={};const preview=load(storage),state={user:'Test',language:'en'};
 preview.handle('choose-language',{dataset:{language:'ta'}},state,()=>{},()=>{});
 preview.handle('finish-intro',{},state,()=>{},()=>{});
 assert.equal(state.language,'ta');assert.equal(preview.needsIntro(),false);
 preview.handle('choose-language',{dataset:{language:'hi'}},state,()=>{},()=>{});
 assert.equal(preview.profile.language,'ta');
 const reloaded=load(storage);assert.equal(reloaded.profile.language,'ta');assert.equal(reloaded.needsIntro(),false);
 reloaded.handle('replay-intro',{},state,()=>{},()=>{});assert.equal(reloaded.needsIntro(),false);
});
test('cannot finish language selection without an installed local voice',()=>{
 const preview=load(),state={user:'Test'};let message='';
 preview.handle('choose-language',{dataset:{language:'or'}},state,()=>{},()=>{});
 preview.handle('finish-intro',{},state,()=>{},text=>message=text);
 assert.equal(preview.needsIntro(),true);assert.match(message,/local voice/);
});
test('onboarding exposes the requested five Indian languages',()=>{
 const codes=load().languages.map(l=>l[0]);
 for(const code of ['hi','ta','te','bn','mr'])assert.ok(codes.includes(code));
});

