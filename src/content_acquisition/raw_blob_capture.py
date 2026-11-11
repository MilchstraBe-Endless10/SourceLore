#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 raw.githubusercontent.com 真实采集文件正文，走官方 ingest 入口入库。

★ 为什么需要这个模块（2026-11-12 实证）：
  preact（42283287）的 captured_blob_content 资产数为 0 —— 连 README 都没抓到，
  导致派生视图 readme.md 只有 227 字节、内容为「本 Commit 未采集到 README 正文」。
  而同一台机器 `curl raw.githubusercontent.com/.../README.md` 直接 200 拿到 14884 字节。
  结论：不是网络问题，是采集环节没走 raw 路径。

★ 只用官方入口，不绕过门禁：
  - 字节落 blob_content_store（内容寻址，sha256 校验）
  - 元数据落 A 层 assets（content_ingest_coordinator.ingest_captured_blob）
  - copy_permitted / distribution_allowed 一律 False（继承既有分发门禁）

★ 不读、不打印任何凭据。公开仓库走匿名 raw 端点。
"""

import hashlib
import sys
import urllib.request
from pathlib import Path

_THIS = Path(__file__).resolve()
_SRC = _THIS.parent.parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

RAW_BASE = "https://raw.githubusercontent.com/{repo}/{commit}/{path}"
UA = "SourceLore-raw-capture/1.0 (+https://github.com/deepseek-ai/deepseek-harness)"

# 每个仓库要补采的路径（按优先级）
TARGETS = {
    "42283287": {
        "repo": "preactjs/preact",
        "commit": "dbeba0d59bb59260ea4a90c5adf9f5a29d43cdab",
        "paths": ["README.md", "package.json", "src/index.js", "src/preact.js",
                  "src/diff/index.js", "src/component.js"],
    },
}


def git_blob_oid(raw: bytes) -> str:
    """Git blob OID = sha1("blob <len>\\0" + bytes)。"""
    h = hashlib.sha1()
    h.update(b"blob %d\0" % len(raw))
    h.update(raw)
    return h.hexdigest()


def fetch_raw(repo: str, commit: str, path: str, timeout: int = 30):
    url = RAW_BASE.format(repo=repo, commit=commit, path=path)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if resp.status != 200:
            return None, url, f"HTTP {resp.status}"
        return resp.read(), url, None


def capture_repository(*, repository_id: str, store, data_root: str,
                       repo: str, commit: str, paths, logger=print):
    """补采一个仓库的若干文件。返回统计。"""
    import content_ingest_coordinator as COORD

    stats = {"ok": 0, "reused": 0, "failed": 0, "details": []}

    for path in paths:
        try:
            raw, url, err = fetch_raw(repo, commit, path)
        except Exception as exc:  # 网络异常
            stats["failed"] += 1
            stats["details"].append({"path": path, "error": str(exc)})
            logger(f"  ✗ {path}: {exc}")
            continue

        if raw is None:
            stats["failed"] += 1
            stats["details"].append({"path": path, "error": err, "url": url})
            logger(f"  ✗ {path}: {err}")
            continue

        oid = git_blob_oid(raw)
        digest = hashlib.sha256(raw).hexdigest()

        res = COORD.ingest_captured_blob(
            store=store,
            data_root=data_root,
            repository_id=str(repository_id),
            commit_sha=commit,
            source_snapshot_id=None,
            file_path=path,
            git_blob_oid=oid,
            git_object_format="sha1",
            raw=raw,
            source_declared_size=len(raw),
            acquisition_policy="ALLOW",
            acquisition_policy_ref="PUBLIC_REPO_RAW",
            provenance_level="OBSERVED",
            source_api="raw.githubusercontent.com",
            source_response_digest=digest,
        )

        if res.get("ok"):
            if res.get("reused"):
                stats["reused"] += 1
                logger(f"  = {path}: 已存在 ({len(raw)} B)")
            else:
                stats["ok"] += 1
                logger(f"  ✓ {path}: {len(raw)} B  blob={oid[:12]}")
            stats["details"].append({
                "path": path, "byte_length": len(raw),
                "git_blob_oid": oid, "content_sha256": digest,
                "asset_id": res.get("content_asset_id"),
                "reused": bool(res.get("reused")),
            })
        else:
            stats["failed"] += 1
            stats["details"].append({
                "path": path, "error": res.get("error"),
                "detail": str(res.get("detail"))[:200]})
            logger(f"  ✗ {path}: ingest 失败 {res.get('error')}")

    return stats
