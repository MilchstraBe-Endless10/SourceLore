#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一输出契约：结构化 JSON 进 stdout，错误进 stderr，退出码真实。"""

import json
import sys

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_FAILURE = 1
EXIT_UNAVAILABLE = 3


class SkillError(Exception):
    def __init__(self, message, *, code="ERROR", exit_code=EXIT_FAILURE, detail=None):
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code
        self.detail = detail or {}


def emit_ok(payload: dict) -> int:
    payload.setdefault("ok", True)
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return EXIT_OK


def emit_error(err: SkillError) -> int:
    sys.stderr.write(f"错误[{err.code}]: {err}\n")
    body = {"ok": False, "error": err.code, "message": str(err)}
    if err.detail:
        body["detail"] = err.detail
    sys.stdout.write(json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return err.exit_code
