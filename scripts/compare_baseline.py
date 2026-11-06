#!/usr/bin/env python3
"""Compare recipient replay frames to the published, immutable visual baseline."""
import argparse, hashlib, json, re, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def compare(actual, baseline):
    expected=json.loads((baseline/'replay.json').read_text())
    replay=json.loads((actual/'replay.json').read_text())
    if replay.get('mode')!='full-replay':raise ValueError('请先不加 --render 运行1440×1080基准重演；4K编码检查另做')
    if replay.get('frames')!=expected['frames']:raise ValueError('总帧数与基准不同，需要检查时钟、动作或组件版本')
    a=[(x['frame'],x['index'],x['key']) for x in replay['transitions']]
    b=[(x['frame'],x['index'],x['key']) for x in expected['transitions']]
    if a!=b:raise ValueError('操作时间线与基准不同')
    results=[]
    for sample in expected['samples']:
        name='frame-'+str(sample['frame']).zfill(5)+'.png'
        ref=baseline/name;out=actual/name
        if hashlib.sha256(ref.read_bytes()).hexdigest()!=sample['sha256']:raise ValueError('参考图摘要不符：'+name)
        if not out.is_file():raise ValueError('缺少接收方参考帧：'+name)
        exact=hashlib.sha256(out.read_bytes()).hexdigest()==sample['sha256']
        if exact:ssim=1.0
        else:
            cmd=['ffmpeg','-v','info','-i',str(ref),'-i',str(out),'-filter_complex','[0:v][1:v]ssim','-f','null','-']
            r=subprocess.run(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True,check=True)
            match=re.search(r'All:([0-9.]+)',r.stderr)
            if not match:raise ValueError('FFmpeg没有返回结构相似度')
            ssim=float(match.group(1))
        results.append({'frame':sample['frame'],'identical':exact,'ssim':ssim,'passed':ssim>=.995})
    report={'status':'passed' if all(x['passed'] for x in results) else 'failed','threshold':{'ssim':.995},'timelineIdentical':True,'frames':results,'scope':'同一标准工程的动作时间线与抽样画面相似度；不替代完整运动/听审，不自动放行新片'}
    (actual/'baseline-comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('actual',type=Path);p.add_argument('--baseline',type=Path,default=ROOT/'verification/baseline');a=p.parse_args()
    try:
        r=compare(a.actual,a.baseline);print(json.dumps(r,ensure_ascii=False,indent=2));sys.exit(0 if r['status']=='passed' else 1)
    except Exception as e:print('基准对比失败：'+str(e),file=sys.stderr);sys.exit(1)
