# Voicertool.com /subs/id — Algorithm Research Notes

## URLs Fetched (all 200 OK, no bot detection)

| URL | HTTP | Size | Type | Purpose |
|---|---|---|---|---|
| https://voicertool.com/subs/id | 200 | 132KB | text/html | Main page (PHP-rendered, has inline JS) |
| https://voicertool.com/setting.js?v=1.0.21 | 200 | 247KB | application/javascript | Obfuscated UI/voice-picker code (NOT the algorithm) |
| https://voicertool.com/srt.js?v=1.0.21 | 200 | 142KB | application/javascript | **Main algorithm** (TTS + atempo + mixing) — also obfuscated |
| https://voicertool.com/voices.json | 200 | 33KB | application/json | Voice list (300+ voices, lang→country→voices) |
| https://voicertool.com/jquery-3.7.1.min.js | 200 | 88KB | application/javascript | jQuery (for audio player UI) |

Site stack: **PHP** (PHPSESSID cookie), Cloudflare CDN, vanilla JS (no SPA framework), obfuscated via `javascript-obfuscator` (string array rotation + index shifting + parseInt comparison control-flow).

## Algorithm Summary (Decoded from srt.js)

### TTS Provider
- **Microsoft Edge TTS** (variable `EDGE_SPEECH_URL` confirmed in srt.js)
- Azure Speech SDK pattern: `context.synthesis.audio.metadataoptions + outputFormat`
- Output format: `audio-24khz-16bit-mono-pcm` (standard Edge TTS output)

### Per-Cue Processing Pipeline
For each SRT cue (cue has `.start`, `.end`, `.text`):

1. **Build SSML** via `prosodyTemplate(text, {pitch, rate, volume})` → `<prosody pitch="X%" rate="Y%" volume="Z%">text</prosody>` (omitted if slider = "0")
   - Wrap in `<voice name="...">` and `<speak version="1.0" xmlns="..." xml:lang="...">` via `speakTemplate`
2. **Call Edge TTS** with SSML → returns ArrayBuffer
3. **Decode** via `audioContext.decodeAudioData()` → AudioBuffer
4. **Trim silence** via `W(audioBuffer, headThreshold=0.01, tailThreshold=0.0036)`
   - Head threshold: `0.01` linear = **-40 dBFS** (aggressive)
   - Tail threshold: `0.0036` linear = **-48.87 dBFS** (gentler, preserves trailing consonants)
   - Asymmetric: head uses higher threshold, tail uses lower threshold
5. **Compute audio duration** (AFTER trim)
6. **Compute cue duration** = `cue.end - cue.start` (NO slack absorption into silent gaps)
7. **Compute atempo ratio** via `y(audioDur, cueDur)`:
   ```
   if speed_setting === "1":      // SPEED UP ONLY mode
     o = clamp(audioDur/cueDur, 1.0, 2.0)    // floor 1.0 (no slow down), cap 2.0 (max 2x speed up)
   else if speed_setting === "2": // SPEED UP AND SLOW DOWN mode
     o = clamp(audioDur/cueDur, 0.68, 2.0)   // floor 0.68 (max 1.47x slow down), cap 2.0 (max 2x speed up)
   else: o = 1;                              // default: no change
   ```
8. **Apply ffmpeg.wasm atempo** via `C(audioBuffer, ratio, chunkIdx)`:
   ```
   if ratio === 1: return audioBuffer  // no-op
   ffmpeg -f f32le -ar 24000 -ac 1 -i in_X.f32 -af atempo=<ratio.toFixed(3)> -f f32le out_X.f32
   ```
   - **Pitch preservation**: atempo preserves pitch automatically (built-in ffmpeg behavior)
   - **Precision**: 3 decimal places (e.g., `atempo=1.234`)
   - **Format**: f32le (32-bit float little-endian PCM), mono, 24000 Hz
