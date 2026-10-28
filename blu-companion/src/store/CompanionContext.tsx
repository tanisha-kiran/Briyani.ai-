import { createContext,useContext,useState,useEffect,useRef,useCallback,type ReactNode } from 'react';
import type { BluEmotion,LanguageCode,LearningEvent,SpeechAdapter } from '../contracts/shared';
import { isLanguage } from '../services/languages';
import { emotionForEvent } from '../animations/transitions';
import { states } from '../animations/states';
interface Profile{name:string;language:LanguageCode;introDone:boolean;muted:boolean}
function readProfile():Profile{try{const p=JSON.parse(localStorage.getItem('blu.profile.v1')||'{}');return {name:typeof p.name==='string'?p.name.slice(0,40):'',language:isLanguage(p.language)?p.language:'en',introDone:p.introDone===true,muted:p.muted===true};}catch{return {name:'',language:'en',introDone:false,muted:false}}}
function useCompanionState(speech:SpeechAdapter){
 const [profile,setProfile]=useState(readProfile),[emotion,setEmotion]=useState<BluEmotion>('idle'),[amplitude,setAmplitude]=useState(0),[status,setStatus]=useState('Silent demo · local speech not connected'),[events,setEvents]=useState<LearningEvent[]>([]);
 const reaction=useRef<ReturnType<typeof setTimeout>|null>(null),controller=useRef<AbortController|null>(null),version=useRef(0);
 const cancel=useCallback(()=>{version.current++;controller.current?.abort();controller.current=null;setAmplitude(0);if(reaction.current)clearTimeout(reaction.current);},[]);
 const react=useCallback((next:BluEmotion)=>{cancel();setEmotion(next);if(states[next].duration)reaction.current=setTimeout(()=>setEmotion('idle'),states[next].duration);},[cancel]);
 const consume=useCallback((event:LearningEvent)=>{setEvents(old=>[event,...old].slice(0,12));react(emotionForEvent(event));if(event.type==='system:error')setStatus(event.message);},[react]);
 const say=useCallback(async(text:string,language:LanguageCode=profile.language,pose:BluEmotion='talking')=>{
  if(profile.muted){setStatus('Muted');return;}
  if(!speech.available(language)){setStatus('Silent demo · no verified offline voice');return;}
  cancel();const run=++version.current,abort=new AbortController();controller.current=abort;setEmotion(pose);setStatus('Playing local audio');
  try{await speech.play(text,language,setAmplitude,abort.signal);if(run===version.current){setStatus('Local audio finished');setEmotion('idle');}}
  catch(error){if(run===version.current&&!abort.signal.aborted){setStatus(error instanceof Error?error.message:'Audio failed. Tap Enable audio and retry.');setEmotion('idle');}}
 },[profile.language,profile.muted,speech,cancel]);
 useEffect(()=>{try{localStorage.setItem('blu.profile.v1',JSON.stringify(profile))}catch{setStatus('Profile storage is unavailable. Preferences last for this session.')}},[profile]);
 useEffect(()=>{cancel();setEmotion('idle');},[profile.language,profile.muted,cancel]);
 useEffect(()=>()=>{version.current++;controller.current?.abort();if(reaction.current)clearTimeout(reaction.current);},[]);
 return {profile,setProfile,emotion,amplitude,status,setStatus,events,react,consume,say,cancel,enableAudio:async()=>{try{await speech.unlock();setStatus(speech.available(profile.language)?'Local audio enabled':'Silent demo · voice service unavailable');}catch{setStatus('Audio could not start. Try another user interaction.');}}};
}
type Store=ReturnType<typeof useCompanionState>;
const Context=createContext<Store|null>(null);
export function CompanionProvider({children,speech}:{children:ReactNode;speech:SpeechAdapter}){const store=useCompanionState(speech);return <Context.Provider value={store}>{children}</Context.Provider>}
export function useCompanion(){const value=useContext(Context);if(!value)throw new Error('CompanionProvider is required.');return value;}
