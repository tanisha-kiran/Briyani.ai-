import type { AnswerResult, CompanionAdapter, LanguageCode, LearningEvent, QuizQuestion } from '../contracts/shared';
import { isLanguage } from './languages';
function object(value: unknown): value is Record<string,unknown> { return !!value && typeof value==='object'; }
export function validateQuestion(value: unknown): QuizQuestion {
 if(!object(value)) throw new Error('Question must be an object.');
 for(const key of ['id','lessonId','sceneId','question','correctOptionId','explanation']) if(typeof value[key]!=='string'||!(value[key] as string).trim()) throw new Error(`Invalid question ${key}.`);
 if(!isLanguage(value.language)||!Array.isArray(value.options)||value.options.length<3||value.options.length>4) throw new Error('Invalid question language or option count.');
 const ids=new Set<string>();
 for(const option of value.options) { if(!object(option)||typeof option.id!=='string'||!option.id||typeof option.text!=='string'||!option.text.trim()||ids.has(option.id)) throw new Error('Invalid or duplicate answer option.');ids.add(option.id); }
 if(!ids.has(value.correctOptionId as string)) throw new Error('Correct option is missing.');
 if(value.misconceptionTag!==undefined&&typeof value.misconceptionTag!=='string')throw new Error('Invalid misconception tag.');
 return value as unknown as QuizQuestion;
}
export function validateTranslation(base: QuizQuestion, translated: QuizQuestion) {
 if(base.id!==translated.id||base.lessonId!==translated.lessonId||base.sceneId!==translated.sceneId||base.correctOptionId!==translated.correctOptionId||base.options.length!==translated.options.length||base.options.some(o=>!translated.options.some(t=>t.id===o.id)))throw new Error('Translation changed stable question or answer IDs.');
 return translated;
}
const base={id:'loops-q1',lessonId:'demo-loops',sceneId:'loops-iterations',correctOptionId:'zero-one-two'};
const questions: Record<string,QuizQuestion>={
 en:{...base,language:'en',question:'Which values does range(3) produce?',options:[{id:'one-two-three',text:'1, 2, 3'},{id:'zero-one-two',text:'0, 1, 2'},{id:'zero-through-three',text:'0, 1, 2, 3'}],explanation:'range(3) starts at 0 and stops before 3. It produces 0, 1, and 2.'},
 hi:{...base,language:'hi',question:'range(3) से कौन-से मान मिलते हैं?',options:[{id:'one-two-three',text:'1, 2, 3 — एक से तीन'},{id:'zero-one-two',text:'0, 1, 2 — शून्य से दो'},{id:'zero-through-three',text:'0, 1, 2, 3 — शून्य से तीन'}],explanation:'range(3) शून्य से शुरू होता है और 3 से पहले रुकता है। इसलिए मान 0, 1 और 2 हैं।'},
 ta:{...base,language:'ta',question:'range(3) எந்த மதிப்புகளைத் தருகிறது?',options:[{id:'one-two-three',text:'1, 2, 3 — ஒன்று முதல் மூன்று'},{id:'zero-one-two',text:'0, 1, 2 — பூஜ்ஜியம் முதல் இரண்டு'},{id:'zero-through-three',text:'0, 1, 2, 3 — பூஜ்ஜியம் முதல் மூன்று'}],explanation:'range(3) பூஜ்ஜியத்தில் தொடங்கி 3க்கு முன் நிற்கிறது. மதிப்புகள் 0, 1, 2 ஆகும்.'}
};
export class DemoAdapter implements CompanionAdapter {
 private listeners=new Set<(event:LearningEvent)=>void>();
 emit(event:LearningEvent){this.listeners.forEach(listener=>listener(event));}
 subscribe(listener:(event:LearningEvent)=>void){this.listeners.add(listener);return()=>{this.listeners.delete(listener);};}
 async fetchQuiz(lessonId:string,language:LanguageCode,signal?:AbortSignal){signal?.throwIfAborted();if(lessonId!==base.lessonId)throw new Error('No fixture for this lesson.');return [validateQuestion(structuredClone(questions[language]||questions.en))];}
 async submitAnswer(questionId:string,optionId:string,language:LanguageCode,signal?:AbortSignal):Promise<AnswerResult>{signal?.throwIfAborted();if(questionId!==base.id||!questions.en.options.some(o=>o.id===optionId))throw new Error('Unknown question or answer.');return {correct:optionId===base.correctOptionId,explanation:(questions[language]||questions.en).explanation};}
 async replayScene(lessonId:string,sceneId:string){if(lessonId!==base.lessonId||sceneId!==base.sceneId)throw new Error('Unknown replay scene.');this.emit({type:'lesson:started',lessonId});}
}
export function validateEvent(value:unknown):LearningEvent {
 if(!object(value)||typeof value.type!=='string')throw new Error('Invalid event.');
 const fields:Record<string,string>={'lesson:requested':'topic','lesson:generating':'lessonId','lesson:ready':'lessonId','lesson:started':'lessonId','lesson:completed':'lessonId','quiz:started':'lessonId','quiz:correct':'questionId','quiz:incorrect':'questionId','lesson:unlocked':'lessonId','system:error':'message'};
 const field=fields[value.type];if(!field||typeof value[field]!=='string'||!value[field])throw new Error('Invalid event payload.');return value as LearningEvent;
}