9. **Wrap into final buffer** (minimum length = max(audio.length, ceil(audio.duration * 0.2)))
10. Return `{ audioBuffer: wrapped, offsetSeconds: cue.start }`

### Mixing (OfflineAudioContext)
```javascript
const sampleRate = audioContext.sampleRate;  // 24000 Hz
const totalDur = Math.max(...results.map(r => r.offsetSeconds + r.audioBuffer.duration));
const totalSamples = Math.max(totalDur * 0.2, sampleRate);
const offlineCtx = new OfflineAudioContext(1, totalSamples, sampleRate);
for (const { audioBuffer, offsetSeconds } of results) {
  const source = offlineCtx.createBufferSource();
  source.buffer = audioBuffer;
  source.connect(offlineCtx.destination);
  source.start(offsetSeconds);  // place at cue.start
}
const rendered = await offlineCtx.startRendering();
// Then encode as WAV (RIFF/WAVE/fmt/data header — manual writing)
```

### Key Design Choices
- **No slack absorption**: only cue.end - cue.start used for ratio. Adjacent silent gaps are NOT extended into.
- **No crossfade between cues**: each cue placed at cue.start as BufferSource. Overlap = additive mix (sum), no crossfade curve.
- **No audio normalization**: TTS amplitude preserved as-is. No peak normalize, no loudnorm, no compander.
- **No server-side rate change**: Edge TTS rate is always "0" (no SSML `<prosody rate="...">` override). All speed adjustment is client-side via `ffmpeg.wasm atempo`.
- **Pitch preservation via ffmpeg atempo** (not server-side TTS rate)
- **Audio I/O format**: f32le mono PCM at 24000 Hz (matches Edge TTS output)
- **Sequential processing**: cues are processed one at a time (not parallel), in batches of 1 (`O.slice(i, i+1)`)

### Output Formats
- MP3 (default) or WAV (selectable via `format_setting` dropdown)
- MP3 quality selectable via `mp3_audio_quality` dropdown
- WAV written manually with `setUint16/32/8` for RIFF/WAVE/fmt/data chunks
- Filename: `voicertool_audio_<voice>_<timestamp>_at_<time>_on_<date>.<ext>`

### UI Configuration (slider → SSML)
- Pitch slider: maps to `<prosody pitch="+X%">` (in %)
- Volume slider: maps to `<prosody volume="+X%">` (in %)
- **No rate slider**: SSML rate is always "0" (no override). Speed adjustment is purely client-side via ffmpeg.wasm atempo.
- Voice selection: 300+ voices, organized by language/country
- speed_setting dropdown: "Hanya percepat" (Speed up only) / "Percepat dan perlambat" (Speed up and slow down)
  - **NOTE**: speed_setting is read INSIDE srt.js (in the y() ratio function). The createAudio() function in index.html only passes {pitch, voice, volume} — speed_setting is read separately via DOM access inside srt.js.
  - `grep` for `speed_setting` in JS files returns 0 matches — the string must be obfuscated in the chunk array (we found the constants "1", "2", and 0.68 in the code that matches the speed_setting branches).

## Comparison to Our Current Implementation (src/lib/tts.ts narrateEntries)

