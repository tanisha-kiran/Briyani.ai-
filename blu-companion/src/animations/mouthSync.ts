/** Sampling stops when audio stops or the document becomes hidden. No idle RAF loop. */
export function attachMouthSync(context:AudioContext,audio:HTMLAudioElement,onValue:(value:number)=>void){
 const source=context.createMediaElementSource(audio),analyser=context.createAnalyser();analyser.fftSize=256;source.connect(analyser);analyser.connect(context.destination);
 const data=new Uint8Array(analyser.fftSize);let frame=0;
 const sample=()=>{if(audio.paused||audio.ended||document.hidden){onValue(0);return;}analyser.getByteTimeDomainData(data);let power=0;for(const n of data)power+=((n-128)/128)**2;onValue(Math.min(1,Math.sqrt(power/data.length)*5));frame=requestAnimationFrame(sample);};
 const start=()=>{cancelAnimationFrame(frame);sample();};const stop=()=>{cancelAnimationFrame(frame);onValue(0);};const visibility=()=>document.hidden?stop():start();
 audio.addEventListener('play',start);audio.addEventListener('pause',stop);document.addEventListener('visibilitychange',visibility);
 return()=>{stop();source.disconnect();analyser.disconnect();audio.removeEventListener('play',start);audio.removeEventListener('pause',stop);document.removeEventListener('visibilitychange',visibility);};
}
