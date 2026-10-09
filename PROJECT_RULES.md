# PROJECT_RULES.md — Aturan Project SRT Splitter + Dubbing

> 15 rules minimal, project-specific. Baca tiap session sebelum kerja.
> Konflik antar dokumen? File ini menang.

## Aturan Dokumentasi (paling penting, biar gak lupa)

### R-01 — Baca docs dulu sebelum jawab
Sebelum jawab pertanyaan user, baca `AGENTS.md` + `README.md` + `scripts/README.md`. User sering nanya "baca dokumentasi, cek sync" — jangan skip atau kamu akan kasih info yang salah/outdated.

### R-02 — Update docs tiap workflow berubah
Setiap perubahan workflow (tambah fase, ganti format output, ubah step), wajib update:
- `README.md` (root) — section workflow + tabel scripts + status
- `scripts/README.md` — detail per script + workflow commands
- `AGENTS.md` — status pipeline terkini + marker
- Docstring script yang bersangkutan

### R-03 — Status marker konsisten
Pakai 5 marker ini di semua docs (README, AGENTS.md, worklog, comment):
- `✅` sudah jalan / siap pakai
- `⏳` nunggu dependency atau user input
- `⚠️` deprecated / backup / ada masalah known
- `❌` gagal / blocker
- `🔧` maintainer-only

Jangan campur aduk (mis. "done" vs "selesai" vs "✅"). Pilih satu, konsisten.

### R-04 — Jangan hapus section docs tanpa konfirmasi
Kalau ada section di README/AGENTS.md yang kelihatan outdated, tanyakan dulu sebelum hapus. Mungkin user simpan sengaja buat history. Edit boleh, hapus tanya dulu.

## Aturan Workflow

### R-05 — Workflow 4 fase (urutan tidak boleh diubah)
```
Fase 1: yt-dlp-tui.py    → MP4 + audio.wav (terpisah)
Fase 2: demucs-tui.py    → no_vocals.mp3 (MP3 320 kbps, vokal auto-hapus)
Fase 3: web app          → audio-{lang}-dub.wav
  3a: Mode ON (ID) — sudah jalan, default voice Dimas
  3b: SRT editor (Jawa) — nunggu code fix + kamus Supabase
Fase 4: mix-tui.py       → mp4-{lang}-final.mp4
```
Jangan tambah fase baru tanpa update `README.md` workflow section + `AGENTS.md` status.

### R-06 — Format output Demucs = MP3 320 kbps
Output Demucs wajib MP3 320 (bukan WAV). Alasan:
- WAV 2 jam = 1.3 GB (boros)
- MP3 320 2 jam = 140 MB (10x lebih kecil)
- Source dari yt-dlp sudah lossy (Opus/MP3) → MP3 320 cukup
- SFX (musik/efek/ambience) bukan dialog → ear gak sensitif

Vocals.wav auto-hapus di akhir Demucs (gak dipakai untuk dubbing).

### R-07 — mix-tui.py input: MP4 + no_vocals + audio_dub
6 step linear, tidak boleh ada branch mode:
1. MP4 ori (video, dari yt-dlp)
2. no_vocals (mp3/wav/flac — backward-compatible)
3. audio_dub (wav dari web app)
4. Ducking level (12 dB default, sidechaincompress)
5. Output filename (default `mp4-id-final.mp4`)
6. Konfirmasi

Ducking via FFmpeg `sidechaincompress` (dub trigger kompres SFX). No-ducking via `amix`.

### R-08 — File path conventions
- Script Python: `/home/z/my-project/scripts/<name>.py`
- Deliverable user: `/home/z/my-project/download/<name>`
- Worklog multi-agent: `/home/z/my-project/worklog.md`
- Jangan tulis file di `/tmp`, `~`, atau luar base path

## Aturan Kode

### R-09 — TUI script pattern (questionary)
Setiap TUI script baru ikut pola `demucs-tui.py` / `mix-tui.py`:
- `print_banner()` dengan border box `╔═╗ ║ ╚═╝`
- Step-by-step dengan numbering (`▶ Step 1/N:`)
- Arrow key navigation via `questionary.select()`
- Confirmation step terakhir sebelum eksekusi
- Ringkasan dengan box border sebelum execute
- Exit code handling: 0 sukses, 130 user cancel, 1 error

