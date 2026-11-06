#!/usr/bin/env python3
"""Create the importable Skill archive from an explicit distributable allowlist."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = ['SKILL.md', 'README.md', 'package.json', 'package-lock.json', '.gitignore']
DIRECTORIES = ['assets', 'references', 'templates', 'scripts', 'tests', 'library', 'vendor', 'verification']


def members():
    result = [ROOT / f for f in FILES]
    result += [p for d in DIRECTORIES for p in (ROOT / d).rglob('*')
               if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc']
    return sorted(result)


def package(output):
    output.mkdir(parents=True, exist_ok=True)
    all_files=members()
    def resource(p):
        rel=p.relative_to(ROOT).as_posix()
        return rel.startswith('library/objects/') or rel.startswith('vendor/cindy-')
    payload=output/'cindy-feature-demo-resources.zip'
    with zipfile.ZipFile(payload,'w',zipfile.ZIP_STORED) as z:
        for p in all_files:
            if resource(p):z.write(p,p.relative_to(ROOT).as_posix())
    payload_sha=hashlib.sha256(payload.read_bytes()).hexdigest()
    config={'version':'2.0.0','url':'https://github.com/zcinta0514/cindy-feature-demo-workflow/releases/download/v2.0.0/'+payload.name,'sha256':payload_sha,'bytes':payload.stat().st_size,'uncompressedBytes':sum(p.stat().st_size for p in all_files if resource(p))}
    (ROOT/'library/payload.json').write_text(json.dumps(config,indent=2)+'\n')
    target = output / 'cindy-feature-demo.zip'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in members():
            if resource(p):continue
            if p.is_symlink():
                raise ValueError('共享包不接受符号链接：' + str(p.relative_to(ROOT)))
            if not p.is_file():
                raise ValueError('缺少必要共享文件：' + p.name)
            z.write(p, 'cindy-feature-demo/' + p.relative_to(ROOT).as_posix())
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (output / 'SHA256SUMS').write_text(digest + '  ' + target.name + '\n'+payload_sha+'  '+payload.name+'\n')
    with zipfile.ZipFile(target) as z:
        assert target.stat().st_size<=200*1024*1024
        assert sum(i.file_size for i in z.infolist())<=64*1024*1024, '保持低于受管 Skill 同步预算'
        assert len(z.infolist())<=10000
    return {'file': str(target), 'bytes': target.stat().st_size, 'sha256': digest, 'resourceBytes':payload.stat().st_size,'resourceSha256':payload_sha,'files': len(members())}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(package(parser.parse_args().output), ensure_ascii=False, indent=2))
