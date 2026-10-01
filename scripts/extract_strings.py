import re
with open('/home/z/my-project/scripts/edge-proxy/voicertool-setting.js') as f:
    content = f.read()

# Cari semua quoted string
pattern = r'"([^"]{1,200})"|\'([^\']{1,200})\''
strings = re.findall(pattern, content)
strings = [s[0] or s[1] for s in strings]
print(f'Total strings: {len(strings)}')

# Filter yang menarik — keyword lebih luas
keywords = ['rate', 'speed', 'edge', 'tts', 'speech', 'prosody', 'sync', 'duration',
            'pitch', 'stret', 'tempo', 'playback', 'wss', 'azure', 'audio', 'voice',
            'Microsoft', 'Neural', 'fitCue', 'audioBuffer', 'webkitAudio', 'AudioContext',
            'OfflineAudio', 'preservePitch', 'sampleRate', 'timeStretch',
            'Edge', 'Azure', 'Microsoft Server', 'tts.microsoft', 'speech.platform']
for s in strings:
    for kw in keywords:
        if kw.lower() in s.lower():
            print(f'  "{s}"')
            break