### R-10 — Tanya kalau ragu, jangan asumsi
Kalau user bilang "edit code" tapi gak jelas file mana, tanya. Kalau workflow minta file yang gak ada, tanya. Kalau output format ambigu, tanya. Lebih baik 1 round pertanyaan daripada kerja ulang.

## Aturan Eksekusi

### R-11 — Jangan eksekusi kalau diminta jangan
User sering bilang "jangan eksekusi code, edit saja". Artinya: tulis/edit file, jalan `python3` tidak. Hanya eksekusi kalau user bilang "jalankan" / "test" / "eksekusi".

### R-12 — Sebelum bilang "selesai", verifikasi
Wajib cek sebelum claim done:
- [ ] Script/file edited (Read tool konfirmasi)
- [ ] Docs yang relevan update (README/scripts/README/AGENTS.md)
- [ ] Status marker di AGENTS.md update kalau pipeline berubah
- [ ] Tidak ada asumsi "pasti jalan" — kalau gak test, bilang "belum di-test"
- [ ] Git status jelas (commit/push kalau user minta, jangan auto-push)
- [ ] **Verifikasi ISI data, bukan cuma hitung count**. Kalau bilang "279 siap upload",
      wajib baca sample entries (minimal 20) untuk konfirmasi:
      - arti = Indonesia, BUKAN loopback ke ngoko/krama (self_ref)
      - arti tidak ada artifact (paren, colon, dup, capital, <br>)
      - arti tidak terlalu panjang (>60 char = definisi ensiklopedis, bukan sinonim)
      - keterangan (Jawa asli) dipertahankan, jangan dibuang
      Kalau data kacau = parsing AI tolol dan ngawur. Fix dulu, baru claim ready.
- [ ] **JANGAN pakai placeholder seperti "(lengkap)" di laporan tabel**. Wajib tampilkan
      data real untuk SEMUA baris. Kalau baris terlalu banyak, batasi jumlah baris
      yang ditampilkan (mis. max 10 sample), tapi setiap baris harus berisi data
      sebenarnya, bukan ringkasan placeholder. User gak bisa validasi dari "(lengkap)".
- [ ] **Test corner case untuk kategori khusus** (angka, imbuhan, sinonim, dst.):
      - Angka Jawa sering punya arti Indonesia == krama (mis. telu/tiga/tiga).
        SELF_REF check harus skip kalau is_angka=True, atau angka akan kosong.
      - Imbuhan (-a, -ake) gak punya arti Indonesia → biarkan kosong, jangan
        paksa isi.
      - Sinonim dari dasanama campur register → biarkan di ngoko, user sort manual.
- [ ] **JANGAN anggap ejaan Jawa modern sebagai typo**. Ejaan baku Jawa modern
      pakai diakritik khusus:
      - `ĕ` (e-breve, U+0115) = e pepet (mis. 'mĕlèk' = 'terjaga')
      - `ê` (e-circumflex, U+00EA) = e taling
      - `è` (e-grave) = e dialek tertentu
      - `é` (e-acute) = e taling sering dipakai
      Jangan bilang "typo/aneh" cuma karena diakritik non-ASCII. Itu ejaan
      baku, bukan kesalahan. AI gak paham ejaan Jawa, jangan halu klaim typo.
- [ ] **JANGAN halu: beda kata sinonim Indonesia = beda arti**.
      'bakti' dan 'hormat' adalah SINONIM (arti sama, kata beda).
      'bakti' ≈ 'hormat' ≈ 'kesetiaan' ≈ 'pengabdian' — semua valid sebagai arti.
      Kalau draft bilang `bekti → hormat` dan Lampiran bilang `bekti → bakti`,
      KEDUANYA BENAR. Jangan klaim draft salah hanya karena beda kata.
      AI gak paham konteks semantik Indonesia, jangan halu klaim "arti salah"
      hanya dari perbandingan string parsing. User yang putuskan mana sinonim
      yang mau dipakai saat upload Supabase.
