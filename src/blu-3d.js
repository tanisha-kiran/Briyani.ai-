import * as THREE from '/vendor/three.module.js';
// Flat reference artwork on a Three.js plane: depth and motion without changing BLU's silhouette.
const canvas=document.createElement('canvas');canvas.className='blu-motion-canvas';canvas.setAttribute('aria-hidden','true');document.body.append(canvas);
const bubble=document.createElement('div');bubble.className='blu-speech-bubble';bubble.setAttribute('role','status');document.body.append(bubble);
let renderer;
try{renderer=new THREE.WebGLRenderer({canvas,alpha:true,antialias:true});}catch{canvas.remove();document.documentElement.classList.add('blu-no-webgl');}
const scene=new THREE.Scene(),camera=new THREE.OrthographicCamera(0,innerWidth,0,innerHeight,.1,2000);camera.position.z=1000;
const atlas=new THREE.TextureLoader().load('/public/blu/poses.png');atlas.colorSpace=THREE.SRGBColorSpace;atlas.repeat.set(1/3,1/2);atlas.minFilter=THREE.LinearFilter;atlas.magFilter=THREE.LinearFilter;
const material=new THREE.MeshBasicMaterial({map:atlas,transparent:true,depthWrite:false,side:THREE.DoubleSide});const actor=new THREE.Mesh(new THREE.PlaneGeometry(1,1),material);scene.add(actor);
let mood='idle',started=performance.now(),busy=false,mouth=0,first=true,last=performance.now(),x=0,y=0,size=220,previewTimer;
const poses={idle:0,happy:1,excited:1,sad:2,eating:3,wave:4,greeting:4,thinking:5,talking:4,speaking:4};
function pose(name){const cell=poses[name]??0;atlas.offset.set((cell%3)/3,cell<3?.5:0);}
function setEmotion(name){if(busy&&name!=='eating')return;mood=name;started=performance.now();pose(name);bubble.textContent=name==='happy'||name==='excited'?'Great job! That’s correct!':name==='sad'?'Not quite. Try again — you can do it!':'';bubble.hidden=!bubble.textContent;}
function beginCooking(){clearTimeout(previewTimer);busy=true;setEmotion('eating');document.body.classList.add('blu-seated');bubble.textContent='A little biryani while your lesson is prepared…';bubble.hidden=false;}
function endCooking(){clearTimeout(previewTimer);busy=false;document.body.classList.remove('blu-seated');setEmotion('idle');}
function target(){const host=document.querySelector(busy?'.composer form':'.companion .blu-3d-slot')||document.querySelector('.intro-stage .blu-3d-slot,.login-blu .blu-3d-slot');if(!host)return null;const r=host.getBoundingClientRect();if(!r.width||!r.height)return null;return busy?{x:r.right-66,y:r.top-20,s:118}:{x:r.left+r.width/2,y:r.top+r.height/2,s:Math.min(r.width,r.height,300)};}
function resize(){if(!renderer)return;renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.setSize(innerWidth,innerHeight);camera.right=innerWidth;camera.bottom=innerHeight;camera.updateProjectionMatrix();}
resize();addEventListener('resize',resize);
function frame(now){requestAnimationFrame(frame);if(!renderer)return;const t=target();actor.visible=!!t;canvas.hidden=!t;if(!t){bubble.hidden=true;return;}const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches||document.documentElement.dataset.motion==='off';const dt=Math.min(.05,(now-last)/1000);last=now;const ease=first||reduced?1:1-Math.exp(-dt*5);x+=(t.x-x)*ease;y+=(t.y-y)*ease;size+=(t.s-size)*ease;first=false;const elapsed=(now-started)/1000;
 let bounce=0,tilt=0,turn=0,squash=1;
 if(!reduced){if(mood==='happy'||mood==='excited'){bounce=elapsed<2.6?Math.abs(Math.sin(elapsed*7))*19:0;tilt=elapsed<2.6?Math.sin(elapsed*9)*.08:0;}
 else if(mood==='sad'){tilt=.07;bounce=-4;turn=-.08;}
 else if(mood==='eating'){const chewing=elapsed>1&&elapsed<4.6;tilt=chewing?Math.sin(elapsed*7)*.035:0;squash=chewing?1+Math.sin(elapsed*12)*.018:1;}
 else{bounce=Math.sin(now/900)*2;turn=Math.sin(now/1500)*.055;tilt=(mood==='wave'||mood==='greeting')?Math.sin(elapsed*6)*.045:0;squash+=mouth*.015;}}
 actor.position.set(x,y-bounce,0);actor.scale.set(size,-size*squash,1);actor.rotation.set(0,turn,tilt);renderer.render(scene,camera);
 bubble.style.left=Math.max(12,Math.min(innerWidth-250,x-115))+'px';bubble.style.top=Math.max(12,y-size*.52-48)+'px';
}
window.Blu3D={setEmotion,setMouth(v){mouth=v},beginCooking,endCooking,relocate(){},greet(){setEmotion('wave')},previewSnack(){clearTimeout(previewTimer);beginCooking();previewTimer=setTimeout(endCooking,7000)},get state(){return {mood,busy,x,y,size}}};
pose('idle');requestAnimationFrame(frame);

