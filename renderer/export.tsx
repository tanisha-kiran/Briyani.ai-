import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {Resvg} from '@resvg/resvg-js';
import {createCanvas,loadImage,GlobalFonts} from '@napi-rs/canvas';
import {readFileSync,writeFileSync,existsSync,readdirSync} from 'node:fs';
import {spawn,spawnSync} from 'node:child_process';
import {once} from 'node:events';
import {join} from 'node:path';
import {SceneFrame} from './SceneFrame';

const manifest=JSON.parse(readFileSync(process.argv[2],'utf8'));
// Loading every installed font for every frame is very expensive on Windows.
// These are OS-provided fonts; no font files are redistributed with the app.
const fontFiles=['segoeui.ttf','seguisb.ttf','consola.ttf','Nirmala.ttf','NirmalaB.ttf'].map(f=>join(process.env.WINDIR||'C:/Windows','Fonts',f)).filter(existsSync);
const fontOptions={loadSystemFonts:fontFiles.length===0,fontFiles,defaultFontFamily:'Segoe UI'};
for(const path of fontFiles)GlobalFonts.registerFromPath(path);
const canvas=createCanvas(1280,720),context=canvas.getContext('2d');
const overlayCanvas=createCanvas(1280,720),overlayContext=overlayCanvas.getContext('2d');
let fallbackFrames=0;const renderStarted=performance.now();
async function pixels(svg:string,background:any=null){
 if(background)svg=svg.replace('<rect width="1280" height="720" fill="#0b1120"></rect>','');
 context.clearRect(0,0,1280,720);
 if(background)context.drawImage(background,0,0,1280,720);
 overlayContext.clearRect(0,0,1280,720);
 try{const image=await loadImage(Buffer.from(svg));context.drawImage(image,0,0);const data=context.getImageData(0,0,1280,720).data;return Buffer.from(data.buffer,data.byteOffset,data.byteLength);}
 catch{fallbackFrames++;const image=await loadImage(new Resvg(svg,{font:fontOptions}).render().asPng());overlayContext.drawImage(image,0,0);context.drawImage(overlayCanvas,0,0);const data=context.getImageData(0,0,1280,720).data;return Buffer.from(data.buffer,data.byteOffset,data.byteLength);}
}
// Fifteen frames per second preserves the simple diagram motion while
// rendering 25% fewer full-HD frames on laptop hardware.
const fps=15, clips:string[]=[];
const gpuTest=manifest.cpuOnly?null:spawnSync(manifest.ffmpeg,['-hide_banner','-loglevel','error','-f','lavfi','-i','color=size=1280x720:rate=15','-frames:v','1','-c:v','h264_nvenc','-f','null','-'],{windowsHide:true,encoding:'utf8',timeout:15000});
const useGPU=gpuTest?.status===0;
const codec=useGPU?['-c:v','h264_nvenc','-preset','p4','-cq','23']:['-c:v','libx264','-preset','ultrafast','-crf','23'];
writeFileSync(join(manifest.output,'encoder.json'),JSON.stringify({encoder:useGPU?'h264_nvenc':'libx264',gpu:useGPU,reason:useGPU?'':gpuTest?.stderr||'CPU requested'}));
console.log(JSON.stringify({progress:45,message:useGPU?'NVIDIA GPU encoding enabled':'CPU encoding enabled'}));
for(let i=0;i<manifest.scenes.length;i++){
 const scene=manifest.scenes[i],file=join(manifest.output,`clip-${i}.mp4`);clips.push(file);
 const frames=Math.round(scene.duration*fps),duration=frames/fps;
 const ltxFrames=scene.ltxBackgroundFrames?await Promise.all(scene.ltxBackgroundFrames.map((path:string)=>loadImage(readFileSync(path)))):[];
 const encoder=spawn(manifest.ffmpeg,['-hide_banner','-loglevel','error','-y','-f','rawvideo','-pixel_format','rgba','-video_size','1280x720','-framerate',String(fps),'-i','pipe:0','-i',scene.audioPath,'-map','0:v:0','-map','1:a:0',...codec,'-pix_fmt','yuv420p','-c:a','aac','-ar','48000','-b:a','128k','-af','loudnorm=I=-16:TP=-2.5:LRA=11,apad','-t',String(duration),'-threads','2',file],{windowsHide:true});
 let error='';encoder.stderr.on('data',c=>error+=c);encoder.stdin.on('error',()=>{});
 const completion=new Promise<void>((resolve,reject)=>{encoder.on('error',reject);encoder.on('close',code=>code===0?resolve():reject(Error(error||'FFmpeg failed')))});completion.catch(()=>{});
 try{for(let f=0;f<frames;f++){if(encoder.exitCode!==null)throw Error(error||'Encoder exited');const t=f/fps;const caption=scene.captions.find((c:any)=>t>=c.start&&t<c.end)?.text||'';let svg=renderToStaticMarkup(<SceneFrame language={manifest.language} scene={scene} time={t} duration={duration} index={i} total={manifest.scenes.length} caption={caption}/>);const background=ltxFrames.length?ltxFrames[Math.floor(t*12)%ltxFrames.length]:null;if(background)svg=svg.replace('<rect width="1280" height="720" fill="#0b1120"/>','');const png=await pixels(svg,background);if(!encoder.stdin.write(png))await Promise.race([once(encoder.stdin,'drain'),completion.then(()=>{throw Error('Encoder closed before all frames were written')})]);if(f%40===0)console.log(JSON.stringify({progress:70+Math.round(25*(i+f/frames)/manifest.scenes.length),message:`Compositing scene ${i+1} of ${manifest.scenes.length}`}));}encoder.stdin.end();await completion;}catch(e){encoder.kill();throw e;}
}
writeFileSync(join(manifest.output,'concat.txt'),clips.map((_,i)=>`file 'clip-${i}.mp4'`).join('\n'));
const joined=spawnSync(manifest.ffmpeg,['-hide_banner','-loglevel','error','-y','-f','concat','-safe','1','-i',join(manifest.output,'concat.txt'),'-c','copy',...(manifest.targetDuration?['-t',String(manifest.targetDuration)]:[]),'-movflags','+faststart',join(manifest.output,'lesson.mp4')],{windowsHide:true,encoding:'utf8'});
if(joined.status!==0)throw Error(joined.stderr||'Final MP4 assembly failed');
console.log(JSON.stringify({progress:96,message:'Checking exported video and narration'}));

writeFileSync(join(manifest.output,'render-performance.json'),JSON.stringify({renderer:'Skia',fallbackFrames,seconds:(performance.now()-renderStarted)/1000,fps},null,2));