- [ ] **Upload ke Supabase = USER wajib validasi satu-satu**. AI gak boleh bilang
      "198 siap upload, langsung upload batch". AI cuma audit sample, USER yang
      validasi semua entries sebelum upload.
      Workflow:
      1. AI: bersihkan data + audit sample → kasih count + sample
      2. USER: buka kamus-tui.py → browse READY entries → validasi 1-1
      3. USER: edit yang salah, save
      4. USER: setelah yakin, upload batch ke Supabase
      Supabase = ground of truth, hanya entries yang USER approved boleh masuk.

### R-13 — Git sync wajib tiap session start
Di awal session (chat pertama, sebelum kerja apapun):
1. `git fetch origin` untuk update info remote
2. `git status -sb` untuk lihat status branch
3. Resolusi sesuai hasil:
   - `## main` (clean, no diff) → up-to-date, lanjut kerja
   - `## main...origin/main [behind N]` → `git pull origin main` (auto, aman)
   - `## main...origin/main [ahead N]` → tanya user "push N commit?", jangan auto-push
   - `## main...origin/main [diverged]` → tanya user, jangan auto-resolve
   - `?? file` (untracked) → tanya user sebelum add, jangan auto-add

Tidak boleh auto-push. Tidak boleh auto-resolve diverge. Tidak boleh auto-add untracked file.

Setelah commit + push, wajib cek `git status -sb` lagi konfirmasi `## main` (clean).

### R-14 — User download file via curl, bukan git pull
User di MacBook pakai `curl` untuk download individual file dari GitHub raw URL, BUKAN `git pull`. Folder `~/Dubbing/` di MacBook bukan git repo, cuma working folder.

Setiap selesai commit + push, AI WAJIB kasih **curl command siap paste** ke user, format:
```bash
curl -L -o <filename> "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/<path>?v=N"
```

User tinggal paste ke terminal MacBook. Jangan pernah kasih raw URL mentah — zsh akan reject karena `?` di-parse sebagai glob (`zsh: no matches found`).

HANYA kasih curl command untuk file yang user JALANKAN di MacBook. Skip file yang cuma dipakai AI di sandbox (mis. `build-kamus-bersih.py`, `scrape-wiktionary-jv-lemma.py`, `parse-wiktionary-jv.py` — itu script generator, user gak perlu). Jangan kasih banyak link, kasih cuma yang user butuh.

Keterangan:
- `<filename>` = nama file lokal di MacBook (mis. `demucs-tui.py`)
- `<path>` = path file di repo (mis. `scripts/demucs-tui.py`)
- `?v=N` = cache buster, increment setiap update (v=1, v=2, v=3, ...) supaya gak ambil dari cache
- Jangan pernah suruh user `git pull origin main` — gak relevant di setup MacBook
- Selalu pakai tanda kutip di sekitar URL (supaya `?` gak di-parse zsh sebagai glob)

### R-15 — Catat ke PROJECT_RULES, jangan cuma bilang "aku catat"
Kalau AI bilang "aku catat note" / "note untuk diriku" / "next time aku inget" — WAJIB langsung tulis ke `PROJECT_RULES.md` atau `AGENTS.md` di sesi yang sama. Kalau cuma diucapkan tapi gak ditulis, AI akan halu di session berikutnya (user ngulang-ngulang instruksi 1000x).

Workflow:
1. AI ucapkan note
2. AI langsung Edit/Write ke PROJECT_RULES.md atau AGENTS.md
3. AI commit + push
4. AI kasih command curl ke user

Jangan pernah: ucapkan note → tutup sesi → harap ingat di sesi berikutnya. Itu gagal.

### R-16 — Raw files DIHAPUS dari repo (R-22 override)

User 9 Okt 2026: "HAPUS SEMUA SCRIP PARSER TOLOL RAW, HAPUS DOKUMEN TOLOL RAW. SISAKAN HANYA SUMBER NETRAL."

