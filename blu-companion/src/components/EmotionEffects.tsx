import { motion,useReducedMotion } from 'motion/react';
import type { BluEmotion } from '../contracts/shared';
export function EmotionEffects({emotion}:{emotion:BluEmotion}){const reduced=useReducedMotion();if(!['happy','celebrating'].includes(emotion)||reduced)return null;return <g aria-hidden="true">{Array.from({length:12},(_,i)=><motion.rect key={i} x={52+i*18} y={90+(i%3)*10} width="5" height="9" rx="1" fill={['#9bdcff','#f8c579','#8bd9ba'][i%3]} initial={{opacity:0,y:0}} animate={{opacity:[0,1,0],y:[0,-35,55],rotate:[0,i%2?110:-110]}} transition={{duration:1.6,delay:(i%3)*.08}}/>)}</g>}
