import { useEffect,useState } from 'react';
import { motion,useReducedMotion } from 'motion/react';
import { BluCharacter } from './BluCharacter';
import { LanguageBoard } from './LanguageBoard';
import { useCompanion } from '../store/CompanionContext';
import { dialogue } from '../services/languages';
export function BluWelcome(){const {profile,setProfile,react,emotion,amplitude,say,enableAudio,status}=useCompanion(),[leaving,setLeaving]=useState(false),reduced=useReducedMotion();
 useEffect(()=>{react('greeting');},[react]);
 function enter(){const phrase=dialogue(profile.language,'choice');void say(phrase.text,phrase.language,'greeting');setLeaving(true);}
 useEffect(()=>{if(!leaving)return;const timer=setTimeout(()=>setProfile(p=>({...p,introDone:true})),reduced?0:600);return()=>clearTimeout(timer)},[leaving,reduced,setProfile]);
 return <main className="welcome-page"><div className="brand">biryani<span>.ai</span><small>BLU COMPANION</small></div><div className="onboarding"><section><span className="eyebrow">YOUR CURIOSITY HAS COMPANY</span><h1>{profile.name?`Welcome back, ${profile.name}.`:'A little wonder.'}<br/><em>A whole new world.</em></h1><motion.div className="welcome-character" animate={leaving&&!reduced?{x:100,scale:.65,opacity:0}:{x:0,scale:1,opacity:1}} transition={{duration:.6}}><BluCharacter emotion={emotion} amplitude={amplitude}/></motion.div><p className="audio-status" role="status">{status}</p><button onClick={()=>{void enableAudio().then(()=>{const phrase=dialogue(profile.language,'greeting');void say(phrase.text,phrase.language,'greeting');});}}>Enable local audio / greet</button></section><section className="onboarding-card"><label className="name-label">What should BLU call you?<input maxLength={40} value={profile.name} placeholder="Your preferred name (optional)" onChange={e=>setProfile(p=>({...p,name:e.target.value}))}/></label><LanguageBoard value={profile.language} onChange={language=>setProfile(p=>({...p,language}))}/><button className="primary w-full" onClick={enter} disabled={leaving}>Enter your learning space →</button><p className="fine">Name and language stay in this browser. This is a companion demo, not an account login.</p></section></div></main>;
}
