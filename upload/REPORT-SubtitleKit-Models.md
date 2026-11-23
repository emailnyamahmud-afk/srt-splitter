# Riset Teknis subtitlekit.com — Model Klien (Browser) & Pemetaan ke TUI

Dokumen ini hasil bedah aset nyata situs (HTML Astro, chunk JavaScript, manifest
ONNX, dan file LICENSE yang diunduh langsung), bukan deskripsi permukaan halaman.
Tujuan: menjawab **model apa saja yang benar-benar berjalan di sisi klien
(browser)**, lisensinya apa saja yang boleh dipakai ulang secara lokal, dan
bagaimana logika setara diadopsi ke `srt2audio-tui` di MacBook.

Tanggal riset: 2026-11-23.

---

## 1. Jawaban singkat

Situs https://subtitlekit.com/ adalah proyek indie satu orang (Daniel Stoianov,
Kanada; halaman About: *“Just me, Daniel Stoianov … a one-person indie
project”*). Klaim privasinya **benar secara teknis**: semua inferensi dijalankan
di browser pengunjung dengan `onnxruntime-web` 1.27.0 (WASM/WebGPU); file tidak
diupload ke server sintesis. Model diunduh sekali lalu di-cache per-browser
(Cache API / IndexedDB).

Screenshot “Downloaded models” (±727 MB) cocok dengan angka byte di bundle:

| Kartu di modal | Model registry | Ukuran terukur |
|---|---|---|
| Speech recognition, Whisper large turbo — 540 MB | `whisper-turbo` | build WebGPU q4f16: **563,479,095 B (537,4 MiB)** → tampilan ±540 MB |
| Speaker labels, high accuracy — 79 MB | `speakers-nemotron` | data expanded 73,769,392 B (70,4 MiB); ONNX int8 8,636,534 B |
| Text to speech voices — 108 MB | `tts-supertonic` | build int8 `w8k` tersimpan 114,374,240 B (109,1 MiB; payload bobot 111,157,762 B) |
| **Total** | | **540 + 79 + 108 ≈ 727 MB** |

**Mesin narasi utama (alur Subtitles to Audio) untuk Bahasa Indonesia (`id`)
adalah `tts-supertonic`** — yaitu bobot **Supertone Supertonic 3**, TTS
flow-matching latent multilingual TTS ONNX, CPU-friendly (fp32 ≈398 MB;
int8 ≈111 MB payload). Bukan model rahasia: kode upstream berlisensi MIT,
bobot berlisensi BigScience Open RAIL-M, dan ada paket Python resmi
(`pip install supertonic`) — itulah dasar parity lokal di proyek ini.

---

## 2. Metode bukti (bukan asumsi)

Yang diunduh dan diperiksa:

1. HTML semua halaman tool (home, `subtitles-to-audio`, `text-to-speech`,
   `srt-to-audio`, `voice-clone`, `audio-to-text`, `about`) dengan User-Agent
   browser; daftar aset `/_astro/*.js` di-crawl dan diekstrak.
2. Manifest TTS langsung dari host:
   `https://models.subtitlekit.com/supertonic/3cadd1ee6394adea1bd021217a0e650ede09a323/onnx/tts.json`
   (HTTP 200, 8.253 B; `tts_version v1.7.3`, split `opensource-multilingual`).
3. File LICENSE aktif dari host model untuk Supertonic, Silero, dan MOSS.
4. Manifest MOSS `browser_poc_manifest.json` (503.354 B) dan `bundle.json`
   Pocket (24.975 B per bahasa).
5. Registry Whisper (repo HF + revisi pinned) dari chunk
   `chunk_models.BKn3GL3I.js`; tabel diarisasi dari `chunk_hosts.BBx7UX30.js`;
   tabel STT per-bahasa dari `chunk_lang-check-model.DPXnVv7h.js`; katalog
   engine TTS dan logika pemilihan bahasa dari
   `chunk_model-cache.Wv8qd2ac.js`, `chunk_models.DJMwcqwr.js`, dan
   `chunk_useRememberedDeviceVerdict.B75W7cmp.js`.

---

## 3. Runtime browser yang terbukti dari JS

- **Framework**: Astro; frontend React kecil; service worker COI
  (`coi-serviceworker.js` v0.1.7, MIT) mengisolasi crossOriginIsolated untuk
  WASM thread; komentar di sumbernya: Safari/WebKit tanpa dukungan credentialless
  isolation → WASM jalan single-core di Safari.
