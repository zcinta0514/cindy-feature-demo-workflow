#!/usr/bin/env python3
"""Use the original score and tactile-event mixer for the standard reference film."""
import argparse, hashlib, json, re, shutil, subprocess, sys
from pathlib import Path

def audio_python(project):
    candidates=[sys.executable]+[shutil.which('python'+v) for v in ('3.12','3.11','3.10','3.9')]
    for executable in dict.fromkeys(x for x in candidates if x):
        check=subprocess.run([executable,'-c','import numpy; assert numpy.__version__ == "2.0.2"'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if check.returncode==0:return executable
    compatible=None
    for executable in dict.fromkeys(x for x in candidates if x):
        if subprocess.run([executable,'-c','import sys; assert (3,9)<=sys.version_info[:2]<(3,13)'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:compatible=executable;break
    if not compatible:raise ValueError('原版声音引擎需要 Python 3.9–3.12 + NumPy 2.0.2；请让 Cindy 准备 Python 3.12 后重试（不覆盖现有 Python）')
    venv=project/'.audio-venv';executable=venv/'bin/python'
    if not executable.exists():subprocess.run([compatible,'-m','venv',str(venv)],check=True)
    subprocess.run([str(executable),'-m','pip','install','numpy==2.0.2'],check=True)
    return str(executable)

def mix(project,folder,output):
    if output.exists():raise ValueError('输出已存在；使用新的版本文件名')
    replay=json.loads((folder/'replay.json').read_text())
    if replay['status']!='passed' or replay['mode']!='full-render':raise ValueError('先完成标准样片逐帧渲染')
    py=audio_python(project)
    (folder/'timing.json').write_text(json.dumps({'duration':replay['duration']}))
    source=project/'production-library/interactive-preview/plan-mode-v2'
    provenance=[]
    for name in ('score.py','mix-audio.py'):
        code=(source/name).read_text()
        adapted,count=re.subn(r"OUT\s*=\s*Path\('deliverables/plan-mode-v2'\)","OUT=Path(__import__('sys').argv[1])",code)
        if count!=1:raise ValueError('原版声音引擎入口发生变化，不能静默套用')
        target=folder/('portable-'+name);target.write_text(adapted)
        if name=='mix-audio.py':
            subprocess.run(['ffmpeg','-nostdin','-y','-v','error','-i',str(folder/'original-score-114bpm.wav'),'-af','loudnorm=I=-22:TP=-1.5:LRA=7','-ar','48000','-ac','2',str(folder/'music-normalized.wav')],check=True)
        subprocess.run([py,str(target),str(folder)],check=True)
        provenance.append({'source':'interactive-preview/plan-mode-v2/'+name,'sha256':hashlib.sha256(code.encode()).hexdigest(),'adaptation':'output path only'})
    subprocess.run(['ffmpeg','-nostdin','-n','-v','error','-i',str(folder/'silent-master.mp4'),'-i',str(folder/'final-mix.wav'),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-ar','48000','-ac','2','-t',str(replay['duration']),'-movflags','+faststart',str(output)],check=True)
    report={'status':'mixed','numpy':'2.0.2','sourceScripts':provenance,'music':'original seed 471142026, 114 BPM, regenerated to the actual film duration','events':'original tactile sound algorithm; current replay frame-aligned cues','videoStream':'copied','humanListening':'not performed'}
    (folder/'original-audio-engine.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--project',type=Path,required=True);p.add_argument('--folder',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try:print(json.dumps(mix(a.project.resolve(),a.folder.resolve(),a.output.resolve()),ensure_ascii=False,indent=2))
    except Exception as e:print('原版音轨合成失败：'+str(e),file=sys.stderr);sys.exit(1)
