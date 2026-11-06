#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地 Git 仓库只读采集入口。

★ 只读 `git` 的对象库（ls-tree / cat-file），**不执行仓库代码**。
★ 不跑 npm install、不跑测试、不跑构建脚本。
★ 产出的 Snapshot 与 GitHub 采集走**同一条** ingest 链路。
"""

import subprocess, hashlib, sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("collector", "storage", "runtime"):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

MAX_FILES = 200
MAX_BLOB_BYTES = 256 * 1024


class LocalRepoError(Exception):
    def __init__(self, code, detail):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _git(repo, *args, timeout=20):
    """只读 git 调用。★ 不使用 shell=True，不拼接用户输入。"""
    try:
        r = subprocess.run(["git", "-C", str(repo), *args],
                           capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise LocalRepoError("GIT_TIMEOUT", "git 命令超时")
    except FileNotFoundError:
        raise LocalRepoError("GIT_NOT_FOUND", "未找到 git 可执行文件")
    if r.returncode != 0:
        raise LocalRepoError("GIT_FAILED",
                             (r.stderr or b"").decode("utf-8", "replace")[:200])
    return r.stdout.decode("utf-8", "replace")


def resolve_commit(repo, ref="HEAD"):
    out = _git(repo, "rev-parse", f"{ref}^{{commit}}").strip()
    if len(out) != 40:
        raise LocalRepoError("INVALID_COMMIT", f"非 40 位 SHA: {out[:16]}")
    return out


def read_tree(repo, commit):
    """读 tree 条目。返回 [{path, sha, size, type, mode}]。"""
    out = _git(repo, "ls-tree", "-r", "-l", commit)
    entries = []
    for line in out.splitlines():
        if not line.strip():
            continue
        meta, path = line.split("\t", 1)
        parts = meta.split()
        if len(parts) < 4:
            continue
        mode, otype, sha = parts[0], parts[1], parts[2]
        size = parts[3] if len(parts) > 3 else "-"
        if otype != "blob":
            continue
        entries.append({"path": path, "sha": sha,
                        "size": int(size) if size.isdigit() else None,
                        "type": "blob", "mode": mode})
        if len(entries) >= MAX_FILES:
            break
    return entries


def read_blob(repo, sha):
    """按 OID 读 blob 字节，并校验 OID 自洽。"""
    try:
        r = subprocess.run(["git", "-C", str(repo), "cat-file", "blob", sha],
                           capture_output=True, timeout=20)
    except Exception as e:
        raise LocalRepoError("BLOB_READ_FAILED", str(e))
    if r.returncode != 0:
        raise LocalRepoError("BLOB_READ_FAILED", sha[:12])
    raw = r.stdout
    if len(raw) > MAX_BLOB_BYTES:
        raise LocalRepoError("BLOB_TOO_LARGE", f"{len(raw)} 字节")
    computed = hashlib.sha1(b"blob " + str(len(raw)).encode()
                            + b"\x00" + raw).hexdigest()
    if computed != sha:
        raise LocalRepoError("BLOB_OID_MISMATCH",
                             f"计算 {computed[:12]} 与给定 {sha[:12]} 不符")
    return raw


def read_root_tree(repo, commit):
    out = _git(repo, "rev-parse", f"{commit}^{{tree}}").strip()
    if len(out) != 40:
        raise LocalRepoError("INVALID_TREE", out[:16])
    return out


def collect_local(repo_path, *, ref="HEAD", repository_id=None):
    """采集本地仓库 → (snapshot, blobs, meta)。

    ★ 零网络。★ 只读 git 对象库。
    """
    repo = Path(repo_path)
    if not repo.is_dir():
        raise LocalRepoError("REPO_NOT_FOUND", str(repo))
    if not (repo / ".git").exists():
        raise LocalRepoError("NOT_A_GIT_REPOSITORY", str(repo))

    commit = resolve_commit(repo, ref)
    root_tree = read_root_tree(repo, commit)
    entries = read_tree(repo, commit)

    blobs = {}
    for e in entries:
        try:
            blobs[e["path"]] = read_blob(repo, e["sha"])
        except LocalRepoError as err:
            if err.code == "BLOB_TOO_LARGE":
                continue
            raise

    rid = repository_id or ("local:" + hashlib.sha256(
        str(repo.resolve()).encode()).hexdigest()[:12])

    from source_snapshot import build_snapshot
    snap = build_snapshot(
        repository_id=rid,
        requested_repository=f"file://{repo.resolve()}",
        resolved_repository=f"file://{repo.resolve()}",
        requested_ref=ref,
        commit_sha=commit,
        root_tree_sha=root_tree,
        tree_query_ref=root_tree,
        completeness_status="COMPLETE",
        tree_entries=entries,
        collected_at="",
        evidence_refs=[f"localgit:{repo.resolve()}@{commit}"],
        retrieval_scope="SCOPE_LOCAL_GIT")
    meta = {"repository_id": rid, "commit_sha": commit,
            "root_tree_sha": root_tree, "file_count": len(entries),
            "blob_count": len(blobs), "source": "LOCAL_GIT",
            "network_requests": 0}
    return snap, blobs, meta
