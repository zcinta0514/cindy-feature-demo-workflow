#!/usr/bin/env python3
"""Restore the actual production library and its locked sources in a new project."""
import argparse, gzip, hashlib, json, os, shutil, sys, tarfile, tempfile, urllib.request, zipfile
from pathlib import Path, PurePosixPath

ROOT=Path(__file__).resolve().parents[1]
def digest(data): return hashlib.sha256(data).hexdigest()
def safe(root,name):
    p=PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts: raise ValueError('非法归档路径')
    target=root.joinpath(*p.parts)
    if not target.resolve().is_relative_to(root.resolve()): raise ValueError('路径越界')
    return target

def payload_root(project, supplied=None):
    if (ROOT/'library/objects').is_dir():return ROOT
    config=json.loads((ROOT/'library/payload.json').read_text())
    target=project/'.workflow-resources'; marker=target/'payload-sha256.txt'
    if marker.exists() and marker.read_text().strip()==config['sha256']:return target
    if target.exists():raise ValueError('资源目录存在但版本不符；保留旧目录并使用新工程')
    archive=Path(supplied) if supplied else project/'.workflow-resources.zip'
    if not supplied and not archive.exists():
        part=archive.with_suffix('.part')
        try:
            with urllib.request.urlopen(config['url'],timeout=60) as response,part.open('wb') as out:
                count=0
                while True:
                    b=response.read(1024*1024)
                    if not b:break
                    count+=len(b)
                    if count>config['bytes']:raise ValueError('下载资源超过声明大小')
                    out.write(b)
            part.rename(archive)
        finally:part.unlink(missing_ok=True)
    h=hashlib.sha256()
    with archive.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    if archive.stat().st_size!=config['bytes'] or h.hexdigest()!=config['sha256']:raise ValueError('完整资源包摘要不符；请重新下载本版本资源')
    staging=Path(tempfile.mkdtemp(prefix='.resources-',dir=project))
    try:
        with zipfile.ZipFile(archive) as z:
            if sum(i.file_size for i in z.infolist())!=config['uncompressedBytes']:raise ValueError('资源包展开大小与声明不一致')
            for info in z.infolist():
                if not (info.filename.startswith('library/objects/') or info.filename.startswith('vendor/cindy-')):raise ValueError('资源包包含未声明目录')
                dest=safe(staging,info.filename);dest.parent.mkdir(parents=True,exist_ok=True)
                with z.open(info) as src,dest.open('wb') as out:shutil.copyfileobj(src,out)
        (staging/'payload-sha256.txt').write_text(config['sha256']+'\n');staging.rename(target)
    finally:
        if staging.exists():shutil.rmtree(staging)
    if not supplied:archive.unlink(missing_ok=True)
    return target

