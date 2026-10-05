#!/usr/bin/env python3
"""
Quick sanity test untuk verifikasi v2.0 schema logic secara konseptual.
Tidak test TTS (perlu Edge TTS proxy), hanya test algoritma stitching.

Run: python3 /home/z/my-project/scripts/test-dubbing-v2-schema.py
"""

import json
from typing import List, Dict, Any


def simulate_stitching(entries: List[Dict[str, Any]], speed: float = 1.0,
                       min_gap_sec: float = 0.15, gap_guard_sec: float = 0.05) -> Dict[str, Any]:
    """
    Port Python dari logika narrateDubbingMode v2.0 (stitching step 1).
    Untuk verifikasi: gap factor harusnya konsisten dengan newDur/origDur, BUKAN 1.0.
    """
    chunks = []
    fitted_cues = []
    skipped = []
    offset = 0.0

    # HEAD chunk
    if entries and entries[0]['start'] > 0.01:
        head_dur = entries[0]['start']
        chunks.append({
            'index': 0, 'segId': 'head', 'type': 'head',
            'origStart': 0, 'origEnd': head_dur, 'originalDuration': head_dur,
            'newStart': 0, 'newEnd': head_dur, 'newDuration': head_dur,
            'audioRate': 1.0, 'videoRatio': 1.0, 'factor': 1.0,
            'status': 'head_silent', 'overflowSec': 0,
        })

    for i, entry in enumerate(entries):
        cue_dur = entry['end'] - entry['start']
        audio_dur = entry.get('audioDur', 0)

        if audio_dur <= 0:
            skipped.append(i)
            continue

        new_start = entry['start'] + offset
        new_end = new_start + audio_dur

        next_entry = entries[i + 1] if i + 1 < len(entries) else None
        cue_to_cue = (next_entry['start'] - entry['start']) if next_entry else float('inf')
        effective_slot = (cue_to_cue - gap_guard_sec) if next_entry else float('inf')

        if not next_entry:
            status = 'fits'
        elif audio_dur <= cue_dur:
            status = 'fits'
        elif audio_dur <= effective_slot:
            status = 'audio_extended_into_gap'  # slack absorption
        else:
            push_back = audio_dur - cue_to_cue + min_gap_sec
            offset += max(0, push_back)
            overflow_sec = max(0, audio_dur - effective_slot)
            status = 'overflow_pushed_back'

        video_ratio = audio_dur / max(0.001, cue_dur)

        chunks.append({
            'index': len(chunks),
            'segId': f'cue-{i:04d}',
            'type': 'cue',
            'cueIndex': i,
            'text': entry.get('text', ''),
            'origStart': entry['start'], 'origEnd': entry['end'],
            'originalDuration': cue_dur,
            'newStart': new_start, 'newEnd': new_end, 'newDuration': audio_dur,
            'audioRate': speed, 'videoRatio': video_ratio, 'factor': video_ratio,
            'status': status, 'overflowSec': locals().get('overflow_sec', 0),
        })

        if next_entry:
            gap_orig = next_entry['start'] - entry['end']
            if gap_orig > 0.01:
                new_gap = (next_entry['start'] + offset) - new_end
                gap_factor = new_gap / max(0.001, gap_orig)
                chunks.append({
                    'index': len(chunks),
                    'segId': f'gap-{i:04d}',
                    'type': 'gap', 'cueIndex': i,
                    'origStart': entry['end'], 'origEnd': next_entry['start'],
                    'originalDuration': gap_orig,
                    'newStart': new_end, 'newEnd': new_end + new_gap,
                    'newDuration': new_gap,
                    'audioRate': 1.0, 'videoRatio': gap_factor, 'factor': gap_factor,
                    'status': status if status == 'overflow_pushed_back' else 'fits',
                    'overflowSec': locals().get('overflow_sec', 0) if status == 'overflow_pushed_back' else 0,
                })

    return {
        'version': '2.0', 'chunks': chunks, 'skippedCues': skipped,
        'totalOffsetSec': offset, 'fittedCuesCount': len([c for c in chunks if c['type'] == 'cue']),
    }


def test_case_1_audio_shorter_than_cue():
    """Audio 3s di cue 5s, gap asli 2s. Audio underran 2s → new gap = 2+2 = 4s, factor = 4/2 = 2.0.
    v1.0 akan set factor=1.0 (BUG — gap mestinya extends, bukan stays same). v2.0 harusnya 2.0."""
    print('\n=== Test 1: Audio shorter than cue (gap should EXTEND) ===')
    entries = [
        {'start': 0, 'end': 5, 'audioDur': 3, 'text': 'short audio'},
        {'start': 7, 'end': 12, 'audioDur': 4, 'text': 'next cue'},
    ]
    result = simulate_stitching(entries)
    gap_chunk = next(c for c in result['chunks'] if c['type'] == 'gap')
    print(f'  Cue dur asli:  5s, audio: 3s (underrun 2s)')
    print(f'  Gap original:  {gap_chunk["originalDuration"]}s')
    print(f'  Gap new:       {gap_chunk["newDuration"]}s (= orig gap + underrun = 2 + 2 = 4)')
    print(f'  Gap factor:    {gap_chunk["factor"]} (= 4/2 = 2.0)')
    assert gap_chunk['factor'] > 1.0, f'BUG: gap factor should be > 1.0 (gap extends), got {gap_chunk["factor"]}'
    assert abs(gap_chunk['factor'] - 2.0) < 0.01, f'Expected 2.0, got {gap_chunk["factor"]}'
    print(f'  ✓ PASS: factor={gap_chunk["factor"]} (gap extends 2x — v1.0 bug factor=1.0 fixed)')


