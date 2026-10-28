import type { LanguageCode } from '../contracts/shared';
export interface LanguageCapability { code: LanguageCode; label: string; native: string; demoText: boolean; translationTested: boolean; voiceTested: boolean }
export const languages: LanguageCapability[] = [
 ['en','English','English'],['kn','Kannada','ಕನ್ನಡ'],['hi','Hindi','हिन्दी'],['te','Telugu','తెలుగు'],['ta','Tamil','தமிழ்'],['ml','Malayalam','മലയാളം'],['mr','Marathi','मराठी'],['bn','Bengali','বাংলা'],['gu','Gujarati','ગુજરાતી'],['pa','Punjabi','ਪੰਜਾਬੀ'],['or','Odia','ଓଡ଼ିଆ']
].map(([code,label,native]) => ({code:code as LanguageCode,label,native,demoText:['en','hi','ta'].includes(code),translationTested:false,voiceTested:false}));
export function isLanguage(value: unknown): value is LanguageCode { return languages.some(l=>l.code===value); }
export type DialogueKey = 'greeting' | 'choice' | 'correct' | 'incorrect' | 'unlocked';
const phrases: Record<'en'|'hi'|'ta',Record<DialogueKey,string>> = {
 en:{greeting:'Hi! I am BLU. What shall we discover today?',choice:'English it is. Let us explore together.',correct:'Great work! You understood that idea.',incorrect:'Not quite yet. Let us look at the explanation together.',unlocked:'Wonderful! Your next lesson is unlocked.'},
 hi:{greeting:'नमस्ते! मैं BLU हूँ। आज हम क्या सीखें?',choice:'हम हिन्दी में सीखेंगे। चलिए शुरू करें।',correct:'बहुत अच्छा! आपने यह समझ लिया।',incorrect:'अभी पूरी तरह सही नहीं है। चलिए फिर से समझते हैं।',unlocked:'बहुत बढ़िया! अगला पाठ खुल गया है।'},
 ta:{greeting:'வணக்கம்! நான் BLU. இன்று என்ன கற்கலாம்?',choice:'தமிழில் கற்கலாம். தொடங்குவோம்.',correct:'அருமை! நீங்கள் புரிந்துகொண்டீர்கள்.',incorrect:'இன்னும் சரியாகவில்லை. விளக்கத்தை மீண்டும் பார்க்கலாம்.',unlocked:'அருமை! அடுத்த பாடம் திறக்கப்பட்டது.'}
};
export function dialogue(language: LanguageCode, key: DialogueKey) { const supported=language==='hi'||language==='ta'?language:'en';return {text:phrases[supported][key],language:supported as LanguageCode,fallback:supported!==language}; }