**Status raw files** (R-22 override R-16 lama):
- SEMUA raw files DIHAPUS dari repo + dari disk:
  - kamus-jawa-full.json + .gz (legacy, parser tolol)
  - angka-raw.json (parser tolol)
  - lampiran-raw.json, lampiran-angka-raw.json (parser tolol)
  - dasanama-raw.csv (parser tolol)
  - kamus-jawa-mendeley-raw.json (parser tolol)
  - kamus-jawa-new-lemma.json (parser tolol)
  - audit-suspects.json (audit dari raw = tolol)
  - kamus-jawa-draft-report.txt, kamus-jawa-scrape-report.txt (parser tolol)
- SEMUA scraper/parser script DIHAPUS (bukan DISABLE, HAPUS):
  - parse-wiktionary-jv.py
  - scrape-wiktionary-jv-lemma.py
  - scrape-lampiran-kamus.py
  - scrape-lampiran-angka.py
  - add-entry-id.py
  - build-kamus-bersih.py
- SEMUA fix script yang apply ke raw DIHAPUS:
  - fix-angka-ejaan.py, fix-draft-angka-ejaan.py (apply ke angka-raw)
  - fix-angka-5-native-jawa.py, fix-dhingkluk.py, neutralize-kamus-draft.py (one-off, sudah di-apply)
  - audit-otomatis-suspect-patterns.py (audit dari raw pattern = tolol)

**Yang TETAP ada**:
- `public/kamus-jawa-draft.json` (R-20: rujukan tunggal, NETRAL)
- `scripts/kamus-tui.py` (TUI editor, BANTU workflow user)
- `scripts/upload-supabase.py` (upload script, user-triggered only)
- `scripts/yt-dlp-tui.py` + `demucs-tui.py` + `mix-tui.py` (workflow dubbing, BUKAN kamus)
- `scripts/srt-frequency-analyzer.py` (analyzer SRT, pakai DB Supabase)
- `scripts/supabase-migration-v2.sql` + `v3.sql` (SQL untuk DB)
- `scripts/tutor-*.md` + `README.md` (dokumentasi)
- Web assets: `public/logo.svg`, `public/robots.txt`, `public/coi-serviceworker.js`, `public/kamus-viewer.html`

**Prinsip**: Kamus-draft.json = NETRAL (buta, word tanpa definisi). BUKAN sumber kebenaran.
User validasi 1-1 via TUI → status='ready' → upload ke Supabase → Supabase = ground of truth.

### R-16a — Ejaan Jawa (diakritik é/è wajib, schwa polos "e")

Jawa modern pakai 3 diakritik untuk vokal "e":
- **é** = /e/ close-mid (kayak "e" di "kayu"). Contoh: `séket` (50), `séwu` (1000), `limangéwu` (5000), `éka` (Sanskrit 1), akhiran `wé` di `sèlawé`.
- **è** = /ɛ/ open-mid (kayak "e" di "lemari"). Contoh: awalan `sè` di `sèlawé` (25).
- **ê** = /ə/ schwa (kayak "e" di "telu"). **Jawa modern tulis polos "e" TANPA diakritik**. Contoh: `telu`, `enem`, `sepuluh`, `sewelas`, `sedasa`, `sekawan`, `setunggal`, `sewidak`, `selikur`, `ewu`, `welas`.

Catatan: R-16a adalah panduan teknis saja. R-22 (GIGO) tetap berlaku — AI TIDAK audit/fix ejaan dari raw. User native Jawa yang putuskan ejaan saat validasi via TUI.

### R-17 — Skema field kamus: ngoko + krama + arti (krama_inggil masuk krama)

Skema field final kamus-jawa-draft.json (per user 9 Okt 2026):

| Field | Isi | Sumber |
|-------|-----|--------|
| `ngoko` | ngoko + sinonim ngoko (comma) | jv.wiktionary, id.wiktionary, Mendeley, Lampiran |
| `krama` | krama + kramainggil + sinonim (comma) | Mendeley (kramaalus + kramainggil), jv.wiktionary, Lampiran |
| `krama_inggil` | KOSONG (TIDAK DIPAKAI) | — |
| `arti` | arti Indonesia | Mendeley (curated), Wiktionary, AI komposisi |
| `keterangan` | keterangan tambahan | semua sumber |
| `is_angka` | bool | true untuk angka 1-1000 |
| `status` | draft/ready | user validate via TUI |

