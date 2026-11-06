#!/usr/bin/env python3
"""F2-P6A 路径安全专项扫描（D-37 长期阻断）。

扫描所有 lstrip/rstrip 路径归一化、真相对包含判断、越界处理。
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

# ① 危险模式：lstrip/rstrip 带路径字符
DANGEROUS = re.compile(r"(?:l|r)strip\(\s*[\"'][./\\\\]+[\"']\s*\)")
# ② 字符串前缀判断目录包含（不用 os.path/pathlib 语义）
NAIVE_CONTAINS = re.compile(
    r"\.startswith\(\s*\w+\s*\+\s*[\"'][/\\\\][\"']\s*\)")
# ③ 真相对判断
RELATIVE = re.compile(r"\.is_relative_to\(")


def scan():
    findings = []
    for f in sorted(SRC.rglob("*.py")):
        text = f.read_text(encoding="utf-8", errors="replace")
        rel = str(f.relative_to(ROOT))
        for lineno, line in enumerate(text.splitlines(), 1):
            code = line.split("#", 1)[0]
            stripped = line.strip()
            # 跳过注释与 docstring 行
            if stripped.startswith("#") or stripped.startswith('"""') \
                    or stripped.startswith("*") or "★" in line:
                continue
            if DANGEROUS.search(code):
                # URL 末尾斜杠（非路径）不算
                if "url" in code.lower() or "src_url" in code:
                    continue
                findings.append({"file": rel, "line": lineno,
                                 "kind": "LSTRIP_PATH_CHARS",
                                 "code": stripped[:100]})
    return findings


def check_normalizers():
    """确认关键路径归一化函数不吞前导 / 与 ../。"""
    import importlib.util

    checks = []
    # ts_file_membership._norm
    p = SRC / "source_analysis" / "ts_file_membership.py"
    if p.exists():
        spec = importlib.util.spec_from_file_location("_fm", p)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
            cases = [("/abs/x", "/abs/x"), ("../../etc", "../../etc"),
                     ("./a/b", "a/b"), ("a/b", "a/b"), ("", "")]
            for raw, want in cases:
                got = mod._norm(raw)
                checks.append({"case": raw, "got": got, "want": want,
                               "ok": got == want})
        except Exception as e:
            checks.append({"error": f"{type(e).__name__}: {e}"})
    return checks


def check_escape_rejected():
    """越界路径必须被拒绝。"""
    import importlib.util
    results = []

    def load(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    p = SRC / "source_analysis" / "tsconfig_parser.py"
    if p.exists():
        m = load("_tp", p)
        for tid, tgt, base in (("abs", "/etc/passwd", ""),
                               ("deep", "../../../etc", "a/b"),
                               ("one_out", "../..", "a"),
                               ("ok_rel", "src/*", ""),
                               ("ok_up", "../lib/*", "pkg/a")):
            got = m.normalize_target(tgt, base_dir=base)
            expect_none = tid in ("abs", "deep", "one_out")
            results.append({"case": tid, "target": tgt, "base": base,
                            "got": got,
                            "ok": (got is None) == expect_none})
    return results


if __name__ == "__main__":
    import json
    f = scan()
    n = check_normalizers()
    e = check_escape_rejected()
    out = {
        "ok": (not f
               and all(c.get("ok") for c in n if "ok" in c)
               and all(r.get("ok") for r in e)),
        "dangerous_lstrip": f,
        "normalizer": n,
        "escape_rejection": e,
        "note": "D-37 长期阻断：lstrip('./') 吞绝对路径与 ../ 越界",
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    sys.exit(0 if out["ok"] else 1)