- **ML runtime**: `onnxruntime-web` **1.27.0**. Build binary:
  - `ort-wasm-simd-threaded[.mjs/.wasm]` — tier `std`.
  - plugin WebGPU `jsep` (~26,8 MB) + asyncify (~24,3 MB) + jspi (~15,0 MB).
  - Pemilihan tier (`chunk_download-size.CUh8SW7Q.js`):
    `supertonic` dan `stress-*` → `jsep` (WebGPU, fallback `std`);
    `silero`, `moss`, `pocket`, `hardsub` → `std`; Safari selalu `std`.
- **Host bobot** (`chunk_ort-hosts.BjVtGDMV.js`, `chunk_model-hosts.B9m8ktn1.js`):
  - utama R2: `https://models.subtitlekit.com`;
  - mirror ModelScope: `https://modelscope.cn/models/<repo>/resolve/main/...`;
  - mirror Yandex; jsdelivr untuk dist ORN (`cdn.jsdelivr.net/npm/onnxruntime-web@1.27.0/dist/`);
    same-origin `/ort/1.27.0/`;
  - routing negara: `cn → modelscope`, `ru → yandex`.
- **Persistensi**: Cache API + IndexedDB; embedding hasil voice-clone disimpan
  di IndexedDB database `subtitlekit-voices`, object store `pocket`
  (field `consentVersion:1`, `embedding: Float32Array`, `frames`).
- **Catatan ukuran**: file ONNX besar dipecah `.partN` (≈9,437,184 B/part)
  untuk unduhan paralel + recovery dengan hash SHA-256 per part.

---

## 4. Registry model lengkap (kunci UI → identitas & lisensi)

### 4.A. Mesin narasi TTS (tool Subtitles to Audio / Text to Speech)

#### (1) `tts-supertonic` — “Text to speech voices” — **narator utama**

- **Upstream**: Supertone Inc. — repo kode `supertone-inc/supertonic` (**MIT**),
  bobot `HF: Supertone/supertonic-3` (**BigScience Open RAIL-M**, 18 Agustus 2022),
  paket PyPI `supertonic` 1.3.x (depends: onnxruntime, numpy, soundfile,
  huggingface-hub). Repack int8 juga ada di sherpa-onnx
  (`sherpa-onnx-supertonic-3-tts-int8-2026-05-11`).
- **Path host**: `supertonic/3cadd1ee6394adea1bd021217a0e650ede09a323/`;
  build aktif `w8k-9fe3252d`; manifest `onnx/tts.json`; tokenizer teks
  `onnx/unicode_indexer.json` (277.676 B); bobot fp32 mentah tersedia dengan
  nama file yang sama persis di host.
- **Byte count build int8 w8k**:

| File | Byte |
|---|---:|
| `duration_predictor.onnx` | 3.700.147 |
| `text_encoder.onnx` (3 part) | 16.071.060 |
| `vector_estimator.onnx` (7 part) | 65.644.142 |
| `vocoder.onnx` (3 part) | 25.742.413 |
| Payload bobot | **111.157.762** |
| + shim runtime (`F`) | 3.216.478 |
| Tersimpan | **114.374.240 (109,1 MiB)** |

- **Build fp32**: text_encoder 36.416.150; vector_estimator 256.534.781;
  vocoder 101.424.195; predictor 3.700.147; total file ≈398.075.273 B;
  total manifest `h = 401.291.751 B` (≈382,7 MiB; unduhan pertama paket
  PyPI disebut ~400 MB).
- **Arsitektur dari `tts.json`** (flow-matching latent TTS):
  - latent dim 24; `chunk_compress_factor 6`; AE sampel 44.100 Hz, n_fft 2048,
    hop 512, n_mels 228, encoder/decoder 10 layer.
  - text encoder: char embedding 256 + ConvNeXt 6 layer (dilation 1,1,2,2,4,4)
    + attention encoder 4 heads × 4 layer.
  - style encoder: `n_style 50` prototipe (sumber 10 suara bawaan
    F1–F5/M1–M5), attention 2 heads.
  - vector field: 4 flow block, time + style + text conditioning.
  - duration predictor (`dp`): char convnext + attention 2 heads × 2 layer,
    `n_style 8`.
