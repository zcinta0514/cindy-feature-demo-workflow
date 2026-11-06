"""Archive a completed production event; never watch folders or infer QA approval."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
import fcntl
from fractions import Fraction
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from zoneinfo import ZoneInfo


DEFAULT_CONFIG = Path.cwd() / "demo.config.json"
REQUIRED = {"functionalLogic", "nativeFidelity", "readabilityAndCaptions",
            "motionAndPacing", "audioAndSync", "finalFileIntegrity", "deliveryCompleteness"}
COLUMNS = ["制作日期", "案例编号", "名称", "成片版本", "相对路径", "X状态", "X发送时间", "X发布链接",
           "小红书状态", "小红书发送时间", "小红书发布链接", "备注"]


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for part in iter(lambda: f.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def atomic_text(path, value):
    path = Path(path)
    fd, tmp = tempfile.mkstemp(prefix="." + path.name + "-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(value)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def exact_text(path):
    # Keep CSV CRLFs and embedded newlines byte-for-byte for rollback.
    with Path(path).open(encoding="utf-8", newline="") as f:
        return f.read()


def safe_name(value, limit=70):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", str(value)).strip(" .")[:limit] or "未命名"


def relative_file(value, base):
    if not isinstance(value, str) or not value.strip():
        return None
    p = Path(value).expanduser()
    return (p if p.is_absolute() else base / p).resolve()


def fingerprint(path):
    s = path.stat()
    return s.st_ino, s.st_size, s.st_mtime_ns


def inspect_video(video, dimensions=(3840, 2880)):
    """Basic physical verification, NOT a substitute for visual/functional review."""
    errors, info = [], {}
    if not video or not video.is_file():
        return ["完整视频文件尚未生成"], info
    try:
        p = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)],
                           check=True, capture_output=True, text=True, timeout=120)
        info = json.loads(p.stdout)
        streams = info.get("streams", [])
        v = next((s for s in streams if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")), {})
        a = next((s for s in streams if s.get("codec_type") == "audio"), {})
        if (v.get("width"), v.get("height")) != dimensions:
            errors.append(f"视频不是{dimensions[0]}×{dimensions[1]}")
        if any(Fraction(v.get(k, "0/1")) != 60 for k in ("avg_frame_rate", "r_frame_rate")):
            errors.append("视频帧率不是60fps")
        if not a:
            errors.append("最终视频缺少音轨")
        elif a.get("sample_rate") != "48000" or a.get("channels") != 2:
            errors.append("音轨不是48kHz立体声")
        if float(info.get("format", {}).get("duration", 0)) <= 0:
            errors.append("视频时长无效")
        # Fail on decode errors; do not merely inspect container metadata.
        subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-nostdin", "-i", str(video),
                        "-map", "0:v:0", "-map", "0:a:0?", "-f", "null", "-"],
                       check=True, capture_output=True, timeout=1800)
        info["archiveCompleteDecode"] = True
    except (OSError, ValueError, ZeroDivisionError, subprocess.SubprocessError) as e:
        errors.append("最终视频探测或完整解码失败：" + type(e).__name__)
    return errors, info


def check_acceptance(path, video, digest):
    errors = []
    if not path or not path.is_file():
        return ["缺少绑定本版视频的完整质检记录"], None
    try:
        data = read_json(path)
        gate = data.get("qualityGate", {})
        if gate.get("status") != "passed" or gate.get("eligibleForLibrary") is not True:
            errors.append("完整质检尚未放行；技术检查不等于完整质检")
        output = data.get("output", {})
        if not digest or output.get("sha256") != digest:
            errors.append("质检记录未绑定本版视频SHA256")
        if relative_file(output.get("path"), path.parent) != video:
            errors.append("质检记录的视频路径与本次生成事件不一致")
        results = gate.get("checkResults", [])
        by_id = {x.get("id"): x for x in results if isinstance(x, dict)}
        if len(by_id) != len(results):
            errors.append("质检项ID重复或格式无效")
        for key in sorted(REQUIRED):
            result = by_id.get(key, {})
            if result.get("status") != "passed":
                errors.append("必检项未通过：" + key)
                continue
            if not result.get("method") or not result.get("scope") or not result.get("evidence"):
                errors.append("必检项缺少检查方法、范围或证据：" + key)
                continue
            for item in result["evidence"]:
                value = item.get("path") if isinstance(item, dict) else item
                evidence = relative_file(value, path.parent)
                if not evidence or not evidence.is_file():
                    errors.append("质检证据文件不存在：" + key)
                elif isinstance(item, dict) and item.get("sha256") and sha256(evidence) != item["sha256"]:
                    errors.append("质检证据摘要不符：" + key)
        if gate.get("blockingIssues"):
            errors.append("质检仍有阻断问题")
        for issue in data.get("openIssues", []):
            if not isinstance(issue, dict) or issue.get("severity") not in ("info", "warning"):
                errors.append("质检存在未解决或未分类的问题")
                break
        return errors, data
    except (OSError, ValueError, TypeError, AttributeError) as e:
        return ["质检记录格式无效：" + type(e).__name__], None


def inside(root, relative):
    p = (root / relative).resolve()
    if not p.is_relative_to(root) or p == root:
        raise ValueError("归档记录路径越出交付目录")
    return p


def restore_transaction(root, journal_path):
    """Roll back an interrupted publish before accepting another event."""
    if not journal_path.is_file():
        return
    tx = read_json(journal_path)
    target = inside(root, tx["target"])
    marker = target / "归档记录.json"
    if marker.is_file() and read_json(marker).get("transactionId") == tx["id"]:
        shutil.rmtree(target)
    for action in reversed(tx["moves"]):
        src, dst = inside(root, action["source"]), inside(root, action["destination"])
        if dst.exists() and not src.exists():
            src.parent.mkdir(parents=True, exist_ok=True)
            os.rename(dst, src)
    for name, content in tx["savedFiles"].items():
        p = inside(root, name)
        if content is None:
            p.unlink(missing_ok=True)
        else:
            atomic_text(p, content)
    staging = inside(root, tx["staging"])
    if staging.is_dir():
        shutil.rmtree(staging)
    journal_path.unlink()


def archive(manifest_path, config_path=DEFAULT_CONFIG):
    manifest_path, config_path = Path(manifest_path).resolve(), Path(config_path).resolve()
    config = read_json(config_path)
    delivery_config = config["delivery"]
    if delivery_config.get("automaticDeliveryActive") is not True:
        return {"status": "disabled", "reason": "自动归档尚未启用"}
    configured_root = Path(delivery_config["root"]).expanduser()
    root = (configured_root if configured_root.is_absolute() else config_path.parent / configured_root).resolve()
    if not root.is_dir():
        raise ValueError("配置的桌面交付目录不存在：" + str(root))
    manifest = read_json(manifest_path)
    if manifest.get("schemaVersion") != 1:
        raise ValueError("不支持的交付清单版本")
    case_id = manifest.get("id", "")
    if not isinstance(case_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", case_id):
        raise ValueError("交付案例ID必须是稳定的字母数字/下划线/短横线标识")
    title = str(manifest.get("title") or case_id)
    version = str(manifest.get("version") or "未指定版本")
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    day = manifest.get("date") or now.date().isoformat()
    if not isinstance(day, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        raise ValueError("制作日期须为YYYY-MM-DD")
    datetime.strptime(day, "%Y-%m-%d")
    data = manifest.get("delivery", {})
    video = relative_file(data.get("video", {}).get("path"), manifest_path.parent)
    acceptance = relative_file(manifest.get("acceptance"), manifest_path.parent)
    before = fingerprint(video) if video and video.is_file() else None
    # New productions use 4:3; explicit legacy 16:9 declarations remain valid.
    # A declared size is an expectation, never inferred from the actual file.
    declared = data.get("video", {})
    defaults = config.get("videoDefaults", {"width": 3840, "height": 2880})
    has_size = "width" in declared or "height" in declared
    spec = declared if has_size else defaults
    dimensions = (spec.get("width"), spec.get("height"))
    supported = dimensions in ((3840, 2880), (3840, 2160))
    errors, probe = inspect_video(video, dimensions if supported else (3840, 2880))
    if not supported:
        errors.append("交付清单或默认配置的画幅规格缺失或不受支持")
    if declared.get("fps", 60) != 60:
        errors.append("交付清单声明的帧率不是60fps")
    digest = sha256(video) if before else None
    qa_errors, qa = check_acceptance(acceptance, video, digest)
    errors += qa_errors
    copies = {}
    for platform in ("x", "xiaohongshu"):
        value = data.get(platform, {})
        copies[platform] = {}
        for field in ("title", "body"):
            text = value.get(field)
            if not isinstance(text, str) or not text.strip():
                errors.append("缺少" + platform + "的" + field)
                text = ""
            copies[platform][field] = text
    if manifest.get("archiveIssues"):
        errors.extend(str(x) for x in manifest["archiveIssues"])
    if before and fingerprint(video) != before:
        raise ValueError("视频仍在变化，未归档；生成完成后可重试")
    errors = sorted(set(errors))
    ready = not errors
    state = "ready" if ready else "held"
    package_digest = hashlib.sha256(json_text({"id": case_id, "title": title, "version": version,
        "video": digest, "copy": copies, "acceptance": sha256(acceptance) if acceptance and acceptance.is_file() else None,
        "issues": errors}).encode()).hexdigest()
    directory_key = "readyDirectory" if ready else "heldDirectory"
    category = delivery_config[directory_key]
    for key in ("readyDirectory", "heldDirectory", "historyDirectory", "publicationRecords"):
        inside(root, delivery_config[key])
    target = inside(root, str(Path(category) / day / (case_id + "-" + safe_name(title))))
    index_path, journal = root / ".归档索引.json", root / ".归档事务.json"
    csv_path = inside(root, delivery_config["publicationRecords"])
    with (root / ".归档.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        restore_transaction(root, journal)
        index = read_json(index_path) if index_path.exists() else {"schemaVersion": 1, "cases": {}}
        entry = index["cases"].setdefault(case_id, {})
        previous = entry.get(state, {})
        previous_path = inside(root, previous["path"]) if previous.get("path") else None
        if previous.get("packageDigest") == package_digest and previous_path and previous_path.is_dir():
            record = read_json(previous_path / "归档记录.json")
            # Verify the delivered bytes, not merely an index entry.
            video_file = "视频-4K60.mp4" if ready else "视频-待处理.mp4"
            intact = record.get("packageDigest") == package_digest
            intact = intact and all((previous_path / name).is_file() for name in
                                    ("交付说明.md", "归档记录.json", "交付清单.json"))
            intact = intact and (qa is None or (previous_path / "验收记录.json").is_file())
            intact = intact and (not digest or (previous_path / video_file).is_file() and sha256(previous_path / video_file) == digest)
            intact = intact and all((previous_path / name).is_file() and
                    (previous_path / name).read_text(encoding="utf-8") == value
                    for name, value in copy_texts(copies).items())
            if intact:
                return {"status": "unchanged", "category": state, "path": str(previous_path),
                        "issues": record["issues"], "packageDigest": package_digest}
        fields, rows = read_publications(csv_path)
        matching = [r for r in rows if r.get("案例编号") == case_id]
        if len(matching) > 1:
            raise ValueError("发送记录存在重复案例编号，请先整理，未覆盖任何归档")
        for candidate in (previous_path, target if target.exists() else None):
            if candidate and candidate.exists():
                marker = candidate / "归档记录.json"
                if not marker.is_file() or read_json(marker).get("id") != case_id:
                    raise ValueError("目标已有非本模块管理的文件，未覆盖：" + str(candidate))
        staging_root = root / ".归档暂存"
        staging_root.mkdir(exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix="delivery-", dir=staging_root))
        transaction_id = staging.name
        video_file = "视频-4K60.mp4" if ready else "视频-待处理.mp4"
        record = {"schemaVersion": 1, "id": case_id, "title": title, "version": version,
            "date": day, "archivedAt": now.isoformat(), "category": state, "videoSha256": digest,
            "packageDigest": package_digest, "transactionId": transaction_id,
            "sourceManifest": str(manifest_path), "sourceVideo": str(video) if video else None,
            "issues": errors, "basicMediaCheck": probe, "videoFile": video_file,
            "acceptancePath": str(acceptance) if acceptance else None}
        try:
            if before:
                shutil.copy2(video, staging / video_file)
                if fingerprint(video) != before or sha256(staging / video_file) != digest:
                    raise ValueError("复制时视频发生变化，未发布到桌面成片目录")
            for name, value in copy_texts(copies).items():
                (staging / name).write_text(value, encoding="utf-8")
            (staging / "归档记录.json").write_text(json_text(record), encoding="utf-8")
            (staging / "交付清单.json").write_text(json_text(manifest), encoding="utf-8")
            if qa is not None:
                (staging / "验收记录.json").write_text(json_text(qa), encoding="utf-8")
            notes = "\n".join("- " + e for e in errors) if errors else "本版适用必检项通过，媒体规格和完整解码已再次核对。"
            (staging / "交付说明.md").write_text(
                f"# {title}\n\n案例：{case_id} · 版本：{version} · 日期：{day}\n\n"
                f"归类：{'可选成片' if ready else '待处理，不计入合格成片'}\n\n{notes}\n\n"
                "X和小红书的发送状态以交付根目录的发送记录.csv为准；复制/下载不算已发送。\n",
                encoding="utf-8")
            # Large copies can take time: re-read publication edits before publish.
            fields, rows = read_publications(csv_path)
            matching = [r for r in rows if r.get("案例编号") == case_id]
            if len(matching) > 1:
                raise ValueError("发送记录存在重复案例编号，未覆盖归档")
            tx = {"id": transaction_id, "target": str(target.relative_to(root)),
                  "staging": str(staging.relative_to(root)), "moves": [],
                  "savedFiles": {str(p.relative_to(root)): exact_text(p) if p.exists() else None
                                 for p in (csv_path, index_path)}}
            atomic_text(journal, json_text(tx))
            try:
                displaced = set()
                held = entry.get("held", {})
                promoted_held = (inside(root, held["path"]) if ready and held.get("path") and
                                 held.get("videoSha256") == digest and held.get("version") == version else None)
                for old in (previous_path, target if target.exists() else None, promoted_held):
                    if not old or not old.exists() or old in displaced:
                        continue
                    displaced.add(old)
                    history = inside(root, str(Path(delivery_config["historyDirectory"]) / day /
                                     (case_id + "-" + safe_name(read_json(old / "归档记录.json").get("version", "old"), 35)
                                      + "-" + transaction_id)))
                    # A ready and held directory can share a version; preserve both uniquely.
                    while history.exists():
                        history = history.with_name(history.name + "-old")
                    history.parent.mkdir(parents=True, exist_ok=True)
                    tx["moves"].append({"source": str(old.relative_to(root)), "destination": str(history.relative_to(root))})
                    atomic_text(journal, json_text(tx))
                    os.rename(old, history)
                if promoted_held:
                    entry.pop("held", None)
                target.parent.mkdir(parents=True, exist_ok=True)
                os.rename(staging, target)
                entry[state] = {"path": str(target.relative_to(root)), "packageDigest": package_digest,
                                "version": version, "videoSha256": digest}
                if ready:
                    row = matching[0] if matching else {k: "" for k in fields}
                    if not matching:
                        row.update({"案例编号": case_id, "X状态": "未发送", "小红书状态": "未发送"})
                        rows.append(row)
                    # Publication flags, times, links and notes are never reset by a rerender.
                    row.update({"制作日期": day, "名称": title, "成片版本": version,
                                "相对路径": str(target.relative_to(root))})
                    buf = io.StringIO(newline="")
                    writer = csv.DictWriter(buf, fieldnames=fields)
                    writer.writeheader()
                    writer.writerows(rows)
                    atomic_text(csv_path, "\ufeff" + buf.getvalue())
                atomic_text(index_path, json_text(index))
                journal.unlink()  # Commit; an interrupted transaction is rolled back next time.
            except BaseException:
                restore_transaction(root, journal)
                raise
        finally:
            if staging.exists():
                shutil.rmtree(staging)
        return {"status": "archived", "category": state, "path": str(target),
                "issues": errors, "packageDigest": package_digest, "videoSha256": digest}


def copy_texts(copies):
    return {name: f"{copies[key]['title']}\n\n{copies[key]['body']}\n"
            for key, name in (("x", "X-标题与文案.txt"), ("xiaohongshu", "小红书-标题与文案.txt"))}


def read_publications(path):
    if not path.exists():
        return list(COLUMNS), []
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        if not set(COLUMNS).issubset(fields):
            raise ValueError("发送记录表头不兼容，未覆盖原文件")
        rows = list(reader)
        if any(None in row or any(value is None for value in row.values()) for row in rows):
            raise ValueError("发送记录列数不完整或有多余列，未覆盖原文件")
        return fields, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    try:
        result = archive(args.manifest, args.config)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"status": "archive_failed", "error": str(error),
                          "nextStep": "生成文件仍留原处；修正目标/清单后重试，不会伪报归档成功。"}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
