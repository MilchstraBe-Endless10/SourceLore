#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""内容寻址原始字节存储（受控 Blob Store）。

★ 设计理由：assets 表只有 payload_json（TEXT），
  把原始字节塞进 JSON 既改变换行/BOM，也无法做二进制级校验。
  因此：**元数据入 assets（权威），字节入内容寻址目录（按 sha256 寻址）**，
  两者由 content_sha256 强绑定。

★ 这不是"第二套知识数据库" —— 它没有独立知识语义，
  只是 assets 里 captured_blob_content 记录的字节后端。
"""

import hashlib
import os
import tempfile
from pathlib import Path

STORE_DIRNAME = "blobs"
MAGIC = b"SLBLOB1\n"
SUFFIX = ".bin"

# 状态
# ★ 存储层状态。★ 与解析层 content_models.C_AVAILABLE ("CONTENT_AVAILABLE")
#   是两套词，不可互换 —— D-42 就是把这个名字拿去判解析层返回值。
AVAILABLE_VERIFIED = "CONTENT_AVAILABLE_VERIFIED"
NOT_CAPTURED = "CONTENT_NOT_CAPTURED"
ASSET_MISSING = "CONTENT_ASSET_MISSING"
INTEGRITY_FAILED = "CONTENT_INTEGRITY_FAILED"
ACQUISITION_BLOCKED = "CONTENT_ACQUISITION_BLOCKED"
PARTIAL = "CONTENT_PARTIAL"
COMMIT_MISMATCH = "CONTENT_COMMIT_MISMATCH"
INTEGRITY_CONFLICT = "CONTENT_INTEGRITY_CONFLICT"


class IntegrityError_(RuntimeError):
    pass


def store_root(data_root) -> Path:
    return Path(data_root) / STORE_DIRNAME


def _sha_of(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _path_for(root: Path, digest_hex: str) -> Path:
    return root / (digest_hex + SUFFIX)


def put_bytes(*, data_root, raw: bytes, expected_sha256=None) -> dict:
    """写入字节。★ 幂等：同内容只存一份。

    返回 {ok, digest, path, reused, byte_length}
    """
    hexd = _sha_of(raw)
    if expected_sha256 is not None:
        want = expected_sha256.split("sha256:", 1)[-1]
        if hexd != want:
            return {"ok": False, "error": INTEGRITY_FAILED,
                    "computed": "sha256:" + hexd,
                    "expected": expected_sha256}

    root = store_root(data_root)
    root.mkdir(parents=True, exist_ok=True)
    target = _path_for(root, hexd)

    # ★ 目标已存在：只能核对并复用，**绝不允许覆盖**
    if target.exists():
        return _verify_existing(target, hexd, raw)

    fd, tmp = tempfile.mkstemp(dir=str(root), suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())

        # ★ 无覆盖发布：用硬链接做 exclusive create
        #   os.link 在目标已存在时会抛 FileExistsError —— 正是我们要的语义。
        try:
            os.link(tmp, target)
        except FileExistsError:
            # 竞态：别的进程先发布了。核对后复用，不覆盖。
            return _verify_existing(target, hexd, raw)
        finally:
            try: os.unlink(tmp)
            except Exception: pass

        _fsync_dir(root)
        return {"ok": True, "digest": "sha256:" + hexd, "path": str(target),
                "reused": False, "byte_length": len(raw),
                "created_exclusive": True}
    except Exception as e:
        try: os.unlink(tmp)
        except Exception: pass
        return {"ok": False, "error": "STORE_WRITE_FAILED",
                "detail": f"{type(e).__name__}: {e}"}


def _fsync_dir(root: Path):
    """★ 目录项也要落盘 —— 否则崩溃后可能"文件存在但目录项丢失"。"""
    try:
        dfd = os.open(str(root), os.O_RDONLY)
        try: os.fsync(dfd)
        finally: os.close(dfd)
    except Exception:
        pass


def _verify_existing(target: Path, hexd: str, raw: bytes) -> dict:
    """★ 已存在目标的唯一处理：核对 → 复用 or 冲突。绝不覆盖、绝不删除。"""
    try:
        if not target.is_file():
            return {"ok": False, "error": INTEGRITY_CONFLICT,
                    "detail": "目标路径存在但不是普通文件",
                    "path": str(target)}
        existing = target.read_bytes()
    except Exception as e:
        return {"ok": False, "error": INTEGRITY_CONFLICT,
                "detail": f"无法读取既有文件: {type(e).__name__}", "path": str(target)}

    got = _sha_of(existing)
    if got != hexd:
        return {"ok": False, "error": INTEGRITY_CONFLICT,
                "path": str(target),
                "existing_digest": "sha256:" + got,
                "expected_digest": "sha256:" + hexd,
                "detail": "既有 Blob 内容与待写入内容不一致；拒绝覆盖"}
    return {"ok": True, "digest": "sha256:" + hexd, "path": str(target),
            "reused": True, "byte_length": len(raw)}


def get_bytes(*, data_root, content_sha256, verify=True) -> dict:
    """按摘要读回字节。★ 纯本地，绝不访问网络。"""
    want = (content_sha256 or "").split("sha256:", 1)[-1]
    if not want:
        return {"ok": False, "error": ASSET_MISSING, "raw": None}
    root = store_root(data_root)
    target = _path_for(root, want)
    if not target.exists():
        return {"ok": False, "error": ASSET_MISSING, "raw": None,
                "path": str(target)}
    try:
        raw = target.read_bytes()
    except Exception as e:
        return {"ok": False, "error": ASSET_MISSING, "raw": None,
                "detail": str(e)}
    if verify:
        got = _sha_of(raw)
        if got != want:
            return {"ok": False, "error": INTEGRITY_FAILED, "raw": None,
                    "computed": "sha256:" + got, "expected": content_sha256}
    return {"ok": True, "raw": raw, "byte_length": len(raw),
            "path": str(target), "digest": "sha256:" + want}


def cleanup_orphans(*, data_root, referenced):
    """清理未被任何资产引用的临时/孤儿文件。

    ★ referenced 是仍被合法资产引用的 digest 集合；
      不删共享 Blob。
    """
    root = store_root(data_root)
    if not root.is_dir():
        return {"removed": 0, "kept": 0}
    removed = kept = 0
    for p in root.iterdir():
        if p.suffix == ".tmp":
            try: p.unlink(); removed += 1
            except Exception: pass
            continue
        if p.suffix != SUFFIX:
            continue
        d = p.stem
        if d in referenced:
            kept += 1
        else:
            try: p.unlink(); removed += 1
            except Exception: pass
    return {"removed": removed, "kept": kept}
