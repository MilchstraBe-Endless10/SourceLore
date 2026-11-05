#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JSONC 解析（tsconfig / jsconfig）。

★ 必须按字符状态机区分字符串与注释——绝不用正则删注释，
   因为 `"https://example.com"` 与 `"text // not a comment"` 是合法字符串。
"""

import json

PARSER_ID = "tsconfig-jsonc"
PARSER_VERSION = "jsonc/1"

MAX_CONFIG_BYTES = 512 * 1024


class JsoncError(Exception):
    def __init__(self, code, detail, line=None):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.line = line


def strip_comments(text):
    """去掉 // 与 /* */ 注释，保留字符串内容与位置信息。

    返回 (cleaned_text, spans)。spans 记录被移除区间，供诊断。
    """
    out = []
    i = 0
    n = len(text)
    state = "code"          # code | string | line_comment | block_comment
    quote = None
    start = 0

    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""

        if state == "code":
            if ch == '"' or ch == "'":
                state = "string"
                quote = ch
                out.append(ch)
                i += 1
            elif ch == "/" and nxt == "/":
                state = "line_comment"
                i += 2
            elif ch == "/" and nxt == "*":
                state = "block_comment"
                i += 2
            else:
                out.append(ch)
                i += 1

        elif state == "string":
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                # 转义：连同下一个字符一起保留
                out.append(text[i + 1])
                i += 2
                continue
            if ch == quote:
                state = "code"
                quote = None
            i += 1

        elif state == "line_comment":
            if ch == "\n":
                out.append("\n")
                state = "code"
            i += 1

        elif state == "block_comment":
            if ch == "*" and nxt == "/":
                state = "code"
                i += 2
            else:
                if ch == "\n":
                    out.append("\n")     # 保留行号
                i += 1

    if state in ("string", "block_comment"):
        raise JsoncError("JSONC_UNTERMINATED",
                         f"未闭合的 {state}", text.count("\n") + 1)
    return "".join(out), []


def strip_trailing_commas(text):
    """去掉 `,` 后紧跟 `}` 或 `]` 的尾随逗号。★ 跳过字符串内部。"""
    out = []
    i = 0
    n = len(text)
    in_str = False
    quote = None
    while i < n:
        ch = text[i]
        if in_str:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == quote:
                in_str = False
                quote = None
            i += 1
            continue
        if ch in "\"'":
            in_str = True
            quote = ch
            out.append(ch)
            i += 1
            continue
        if ch == ",":
            j = i + 1
            while j < n and text[j] in " \t\r\n":
                j += 1
            if j < n and text[j] in "}]":
                i += 1          # 丢弃该逗号
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def parse_jsonc(text, *, path="tsconfig.json"):
    """解析 JSONC。返回 dict。失败抛 JsoncError。"""
    if not isinstance(text, str):
        raise JsoncError("JSONC_INPUT_NOT_TEXT", "输入不是文本", None)
    raw_len = len(text.encode("utf-8"))
    if raw_len > MAX_CONFIG_BYTES:
        raise JsoncError("JSONC_TOO_LARGE",
                         f"{raw_len} 字节超过上限 {MAX_CONFIG_BYTES}", None)

    cleaned, _ = strip_comments(text)
    cleaned = strip_trailing_commas(cleaned)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise JsoncError("JSONC_INVALID_JSON",
                         f"{e.msg} @line {e.lineno}", e.lineno)

    if not isinstance(data, dict):
        raise JsoncError("JSONC_NOT_OBJECT", "顶层不是 JSON 对象", None)
    return data


def parse_jsonc_bytes(raw, *, path="tsconfig.json"):
    """从字节解析（处理 BOM）。"""
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise JsoncError("JSONC_UNSUPPORTED_ENCODING", str(e), None)
    return parse_jsonc(text, path=path)
