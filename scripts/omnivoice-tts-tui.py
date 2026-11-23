#!/usr/bin/env python3
"""
omnivoice-tts-tui.py v0.7 — TTS LOKAL (offline) via OmniVoice (k2-fsa)

⚠ DEPRECATED (23 Nov 2026) — ref clone BERANTAKAN per user VLC test.
   v0.7 fix 3 lapis (encode-once + pos_temp=0 + guidance=3 + seed) TIDAK solve
   drift. Output audio berantakan, ref WAV gak fungsi. Pakai supertonic-tts-tui
   v0.1 (TUI #20) sebagai pengganti — deterministic fixed voices, no drift,
   ~100x faster. Script tetap di repo untuk referensi, JANGAN pakai production.

Eksperimen TTS offline (bukan TUI bernomor — collision dgn voicestudio #19).
Saudara dari piper-tts-tui v0.2 — workflow & algoritma SAMA PERSIS
(parse_srt, smart_fit_cue, trim/normalize/fade, mix_into_buffer, cache + lock,
2 mode SRT + Narasi). Hanya beda engine: Piper VITS → OmniVoice diffusion LM.

v0.6.3 (22 Nov 2026) — FIX 12x slowdown via voice_clone_prompt (encode once, reuse):
  - USER VERDICT v0.6.2 PENDING (belum diuji user — patch ditulis berdasarkan
    analisa source code OmniVoice setelah baca dokumentasi resmi k2-fsa/OmniVoice).
  - ROOT CAUSE v0.6.1/v0.6.2 slowdown 12x (11m33s vs 1m v0.5 Auto Voice):
    generate_cue_audio pass ref_audio=seed.wav per cue → OmniVoice internal
    _preprocess_all() panggil create_voice_clone_prompt() SETIAP cue →
    audio_tokenizer.encode() (CPU-bound, higgs-audio-v2-tokenizer TIDAK support
    MPS → WAJIB jalan di CPU) → ~16s overhead per cue. 39 cue × 16s = 10m+ overhead.
  - DOKUMENTASI RESMI (k2-fsa/OmniVoice README + source code omnivoice.py):
    Pattern resmi untuk reuse voice across multiple generate() calls:
      prompt = model.create_voice_clone_prompt(ref_audio="ref.wav", ref_text="...")
      prompt.save("my_voice.pt")           # encode SEKALI
      prompt = VoiceClonePrompt.load("my_voice.pt")  # load instant, no re-encode
      audio = model.generate(text="...", voice_clone_prompt=prompt)  # reuse token
    Source code _preprocess_all():
      if voice_clone_prompt is None and ref_audio is not None:
          voice_clone_prompt = self.create_voice_clone_prompt(...)  # ENCODE di sini
    → Kalau voice_clone_prompt= di-pass → block ini SKIP total → NO per-cue encode.
  - FIX v0.6.3:
    1. Pre-step Auto Lock: model.create_voice_clone_prompt(ref_audio=seed.wav,
       ref_text=SEED_REF_TEXT) → prompt.save(voice.pt). Encode SEKALI (CPU, ~2-3s).
    2. Cue loop: pass voice_clone_prompt=prompt (in-memory object) ke generate()
       → bypass create_voice_clone_prompt() internal → NO per-cue CPU encode.
    3. Resume: VoiceClonePrompt.load(voice.pt) instant → skip encode di re-run.
    4. Cache key tetap hash seed.wav content (voice.pt derived dari seed.wav,
       identity sama) → cache NPY tetap valid untuk resume.
  - SEED_REF_TEXT dipendekkan: 32 kata (~13s) → 17 kata (~6s). README resmi:
    "Use a 3-10 seconds reference audio clip. Longer audio slows down inference
    and may degrade cloning quality." 13s di atas range optimal → 6s sweet spot.
  - ESTIMASI SPEEDUP: 39 cue × ~2-3s (diffusion only, no encode) = ~2 menit
    (vs 11m33s v0.6.1). ~5x faster. Untuk 5000 cue: ~4 jam (vs ~24 jam v0.6.1).
  - KEEP num_step=16 (user request 22 Nov: "jangan 32, pake 16 saja"). README:
    "Use 16 for faster inference." pos_temp=0 (v0.6.2) + voice_clone_prompt (v0.6.3)
    sudah fix drift + slowdown — tidak perlu num_step=32.
  - MANUAL VOICE CLONING (user provide ref audio sendiri): tetap pakai ref_audio=
    per cue (belum pre-encode). Slower tapi hanya untuk mode itu. Auto Lock =
    pattern voice_clone_prompt (pre-encoded, fast).

v0.6.2 (22 Nov 2026) — FIX clone drift via pos_temp=0 + guidance=3 (clone-only):
  - USER VERDICT v0.6.1 FAILED (22 Nov 2026, real test 39 cue SRT):
    "hasil suara sangat buruk. suara laki-laki, kadang tua, muda, anak kecil.
     durasi generate juga sangat lama. jadi 9menit. padahal sebelumnya 1m."
    Log test: seed.wav 13.1s (dalam range 3-25s, FIX v0.6 OK) → TAPI clone cue
    2-N tetap drift parah (voice beda per cue). Waktu 11m33s (vs 1m v0.5 Auto
    Voice) — clone 12x lebih lambat. 1 cue fail (cue 39 output kosong).
  - ROOT CAUSE v0.6.1 drift (bukan seed length — hipotesis v0.6.1 SALAH):
    generate_cue_audio pass position_temperature=5.0 (default OmniVoice, STOCHASTIC)
    ke model.generate() untuk SEMUA mode termasuk clone. pos_temp=5.0 = di setiap
    diffusion step, model random-sample posisi dengan temp 5.0 → randomisasi
    position OVERRIDE voice lock dari ref_audio → voice drift per call meski
    ref_audio sama persis. Seed 13.1s lock voice embedding, tapi pos_temp=5.0
    inject random variation ON TOP → "laki-laki, tua, muda, anak kecil".
  - KENAPA v0.4 gagal tapi v0.6.2 harus succeed:
    v0.4 apply pos_temp=0 GLOBAL (semua mode). Tidak efektif untuk Voice Design
    karena drift source Voice Design = instruct text interpretation (model
    menebak attribute dari "female young adult"), BUKAN position sampling.
    v0.5 revert global ke 5.0 (verdict v0.4 FAILED). v0.6/v0.6.1 inherit 5.0
    → clone mode drift parah. v0.6.2 apply pos_temp=0 HANYA clone mode — drift
    source clone = position sampling (ref_audio lock voice embedding, pos_temp=5.0
    override dgn random). Berbeda mode, berbeda drift source, beda fix.
  - FIX v0.6.2:
    1. CLONE_POSITION_TEMPERATURE = 0.0 (greedy argmax, NO random sampling).
       Override via env OMNIVOICE_CLONE_POS_TEMP. Default 0.0 = lock voice.
    2. CLONE_GUIDANCE_SCALE = 3.0 (tighter CFG toward ref_audio voice embedding).
       Override via env OMNIVOICE_CLONE_GUIDANCE. Default 3.0 (vs 2.0 global).
    3. Apply HANYA di generate_cue_audio ketika mode=='clone' (autolock + manual
       Voice Cloning). Auto Voice + Voice Design tetap pakai global 5.0/2.0.
    4. num_step tetap 16 (tidak naik ke 32 — pos_temp=0 sudah lock, tidak perlu
       lebih banyak step. Avoid slowdown tambahan).
  - CACHE KEY: compute_cache_key sudah include pos_temp + guidance + num_step
    (sejak v0.4). Cache v0.6.1 (pos_temp=5.0, guidance=2.0) auto-bypass untuk
    v0.6.2 (pos_temp=0.0, guidance=3.0) → semua cue regenerate dgn params baru.
    User WAJIB rm -rf cache dir sebelum re-run v0.6.2 (atau jawab Yes di cleanup
    prompt untuk hapus cache v0.6.1 yang stale).
  - SPEED: clone mode 12x lebih lambat dari Auto Voice (18s/cue vs 1.5s/cue di
    MPS Mac M1). Ini inherent cost OmniVoice clone pipeline (ref_audio encode +
    voice embedding extraction per call). pos_temp=0 mungkin sedikit faster
    (greedy argmax cheaper dari sampling), tapi tidak dramatic. Trade-off:
    1 voice konsisten = waktu 9-11m untuk 39 cue. Tidak ada shortcut tanpa
    pre-compute voice embedding (butuh hack OmniVoice internals, out of scope).
  - TODO v0.6.3 (kalau masih drift setelah v0.6.2):
    - num_step 16 → 32 untuk clone (lebih banyak iterasi lock, 2x lambat lagi)
    - Pre-compute voice embedding sekali, reuse untuk semua cue (butuh akses
      ke OmniVoice internal API, bukan model.generate() public interface)
    - Fallback: kalau clone masih drift → rekomendasi Voice Cloning manual dgn
      ref_audio user rekam sendiri (voice asli = anchor lebih kuat dari random)

v0.6.1 (22 Nov 2026) — FIX Auto Lock seed terlalu pendek (root cause v0.6 gagal):
  - USER VERDICT v0.6 FAILED (22 Nov 2026, real test 39 cue SRT):
    "sudah play wav = hasil sangat buruk suara beda-beda tiap cue. gak jalan."
    Log test: cue 1 = "biarkan aku pergi" → seed.wav 1.1s → clone cue 2-N
    drift parah (voice beda tiap cue).
  - ROOT CAUSE: v0.6 pakai cue 1 text sebagai seed source. Kalau cue 1 pendek
    (1.1s untuk "biarkan aku pergi") → seed.wav 1.1s → OmniVoice Voice Cloning
    GAGAL extract voice embedding stabil (README: ref audio 3-25s WAJIB).
    Clone dari ref 1.1s → voice embedding hampir random → tiap call clone
    produksi voice beda → drift parah. v0.6 cuma kasih WARNING (tidak prevent),
    user abaikan warning → hasil buruk.
  - FIX v0.6.1: seed dari SEED_REF_TEXT (fixed Indonesian paragraph ~10s,
    phoneme-rich), BUKAN cue 1 text. Ref text 32 kata ~10s spoken → dalam
    range 3-25s OmniVoice → voice embedding stabil → clone lock voice character.
    SEMUA cue (1-N) clone dari seed.wav yang sama → 1 voice guaranteed.
  - IMPLIKASI: cue 1 di final output = CLONE dari seed (bukan Auto Voice random
    langsung). Voice character tetap = voice seed (random Auto Voice dari
    SEED_REF_TEXT). Konsistensi 1 voice LEBIH KETAT dari v0.6 (yang cue 1 = auto,
    cue 2-N = clone — bisa beda tipis). Trade-off: cue 1 tidak lagi = voice
    random persis, tapi voice character konsisten = GOAL utama user.
  - SEED_REF_TEXT: 32 kata Indonesian, phoneme-rich (cover a/i/u/e/o, ng, ny,
    kh via "akhir", sy via "sayuran"), gender-neutral, natural narrative tone.
    Override via env: OMNIVOICE_SEED_REF_TEXT="..." (kalau user mau ref custom).
  - SIMPLIFIKASI KODE: cue loop tidak lagi special-case cue 1. SEMUA cue pakai
    per_cue_vc = {'mode':'clone', ref_audio=seed.wav, ref_text=SEED_REF_TEXT}.
    Hapus first_cue_idx tracking + pre-save cue 1 .npy logic (tidak perlu —
    cue 1 generate fresh via clone seperti cue 2-N).
  - HARD GUARD: kalau seed.wav durasi < 3.0s setelah generate (rare: model
    trim terlalu agresif atau error) → print warning TEGAS + sarana re-roll.
    Tidak ada lagi silent pass dengan seed pendek.

v0.6 (22 Nov 2026) — SINGLE VOICE MODE (Auto Lock):
  - USER VERDICT v0.5 NOT FIT (22 Nov 2026): Auto Voice random per cue = multi-
    speaker natural untuk DUBBING, TAPI tidak cocok kalau user mau 1 voice
    konsisten untuk seluruh SRT (audiobook, narator tunggal, video tutorial).
    User request 22 Nov 2026: "1 voice untuk seluruh SRT. Konsistensi maksimal,
    zero setup." Strategi: lock voice cue 1, clone ke cue 2-N (mirror VoiceStudio
    "Consistent" mode pattern).
  - SOLUSI v0.6 Auto Lock:
      Cue 1: generate pakai Auto Voice (random) → save seed.wav + seed.txt
             (seed.txt = transkrip cue 1, WAJIB untuk OmniVoice clone alignment)
      Cue 2-N: Voice Cloning dengan ref_audio=seed.wav → voice sama dengan cue 1
    README resmi OmniVoice: "If ref_audio is provided, the model will clone the
    voice from the reference audio." → 1 voice untuk seluruh SRT, guaranteed.
  - ZERO SETUP: tidak perlu siapkan ref audio user. Voice cue 1 = voice seluruh
    SRT. Auto Voice random Indonesian v0.5 verified bagus → lock itu.
  - RE-ROLL VOICE: kalau voice cue 1 jelek → jawab "n" di preview prompt (seed
    dihapus + abort), atau re-run (seed.wav regenerate dengan random voice baru).
  - PREVIEW PROMPT: setelah cue 1 di-generate, TUI prompt "Voice cue 1 OK?
    [Y/n]" — kalau n, abort & delete seed, user re-run untuk acak ulang.
  - CACHE STRATEGY (resume-friendly):
      Cue 1 (mode 'auto' internal): cache key = text+language+params (no seed,
        random by design). NP-resume kalau SRT sama dijalankan ulang. seed.wav
        di-reuse kalau ada → resume = voice cue 1 tetap sama.
      Cue 2-N (mode 'clone' internal): cache key = text+seed.wav content hash+
        language+params. Kalau seed.wav berubah (re-roll), cache otomatis bypass
        → cue 2-N regenerated dengan voice baru. Old NPY orphaned, tidak dipakai.
  - VOICE_CONFIG SCHEMA: tambah mode='autolock' (resolved per-cue di main_srt
    jadi 'auto' untuk cue 1 / 'clone' untuk cue 2-N). generate_cue_audio,
    smart_fit_cue, compute_cache_key TIDAK diubah — tetap lihat 'auto'/'clone'.
    Patch terbatas di select_voice + main_srt + main_narration guard.
  - GUARD: Auto Lock untuk SRT mode saja. Narasi = single-call, tidak ada cue
    2-N untuk di-clone. main_narration exit dengan pesan kalau user pilih Auto
    Lock (arahkan ke Auto Voice / preset / clone biasa).
  - TRADE-OFF vs v0.5 Auto Voice random:
      + 1 voice konsisten untuk seluruh SRT (utama)
      + Zero setup (tidak perlu ref audio user)
      + Re-roll mudah (delete seed + re-run, atau jawab n di preview)
      - Cue 2-N butuh ref_audio load per call → sedikit overhead (~0.1-0.3s
        per cue, negligible vs generate time ~5s di MPS Mac M1)
      - Clone quality tergantung seed.wav durasi. OmniVoice rekomendasi 3-25s.
        Kalau cue 1 pendek (<3s) → warning + clone quality mungkin menurun.
        Workaround: pindah cue lebih panjang ke posisi cue 1 di SRT editor.

v0.5 (22 Nov 2026) — PIVOT: Auto Voice + language lock + librosa time_stretch:
  - VERDICT v0.4 FAILED (user 22 Nov 2026): "Hasil Wav = berantakan sangat parah,
    tiap cue beda-beda parah." pos_temp=0 + guidance=3 tidak fix drift karena
    drift source BUKAN di token sampling layer — di voice embedding derivation.
    Voice Design untuk Indonesian = low-resource; README resmi OmniVoice bilang:
    "Voice design is trained on Chinese and English data only. It can produce
    unstable results for some low-resource languages or edge cases."
    → Voice Design path MATI untuk konsistensi multi-cue Indonesian. Bukan bug
    parameter, limitasi training data. Saya salah claim v0.4 fix, mengaku.
  - USER INSIGHT 22 Nov 2026: "terlanjur suara engga bisa satu, maka sekalin
    bikin random saja. Model baca konteks... cuma harus dikunci adalah bahasa =
    wajib bahasa indonesia, logat indonesia."
  - SOLUSI v0.5: pakai Auto Voice mode (README resmi: "If no reference audio or
    instruct are provided, the model will generate text in a random voice.").
    Random voice per cue BY DESIGN → leverage untuk multi-speaker natural dubbing.
    Language DIPAKSA via language="id" (atau "jv") supaya phoneme mapping +
    accent routing tetap konsisten. Hanya voice character yang random, bahasa
    tetap Indonesia.
  - SPEEDUP v0.5 (estimated ~3.5x vs v0.4 untuk 39 cue):
      1. num_step 32 → 16 (official 2x cepat, README sanclip)
      2. Smart Fit pass 2 generate call → librosa.effects.time_stretch
         (1x generate per cue, audio di-stretch untuk fit slot SRT)
  - DROP v0.4 override (tidak efektif): position_temperature kembali 5.0
    (default OmniVoice), guidance_scale kembali 2.0 (default OmniVoice).
    Override tetap tersedia via env var OMNIVOICE_POS_TEMP/GUIDANCE untuk
    eksperimen.
  - DROP seed (torch.manual_seed) untuk Auto Voice mode — random voice diinginkan,
    seed malah kontra-produktif. Voice Cloning mode tetap pakai seed.
  - Voice Design mode tetap tersedia (untuk Narasi/ref WAV single-call yang
    user verified "sangat bagus"), TAPI di-mark DEPRECATED untuk SRT multi-cue.

v0.4 (22 Nov 2026) — FIX VOICE DRIFT antar cue (untuk SRT mode):
  - BUG v0.3: walaupun language="id" fix 80% aksen ke Indonesia, masih ada
    drift voice antar cue (anak kecil → perempuan muda → paruh baya → tua).
    User report 22 Nov 2026: "1 srt = 1 suara titik" untuk konsistensi.
  - ROOT CAUSE dari source code OmniVoice (omnivoice/models/omnivoice.py
    baris 175-189 OmniVoiceGenerationConfig dataclass):
      position_temperature: float = 5.0   ← STOCHASTIC, temp > 0 = sampling acak
      class_temperature:    float = 0.0   ← sudah greedy default
      guidance_scale:       float = 2.0   ← classifier-free guidance scale
      num_step:             int   = 32    ← diffusion steps
    position_temperature=5.0 = di setiap diffusion step, model random sample
    posisi mana yang di-unmask dengan temp 5.0 (high randomness).
  - KENAPA SEED TIDAK BERGUNA (user insight 22 Nov 2026):
    torch.manual_seed(42) seharusnya lock RNG, TAPI:
      1. MPS Apple Silicon non-deterministic di beberapa op meskipun seed di-set
         (PyTorch known limit, sudah di-documented di v0.2 docstring)
      2. Kalau internal OmniVoice pakai generator terpisah, seed tidak tembus
      3. Smart Fit ON ~80% cue dapat 2 generate call (pass 2) → drift berlipat
    → seed-based determinism TIDAK BISA garantasi konsistensi voice di SRT.
  - FIX v0.4: set position_temperature=0.0 → GREEDY ARGMAX posisi. Tidak ada
    RNG call sama sekali → tidak peduli MPS non-determinism. Pass 1 & pass 2
    Smart Fit harusnya menghasilkan voice identik karena tidak ada randomness
    source. guidance_scale dinaikkan 2.0 → 3.0 untuk lock attribute region
    lebih ketat di sekitar titik yang di-define oleh instruct.
  - OVERRIDE via env var (tanpa edit kode):
      OMNIVOICE_POS_TEMP=0.0   (default 5.0 di OmniVoice, v0.4 pakai 0.0)
      OMNIVOICE_GUIDANCE=3.0   (default 2.0 di OmniVoice, v0.4 pakai 3.0)
      OMNIVOICE_NUM_STEP=32    (default 32, 16 = 2x cepat trade quality)
  - CACHE KEY v0.4: include pos_temp + class_temp + guidance + num_step
    supaya cache v0.3 (default decoding) tidak dipakai ulang untuk v0.4.
  - SMART FIT TETAP ON untuk SRT (user requirement 22 Nov 2026): "mode ON
    wajib untuk srt ke audio. Kalau mode ON mati = audio akan kacau, audio
    bisa sangat panjang melebihi srt, padahal srt sudah fix timestamp."
    Smart Fit OFF hanya untuk Narasi/ref WAV (tidak ada constraint durasi).

v0.3 (22 Nov 2026) — FIX AKSEN ASAP (bug terkonfirmasi dari source code OmniVoice):
  - BUG v0.2: parameter `language=` TIDAK DIPASS ke model.generate(). Default
    None → OmniVoice pasang string "None" literal ke slot token bahasa
    `<|lang_start|>None<|lang_end|>` → mode language-agnostic → menebak aksen
    sendiri. Untuk teks Indonesia tanpa language="id" → condong aksen luar.
    User report 22 Nov 2026: "suara berubah-ubah gak jelas, aksen luar, padahal
    sebelumnya aksen Indonesia".
  - BUG v0.2: field `lang_hint` di preset (id/jv) di-drop sebelum sampai
    generate_cue_audio(). select_voice() return dict cuma {mode, instruct,
    label} — lang_hint hilang di tengah jalan. Fix: include 'language' di
    voice_config, di-pass ke generate().
  - FIX: tambah step "Language" di select_voice() (preset otomatis pakai
    lang_hint-nya, custom bisa pilih id/jv/en/auto). Default "id" untuk
    preset ID, "jv" untuk preset Jawa. Custom default "id".
  - CACHE KEY v0.3: include language supaya cache v0.2 (bug aksen) tidak
    dipakai ulang untuk v0.3 (fix aksen).
  - CAVEAT README resmi: "Voice design is trained on Chinese and English
    data only." — voice design untuk ID tetap agak miss, tapi language="id"
    setidaknya membantu model pilih tokenizer + phoneme mapping yang benar,
    reduce aksen drift signifikan.

v0.2 (22 Nov 2026) — Custom instruct + reinforced determinism:
  - CUSTOM INSTRUCT: free-text instruct (bukan cuma 7 preset). User reported
    "terserah model yg isi suara, baik laki atau perempuan" → kasih opsi ketik
    instruct sendiri. Valid keyword (gender/age/pitch/accent) ada hint bantu,
    tapi tidak diblokir — OmniVoice sendiri yang validasi via error message.
    Cocok untuk eksplor "male, young adult, low pitch" vs "male, elderly,
    very low pitch" dll tanpa edit source code.
  - INSTRUCT HISTORY: instruct custom disimpan ke ~/.omnivoice_instruct_history.txt
    (max 20 entry, dedup). Tampil di menu custom sebagai quick-reuse pilihan,
    mirror pattern "recently used" di shell. Persist antar session.
  - REINFORCED DETERMINISM: v0.1 cuma torch.manual_seed(42). Tapi OmniVoice
    diffusion pakai 3 sumber randomness: torch, numpy, random module. Tanpa
    seed 3-nya → noise init beda tiap cue → "kadang perempuan muda, kadang
    anak kecil, kadang separuh baya" (user feedback 22 Nov 2026).
    v0.2 seed semua 3 + use_deterministic_algorithms(True, warn_only=True).
    MPS tetap non-deterministic untuk sebagian operator (PyTorch known limit),
    tapi variasi antar cue berkurang drastis.
  - CACHE KEY DIPERLUAS: kini include seed (OMNIVOICE_SEED) supaya cache v0.1
    tidak dipakai ulang untuk voice yang berbeda determinism-nya.

v0.1 (22 Nov 2026) — Initial release:
  - Engine: OmniVoice 0.6B (k2-fsa/OmniVoice), Apache 2.0 code, CC-BY-NC model.
    Model download sekali (~3.27GB cache di ~/.cache/huggingface), 100% offline.
  - GPU Metal via PyTorch MPS (device_map="mps", dtype=float32).
    float16 segfault di Python 3.14 + torch 2.14 (verified via omnivoice_diag.py),
    pakai float32 saja. Mac M1 tetap cepat (model load 2.1s, RTF ~2.0).
  - 2 mode voice:
    * Voice Design: 4 preset (ID perempuan verified bagus, ID laki 2 variant,
      Jawa perempuan + laki 2 variant). Instruct text dari valid list OmniVoice
      (female/male, young adult/middle-aged/elderly, low/moderate/high pitch).
    * Voice Cloning: ref_audio + ref_text → clone voice user. Paling akurat
      untuk laki-laki (Voice Design ID laki sering miss/kemresek).
  - Smart Fit via speed= parameter (mirror piper length_scale, terbalik).
    speed=1.0 natural, speed=1.5 = 1.5x cepat. Verified speed 1.5x tidak robotik.
  - 2 Mode (match piper-tts-tui v0.2):
    * SRT mode: SRT → ~/Dubbing/tts/{prefix}-audio-id-dub.wav (24kHz mono 16-bit, mix-tui compatible)
    * Narration mode: naskah.txt → ~/Dubbing/tts/{stem}-narasi.wav (48kHz stereo)

Trade-off vs piper-tts-tui v0.2:
  + Kualitas audio JAUH lebih bagus (user verified: "jauh lebih bagus dari piper")
  + Voice cloning zero-shot (bisa klon voice suami/istri/teman dari 3-25 detik ref audio)
  + Multi-voice: 4 preset + voice cloning (vs Piper cuma id_ID-news_tts perempuan)
  - RTF ~2.0 (2x lebih lambat dari real-time). Piper VITS ~0.15 RTF.
    Untuk SRT 10 menit → ~25 menit generate. Acceptable untuk LAN/keluarga.
  - Jawa pakai logat Indo (OmniVoice training data Jawa cuma 11 jam vs ID 6327 jam).
    Untuk Jawa natural → pakai Voice Cloning dengan ref audio penutur asli Jawa.
  - Model 3.27GB (vs Piper 62MB). Install size: torch + omnivoice ~2GB.
  - ID laki via Voice Design sering miss/kemresek. Workaround: Voice Cloning,
    atau coba variant instruct lain (2 variant disediakan di preset).

Anti-amnesia pattern (adopsi dari 3 TUI existing):
  - piper-tts-tui v0.2 → algoritma TTS: parse_srt, smart_fit_cue, trim/normalize/fade,
    mix_into_buffer, cache key + lock file, 2 mode (SRT + Narasi). VERBATIM PORT.
  - whisper-tui v2.1 → pattern LOCAL MODEL: model load SEKALI per session, cached.
  - omnivoice_test2.py → verified config: device_map="mps" + float32, instruct valid keywords,
    speed= parameter untuk smart_fit (bukan length_scale).

Setup user (Mac ~/Dubbing/ venv):
  # venv existing sudah ada piper-tts → tambah omnivoice saja (torch sudah ada)
  source ~/Dubbing/venv/bin/activate
  pip3 install omnivoice soundfile
  # Verifikasi MPS: python3 -c "import torch; print(torch.backends.mps.is_available())"
  # → True
  # First run: download model 3.27GB (cached sekali di ~/.cache/huggingface)

Pakai:
  cd ~/Dubbing && source venv/bin/activate && python3 omnivoice-tts-tui.py

Model load: ~2s cached, RTF ~2.0 di MPS Mac M1.
"""