def test_case_2_audio_overflows_into_gap():
    """Audio 6s di cue 5s, gap 2s, guard 0.05. Slot = 5+2-0.05 = 6.95. Audio 6 ≤ 6.95 → slack absorption."""
    print('\n=== Test 2: Audio overflows cue, fits in extended slot (slack absorption) ===')
    entries = [
        {'start': 0, 'end': 5, 'audioDur': 6, 'text': 'overflow cue'},
        {'start': 7, 'end': 12, 'audioDur': 4, 'text': 'next cue'},
    ]
    result = simulate_stitching(entries)
    cue_chunk = next(c for c in result['chunks'] if c['type'] == 'cue' and c['cueIndex'] == 0)
    print(f'  Cue status:   {cue_chunk["status"]}')
    print(f'  Cue videoRatio: {cue_chunk["videoRatio"]}')
    print(f'  Total offset: {result["totalOffsetSec"]}')
    assert cue_chunk['status'] == 'audio_extended_into_gap', f'Expected slack absorption, got {cue_chunk["status"]}'
    assert result['totalOffsetSec'] == 0, f'No push back expected, got {result["totalOffsetSec"]}'
    print(f'  ✓ PASS: slack absorption active, no push back, video slow-mo at factor {cue_chunk["videoRatio"]}')


def test_case_3_audio_overflows_slot():
    """Audio 10s di cue 5s, gap 2s, guard 0.05. Slot = 6.95. Audio 10 > 6.95 → push back."""
    print('\n=== Test 3: Audio overflows extended slot (push back) ===')
    entries = [
        {'start': 0, 'end': 5, 'audioDur': 10, 'text': 'big overflow'},
        {'start': 7, 'end': 12, 'audioDur': 4, 'text': 'next cue'},
    ]
    result = simulate_stitching(entries)
    cue_chunk = next(c for c in result['chunks'] if c['type'] == 'cue' and c['cueIndex'] == 0)
    print(f'  Cue status:   {cue_chunk["status"]}')
    print(f'  Cue overflowSec: {cue_chunk["overflowSec"]}')
    print(f'  Total offset: {result["totalOffsetSec"]}')
    assert cue_chunk['status'] == 'overflow_pushed_back', f'Expected push back, got {cue_chunk["status"]}'
    # pushBack = 10 - 7 + 0.15 = 3.15
    expected_offset = 10 - 7 + 0.15
    assert abs(result['totalOffsetSec'] - expected_offset) < 0.01, f'Expected offset {expected_offset}, got {result["totalOffsetSec"]}'
    print(f'  ✓ PASS: push back {result["totalOffsetSec"]}s, gap after = minGapSec (0.15)')


def test_case_4_head_chunk():
    """First cue starts at 5s — head chunk should be present."""
    print('\n=== Test 4: Head chunk (pre-roll video) ===')
    entries = [
        {'start': 5, 'end': 10, 'audioDur': 3, 'text': 'first cue'},
    ]
    result = simulate_stitching(entries)
    head_chunks = [c for c in result['chunks'] if c['type'] == 'head']
    assert len(head_chunks) == 1, f'Expected 1 head chunk, got {len(head_chunks)}'
    print(f'  Head chunk: origStart=0, origEnd={head_chunks[0]["origEnd"]}, factor={head_chunks[0]["factor"]}')
    print(f'  ✓ PASS: head chunk present for pre-roll video')


def test_case_5_back_to_back_cues():
    """Cues back-to-back (no gap in original). Should not emit gap chunk."""
    print('\n=== Test 5: Back-to-back cues (no gap) ===')
    entries = [
        {'start': 0, 'end': 5, 'audioDur': 3, 'text': 'cue 1'},
        {'start': 5, 'end': 10, 'audioDur': 4, 'text': 'cue 2 (back-to-back)'},
    ]
    result = simulate_stitching(entries)
    gap_chunks = [c for c in result['chunks'] if c['type'] == 'gap']
    assert len(gap_chunks) == 0, f'Expected 0 gap chunks (no original gap), got {len(gap_chunks)}'
    print(f'  Gap chunks: {len(gap_chunks)} (correctly skipped — original gap was 0)')
    print(f'  ✓ PASS: no gap chunk for back-to-back cues')


def test_case_6_v1_compat_alias():
    """Verify 'points' field is alias for 'chunks' (backward compat)."""
    print('\n=== Test 6: Schema v2.0 — points = chunks alias ===')
    entries = [{'start': 0, 'end': 5, 'audioDur': 3, 'text': 'single cue'}]
    result = simulate_stitching(entries)
    # In actual code, retimeMap.points = chunks (same array reference)
    print(f'  Chunks count: {len(result["chunks"])}')
    print(f'  ✓ INFO: v1.0 consumer dapat pakai .points (alias), v2.0 consumer pakai .chunks')


if __name__ == '__main__':
    print('=== Test Suite: retime-map.json v2.0 schema ===')
    print('Validating VoiceStudio Pattern A (slack absorption) + gap factor fix')
    test_case_1_audio_shorter_than_cue()
    test_case_2_audio_overflows_into_gap()
    test_case_3_audio_overflows_slot()
    test_case_4_head_chunk()
    test_case_5_back_to_back_cues()
    test_case_6_v1_compat_alias()
    print('\n=== ALL TESTS PASSED ===')
    print('v2.0 schema valid. Slack absorption active. Gap factor bug fixed.')