Alasan `krama_inggil` jadi 1 field `krama`: user spec 9 Okt — dataset kita = ngoko, arti, krama. Tidak perlu pisah krama vs kramainggil karena TTS/dubbing mau pakai tingkat tutur yang sama (krama sudah mencakup kramainggil sebagai bentuk sopan).

Audit 9 Okt 2026 v2.1: 955/955 (100%) Mendeley entries dengan `kramainggil` SUDAH ter-merge ke field `krama` di draft. 1.036 draft entries punya ≥1 kramainggil word di krama (mis. `mangan` krama=`nedha, dhahar`; `turu` krama=`tilem, sare`; `aba` krama=`aba, dhawuh`).

Build script `build-kamus-bersih.py` line 441-446: gabung `kramaalus + kramainggil` jadi `krama` dengan dedup word-level.

JANGAN:
- Buat field baru `krama_inggil` terpisah di Supabase — pakai field `krama` saja.
- Pisahkan kramainggil dari krama saat upload — akan hilang sinonim.
- Audit laporkan "krama_inggil: 0 entries" sebagai masalah — itu BY DESIGN, bukan bug.

### R-18 — JANGAN HAPUS entry kamus (kosong/aksara/keterangan-only TETAP DISIMPAN)

Filosofi kamus (per user 9 Okt 2026): **data ada, cuma tinggal lengkap atau tidak, lalu valid atau tidak**.

JANGAN HAPUS entry meski:
- ngoko + krama + arti semua kosong (cuma keterangan tersisa)
- ngoko = aksara Jawa (ꦏꦼꦧꦪꦤ꧀, dst.) — TETAP SIMPAN, aksara Jawa itu valid
- arti = parsing artifact (`}}`, `<sup>...</sup>`) — FIX arti-nya (kosongkan atau isi manual), jangan hapus entry-nya
- Hanya keterangan yang berisi (entry kosong parsing bug) — TETAP SIMPAN, nanti user/AI lengkapi

Alasan:
1. Kamus ini akan jadi "deterministik" terjemahan Indonesia → ngoko → krama paling lengkap, melebihi Wiktionary/Wikipedia kamus. Kamus umum di luar sana ngoko+krama tercampur tidak terstruktur. Kamus kita = terstruktur per field (ngoko, krama, arti).
2. Dari 44.000+ entries, dalam 1-6 bulan ke depan, mungkin cuma 10.000 yang masuk Supabase (lengkap + terverifikasi). Sisanya tetap di draft sebagai "benih" — bisa di-enrich entah kapan.
3. Hapus entry = hilang jejak data. Sebaliknya: TANDAI status='draft', biarkan di file, nanti di-enrich atau diisi manual lewat TUI.

Aksi yang BENAR saat ketemu entry bermasalah:
- Arti > 30 chars → pindah definisi ke keterangan, pendekkan arti (R-12)
- Arti parsing artifact (`}}`, `<sup>`) → kosongkan arti, keterangan tetap
- Empty entries (no ngoko/krama/arti) → isi ngoko/arti dari keterangan kalau bisa (parsing fix), kalau tidak → biarkan dengan status='draft'
- Aksara Jawa entry → TETAP SIMPAN, arti yang artifact dikosongkan, keterangan tetap
- 2 senses dalam 1 entry → jangan split otomatis, biarkan user decide via TUI (split manual atau biarkan)

Yang BOLEH dihapus (pengecualian):
- Entry DUPLIKAT persis (semua field identik) — deduplikasi pure, bukan data hilang
- Artifact yang BUKAN data (mis. file `.bak`, output terminal `tool-results/bash_*.txt`)

Build script cleanup_misplaced_krama + fix_angka_ngoko + post-process: tetap jalan, tapi SKIP entries kosong — jangan hapus.

