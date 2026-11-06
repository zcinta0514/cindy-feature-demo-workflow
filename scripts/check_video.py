#!/usr/bin/env python3
"""Check a final video's actual dimensions, rate, audio and full decode."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from archive_delivery import inspect_video


def check(video):
    errors, probe = inspect_video(video)
    return {'status': 'failed' if errors else 'passed', 'scope': '文件与音轨技术检查；不是视觉/功能/用户放行',
            'errors': errors, 'sha256': hashlib.sha256(video.read_bytes()).hexdigest() if video.is_file() else None,
            'probe': probe}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('video', type=Path)
    p.add_argument('--report', type=Path)
    args = p.parse_args()
    result = check(args.video)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'probe'}, ensure_ascii=False))
    sys.exit(0 if result['status'] == 'passed' else 1)
