> Historical document from the supplied archive. For the repaired 2D implementation and current checks, see README.md and docs/VALIDATION-UPDATED.md.

# Validation notes — 27 October 2026

## Observed working

- Existing `biryani-planner:latest` found in Ollama, digest `6fcef6e05f08b338bf1bd2fdc7d940308244ac65281dfc607d4e4f555d1d78a8`. No planner was downloaded, recreated or replaced.
- `npm run build`: local React/SVG exporter built and TypeScript check passed.
- Python tests: 16 passing checks for normalization, strict fields, valid references, plain narration, unique headings, bounded code highlights and measured-audio caption coverage.
- Motion tests: 3 passing checks for head-to-lap placement, spoon phase/cycle continuity and bite/food timing.
- All 7 SVG templates rendered at 1280×720. Executable-looking display code was escaped as text. Representative flow and comparison images inspected; connector endpoints and long-label sizing corrected.
- Python-loop lesson exported as an actual 46.396508-second H.264/AAC MP4. FFprobe confirmed 1280×720, yuv420p. WAV narration contains nonzero audio, not placeholder silence.
- Apple-browning lesson exported as a second actual 53.696463-second H.264/AAC MP4 with three distinct scenes and a generated quiz. Both exports use recovered, model-generated plans after validation fixes.
- MP4 played in the in-app browser: readyState 4, advancing currentTime, 1280×720 decoded dimensions, no media error. Scene seeking worked.
- Quiz unlocked after the video ended. Wrong-answer explanation, correct-answer feedback, related-scene replay and generated follow-up controls checked in the UI.
- Completed lesson cache survived a service restart. Repeating its request returned the same completed job with cached=true. Video byte-range request returned 206 and exactly the requested 1024 bytes.
- Desktop 1440×900 and narrow 390×844 layouts inspected. BLU docks in the right panel on desktop and above the conversation on narrow screens.
- BLU was visually observed with bowl on lap during real rendering, and back in the dock after completion. Its canvas stays noninteractive. Browser console was clear during normal playback checks.
- Greeting classification tested against the actual model: Hi returned conversation with no lesson. The first successful cold classification took about 7 seconds on CPU.
- Missing Kannada voice rejected immediately with HTTP 422 and a specific installation/English-choice message; no English substitute job was created.

## Integration evidence

`output/verification/results.json` records the six requested prompt checks. `passed` means the intent and structured plan validated; it is **not** a factual-quality score. Reruns reuse saved drafts, so near-zero elapsed values are validation times for cached drafts, not cold model benchmarks. Raw failed attempts are retained alongside accepted plans for diagnosis.

All six inputs produced accepted structured results after normalization fixes: Hi, What is Python?, Why do apples turn brown?, How do neural networks learn?, Who was Alan Turing?, and Compare Python and Java. Recovery covered self-labeled year endpoints, template names used as scene references, and incomplete narration tails. Opaque missing references and ambiguous mappings remain errors. These results do not establish six clean first-attempt generations or factual correctness.

Generated media and full FFprobe reports are under `output/lessons/`. During development, failed drafts were recovered after validation/renderer fixes. This exercises recovery; it must not be presented as six clean cold end-to-end exports.

## Remaining acceptance work

- Install and verify Hindi, Kannada and other desired local voices, including corresponding renderer fonts. Only local English voices are operational on this computer.
- Factual and pedagogical review of generated explanations, graph values and quiz grounding. The small model can still produce shallow or inaccurate explanations; validation cannot prove facts.
- Physical Wi-Fi-off acceptance on the target computer, memory measurements on 8 GB hardware, and repeated cold performance benchmarks. The network adapter was not changed during development.
- Caption timing uses proportional phrases within measured audio, not phoneme-level or word-level forced alignment.
- Exact target duration is not guaranteed; the actual video length follows synthesized narration and is displayed in the player.
- Local profiles are not production authentication. Packaging, distribution licenses and multi-user isolation require separate work before a public release.
