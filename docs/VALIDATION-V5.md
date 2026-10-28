# Validation on this laptop — 27 October 2026

The interface and Blu design remain a preview. This revision changes the lesson engine, speech, renderer and saved-video retrieval.

## Current configuration and checks

- RTX 4050 Laptop GPU, 6141 MiB VRAM; about 16 GB system RAM. Default planner: Qwen3 4B Instruct Q4_K_M, replacing the supplied Qwen2.5 3B. At 8192 context, Ollama reported about 3.8 GB GPU allocation. CPU mode uses 4096 context. These observations do not certify every 8 GB laptop.
- Current-model, complete CPU-only generation passed: 30.171-second video, 1280×720 H.264 + AAC, 3 scenes, Indian Piper narration, real code trace and output/stop comparison. Total 272.43 seconds: planning 227.24, narration 18.50, rendering 26.57. Ollama reported zero GPU allocation; FFmpeg used libx264. See output/cpu-full-validation-v5.json.
- Final fresh GPU run with the current Qwen3 model: 30.221-second lesson in 107.36 seconds (planning 61.51, narration 17.93, rendering 27.42). The planner needed one correction to fit the word budget. Encoder: h264_nvenc. The loop code/output were reviewed without editing the generated script. See output/gpu-full-validation-v5.json.
- Earlier Qwen3.5 4B trial produced the 43.571-second Improved-Loop-Lesson demo in 125.86 seconds (planning 72.08, narration 18.44, rendering 35.26). That timing is an earlier-model observation, not a benchmark for the final default. Its correct video remains available.
- Reviewed physics demonstration: 51.271 seconds, 4 scenes, British Piper voice, energy comparison, shrinking pendulum motion and branching energy-transfer diagram. Export took 109.12 seconds. This is a prepared, reviewed example, not an untouched AI answer.
- Reviewed Hindi demonstration: 52.471 seconds, local MMS Hindi speech, native headings/captions and localized code-trace labels. Narration and export took 183.95 seconds. The model's original Hindi draft was edited for clarity. English, Hindi and Tamil fallback videos are also packaged for fresh installations.
- Final saved-video checks returned equivalent questions in 27.42–34.88 ms round-trip and related candidates in 33.74 ms, without adding jobs. These are local API timings; browser media loading/decoding adds time. Exact matching preserves numeric signs and mathematical operators. Related suggestions require explicit selection.
- Browser playback verified 1280×720, a 30.171-second current-model video, exact reuse, related previews, no JavaScript errors, and no horizontal overflow at 390px.
- 58 Python regression tests passed, including incorrect pendulum claims, safe bounded AST traces, offline speech restrictions and cache mismatches. Three Blu motion tests passed; TypeScript and renderer build passed. One upstream Starlette/httpx deprecation warning remains.

## Limits that remain

The planner still makes factual errors. Manual review rejected a generated pendulum lesson that incorrectly described gravity as upward. That job was removed from eligible saved results, and a regression check now rejects that specific mistake. Structural and selected factual checks do not prove arbitrary-topic correctness. The unedited Hindi draft was also awkward; fluent translation across all ten Indian languages has not been established. Reviewed demonstrations must not be represented as unedited model outputs.

All runtime AI calls are local. Cloud narration is rejected in both API and UI. Initial setup requires downloads. The whole pipeline has not been tested with Wi-Fi physically disabled. Related retrieval uses lexical matching, not embeddings. Captions use approximate phrase timing within measured speech scenes. Novel questions can still take minutes, especially on CPU or with regional speech; saved playback bypasses generation.

See README for model licences, setup and the event-time eligibility condition in the supplied problem statement. Pre-event development is not a claim of competition eligibility.
