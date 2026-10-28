# BLU Companion Engine

Independent React + TypeScript + Vite companion module, with Tailwind CSS, layered SVG, Motion for React, React Context, and typed adapters. It contains **no video generation pipeline**.

## Two ways to inspect the work

- The parent `index.html` remains the no-install, direct-file visual prototype. Refresh it for onboarding, language selection, persistent preferences, post-lesson questions, language switching, retry limits and BLU reactions. Its CSS character and small compatibility facade are not the production SVG module.
- This folder is the requested modular React implementation. From this folder, when you choose to run it: `npm install`, then `npm run dev`. `npm run build` performs TypeScript checking and creates `dist/`. After dependencies are installed, the silent demo has no network requirements.

No dependency install, app execution, build, browser verification, or tests were performed. These are authored implementations, not verified production readiness.

## Architecture

`contracts/shared.ts` preserves **LanguageCode**, **BluEmotion**, **QuizQuestion**, and **LearningEvent** exactly. `CompanionAdapter` is the only route to quiz data, submissions, scene replay and status events. Components never import a video renderer. `SpeechAdapter` connects to the shared local TTS service; it does not implement another TTS engine.

- `components/BluCharacter.tsx`: independently animated SVG body, food/bowl, steam, eyes, eyebrows, mouth, arms, legs and ground shadow. The design follows the supplied blue body, biryani hat and little black limbs. Original art is an approximation of the reference, not a raster extraction.
- `animations/states.ts`, `transitions.ts`: the seven exact emotions and timed return-to-idle reactions. Happy has two jumps; celebration is finite. Motion reduction is respected.
- `animations/mouthSync.ts`: local audio RMS amplitude drives small/wide mouth shapes; sampling stops when paused, hidden or disposed. No fake speech animation in silent mode.
- `store/CompanionContext.tsx`: shared profile/language/mute state, event history, cancellable speech and reactions. Name and language persist in `blu.profile.v1` in browser storage.
- `components/BluWelcome.tsx`, `LanguageBoard.tsx`: entrance, greeting, saved name, language selection and transition toward the sidebar. Replay introduction is available.
- `components/BluSidebar.tsx`: separate from the lesson canvas; mobile layout occupies its own row. Personal dialogue is not displayed as persistent subtitles. Visible text reports operational status only.
- `components/QuizPanel.tsx`: validated adapter questions after completion, stable option IDs, translation invariant checks, preserved attempts/selection, English/selected-language toggle, bounded retries, scene replay and mastery unlock.
- `services/languages.ts`: all eleven requested languages, with curated text flags separate from tested voice/translation flags. **No voice or model translation is marked operational.** English, Hindi and Tamil have curated demo dialogue/question text only. Other choices show an explicit fallback.

## Independent demonstration

1. Choose a name and language on entry. Choose **Enter your learning space**.
2. Use **Simulate generation** to send requested/generating/ready events. The shown Python snippet is a static teaching reference, not a lesson renderer.
3. Click **Complete mock lesson**. This sends `lesson:completed`; only then does the quiz mount and emit `quiz:started`.
4. Try an incorrect answer, see the sad expression and explanation, then try the correct answer. BLU jumps twice. All questions must pass before the next-lesson unlock event.
5. Toggle question language; selection and attempts remain tied to IDs. On the third wrong attempt, answers lock. Request scene replay, review the reference and explicitly reset attempts. This is configurable with `MasteryPolicy`.
6. Inspect the event log. Test replay introduction, mute and saved preferences.

## Integrating a video engine

Construct the store with the real shared `SpeechAdapter`, and replace `DemoAdapter` with `HttpCompanionAdapter` or implement `CompanionAdapter` against the team's API. The host owns when a lesson completes and when the question panel mounts. Mount one `QuizPanel` per lesson, keyed by the lesson ID; mount it only after `lesson:completed`. Deliver events to `consume()` through one subscription and unsubscribe on teardown.

The supplied HTTP protocol expects:

| Request | Response |
| --- | --- |
| `GET /api/lessons/:id/quiz?language=en` | `QuizQuestion[]`, validated at runtime; return English questions if translation is unavailable |
| `POST /api/quiz/:questionId/answers` with `{optionId, language}` | `{correct: boolean, explanation: string}` |
| `POST /api/lessons/:lessonId/replay` with `{sceneId}` | JSON acknowledgement; host handles actual scene playback |
| `GET /api/events` | SSE messages containing a JSON `LearningEvent` |
| `POST /api/speech` with `{text, language}` | `{audioUrl: string}` served from the same local origin |

These are adapter expectations, **not implemented backend routes**. Adapt route names in the adapter if the video engine uses different routes; do not rename the shared contracts. SSE errors are recoverable and reported; EventSource owns reconnection. Malformed events, mismatched lesson IDs, invalid questions, duplicate IDs and translation changes to correct-answer IDs are rejected.

Create `LocalSpeechAdapter` with only languages whose local voices have been installed, licensed and verified. Its media URLs are restricted to the local application's origin. An explicit **Enable audio** action resumes AudioContext for browser autoplay policies. Muting, changing language, new events and teardown cancel obsolete speech. The default `SilentSpeechAdapter` never calls browser/cloud speech synthesis or fabricates audio.

## Manual acceptance checks (not executed)

1. Install and build this module. Resolve any compiler or browser errors before considering it integration-ready.
2. Clear `blu.profile.v1`, enter a name and Hindi, and complete onboarding. Reload: name/language should persist and onboarding should be skipped. Replay the introduction and check the selected language.
3. Verify all seven SVG states with reduced motion enabled and disabled. Confirm greeting enters from the edge, steam and blink are subtle, correct answers produce two hops, sad returns to idle, and celebration ends.
4. Complete the mock lesson, answer incorrectly, toggle English/Hindi, and confirm the same selected option ID and attempt count. Answer correctly and observe exactly one unlock event. Repeat using Tamil and an unsupported-language fallback.
5. Make three incorrect attempts and confirm no further answer submission is allowed until explicit scene review and reset. Test multiple questions via a custom adapter and confirm unlock waits for all of them.
6. Supply malformed question data, duplicate IDs, missing correct option, wrong lesson ID, and a translation with altered IDs. The panel must show an error rather than accepting it.
7. With a real local speech service: explicitly enable audio, hear the selected language, observe amplitude-driven mouth movement, mute mid-speech, switch language mid-speech and unmount. Confirm no stale audio or RAF sampling survives. Test blocked autoplay, failed media and unavailable voices.
8. Disconnect Wi-Fi after dependencies and local assets are available. Exercise the silent demo, then the separately installed speech adapter. Inspect network requests: no external AI, translation or speech request should occur.
9. Inspect at 360px, 768px and desktop widths. BLU must remain in a dedicated panel without covering lesson captions, controls or questions. Test keyboard focus and visible question text.
10. The direct-file compatibility preview should also retain correct answers and attempt counts on reload. This does not establish secure user accounts; its shared browser storage is demo data.

## Remaining verification and assets

Production acceptance remains pending runtime/visual verification, tested offline speech for English and two Indian languages, native-language review, font coverage, performance measurements and integration against the real backend. Runtime translation is intentionally absent here. The host video engine retains responsibility for video captions and synchronization.

No pretrained models, voices or external fonts are bundled. The SVG is newly authored from the user-provided reference. Confirm the supplied mascot artwork's usage rights before distribution. Dependency licenses must be captured from the versions actually installed; no lockfile exists because installation was not run. Secure authentication is outside this companion module.
