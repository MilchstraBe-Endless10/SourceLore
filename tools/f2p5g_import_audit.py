#!/usr/bin/env python3
"""F2-P5G 有界导入审计：验证同名模块不会因子目录/sys.path 顺序解析错实现。

用法：
  python3 tools/f2p5g_import_audit.py            # 全审计
  python3 tools/f2p5g_import_audit.py --json     # JSON 输出
"""
import json
import subprocess
import sys
import tempfile
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

# 必须能解析到正确实现的模块 → 期望的 src 子目录
CRITICAL = {
    "content_knowledge_query": "content_persistence",
    "content_claim_adapter": "content_persistence",
    "content_fact_ingest": "content_persistence",
    "content_claim_ingest": "content_persistence",
    "content_extractor": "content",
    "blob_content_store": "storage",
    "content_ingest_coordinator": "storage",
    "captured_blob_loader": "content",
    "content_card_models": "renderer",
    "content_card_renderer": "renderer",
    "safe_html": "renderer",
    "content_card": "skill_interface",
    "content_capture": "skill_interface",
    "content_acquisition_policy": "collector",
    "blob_fetcher": "collector",
}

PROBE = r'''
import json, sys, os
for p in {paths!r}:
    if p not in sys.path:
        sys.path.insert(0, p)
out = {{}}
for name in {names!r}:
    try:
        m = __import__(name)
        out[name] = getattr(m, "__file__", None)
    except Exception as e:
        out[name] = "ERROR:" + type(e).__name__
print(json.dumps(out))
'''


def _paths_for(root, with_decoy=None):
    subs = ["runtime", "storage", "collector", "facts", "evidence_claims",
            "lifecycle", "views", "renderer", "research", "skill_interface",
            "content", "content_persistence"]
    ps = [str(root / "src" / s) for s in subs]
    if with_decoy:
        ps.insert(0, str(with_decoy))
    return ps


def probe(root, cwd, with_decoy=None):
    code = PROBE.format(paths=_paths_for(root, with_decoy),
                        names=sorted(CRITICAL))
    p = subprocess.run([sys.executable, "-c", code], capture_output=True,
                       text=True, cwd=str(cwd), timeout=120)
    if p.returncode != 0:
        return {"_error": p.stderr[-400:]}
    import json as _j
    return _j.loads(p.stdout.strip().splitlines()[-1])


def classify(results):
    problems = []
    for name, expected in CRITICAL.items():
        got = results.get(name)
        if not isinstance(got, str) or got.startswith("ERROR:"):
            problems.append({"module": name, "issue": "IMPORT_FAILED",
                             "detail": got})
            continue
        if f"/src/{expected}/" not in got.replace("\\", "/"):
            problems.append({"module": name, "issue": "WRONG_IMPLEMENTATION",
                             "expected_dir": expected, "resolved": got})
    return problems


def run():
    report = {"root": str(ROOT), "checks": []}

    # 1. 从项目根
    r1 = probe(ROOT, ROOT)
    report["checks"].append({"context": "project_root", "cwd": str(ROOT),
                             "problems": classify(r1)})

    # 2. 从 /tmp
    with tempfile.TemporaryDirectory() as td:
        r2 = probe(ROOT, td)
        report["checks"].append({"context": "from_tmp", "cwd": td,
                                 "problems": classify(r2)})

        # 3. 人为注入同名干扰模块
        decoy = Path(td) / "decoy"
        decoy.mkdir()
        for name in ("content_knowledge_query", "content_card_models",
                     "blob_content_store", "safe_html"):
            (decoy / f"{name}.py").write_text(
                "def __getattr__(n):\n"
                "    raise RuntimeError('DECOY_MODULE_LOADED')\n",
                encoding="utf-8")
        r3 = probe(ROOT, td, with_decoy=decoy)
        problems = classify(r3)
        # 干扰模块若被加载，会表现为 WRONG_IMPLEMENTATION 指向 decoy
        report["checks"].append({"context": "with_decoy_module", "cwd": td,
                                 "decoy_dir": str(decoy),
                                 "problems": problems})

    # 4. 安装版 Skill 独立进程
    installed = Path.home() / ".agents/skills/sourcelore"
    if installed.is_dir():
        # ★ 走安装版启动器自身的路径解析，不手工拼 sys.path
        probe_src = (
            "import sys, json\n"
            f"launcher = {str(installed/'scripts'/'sourcelore.py')!r}\n"
            "src = open(launcher, encoding='utf-8').read()\n"
            "g = {'__name__': '__launcher__', '__file__': launcher}\n"
            "exec(compile(src, launcher, 'exec'), g)\n"
            "import content_knowledge_query as m\n"
            "print(json.dumps({'file': m.__file__}))\n")
        r4 = subprocess.run([sys.executable, "-c", probe_src],
                            capture_output=True, text=True, cwd="/tmp",
                            timeout=120)
        if r4.returncode == 0:
            import json as _j
            got = _j.loads(r4.stdout.strip().splitlines()[-1])
            ok = "src/content_persistence/" in got["file"].replace("\\", "/") \
                 or "content_persistence/content_knowledge_query.py" in got["file"].replace("\\", "/")
            report["checks"].append({
                "context": "installed_skill_isolated_process",
                "installed_dir": str(installed),
                "resolved": got["file"],
                "problems": [] if ok else [{
                    "module": "content_knowledge_query",
                    "issue": "WRONG_IMPLEMENTATION_IN_INSTALLED_SKILL",
                    "resolved": got["file"]}]})
        else:
            report["checks"].append({
                "context": "installed_skill_isolated_process",
                "problems": [{"issue": "INSTALLED_PROBE_FAILED",
                              "detail": r4.stderr[-300:]}]})
    else:
        report["checks"].append({"context": "installed_skill",
                                 "problems": [],
                                 "note": "未安装，跳过"})

    total = sum(len(c["problems"]) for c in report["checks"])
    report["total_problems"] = total
    report["ok"] = total == 0
    return report


if __name__ == "__main__":
    rep = run()
    if "--json" in sys.argv:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        for c in rep["checks"]:
            mark = "OK  " if not c["problems"] else "FAIL"
            print(f"[{mark}] {c['context']}")
            for p in c["problems"]:
                print(f"        {p}")
        print(f"\n合计问题: {rep['total_problems']}  结论: "
              f"{'PASS' if rep['ok'] else 'FAIL'}")
    sys.exit(0 if rep["ok"] else 1)
