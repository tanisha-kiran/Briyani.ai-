> Updated preview: see [voice and motion review](docs/PREVIEW-V3.md). The earlier baseline notes below describe the first repair; natural voices and optional online narration now replace the basic default.

# Biryani.ai — local GPU visual teacher

This repaired copy runs on this laptop. Your original ZIP files are unchanged.

## Open the app

Double-click `START-STUDIO.cmd`, then open http://127.0.0.1:53841/.
If the app is already running, open the URL directly. Keep the launcher open while using the app; Ctrl+C stops services started by it. An already-running Ollama service is reused.

The launcher uses the registered `biryani-planner` on port 11434. If it is unavailable, it can start an isolated Ollama instance on 11435 using the included `models` directory. The restored model is Qwen2.5 3B Q4_K_M from your archive. The original model configuration was registered using the already-installed identical base weights; no new foundation model was downloaded.

## Using the studio

1. Continue as a guest or enter a local display name.
2. Choose a language, beginner/intermediate level, and a 30/60/90-second target.
3. Ask a teaching question. The local model produces JSON; trusted components render it. Displayed model code is never executed.
4. Play the lesson, replay or jump to a scene, and download MP4 or the lesson plan.
5. Open **Audio refinery** below a completed video. Edit each scene's narration, preview it, choose speed/voice, and select **Refine audio & rebuild video**. This makes a new version and keeps the original lesson. It does not call the planner again.
6. **My lessons** restores completed lessons from local storage after reopening the app.

The included Python-loop demonstrations in English, Hindi, and Tamil are reviewed sample lessons, explicitly labeled as demonstrations. Planner failures use the labeled sample in those languages; they never silently present an unrelated sample as the requested answer.

## What changed

- Replaced the eating/WebGL character with a lightweight 2D SVG Blu holding a book.
- Replaced failing Windows System.Speech with bundled offline speech synthesis.
- Added fast narration in English, Hindi, Tamil, Telugu, Kannada, Malayalam, Marathi, Bengali, Gujarati, Punjabi, and Odia.
- Added Audio refinery, scene previews, speed controls, and optional neural English/Hindi male/female voices.
- Kept audio-first scene timing; added loudness normalization, AAC audio, burned-in captions and downloadable WebVTT.
- Added NVIDIA NVENC encoding with a real capability probe and CPU H.264 fallback.
- Matched lesson styling to the supplied references: navy background, teal accents, large headings, step diagrams, caption bar and progress.
- Bundled Noto fonts and used Skia text shaping for readable Indian-script captions. The SVG text path alone produced overlapping glyphs on this machine.
- Simplified the small model's output format and validated it before rendering. Review questions are grounded in actual scene narration.
- Improved startup, saved-lesson recovery, export error reporting, interrupted-job handling, and caption wrapping.

## Performance and limitations

The RTX 4050 Laptop GPU has 6 GB VRAM. Ollama was observed reporting **100% GPU** at an 8192-token context. MP4 exports were observed using **h264_nvenc**. SVG rasterization and speech use CPU; this avoids competing with the planner for VRAM. A CPU-only planning switch is available in Settings and disables NVENC for that lesson too.

**Fast offline** is the default voice because it is efficient and works across all listed languages. Its speech sounds synthetic. **Neural female/male** uses Kokoro for English and Hindi and is substantially slower on this laptop. Neural English uses British English voices, not an Indian-accent voice. For other languages, voice choice continues to use the basic local voice. Neural voice previews can take a minute or longer. Speech is cached by text, language, speed and voice; unchanged scene audio is reused.

Scene duration is measured from the actual WAV plus a short pause. The requested duration is a target, not an exact limit. Caption phrases are proportionally timed, not forced word alignment. Rebuilding audio rerenders the video while preserving scene content. Revoicing an existing lesson into another language is not implemented; select the language before generating a new lesson.

A 3B local model can still make factual or translation errors. Structural validation and specific reference checks do not prove every fact. Review narration before sharing. The application includes no external AI/translation/voice APIs. Downloads are needed for initial setup only; generation uses localhost and installed assets.

## Reinstall dependencies

This folder already contains working dependencies. For another Windows computer, install Python 3.12 and Node.js, keep the supplied model and voice assets, then run `SETUP-WINDOWS.cmd`. Do not use Python 3.15 for these pinned binary packages.

Run checks from this folder:

```
npm run build
npm run test:renderer
.venv\Scripts\python.exe -m pytest tests -q
```

`output/lessons/<id>/` contains the WAV files, captions, MP4, schema-validated plan, FFprobe report and encoder selection. `output/voice-checks.json` records synthesis checks for all 11 language codes. Local application logs are `node.exe.log` and `python.exe-error.log` when using the launcher.

## Licences and asset sources

- Supplied Qwen2.5 3B weights: Qwen Research License, preserved in the supplied model blob. This is not the Apache licence used by some other Qwen sizes. See https://huggingface.co/Qwen/Qwen2.5-3B-Instruct and the supplied licence.
- Kokoro model/voice pack: Apache 2.0, https://huggingface.co/hexgrad/Kokoro-82M. ONNX conversion/runtime: https://github.com/thewh1teagle/kokoro-onnx (MIT). Voices used: bf_emma, bm_george, hf_alpha, hm_omega.
- eSpeak NG: GPL v3 or later, https://github.com/espeak-ng/espeak-ng. Used locally through espeakng-loader; preserve its notices and source obligations if distributing binaries.
- Noto fonts: SIL Open Font License 1.1. Font-specific OFL files are included in `fonts/`.
- React: MIT. resvg: MPL 2.0. @napi-rs/canvas: MIT. FFmpeg binary comes from imageio-ffmpeg; its build/licence notices must be preserved when redistributing.
- Blu SVG is newly authored code based on the provided brand reference. Original user-provided assets remain in `public/`.

See `docs/VALIDATION-UPDATED.md` for checks and known limits of this repair.
