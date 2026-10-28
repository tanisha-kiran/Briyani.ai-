import type { LanguageCode, SpeechAdapter } from '../contracts/shared';
import { attachMouthSync } from '../animations/mouthSync';
/** Silent by design. No synthetic voice and no fake amplitude. */
export class SilentSpeechAdapter implements SpeechAdapter {
 available(){return false;} async unlock(){} async play(){throw new Error('Offline speech is not connected. This demo is silent.');}
}
/** Connect to ONE shared local TTS service. Call only with verified supported voices. */
export class LocalSpeechAdapter implements SpeechAdapter {
 private context:AudioContext|null=null;
 constructor(private supported:ReadonlySet<LanguageCode>,private endpoint='/api/speech'){}
 available(language:LanguageCode){return this.supported.has(language);}
 async unlock(){this.context??=new AudioContext();await this.context.resume();}
 async play(text:string,language:LanguageCode,onAmplitude:(n:number)=>void,signal:AbortSignal){
  if(!this.available(language))throw new Error('No verified local voice for this language.');
  signal.throwIfAborted();await this.unlock();
  const response=await fetch(this.endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text,language}),signal});
  if(!response.ok)throw new Error('Local speech generation failed.');
  const data:unknown=await response.json();if(!data||typeof data!=='object'||!('audioUrl' in data)||typeof data.audioUrl!=='string')throw new Error('Speech response needs audioUrl.');
  const url=new URL(data.audioUrl,location.href);if(url.origin!==location.origin||!['http:','https:'].includes(url.protocol))throw new Error('Speech media must be served by the same local origin.');
  signal.throwIfAborted();const audio=new Audio(url.href);const detach=attachMouthSync(this.context!,audio,onAmplitude);
  try{await new Promise<void>((resolve,reject)=>{const cleanup=()=>{signal.removeEventListener('abort',abort);audio.onended=null;audio.onerror=null;};const abort=()=>{audio.pause();cleanup();reject(new DOMException('Aborted','AbortError'));};audio.onended=()=>{cleanup();resolve();};audio.onerror=()=>{cleanup();reject(new Error('Local audio playback failed.'));};signal.addEventListener('abort',abort,{once:true});if(signal.aborted){abort();return;}audio.play().catch(error=>{cleanup();reject(error);});});}
  finally{audio.pause();detach();audio.removeAttribute('src');audio.load();onAmplitude(0);}
 }
}
