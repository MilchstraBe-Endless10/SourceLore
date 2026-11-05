#!/usr/bin/env python3
"""源码字节/行号定位。

★ 关键：AST col_offset 是 **UTF-8 字节偏移**（相对行首，不含换行符）。
   要得到整文件绝对字节偏移，需按行累加该行真实字节长度。
"""

LINE_ENDS = ("\n", "\r\n", "\r")


def decode_source(raw: bytes):
    """返回 (text, encoding, had_bom) 或抛 ValueError。"""
    bom = raw[:3] == b"\xef\xbb\xbf"
    if bom:
        raw_body = raw[3:]
        enc = "utf-8-sig"
    else:
        raw_body = raw
        enc = "utf-8"
    try:
        text = raw_body.decode("utf-8")
    except UnicodeDecodeError as e:
        raise ValueError(f"UNSUPPORTED_ENCODING: {e}")
    if "\x00" in text:
        raise ValueError("BINARY_CONTENT: NUL byte")
    return text, enc, bom


def line_starts_bytes(raw: bytes):
    """每行起始的**绝对字节偏移**（0 基）。同时返回行文本列表。

    ★ 按原始字节切分，保留 CRLF / LF / 单独 CR。
    """
    starts = [0]
    lines = []
    i = 0
    n = len(raw)
    cur = 0
    while i < n:
        b = raw[i]
        if b == 0x0A:                       # LF
            lines.append(raw[cur:i + 1])
            cur = i + 1
            starts.append(cur)
        elif b == 0x0D:                     # CR or CRLF
            if i + 1 < n and raw[i + 1] == 0x0A:
                lines.append(raw[cur:i + 2])
                cur = i + 2
                starts.append(cur)
                i += 1
            else:
                lines.append(raw[cur:i + 1])
                cur = i + 1
                starts.append(cur)
        i += 1
    if cur < n:
        lines.append(raw[cur:n])
        starts.append(n)
    return starts, lines


def abs_byte(line_no, col_offset, starts, raw):
    """(1 基行号, 该行 UTF-8 字节列偏移) → 整文件绝对字节偏移。"""
    if line_no < 1:
        return 0
    if line_no - 1 >= len(starts):
        return len(raw)
    return min(starts[line_no - 1] + col_offset, len(raw))


def byte_range_of(node, starts, raw):
    """AST 节点的字节范围（半开区间 [start, end)）。"""
    sl = node.lineno
    sc = node.col_offset
    el = getattr(node, "end_lineno", sl)
    ec = getattr(node, "end_col_offset", sc)
    start = abs_byte(sl, sc, starts, raw)
    end = abs_byte(el, ec, starts, raw)
    if end < start:
        end = start
    return start, end


def line_range_of(node):
    return node.lineno, getattr(node, "end_lineno", node.lineno)


def verify_range(raw: bytes, *, start_byte, end_byte, start_line, end_line,
                 expect_text=None):
    """★ 核验证据范围确实覆盖该声明。返回问题清单（空=通过）。"""
    problems = []
    if start_byte < 0 or end_byte > len(raw) or end_byte <= start_byte:
        problems.append("RANGE_OUT_OF_BOUNDS")
        return problems
    starts, _ = line_starts_bytes(raw)
    if start_line < 1 or start_line > len(starts):
        problems.append("LINE_OUT_OF_RANGE")
    if end_line < start_line:
        problems.append("END_LINE_BEFORE_START")
    if expect_text is not None:
        snippet = raw[start_byte:end_byte].decode("utf-8", "replace")
        if expect_text.strip() and expect_text.strip() not in snippet:
            problems.append("TEXT_NOT_IN_RANGE")
    return problems


def to_evidence_ref(*, kind, start_byte, end_byte, start_line, end_line,
                    git_blob_oid, file_path, raw):
    """结构化证据引用。★ label 只放结构化描述，不回显原文（D-6 规则）。"""
    import hashlib
    snippet = raw[start_byte:end_byte]
    return {
        "kind": kind,
        "label": f"{kind}@L{start_line}-{end_line}",
        "start_byte": start_byte,
        "end_byte": end_byte,
        "start_line": start_line,
        "end_line": end_line,
        "byte_length": end_byte - start_byte,
        "git_blob_oid": git_blob_oid,
        "file_path": file_path,
        "snippet_sha256": "sha256:" + hashlib.sha256(snippet).hexdigest(),
    }
