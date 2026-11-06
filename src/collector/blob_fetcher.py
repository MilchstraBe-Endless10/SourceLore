#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GitHub Blob 获取与字节级校验。

★ Git Blob OID 与 SourceLore 内容摘要**严格区分**：
  - git_blob_oid = SHA1(b"blob " + len + b"\\0" + raw)   （SHA-1 仓库）
  - content_sha256 = sha256(raw)
"""

import base64
import binascii
import hashlib

# 状态
OK = "FETCH_OK"
TOO_LARGE = "SKIPPED_CONTENT_TOO_LARGE"
INCOMPLETE = "CONTENT_TRANSFER_INCOMPLETE"
BAD_BASE64 = "BLOB_BASE64_INVALID"
SIZE_MISMATCH = "BLOB_SIZE_MISMATCH"
OID_MISMATCH = "GIT_BLOB_OID_MISMATCH"
UNSUPPORTED_FORMAT = "GIT_OBJECT_FORMAT_UNSUPPORTED"
HTTP_ERROR = "BLOB_HTTP_ERROR"
UNKNOWN_SIZE = "BLOB_SIZE_UNKNOWN"

# GitHub blobs API 的传输预算：base64 约 4/3 膨胀 + JSON 包装。
# 不把 GitHub 支持的 100MB 当 SourceLore 预算。
BASE64_EXPANSION = 4.0 / 3.0
JSON_OVERHEAD_BYTES = 512


def git_blob_oid(raw: bytes, *, fmt="sha1") -> str:
    """计算 Git 对象 OID。★ 不是普通文件的 sha1。"""
    if fmt == "sha1":
        h = hashlib.sha1()
    elif fmt == "sha256":
        h = hashlib.sha256()
    else:
        raise ValueError(f"unsupported git object format: {fmt}")
    h.update(b"blob " + str(len(raw)).encode("ascii") + b"\x00")
    h.update(raw)
    return h.hexdigest()


def content_sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def transport_budget(max_decoded_bytes: int) -> int:
    """估算响应体上限（含 base64 膨胀 + JSON 包装）。"""
    return int(max_decoded_bytes * BASE64_EXPANSION) + JSON_OVERHEAD_BYTES


def declared_size_gate(declared_size, max_bytes: int):
    """★ 发请求前用 Tree entry 的 size 判断。

    返回 (是否允许请求, 原因码)。None = 未知大小 → 保守跳过。
    """
    if declared_size is None:
        return False, UNKNOWN_SIZE
    try:
        n = int(declared_size)
    except Exception:
        return False, UNKNOWN_SIZE
    if n < 0:
        return False, UNKNOWN_SIZE
    if n > max_bytes:
        return False, TOO_LARGE
    return True, None


def decode_and_verify(*, response_payload, expected_oid,
                      expected_size=None, max_bytes=256 * 1024,
                      git_object_format="sha1"):
    """解析 GitHub blobs 响应并做八项校验。

    返回 dict: status / raw / byte_length / content_sha256 / git_blob_oid / reasons
    """
    reasons = []
    if not isinstance(response_payload, dict):
        return {"status": HTTP_ERROR, "raw": None, "reasons": ["响应不是 JSON 对象"]}

    enc = response_payload.get("encoding")
    if enc != "base64":
        return {"status": BAD_BASE64, "raw": None,
                "reasons": [f"encoding={enc}，本实现只接受 base64"]}

    sha = response_payload.get("sha")
    if expected_oid and sha != expected_oid:
        reasons.append("RESPONSE_SHA_MISMATCH")

    b64 = response_payload.get("content")
    if not isinstance(b64, str):
        return {"status": BAD_BASE64, "raw": None,
                "reasons": reasons + ["content 字段缺失"]}

    declared = response_payload.get("size")
    if expected_size is not None and declared is not None:
        if int(declared) != int(expected_size):
            reasons.append("DECLARED_SIZE_MISMATCH")

    # ★ 传输预算：编码后的长度先卡一道
    budget = transport_budget(max_bytes)
    if len(b64) > budget:
        return {"status": TOO_LARGE, "raw": None,
                "reasons": reasons + [f"base64 长度 {len(b64)} > 传输预算 {budget}"]}

    compact = "".join(b64.split())    # 去掉换行
    try:
        raw = base64.b64decode(compact, validate=True)
    except (binascii.Error, ValueError) as e:
        return {"status": BAD_BASE64, "raw": None,
                "reasons": reasons + [f"base64 解码失败: {e}"]}

    if declared is not None and int(declared) != len(raw):
        reasons.append("SIZE_MISMATCH")

    if len(raw) > max_bytes:
        return {"status": TOO_LARGE, "raw": None,
                "reasons": reasons + [f"解码长度 {len(raw)} > 预算 {max_bytes}"]}

    # ★ Git 对象格式
    if git_object_format not in ("sha1", "sha256"):
        return {"status": UNSUPPORTED_FORMAT, "raw": None,
                "reasons": reasons + [f"不支持的 Git 对象格式 {git_object_format}"]}

    computed = git_blob_oid(raw, fmt=git_object_format)
    if expected_oid and computed != expected_oid:
        reasons.append("COMPUTED_OID_MISMATCH")

    if reasons:
        status = OID_MISMATCH if any("OID" in r or "SHA_MISMATCH" in r
                                     for r in reasons) else SIZE_MISMATCH
        return {"status": status, "raw": None, "reasons": reasons,
                "computed_oid": computed, "byte_length": len(raw)}

    return {"status": OK, "raw": raw, "byte_length": len(raw),
            "content_sha256": content_sha256(raw),
            "git_blob_oid": computed, "reasons": [],
            "response_sha": sha, "declared_size": declared}


def fetch_blob(client, *, owner, name, blob_sha, expected_size,
               max_bytes=256 * 1024, repository_id=None, commit_sha=None,
               git_object_format="sha1"):
    """用既有 GitHubClient 取 Blob。★ 不新建网络客户端。"""
    allow, why = declared_size_gate(expected_size, max_bytes)
    if not allow:
        return {"status": why, "raw": None, "reasons": [f"前置拒绝：{why}"],
                "network_requests": 0}

    resp = client.blob(owner, name, blob_sha,
                       repository_id=repository_id, commit_sha=commit_sha)
    if not getattr(resp, "ok", False):
        err = getattr(resp, "error", None)
        code = getattr(err, "error_code", "UNKNOWN")
        return {"status": HTTP_ERROR, "raw": None,
                "error_code": code,
                "http_status": getattr(resp, "status", 0),
                "reasons": [f"HTTP 失败: {code}"],
                "headers": dict(getattr(resp, "headers", None) or {}),
                "network_requests": 1}

    got = decode_and_verify(
        response_payload=getattr(resp, "data", None) or {},
        expected_oid=blob_sha, expected_size=expected_size,
        max_bytes=max_bytes, git_object_format=git_object_format)
    # ★ F2-P6F：透传响应头，预算才能用真实 remaining 而不是本地推断
    got["headers"] = dict(getattr(resp, "headers", None) or {})
    got["http_status"] = getattr(resp, "status", 200)
    got["network_requests"] = 1
    return got
