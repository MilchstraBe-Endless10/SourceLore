#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补采仓库文件正文（raw.githubusercontent.com → 官方 ingest 入口）。

★ 为什么有这个脚本（2026-11-12 实证）：
  preact（42283287）的 captured_blob_content = 0，派生视图 readme.md 只有 227 B，
  内容为「本 Commit 未采集到 README 正文」。
  同机 curl raw.githubusercontent.com/.../README.md 直接 200 / 14884 B。
  → 不是网络问题，是采集环节漏了 raw 路径。

用法：
  python3 tools/capture_raw.py --repository-id 42283287 \
      --repo preactjs/preact --commit <sha> \
      --paths README.md package.json src/index.js
  python3 tools/capture_raw.py --repository-id 42283287 --preset preact
"""

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

_THIS = Path(__file__).resolve()
_SRC = _THIS.parent.parent / "src"
sys.path.insert(0, str(_SRC / "skill_interface"))
import paths  # noqa: E402
paths.ensure_import_path()

from knowledge_store import KnowledgeStore            # noqa: E402
import content_ingest_coordinator as CIC              # noqa: E402
from paths import db_path                              # noqa: E402

RAW = "https://raw.githubusercontent.com/{repo}/{commit}/{path}"
UA = "SourceLore-raw-capture/1.0"

PRESETS = {
    "preact": {
        "repo": "preactjs/preact",
        "commit": "dbeba0d59bb59260ea4a90c5adf9f5a29d43cdab",
        "paths": [
            "README.md",
            "package.json",
            "src/index.js",
            "src/preact.js",
            "src/component.js",
            "src/diff/index.js",
        ],
    },
    "is-number": {
        "repo": "jonschlinkert/is-number",
        "commit": "98e8ff1da1a89f93d1397a24d7413ed15421c139",
        "paths": ["README.md", "index.js", "package.json"],
    },
    "is-plain-obj": {
        "repo": "sindresorhus/is-plain-obj",
        "commit": "666df7c10035f7e26f27ec214fe5ae3173435f34",
        "paths": ["index.js", "package.json", "readme.md", "license"],
    },
}


def git_blob_oid(raw: bytes) -> str:
    h = hashlib.sha1()
    h.update(b"blob %d\0" % len(raw))
    h.update(raw)
    return h.hexdigest()


def fetch(repo, commit, path):
    url = RAW.format(repo=repo, commit=commit, path=path)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        if r.status != 200:
            return None, url, f"HTTP {r.status}"
        return r.read(), url, None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--repository-id", required=True)
    ap.add_argument("--repo")
    ap.add_argument("--commit")
    ap.add_argument("--paths", nargs="*")
    ap.add_argument("--preset", choices=sorted(PRESETS))
    ap.add_argument("--data-root")
    a = ap.parse_args(argv)

    data_root = a.data_root or str(Path(__file__).resolve().parent.parent.parent / "SourceLore_Data")

    if a.preset:
        p = PRESETS[a.preset]
        repo, commit, paths = p["repo"], p["commit"], p["paths"]
    else:
        if not (a.repo and a.commit and a.paths):
            print(json.dumps({"ok": False, "error": "需要 --preset 或 (--repo + --commit + --paths)"},
                             ensure_ascii=False))
            return 2
        repo, commit, paths = a.repo, a.commit, a.paths

    dbp = db_path(data_root)
    if not Path(dbp).exists():
        print(json.dumps({"ok": False, "error": "KNOWLEDGE_DB_MISSING", "db": str(dbp)},
                         ensure_ascii=False))
        return 3

    store = KnowledgeStore(str(dbp), create=False)
    out = {"ok": True, "repository_id": a.repository_id, "repo": repo,
           "commit": commit, "captured": [], "reused": [], "failed": []}

    for path in paths:
        try:
            raw, url, err = fetch(repo, commit, path)
        except Exception as exc:
            out["failed"].append({"path": path, "error": str(exc)})
            continue
        if raw is None:
            out["failed"].append({"path": path, "error": err, "url": url})
            continue

        oid = git_blob_oid(raw)
        sha = hashlib.sha256(raw).hexdigest()
        res = CIC.ingest_captured_blob(
            store, data_root=data_root,
            repository_id=str(a.repository_id), commit_sha=commit,
            source_snapshot_id=None, file_path=path,
            git_blob_oid=oid, git_object_format="sha1", raw=raw,
            source_declared_size=len(raw),
            acquisition_policy="ALLOW",
            acquisition_policy_ref="PUBLIC_REPO_RAW",
            provenance_level="OBSERVED",
            source_api="raw.githubusercontent.com",
            source_response_digest=sha,
        )
        rec = {"path": path, "byte_length": len(raw), "git_blob_oid": oid,
               "content_sha256": sha}
        if res.get("ok"):
            rec["asset_id"] = res.get("content_asset_id")
            (out["reused"] if res.get("reused") else out["captured"]).append(rec)
        else:
            rec["error"] = res.get("error")
            out["failed"].append(rec)

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not out["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
