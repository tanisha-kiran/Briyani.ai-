export type LanguageCode = 'en' | 'kn' | 'hi' | 'te' | 'ta' | 'ml' | 'mr' | 'bn' | 'gu' | 'pa' | 'or';
export type BluEmotion = 'idle' | 'greeting' | 'talking' | 'happy' | 'sad' | 'thinking' | 'celebrating';
export interface QuizQuestion {
  id: string; lessonId: string; sceneId: string; language: LanguageCode;
  question: string; options: { id: string; text: string }[];
  correctOptionId: string; explanation: string; misconceptionTag?: string;
}
export type LearningEvent =
  | { type: 'lesson:requested'; topic: string }
  | { type: 'lesson:generating'; lessonId: string }
  | { type: 'lesson:ready'; lessonId: string }
  | { type: 'lesson:started'; lessonId: string }
  | { type: 'lesson:completed'; lessonId: string }
  | { type: 'quiz:started'; lessonId: string }
  | { type: 'quiz:correct'; questionId: string }
  | { type: 'quiz:incorrect'; questionId: string }
  | { type: 'lesson:unlocked'; lessonId: string }
  | { type: 'system:error'; message: string };
export interface AnswerResult { correct: boolean; explanation: string }
export interface CompanionAdapter {
  fetchQuiz(lessonId: string, language: LanguageCode, signal?: AbortSignal): Promise<QuizQuestion[]>;
  submitAnswer(questionId: string, optionId: string, language: LanguageCode, signal?: AbortSignal): Promise<AnswerResult>;
  replayScene(lessonId: string, sceneId: string): Promise<void>;
  subscribe(listener: (event: LearningEvent) => void): () => void;
}
export interface SpeechAdapter {
  available(language: LanguageCode): boolean;
  play(text: string, language: LanguageCode, onAmplitude: (value: number) => void, signal: AbortSignal): Promise<void>;
  unlock(): Promise<void>;
}
