#!/usr/bin/env python3
"""Create the importable Skill archive from an explicit distributable allowlist."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = ['SKILL.md', 'README.md', 'package.json', 'package-lock.json', '.gitignore']
DIRECTORIES = ['assets', 'references', 'templates', 'scripts', 'tests']


def members():
    result = [ROOT / f for f in FILES]
    result += [p for d in DIRECTORIES for p in (ROOT / d).rglob('*')
               if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc']
    return sorted(result)


def package(output):
    output.mkdir(parents=True, exist_ok=True)
    target = output / 'cindy-feature-demo.zip'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in members():
            if p.is_symlink():
                raise ValueError('共享包不接受符号链接：' + str(p.relative_to(ROOT)))
            if not p.is_file():
                raise ValueError('缺少必要共享文件：' + p.name)
            z.write(p, 'cindy-feature-demo/' + p.relative_to(ROOT).as_posix())
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (output / 'SHA256SUMS').write_text(digest + '  ' + target.name + '\n')
    return {'file': str(target), 'bytes': target.stat().st_size, 'sha256': digest, 'files': len(members())}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(package(parser.parse_args().output), ensure_ascii=False, indent=2))