import os
import sys
import time
import wave
import struct
import hashlib
import argparse
import random
from pathlib import Path

# ============================================================
# Version
# ============================================================
VERSION = 'v0.7'  # ref-only: simplify ke Voice Cloning only + pre-encode voice_clone_prompt

# ============================================================
# Dependency check
# ============================================================
_MISSING_DEPS = []

try:
    import questionary
except ImportError:
    _MISSING_DEPS.append('questionary')

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    _MISSING_DEPS.append('numpy')

try:
    import torch
    HAS_TORCH = True
    _MPS_AVAILABLE = getattr(torch.backends, 'mps', None) and torch.backends.mps.is_available()
except ImportError:
    HAS_TORCH = False
    _MPS_AVAILABLE = False
    _MISSING_DEPS.append('torch')

try:
    import soundfile as sf
    HAS_SOUNDFILE = True
except ImportError:
    HAS_SOUNDFILE = False
    _MISSING_DEPS.append('soundfile')

# v0.5: time_stretch untuk Smart Fit — ganti pass 2 generate call (yang bikin
# drift voice antar pass karena Auto Voice = random per call). Pakai resample
# scipy (phase-vocoder-free, simple linear interpolation). Fallback numpy interp
# kalau scipy tidak ada.
try:
    from scipy.signal import resample as scipy_resample
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

try:
    from omnivoice import OmniVoice
    HAS_OMNIVOICE = True
except ImportError:
    HAS_OMNIVOICE = False
    _MISSING_DEPS.append('omnivoice')

if _MISSING_DEPS:
    print()
    print('═' * 64)
    print('❌ Dependensi belum lengkap!')
    print('═' * 64)
    print()
    print(f'   Missing: {", ".join(_MISSING_DEPS)}')
    print()
    print('   Install dengan (Mac M1, venv ~/Dubbing/):')
    print('   source ~/Dubbing/venv/bin/activate')
    print('   pip3 install omnivoice soundfile numpy questionary')
    print()
    print('═' * 64)
    sys.exit(1)