- **Bahasa**: 31 kode ISO upstream — `en ko ja ar bg cs da de el es et fi
  fr hi hr hu id it lt lv nl pl pt ro ru sk sl sv tr uk vi` + fallback `na`;
  situs menampilkan alias `jp`/`kr` yang dipetakan ke `ja`/`ko`. **`id`
  (Indonesia) didukung**.
- **Suara**: F1, F2, F3, F4, F5, M1, M2, M3, M4, M5; gaya UI mis. Bright,
  Deep · Unhurried, Bright · Brisk.
- **Lisensi**: kode MIT; bobot RAIL-M (boleh dipakai dan didistribusikan ulang
  dengan menyertakan lisensi, menandai modifikasi, dan mematuhi batas
  Attachment A — mis. tidak untuk manipulasi identitas tanpa izin,
  tidak untuk kegiatan berbahaya).

#### (2) `tts-silero` — “Text to speech voices, Silero” — opsi RU/CIS

- **Upstream**: `snakers4/silero-models`, build `v5_cis_base_nostress-0405777e-r2`
  (+ varian `-br`). **LICENSE file aktif di host = MIT** (1.076 B); catatan repo:
  model `base`/`base_nostress` CIS di bawah MIT, model `ext` di bawah
  CC-BY-NC-BY.
- **Path**: `silero-tts/v5_cis_base_nostress-0405777e-r2/`.
- **File (build penuh)**: meta 54.253 B; predictors.onnx 5.058.474 B;
  encoder.onnx 14.440.641 B; decoder_int8.onnx 27.895.740 B (total 47.449.108 B);
  wire/parts tersimpan 35.120.543 B (33,5 MiB).
- **Meta**: sample_rate 48.000, hop 600, n_fft 2400, **60 speaker**
  (`ru_*`, `ukr_*`, `bel_*`, `kaz_*`, `tat_*`, `bak_*`, `uzb_*`, `aze_*`,
  `hye_*`, `kat_*`, `kir_*`, `tgk_*`, `sah_*`, `udm_*`, `kbd_*`, `xal_*`,
  `kjh_*`, `mdf_*`, `myv_*`, `chv_*`, `erz_*`).
- Pendamping stres homofon: `silero-stress/1.5-parts`
  (`homo_fp32.onnx.part0..part4` ≈5,74 + 4,81 + 4,75 + 8,48 + 0,77 MB)
  untuk `stress-ru/uk/be`.
- Di katalog situs hanya tampil untuk `ru` saat flag internal aktif
  (`PUBLIC_SILERO_OFF != "1"`); bahasa CIS lain tersedia di data katalog.

#### (3) `tts-moss` — “Text to speech voices, MOSS” — galeri `cn`/`fa`

- **Upstream**: `OpenMOSS/MOSS-TTS-Nano` (**Apache-2.0**; HF
  `OpenMOSS-Team/MOSS-TTS-Nano`, mirror ModelScope `openmoss/MOSS-TTS-Nano`);
  model 0,1B, CPU, audio native 48 kHz stereo; tokenizer bersama
  `MOSS-Audio-Tokenizer-Nano-ONNX`.
- **Path**: `moss-tts-nano/23fd19793be20a4f3f6aacd4e3a2130c8e3d2519/`;
  LICENSE Apache 2.0 (11.374 B).
- **Total byte `ce = 243.415.892` (232,1 MiB)**. Komponen utama:

| File | Byte |
|---|---:|
| `moss_tts_global_shared_int8.data` | 110.512.128 |
| `moss_tts_local_fixed_sampled_frame_int8.data` | 84.974.592 |
| tokenizer `moss_audio_tokenizer_decode_shared.data` | 44.198.912 |
| `moss_tts_prefill.onnx` | 477.742 |
| `moss_tts_decode_step.onnx` | 489.413 |
| `moss_tts_local_fixed_sampled_frame.onnx` | 744.178 |
| `tokenizer.model` | 470.897 |
| codec onnx (full/step) | 681.902 + 351.400 |
| `browser_poc_manifest.json` | 503.354 |

- Arsitektur manifest: 16 codebook × 1024 token, vocab 16.384; LLM autoregresif
  atas token codec audio; default `max_new_frames 375`, audio temperature 0.8,
  repetition penalty 1.2. Suara galeri web: Junhao/Zhiming/Weiguo (M CN),
  Xiaoyu/Yuewen/Lingyu (F); varian `fa` tanpa F3.
- Catatan: upstream multilingual; build browser dibatasi menampilkan `cn`/`fa`.

