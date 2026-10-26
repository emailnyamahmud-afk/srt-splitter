# srt-editor-tui

TUI editor untuk file SRT (subtitle). Dibuat untuk memperbaiki terjemahan hasil Google Translate / editsub.com yang masih punya banyak typo, nama orang salah, dan konteks aneh.

## Kenapa pakai ini?

Kalau kamu pernah ngedit 5000+ cue SRT manual untuk dubbing, kamu tahu pain-nya:
- Nama orang muncul 5 variasi (Hongying / Elang Merah / Red Eagle / Qin Hongying Nyonya Qin) — harus diganti satu-satu
- "Cumming" muncul padahal aslinya "menarik pelatuk" — kamu harus ingat di cue mana
- Kadang kamu udah review cue 1-100, lalu scroll ke atas, susah tahu mana yang udah/belum

TUI ini ngebantu:
- **List + detail view** — lihat semua cue sambil edit yang dipilih
- **Mark reviewed** — tahu mana yang sudah diperiksa
- **Flag** — tandai yang bermasalah untuk diulangi nanti
- **Glossary** — satu file JSON, edit sekali → semua cue diperbaiki otomatis
- **Search, jump, find&replace** — cepat lompat ke cue manapun
- **Auto-save** — ga takut kehilangan progress kalau terminal ke-close

## Cara Install (Mac)

### 1. Pastikan Python 3.9+ terpasang

Cek di Terminal:
```bash
python3 --version
```
Kalau belum ada / di bawah 3.9, install dari https://www.python.org/downloads/

### 2. Install textual

```bash
pip3 install textual
```

Atau kalau pip bermasalah (externally-managed-environment):
```bash
pip3 install textual --break-system-packages
```

Atau lebih clean pakai venv:
```bash
python3 -m venv ~/srt-venv
source ~/srt-venv/bin/activate
pip install textual
```

### 3. Download srt-editor-tui

Salin folder ini ke Mac kamu, misal ke `~/tools/srt-editor-tui/`.

## Cara Pakai

### Basic (tanpa glossary)
```bash
cd ~/tools/srt-editor-tui
python3 run.py /path/ke/file.srt
```

### Dengan glossary (recommended)
```bash
python3 run.py /path/ke/file.srt --glossary sample-glossary.json
```

### Quit
Tekan `q` (auto-save working state dulu sebelum quit).

## Keyboard Shortcuts

| Key | Aksi |
|-----|------|
| `↑` / `↓` | Navigasi cue list |
| `e` | Edit cue (buka modal input) |
| `r` | Revert ke text asli |
| `m` | Toggle "reviewed" (sudah diperiksa) |
| `f` | Toggle "flagged" (tandai bermasalah) |
| `n` | Lompat ke cue berikutnya yang belum di-review |
| `p` | Lompat ke cue sebelumnya yang belum di-review |
| `F2` | Buka panel glossary (apply canonical forms) |
| `F3` | Search text (case-insensitive) |
| `F4` | Find & Replace (case-sensitive, semua cue) |
| `F5` | Jump to cue by ID |
| `Ctrl+S` | Save: tulis `.final.srt` + `.working.json` |
| `Ctrl+R` | Reload dari `.working.json` (discard perubahan in-memory) |
| `?` | Bantuan |
| `q` | Quit (auto-save dulu) |

## Status Icons (di cue list)

| Icon | Arti | Warna |
|------|------|-------|
| ` ` (kosong) | Belum disentuh | dim |
| `✓` | Reviewed | hijau |
| `!` | Flagged (masalah) | merah |
| `*` | Changed (text berubah) | kuning |
| `@` | Auto-fixed by glossary | cyan |

## File Output

Setelah save, akan ada 3 file di folder yang sama dengan input:

| File | Tujuan |
|------|--------|
| `file.final.srt` | **Output final** — pakai ini untuk TTS & mix |
| `file.srt.bak` | Backup original (dibuat sekali saat save pertama) |
| `file.working.json` | Auto-save state — supaya bisa resume kapan saja |

Kalau kamu buka TUI lagi dengan file SRT yang sama, dia auto-load dari `.working.json` (progress tidak hilang).

## Glossary

File JSON untuk standarisasi nama & istilah. Contoh:

```json
{
  "version": 1,
  "entries": [
    {
      "canonical": "Lin Zhao",
      "variants": ["Lin Yanya", "Peti mati Lin", "Peti mati Lin Ya"],
      "scope": "names"
    },
    {
      "canonical": "menarik pelatuk",
      "variants": ["cumming", "melakukan cumming"],
      "scope": "terms"
    }
  ]
}
```

**Aturan:**
- `canonical` = bentuk yang kita inginkan (final)
- `variants` = bentuk-bentuk salah yang harus diganti dengan canonical
- Replacement **case-sensitive** (cocok persis)
- Variants diurutkan by length DESC otomatis — jadi "Peti mati Lin Ya" diganti sebelum "Peti mati Lin" (cegah replacement parsial)
- `scope` field optional — info saja, tidak mempengaruhi behavior

