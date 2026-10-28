import {createCanvas,GlobalFonts} from '@napi-rs/canvas';
import {existsSync,readdirSync} from 'node:fs';
import {join} from 'node:path';
const fontDir=process.env.BIRYANI_FONT_DIR||join(process.cwd(),'fonts');
if(existsSync(fontDir))for(const file of readdirSync(fontDir).filter(f=>f.endsWith('.ttf')))GlobalFonts.registerFromPath(join(fontDir,file));
const cache=new Map<string,any>();
export function shapedText(text:string,width:number,size:number,fill:string,family:string,anchor:string){
 const key=JSON.stringify([text,width,size,fill,family,anchor]);if(cache.has(key))return cache.get(key);
 const measuring=createCanvas(1,1).getContext('2d');measuring.font=`${size}px "${family}"`;
 const rows:string[]=[];for(const paragraph of String(text).split('\n')){let row='';for(const word of paragraph.split(/\s+/)){if(row&&measuring.measureText(row+' '+word).width>width){rows.push(row);row=''}row+=(row?' ':'')+word}if(row)rows.push(row)}
 const w=Math.ceil(Math.min(width,Math.max(1,...rows.map(row=>measuring.measureText(row).width))))+12;
 const baseline=size*1.3+6,h=Math.ceil(baseline+Math.max(0,rows.length-1)*size*1.5+size*.6+6);
 const canvas=createCanvas(w*2,h*2),ctx=canvas.getContext('2d');ctx.scale(2,2);ctx.font=`${size}px "${family}"`;ctx.fillStyle=fill;ctx.textAlign=anchor==='middle'?'center':anchor==='end'?'right':'left';
 const x=anchor==='middle'?w/2:anchor==='end'?w-6:6;
 rows.forEach((row,i)=>ctx.fillText(row,x,baseline+i*size*1.5,width));
 const result={w,h,baseline,href:'data:image/png;base64,'+canvas.toBuffer('image/png').toString('base64')};cache.set(key,result);if(cache.size>600)cache.delete(cache.keys().next().value!);return result;
}