#### (4) `tts-pocket-*` — “Voice cloning” (tool terpisah, bukan narator default)

- **Upstream**: **Kyutai Pocket TTS** — repo `kyutai-labs/pocket-tts` (kode MIT;
  bobot HF `kyutai/pocket-tts` **CC-BY-4.0**); ~100 juta parameter, CPU,
  diklaim ~6× real-time di MacBook Air M4; cloning dari ±5 detik sampel.
- **Path**: `pocket/<lang>/` dengan 7 bahasa: `english_2026-10`, `spanish`,
  `french`, `german`, `italian`, `dutch`, `portuguese`.
- **`bundle.json`**: `sample_rate 24000`, `frame_rate 12.5`,
  `samples_per_frame 1920`, `latent_dim 32`, `conditioning_dim 1024`,
  `schema_version 2`, `source_weights = hf://kyutai/pocket-tts/...@db04f0…`,
  `tokenizer_parity_vs_official = identical`, temperatur default 0.3,
  EOS threshold −4.0.
- File per bahasa (English terukur 165.763.880 B ≈158,1 MiB):
  `flow_lm_main_int8.onnx` 76.622.820; `mimi_encoder.onnx` 39.797.737;
  `mimi_decoder_int8.onnx` 22.730.197; `flow_lm_flow_int8.onnx` 10.060.096;
  `text_conditioner.onnx` 16.388.344; `vocab.json` ±136 KB; `bos.f32`;
  `bundle.json`. Codec = Mimi (Kyutai) di-encode/decode int8.
- Syarat lisensi bobot: atribusi Kyutai; ketentuan Kyutai melarang impersonasi
  suara tanpa persetujuan orang terdengar.

### 4.B. Speech recognition (tool Audio to Text; di luar inti SRT→audio)

| Kunci UI | Upstream / repo pinned | Lisensi | Ukuran terukur |
|---|---|---|---|
| `whisper-turbo` “Whisper large turbo” | `onnx-community/whisper-large-v3-turbo` @`360ebcde…` (Whisper OpenAI) | Whisper **MIT**; ekspor komunitas | WebGPU q4f16 tersimpan 563.479.095 B (537,4 MiB ≈540 MB UI); WASM quantized 1.084.758.911 B |
| `whisper-small` | `onnx-community/whisper-small_timestamped` @`65caa70f…` | MIT | WebGPU 586.213.010 B; WASM 249.036.248 B |
| `whisper-base` | `onnx-community/whisper-base_timestamped` @`608c49e…` | MIT | WebGPU 206.190.057 B; WASM 76.871.875 B |
| `fast-stt` | per bahasa: ru=GigaAM v3 e2e CTC (**MIT**); es/ar/fr/de=NeMo FastConformer hybrid CTC (**CC-BY-4.0**; pt **CC-BY-NC-4.0**); ko=Dolphin int8 (**Apache-2.0**); vi=Zipformer (**MIT**); tr=Zipformer (**Apache-2.0**) | bervariasi | mis. NeMo es model.onnx 79.504.894 B + frontend 1.140.933 B + vocab |
| `lang-check` “Spoken language detection” | Silero LID-95 `lang_classifier_95.onnx` | **MIT** | 16.972.591 B |

Catatan: `id` tidak punya entri `fast-stt`; di situs fall back ke Whisper.

### 4.C. Label pembicara (diarisasi)

| Kunci UI | Susunan | Lisensi | Ukuran |
|---|---|---|---|
| `speakers-nemotron` high accuracy | NVIDIA **Nemotron 3 Diarization** q4 (`diarize/nemotron-q4-v1`; ONNX oleh onnx-community) | **OpenMDW License 1.1** | graph 359.731 B + `_data` 8.276.803 B; data expanded mirror 73.769.392 B (UI ±79 MB) |
| `speakers-small` compact | pyannote segmentation-3.0 (MIT, CNRS) + WeSpeaker ResNet34-LM (VoxCeleb, **CC-BY-4.0**) + VBx/PLDA dari pyannote community-1 / BUT (**CC-BY-4.0**) | MIT + CC-BY-4.0 | segmentation 1.542.304 + embedding 6.685.134 + PLDA 267.352 B |

### 4.D. Alat lain (terdaftar di modal, bukan alur narasi)

- `ocr-vl` / `ocr`: PP-OCRv5 mobile det + PP-OCRv6 small rec PaddleOCR
  (lisensi proyek PaddleOCR Apache-2.0), `ppocrv6_small_dict.txt`, model
  `korean_PP-OCRv5_mobile_rec.onnx`.
