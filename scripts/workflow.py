#!/usr/bin/env python3
"""Initialize and prepare an isolated, movable demo project. No account access."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def init(project):
    project = project.resolve()
    if (project / 'demo.config.json').exists():
        return {'status': 'exists', 'project': str(project), 'changed': False}
    if project.exists() and any(project.iterdir()):
        raise ValueError('目标目录非空且没有本工作流配置；请使用独立目录')
    project.mkdir(parents=True, exist_ok=True)
    for directory in ('assets', 'templates'):
        shutil.copytree(ROOT / directory, project / directory)
    shutil.copytree(ROOT / 'scripts', project / 'tools', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for name in ('package.json', 'package-lock.json'):
        shutil.copy2(ROOT / name, project / name)
    package = json.loads((project / 'package.json').read_text())
    package['scripts'] = {'doctor': 'python3 tools/workflow.py doctor .',
                          'setup': 'python3 tools/workflow.py setup .'}
    write_json(project / 'package.json', package)
    for name in ('scene', 'audio', 'sources', 'output', 'evidence', 'library', 'deliveries'):
        (project / name).mkdir()
    shutil.copy2(ROOT / 'templates/production-script.json', project / 'production-script.json')
    write_json(project / 'demo.config.json', {
        'schemaVersion': 1, 'packageVersion': '2.0.0',
        'videoDefaults': {'width': 3840, 'height': 2880, 'fps': 60},
        'delivery': {'root': 'deliveries', 'automaticDeliveryActive': True,
                     'readyDirectory': '01_可选成片', 'heldDirectory': '02_待处理',
                     'historyDirectory': '03_历史版本', 'publicationRecords': '发送记录.csv'},
        'languages': ['en', 'zh-CN'], 'policyRevision': '2026-11-06'})
    (project / '.gitignore').write_text('node_modules/\n.browsers/\noutput/\ndeliveries/\n__pycache__/\n.env*\n')
    return {'status': 'initialized', 'project': str(project), 'changed': True}


def environment(project):
    env = os.environ.copy()
    env['PLAYWRIGHT_BROWSERS_PATH'] = str(project / '.browsers')
    return env


def doctor(project):
    project = project.resolve()
    missing = [name for name in ('node', 'npm', 'ffmpeg', 'ffprobe') if not shutil.which(name)]
    if shutil.which('node'):
        major = int(subprocess.check_output(['node', '-p', 'process.versions.node.split(".")[0]'], text=True))
        if major < 20:
            missing.append('Node >= 20')
    integrity = []
    manifest = json.loads((project / 'assets/manifest.json').read_text())
    for item in manifest['assets']:
        f = project / item['path']
        if not f.is_file() or hashlib.sha256(f.read_bytes()).hexdigest() != item['sha256']:
            integrity.append(item['path'])
    browser = False
    if not missing and (project / 'node_modules/playwright/package.json').is_file():
        result = subprocess.run(['node', '--input-type=module', '-e',
            "import {chromium} from 'playwright'; import fs from 'node:fs'; console.log(fs.existsSync(chromium.executablePath()))"],
            cwd=project, env=environment(project), capture_output=True, text=True)
        browser = result.returncode == 0 and result.stdout.strip() == 'true'
    return {'status': 'ready' if not missing and browser and not integrity else 'needs_setup',
            'missingTools': missing, 'renderBrowserPresent': browser, 'assetMismatches': integrity,
            'scope': '环境与资源检查，不代表产品影片验收通过'}


def setup(project):
    project = project.resolve()
    if not (project / 'demo.config.json').is_file():
        raise ValueError('请先初始化工程')
    needed = []
    if not shutil.which('node') or not shutil.which('npm'):
        needed.append('node')
    elif int(subprocess.check_output(['node', '-p', 'process.versions.node.split(".")[0]'], text=True)) < 20:
        raise ValueError('现有 Node 低于20；请由 Cindy 核对 PATH 和版本后升级，不覆盖未知全局配置')
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        needed.append('ffmpeg')
    if needed:
        if sys.platform != 'darwin' or not shutil.which('brew'):
            raise ValueError('缺少系统工具 ' + ', '.join(needed) + '，且没有可用的 Mac Homebrew；先安装这些工具后重试 setup')
        subprocess.run(['brew', 'install', *needed], check=True)
    subprocess.run(['npm', 'ci', '--ignore-scripts', '--no-audit', '--no-fund'], cwd=project, check=True)
    subprocess.run(['node', 'node_modules/playwright/cli.js', 'install', 'chromium'],
                   cwd=project, env=environment(project), check=True)
    result = doctor(project)
    write_json(project / 'evidence/environment.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['init', 'doctor', 'setup'])
    parser.add_argument('project', type=Path)
    args = parser.parse_args()
    try:
        result = globals()[args.action](args.project)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result['status'] in ('initialized', 'exists', 'ready') else 1
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(json.dumps({'status': 'error', 'message': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
