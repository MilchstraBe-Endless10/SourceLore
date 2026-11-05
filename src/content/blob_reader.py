#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Blob 内容读取：严格区分「有引用」与「有内容」。

★ 实测 P1C/P5A 只保存 blob_refs（blob_sha/path/size），**没有内容字节**。
  因此真实仓库必须返回 BLOB_CONTENT_NOT_AVAILABLE，不得凭路径猜内容。
"""

import hashlib

from content_models import (C_AVAILABLE, C_NOT_CAPTURED, C_TOO_LARGE,
                            C_BINARY, C_BAD_ENCODING)
from content_budget import Budget, DEFAULT, BudgetError

BOM_UTF8 = b"\xef\xbb\xbf"


def _looks_binary(data: bytes) -> bool:
    """NUL 字节或高比例不可打印 → 视为二进制。"""
    if b"\x00" in data:
        return True
    if not data:
        return False
    sample = data[:2048]
    ctrl = sum(1 for b in sample if b < 9 or (13 < b < 32))
    return ctrl / len(sample) > 0.10


def content_digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def read_text(*, data, budget: Budget = DEFAULT, declared_size=None):
    """返回 (status, text_or_None, meta)。

    status ∈ CONTENT_AVAILABLE / BLOB_TOO_LARGE / BINARY_CONTENT /
             UNSUPPORTED_ENCODING / CONTENT_NOT_CAPTURED
    """
    if data is None:
        return C_NOT_CAPTURED, None, {
            "message": ("该路径只有 Blob 引用（blob_sha/size），"
                        "未保存内容字节；不得凭路径猜测内容")}

    meta = {"byte_length": len(data)}
    if len(data) > budget.max_blob_bytes:
        return C_TOO_LARGE, None, {
            "byte_length": len(data),
            "limit": budget.max_blob_bytes,
            "message": f"超过单 Blob 上限 {budget.max_blob_bytes} 字节",
        }

    if _looks_binary(data):
        return C_BINARY, None, {"byte_length": len(data),
                                "message": "二进制内容，不做文本解析"}

    raw = data
    had_bom = False
    if raw.startswith(BOM_UTF8):
        raw = raw[len(BOM_UTF8):]
        had_bom = True

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        return C_BAD_ENCODING, None, {
            "byte_length": len(data), "had_bom": had_bom,
            "message": f"非法 UTF-8：{e.reason} @byte {e.start}",
        }

    meta.update({"had_bom": had_bom,
                 "digest": content_digest(data),
                 "line_ending": ("CRLF" if "\r\n" in text else
                                 "LF" if "\n" in text else "NONE"),
                 "line_count": 0 if not text else text.count("\n") + (
                     0 if text.endswith("\n") else 1)})
    return C_AVAILABLE, text, meta


def read_from_snapshot(snapshot_payload, path, budget: Budget = DEFAULT):
    """从快照 payload 取内容。★ 现版本永远拿不到字节 → 明确 NOT_CAPTURED。

    保留此函数是为了：未来若写入 blob 内容资产，这里自动生效。
    """
    refs = (snapshot_payload or {}).get("blob_refs") or []
    ref = next((r for r in refs if r.get("path") == path), None)
    if ref is None:
        return C_NOT_CAPTURED, None, {"message": "快照中无该路径的 Blob 引用"}

    inline = snapshot_payload.get("blob_contents") or {}
    data = inline.get(ref.get("blob_sha"))
    return read_text(data=data, budget=budget, declared_size=ref.get("size"))