**Workflow:**
1. Edit `sample-glossary.json` (atau buat glossary baru) pakai editor teks biasa
2. Buka TUI dengan `--glossary sample-glossary.json`
3. Tekan `F2` → pilih entry → "Apply Selected" atau "Apply ALL"
4. Cues yang ketularan otomatis ditandai `@` (auto-fixed) — bisa di-revert (`r`) kalau salah

## Contoh Workflow Lengkap

```bash
# 1. Punya file SRT hasil editsub.com
ls S2-FB-Mandarin.id.srt

# 2. Edit glossary (pakai VS Code / nano / apapun)
nano sample-glossary.json

# 3. Buka TUI
python3 run.py S2-FB-Mandarin.id.srt --glossary sample-glossary.json

# 4. Di TUI:
#    - F2 → Apply ALL (semua nama/istilah distandarisasi)
#    - Tekan n untuk loncat ke cue yang belum di-review
#    - Tekan e untuk edit text kalau ada yang masih aneh
#    - Ctrl+S untuk save

# 5. Output siap dipakai
ls S2-FB-Mandarin.id.final.srt  # pakai ini untuk edge-tts + mix-tui
```

## Glossary yang Sudah Disiapkan

Folder ini sudah include `sample-glossary.json` berisi temuan-temuan dari S2-FB-Mandarin.id.srt:

**Names (10 entries):**
- Lin Zhao ← Lin Yanya, Peti mati Lin, Peti mati Lin Ya, Lin Zhou, dst
- Xie Changfeng ← Xie Zangfeng, Pelatih Xie, Tuan Xie, Xie Chaojin, Xie Dutou
- Wang Haochuan ← Aokawa
- Ma Zhenbang ← Marco, Ma Zhenzhuang
- Chen Su ← Saudari Chen Su, Nyonya Chen, Nona Chen, Dokter Chen, Chen Xinlang
- Qin Hongying ← Hongying, Elang Merah, Red Eagle
- Mu En ← Bulan, bulan mudu xu, bulan yang rendah hati, Mu Xunjian
- Yao Sihai ← Butler Yao, Yao Gu, Yao Dadu, Yao Zhong
- Zhou Lizheng ← Paman Zhou, Zhou Laozhang, Zhou Lao
- Qin Fenglu ← Qin Fengzhan, Qin Fengjun

**Terms (8 entries):**
- Xiangjun ← Tentara Hunan, debitur, pemberontak debitur, tentara utang
- panah otomatis ← ayam panah, ayam panah otomatis
- obat luka emas ← payung emas, payung tempat tidur emas
- Jiedushi ← dot polisi, Qin Fenglu dot polisi
- menarik pelatuk ← cumming, melakukan cumming
- laras meledak ← menggoreng permen
- pembalasan ← retribusi
- akademi ← universitas terkemuka, SMP Desa

Dengan glossary ini, **144 replacement** otomatis terdeteksi di file S2-FB-Mandarin.id.srt.

## Troubleshooting

**"ModuleNotFoundError: No module named 'textual'"**
→ Install dulu: `pip3 install textual`

**" externally-managed-environment"** (Mac Homebrew Python)
→ Pakai: `pip3 install textual --break-system-packages`
→ Atau pakai venv (lihat cara install di atas)

**TUI render aneh / warna rusak**
→ Pastikan terminal kamu mendukung 256-color. Mac Terminal/iTerm2/Warp/tmux semua OK.

**File SRT tidak terbaca**
→ Pastikan encoding UTF-8. Kalau file dari Windows (CRLF + BOM), parser otomatis handle.

**Quit tanpa save, progress hilang?**
→ Tidak. TUI auto-save ke `.working.json` setiap 30 detik kalau ada perubahan, dan saat quit. Buka lagi file SRT yang sama → auto-resume.

**Mau mulai dari awal lagi (reset progress)?**
→ Hapus `file.working.json`. TUI akan load dari `.srt` original.

## Struktur File

```
srt-editor-tui/
├── README.md                  # file ini
├── requirements.txt           # textual>=0.50.0
├── run.py                     # entry point
├── sample-glossary.json       # template glossary (terisi temuan S2-FB-Mandarin)
└── srt_editor/
    ├── __init__.py
    ├── parser.py              # SRT parser & serializer
    ├── glossary.py            # glossary loader & applier
    └── editor.py              # TUI app utama
```

## Roadmap (Belum Diimplementasi)

Phase berikutnya kalau ternyata butuh:

- **Phase 4**: Voice assignment per cue (untuk multi-voice TTS) — format `cue.voice = "male"` di working JSON, generate JSON manifest untuk edge-tts
- **Phase 5**: Merge adjacent short cues (cue 1-2 kata digabung supaya TTS natural)
- **Phase 6**: Regex find & replace (vs simple string replace sekarang)
- **Phase 7**: Multi-file batch mode — proses 1 folder episode sekaligus
- **Phase 8**: Diff view (original vs current side-by-side)

Bilang aja kalau butuh salah satu.

## Lisensi

Pakai buat kamu sendiri. Bebas.
