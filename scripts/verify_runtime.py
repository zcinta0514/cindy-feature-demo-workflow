#!/usr/bin/env python3
"""Render a short branded calibration, not a product demonstration or approval."""
import argparse
import json
import math
from pathlib import Path
import struct
import subprocess
import wave

HTML = '''<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="../assets/brand/style.css">
<style>body{margin:0;width:1440px;height:1080px}#stage{left:-240px}.content-stage{top:115px;height:820px;outline:1px solid #fff}.calibration{padding:60px;font:28px sans-serif}#marker{position:absolute;top:320px;width:80px;height:80px;border:2px solid currentColor}.cursor-shape{display:none}.brand-closing{top:664px}</style></head><body>
<main class="cindy-motion" id="stage"><div class="mesh"></div><div class="brand"><img class="brand-icon" src="../assets/brand/assets/brand/icon.png"><img class="brand-wordmark" src="../assets/brand/assets/brand/wordmark.svg"><p class="brand-feature"></p><p class="brand-closing"></p></div><div class="content-stage"><p class="calibration">工具链校准 / Calibration — not product UI</p><div id="marker"></div></div><span class="cursor-shape"></span></main>
<script src="../assets/brand/assets/gsap.min.js"></script><script src="../assets/brand/motion.js"></script>
<script type="module">
const ready=(async()=>{await document.fonts.ready;await Promise.all([...document.images].map(i=>i.decode()));})();
const kit=CindyMotion.create(document.querySelector('#stage'),{duration:14,feature:'Workflow calibration',closing:'Not a product demonstration'});
window.__DEMO_EXPORT__={ready,frameCount:72,async render(frame){await ready;kit.seek(4+frame/60);document.querySelector('#marker').style.left=(180+frame*5)+'px';},async finish(){return{complete:true,assertions:[{name:'calibration marker reaches end',passed:document.querySelector('#marker').style.left==='535px'}],audioCues:[{frame:30,kind:'click'}]};}};
</script></body></html>'''


def run(project):
    project = project.resolve()
    scene = project / 'scene/calibration.html'
    scene.write_text(HTML)
    output = project / 'output/calibration'
    output.mkdir(parents=True, exist_ok=True)
    subprocess.run(['node', str(project / 'tools/render.mjs'), '--project', str(project), '--entry', 'scene/calibration.html',
                    '--output', 'output/calibration/silent.mp4'], check=True)
    tone = output / 'calibration-tone.wav'
    with wave.open(str(tone), 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(48000)
        w.writeframes(b''.join(struct.pack('<hh', *([int(250 * math.sin(2 * math.pi * 220 * i / 48000))] * 2)) for i in range(57600)))
    subprocess.run(['python3', str(project / 'tools/mix_audio.py'), '--video', str(output / 'silent.mp4'),
                    '--music', str(tone), '--cues', str(output / 'audio-cues.json'), '--output', str(output / 'final.mp4')], check=True)
    subprocess.run(['python3', str(project / 'tools/check_video.py'), str(output / 'final.mp4'),
                    '--report', str(output / 'technical.json')], check=True)
    probe = json.loads((output / 'technical.json').read_text())['probe']
    v = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    if int(v['nb_frames']) != 72:
        raise ValueError('编码帧数与逐帧输入不一致')
    result = {'status': 'passed', 'frames': 72, 'resolution': '3840x2880', 'fps': 60,
              'scope': '离线品牌资源、逐帧渲染、混音、完整解码；非产品保真或观感验收'}
    (output / 'verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project', type=Path, required=True)
    run(p.parse_args().project)