- `hardsub`: pembaca subtitle terbakar (OCR + koreksi waktu).
- `separation` (2 stem) dan `separation-4stem`: pemisahan vokal/akustik.
- `denoise`: penghilang noise.
- `soundfont`: instrumen MIDI.
- `ctc-align` / `whisper-align`: timing kata lirik.
- `stress-ru`/`stress-uk`/`stress-be`: model stres homofon (lihat 4.A.2).

---

## 5. Logika pemilihan engine narator di situs (dari katalog chunk)

Urutan katalog (variabel `X`): spesifikasi Silero → Supertonic (`mo`) →
MOSS CN (`ir`) → MOSS FA (`ar`). Pemilihan: `X.find(locales.includes(lang))`,
fallback Supertonic (`ho`); Silero hanya ditampilkan untuk `ru` bila flag
`PUBLIC_SILERO_OFF != "1"`.

| Bahasa | Engine web terpilih | Catatan |
|---|---|---|
| `id` Indonesia | **`tts-supertonic`** | F1 default pada UI; salah satu 31 bahasa Supertonic |
| `en, de, es, fr, it, pt, ru, uk, tr, vi, ja, ko, …` (dalam 31 kode) | `tts-supertonic` | suara lintas-bahasa, style universal |
| `cn` | `tts-moss` | galeri M CN/F |
| `fa` | `tts-moss` | galeri FA tanpa F3 |
| `ru` (flag aktif) | opsi `tts-silero` | cis base nostress; default tetap Supertonic |
| Bahasa tak dikenal | Supertonic `na` | mode agnostik bahasa |

**Pola alur narasi yang diadopsi ke TUI (bukan tampilan, melainkan logika):**

1. Parse file subtitle (SRT/VTT) menjadi cue `(index, start, end, text)`.
2. Pilih engine + suara; pratinjau suara dan satu cue.
3. Sintesis **per cue** (bukan satu blok teks), lalu ukur durasi clip.
4. Dua mode pacing:
   - **Natural**: bicara memakai kecepatan wajar; boleh memakai jeda sebelum
     cue berikut; baru dipercepat bila perlu, dengan batas `max_speedup`.
   - **Tight**: clip dipas tepat di jendela cue; sisa overflow dilaporkan.
5. Tempatkan tiap clip pada `cue.start` di timeline master; ekspor
   WAV/MP3/M4A.
6. Lewati cue non-percakapan (mis. `(...)`, `[...]`).

Implementasi proyek ini: `timing.fit_cue()`, `mixer.build_master()` (overlay
pydub + `atempo` berantai FFmpeg), `pipeline.generate()`.

---

## 6. Pemetaan parity lokal ke `srt2audio-tui`

| Model web | Engine lokal di proyek ini | Status | Cara pakai |
|---|---|---|---|
| `tts-supertonic` (id & 30 bahasa) | **`supertonic`** | **Diimplementasikan** (opsional) | `pip install supertonic`; `--engine supertonic`; suara F1–F5/M1–M5; `SUPERTONIC_LANG=id` untuk paksa Indonesia |
| `tts-silero` (CIS) | roadmap (`roadmap` di registry) | belum | runner PyTorch Hub / ONNX; MIT untuk base |
| `tts-moss` (cn/fa) | roadmap | belum | `OpenMOSS-Team/MOSS-TTS-Nano` Apache-2.0, CPU ONNX |
| `tts-pocket-*` (clone) | roadmap | belum | `pip` paket pocket-tts; bobot CC-BY-4.0, syarat persetujuan suara |
| `whisper-turbo/base/small` | roadmap (fitur transkripsi balik) | belum | `faster-whisper` / `whisper.cpp` |
| `speakers-*` | roadmap (mode multi-suara) | belum | nemotron OpenMDW; small = pyannote/WeSpeaker |
| (fallback online) | `edge` | ada | neural Microsoft, termasuk `id-ID-GadisNeural`/`id-ID-ArdiNeural` |
| (fallback offline macOS) | `say` | ada | suara sistem bawaan MacBook |
| (ringan offline) | `piper` | opsional | VITS open-weights; suara bahasa tersedia sesuai rilis |
| tes / dry-run | `dummy` | ada | beep deterministik |

Urutan `auto` di TUI: `say → supertonic → edge → piper → dummy`.

