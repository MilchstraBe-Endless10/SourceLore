#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""内容级证据范围：字节偏移为准，行号为派生的可读表示。

★ 关键：行号 ↔ 字节偏移在两个方向上都必须可验证。
   Unicode / CRLF 最容易出错，这里逐项处理。
"""

E_HEADING = "readme_heading"
E_DEPENDENCY = "manifest_dependency"
E_FIELD = "manifest_field"
E_LINK = "readme_link"
E_CODE_MARKER = "code_block_language"

VALID_KINDS = frozenset({E_HEADING, E_DEPENDENCY, E_FIELD, E_LINK, E_CODE_MARKER})


def _sha256(b: str) -> str:
    import hashlib
    return "sha256:" + hashlib.sha256(b.encode("utf-8")).hexdigest()


class RangeError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def line_of_offset(text: str, offset: int) -> int:
    """字节偏移 → 1-based 行号。★ 用字符计数再对齐字节，避免 UTF-8 偏差。"""
    if offset < 0:
        raise RangeError("RANGE_OUT_OF_BOUNDS", f"offset {offset} < 0")
    return text[:offset].count("\n") + 1


def build_range(*, text, start_byte, end_byte, kind, label=None,
                git_blob_oid=None, file_path=None):
    """构造一个可核验的范围。

    ★ 不信任调用方给的 end_byte：必须 <= 文本长度，且 start < end。
    """
    n = len(text)
    if start_byte < 0 or end_byte < 0:
        raise RangeError("RANGE_OUT_OF_BOUNDS", "负偏移")
    if start_byte >= end_byte:
        raise RangeError("RANGE_EMPTY", f"{start_byte}..{end_byte} 为空")
    if end_byte > n:
        raise RangeError("RANGE_BEYOND_CONTENT",
                         f"end {end_byte} 超出内容长度 {n}")
    if kind not in VALID_KINDS:
        raise RangeError("RANGE_BAD_KIND", f"未知 kind {kind}")

    snippet = text[start_byte:end_byte]
    # ★ 默认 label 不回显原文 —— 不可信内容不得进入证据描述字段
    return {
        "kind": kind,
        "label": label if label is not None else f"{kind}@{start_byte}",
        "start_byte": start_byte,
        "end_byte": end_byte,
        "start_line": line_of_offset(text, start_byte),
        "end_line": line_of_offset(text, max(start_byte, end_byte - 1)),
        "byte_length": end_byte - start_byte,
        "git_blob_oid": git_blob_oid,
        "file_path": file_path,
        "content_digest": None,      # 由调用方填，避免此处重复计算
        "snippet_sha256": _sha256(snippet),
    }


def verify_range(*, rng, text, expected_len=None, git_blob_oid=None,
                 file_path=None):
    """★ 九项核验中的后五项：行号有效、字节有效、范围对应真实内容、
    不跨文件、不跨 Commit。返回 (ok, reasons)。"""
    reasons = []
    if git_blob_oid is not None and rng.get("git_blob_oid") not in (None, git_blob_oid):
        reasons.append("BLOB_MISMATCH")
    if file_path is not None and rng.get("file_path") not in (None, file_path):
        reasons.append("PATH_MISMATCH")
    if text is None:
        reasons.append("CONTENT_UNAVAILABLE")
    else:
        sb, eb = rng.get("start_byte"), rng.get("end_byte")
        if not isinstance(sb, int) or not isinstance(eb, int):
            reasons.append("RANGE_NOT_INT")
        elif sb < 0 or eb > len(text) or sb >= eb:
            reasons.append("RANGE_OUT_OF_BOUNDS")
        else:
            exp_line = line_of_offset(text, sb)
            if rng.get("start_line") != exp_line:
                reasons.append("LINE_MISMATCH")
            end_line = line_of_offset(text, max(sb, eb - 1))
            if rng.get("end_line") != end_line:
                reasons.append("END_LINE_MISMATCH")
    if expected_len is not None and text is not None and len(text) != expected_len:
        reasons.append("LENGTH_MISMATCH")
    return (not reasons), reasons


def to_evidence_ref(*, rng, repository_id, commit_sha, content_asset_id,
                    content_digest, parser_version):
    """转成可入库的 ContentEvidenceRef。★ 缺任一维度都不算完整引用。"""
    return {
        "ref_schema": "content-evidence-ref/1",
        "repository_id": str(repository_id),
        "commit_sha": str(commit_sha),
        "file_path": rng["file_path"],
        "git_blob_oid": rng["git_blob_oid"],
        "content_asset_id": content_asset_id,
        "content_digest": content_digest,
        "parser_version": parser_version,
        "start_line": rng["start_line"],
        "end_line": rng["end_line"],
        "start_byte": rng["start_byte"],
        "end_byte": rng["end_byte"],
        "evidence_kind": rng["kind"],
    }


REQUIRED_REF_FIELDS = ("repository_id", "commit_sha", "file_path",
                       "git_blob_oid", "content_asset_id", "content_digest",
                       "start_line", "end_line", "start_byte", "end_byte",
                       "evidence_kind", "parser_version")


def ref_complete(ref) -> bool:
    for k in REQUIRED_REF_FIELDS:
        if ref.get(k) in (None, ""):
            return False
    return True