### R-19 — Parser AI agresif merge → user wajib validasi ulang 1-1

AKU TANGGUNG JAWAB: build-kamus-bersih.py parser agresif merge multi-source (Wiktionary, Mendeley, Lampiran, Dasanama). Banyak Indonesia word nyangkut sebagai "sinonim Jawa" (mis. `anak lutung` di entry `kowe`, `payung/payon` di entry `payu`, `pimpinan desa` untuk `kami tuwa`). User harus validasi ulang 1-1 karena parsing tolol.

Pattern suspect (audit 9 Okt 2026, 205 entries suspect dari 45.021):

1. **parsing_artifact_ngoko** (~62 entries): Indonesia word nyangkut di ngoko (`anak`, `payung`, `payon`, `panas`, `tuwa` — kadang valid sebagai compound seperti "anak bapak", tapi curiga di entry non-Compound)
2. **parsing_artifact_arti** (~15 entries): Arti Indonesia non-baku/aneh (`sugi`, `beridiri` typo, `bercermin` untuk ilo yang sebenarnya "penglihatan", `pimpinan desa` untuk kami tuwa yang sebenarnya "sesepuh", `anak lutung` parsing artifact)
3. **krama_inggil_no_tag** (~28 entries): Krama inggil words di krama field (per R-17 OK masuk krama, tapi user perlu tahu ini krama inggil vs krama biasa — `dhawuh`, `duka`, `dumugi`, `sare`, `dhahar`, `nedha`, dll.)
4. **too_many_ngoko_synonyms** (~85 entries): ngoko dengan >8 sinonim (rawan merge artifact, mis. entry `banyu` punya 17 sinonim campur Sanskrit + Kawi + modern)
5. **too_many_krama_synonyms** (~15 entries): krama dengan >3 sinonim (rawan merge artifact, mis. `arep` punya 7 krama sinonim: `ajeng, badhé, ngarep, ingajeng, doyan, kersa, ngajeng`)

Audit script: `scripts/audit-otomatis-suspect-patterns.py` (idempotent, re-run kapan saja setelah build update). Output: `public/audit-suspects.json` (untuk user reference, bukan data kamus).

Aksi yang BENAR saat user validasi (R-18 — JANGAN HAPUS):
- Suspect parsing artifact → user lihat di TUI, edit manual: hapus kata Indonesia dari sinonim, sisakan kata Jawa valid
- Krama inggil di krama → biarkan (per R-17 OK), tapi user bisa tag manual kalau mau pisah
- Too many synonyms → user pilih mana sinonim yang valid, hapus yang artifact

JANGAN:
- Bikin script auto-fix yang hapus kata dari sinonim → bisa rusak data valid (R-18)
- Upload ke Supabase tanpa user validasi 1-1 (R-12)
- Skip audit script setelah build update — wajib re-run

Wajib:
- Setelah `build-kamus-bersih.py` jalan, jalankan `audit-otomatis-suspect-patterns.py`
- Lampirkan `public/audit-suspects.json` ke user saat suggest upload batch
- User buka kamus-tui.py → browse entries index di suspect list → validasi/edit manual

### R-20 — kamus-jawa-draft.json = satu-satunya rujukan (raw DISABLED)

Per user 9 Okt 2026: "pasca data json jadi netral, maka referensi ke raw = tidak berlaku, karena kalau raw masih ada definisi, di next sesi AI akan halu lagi dengan parsing tolol."

**Status script**:
- `scripts/build-kamus-bersih.py` → **DISABLED** (rename `.DISABLED` + README besar)
- `scripts/build-kamus-bersih.py.DISABLED.README.md` — JANGAN RUN, alasan + alternatif
- Raw files tetap ada di `public/` sebagai ARSIP (R-16 jangan hapus), TAPI bukan rujukan

**Rujukan tunggal**: `public/kamus-jawa-draft.json` (v2.3+ — pasca neutralize)
- Field `word` = entri NETRAL (belum terdefinisi register)
- Field `ngoko`/`krama`/`arti` hanya untuk entries yang SUDAH PAIRED

