# Prompt Template: Generate Shorts Timestamps dari SRT

Template ini untuk user yang mau generate JSON timestamps dari SRT Indonesia
(lengkap, hasil whisper-tui atau dari editsub.com), lalu pakai di `shorts-tui.py`.

## Cara pakai

1. **Buka ChatGPT/Claude/Gemini** (web atau app)
2. **Copy salah satu prompt di bawah** (pilih sesuai kebutuhan)
3. **Paste SRT Indonesia** di akhir prompt
4. **Send**, tunggu AI generate JSON
5. **Copy JSON** hasil AI
6. **Save ke file**, misalnya `/Volumes/HDD/Dubbing/shorts/S2-FB-Mandarin.timestamps.json`
7. **Jalankan `shorts-tui.py`**, pilih file JSON itu

---

## Prompt 1: Default — 30 shorts dari film 2-3 jam

```
Saya punya SRT Indonesia dari film Mandarin (durasi 2-3 jam).
Tolong pilih 30 segment paling menarik untuk dijadikan YouTube Shorts / TikTok / Reels.

Kriteria segment:
1. Durasi MAX 60 detik per segment (YouTube Shorts strict)
2. Mulai di awal kalimat (awal cue SRT, bukan tengah dialog)
3. Berakhir di akhir kalimat (akhir cue SRT)
4. Punya "hook" di 3 detik pertama — kalimat pembuka yang bikin penasaran
5. Berdiri sendiri — penonton ga perlu nonton scene sebelumnya untuk paham
6. Pilih scene: climax, plot twist, konfrontasi, reveal, momen emosional
7. Hindari: scene tenang, monolog panjang, transisi kosong
8. Hindari: scene yang spoiler ending (kalau perlu)

Output WAJIB format JSON array, tanpa markdown, tanpa penjelasan tambahan:
[{"start": 12.5, "end": 65.3, "title": "Judul singkat Indonesia"}, ...]

Dimana:
- start: detik awal segment (float)
- end: detik akhir segment (float)
- title: judul singkat untuk short (5-10 kata, Indonesia)

Berikut SRT Indonesia:

[PASTE SRT ANDA DI SINI — full 5000 cue]
```

---

## Prompt 2: Custom jumlah shorts (mis. 20 atau 50)

```
Saya punya SRT Indonesia dari film Mandarin (durasi 2-3 jam).
Tolong pilih [JUMLAH] segment paling menarik untuk dijadikan YouTube Shorts.

[Copy kriteria 1-8 dari prompt 1 di atas]

Output WAJIB format JSON array:
[{"start": 12.5, "end": 65.3, "title": "..."}, ...]

Berikut SRT:

[PASTE SRT]
```

Ganti `[JUMLAH]` dengan angka yang diinginkan (20, 50, dst).

---

## Prompt 3: Fokus tema tertentu (mis. adegan action, atau komedi)

```
Saya punya SRT Indonesia dari film Mandarin (durasi 2-3 jam).
Tolong pilih 30 segment untuk YouTube Shorts dengan tema: [TEMA].

Tema: adegan action / momen komedi / plot twist / adegan romantis / dst.

[Copy kriteria 2-8 dari prompt 1 di atas, kecuali kriteria 6]

Kriteria khusus tema:
- Pilih scene yang sesuai dengan tema [TEMA]
- Prioritaskan momen yang strongest untuk tema tersebut

Output WAJIB format JSON array:
[{"start": 12.5, "end": 65.3, "title": "..."}, ...]

Berikut SRT:

[PASTE SRT]
```

---

## Tips untuk hasil AI terbaik

### Pilih AI mana?

| AI | Kekuatan | Lemah | Cocok untuk |
|----|---------|------|-------------|
| **Claude Sonnet** | Context 200K token, paling teliti | Lambat (~2-5 menit untuk SRT 5000 cue) | Default, hasil paling akurat |
| **ChatGPT-4** | Cepat, output rapi | Context 128K (bisa kepenuhan untuk SRT 3 jam) | SRT < 2 jam |
| **Gemini Pro** | Context 1M token, gratis | Quality slightly below Claude | SRT > 3 jam, budget gratis |

### Kalau SRT terlalu panjang (>5000 cue)
- Pisah jadi 2 batch (cue 1-2500 dan 2501-5000)
- Run prompt untuk masing-masing
- Merge hasil JSON manual

### Kalau AI return format bukan JSON
Beberapa AI pakai markdown codeblock. Tinggal hapus `\`\`\`json` dan `\`\`\` manually
sebelum save. Format yang diterima shorts-tui.py:
```json
[
  {"start": 12.5, "end": 65.3, "title": "..."}
]
```

### Kalau AI return timestamps bukan detik
Beberapa AI mungkin return format `MM:SS` atau `HH:MM:SS`. Konversi manual ke detik:
- `00:00:12,500` → 12.5 detik
- `00:01:05,300` → 65.3 detik
- `00:10:00,000` → 600.0 detik

Atau edit prompt: tambahkan `start dan end dalam DETIK (float), bukan timestamp HH:MM:SS`.

### Validasi sebelum pakai

Setelah save JSON, cek manual:
```bash
# Quick check
python3 -c "import json; data=json.load(open('your-file.json')); print(len(data), 'segments'); print(data[0])"
```

Atau langsung jalankan shorts-tui.py — dia akan validasi otomatis.

---

## Format JSON yang diterima shorts-tui.py

### Format utama (array di root):
```json
[
  {"start": 12.5, "end": 65.3, "title": "Lin Zhao tiba"},
  {"start": 145.2, "end": 198.7, "title": "Konfrontasi paman"}
]
```

### Format alternatif (dengan wrapper, juga diterima):
```json
{
  "segments": [
    {"start": 12.5, "end": 65.3, "title": "Lin Zhao tiba"},
    {"start": 145.2, "end": 198.7, "title": "Konfrontasi paman"}
  ]
}
```

### Field yang diharapkan per segment:
| Field | Wajib | Tipe | Catatan |
|-------|------|------|---------|
| `start` | ✅ | float (detik) | 0.0 atau lebih |
| `end` | ✅ | float (detik) | Harus > `start` |
| `title` | ⚠️ opsional | string | Default: "Short N" kalau kosong |

### Warning yang akan tampil (tetap lanjut, user konfirmasi):
- Durasi segment > 60 detik (tetap bisa, tapi YouTube Shorts reject)
- Segment overlap dengan sebelumnya
- Segment end > durasi video total

---

## Contoh end-to-end workflow

```bash
# 1. User copy SRT dari /Volumes/HDD/Dubbing/input/S2-FB-Mandarin.id.srt
# 2. User paste ke ChatGPT dengan Prompt 1 di atas
# 3. ChatGPT return JSON 30 segments
# 4. User save ke /Volumes/HDD/Dubbing/shorts/S2-FB-Mandarin.timestamps.json
# 5. User jalankan shorts-tui:

cd ~/Dubbing
source venv/bin/activate
python3 shorts-tui.py
# → Step 1: pilih JSON (S2-FB-Mandarin.timestamps.json)
# → Step 2: pilih MP4 (HDD/mix/S2-FB-Mandarin-id-orig-sub.mp4)
# → Step 3: output dir (default: HDD/shorts/S2-FB-Mandarin/)
# → Step 4: stream copy
# → 15 detik: 30 MP4 di HDD/shorts/S2-FB-Mandarin/short-001.mp4 s/d short-030.mp4
```
