export const clamp=(x,min=0,max=1)=>Math.min(max,Math.max(min,x));
export const ease=x=>{x=clamp(x);return x*x*x*(x*(x*6-15)+10)};
export const mix=(a,b,t)=>a+(b-a)*t;
export function bowlPose(amount){const p=ease(amount);return {x:-.09*p-.72*Math.sin(Math.PI*p),y:mix(1.48,-.19,p)+.34*Math.sin(Math.PI*p),z:1.01*p,tilt:mix(-.10,.035,p)};}
export function spoonPose(seconds){
 const phase=((seconds%5.4)+5.4)%5.4;
 const scoop={x:-.10,y:.21,z:1.04},mouth={x:.055,y:.43,z:.78};
 let progress=0;
 if(phase<1.1)progress=0;
 else if(phase<2.5)progress=ease((phase-1.1)/1.4);
 else if(phase<3.15)progress=1;
 else progress=1-ease((phase-3.15)/2.25);
 return {x:mix(scoop.x,mouth.x,progress)+Math.sin(Math.PI*progress)*.19,y:mix(scoop.y,mouth.y,progress),z:mix(scoop.z,mouth.z,progress),bite:phase>=2.5&&phase<3.15,grain:phase<2.5?1:1-ease((phase-2.5)/.35),progress};
}
