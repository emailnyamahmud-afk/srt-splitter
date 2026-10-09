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

### R-16 — Ejaan Jawa: diakritik é/è wajib, schwa polos "e"

Jawa modern pakai 3 diakritik untuk vokal "e":
- **é** = /e/ close-mid (kayak "e" di "kayu"). Contoh: `séket` (50), `séwu` (1000), `limangéwu` (5000), `éka` (Sanskrit 1), akhiran `wé` di `sèlawé`.
- **è** = /ɛ/ open-mid (kayak "e" di "lemari"). Contoh: awalan `sè` di `sèlawé` (25).
- **ê** = /ə/ schwa (kayak "e" di "telu"). **Jawa modern tulis polos "e" TANPA diakritik**. Contoh: `telu`, `enem`, `sepuluh`, `sewelas`, `sedasa`, `sekawan`, `setunggal`, `sewidak`, `selikur`, `ewu`, `welas`.

Aturan praktis audit angka:
1. Sanskrit loan yang masih /e/ close-mid → wajib **é** (mis. `eka` → `éka`).
2. Kata native Jawa dengan schwa → polos "e", JANGAN tambah diakritik (mis. `telu`, `enem`, `sepuluh`).
3. Wiktionary baku: `séket` (50), `séwu` (1000), `sèlawé` (25), `limangéwu` (5000) — sudah pakai diakritik benar di angka-raw.json v6.1+.

Krama-only words (JANGAN taruh di ngoko):
`éka, dwi, hastha, asta, catur, ponco, panca, sad, sapta, tri, nawa, nowo, songo, doso, yuta, sékawan`

Ngoko words (JANGAN taruh di krama, KECUALI yang betul dipakai di dua register):
`papat, papat, lima, enem, pitu, wolu, sanga` — sanga & wolong dipakai di dua register.

Verifikasi per angka WAJIB cek isi data (R-12), bukan asumsi dari pola komposisi AI-generated. Setiap angka punya potensi anomali (mis. `séket` (50), `sewidak` (60) = pengecualian komposisi).

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

---

## Catatan untuk AI

- User bukan coder. Jawaban teknis perlu di-explain sederhana.
- User sering paste output terminal (ls, ffmpeg, error). Baca teliti, jangan skip.
- Bahasa default: Indonesia (casual, gak formal kaya dokumentasi).
- User makasih kalau AI proaktif bilang "aku update docs X, Y, Z soal perubahan ini" — bukan AI nunggu disuruh.