| Feature | Voicertool | Our mode ON |
|---|---|---|
| **TTS provider** | Edge TTS (server-side via EDGE_SPEECH_URL) | Edge TTS (server-side via edge-tts.ts) ✓ Same |
| **SSML prosody** | `<prosody pitch="X%" rate="Y%" volume="Z%">` | Edge TTS `rate: "+X%"` via formatEdgeRate |
| **Speed adjustment mechanism** | `ffmpeg.wasm atempo` (client-side, pitch-preserving) | Server-side Edge TTS rate (pitch-preserving) |
| **Pitch preservation** | ffmpeg atempo (built-in) | Edge TTS server-side rate (built-in) |
| **Slack absorption** | NO — only cue.end - cue.start | NO — but availableDuration extends into next cue's slot ✓ Better than Voicertool |
| **Crossfade between cues** | NO — additive mix on overlap | YES — mixAudioInto with 15ms fade (Pattern C from VoiceStudio) ✓ Better than Voicertool |
| **Per-cue normalization** | NO — TTS amplitude as-is | YES — peakNormalize -2 dBFS (Pattern D from VoiceStudio) ✓ Better than Voicertool |
| **Silence trim before ratio** | YES — W() with -40dBFS head, -49dBFS tail (asymmetric) | YES — decodeMonoTrimResample with -30dBFS + 50ms padding (symmetric) |
| **Mode 1 (speedup only)** | `clamp(audioDur/cueDur, 1.0, 2.0)` | Re-generate via Edge TTS server rate, no clamp floor (always ≥1) |
| **Mode 2 (speedup+slowdown)** | `clamp(audioDur/cueDur, 0.68, 2.0)` | Edge TTS rate, MIN_SLOWDOWN_RATIO=0.7 (close to 0.68) |
| **Speed cap** | Max 2.0x (both modes) | audioRateCap=1.5 (Smart Fit), no explicit cap in ON mode |
| **Slowdown floor** | 0.68 (Mode 2 only) — about -32% rate | MIN_SLOWDOWN_RATIO=0.7 (close to 0.68) |
| **atempo precision** | 3 decimal places (`toFixed(3)`) | Edge TTS rate as "+/-X%" (integer percent) |
| **Audio format** | f32le PCM, mono, 24000 Hz (Edge TTS native) | Float32Array, mono, OUTPUT_SAMPLE_RATE (24000 Hz) |
| **Mixing strategy** | OfflineAudioContext with BufferSource.start(offsetSeconds) | Manual mixAudioInto (ADD with fade) |
| **Sequential vs parallel** | Sequential (batch=1) | Sequential (await per cue) |
| **Output** | WAV (manual header) or MP3 | WAV (via audio-utils) |
| **Empty cue handling** | Skipped | Cursor advances to entry.end (timing respected) |
| **Failure handling** | Try/catch per cue, fallback | Try/catch per cue, fallback message |
| **Pre-synthesis duration prediction** | NO — actual TTS first, then measure | NO — actual TTS first, then measure |

## Recommendations

### ADOPT from Voicertool:
1. **Explicit speed caps** — both upper (2.0) and lower (0.68) — make them configurable constants in `NarrationOptions`
   - Currently we have `MIN_SLOWDOWN_RATIO=0.7` hardcoded in narrateEntries
   - Add `MAX_SPEEDUP_RATIO=2.0` constant (currently implicit, only Smart Fit has `audioRateCap=1.5`)
2. **Asymmetric silence trim** — head trim more aggressive (-40dBFS) than tail trim (-49dBFS)
   - Currently `decodeMonoTrimResample` uses symmetric -30dBFS
   - VoiceStudio uses 50ms context-sensitive trim; we use -30dBFS + 50ms padding
   - Voicertool: head -40dBFS, tail -49dBFS — preserves trailing consonants better
3. **3-decimal atempo precision** — even if we use Edge TTS server rate, we can use 3-decimal float for ratio (currently `formatEdgeRate` rounds to integer %)
   - More precise fit when audio is just slightly off cue
   - Lower artifact rate vs integer rounding
4. **Server-side rate=0 default** — Voicertool sends `rate="0"` (no SSML rate override) and does ALL speed adjustment via client-side ffmpeg atempo
   - This decouples TTS generation from speed adjustment → can re-generate without re-synthesis
   - We currently re-generate Edge TTS for every speed change → 2x TTS cost
   - **Adopt**: use ffmpeg.wasm atempo for client-side speed adjustment (POST-TTS), avoid re-synthesis
   - **Trade-off**: adds ffmpeg.wasm dependency (~30MB initial download, but cached via Cache API)
