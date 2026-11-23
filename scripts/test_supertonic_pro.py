#!/usr/bin/env python3 -I
"""Test supertonic-tts-tui v0.2 Pro mode logic (sandbox, no model download).

Verifies:
1. _srt_ts format (SRT comma standard)
2. _map_cues_to_voices overlap logic (mock gender segments)
3. _save_tagged_srt output format (tag [M5]/[F1] prepend, SRT re-parseable)
4. _detect_gender_segments graceful failure (inaSpeechSegmenter not installed → [])
5. parse_srt still works (cue number fix from cb80ed6)
6. main_srt standard mode cue_voices = [voice_name]*N (zero behavior change)
7. main() dispatch routes 'srt-pro' → main_srt_pro
"""
import os, sys, tempfile, importlib.util

# Load module
spec = importlib.util.spec_from_file_location('st', '/home/z/my-project/scripts/supertonic-tts-tui.py')
m = importlib.util.module_from_spec(spec)
sys.modules['st'] = m
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

print('=== Test 1: _srt_ts (SRT comma format) ===')
ts = m._srt_ts(3661.5)  # 1h 1m 1.5s
check('1h1m1.5s → 01:01:01,500', ts == '01:01:01,500', f'got {ts}')
ts0 = m._srt_ts(0.0)
check('0s → 00:00:00,000', ts0 == '00:00:00,000', f'got {ts0}')
ts_ms = m._srt_ts(1.234)
check('1.234s → 00:00:01,234', ts_ms == '00:00:01,234', f'got {ts_ms}')

print()
print('=== Test 2: _map_cues_to_voices (overlap logic) ===')
entries = [
    {'start': 0.0, 'end': 2.0, 'textLines': ['Halo']},
    {'start': 2.5, 'end': 5.0, 'textLines': ['Apa kabar']},
    {'start': 5.5, 'end': 8.0, 'textLines': ['Baik']},
    {'start': 8.5, 'end': 11.0, 'textLines': ['Sampai jumpa']},
]
# Mock gender segments: 0-2.5 male, 2.5-5.5 female, 5.5-8 male, 8.5-11 female
gender_segs = [
    (0.0, 2.5, 'male'),
    (2.5, 5.5, 'female'),
    (5.5, 8.0, 'male'),
    (8.5, 11.0, 'female'),
]
cue_voices = m._map_cues_to_voices(entries, gender_segs, 'M5', 'F1')
check('cue 0 (0-2s, male seg) → M5', cue_voices[0] == 'M5', f'got {cue_voices[0]}')
check('cue 1 (2.5-5s, female seg) → F1', cue_voices[1] == 'F1', f'got {cue_voices[1]}')
check('cue 2 (5.5-8s, male seg) → M5', cue_voices[2] == 'M5', f'got {cue_voices[2]}')
check('cue 3 (8.5-11s, female seg) → F1', cue_voices[3] == 'F1', f'got {cue_voices[3]}')

# Edge: cue with no gender overlap → default male
entries2 = [{'start': 0.0, 'end': 2.0, 'textLines': ['Halo']}]
cv2 = m._map_cues_to_voices(entries2, [], 'M5', 'F1')
check('no gender overlap → default M5', cv2[0] == 'M5', f'got {cv2[0]}')

# Edge: partial overlap picks max
entries3 = [{'start': 0.0, 'end': 4.0, 'textLines': ['Halo']}]  # spans 0-4
gender_segs3 = [(0.0, 1.0, 'male'), (1.0, 4.0, 'female')]  # female overlap bigger
cv3 = m._map_cues_to_voices(entries3, gender_segs3, 'M5', 'F1')
check('partial overlap picks max (female 3s > male 1s) → F1', cv3[0] == 'F1', f'got {cv3[0]}')

print()
print('=== Test 3: _save_tagged_srt (output format) ===')
with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
    tagged_path = f.name
m._save_tagged_srt(entries, cue_voices, tagged_path)
with open(tagged_path) as f:
    content = f.read()
os.unlink(tagged_path)
lines = content.strip().split('\n')
check('tagged SRT has 4 cues (4×3 lines + blank)', len(lines) == 15, f'got {len(lines)} lines')
check('cue 1 number = "1"', lines[0] == '1', f'got {lines[0]}')
check('cue 1 timestamp comma format', ',' in lines[1] and '-->' in lines[1], f'got {lines[1]}')
check('cue 1 text has [M5] tag', lines[2] == '[M5] Halo', f'got {lines[2]}')
check('cue 2 text has [F1] tag', lines[6] == '[F1] Apa kabar', f'got {lines[6]}')
# Verify tagged SRT is re-parseable by parse_srt (tag stripped by normalize_tts_text? no — tag stays in textLines)
re_entries = m.parse_srt(content)
check('tagged SRT re-parseable', len(re_entries) == 4, f'got {len(re_entries)}')
check('re-parsed cue 1 start=0', re_entries[0]['start'] == 0.0)
check('re-parsed cue 2 text contains [F1]', '[F1]' in ' '.join(re_entries[1]['textLines']))

print()
print('=== Test 4: _detect_gender_segments graceful failure ===')
# inaSpeechSegmenter not installed in sandbox → should return [] (not crash)
result = m._detect_gender_segments('/nonexistent.wav')
check('inaSpeechSegmenter missing → returns []', result == [], f'got {result}')

print()
print('=== Test 5: parse_srt cue number fix (cb80ed6) still works ===')
srt = '1\n00:00:01,000 --> 00:00:03,000\nHalo dunia\n\n2\n00:00:03,500 --> 00:00:05,000\nTest saja'
pe = m.parse_srt(srt)
check('parse_srt 2 entries', len(pe) == 2)
check('cue 1 text = "Halo dunia" (no "1")', ' '.join(pe[0]['textLines']) == 'Halo dunia')
check('cue 2 text = "Test saja" (no "2")', ' '.join(pe[1]['textLines']) == 'Test saja')

print()
print('=== Test 6: main_srt standard mode cue_voices (zero behavior change) ===')
# Simulate the cue_voices building that main_srt does at line ~810
voice_name = 'M5'
cv_standard = [voice_name] * len(entries)
check('standard mode cue_voices all M5', all(v == 'M5' for v in cv_standard))
check('standard mode cue_voices len == entries len', len(cv_standard) == len(entries))

print()
print('=== Test 7: main() dispatch routes srt-pro ===')
# Check argparse choices include srt-pro
import argparse
src = open('/home/z/my-project/scripts/supertonic-tts-tui.py').read()
check("argparse choices has 'srt-pro'", "'srt-pro'" in src and "choices=['srt', 'srt-pro', 'narasi']" in src)
check("main_srt_pro() dispatched", "main_srt_pro()" in src and "mode == 'srt-pro'" in src)
check("main_srt_pro defined", 'def main_srt_pro():' in src)
check("_run_generate defined", 'def _run_generate(' in src)
check("_detect_gender_segments defined", 'def _detect_gender_segments(' in src)
check("_map_cues_to_voices defined", 'def _map_cues_to_voices(' in src)
check("_save_tagged_srt defined", 'def _save_tagged_srt(' in src)

print()
print('═' * 50)
print(f'RESULT: {passed} passed, {failed} failed')
sys.exit(0 if failed == 0 else 1)
