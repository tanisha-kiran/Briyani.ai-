# BLU preview v3 — voice and motion review

Open http://127.0.0.1:53841/ and refresh the tab. This design is a preview and is not locked.

## Try it

1. Beside the question bar, choose **Online natural female/male** or **Local neural voice**. Select British or American for English. Click **Hear voice** to audition the current language. Regional languages use their own native-language voice; the English accent control does not change them.
2. Click **Sit & snack**, **Cheer**, and **Try again** in BLU's panel. During real generation, BLU travels from the panel to the right edge of the question bar, shrinks, and performs one short eating motion. Correct quiz answers trigger a cheer; wrong answers show an encouraging retry bubble. Motion respects reduced-motion preferences.
3. Open **My lessons → Reviewed animation preview: pendulum motion**. This reviewed example demonstrates an animated illustration, a cycle diagram, neural narration, and captions. It is clearly labeled as a reviewed preview.
4. Existing videos retain their original audio. Open **Audio refinery** to rebuild any saved lesson using a new voice.

## Speech

- English: local Kokoro British/American neural voices, or online Microsoft English voices.
- Hindi: local Kokoro Hindi, or online native Hindi voices.
- Kannada, Tamil, Telugu, Malayalam, Marathi, Bengali, Gujarati: downloaded, language-specific local MMS neural models and online native voices.
- Punjabi and Odia: downloaded local native MMS voices. They are absent from the current online voice inventory, so the UI selects local mode explicitly.
- Online mode sends narration text to Microsoft through edge-tts 7.3.1. Planning, graphics, video encoding and stored lessons remain local. Local mode makes no speech-network requests once models are installed.
- No silent fallback to the old robotic synthesizer. The legacy basic voice exists only for compatibility with old requests, and is removed from UI choices.
- Regional MMS models provide one learned speaker per language. Male/female alternates apply to English/Hindi locally; online choices use distinct speakers.
- Samples are in `../Voice-Previews`. Speech quality is subjective; listen to English and Kannada in both modes before choosing your default. Successful synthesis is not a native-speaker pronunciation audit.

## Visuals

BLU uses a transparent raster pose atlas adapted from the supplied reference, displayed as a flat plane in Three.js. Three.js supplies perspective tilt, bob, bounce, movement and scaling; it does not replace the character with a different 3D model. The six authored poses are idle, happy, sad, seated eating, wave and thinking. This is pose-based motion, not skeletal arm animation or phoneme lip-sync.

The renderer supports linear, cycle, branching and hub layouts, with moving flow markers. It also supports simple pendulum, orbit, collision, diffusion, wave and transfer illustrations. The planner chooses a supported motion based on the narration; it does not invent arbitrary 3D scenes. Illustrations are explicitly labeled as simplified and are not quantitative simulations. Model failures now report an error rather than substituting an unrelated lesson.

## Validation

- 30 Python tests pass; app build passes.
- Original seven renderer templates, three nonlinear diagram layouts and six illustration motions render successfully.
- Browser checks: actor relocation and shrink, seated pose, actual quiz incorrect→sad and correct→happy, native Kannada preview HTTP 200, audio refinery preview, no JavaScript errors, no horizontal overflow at 390 px.
- Reviewed 36.5-second preview: playable H.264 1280×720 with AAC, NVENC encoding. Actual generated lesson also completed with the new animation renderer; its QA artifact is retained outside the visible library.
- Local speech synthesized successfully in all eleven languages. Online English (British/American) and Kannada generated valid audio; configured online names were checked against the live inventory.
- Local inference/encoding GPU behavior remains as before: Ollama on RTX 4050 and FFmpeg NVENC. Speech inference is CPU; downloaded native models are loaded one language at a time.

## Setup and sources

The installed app folder includes dependencies and downloaded voice weights. The source ZIP excludes dependencies, voice/model weights, caches and generated videos. Run SETUP-WINDOWS.cmd and SETUP-NATIVE-VOICES.cmd to prepare a separate installation; Kokoro and Ollama assets still need the setup described in README.md.

- [Kokoro ONNX](https://github.com/thewh1teagle/kokoro-onnx)
- [Microsoft speech client: edge-tts](https://github.com/rany2/edge-tts)
- [Meta MMS Kannada model card](https://huggingface.co/facebook/mms-tts-kan): MMS models are CC BY-NC 4.0. These local regional models are suitable for this noncommercial prototype; a commercial release needs a compatible voice model/license. Each downloaded language folder contains its source model card.
- Generated BLU artwork: built-in image generation, using the attached reference. The exact asset prompt is in BLU-ASSET-PROMPT.md.

Generated lesson facts still require review. The local 3B planner can make factual or visual-selection mistakes. The reviewed preview is not a guarantee of arbitrary-topic accuracy.