# ============================================================
# Config import (mirror piper-tts-tui pattern, sama persis)
# ============================================================
# Pakai config.py yang sama dengan piper-tts-tui (SSD_HOME, HDD_BASE,
# INPUT_DIR, TTS_DIR, REVIEW_DIR, ensure_hdd). Struktur:
#   SSD ~/Dubbing/             → scripts + venv (cepat)
#   HDD /Volumes/HDD/Dubbing/  → data (input, demucs, tts, mix, review, ...)
#
# Kalau config.py tidak ada (rare case), fallback ke default HDD path.
try:
    from config import (
        SSD_HOME, HDD_BASE,
        INPUT_DIR, TTS_DIR, REVIEW_DIR,
        ensure_hdd,
    )
    _HAS_CONFIG = True
except ImportError:
    _HAS_CONFIG = False
    SSD_HOME = Path.home() / 'Dubbing'
    HDD_BASE = Path('/Volumes/HDD/Dubbing')
    INPUT_DIR = HDD_BASE / 'input'
    TTS_DIR = HDD_BASE / 'tts'
    REVIEW_DIR = HDD_BASE / 'review'

    def ensure_hdd():
        if not HDD_BASE.exists():
            print('\n❌ HDD eksternal tidak ter-colok!')
            print(f'   Folder tidak ditemukan: {HDD_BASE}')
            print('   Colok HDD eksternal, lalu jalankan ulang.')
            return False
        for d in [INPUT_DIR, TTS_DIR, REVIEW_DIR]:
            d.mkdir(parents=True, exist_ok=True)
        return True


# Ref audio search dirs (untuk Voice Cloning).
# Mirror struktur config.py: data di HDD, bukan SSD.
# Priority: HDD/refs (khusus ref audio) → HDD/input (audio yt-dlp) → SSD root.
REF_AUDIO_DIRS = [
    str(HDD_BASE / 'refs'),   # /Volumes/HDD/Dubbing/refs (khusus ref voice cloning)
    str(INPUT_DIR),           # /Volumes/HDD/Dubbing/input (audio yt-dlp, mungkin ada)
    str(SSD_HOME),            # ~/Dubbing (SSD root, fallback kalau ref ada di sini)
]


# ============================================================
# Constants — match piper-tts-tui v0.2 (mix-tui compatible)
# ============================================================
OUTPUT_SAMPLE_RATE = 24000  # SRT mode: match piper-tts-tui (mix-tui expects 24kHz)
OUTPUT_CHANNELS = 1
OUTPUT_BITS = 16

NARR_SAMPLE_RATE = 48000  # Narration mode: stereo
NARR_CHANNELS = 2

CROSSFADE_MS = 150
TRIM_HEAD_DB = -30
TRIM_TAIL_DB = -30
TRIM_PADDING_MS = 30
NORMALIZE_DBFS = -2.0
NOISE_FLOOR_DB = -50.0

# Smart Fit cap — SELECT match piper-tts-tui (4 opsi, default 1.5x)
# OmniVoice speed=1.5 verified tidak robotik (user test 22 Nov 2026).
SMART_FIT_CAP_DEFAULT = 1.5
SMART_FIT_DEBUG = os.environ.get('OMNIVOICE_SMART_FIT_DEBUG') == '1'

# OmniVoice model config (verified via omnivoice_diag.py + omnivoice_test2.py)
MODEL_ID = 'k2-fsa/OmniVoice'
DEVICE_MAP = 'mps' if _MPS_AVAILABLE else 'cpu'
DTYPE = torch.float32  # float16 segfault di Mac M1 Python 3.14, pakai float32

# OmniVoice native output sample rate (model generate di 24kHz)
OMNIVOICE_NATIVE_SR = 24000

# Determinism seed — fix "suara beda-beda tiap cue" problem.
# OmniVoice = diffusion model, tanpa seed → random noise init berbeda tiap call.
# Set torch.manual_seed(SEED) sebelum setiap generate() supaya cue 1 & cue 2
# dengan voice_config sama menghasilkan prosodi & timbre konsisten.
#
# v0.2: REINFORCED determinism. v0.1 cuma torch.manual_seed → variasi masih
# signifikan karena diffusion model juga ambil noise dari numpy.random + Python
# random module (untuk sampling step, dropout, dll). v0.2 seed 3-nya sebelum
# setiap generate:
#   - torch.manual_seed(SEED) + torch.mps.manual_seed(SEED)   → tensor ops
#   - np.random.seed(SEED)                                    → numpy sampling
#   - random.seed(SEED)                                        → Python random
# Plus use_deterministic_algorithms(True, warn_only=True) — kalau ada op
# non-deterministic di MPS, log warning tapi tidak crash.
#
# Override via env: OMNIVOICE_SEED=123
SEED = int(os.environ.get('OMNIVOICE_SEED', '42'))

# v0.4 DECODING PARAMETERS — fix voice drift antar cue (untuk SRT mode).
# Default OmniVoice:
#   position_temperature = 5.0   ← STOCHASTIC, temp > 0 = sampling posisi acak
#   class_temperature    = 0.0   ← sudah greedy default
#   guidance_scale       = 2.0   ← classifier-free guidance scale
#   num_step             = 32    ← diffusion steps (16 = 2x cepat, 32 = stabil)
#
# BUG v0.3 dengan seed: torch.manual_seed(42) seharusnya lock RNG, TAPI:
#   1. MPS Apple Silicon non-deterministic di beberapa op meskipun seed di-set
#   2. position_temperature=5.0 = di setiap diffusion step, model random sample
#      posisi mana yang di-unmask dengan temp 5.0 (high randomness). Kalau RNG
#      tidak ter-kontrol (point 1), position akan beda antar cue walaupun
#      instruct sama.
#   3. Smart Fit ON ~80% cue dapat 2 generate call (pass 2) → drift berlipat.
#
# FIX v0.4: set position_temperature=0.0 → GREEDY ARGMAX posisi. Tidak ada
# RNG call → tidak peduli MPS non-determinism. Pass 1 & pass 2 Smart Fit
# harusnya menghasilkan voice identik (karena tidak ada randomness source).
#
# guidance_scale dinaikkan dari 2.0 → 3.0: lock attribute region lebih ketat,
# voice character lebih stabil di sekitar titik yang di-define oleh instruct.
#
# Source: OmniVoice source code omnivoice/models/omnivoice.py baris 175-189
# (OmniVoiceGenerationConfig dataclass):
#   num_step: int = 32
#   guidance_scale: float = 2.0
#   t_shift: float = 0.1
#   layer_penalty_factor: float = 5.0
#   position_temperature: float = 5.0
#   class_temperature: float = 0.0
#   denoise: bool = True
#   ...
# v0.5 STRATEGY PIVOT — Auto Voice + language lock (drop Voice Design untuk SRT):
#   v0.4 FAILED: pos_temp=0 + guidance=3 tidak fix drift karena drift source BUKAN
#   di token sampling layer — di voice embedding derivation (Voice Design untuk
#   Indonesian = low-resource, README resmi bilang "may produce unstable results").
#   User verdict 22 Nov 2026: "berantakan sangat parah, tiap cue beda-beda parah"
#
#   v0.5 SOLUSI: drop Voice Design, pakai Auto Voice mode.
#   Quote README resmi: "If no reference audio or instruct are provided, the
#   model will generate text in a random voice."
#   Voice random per cue BY DESIGN — leverage untuk multi-speaker natural dubbing.
#   Language tetap DIPAKSA via language="id" (atau "jv") supaya phoneme mapping
#   + accent routing tetap konsisten, hanya voice character yang random.
#
#   Speedup v0.5:
#     - num_step 32 → 16 (official 2x cepat, README sanclip)
#     - Smart Fit pass 2 generate → librosa time_stretch (1x generate per cue)
#
#   Override via env (untuk eksperimen — default v0.5 sudah optimal):
#     OMNIVOICE_NUM_STEP=16     (default v0.5; 32 = stabil tapi 2x lambat)
#     OMNIVOICE_POS_TEMP=5.0    (default OmniVoice; v0.4 pakai 0.0 tapi tidak efektif)
#     OMNIVOICE_GUIDANCE=2.0    (default OmniVoice; v0.4 pakai 3.0 tapi tidak efektif)
NUM_STEP = int(os.environ.get('OMNIVOICE_NUM_STEP', '16'))                # v0.5: 32 → 16 (2x cepat)
POSITION_TEMPERATURE = float(os.environ.get('OMNIVOICE_POS_TEMP', '5.0'))  # v0.5: kembali ke default OmniVoice
CLASS_TEMPERATURE = float(os.environ.get('OMNIVOICE_CLASS_TEMP', '0.0'))  # default OmniVoice (greedy)
GUIDANCE_SCALE = float(os.environ.get('OMNIVOICE_GUIDANCE', '2.0'))       # v0.5: kembali ke default OmniVoice

# v0.6.2 Clone mode decoding params — lock voice dari ref_audio (FIX drift).
# ROOT CAUSE v0.6.1 drift: position_temperature=5.0 (default OmniVoice) =
# stochastic sampling di setiap diffusion step → bahkan dengan ref_audio 13.1s,
# voice drift per call (verdict user 22 Nov 2026: "suara laki-laki, kadang tua,
# muda, anak kecil"). pos_temp=0.0 = greedy argmax → lock voice dari ref.
# guidance_scale 2.0 → 3.0: tighter classifier-free guidance toward ref_audio
# voice embedding (kuatkan adherence ke voice yang di-clone).
#
# Kenapa v0.4 gagal tapi v0.6.2 harus succeed:
#   v0.4 apply pos_temp=0 GLOBAL (semua mode). Tidak efektif untuk Voice Design
#   karena drift source Voice Design = instruct text interpretation (model
#   menebak "female young adult" → random attribute), BUKAN position sampling.
#   v0.5 revert global ke 5.0. v0.6/v0.6.1 inherit 5.0 → clone mode drift parah.
#   v0.6.2 apply pos_temp=0 HANYA clone mode — drift source clone = position
#   sampling (ref_audio sudah lock voice embedding, pos_temp=5.0 override dgn
#   random). Berbeda dari Voice Design, fix-nya berbeda.
#
# Override via env (eksperimen — default v0.6.2 sudah optimal untuk clone):
#   OMNIVOICE_CLONE_POS_TEMP=0.0   (0 = greedy lock; 1.0 = slight variation)
#   OMNIVOICE_CLONE_GUIDANCE=3.0   (2.0 = loose; 4.0 = very tight ke ref)
CLONE_POSITION_TEMPERATURE = float(os.environ.get('OMNIVOICE_CLONE_POS_TEMP', '0.0'))
CLONE_GUIDANCE_SCALE = float(os.environ.get('OMNIVOICE_CLONE_GUIDANCE', '3.0'))

# v0.6.1 Auto Lock seed reference text — fixed Indonesian paragraph ~6s spoken.
# v0.6.3: dipendekkan dari 32 kata (~13s) ke 17 kata (~6s). README resmi OmniVoice:
# "Use a 3-10 seconds reference audio clip. Longer audio slows down inference
# and may degrade cloning quality." 13s = di atas range optimal → clone quality
# menurun + encode lebih lambat. 6s = sweet spot (cukup phoneme coverage, cepat).
# Phoneme coverage: a/i/u/e/o, ng (selamat/datang/bernama/pergi/bersama/membeli),
# ny (ibunya). Gender-neutral, natural narrative tone.
# Override via env OMNIVOICE_SEED_REF_TEXT kalau user mau ref custom (harus 3-10s
# spoken — kalau kurang dari 3s clone gagal, kalau lebih dari 10s quality menurun).
_DEFAULT_SEED_REF_TEXT = (
    'Halo, selamat datang. Seorang anak bernama Budi pergi ke pasar bersama '
    'ibunya membeli buah segar. Terima kasih.'
)
SEED_REF_TEXT = os.environ.get('OMNIVOICE_SEED_REF_TEXT', _DEFAULT_SEED_REF_TEXT)

# Instruct history file — custom instruct yang user pernah ketik disimpan
# di sini, supaya bisa dipakai ulang di session berikutnya (quick-reuse).
# Mirror pattern: shell history, atau "recently used" di GUI app.
# Lokasi home dir (bukan HDD) supaya survive walau HDD tidak colok.
INSTRUCT_HISTORY_FILE = os.path.expanduser('~/.omnivoice_instruct_history.txt')
INSTRUCT_HISTORY_MAX = 20  # max entry yang disimpan

# Valid keyword hint untuk custom instruct (dari error message OmniVoice).
# Dipakai di select_voice() sebagai bantuan, TIDAK memvalidasi input user —
# OmniVoice sendiri yang validasi via error message (mirror v0.1 behavior).
INSTRUCT_VALID_HINT = """\
gender : female | male
age    : child | teenager | young adult | middle-aged | elderly
pitch  : very low | low | moderate | high | very high
other  : whisper
accent : american | australian | british | canadian | chinese | indian | japanese | korean | portuguese | russian
(NOT Indonesian/Javanese accent — bahasa dikontrol dari text input, bukan instruct)
Contoh: "male, young adult, low pitch"
        "female, middle-aged, high pitch"
        "male, elderly, very low pitch"
"""

# Language option untuk OmniVoice generate(language=...) — v0.3 fix aksen.
# Source: OmniVoice source code baris 619-621 (docstring generate()):
#   "Language name (e.g. "English") or code (e.g. "en"). None for language-
#    agnostic mode. Performance is slightly better if you specify the language."
# Resolusi (baris 1472-1489 _resolve_language):
#   - None atau "none" → None (language-agnostic, MODEL MENEBAK AKSEN)
#   - kode 2-huruf di LANG_IDS → dipakai apa adanya ("id", "jv", "en", ...)
#   - nama di LANG_NAME_TO_ID → dipetakan ke kode ("Indonesian" → "id")
#   - tidak dikenali → WARNING + fallback ke None (BUKAN error)
#
# Daftar di bawah adalah subset yang relevan untuk user Indonesia + fallback.
# Untuk list lengkap 647 bahasa, lihat docs/lang_id_name_map.tsv di repo OmniVoice.
LANGUAGE_OPTIONS = [
    ('id', 'Indonesian (id) — default untuk teks Indonesia'),
    ('jv', 'Javanese (jv) — untuk teks Jawa'),
    ('en', 'English (en) — untuk teks English/aksen luar'),
    ('su', 'Sundanese (su)'),
    ('ms', 'Malay (ms)'),
    ('auto', 'Auto (None — model menebak bahasa, AKAN BISA NYIMPANG AKSEN)'),
]
# Peta lang_hint preset → kode language
LANGUAGE_PRESET_MAP = {
    'id': 'id',
    'jv': 'jv',
    'en': 'en',
}