Batas kejujuran teknis:

- Bit-exact identik dengan audio web tidak dijamin untuk Supertonic karena
  situs memuat build int8 `w8k` repack milik situs, sedangkan paket PyPI
  memakai rilis resmi Supertone (arsitektur dan bobot keluarga sama; default
  8 langkah denoising, speed 1.05 upstream; TUI ini memakai speed 1.0 lalu
  menyesuaikan tempo lewat `atempo`, sesuai mode Natural/Tight).
- RAIL-M membatasi penggunaan tertentu (mis. pembuatan konten menyesatkan /
  pelanggaran hak suara); baca Attachment A sebelum distribusi produk.
- MOSS/Pocket/Silero lokal butuh runner tambahan dan belum diaktifkan di
  rilis ini; datanya sudah dicatat di modul `srt2audio/webregistry.py`
  supaya pemasangan berikutnya tinggal menambah backend.

---

## 7. Arsitektur singkat Supertonic (dari manifest live)

`tts.json` v1.7.3, split `opensource-multilingual`:

- Text → `text_encoder` (char embed 256; ConvNeXt 6 layer; attention 4×4)
  → token teks 256-dim.
- Style → `style_encoder` dengan 50 prototipe; 10 suara bawaan memetakan ke
  prototipe tersebut; Voice Builder ekspor JSON style kustom.
- Duration predictor memprediksi panjang tiap segmen.
- **Flow matching**: `vector_field` 4 blok mengubah latent 24-dim dari
  noise ke spectrogram selama `total_steps` (default 8; kualitas 5–12).
- Vocoder/AE: spectrogram 228 mels @ 44,1 kHz → waveform 10-layer
  encoder/decoder; output WAV 16-bit.
- Preprocessing teks: `unicode_indexer.json` (277 KB); normalisasi, emoji
  removal, substitusi simbol; chunk otomatis ~300 karakter dengan jeda 0,3 dtk
  pada paket resmi.

Referensi performa upstream (CPU M4 Pro): ratusan–ribu karakter/detik; CPU
dioptimalkan untuk laptop tanpa GPU.

---

## 8. Sumber (URL langsung terverifikasi saat riset)

Situs dan halaman:

- `https://subtitlekit.com/en/about/` (Daniel Stoianov, Kanada, proyek indie;
  “run in your browser, with no registration required … nothing to install”)
- `https://subtitlekit.com/en/subtitles-to-audio/`
- `https://subtitlekit.com/en/voice-clone/`

Bobot & manifest host:

- `https://models.subtitlekit.com/supertonic/3cadd1ee6394adea1bd021217a0e650ede09a323/onnx/tts.json`
- `https://models.subtitlekit.com/supertonic/3cadd1ee6394adea1bd021217a0e650ede09a323/LICENSE` (BigScience RAIL-M, 15.007 B)
- `https://models.subtitlekit.com/silero-tts/v5_cis_base_nostress-0405777e-r2/LICENSE` (MIT, 1.076 B)
- `https://models.subtitlekit.com/moss-tts-nano/23fd19793be20a4f3f6aacd4e3a2130c8e3d2519/LICENSE` (Apache-2.0, 11.374 B)

Upstream open source:

- Supertonic: `https://github.com/supertone-inc/supertonic`,
  `https://pypi.org/project/supertonic/`,
  `https://huggingface.co/Supertone/supertonic-3`
- Silero: `https://github.com/snakers4/silero-models`
- MOSS Nano: `https://github.com/OpenMOSS/MOSS-TTS-Nano`,
  `https://huggingface.co/OpenMOSS-Team/MOSS-TTS-Nano`
- Pocket TTS: `https://github.com/kyutai-labs/pocket-tts`,
  `https://huggingface.co/kyutai/pocket-tts`,
  laporan teknis `https://kyutai.org/pocket-tts-technical-report`
- Whisper exports: `https://huggingface.co/onnx-community/whisper-large-v3-turbo`
  (dan repo `whisper-small_timestamped`, `whisper-base_timestamped`)
- Diarisasi kecil: `https://github.com/pyannote/pyannote-audio`

Referensi pola sinkronisasi SRT (logika, bukan kode situs):

- `https://pypi.org/project/srt2speech/1.2.0/` (strategi hybrid/overflow/precise, cap max-speedup)
- `https://github.com/ThioJoe/Auto-Synced-Translated-Dubs` (sintesis per-cue lalu stretch/shrink)
