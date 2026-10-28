# Validation of the repaired application

Tested on 27 October 2026 on Windows with NVIDIA GeForce RTX 4050 Laptop GPU, 6 GB VRAM, and approximately 16 GB system RAM.

## Passed

- Application build and TypeScript check.
- 23 Python tests: planner normalization, invalid data rejection, caption boundaries, fallback labeling, refinement input validation, and safe audio-file paths.
- Seven animated renderer templates render successfully; display code is escaped.
- The supplied planner was registered locally using the existing identical Qwen2.5 3B model weights. Ollama reported 100% GPU, context length 8192.
- An actual new English Python-loop request completed planning, narration, animation and MP4 export through the HTTP API.
- English, Hindi and Tamil reviewed demonstrations exported as H.264 1280×720, 20 fps, AAC 48 kHz, with non-silent audio, embedded captions and WebVTT files.
- NVENC capability probe selected h264_nvenc. A separate real CPU-only short export selected libx264 and completed successfully.
- Scene durations follow WAV measurements; final demonstration videos differ from summed scene durations by less than 0.03 seconds.
- Final Hindi/Tamil video frames visually inspected. Fixed missing fonts and overlapping script shaping by bundling Noto fonts and using Skia for script text.
- All 11 listed language codes synthesized non-empty WAV files successfully. These are synthesis checks, not native-speaker pronunciation reviews.
- Chrome browser test: onboarding, lesson library, 720p video metadata and playback, Audio refinery opening, narration editing, voice preview, speed selection and rebuild submission. No JavaScript page errors. Video reached readyState 4 and decoded frames.
- Audio-refinement job completed. Edited narration was applied, original lesson preserved and scene visual configurations remained identical.
- Mobile viewport width 390: no horizontal document overflow.

## Demonstrations

- English Python loops: approximately 40 seconds.
- Hindi Python loops: approximately 41 seconds.
- Tamil Python loops: approximately 49 seconds.

These are reviewed demonstrations, not claims of arbitrary-topic generation. A separately generated English lesson is retained in the app library.

## Practical limits

Fast voices are synthetic. Optional neural English/Hindi speech works locally on CPU but is much slower on this laptop. The experimental DirectML speech path failed a convolution operation and was removed; GPU acceleration is used for the planner and H.264 encoding. CPU-only model inference is supported in code but a full CPU-only LLM lesson was not timed. CPU export was tested.

English neural voices are British, not Indian-accent voices. No fluent-speaker audit of all translations or pronunciations was performed. The small LLM's factual quality varies; structural validation cannot guarantee factual correctness. Captions use approximate phrase timing. Audio refinement rerenders the video and reuses cached unchanged speech; it is not a frame-level editing system. Wi-Fi-off operation was not physically tested, although inference, synthesis and rendering use local files and localhost endpoints.

The native computer-use browser check stopped because it could not establish the browser URL reliably. Subsequent application-owned Chrome automation tests succeeded; no Windows security or browser permission settings were changed.

Evidence: `output/export-validation.json`, `output/voice-checks.json`, each lesson's `probe.json`, `encoder.json`, `lesson.json`, and the UI screenshots under `output/`.