def restore(project, case='all', sources=False, resources=None):
    project=project.resolve()
    if not (project/'demo.config.json').is_file(): raise ValueError('请先用 workflow.py init 初始化独立工程')
    catalog=json.loads((ROOT/'library/catalog.json').read_text())
    manifest=json.loads((ROOT/'library/manifest.json').read_text())
    if case=='all': selected=manifest['files']
    else:
        item=next((c for c in catalog['cases'] if c['id']==case),None)
        if not item:raise ValueError('案例不存在：'+case)
        selected={n:v for n,v in manifest['files'].items() if n.startswith(item['root']+'/')}
    target=project/'production-library'
    if target.exists(): raise ValueError('production-library 已存在；请使用新的独立工程，避免覆盖修改')
    payload=payload_root(project,resources)
    staging=Path(tempfile.mkdtemp(prefix='.restore-',dir=project))
    try:
        for name,info in selected.items():
            data=gzip.decompress((payload/'library/objects'/(info['sha256']+'.gz')).read_bytes())
            if len(data)!=info['bytes'] or digest(data)!=info['sha256']:raise ValueError('资源摘要不匹配：'+name)
            dest=safe(staging,name);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
        (staging/'catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2))
        (staging/'restored-manifest.json').write_text(json.dumps({'case':case,'files':selected},ensure_ascii=False,indent=2))
        staging.rename(target)
    finally:
        if staging.exists():shutil.rmtree(staging)
    if sources:extract_sources(project,manifest,resources)
    return {'status':'restored','files':len(selected),'directory':str(target),'case':case,'sources':sources}

def extract_sources(project,manifest=None,resources=None):
    manifest=manifest or json.loads((ROOT/'library/manifest.json').read_text())
    info=manifest['sourceArchive'];target=project/'product-source'
    if target.exists():raise ValueError('product-source 已存在；不覆盖')
    payload=payload_root(project,resources)
    archive=project/'.product-source.tar.gz'
    if archive.exists():raise ValueError('源码恢复临时文件已存在，请检查先前恢复是否中断')
    with archive.open('wb') as f:
        for part in info.get('parts',[info['path']]):
            with (payload/part).open('rb') as src:shutil.copyfileobj(src,f)
    if digest(archive.read_bytes())!=info['sha256']:
        archive.unlink();raise ValueError('产品源码摘要不匹配')
    staging=Path(tempfile.mkdtemp(prefix='.source-',dir=project))
    try:
        with tarfile.open(archive) as tf:
            members=tf.getmembers()
            for m in members:
                dest=safe(staging,m.name)
                if m.issym():
                    if PurePosixPath(m.linkname).is_absolute() or not (dest.parent/m.linkname).resolve().is_relative_to(staging.resolve()):raise ValueError('链接越界')
                elif not (m.isfile() or m.isdir()):raise ValueError('不支持的归档成员：'+m.name)
            # The verified public Git archive has only regular files/directories and internal symlinks.
            for m in members:
                dest=safe(staging,m.name)
                if m.isdir():dest.mkdir(parents=True,exist_ok=True)
                elif m.isfile():
                    dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(tf.extractfile(m).read());dest.chmod(m.mode&0o777)
            for m in members:
                if m.issym():
                    dest=safe(staging,m.name);dest.parent.mkdir(parents=True,exist_ok=True);dest.symlink_to(m.linkname)
        staging.rename(target)
    finally:
        if staging.exists():shutil.rmtree(staging)
        archive.unlink(missing_ok=True)
    return {'status':'sources-restored','commit':info['commit']}

def bind_sources(project):
    """Bind historical builders only inside this recipient's isolated copy."""
    library=project/'production-library'; source=project/'product-source'
    if not (source/'apps/desktop/package.json').is_file():raise ValueError('先恢复固定版本产品源码')
    count=0
    for p in library.rglob('*'):
        if p.is_file() and p.suffix in {'.json','.py','.mjs','.js','.md','.tsx','.ts','.sh'}:
            s=p.read_text();n=s.replace('__PROJECT_ROOT__',str(library)).replace('__CINDY_SOURCE__',str(source))
            if n!=s:p.write_text(n);count+=1
    config={'repo':str(source),'desktop':str(source/'apps/desktop')}
    (library/'sample-video').mkdir(exist_ok=True)
    (library/'sample-video/source.json').write_text(json.dumps(config))
    for p in list((library/'interactive-preview').glob('*/build.mjs'))+list((library/'videos').glob('*/build*.mjs')):
        (p.parent/'source.json').write_text(json.dumps(config))
    engine=library/'sample-video/reusable/workflow-skill/engine.json'
    if engine.exists():
        cfg=json.loads(engine.read_text());cfg['projectRoot']=str(library);cfg['engineDir']=str(library/'sample-video/reusable')
        cfg['caseLibrary']={'root':str(library),'readOnly':True,'inheritProductionRules':False}
        cfg['delivery']['root']=str(project/'deliveries');engine.write_text(json.dumps(cfg,ensure_ascii=False,indent=2))
    return {'status':'bound','changedFiles':count,'note':'重建前还需按 product-source 的锁文件安装源码依赖；预构建样片无需这一步'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['list','restore','sources','bind']);p.add_argument('--project',type=Path);p.add_argument('--case',default='all');p.add_argument('--with-sources',action='store_true');p.add_argument('--resources',type=Path,help='离线完整资源ZIP，省去自动下载');a=p.parse_args()
    try:
        if a.action=='list':r=json.loads((ROOT/'library/catalog.json').read_text())
        else:
            if not a.project:raise ValueError('缺少 --project')
            project=a.project.resolve()
            r=restore(project,a.case,a.with_sources,a.resources) if a.action=='restore' else extract_sources(project,resources=a.resources) if a.action=='sources' else bind_sources(project)
        print(json.dumps(r,ensure_ascii=False,indent=2))
    except Exception as e:print('恢复失败：'+str(e),file=sys.stderr);sys.exit(1)