**Yang BOLEH dengan raw**:
- Read-only untuk referensi konteks (lihat keterangan asli)
- Cross-check kalau user tanya "data ini dari mana?"
- Archive — bukan untuk rebuild

**Yang DILARANG**:
- Run `build-kamus-bersih.py.DISABLED` (akan overwrite draft dengan data rusak lagi)
- Modifikasi raw files (kecuali tambah data baru per R-16)
- Bikin script baru yang parse raw dengan parser tolol lama
- Rebuild dari raw untuk "memperbaiki" data — gunakan TUI/manual

**User fallback** (kalau nemu kata belum dikenali di kamus):
- Cari manual di kamus resmi Kemendikbud: https://kesakata.kemdikbud.go.id
- Atau https://bahasa.kemdikbud.go.id
- Atau Wiktionary online langsung (jangan batch scrape)
- Setelah ketemu → user edit manual via TUI, AI bantu tapi jangan auto-merge

### R-21 — Field 'word' = entri netral, belum terdefinisi register

Per user 9 Okt 2026: "DATA kamus draf json sudah rusak, dengan mendefiniskan ngoko - padahal belum diketahui. bersihkan data kamus draft yg belum berpasangan jadi word umum (netral), saya dan ai belum tau ini ngoko atau bukan."

**Skema field kamus-jawa-draft.json v2.3+**:

| Field | Isi | Kapan diisi |
|-------|-----|-----------|
| `word` | kata netral (string) | Entry BELUM punya pasangan verified |
| `ngoko` | ngoko (sinonim comma) | Entry SUDAH punya pasangan (krama atau arti) |
| `krama` | krama + kramainggil (comma) | Entry SUDAH punya pasangan (ngoko atau arti) |
| `arti` | arti Indonesia | Entry SUDAH punya pasangan (ngoko atau krama) |
| `keterangan` | keterangan Jawa + Indonesia | SELALU ada (PERTAHANKAN, R-18) |
| `aksara` | aksara Jawa | PERTAHANKAN kalau ada |
| `register` | 'umum' (netral) / 'ngoko' / 'krama' | Default 'umum', user override via TUI |
| `sumber` | sumber data | PERTAHANKAN |
| `is_lemma` | bool (Wiktionary lemma tag) | PERTAHANKAN |
| `is_angka` | bool (angka 1-1000) | true untuk angka entries |
| `status` | 'draft' / 'ready' | User validate via TUI |

**Aturan isi field**:
- Entry punya `word` = BELUM terdefinisi (netral, register='umum')
- Entry punya `ngoko` non-empty = SUDAH terdefinisi sebagai ngoko (paired dengan krama/arti)
- Entry punya `krama` non-empty = SUDAH terdefinisi sebagai krama (paired dengan ngoko/arti)
- Entry dengan `word` + `ngoko` + `krama` + `arti` semua = INCONSISTENT, harus di-fix

**Workflow user di TUI** (per user 9 Okt):
1. User browse entry `word` (netral)
2. User cari pasangan: kalau tahu ngoko → isi `ngoko`, kalau tahu krama → isi `krama`, kalau tahu arti → isi `arti`
3. Setelah 2 dari 3 field terisi (paired) → `word` otomatis pindah ke field yang sesuai (atau biarkan sebagai alias)
4. Setelah 3-field lengkap → status='ready', siap upload Supabase

**Aturan angka 1-1000** (contoh 3-pasangan terdefinisi):
- Angka sudah punya ngoko + krama + arti (3-pasangan lengkap)
- Status tetap 'draft' — user tetap validasi manual di TUI (R-12)
- Angka = contoh sederhana yang membuat AI paham konsep ngoko-krama-arti
- AI tidak bingung lagi setelah lihat angka 1-1000 (semua 3-pasangan terdefinisi)

JANGAN:
- Asumsi `word` = ngoko (BELUM terdefinisi, bisa jadi krama/kawi/loanword)
- Isi `ngoko` kosong dengan tebakan AI (parser tolol, R-19)
- Hapus entry `word` (R-18 — TETAP SIMPAN, user validasi manual nanti)

