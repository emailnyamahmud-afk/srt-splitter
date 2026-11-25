#!/usr/bin/env python3 -I
"""Test mix-audiobook-tui v0.1 logic (sandbox, no model download).

Verifies:
1. strip_markdown: YAML frontmatter stripped, heading # stripped (text kept),
   · → ,, HR removed, paragraph breaks preserved
2. chunk_paragraphs: splits per paragraph, merges short ones, splits long ones per sentence
3. detect_bab_mode: A/B/C detection based on file presence
4. detect_thumb_resolution: aspect ratio → resolution (mock images via PIL)
5. find_whisper_cli / find_whisper_model: graceful None on sandbox
6. main() argparse + dispatch
"""
import os, sys, tempfile, importlib.util

spec = importlib.util.spec_from_file_location('ma', '/home/z/my-project/scripts/mix-audiobook-tui.py')
m = importlib.util.module_from_spec(spec)
sys.modules['ma'] = m
spec.loader.exec_module(m)

passed = 0
failed = 0
def check(name, cond, detail=''):
    global passed, failed
    if cond:
        passed += 1
        print(f'  ✓ {name}')
    else:
        failed += 1
        print(f'  ✗ {name} {detail}')

# Load the real .md file user attached
MD_PATH = '/home/z/my-project/upload/v1-b001-dunia-yang-terlempar-ke-dalam.md'
with open(MD_PATH, 'r', encoding='utf-8') as f:
    md_content = f.read()

print('=== Test 1: strip_markdown ===')
plain = m.strip_markdown(md_content)
check('strip_markdown returns non-empty', len(plain) > 100, f'len={len(plain)}')
check('YAML frontmatter stripped (no "title:")', 'title:' not in plain[:200])
check('YAML frontmatter stripped (no "source:")', 'source:' not in plain[:300])
check('heading # stripped (no "# Volume")', '# Volume' not in plain)
check('heading text kept ("Volume 1" present)', 'Volume 1' in plain)
check('middle dot · replaced with ,', '·' not in plain, 'found · in output')
check('HR --- stripped (no standalone ---)', '\n---\n' not in plain)
check('paragraph breaks preserved (\\n\\n present)', '\n\n' in plain)
check('curly dialogue quotes preserved', '"Kapten' in plain or '"Kapten' in plain, 'no curly quote dialogue found')
check('no markdown # markers left', '\n#' not in plain and not plain.startswith('#'))
# show first 200 chars
print(f'  [preview first 150 chars]: {plain[:150]!r}')

print()
print('=== Test 2: chunk_paragraphs ===')
chunks = m.chunk_paragraphs(plain, max_chars=1500)
check('chunk_paragraphs returns list', isinstance(chunks, list))
check('chunks non-empty', len(chunks) > 0, f'len={len(chunks)}')
check('all chunks under max_chars', all(len(c) <= 1500 for c in chunks), f'max len={max((len(c) for c in chunks), default=0)}')
check('all chunks non-empty', all(c.strip() for c in chunks))
check('chunk count reasonable (1-20)', 1 <= len(chunks) <= 20, f'count={len(chunks)}')
# reconstruct: chunks joined should contain all paragraph content
joined = '\n\n'.join(chunks)
check('joined chunks length ≈ plain length', abs(len(joined) - len(plain)) < 200, f'joined={len(joined)} plain={len(plain)}')

# Edge: single short paragraph
single = m.chunk_paragraphs('Halo dunia.', max_chars=1500)
check('single short para → 1 chunk', len(single) == 1)

# Edge: very long paragraph (>max_chars) splits per sentence
long_para = 'Ini kalimat satu. ' * 200  # ~3600 chars
long_chunks = m.chunk_paragraphs(long_para, max_chars=1500)
check('long paragraph splits into >1 chunk', len(long_chunks) > 1, f'count={len(long_chunks)}')
check('long para chunks all under max', all(len(c) <= 1500 for c in long_chunks))

print()
print('=== Test 3: detect_bab_mode ===')
with tempfile.TemporaryDirectory() as td:
    # Mode A: txt + jpg, no wav
    open(os.path.join(td, 'B001.txt'), 'w').write('test')
    open(os.path.join(td, 'B001.jpg'), 'w').write('fake jpg')
    mode, files = m.detect_bab_mode('B001', td)
    check('Mode A (txt+jpg, no wav)', mode == 'A', f'got {mode}')
    check('Mode A thumb detected', files.get('thumb') is not None)

    # Mode B: wav + jpg, no srt
    os.unlink(os.path.join(td, 'B001.txt'))
    open(os.path.join(td, 'B001.wav'), 'w').write('fake wav')
    mode, files = m.detect_bab_mode('B001', td)
    check('Mode B (wav+jpg, no srt)', mode == 'B', f'got {mode}')

    # Mode C: wav + srt + jpg
    open(os.path.join(td, 'B001.srt'), 'w').write('1\n00:00:01 --> 00:00:02\nHalo')
    mode, files = m.detect_bab_mode('B001', td)
    check('Mode C (wav+srt+jpg)', mode == 'C', f'got {mode}')

    # No files
    mode, files = m.detect_bab_mode('B999', td)
    check('No files → mode None', mode is None)

    # No thumb → mode detected but thumb None
    os.unlink(os.path.join(td, 'B001.jpg'))
    open(os.path.join(td, 'B001.txt'), 'w').write('test')
    os.unlink(os.path.join(td, 'B001.wav'))
    os.unlink(os.path.join(td, 'B001.srt'))
    mode, files = m.detect_bab_mode('B001', td)
    check('Mode A but no thumb → thumb None', mode == 'A' and files.get('thumb') is None)

    # PNG thumb fallback
    open(os.path.join(td, 'B001.png'), 'w').write('fake png')
    mode, files = m.detect_bab_mode('B001', td)
    check('PNG thumb fallback', files.get('thumb', '').endswith('.png'))

