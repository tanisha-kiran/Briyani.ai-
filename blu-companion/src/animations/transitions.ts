import type { BluEmotion, LearningEvent } from '../contracts/shared';
export function emotionForEvent(event:LearningEvent):BluEmotion {
 switch(event.type){case 'lesson:requested':case 'lesson:generating':return 'thinking';case 'quiz:started':return 'thinking';case 'quiz:correct':return 'happy';case 'quiz:incorrect':case 'system:error':return 'sad';case 'lesson:unlocked':return 'celebrating';default:return 'idle';}
}
