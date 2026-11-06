#!/usr/bin/env python3
"""Mix one music track and deterministic visible-event sounds, preserving video."""
import argparse
from array import array
import json
import math
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import wave


def mix(video, music, cues, output):
    if output.exists():
        raise ValueError('输出已存在，请使用新版本路径')
    for p in (video, music, cues):
        if not p.is_file():
            raise ValueError('输入不存在：' + str(p))
    duration = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                                             '-of', 'default=nw=1:nk=1', str(video)], text=True))
    if not 0 < duration <= 600:
        raise ValueError('时长须在0–600秒')
    events = json.loads(cues.read_text())
    samples = array('h', [0]) * (math.ceil(duration * 48000) * 2)
    rng = random.Random(114)
    for event in events:
        frame = event.get('frame')
        if event.get('kind') not in ('key', 'click') or not isinstance(frame, int) or not 0 <= frame < math.ceil(duration * 60):
            raise ValueError('音效事件必须是片内60fps帧号及key/click类型')
        start = frame * 800
        count = 1344 if event['kind'] == 'key' else 2160
        frequency = 1580 if event['kind'] == 'key' else 1100
        for i in range(min(count, len(samples) // 2 - start)):
            t = i / 48000
            amp = ((rng.random() * 2 - 1) * .65 + math.sin(2 * math.pi * frequency * t) * .35)
            value = int(amp * math.exp(-t / .0032) * min(1, t / .0007) * 3500)
            for channel in range(2):
                index = (start + i) * 2 + channel
                samples[index] = max(-32768, min(32767, samples[index] + value))
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='cindy-audio-') as temp:
        sfx = Path(temp) / 'events.wav'
        if sys.byteorder != 'little':
            samples.byteswap()
        with wave.open(str(sfx), 'wb') as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(48000); w.writeframes(samples.tobytes())
        fade = min(.65, duration / 3)
        graph = f'[1:a]volume=0.32,afade=t=in:d={fade},afade=t=out:st={duration-fade}:d={fade}[m];[m][2:a]amix=inputs=2:duration=shortest:normalize=0,alimiter=limit=0.95[a]'
        subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-n', '-i', str(video), '-stream_loop', '-1', '-i', str(music),
                        '-i', str(sfx), '-filter_complex', graph, '-map', '0:v:0', '-map', '[a]', '-c:v', 'copy',
                        '-c:a', 'aac', '-ar', '48000', '-ac', '2', '-t', str(duration), '-movflags', '+faststart', str(output)], check=True)
    return {'status': 'mixed', 'events': len(events), 'duration': duration, 'videoStreamCopied': True,
            'scope': '混音完成，仍须检查最终音画与听感'}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('video', 'music', 'cues', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    try:
        print(json.dumps(mix(a.video, a.music, a.cues, a.output), ensure_ascii=False))
    except (ValueError, OSError, subprocess.CalledProcessError) as e:
        print('音轨合成失败：' + str(e), file=sys.stderr); sys.exit(1)