# ============================================================
# Voice presets — Voice Design (instruct text valid)
# ============================================================
# Instruct valid keywords (dari error message OmniVoice):
#   gender: female, male
#   age   : child, teenager, young adult, middle-aged, elderly
#   pitch : very low, low, moderate, high, very high
#   other : whisper
#   accent: american, australian, british, canadian, chinese,
#            indian, japanese, korean, portuguese, russian
#   (NO Indonesian/Javanese accent — bahasa dari text input)
#
# User feedback 22 Nov 2026:
#   - id_perempuan (female, young adult) = sangat bagus → verified default
#   - id_laki (male, middle-aged, low pitch) = kemresek → variant lain disediakan
#   - jv_perempuan + jv_laki = logat Indo (limitasi model, 11 jam training Jawa)

VOICE_PRESETS = [
    {
        'id': 'id_perempuan',
        'label': 'Indonesia, perempuan muda (verified bagus)',
        'instruct': 'female, young adult',
        'lang_hint': 'id',
    },
    {
        'id': 'id_laki_v1',
        'label': 'Indonesia, laki-laki — variant 1: young adult (simple)',
        'instruct': 'male, young adult',
        'lang_hint': 'id',
    },
    {
        'id': 'id_laki_v2',
        'label': 'Indonesia, laki-laki — variant 2: middle-aged, low pitch (DEPRECATED: kemresek)',
        'instruct': 'male, middle-aged, low pitch',
        'lang_hint': 'id',
    },
    {
        'id': 'id_laki_v3',
        'label': 'Indonesia, laki-laki — variant 3: elderly, very low pitch',
        'instruct': 'male, elderly, very low pitch',
        'lang_hint': 'id',
    },
    {
        'id': 'jv_perempuan',
        'label': 'Jawa, perempuan muda (caveat: logat Indo)',
        'instruct': 'female, young adult',
        'lang_hint': 'jv',
    },
    {
        'id': 'jv_laki_v1',
        'label': 'Jawa, laki-laki — variant 1: young adult',
        'instruct': 'male, young adult',
        'lang_hint': 'jv',
    },
    {
        'id': 'jv_laki_v3',
        'label': 'Jawa, laki-laki — variant 3: elderly, very low pitch',
        'instruct': 'male, elderly, very low pitch',
        'lang_hint': 'jv',
    },
]

# Special marker for voice cloning
VOICE_CLONE_ID = '__clone__'


# ============================================================
# GPU detection (MPS = Metal di M1)
# ============================================================

def get_gpu_status():
    """Return (provider_label, has_mps)."""
    if _MPS_AVAILABLE:
        return ('MPS (Metal GPU)', True)
    return ('CPU', False)


# ============================================================
# OmniVoice model loader (cached, single load per session)
# ============================================================

_MODEL_CACHE = {}


def load_omnivoice_model():
    """Load OmniVoice model sekali per session. Cache hasil load.
    Return (model, load_time, ep_label).
    """
    if 'model' in _MODEL_CACHE:
        return _MODEL_CACHE['model'], _MODEL_CACHE['load_time'], _MODEL_CACHE['ep_label']

    print(f'  Loading OmniVoice (device={DEVICE_MAP}, dtype=float32)...')
    print(f'  (First run: download 3.27GB dari HuggingFace, cached sekali)')
    t0 = time.time()
    try:
        model = OmniVoice.from_pretrained(
            MODEL_ID,
            device_map=DEVICE_MAP,
            dtype=DTYPE,
        )
    except Exception as e:
        print(f'  ❌ Load gagal: {e}')
        print()
        print('  Kemungkinan:')
        print('    - HuggingFace blocked: export HF_ENDPOINT=https://hf-mirror.com')
        print('    - Disk penuh (butuh ~3.3GB free)')
        print('    - MPS issue: coba DEVICE_MAP="cpu" (edit baris DEVICE_MAP di script)')
        sys.exit(1)
    load_time = time.time() - t0
    ep_label = f'MPS (Metal GPU)' if DEVICE_MAP == 'mps' else 'CPU'
    _MODEL_CACHE['model'] = model
    _MODEL_CACHE['load_time'] = load_time
    _MODEL_CACHE['ep_label'] = ep_label
    return model, load_time, ep_label


# ============================================================
# SRT parsing + formatting (port verbatim dari piper-tts-tui v0.2)
# ============================================================

def parse_srt(content):
    entries = []
    blocks = content.strip().replace('\r\n', '\n').replace('\r', '\n').split('\n\n')
    for block in blocks:
        lines = [l for l in block.split('\n') if l.strip()]
        if len(lines) < 2:
            continue
        idx = 0
        time_line_idx = 0
        if lines[0].strip().isdigit():
            idx = int(lines[0].strip())
            time_line_idx = 1
        if time_line_idx >= len(lines):
            continue
        time_line = lines[time_line_idx]
        if ' --> ' not in time_line:
            continue
        start_str, end_str = time_line.split(' --> ')[:2]
        start = _parse_time(start_str.strip())
        end = _parse_time(end_str.strip())
        if start is None or end is None:
            continue
        text_lines = lines[time_line_idx + 1:]
        entries.append({'index': idx, 'start': start, 'end': end, 'textLines': text_lines})
    return entries


def _parse_time(ts):
    try:
        ts = ts.replace(',', '.')
        h, m, s = ts.split(':')
        return int(h) * 3600 + int(m) * 60 + float(s)
    except (ValueError, AttributeError):
        return None


def format_timestamp(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f'{h:02d}:{m:02d}:{s:06.3f}'


def format_duration(seconds):
    if seconds < 0:
        seconds = 0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f'{h}j {m}m {s}s'
    if m > 0:
        return f'{m}m {s}s'
    return f'{s}s'


def normalize_tts_text(text):
    import re
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\{[^}]*\}', '', text)
    text = ' '.join(text.split())
    return text.strip()


# ============================================================
# Audio processing (port verbatim dari piper-tts-tui v0.2)
# ============================================================

def resample_audio(audio, src_sr, target_sr):
    """Resample float32 array via linear interpolation (numpy)."""
    if src_sr == target_sr or len(audio) == 0:
        return audio
    if HAS_NUMPY:
        ratio = target_sr / src_sr
        new_len = int(len(audio) * ratio)
        if new_len < 1:
            return np.zeros(1, dtype=np.float32)
        indices = np.linspace(0, len(audio) - 1, new_len)
        lo = indices.astype(np.int32)
        hi = np.minimum(lo + 1, len(audio) - 1)
        frac = (indices - lo).astype(np.float32)
        return (audio[lo] * (1 - frac) + audio[hi] * frac).astype(np.float32)
    else:
        ratio = target_sr / src_sr
        new_len = int(len(audio) * ratio)
        resampled = []
        for i in range(new_len):
            src_idx = i / ratio
            lo = int(src_idx)
            hi = min(lo + 1, len(audio) - 1)
            frac = src_idx - lo
            resampled.append(audio[lo] * (1 - frac) + audio[hi] * frac)
        return resampled


def time_stretch_audio(audio, rate):
    """Time-stretch audio by `rate` (1.0 = no change, >1.0 = faster/shorter,
    <1.0 = slower/longer). Pitch shifts slightly (simple resample approach) —
    acceptable untuk rate 0.7-1.5 range (Smart Fit cap=1.5).

    v0.5: dipakai Smart Fit pass 2 — ganti generate call (yang bikin drift voice
    antar pass di Auto Voice mode). Lock 1 random voice dari pass 1, lalu stretch
    untuk fit slot SRT. Lebih cepat (~3.5x vs pass 2 generate) + tidak drift.

    Prefers scipy.signal.resample (FFT-based, higher quality), falls back to
    numpy linear interp (sama dengan resample_audio).
    """
    if rate <= 0 or len(audio) == 0 or abs(rate - 1.0) < 1e-4:
        return audio
    new_len = max(1, int(len(audio) / rate))
    if HAS_SCIPY:
        # scipy.signal.resample: FFT-based, preserves spectral shape better
        # than linear interp. Output dtype float64, cast balik ke float32.
        out = scipy_resample(audio, new_len).astype(np.float32) if HAS_NUMPY else scipy_resample(audio, new_len)
        return out
    # Fallback numpy linear interp (mirror resample_audio)
    if HAS_NUMPY:
        indices = np.linspace(0, len(audio) - 1, new_len)
        lo = indices.astype(np.int32)
        hi = np.minimum(lo + 1, len(audio) - 1)
        frac = (indices - lo).astype(np.float32)
        return (audio[lo] * (1 - frac) + audio[hi] * frac).astype(np.float32)
    # Pure Python fallback (very slow, only if numpy missing — should not happen)
    out = []
    for i in range(new_len):
        src_idx = i * rate
        lo = int(src_idx)
        hi = min(lo + 1, len(audio) - 1)
        frac = src_idx - lo
        out.append(audio[lo] * (1 - frac) + audio[hi] * frac)
    return out


def db_to_linear(db):
    return 10 ** (db / 20.0)


def trim_silence_asymmetric(audio, sr, padding_ms=TRIM_PADDING_MS):
    if HAS_NUMPY:
        if len(audio) == 0:
            return np.zeros(0, dtype=np.float32)
        head_thresh = db_to_linear(TRIM_HEAD_DB)
        tail_thresh = db_to_linear(TRIM_TAIL_DB)
        abs_audio = np.abs(audio)
        head_idx = int(np.argmax(abs_audio > head_thresh))
        if abs_audio[head_idx] <= head_thresh:
            return np.zeros(0, dtype=np.float32)
        rev_abs = abs_audio[::-1]
        tail_idx_from_end = int(np.argmax(rev_abs > tail_thresh))
        tail_idx = len(audio) - tail_idx_from_end
        if tail_idx <= head_idx:
            return audio[head_idx:head_idx + 1]
        pad = int(sr * padding_ms / 1000)
        head = max(0, head_idx - pad)
        tail = min(len(audio), tail_idx + pad)
        return audio[head:tail].copy()
    else:
        head_thresh = db_to_linear(TRIM_HEAD_DB)
        tail_thresh = db_to_linear(TRIM_TAIL_DB)
        abs_audio = [abs(v) for v in audio]
        head_idx = 0
        for i, v in enumerate(abs_audio):
            if v > head_thresh:
                head_idx = i
                break
        tail_idx = len(audio) - 1
        for i in range(len(abs_audio) - 1, -1, -1):
            if abs_audio[i] > tail_thresh:
                tail_idx = i
                break
        if tail_idx <= head_idx:
            return audio[head_idx:head_idx + 1]
        pad = int(sr * padding_ms / 1000)
        head = max(0, head_idx - pad)
        tail = min(len(audio), tail_idx + pad + 1)
        return audio[head:tail]


def peak_normalize(audio, target_db=NORMALIZE_DBFS, noise_floor_db=NOISE_FLOOR_DB):
    if HAS_NUMPY:
        if len(audio) == 0:
            return audio
        peak = float(np.max(np.abs(audio)))
        if peak < db_to_linear(noise_floor_db):
            return audio
        target = db_to_linear(target_db)
        gain = target / max(peak, 1e-9)
        return (audio * gain).astype(np.float32)
    else:
        if len(audio) == 0:
            return audio
        peak = max(abs(v) for v in audio)
        if peak < db_to_linear(noise_floor_db):
            return audio
        target = db_to_linear(target_db)
        gain = target / max(peak, 1e-9)
        return [v * gain for v in audio]


def apply_fade_out(audio, fade_start, fade_end):
    if fade_end <= fade_start or len(audio) == 0:
        return audio
    fade_len = fade_end - fade_start
    if HAS_NUMPY:
        fade = np.linspace(1.0, 0.0, fade_len, dtype=np.float32)
        audio[fade_start:fade_end] *= fade
        return audio
    else:
        for i in range(fade_len):
            idx = fade_start + i
            if idx < len(audio):
                audio[idx] *= (1.0 - i / fade_len)
        return audio


def apply_fade_in(audio, fade_start, fade_end):
    if fade_end <= fade_start or len(audio) == 0:
        return audio
    fade_len = fade_end - fade_start
    if HAS_NUMPY:
        fade = np.linspace(0.0, 1.0, fade_len, dtype=np.float32)
        audio[fade_start:fade_end] *= fade
        return audio
    else:
        for i in range(fade_len):
            idx = fade_start + i
            if idx < len(audio):
                audio[idx] *= (i / fade_len)
        return audio


def mix_into_buffer(all_audio, audio, position, fade_out_end=None, fade_in_start=None, fade_len=0):
    if len(audio) == 0:
        return all_audio
    end = position + len(audio)
    if fade_out_end is not None and end > fade_out_end:
        audio_len = len(audio)
        fade_start_in_audio = fade_out_end - position
        if fade_start_in_audio < audio_len:
            audio = apply_fade_out(
                audio.copy() if HAS_NUMPY else list(audio),
                fade_start_in_audio, audio_len,
            )
            end = position + len(audio)
    if fade_in_start is not None and fade_len > 0:
        audio = apply_fade_in(
            audio.copy() if HAS_NUMPY else list(audio),
            0, min(fade_len, len(audio)),
        )
    if end > len(all_audio):
        audio = audio[:len(all_audio) - position]
        end = len(all_audio)
    if position < 0:
        audio = audio[-position:]
        position = 0
    if HAS_NUMPY:
        all_audio[position:end] += audio
    else:
        for i in range(len(audio)):
            all_audio[position + i] += audio[i]
    return all_audio


