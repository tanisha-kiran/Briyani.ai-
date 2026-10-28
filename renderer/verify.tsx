import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {Resvg} from '@resvg/resvg-js';
import assert from 'node:assert/strict';
import {mkdirSync,writeFileSync,readdirSync} from 'node:fs';
import {SceneFrame} from './SceneFrame';
const visual={keywords:['Understand an idea','Follow an example'],nodes:[{id:'a',label:'Input'},{id:'b',label:'Transformation'},{id:'c',label:'Output'}],edges:[{source:'a',target:'b',label:'process'},{source:'b',target:'c',label:'result'}],code:'for value in range(3):\n    print(value)',highlightLines:[1,2],points:[{label:'A',value:2},{label:'B',value:5},{label:'C',value:3}],xLabel:'Illustrative categories',yLabel:'Illustrative values',items:[{date:'Step 1',text:'Define the problem'},{date:'Step 2',text:'Explore the evidence'},{date:'Step 3',text:'Explain the result'}],leftTitle:'First approach',rightTitle:'Second approach',rows:[{label:'Focus',left:'One concept',right:'Another concept'},{label:'Use',left:'An example',right:'A comparison'}]};
mkdirSync('output/template-checks',{recursive:true});
for(const [index,type] of ['title_card','labeled_diagram','code_walkthrough','flow_diagram','graph_animation','timeline','comparison'].entries()){
 const scene={id:type,type,heading:'A visual explanation',visual};
 const svg=renderToStaticMarkup(<SceneFrame scene={scene} time={5} duration={10} index={index} total={7} caption="This is a renderer verification fixture, not generated lesson content."/>);
 const start=renderToStaticMarkup(<SceneFrame scene={scene} time={0} duration={10} index={index} total={7}/>);
 assert.notEqual(svg,start);assert.ok(svg.includes('viewBox="0 0 1280 720"'));assert.ok(!svg.includes('undefined'));
 const png=new Resvg(svg,{font:{loadSystemFonts:false,fontFiles:['C:/Windows/Fonts/segoeui.ttf','C:/Windows/Fonts/consola.ttf',...readdirSync('fonts').filter(f=>f.endsWith('.ttf')).map(f=>'fonts/'+f)]}}).render().asPng();assert.ok(png.length>10000);writeFileSync(`output/template-checks/${type}.png`,png);
}
const escaped=renderToStaticMarkup(<SceneFrame scene={{id:'x',type:'code_walkthrough',heading:'Escape check',visual:{...visual,code:'<script>alert(1)</script>'}}} time={1} duration={2} index={0} total={1}/>);
assert.ok(!escaped.includes('<script>'));assert.ok(escaped.includes('&lt;script&gt;'));console.log('7 animated templates rendered; untrusted display code escaped.');
assert.ok(escaped.includes('<rect width="1280" height="720" fill="#0b1120"></rect>'));

for(const layout of ['cycle','branch','hub']){
 const v={...visual,layout};const scene={id:layout,type:'flow_diagram',heading:'Relationship layout: '+layout,visual:v};
 const svg=renderToStaticMarkup(<SceneFrame scene={scene} time={6} duration={10} index={0} total={1}/>);assert.ok(!svg.includes('NaN'));writeFileSync(`output/template-checks/layout-${layout}.png`,new Resvg(svg).render().asPng());
}
for(const motion of ['orbit','collision','diffusion','pendulum','wave','transfer']){
 const v={...visual,motion,shape:'sphere',nodes:[{id:'a',label:'First concept'},{id:'b',label:'Second concept'}]};const scene={id:motion,type:'animated_illustration',heading:'Motion: '+motion,visual:v};
 const a=renderToStaticMarkup(<SceneFrame scene={scene} time={1} duration={10} index={0} total={1}/>),b=renderToStaticMarkup(<SceneFrame scene={scene} time={3} duration={10} index={0} total={1}/>);assert.notEqual(a,b);assert.ok(!a.includes('NaN'));writeFileSync(`output/template-checks/motion-${motion}.png`,new Resvg(a).render().asPng());
}
console.log('3 nonlinear layouts and 6 concept motions rendered with frame changes.');