print()
print('=== Test 4: detect_thumb_resolution ===')
try:
    from PIL import Image
    has_pil = True
except ImportError:
    has_pil = False

if has_pil:
    with tempfile.TemporaryDirectory() as td:
        # vertical 1080x1920
        vp = os.path.join(td, 'v.jpg')
        Image.new('RGB', (1080, 1920), 'red').save(vp)
        r = m.detect_thumb_resolution(vp)
        check('vertical thumb → 1080x1920 vertical', r == m.RES_VERTICAL, f'got {r}')

        # horizontal 1920x1080
        hp = os.path.join(td, 'h.jpg')
        Image.new('RGB', (1920, 1080), 'blue').save(hp)
        r = m.detect_thumb_resolution(hp)
        check('horizontal thumb → 1920x1080 horizontal', r == m.RES_HORIZONTAL, f'got {r}')

        # square 1080x1080
        sp = os.path.join(td, 's.jpg')
        Image.new('RGB', (1080, 1080), 'green').save(sp)
        r = m.detect_thumb_resolution(sp)
        check('square thumb → 1080x1080 square', r == m.RES_SQUARE, f'got {r}')

        # invalid image → fallback vertical
        bad = os.path.join(td, 'bad.jpg')
        open(bad, 'w').write('not an image')
        r = m.detect_thumb_resolution(bad)
        check('invalid image → fallback vertical', r == m.RES_VERTICAL, f'got {r}')
else:
    print('  (PIL not available, skip thumb tests)')

print()
print('=== Test 5: find_whisper_cli / find_whisper_model (sandbox) ===')
cli = m.find_whisper_cli()
print(f'  whisper-cli: {cli}')
model = m.find_whisper_model()
print(f'  whisper model: {model}')
# sandbox may or may not have these — just check functions don't crash
check('find_whisper_cli returns (str or None)', cli is None or isinstance(cli, str))
check('find_whisper_model returns (str or None)', model is None or isinstance(model, str))

print()
print('=== Test 6: main() argparse + dispatch ===')
src = open('/home/z/my-project/scripts/mix-audiobook-tui.py').read()
check('--voice arg present', "--voice" in src and "default=DEFAULT_VOICE" in src)
check('--no-ken-burns arg present', "--no-ken-burns" in src)
check('--no-burn-sub arg present', "--no-burn-sub" in src)
check('--force-regen-srt present', "--force-regen-srt" in src)
check('--force-regen-wav present', "--force-regen-wav" in src)
check('LUFS_TARGET = -16', 'LUFS_TARGET = -16' in src)
check('DEFAULT_VOICE = M5', "DEFAULT_VOICE = 'M5'" in src)
check('NARR_SAMPLE_RATE = 48000', 'NARR_SAMPLE_RATE = 48000' in src)
check('AUDIOBOOK_DIR imported from config', 'AUDIOBOOK_DIR' in src and 'from config import' in src)
check('AUDIOBOOK_INPUT_DIR imported', 'AUDIOBOOK_INPUT_DIR' in src)
check('process_bab defined', 'def process_bab(' in src)
check('generate_wav_supertonic defined', 'def generate_wav_supertonic(' in src)
check('generate_srt_whisper defined', 'def generate_srt_whisper(' in src)
check('render_mp4 defined', 'def render_mp4(' in src)
check('strip_markdown defined', 'def strip_markdown(' in src)
check('chunk_paragraphs defined', 'def chunk_paragraphs(' in src)
check('detect_bab_mode defined', 'def detect_bab_mode(' in src)
check('detect_thumb_resolution defined', 'def detect_thumb_resolution(' in src)
check('Ken Burns zoompan filter present', 'zoompan' in src)
check('loudnorm filter present', 'loudnorm' in src)
check('subtitles burn filter present', "subtitles='" in src)
check('resample_audio defined', 'def resample_audio(' in src)
check('encode_wav defined', 'def encode_wav(' in src)

print()
print('═' * 50)
print(f'RESULT: {passed} passed, {failed} failed')
sys.exit(0 if failed == 0 else 1)