def encode_wav(audio, sample_rate=OUTPUT_SAMPLE_RATE, channels=OUTPUT_CHANNELS, output_path=None):
    if HAS_NUMPY:
        clipped = np.clip(audio, -1.0, 1.0)
        int_audio = (clipped * 32767).astype(np.int16)
    else:
        int_audio = []
        for v in audio:
            v = max(-1.0, min(1.0, v))
            int_audio.append(int(v * 32767))
        int_audio = struct.pack(f'<{len(int_audio)}h', *int_audio)

    if output_path:
        with wave.open(output_path, 'wb') as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(OUTPUT_BITS // 8)
            wf.setframerate(sample_rate)
            if HAS_NUMPY:
                if channels == 2 and int_audio.ndim == 1:
                    int_audio = np.column_stack([int_audio, int_audio]).flatten()
                wf.writeframes(int_audio.tobytes())
            else:
                if channels == 2:
                    int_audio = b''.join(
                        struct.pack('<hh', v, v)
                        for v in struct.unpack(f'<{len(int_audio)//2}h', int_audio)
                    )
                wf.writeframes(int_audio)
        return None
    else:
        import io
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(OUTPUT_BITS // 8)
            wf.setframerate(sample_rate)
            if HAS_NUMPY:
                wf.writeframes(int_audio.tobytes())
            else:
                wf.writeframes(int_audio)
        return buf.getvalue()


# ============================================================
# OmniVoice generate (Voice Design + Voice Cloning)
# ============================================================

def generate_cue_audio(text, model, voice_config, speed=1.0, target_sr=OUTPUT_SAMPLE_RATE,
                       seed=SEED):
    """Generate 1 cue via OmniVoice. Return float32 numpy array at target_sr, mono.

    voice_config (v0.5 — 3 mode resmi OmniVoice):
      - mode='auto':   {'mode': 'auto', 'language': 'id', 'label': '...'}
                       RANDOM voice per cue BY DESIGN (leverage multi-speaker).
                       language=WAJIB untuk lock phoneme + accent routing.
      - mode='design': {'mode': 'design', 'instruct': 'female, young adult',
                        'language': 'id', 'label': '...'}
                       DEPRECATED untuk SRT multi-cue (drift parah — v0.4 FAILED).
                       Tetap tersedia untuk Narasi single-call.
      - mode='clone':  {'mode': 'clone', 'ref_audio': '/path.wav',
                        'ref_text': '...', 'language': 'id', 'label': '...'}
                       Stable by design (untuk Narasi/ref WAV).

    v0.5 PIVOT: Auto Voice mode jadi DEFAULT untuk SRT. README resmi OmniVoice:
      "If no reference audio or instruct are provided, the model will generate
       text in a random voice."
    Language DIPAKSA via language="id" supaya random voice tetap logat Indonesia.
    User insight 22 Nov 2026: "terlanjur suara engga bisa satu, maka sekalin
    bikin random saja... cuma harus dikunci adalah bahasa = wajib bahasa
    indonesia, logat indonesia."

    v0.5 DROP seed untuk Auto Voice mode: random voice diinginkan, seed
    kontra-produktif. Voice Design/Clone tetap pakai seed (untuk reproducibility
    kalau perlu debug).

    speed: >1.0 faster (mirror piper length_scale inverse).
    num_step: v0.5 default 16 (official 2x cepat, README sanclip).
    """
    # Seed hanya untuk mode yang butuh reproducibility (design/clone).
    # v0.5: Auto Voice mode SKIP seed — random voice per cue BY DESIGN.
    if seed is not None and voice_config['mode'] != 'auto':
        torch.manual_seed(seed)
        if _MPS_AVAILABLE:
            torch.mps.manual_seed(seed)
        if HAS_NUMPY:
            np.random.seed(seed)
        random.seed(seed)
        # Aktifkan deterministic algorithms dengan warn_only=True — kalau ada
        # op non-deterministic di MPS, log warning tapi tidak crash (better
        # partial determinism + finish than hard crash on first non-det op).
        try:
            torch.use_deterministic_algorithms(True, warn_only=True)
        except TypeError:
            # torch versi lama tidak punya warn_only kwarg — fallback silent
            try:
                torch.use_deterministic_algorithms(True)
            except Exception:
                pass
        except Exception:
            pass

    kwargs = {
        'text': text,
        'speed': speed,
        # v0.5: num_step=16 (default v0.5, 2x cepat dari 32). Override via env.
        # pos_temp/guidance kembali default OmniVoice (5.0/2.0) — v0.4 override
        # TIDAK efektif fix drift, jadi kembalikan ke default resmi.
        'num_step': NUM_STEP,
        'position_temperature': POSITION_TEMPERATURE,
        'class_temperature': CLASS_TEMPERATURE,
        'guidance_scale': GUIDANCE_SCALE,
    }
    # v0.3 FIX AKSEN: pass language= ke model.generate(). v0.2 bug: tidak
    # di-pass → default None → mode language-agnostic → menebak aksen sendiri.
    # v0.5: language= WAJIB untuk Auto Voice supaya random voice tetap logat ID.
    language = voice_config.get('language')
    if language is not None and language != 'auto':
        kwargs['language'] = language

    if voice_config['mode'] == 'design':
        kwargs['instruct'] = voice_config['instruct']
    elif voice_config['mode'] == 'clone':
        # v0.6.3: prefer voice_clone_prompt (pre-encoded) kalau ada → bypass
        # per-cue CPU encode (fix 12x slowdown). Source code OmniVoice
        # _preprocess_all(): if voice_clone_prompt is not None → skip
        # create_voice_clone_prompt() internal → NO audio_tokenizer.encode().
        # Fallback ref_audio+ref_text untuk manual Voice Cloning mode (user
        # provide ref audio sendiri, belum pre-encode — slower tapi accurate).
        if voice_config.get('voice_clone_prompt') is not None:
            kwargs['voice_clone_prompt'] = voice_config['voice_clone_prompt']
        else:
            kwargs['ref_audio'] = voice_config['ref_audio']
            kwargs['ref_text'] = voice_config['ref_text']
        # v0.6.2 FIX CLONE DRIFT: override pos_temp + guidance HANYA untuk clone
        # mode. Default POSITION_TEMPERATURE=5.0 (stochastic) = drift parah untuk
        # clone — randomisasi position override voice lock dari ref_audio, hasil
        # voice beda per call meski ref_audio sama (verdict v0.6.1 FAILED).
        # pos_temp=0.0 (greedy argmax) + guidance=3.0 (tighter CFG) → lock voice.
        # v0.4 coba ini global tapi tidak efektif untuk Voice Design (drift source
        # = instruct interpretation, bukan position sampling). Clone berbeda.
        kwargs['position_temperature'] = CLONE_POSITION_TEMPERATURE
        kwargs['guidance_scale'] = CLONE_GUIDANCE_SCALE
    elif voice_config['mode'] == 'auto':
        # v0.5 Auto Voice: NO instruct, NO ref_audio → model random voice per call.
        # Language lock via kwargs['language'] di atas.
        pass
    else:
        raise ValueError(f'Unknown voice mode: {voice_config["mode"]}')

    try:
        audio = model.generate(**kwargs)
    except Exception as e:
        raise RuntimeError(f'OmniVoice generate gagal: {e}')

    if not audio or len(audio) == 0:
        return np.zeros(0, dtype=np.float32) if HAS_NUMPY else []

    audio_arr = audio[0] if isinstance(audio, list) else audio
    if not HAS_NUMPY:
        audio_arr = np.array(audio_arr, dtype=np.float32)

    # Resample jika perlu (OmniVoice native 24kHz, SRT mode 24kHz, Narasi 48kHz)
    if OMNIVOICE_NATIVE_SR != target_sr:
        audio_arr = resample_audio(audio_arr, OMNIVOICE_NATIVE_SR, target_sr)
    return audio_arr


def format_speed(need, cap):
    """need (natural_dur/cue_dur) → OmniVoice speed parameter.
    speed: >1.0 faster. need>1.0 (too long) → speedup → speed=need (capped).
    """
    if need <= 1.0:
        return 1.0
    return min(need, cap)


# ============================================================
# Smart Fit (adapted for speed= parameter — mirror piper smart_fit_cue)
# ============================================================

def compute_cache_key(text, voice_config, speed=1.0, seed=SEED):
    """Cache key berdasarkan text + voice config + speed + seed + language + decoding params.
    Untuk Voice Design: hash(text + instruct + speed + seed + language + pos_temp + guidance + num_step)
    Untuk Voice Cloning: hash(text + ref_audio + ref_text + speed + seed + language + decoding params)
    Untuk Auto Voice: hash(text + speed + language + num_step) — NO seed (random by design)

    v0.5: 'auto' mode dimasukkan. Auto Voice tidak pakai seed (random voice per
    cue BY DESIGN), tapi text+language tetap dipakai untuk cache (resume kalau
    SRT sama dijalankan ulang — walau voice beda, audio cache tetap valid untuk
    fit slot SRT). Tag 'v0.5_time_stretch' supaya cache v0.4 (pakai pass 2
    generate) tidak dipakai ulang untuk v0.5 (pakai time_stretch).
    v0.4: decoding params (position_temperature, guidance_scale, num_step) dimasukkan ke
    cache key supaya cache v0.3 (default decoding: pos_temp=5.0, guidance=2.0) tidak dipakai
    ulang untuk v0.4 (pos_temp=0.0 greedy, guidance=3.0 tighter). Kalau user override via
    env var, cache otomatis bypass → generate ulang dengan parameter baru.
    v0.3: language dimasukkan ke cache key supaya cache v0.2 (bug aksen:
    tidak pass language) tidak dipakai ulang untuk v0.3 (fix aksen). Kalau
    user ganti language antar run, cache otomatis bypass → generate ulang.
    v0.2: seed dimasukkan supaya cache v0.1 tidak dipakai ulang.
    """
    h = hashlib.sha256()
    h.update(text.encode('utf-8'))
    if voice_config['mode'] == 'design':
        h.update(b'design|')
        h.update(voice_config['instruct'].encode('utf-8'))
    elif voice_config['mode'] == 'clone':
        h.update(b'clone|')
        # Hash ref_audio file content (kalau path tidak berubah tapi isi berubah)
        try:
            with open(voice_config['ref_audio'], 'rb') as f:
                ref_hash = hashlib.md5(f.read()).hexdigest()[:16]
            h.update(ref_hash.encode('utf-8'))
        except IOError:
            h.update(voice_config['ref_audio'].encode('utf-8'))
        h.update(b'|')
        h.update(voice_config['ref_text'].encode('utf-8'))
    elif voice_config['mode'] == 'auto':
        # v0.5: Auto Voice mode. Tidak ada instruct/ref_audio → hash cuma text.
        # Seed TIDAK dimasukkan (random voice by design).
        h.update(b'auto|')
    h.update(f'|speed={speed:.4f}'.encode('utf-8'))
    # v0.5: Auto Voice skip seed (random). Design/Clone tetap include seed.
    if voice_config['mode'] != 'auto':
        h.update(f'|seed={seed}'.encode('utf-8'))
    # v0.3: include language. 'auto' atau None → language-agnostic (None),
    # coded same supaya cache key konsisten untuk mode language-agnostic.
    lang = voice_config.get('language')
    if lang is None or lang == 'auto':
        h.update(b'|lang=None')
    else:
        h.update(f'|lang={lang}'.encode('utf-8'))
    # v0.4: include decoding parameters (pos_temp, class_temp, guidance, num_step)
    # supaya cache v0.3 (default decoding) tidak dipakai ulang untuk v0.4.
    h.update(f'|pos_temp={POSITION_TEMPERATURE}'.encode('utf-8'))
    h.update(f'|class_temp={CLASS_TEMPERATURE}'.encode('utf-8'))
    h.update(f'|guidance={GUIDANCE_SCALE}'.encode('utf-8'))
    h.update(f'|num_step={NUM_STEP}'.encode('utf-8'))
    # v0.5: tag time_stretch supaya cache v0.4 (pass 2 generate) tidak dipakai ulang.
    h.update(b'|v05_timestretch')
    return h.hexdigest()[:16]


def smart_fit_cue(text, cue_dur, model, voice_config, cap, cache_dir, cache_key, prefix, cue_idx):
    """Smart Fit 1 cue (v0.5 — time_stretch, no pass 2 generate):
    1. Cache check: natural .npy (speed=1.0) ada?
    2. Generate natural (speed=1.0) kalau belum → trim → compute need
    3. need <= 1.0 → peak normalize natural
    4. need > 1.0 → time_stretch natural dengan rate=min(need, cap) → peak normalize
       (v0.5: ganti pass 2 generate call. Auto Voice mode = random voice per call,
        jadi pass 2 generate akan bikin voice cue 1 bagian awal ≠ cue 1 bagian akhir.
        time_stretch lock 1 random voice, hanya compress durasi.)

    v0.5 SPEEDUP: 1x generate per cue (vs v0.4 ~1.8x dengan pass 2 generate).
    Trade-off: pitch shift sedikit di rate >1.0 (acceptable untuk cap=1.5).
    """
    natural_npy = os.path.join(cache_dir, f'{prefix}-cue-{cue_idx:04d}-{cache_key}.npy')

    # Pass 1: natural (speed=1.0)
    if not (os.path.isfile(natural_npy) and os.path.getsize(natural_npy) > 0):
        audio = generate_cue_audio(text, model, voice_config, speed=1.0)
        if len(audio) == 0:
            raise RuntimeError(f'Pass 1 gagal cue {cue_idx} (output kosong)')
        if HAS_NUMPY:
            np.save(natural_npy, audio)
        else:
            import pickle
            with open(natural_npy, 'wb') as f:
                pickle.dump(audio, f)

    if HAS_NUMPY:
        natural_audio_raw = np.load(natural_npy)
    else:
        import pickle
        with open(natural_npy, 'rb') as f:
            natural_audio_raw = pickle.load(f)

    natural_audio = trim_silence_asymmetric(natural_audio_raw, OUTPUT_SAMPLE_RATE)
    natural_dur = len(natural_audio) / OUTPUT_SAMPLE_RATE
    need = natural_dur / max(0.001, cue_dur)

    if SMART_FIT_DEBUG:
        fit_status = 'FIT' if need <= 1.0 else f'OVERFLOW need={need:.2f}'
        print(f'  [cue {cue_idx}] dur={cue_dur:.2f}s nat={natural_dur:.2f}s {fit_status}')

    if need <= 1.0:
        return peak_normalize(natural_audio)

    # v0.5 Pass 2: time_stretch (ganti pass 2 generate call)
    # rate = speedup factor (>1.0 = shorter/faster). Capped ke `cap` (1.5).
    speedup = min(need, cap)
    if SMART_FIT_DEBUG:
        print(f'  [cue {cue_idx}] Pass 2 (time_stretch): need={need:.2f} cap={cap} rate={speedup:.3f}')
    stretched_audio = time_stretch_audio(natural_audio, rate=speedup)
    return peak_normalize(stretched_audio)


# ============================================================
# Cache + lock (port verbatim dari piper-tts-tui v0.2)
# ============================================================

def _pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def lock_path_for(output_dir, prefix):
    return os.path.join(output_dir, f'.{prefix}.omnivoice.lock')


def acquire_lock(output_dir, prefix):
    lock_path = lock_path_for(output_dir, prefix)
    if os.path.isfile(lock_path):
        try:
            with open(lock_path, 'r') as f:
                pid = int(f.read().strip())
            if _pid_alive(pid):
                return (False, f'Lock aktif (PID {pid}). Instance lain jalan untuk prefix "{prefix}".')
        except (ValueError, IOError):
            pass
    try:
        with open(lock_path, 'w') as f:
            f.write(str(os.getpid()))
        return (True, lock_path)
    except IOError as e:
        return (False, f'Tidak bisa tulis lock: {e}')


def release_lock(output_dir, prefix):
    lock_path = lock_path_for(output_dir, prefix)
    try:
        if os.path.isfile(lock_path):
            os.unlink(lock_path)
    except OSError:
        pass


def suggest_unique_prefix(output_dir, prefix, max_attempts=99):
    if not os.path.isfile(os.path.join(output_dir, f'{prefix}-audio-id-dub.wav')):
        return prefix
    for i in range(2, max_attempts + 1):
        cand = f'{prefix}-{i}'
        if not os.path.isfile(os.path.join(output_dir, f'{cand}-audio-id-dub.wav')):
            return cand
    return prefix + '-' + str(int(time.time()))


# ============================================================
# TUI helpers
# ============================================================

def clear_screen():
    os.system('clear' if os.name != 'nt' else 'cls')


def print_banner():
    gpu_label, has_mps = get_gpu_status()
    gpu_line = f'GPU: {gpu_label}'
    print('╔' + '═' * 64 + '╗')
    print('║  🗣️  OmniVoice TTS TUI v0.7 — REF CLONE ONLY (1 voice konsisten) ║')
    print('║' + ' ' * 64 + '║')
    print(f'║  Backend : OmniVoice 0.6B + {gpu_line:<37}║')
    print('║  Pattern : piper-tts-tui v0.2 algoritma + omnivoice engine     ║')
    print('║  v0.7    : ref audio only + voice_clone_prompt encode-once     ║')
    print('╚' + '═' * 64 + '╝')
    if not has_mps:
        print()
        print('⚠ MPS tidak aktif (CPU mode). Mac M1 seharusnya support MPS.')
        print('  Cek: python3 -c "import torch; print(torch.backends.mps.is_available())"')
        print('  Harus True. Kalau False, reinstall torch: pip3 install torch --force-reinstall')
    print()


def find_srt_files(search_dir):
    if not os.path.isdir(search_dir):
        return []
    files = [f for f in os.listdir(search_dir) if f.lower().endswith('.srt')]
    files.sort()
    return files


# Audio extensions yang diterima OmniVoice (PCM WAV, MP3, FLAC, OPUS)
AUDIO_EXTS = ('.wav', '.mp3', '.flac', '.opus', '.m4a')


def find_ref_audio_files(search_dirs=None):
    """Scan folder lokal untuk ref audio (Voice Cloning).
    Return list of (path, basename, dur_seconds) — sorted by name.
    """
    if search_dirs is None:
        search_dirs = REF_AUDIO_DIRS
    found = []
    seen = set()
    for d in search_dirs:
        if not d or not os.path.isdir(d):
            continue
        try:
            for f in sorted(os.listdir(d)):
                if f.lower().endswith(AUDIO_EXTS) and not f.startswith('.'):
                    full = os.path.join(d, f)
                    if full in seen:
                        continue
                    seen.add(full)
                    # Coba ambil durasi
                    dur = None
                    try:
                        if HAS_SOUNDFILE:
                            info = sf.info(full)
                            dur = info.frames / info.samplerate
                    except Exception:
                        pass
                    found.append((full, f, dur))
        except OSError:
            continue
    return found


# ============================================================
# Voice selection — Voice Design preset atau Voice Cloning
# ============================================================

def load_instruct_history():
    """Load instruct custom history dari file.
    Return list of instruct string, urut paling baru terakhir (cronological).
    File format: 1 instruct per line, format JSON-encoded string (aman untuk
    newline/multi-line instruct, mirror shell history pattern).
    """
    if not os.path.isfile(INSTRUCT_HISTORY_FILE):
        return []
    history = []
    try:
        import json as _json
        with open(INSTRUCT_HISTORY_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.rstrip('\n')
                if not line:
                    continue
                try:
                    instr = _json.loads(line)
                    if isinstance(instr, str) and instr.strip():
                        history.append(instr.strip())
                except (ValueError, _json.JSONDecodeError):
                    # Fallback: line bukan JSON, pakai raw (backward compat)
                    if line.strip():
                        history.append(line.strip())
    except (IOError, OSError):
        pass
    # Dedup preserve order (keep first occurrence / paling lama),
    # supaya entry unik tapi urutan tetap kronologis.
    seen = set()
    deduped = []
    for instr in history:
        if instr not in seen:
            seen.add(instr)
            deduped.append(instr)
    return deduped


def save_instruct_history(history_list):
    """Save instruct history ke file. Trim ke INSTRUCT_HISTORY_MAX entry
    terbaru (keep paling baru di akhir list).
    """
    # Dedup preserve order
    seen = set()
    deduped = []
    for instr in history_list:
        if isinstance(instr, str) and instr.strip() and instr not in seen:
            seen.add(instr)
            deduped.append(instr.strip())
    # Trim ke max entry (keep yang paling baru = paling akhir)
    if len(deduped) > INSTRUCT_HISTORY_MAX:
        deduped = deduped[-INSTRUCT_HISTORY_MAX:]
    try:
        import json as _json
        with open(INSTRUCT_HISTORY_FILE, 'w', encoding='utf-8') as f:
            for instr in deduped:
                # JSON-encode supaya newline dalam instruct tidak corrupt file
                f.write(_json.dumps(instr) + '\n')
    except (IOError, OSError) as e:
        print(f'  ⚠ Tidak bisa simpan instruct history: {e}')


def prompt_custom_instruct():
    """Prompt custom instruct dari user. Tampilkan history sebagai quick-reuse.
    Return (instruct_str, label_str) atau (None, None) kalau batal.
    """
    print()
    print('── Custom Instruct ──')
    print('  Ketik instruct sendiri (gender, age, pitch, accent, ...).')
    print('  Valid keyword hint:')
    for line in INSTRUCT_VALID_HINT.split('\n'):
        if line.strip():
            print(f'    {line}')
    print()

    history = load_instruct_history()
    choices = []
    if history:
        # Tampilkan history (paling baru di atas) — max 10 supaya menu tidak panjang
        recent = history[-10:][::-1]
        for instr in recent:
            choices.append(f'  ↻ {instr}')
        choices.append('[Ketik instruct baru]')
    else:
        print('  (Belum ada history — ketik instruct baru.)')
        choices.append('[Ketik instruct baru]')

    choice = questionary.select(
        'Pilih atau ketik custom instruct:',
        choices=choices,
        default=choices[0],
    ).ask()

    if choice == '[Ketik instruct baru]':
        instruct = questionary.text(
            'Instruct (mis: "male, young adult, low pitch"):'
        ).ask()
    else:
        # Strip "  ↻ " prefix
        instruct = choice[4:] if choice.startswith('  ↻ ') else choice

    if not instruct or not instruct.strip():
        print('❌ Instruct kosong, batal.')
        return None, None
    instruct = instruct.strip()

    # Validasi ringan (warning only — tidak blok, biar OmniVoice yang validasi)
    instr_lower = instruct.lower()
    known_gender = any(g in instr_lower for g in ['female', 'male'])
    if not known_gender:
        print(f'  ⚠ Instruct "{instruct}" tidak mengandung keyword gender')
        print(f'    (female/male). OmniVoice mungkin reject. Lanjutkan? ')
        if not questionary.confirm('Lanjut dengan instruct ini?', default=False).ask():
            return None, None

    # Save ke history (append, dedup nanti di save)
    if instruct not in history:
        history.append(instruct)
        save_instruct_history(history)
        print(f'  ✓ Disimpan ke history: {INSTRUCT_HISTORY_FILE}')

    label = f'Custom: {instruct}'
    return instruct, label


def prompt_language(default='id'):
    """Prompt pilihan language untuk model.generate(language=...).
    v0.3 FIX AKSEN — wajib di-pass ke generate(). Default 'id' untuk teks ID.

    Return: kode language ('id'/'jv'/'en'/...) atau 'auto' (None, language-agnostic).
    """
    print()
    print('── Language ──')
    print('  OmniVoice language= — kontrol aksen + phoneme mapping.')
    print('  v0.2 bug: tidak di-pass → model menebak → bisa nyimpang aksen.')
    print('  Default "id" untuk teks Indonesia. Pilih "auto" HANYA kalau teks')
    print('  multi-bahasa atau Anda mau eksplor (resiko aksen drift).')
    print()
    labels = [f'{code} — {name}' for code, name in LANGUAGE_OPTIONS]
    # Pilih default berdasarkan parameter
    default_label = next(
        (f'{code} — {name}' for code, name in LANGUAGE_OPTIONS if code == default),
        labels[0],
    )
    choice = questionary.select(
        'Language target teks:',
        choices=labels,
        default=default_label,
    ).ask()
    # Extract code dari "code — name"
    return choice.split(' — ')[0].strip()


# ============================================================
# Auto Lock helpers (v0.6 — Single Voice Mode)
# ============================================================

def autolock_seed_path(cache_dir, prefix):
    """Path ke seed.wav untuk Auto Lock mode v0.6.

    seed.wav = audio cue 1 (Auto Voice random, trimmed + peak-normalized).
    Di-pass sebagai ref_audio ke generate_cue_audio (mode clone) untuk cue 2-N
    supaya voice cue 2-N = voice cue 1 (1 voice untuk seluruh SRT).

    Lokasi: di cache_dir (bukan output_dir root) supaya ikut di-cleanup bersama
    NPY cache. Survive antar run untuk resume → voice cue 1 tetap sama kalau
    SRT sama dijalankan ulang. Delete seed.wav + re-run untuk acak ulang voice.
    """
    return os.path.join(cache_dir, f'{prefix}-seed.wav')


def autolock_seed_text_path(cache_dir, prefix):
    """Path ke seed.txt untuk Auto Lock mode v0.6.

    seed.txt = transkrip cue 1 (exact text, normalized). WAJIB untuk OmniVoice
    Voice Cloning — model butuh ref_text untuk alignment ref_audio → phoneme.
    Tanpa ref_text → clone gagal (OmniVoice error "ref_text required").
    """
    return os.path.join(cache_dir, f'{prefix}-seed.txt')


def autolock_voice_prompt_path(cache_dir, prefix):
    """Path ke voice_clone_prompt.pt untuk Auto Lock mode v0.6.3.

    voice.pt = VoiceClonePrompt pre-encoded (ref_audio_tokens + ref_text + ref_rms).
    Di-create SEKALI di pre-step via model.create_voice_clone_prompt(ref_audio=
    seed.wav, ref_text=SEED_REF_TEXT), lalu di-load + reuse untuk SEMUA cue via
    model.generate(voice_clone_prompt=prompt). Bypass audio_tokenizer.encode()
    per cue (CPU-bound di MPS — higgs-audio-v2-tokenizer tidak support MPS,
    WAJIB CPU). Ini fix 12x slowdown v0.6.1/v0.6.2 (11m33s → estimasi ~2m).

    Format: PyTorch .pt (torch.save dict). Load via VoiceClonePrompt.load(path).
    Survive antar run untuk resume → load instant (no re-encode). Delete voice.pt
    + re-run untuk re-encode (kalau seed.wav berubah setelah re-roll).

    v0.6.3 NEW — tidak ada di v0.6/v0.6.1/v0.6.2.
    """
    return os.path.join(cache_dir, f'{prefix}-voice.pt')


def select_voice():
    """TUI prompt untuk pilih voice. v0.7: REF AUDIO CLONE ONLY.

    Return voice_config dict:
      {'mode': 'clone', 'ref_audio': '/path.wav', 'ref_text': '...',
       'language': 'id', 'label': 'Clone: filename.wav'}

    v0.7 SIMPLIFY: buang Auto Lock / Auto Voice / Voice Design / Custom Instruct
    (semua punya masalah konsistensi atau kecepatan). Hanya Voice Cloning:
    - User pilih ref WAV (3-25s) dari folder lokal
    - ref_text: auto-load sibling .txt atau ketik manual
    - language: prompt (default 'id')
    - Pre-encode voice_clone_prompt SEKALI di main_srt (v0.6.3 fix 12x slowdown)
      → SEMUA cue reuse prompt → 1 voice konsisten + cepat
    - Clone params: pos_temp=0.0 + guidance=3.0 (v0.6.2 fix drift)
    """
    print('▶ Pilih voice (v0.7 — Voice Cloning only):')
    print('  Ref audio 3-25 detik → clone ke SEMUA cue (1 voice konsisten)')
    print('  voice_clone_prompt encode-once (v0.6.3 fix, no per-cue encode)')
    print('  clone pos_temp=0 + guidance=3 (v0.6.2 fix drift)')
    print()

    # Scan ref audio files di folder lokal
    ref_files = find_ref_audio_files()
    if ref_files:
        labels = []
        for path, name, dur in ref_files:
            dur_str = f'{dur:.1f}s' if dur is not None else '?'
            warn = ''
            if dur is not None and (dur < 3 or dur > 30):
                warn = ' ⚠ outside 3-25s'
            labels.append(f'{name} ({dur_str}){warn}')
        labels.append('[Ketik path manual]')
        ref_choice = questionary.select(
            f'Ref audio (ditemukan {len(ref_files)} file):',
            choices=labels,
            default=labels[0],
        ).ask()
        if ref_choice == '[Ketik path manual]':
            ref_audio = questionary.text('Path ref audio (WAV/MP3/FLAC, 3-25 detik):').ask()
        else:
            idx = labels.index(ref_choice)
            ref_audio = ref_files[idx][0]
    else:
        ref_audio = questionary.text(
            f'Tidak ada file audio di {", ".join(REF_AUDIO_DIRS)}. Ketik path lengkap:'
        ).ask()
    if not ref_audio or not os.path.isfile(ref_audio):
        print(f'❌ File tidak ditemukan: {ref_audio}')
        sys.exit(1)

    # Cek durasi ref audio
    try:
        if HAS_SOUNDFILE:
            info = sf.info(ref_audio)
            dur = info.frames / info.samplerate
            if dur < 3 or dur > 30:
                print(f'⚠ Durasi ref audio {dur:.1f}s — OmniVoice rekomendasi 3-25 detik.')
                print(f'  Kalau >30s mungkin perlu trim dulu.')
            else:
                print(f'  ✓ Durasi {dur:.1f}s (dalam range optimal)')
    except Exception:
        pass

    # Auto-load ref_text dari sibling .txt file kalau ada
    # (mirror pattern: ref_laki.wav + ref_laki.txt → auto-load)
    ref_text = ''
    stem = os.path.splitext(ref_audio)[0]
    for txt_ext in ['.txt', '.transcript', '.text']:
        sibling = stem + txt_ext
        if os.path.isfile(sibling):
            try:
                with open(sibling, 'r', encoding='utf-8-sig') as f:
                    ref_text = f.read().strip()
                print(f'  ✓ Auto-load ref_text dari: {sibling}')
                break
            except Exception:
                pass
    if not ref_text:
        ref_text = questionary.text(
            'Transkripsi ref audio (apa yang diucapkan di ref, exact):'
        ).ask()
    if not ref_text:
        print('❌ Transkripsi wajib (OmniVoice butuh ref_text untuk alignment).')
        sys.exit(1)

    # Language prompt (default 'id')
    language = prompt_language(default='id')
    print(f'  ✓ language: {language}')

    return {
        'mode': 'clone',
        'ref_audio': ref_audio,
        'ref_text': ref_text,
        'language': language,
        'label': f'Clone: {os.path.basename(ref_audio)}',
    }


# ============================================================
# SRT mode (mirror piper-tts-tui main, 6 step)
# ============================================================

def main_srt():
    print_banner()
    print('📋 Mode: SRT (dub per cue dari subtitle)')
    print('   Navigasi: ↑↓ arrow keys, Enter konfirmasi, Ctrl+C batal')
    print()

    # Step 1: SRT
    print('▶ Step 1/6: Pilih SRT')
    if ensure_hdd():
        default_srt_dir = str(INPUT_DIR)
    else:
        default_srt_dir = os.getcwd()
    srt_files = find_srt_files(default_srt_dir)
    if srt_files:
        srt_choice = questionary.select(
            f'File SRT (ditemukan {len(srt_files)} di {default_srt_dir}):',
            choices=srt_files + ['[Ketik path manual]'],
            default=srt_files[0],
        ).ask()
        if srt_choice == '[Ketik path manual]':
            srt_path = questionary.text('Path SRT:').ask()
        else:
            srt_path = os.path.join(default_srt_dir, srt_choice)
    else:
        srt_path = questionary.text(f'Tidak ada SRT di {default_srt_dir}. Ketik path lengkap:').ask()
    if not srt_path or not os.path.isfile(srt_path):
        print('❌ File SRT tidak ditemukan.')
        sys.exit(1)
    print(f'  ✓ {srt_path}')
    print()

    # Step 2: output dir
    print('▶ Step 2/6: Output directory')
    default_out = str(TTS_DIR)
    output_dir = questionary.text('Output directory:', default=default_out).ask()
    if not output_dir:
        output_dir = default_out
    os.makedirs(output_dir, exist_ok=True)
    print(f'  ✓ {output_dir}')
    print()

    # Step 3: voice
    print('▶ Step 3/6: Pilih voice')
    voice_config = select_voice()
    print(f'  ✓ {voice_config["label"]}')
    # v0.7: clone-only. Tampilkan ref_audio + ref_text.
    print(f'    ref_audio: {voice_config["ref_audio"]}')
    print(f'    ref_text : {voice_config["ref_text"][:60]}{"..." if len(voice_config["ref_text"]) > 60 else ""}')
    print(f'    language : {voice_config.get("language", "?")} (DI-LOCK — clone tetap logat ini)')
    print()

    # Step 4: Smart Fit cap
    print('▶ Step 4/6: Smart Fit cap')
    cap_choice = questionary.select(
        'Smart Fit cap (max speed):',
        choices=[
            '1.5x (clean, recommended — verified tidak robotik)',
            '2.0x (cepat, sedikit robotik untuk cue padat)',
            '1.25x (paling natural, lebih sering overflow)',
            'OFF (no smart fit, natural only)',
        ],
        default='1.5x (clean, recommended — verified tidak robotik)',
    ).ask()
    if 'OFF' in cap_choice:
        smart_fit = False
        cap = 1.0
    else:
        smart_fit = True
        cap = float(cap_choice.split('x')[0])
    print(f'  ✓ cap={cap}, smart_fit={smart_fit}')
    print()

    # Step 5: prefix
    print('▶ Step 5/6: Prefix output')
    default_prefix = os.path.splitext(os.path.basename(srt_path))[0]
    prefix = questionary.text('Prefix (output: {prefix}-audio-id-dub.wav):', default=default_prefix).ask()
    if not prefix:
        prefix = default_prefix
    prefix = suggest_unique_prefix(output_dir, prefix)
    print(f'  ✓ {prefix}')
    print()

    # Parse SRT
    with open(srt_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    entries = parse_srt(content)
    if not entries:
        print('❌ SRT kosong/tidak terparse.')
        sys.exit(1)
    total_dur = entries[-1]['end']

    # Step 6: load model
    print('▶ Step 6/6: Load model OmniVoice')
    model, load_time, ep_label = load_omnivoice_model()
    print(f'  ✓ Model loaded ({load_time:.1f}s), EP: {ep_label}')
    print()

    # Estimasi waktu — VERIFIED dari real test 22 Nov 2026:
    #   SRT 1m27s (39 cue) → generate 5m33s = 333s
    #   Per cue (pass 1 + pass 2): 333/39 = 8.5s (smart_fit ON, ~80% cue pass 2)
    #   Per generate: ~5s (test2.py: 11-12s untuk text 5 detik, cue biasanya 2-3s)
    #
    # Rumus: cues × per_generate × (1 + pass2_ratio if smart_fit)
    #   - per_generate: 5s di MPS Mac M1 (RTF ~2.0 untuk text 2-3 detik)
    #   - pass2_ratio: 0.8 (80% cue butuh speedup, verified dari 70 NPY / 39 cue)
    gpu_label, has_mps = get_gpu_status()
    per_generate = 5.0 if has_mps else 15.0  # detik per generate call
    pass2_ratio = 0.8 if smart_fit else 0.0  # 80% cue butuh pass 2
    est_total_sec = len(entries) * per_generate * (1 + pass2_ratio)

    print('═' * 64)
    print('📋 Ringkasan:')
    print('═' * 64)
    print(f'  SRT      : {os.path.basename(srt_path)}')
    print(f'  Output   : {os.path.join(output_dir, prefix + "-audio-id-dub.wav")}')
    print(f'  Voice    : {voice_config["label"]}')
    print(f'  Language : {voice_config.get("language", "?")} (v0.3 fix aksen — pass ke generate)')
    print(f'  Engine   : OmniVoice ({ep_label})')
    print(f'  Speed    : natural (smart fit handles speedup via speed= parameter)')
    print(f'  Smart Fit: {"ON" if smart_fit else "OFF"}, cap={cap}')
    print(f'  Cues     : {len(entries)}')
    print(f'  Durasi   : {format_duration(total_dur)}')
    print(f'  Estimasi : {format_duration(est_total_sec)} (smart_fit={"ON" if smart_fit else "OFF"})')
    # v0.7: clone-only. Voice_clone_prompt encode-once → reuse semua cue.
    print(f'  Language : {voice_config.get("language", "?")} (DI-LOCK — clone tetap logat ini)')
    print(f'  Ref      : {voice_config["ref_audio"]}')
    print(f'  Seed     : {SEED} (determinism — voice konsisten antar cue)')
    print(f'  Decoding : num_step={NUM_STEP}, clone pos_temp={CLONE_POSITION_TEMPERATURE} guidance={CLONE_GUIDANCE_SCALE}')
    print('             voice_clone_prompt encode-once (v0.6.3 fix 12x slowdown)')
    print('═' * 64)
    print()
    print('⚠ NOTE v0.7: Voice Cloning only — 1 voice untuk seluruh SRT.')
    print('  Ref WAV user (3-25s) → voice_clone_prompt.pt (encode SEKALI, CPU ~2-5s).')
    print('  SEMUA cue (1-N): model.generate(voice_clone_prompt=prompt) → NO per-cue encode.')
    print('  v0.6.3 FIX: voice_clone_prompt encode-once (fix 12x slowdown v0.6.1/v0.6.2).')
    print('  v0.6.2 FIX: clone pos_temp=0.0 + guidance=3.0 (v0.6.1 pakai 5.0/2.0 = drift parah).')
    print('  Smart Fit pakai time_stretch (1x generate per cue, audio di-stretch).')
    print()
    print('  Override env (opsional):')
    print('    OMNIVOICE_NUM_STEP=32        (stabil, 2x lebih lambat)')
    print('    OMNIVOICE_SEED=123           (reproducibility)')
    print('    OMNIVOICE_CLONE_POS_TEMP=0.0 (clone greedy lock; 1.0 = slight variation)')
    print('    OMNIVOICE_CLONE_GUIDANCE=3.0 (tighter CFG to ref; 4.0 = very tight)')
    print()

    if not questionary.confirm('Lanjut generate?', default=True).ask():
        print('Batal.')
        sys.exit(0)

    ok, lock_info = acquire_lock(output_dir, prefix)
    if not ok:
        print(f'❌ {lock_info}')
        sys.exit(1)

    try:
        print()
        print('═' * 64)
        print(f'🚀 Mulai generate TTS (OmniVoice {ep_label}) + mix inline...')
        print('═' * 64)
        print()

        cache_dir = os.path.join(output_dir, '.omnivoice-cache')
        os.makedirs(cache_dir, exist_ok=True)

        # v0.6.3 Auto Lock state.
        # seed_wav / seed_txt = path file seed (audio + text) di cache_dir.
        # voice_pt = path ke voice_clone_prompt.pt (pre-encoded prompt, v0.6.3 NEW).
        # prompt = VoiceClonePrompt object (in-memory, reused untuk semua cue).
        # autolock_seed_text = SEED_REF_TEXT (fixed Indonesian ~6s phoneme-rich).
        #
        # v0.6.3 FIX SLOWDOWN: pakai create_voice_clone_prompt() + voice_clone_prompt=
        # (bukan ref_audio= per cue). Source code OmniVoice _preprocess_all():
        #   if voice_clone_prompt is None and ref_audio is not None:
        #       voice_clone_prompt = self.create_voice_clone_prompt(...)  # ENCODE
        # Kalau voice_clone_prompt= di-pass → block SKIP → NO audio_tokenizer.encode()
        # per cue (CPU-bound di MPS, higgs-audio-v2-tokenizer tidak support MPS).
        # v0.6.1/v0.6.2 pass ref_audio= per cue → re-encode 13s audio setiap call
        # → 12x slowdown (11m33s vs 1m v0.5). v0.6.3 encode SEKALI → reuse → ~5x faster.
        # v0.7 SIMPLIFY: pre-encode dari USER ref WAV langsung (bukan generated seed).
        # voice_pt path based on ref_audio content hash supaya beda ref WAV → beda cache.
        prompt = None
        voice_pt = None
        if voice_config['mode'] == 'clone':
            # Hash ref_audio content → unique voice_pt per ref WAV
            ref_hash = ''
            try:
                h = hashlib.md5()
                with open(voice_config['ref_audio'], 'rb') as f:
                    while True:
                        chunk = f.read(8192)
                        if not chunk:
                            break
                        h.update(chunk)
                ref_hash = h.hexdigest()[:12]
            except Exception:
                ref_hash = 'norefh'
            voice_pt = os.path.join(
                cache_dir, f'{prefix}-voice-{ref_hash}.pt')

            print()
            print('▶ v0.7: Encode voice_clone_prompt dari ref WAV (once)')
            # v0.6.3 core fix: encode SEKALI di sini, token simpan ke .pt, reuse
            # untuk semua cue via model.generate(voice_clone_prompt=prompt).
            # Bypass create_voice_clone_prompt() internal → NO per-cue CPU encode
            # (12x slowdown source — audio_tokenizer higgs-audio-v2 tidak support MPS).
            try:
                from omnivoice import VoiceClonePrompt
            except ImportError:
                print('❌ omnivoice package tidak ada — tidak bisa encode voice prompt.')
                sys.exit(1)
            if os.path.isfile(voice_pt):
                print(f'  ✓ Voice prompt existing (resume, no re-encode): {voice_pt}')
                prompt = VoiceClonePrompt.load(voice_pt)
            else:
                print(f'  Ref audio : {voice_config["ref_audio"]}')
                preview = voice_config['ref_text'][:80] + ('...' if len(voice_config['ref_text']) > 80 else '')
                print(f'  Ref text  : "{preview}"')
                print(f'  Encode voice prompt (CPU, sekali saja ~2-5s untuk ref 3-25s)...')
                prompt = model.create_voice_clone_prompt(
                    ref_audio=voice_config['ref_audio'],
                    ref_text=voice_config['ref_text'])
                prompt.save(voice_pt)
                print(f'  ✓ Voice prompt encoded + saved: {voice_pt}')
            print()

        total_samples = int(total_dur * OUTPUT_SAMPLE_RATE)
        if HAS_NUMPY:
            all_audio = np.zeros(total_samples, dtype=np.float32)
        else:
            all_audio = [0.0] * total_samples
        print(f'  Buffer: {total_samples} samples = {total_dur/3600:.1f}j = {total_samples*4/1024/1024:.0f} MB')
        print()

        success_count = 0
        fail_count = 0
        start_time = time.time()
        crossfade_samples = int(OUTPUT_SAMPLE_RATE * CROSSFADE_MS / 1000)

        prev_audio_end_samples = 0

        for i, entry in enumerate(entries):
            cue_idx = i + 1
            text = normalize_tts_text(' '.join(entry['textLines']))
            cue_dur = entry['end'] - entry['start']
            position = int(entry['start'] * OUTPUT_SAMPLE_RATE)

            # Fade in head: crossfade dengan prev ACTUAL audio
            fade_in_start = None
            fade_len = 0
            if i > 0 and position < prev_audio_end_samples:
                overlap = prev_audio_end_samples - position
                fade_in_start = position
                fade_len = min(overlap, crossfade_samples)

            next_entry = entries[i + 1] if i + 1 < len(entries) else None

            if not text:
                prev_audio_end_samples = max(prev_audio_end_samples, position)
                continue

            # v0.7: SEMUA cue clone via voice_clone_prompt (pre-encoded once).
            # prompt object di-pass langsung → model.generate(voice_clone_prompt=prompt)
            # → bypass create_voice_clone_prompt() internal → NO per-cue CPU encode
            # (fix 12x slowdown). ref_audio/ref_text tetap di-include untuk
            # compute_cache_key hash (cache identity = ref WAV content).
            per_cue_vc = {'mode': 'clone',
                          'voice_clone_prompt': prompt,
                          'ref_audio': voice_config['ref_audio'],
                          'ref_text': voice_config['ref_text'],
                          'language': voice_config['language'],
                          'label': voice_config['label']}

            cache_key = compute_cache_key(text, per_cue_vc, speed=1.0)

            try:
                if smart_fit:
                    final_audio = smart_fit_cue(
                        text, cue_dur, model, per_cue_vc, cap,
                        cache_dir, cache_key, prefix, cue_idx,
                    )
                else:
                    natural_npy = os.path.join(cache_dir, f'{prefix}-cue-{cue_idx:04d}-{cache_key}.npy')
                    if not (os.path.isfile(natural_npy) and os.path.getsize(natural_npy) > 0):
                        audio = generate_cue_audio(text, model, per_cue_vc, speed=1.0)
                        if len(audio) == 0:
                            fail_count += 1
                            continue
                        if HAS_NUMPY:
                            np.save(natural_npy, audio)
                    if HAS_NUMPY:
                        raw = np.load(natural_npy)
                    else:
                        import pickle
                        with open(natural_npy, 'rb') as f:
                            raw = pickle.load(f)
                    natural_audio = trim_silence_asymmetric(raw, OUTPUT_SAMPLE_RATE)
                    final_audio = peak_normalize(natural_audio)
            except Exception as e:
                print(f'\n  ⚠ Cue {cue_idx} gagal: {e}')
                fail_count += 1
                continue

            this_audio_end = position + len(final_audio)

            fade_out_end = None
            if next_entry:
                next_start_samples = int(next_entry['start'] * OUTPUT_SAMPLE_RATE)
                if this_audio_end > next_start_samples:
                    fade_out_end = next_start_samples
                    max_end = next_start_samples + crossfade_samples
                    if this_audio_end > max_end:
                        cut_idx = max_end - position
                        if 0 < cut_idx < len(final_audio):
                            final_audio = final_audio[:cut_idx]
                            this_audio_end = position + len(final_audio)
                            if SMART_FIT_DEBUG:
                                print(f'  [cue {cue_idx}] TRUNCATE overflow to {crossfade_samples/OUTPUT_SAMPLE_RATE:.3f}s window')

            mix_into_buffer(all_audio, final_audio, position,
                            fade_out_end=fade_out_end, fade_in_start=fade_in_start, fade_len=fade_len)

            prev_audio_end_samples = this_audio_end
            success_count += 1

            if cue_idx % 5 == 0 or cue_idx == len(entries):
                elapsed = time.time() - start_time
                pct = cue_idx / len(entries) * 100
                eta = (elapsed / cue_idx) * (len(entries) - cue_idx) if cue_idx > 0 else 0
                sys.stdout.write(
                    f'\r  [{cue_idx}/{len(entries)}] {pct:5.1f}% | '
                    f'ok={success_count} fail={fail_count} | '
                    f'elapsed={format_duration(elapsed)} | ETA={format_duration(eta)}   '
                )
                sys.stdout.flush()

        print()
        elapsed = time.time() - start_time
        print()
        print(f'  ✓ Selesai generate: {success_count} cue ok, {fail_count} fail ({format_duration(elapsed)})')

        output_path = os.path.join(output_dir, f'{prefix}-audio-id-dub.wav')
        print(f'  Encoding WAV → {output_path}...')
        encode_wav(all_audio, OUTPUT_SAMPLE_RATE, OUTPUT_CHANNELS, output_path)

        # Cleanup cache (opsional)
        # v0.7: cache_files = NPY (per-cue audio) + voice.pt (encoded prompt).
        # voice.pt reuse cross-run (same ref WAV → same prompt, no re-encode).
        # Hapus voice.pt HANYA kalau ref WAV berubah (hash beda → file beda jg).
        try:
            cache_files = [f for f in os.listdir(cache_dir) if f.startswith(prefix)]
            cache_size_mb = sum(os.path.getsize(os.path.join(cache_dir, f)) for f in cache_files) / 1024 / 1024
            if cache_files:
                npy_count = sum(1 for f in cache_files if f.endswith('.npy'))
                pt_count = sum(1 for f in cache_files if f.endswith('.pt'))
                msg = (
                    f'Hapus cache ({npy_count} NPY + {pt_count} voice.pt, {cache_size_mb:.1f} MB)? '
                    f'(No = simpan untuk resume + reuse voice.pt cross-run)'
                )
                if questionary.confirm(msg, default=False).ask():
                    for f in cache_files:
                        try:
                            os.unlink(os.path.join(cache_dir, f))
                        except OSError:
                            pass
                    try:
                        os.rmdir(cache_dir)
                    except OSError:
                        pass
                    print('  ✓ Cache dihapus (voice.pt juga — re-run = re-encode ref WAV)')
                else:
                    print(f'  Cache disimpan: {cache_dir} ({cache_size_mb:.1f} MB)')
        except Exception:
            pass

        if os.path.isfile(output_path):
            size_mb = os.path.getsize(output_path) / 1024 / 1024
            print()
            print('═' * 64)
            print('✅ SELESAI!')
            print(f'   Output : {output_path}')
            print(f'   Size   : {size_mb:.1f} MB')
            print(f'   Format : {OUTPUT_SAMPLE_RATE}Hz mono 16-bit PCM (mix-tui compatible)')
            print(f'   Engine : OmniVoice ({ep_label})')
            print(f'   Cues   : {success_count} ok / {fail_count} fail / {len(entries)} total')
            print(f'   Waktu  : {format_duration(elapsed)} (model load {load_time:.1f}s + generate)')
            print()
            print('🎬 Langkah berikutnya:')
            print(f'   1. Preview: open {output_path}')
            print(f'   2. Feed ke mix-tui (sama dengan edge-tts/piper-tts SRT output)')
            print('═' * 64)
        else:
            print('❌ Output tidak terbentuk.')

    except KeyboardInterrupt:
        print('\n\n⏹ Dibatalkan user.')
    finally:
        release_lock(output_dir, prefix)


# ============================================================
# Narration mode (mirror piper-tts-tui main_narration, 48kHz stereo)
# ============================================================

def main_narration():
    print_banner()
    print('═' * 64)
    print('🎙️  Narration Mode — naskah plain text → 1 WAV (48kHz stereo)')
    print('═' * 64)
    print()

    # Step 1: naskah
    print('▶ Step 1/6: Pilih naskah (.txt)')
    default_dirs = [str(REVIEW_DIR), str(TTS_DIR)]
    txt_files = []
    for d in default_dirs:
        if os.path.isdir(d):
            txt_files.extend(os.path.join(d, f) for f in os.listdir(d) if f.lower().endswith('.txt'))
    if txt_files:
        txt_files.sort()
        rel_files = [os.path.relpath(f) for f in txt_files]
        choice = questionary.select(
            f'Naskah (ditemukan {len(txt_files)}):',
            choices=rel_files + ['[Ketik path manual]'],
            default=rel_files[0],
        ).ask()
        if choice == '[Ketik path manual]':
            naskah_path = questionary.text('Path naskah .txt:').ask()
        else:
            naskah_path = choice
    else:
        naskah_path = questionary.text('Path naskah .txt:').ask()
    if not naskah_path or not os.path.isfile(naskah_path):
        print('❌ File naskah tidak ditemukan.')
        sys.exit(1)
    with open(naskah_path, 'r', encoding='utf-8-sig') as f:
        naskah = f.read()
    print(f'  ✓ {naskah_path} ({len(naskah)} chars)')
    print()

    # Step 2: output
    print('▶ Step 2/6: Output directory')
    default_out = str(TTS_DIR)
    output_dir = questionary.text('Output directory:', default=default_out).ask()
    if not output_dir:
        output_dir = default_out
    os.makedirs(output_dir, exist_ok=True)
    print(f'  ✓ {output_dir}')
    print()

    # Step 3: voice
    print('▶ Step 3/6: Voice')
    voice_config = select_voice()
    print(f'  ✓ {voice_config["label"]}')
    print()

    # Step 4: speed
    print('▶ Step 4/6: Speed')
    speed_str = questionary.text('Speed (1.0=natural, 1.2=cepat, 0.9=pelan):', default='1.0').ask()
    try:
        speed = float(speed_str)
    except ValueError:
        speed = 1.0
    print(f'  ✓ {speed}')
    print()

    # Step 5: filename
    print('▶ Step 5/6: Output filename')
    stem = os.path.splitext(os.path.basename(naskah_path))[0]
    default_name = f'{stem}-narasi.wav'
    out_name = questionary.text('Output filename:', default=default_name).ask()
    if not out_name:
        out_name = default_name
    output_path = os.path.join(output_dir, out_name)
    print(f'  ✓ {output_path}')
    print()

    # Step 6: load model
    print('▶ Step 6/6: Load model OmniVoice')
    model, load_time, ep_label = load_omnivoice_model()
    print(f'  ✓ Model loaded ({load_time:.1f}s), EP: {ep_label}')
    print()

    # v0.7: pre-encode voice_clone_prompt SEKALI (mirror SRT mode).
    # Narration split per-kalimat → tanpa pre-encode, tiap kalimat re-encode
    # ref audio (CPU-bound, 12x slowdown). Pre-encode → reuse prompt semua kalimat.
    cache_dir = os.path.join(output_dir, '.omnivoice-cache')
    os.makedirs(cache_dir, exist_ok=True)
    ref_hash = ''
    try:
        h = hashlib.md5()
        with open(voice_config['ref_audio'], 'rb') as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                h.update(chunk)
        ref_hash = h.hexdigest()[:12]
    except Exception:
        ref_hash = 'norefh'
    voice_pt = os.path.join(cache_dir, f'narr-voice-{ref_hash}.pt')
    try:
        from omnivoice import VoiceClonePrompt
    except ImportError:
        print('❌ omnivoice package tidak ada — tidak bisa encode voice prompt.')
        sys.exit(1)
    prompt = None
    if os.path.isfile(voice_pt):
        print(f'  ✓ Voice prompt existing (resume): {voice_pt}')
        prompt = VoiceClonePrompt.load(voice_pt)
    else:
        print(f'  Encode voice prompt dari ref WAV (CPU, sekali ~2-5s)...')
        prompt = model.create_voice_clone_prompt(
            ref_audio=voice_config['ref_audio'], ref_text=voice_config['ref_text'])
        prompt.save(voice_pt)
        print(f'  ✓ Voice prompt saved: {voice_pt}')
    print()

    import re
    sentences = re.split(r'(?<=[.!?。])\s+', naskah.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        print('❌ Naskah kosong.')
        sys.exit(1)

    print('═' * 64)
    print('📋 Ringkasan:')
    print(f'  Naskah   : {os.path.basename(naskah_path)} ({len(sentences)} kalimat)')
    print(f'  Voice    : {voice_config["label"]}')
    print(f'  Language : {voice_config.get("language", "?")} (pass ke generate)')
    print(f'  Engine   : OmniVoice ({ep_label})')
    print(f'  Speed    : {speed}')
    print(f'  Output   : {output_path} (48kHz stereo)')
    print(f'  Decoding : num_step={NUM_STEP} pos_temp={POSITION_TEMPERATURE} guidance={GUIDANCE_SCALE}')
    print('═' * 64)
    print()

    if not questionary.confirm('Lanjut generate?', default=True).ask():
        print('Batal.')
        sys.exit(0)

    print(f'🚀 Mulai generate narasi (OmniVoice {ep_label})...')
    print()
    start_time = time.time()

    all_chunks = []
    per_cue_vc = {'mode': 'clone',
                  'voice_clone_prompt': prompt,
                  'ref_audio': voice_config['ref_audio'],
                  'ref_text': voice_config['ref_text'],
                  'language': voice_config['language'],
                  'label': voice_config['label']}
    for i, sent in enumerate(sentences):
        try:
            audio = generate_cue_audio(sent, model, per_cue_vc, speed=speed, target_sr=NARR_SAMPLE_RATE)
        except Exception as e:
            print(f'\n  ⚠ Kalimat {i+1} gagal: {e}')
            continue
        if len(audio) == 0:
            continue
        audio = trim_silence_asymmetric(audio, NARR_SAMPLE_RATE)
        audio = peak_normalize(audio)
        sil = int(NARR_SAMPLE_RATE * 0.2)
        if HAS_NUMPY:
            audio = np.concatenate([audio, np.zeros(sil, dtype=np.float32)])
        else:
            audio = audio + [0.0] * sil
        all_chunks.append(audio)
        if (i + 1) % 3 == 0 or i + 1 == len(sentences):
            elapsed = time.time() - start_time
            pct = (i + 1) / len(sentences) * 100
            sys.stdout.write(f'\r  [{i+1}/{len(sentences)}] {pct:5.1f}% | elapsed={format_duration(elapsed)}   ')
            sys.stdout.flush()
    print()
    print()

    if not all_chunks:
        print('❌ Tidak ada chunk berhasil di-generate.')
        sys.exit(1)

    if HAS_NUMPY:
        final = np.concatenate(all_chunks)
    else:
        final = []
        for c in all_chunks:
            final.extend(c)

    encode_wav(final, NARR_SAMPLE_RATE, NARR_CHANNELS, output_path)
    elapsed = time.time() - start_time

    if os.path.isfile(output_path):
        size_mb = os.path.getsize(output_path) / 1024 / 1024
        print('═' * 64)
        print('✅ SELESAI!')
        print(f'   Output : {output_path}')
        print(f'   Size   : {size_mb:.1f} MB')
        print(f'   Format : {NARR_SAMPLE_RATE}Hz stereo 16-bit PCM (review-mix/konten-tui compatible)')
        print(f'   Engine : OmniVoice ({ep_label})')
        print(f'   Waktu  : {format_duration(elapsed)} (model load {load_time:.1f}s + generate)')
        print()
        print('🎬 Langkah berikutnya:')
        print(f'   Feed ke review-mix-tui / konten-tui / talkinghead-tui / manim-shorts-tui')
        print('═' * 64)


# ============================================================
# Entry
# ============================================================

def main():
    print_banner()
    print('📋 Pilihan: ikuti petunjuk di layar.')
    print('   Navigasi: ↑↓ arrow keys, Enter konfirmasi, Ctrl+C batal')
    print()

    mode = questionary.select(
        'Mode:',
        choices=[
            'SRT (dub per cue dari subtitle)',
            'Narration (1 naskah plain text → 1 WAV)',
        ],
        default='SRT (dub per cue dari subtitle)',
    ).ask()

    if 'Narration' in mode:
        main_narration()
    else:
        main_srt()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n\n⏹ Dibatalkan user.')
        sys.exit(130)
