# PROJECT_RULES.md — Aturan Project SRT Splitter + Dubbing

> 13 rules minimal, project-specific. Baca tiap session sebelum kerja.
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

---

## Catatan untuk AI

- User bukan coder. Jawaban teknis perlu di-explain sederhana.
- User sering paste output terminal (ls, ffmpeg, error). Baca teliti, jangan skip.
- Bahasa default: Indonesia (casual, gak formal kaya dokumentasi).
- User makasih kalau AI proaktif bilang "aku update docs X, Y, Z soal perubahan ini" — bukan AI nunggu disuruh.