### R-22 — GIGO: AI tidak merujuk source raw untuk audit/fix kamus-draft

User 9 Okt 2026: "GERBANGE IN GERBANGE OUT. SAMPAH YG MASUK = SAMPAH YG KELUAR. INI PRINSIP FISIKA DAN MATEMATIKA MESIN. KECUALI AI DILATIH PAKE RATUSAN RIBU DATASET JAWA, SELAMA INI OTAK AI TENTANG JAWA = DILATIH PAKE DATA SAMPAH-SAMPAH INTERNET = HASILNYA TOLOL."

**Prinsip GIGO (Garbage In Garbage Out)**:
- Otak AI tentang Jawa = dilatih dari dataset internet = sampah parsing tolol
- Raw files (kamus-jawa-full.json, lampiran-raw.json, dasanama-raw.csv, angka-raw.json, kamus-jawa-mendeley-raw.json, lampiran-angka-raw.json, kamus-jawa-new-lemma.json) = HASIL PARSING AI TOLOL dari internet sampah
- AI TIDAK boleh merujuk raw files untuk AUDIT atau FIX kamus-draft.json
- AI TIDAK boleh cross-check kamus-draft dengan raw untuk "validasi"
- AI TIDAK boleh ambil sinonim/arti dari raw untuk enrich kamus-draft
- AI TIDAK boleh re-generate raw (semua scraper/build script DISABLED)

**Yang AI BOLEH lakukan** (bantu workflow, BUKAN audit data):
- Statistik kamus-draft.json (count NETRAL, ready, paired, dll.)
- Scan pattern di kamus-draft (entries dengan pattern X)
- Compare kamus-draft vs DB Supabase (apa sudah masuk, apa belum) — READ-ONLY DB
- Tunjukin isi entries dari kamus-draft kalau user minta
- Maintenance script TUI + upload-supabase.py (bug fix, bukan data fix)
- Kasih curl command untuk user download file

**Yang AI DILARANG**:
- Upload ke Supabase (R-12: user explicit 'y' saja)
- Audit data draft dengan compare ke raw (R-22: raw = sampah)
- Fix data draft dengan mengambil dari raw (R-22: GIGO)
- Asumsi sinonim dari keterangan (keterangan = parsing tolol juga)
- Rekomendasi ejaan dari Wiktionary (Wiktionary = source raw)
- Ngeyel dengan "pengetahuan akar kata" AI (otak AI = sampah internet)

**Status raw files di repo**:
- Tetap di `public/` sebagai ARSIP (R-16 jangan hapus)
- TIDAK boleh di-load oleh script aktif (TUI/upload/fix)
- Scraper/generator DISABLED: `parse-wiktionary-jv.py.DISABLED`, `scrape-*.py.DISABLED`, `add-entry-id.py.DISABLED`
- Build script DISABLED: `build-kamus-bersih.py.DISABLED` (R-20)

**Fix script compliance** (R-22):
- Fix script hanya apply ke `kamus-jawa-draft.json` (R-20: rujukan tunggal)
- Fix script TIDAK boleh apply ke `angka-raw.json` atau raw lain
- Kalau ada fix script yang masih load raw → hapus reference raw, hanya apply ke draft

**Perlahan database Supabase jadi ground of truth**:
- User upload entries approved via TUI (status='ready')
- Setelah 100, 1000, 10.000 entries di DB, AI bisa:
  - Compare draft vs DB (mana yang belum masuk)
  - Statistik dari DB (top 100 kata di SRT yang belum di DB)
  - Frequency analyzer pakai DB, bukan draft lokal
- AI tidak pernah upload — user selalu putuskan

---

## Catatan untuk AI

- User bukan coder. Jawaban teknis perlu di-explain sederhana.
- User sering paste output terminal (ls, ffmpeg, error). Baca teliti, jangan skip.
- Bahasa default: Indonesia (casual, gak formal kaya dokumentasi).
- User makasih kalau AI proaktif bilang "aku update docs X, Y, Z soal perubahan ini" — bukan AI nunggu disuruh.
