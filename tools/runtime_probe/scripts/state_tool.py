#!/usr/bin/env python3
"""状态写入/读取工具。只允许在受控目录内读写，防止越界。"""
import json, sys, os
from pathlib import Path

ALLOWED_ROOT = Path(os.environ.get("SOURCELORE_PROBE_ROOT", "")).resolve()

def main():
    if not ALLOWED_ROOT or not ALLOWED_ROOT.exists():
        print(json.dumps({"error": "PROBE_ROOT_NOT_SET"}))
        return 2
    op = sys.argv[1] if len(sys.argv) > 1 else ""
    key = sys.argv[2] if len(sys.argv) > 2 else ""
    val = sys.argv[3] if len(sys.argv) > 3 else ""
    target = (ALLOWED_ROOT / f"{key}.json").resolve()
    # 越界保护：目标必须仍在受控目录内
    if ALLOWED_ROOT not in target.parents and target.parent != ALLOWED_ROOT:
        print(json.dumps({"error": "PATH_ESCAPE_BLOCKED", "target": str(target)}))
        return 3
    if op == "write":
        target.write_text(json.dumps({"key": key, "value": val, "pid": os.getpid()},
                                     ensure_ascii=False), encoding="utf-8")
        print(json.dumps({"op": "write", "ok": True, "path": target.name}))
    elif op == "read":
        if not target.exists():
            print(json.dumps({"op": "read", "ok": False, "error": "NOT_FOUND"}))
            return 4
        print(json.dumps({"op": "read", "ok": True, **json.loads(target.read_text(encoding="utf-8"))}))
    else:
        print(json.dumps({"error": "UNKNOWN_OP"}))
        return 5
    return 0

if __name__ == "__main__":
    sys.exit(main())