5. **Sequential batching** — Voicertool processes one cue at a time (batch=1), not all in parallel
   - Edge TTS may rate-limit on concurrent requests
   - We already do sequential `await` per cue ✓
6. **Min buffer length floor** — `Math.max(audio.length, ceil(audio.duration * 0.2))` ensures buffer is at least 0.2s
   - Prevents zero-length buffers from breaking AudioContext operations

### SKIP from Voicertool (we already do better):
1. **No slack absorption** — Voicertool only uses `cue.end - cue.start`. We use `availableDuration = nextCueStart - cue.start` which extends into silent gaps naturally. **Keep our approach**.
2. **No crossfade between cues** — Voicertool uses additive mix only. We have 15ms fade in/out (Pattern C from VoiceStudio) to prevent pops/clicks. **Keep our approach**.
3. **No per-cue normalization** — Voicertool leaves TTS amplitude as-is. We peakNormalize to -2 dBFS (Pattern D from VoiceStudio) for consistent loudness. **Keep our approach**.
4. **No push-back / overflow handling** — Voicertool's OfflineAudioContext just sums overlapping audio. Our Dubbing Mode has slack absorption + push-back + gap chunks + fittedCues[] in retime-map.json v2.0. **Keep our approach**.
5. **ffmpeg.wasm dependency** — adds 30MB+ download (cached but heavy). Our server-side Edge TTS rate approach is lighter (no extra deps, pitch preserved in TTS server). Only adopt ffmpeg.wasm if we need atempo beyond what Edge rate supports (0.5x–2x for atempo vs ~0.7x–1.5x for Edge rate).

### WHY their approach differs:
- Voicertool is a generic tool for many languages (300+ voices, all via Edge TTS). They need a single algorithm that works for ALL voices — hence ffmpeg.wasm atempo (universal) vs Edge-specific rate (Edge-only).
- Our app is Mandarin→Indonesia focused on Edge TTS, so we can use Edge-specific server-side rate (lighter, no ffmpeg.wasm dependency).
- Trade-off: their approach handles ANY Edge voice the same way. Ours uses server-side rate which only Edge supports natively.

## Snippets Saved

All key algorithm snippets saved to `/home/z/my-project/upload/voicertool-research/snippets/`:

- `01_prosodyTemplate.js` — SSML `<prosody pitch rate volume>` builder
- `02_speakTemplate.js` — SSML `<speak><voice>` wrapper
- `03_speedSettingRatio_y.js` — function y() — speed_setting ratio computation (the algorithm)
- `04_silenceTrim_W.js` — function W() — silence trim with -40/-49 dBFS asymmetric thresholds
- `05_atempoApply_C.js` — async function C() — ffmpeg.wasm atempo application
- `06_perCueOrchestration_map.js` — the main per-cue map (TTS → trim → ratio → atempo → wrap)
- `07_mixing_OfflineAudioContext.js` — OfflineAudioContext mixing (BufferSource.start at cue.start)
- `08_wavWriter.js` — manual RIFF/WAVE header writer
- `09_getreplica_srtParser.js` — SRT parser (regex + time-to-ms)
- `10_edgeTtsUrl.js` — EDGE_SPEECH_URL variable context (confirms Edge TTS provider)

Raw files (full fetched content) saved alongside:
- `index.html` (132KB) — main page
- `setting.js` (247KB) — UI/voice-picker code (obfuscated)
- `srt.js` (142KB) — main algorithm code (obfuscated)
- `voices.json` (33KB) — voice catalog
- `m_tokens.txt`, `srt_tokens.txt` — deobfuscated string arrays (for keyword search)

## Reproducibility
- All fetches done via curl with User-Agent `Mozilla/5.0 ... Chrome/120` and Referer header
- No bot detection triggered (Cloudflare returned 200 with PHPSESSID)
- Files cached at `/home/z/my-project/upload/voicertool-research/`
- Snippets are human-readable with decoded algorithm in comments + raw obfuscated code below
