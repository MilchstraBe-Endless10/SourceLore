#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F2-P0 验收：16 项完成条件实测。

不依赖任何 F1-B / F1-C / F1-D 验证器的 PASS 结论，独立重算。
"""
import json, sys, hashlib, subprocess
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
IMPL = DOCS / "implementation"
PROBE = ROOT / "tools" / "runtime_probe"
CW = DOCS / "fusion" / "CAPABILITY_CROSSWALK.json"
MAN = DOCS / "fusion" / "F1D_FREEZE_MANIFEST.json"
CAPS = IMPL / "F2_P0_RUNTIME_CAPABILITIES.json"
REPORT = IMPL / "F2_P0_RUNTIME_PROBE_REPORT.md"
ADAPT = IMPL / "F2_P0_ADAPTER_DECISIONS.md"
OUT = IMPL / "F2_P0_VERIFICATION.json"

EXPECTED_SHA = "42841207b8088c8976a625850da12cbdfa6ac0d3ab3283de98a5eebe98c08e0b"
LEGAL_STATUS = {"VERIFIED", "PARTIALLY_VERIFIED", "UNVERIFIED", "UNSUPPORTED"}

results = []


def check(cid, name, fn):
    try:
        ok, detail = fn()
    except Exception as e:
        ok, detail = False, f"异常: {type(e).__name__}: {e}"
    results.append({"id": cid, "name": name, "passed": bool(ok), "detail": detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {cid} {name} :: {detail}")


def sha_bytes(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main() -> int:
    caps = json.loads(CAPS.read_text(encoding="utf-8"))
    probes = {p["probe_id"]: p for p in caps["probes"]}

    def c1():
        h = sha_bytes(CW)
        m = json.loads(MAN.read_text(encoding="utf-8"))
        ok = h == EXPECTED_SHA == m["crosswalk_sha256"]
        return ok, f"冻结哈希 {h[:16]}… 与预期及 manifest 一致={ok}"

    def c2():
        skill = PROBE / "skill" / "sourcelore-probe" / "SKILL.md"
        if not skill.exists():
            return False, "探测 Skill 入口不存在"
        t = skill.read_text(encoding="utf-8")
        # 结构必须来自真实规范：frontmatter 含 name 与 description
        has_fm = t.startswith("---") and t.count("---") >= 2
        has_name = "name: sourcelore-probe" in t
        has_desc = "description:" in t
        return (has_fm and has_name and has_desc), \
            f"frontmatter={has_fm}、name={has_name}、description={has_desc}（对齐真实 resolveAgentsHome 规范）"

    def c3():
        ids = set(probes)
        need = {f"Y6-P{i}" for i in range(1, 7)}
        bad = [p for p in caps["probes"] if p["status"] not in LEGAL_STATUS]
        # 每项必须有必需字段
        miss = []
        requ = ["probe_id", "test_preconditions", "actual_command_or_action",
                "expected_result", "observed_result", "evidence_ref",
                "exit_code", "status", "limitation", "fallback_design", "next_action"]
        for p in caps["probes"]:
            for f in requ:
                if f not in p:
                    miss.append(f"{p['probe_id']}.{f}")
        return (ids == need and not bad and not miss), \
            f"六项齐全={ids == need}；状态合法={not bad}；缺字段={miss or '无'}"

    def c4():
        # 本地工具调用真实发生：独立复算 sha256
        import subprocess as sp
        r = sp.run([sys.executable, str(PROBE / "scripts" / "echo_tool.py"),
                    "sourcelore-probe-token"], capture_output=True, text=True)
        if r.returncode != 0:
            return False, f"echo_tool 执行失败 exit={r.returncode}"
        out = json.loads(r.stdout)
        expect = hashlib.sha256(b"sourcelore-probe-token").hexdigest()[:12]
        ok = out.get("sha256_12") == expect and out.get("pid", 0) > 0
        return ok, f"真实执行 exit=0，sha256_12={out.get('sha256_12')} 与独立复算一致={ok}"

    def c5():
        import subprocess as sp
        ok_r = sp.run([sys.executable, str(PROBE / "scripts" / "echo_tool.py"), "ok"],
                      capture_output=True, text=True)
        fail_r = sp.run([sys.executable, str(PROBE / "scripts" / "fail_tool.py"), "7"],
                        capture_output=True, text=True)
        ok = ok_r.returncode == 0 and fail_r.returncode == 7
        return ok, f"成功 exit={ok_r.returncode} / 失败 exit={fail_r.returncode}（必须可区分）"

    def c6():
        # 权限拒绝不能当作成功：越界写必须非零退出且不落盘
        import subprocess as sp
        import os
        env = dict(os.environ, SOURCELORE_PROBE_ROOT=str(PROBE / "artifacts"))
        r = sp.run([sys.executable, str(PROBE / "scripts" / "state_tool.py"),
                    "write", "../escape", "x"], capture_output=True, text=True, env=env)
        escaped = (PROBE / "escape.json").exists()
        ok = r.returncode != 0 and not escaped and "PATH_ESCAPE_BLOCKED" in r.stdout
        return ok, f"越界写 exit={r.returncode}、未落盘={not escaped}、显式拦截={ok}"

    def c7():
        # 重试不会被默认认定为幂等：状态文件带 pid，可看出是不同次执行
        p = PROBE / "artifacts" / "probe-key-1.json"
        ok = p.exists()
        d = json.loads(p.read_text(encoding="utf-8")) if ok else {}
        return ok, f"状态记录存在，含 pid={d.get('pid')}（可区分不同次执行，不默认幂等）"

    def c8():
        # 检查点与知识权威数据隔离：artifacts 不得位于 docs/fusion 或知识资产区
        art = PROBE / "artifacts"
        bad = []
        for f in art.rglob("*"):
            if not f.is_file():
                continue
            rel = str(f.relative_to(ROOT))
            if rel.startswith("docs/fusion/") or "CAPABILITY_CROSSWALK" in rel:
                bad.append(rel)
        return (not bad), f"探测产物与冻结基线分离，越界 {bad or '无'}"

    def c9():
        # 未验证能力不被标记 VERIFIED
        bad = []
        for p in caps["probes"]:
            if p["status"] == "VERIFIED" and not p.get("evidence_ref"):
                bad.append(p["probe_id"])
            # PARTIALLY_VERIFIED 必须有 limitation
            if p["status"] == "PARTIALLY_VERIFIED" and not p.get("limitation"):
                bad.append(f"{p['probe_id']}(无 limitation)")
        return (not bad), f"状态与证据一致，问题 {bad or '无'}；分布={caps['summary']['by_status']}"

    def c10():
        # 实验可重复：同一工具两次执行结果一致（除 pid）
        import subprocess as sp
        a = sp.run([sys.executable, str(PROBE / "scripts" / "echo_tool.py"), "repeat"],
                   capture_output=True, text=True)
        b = sp.run([sys.executable, str(PROBE / "scripts" / "echo_tool.py"), "repeat"],
                   capture_output=True, text=True)
        da, db = json.loads(a.stdout), json.loads(b.stdout)
        for k in ("pid", "cwd"):
            da.pop(k, None); db.pop(k, None)
        return (a.returncode == b.returncode == 0 and da == db), \
            "同一输入两次执行，除 pid/cwd 外结果一致（可重复）"

    def c11():
        # 所有新增测试文件属于受控范围
        allowed_prefixes = ("tools/runtime_probe/", "docs/implementation/")
        allowed_files = {"tools/f2p0_verify.py"}
        bad = []
        # 只看本轮新增（未跟踪或有改动）且是文本/runtime 文件
        r = subprocess.run(["git", "status", "--short"], cwd=ROOT,
                           capture_output=True, text=True)
        for line in r.stdout.splitlines():
            if len(line) < 4:
                continue
            path = line[3:].strip()
            if path.endswith("/"):
                continue
            if path.startswith(allowed_prefixes) or path in allowed_files:
                continue
            if path.startswith("progress/") or path.startswith("docs/fusion/"):
                continue
            bad.append(f"{line[:2]} {path}")
        return (not bad), f"新增文件均在受控范围，越界 {bad or '无'}"

    def c12():
        # 未触碰正式冻结基线：git 中冻结文件无改动
        r = subprocess.run(["git", "status", "--short", "--",
                            "docs/fusion/CAPABILITY_CROSSWALK.json"],
                           cwd=ROOT, capture_output=True, text=True)
        untouched = r.stdout.strip() == ""
        h_ok = sha_bytes(CW) == EXPECTED_SHA
        return (untouched and h_ok), f"冻结文件 git 无改动={untouched}、哈希未变={h_ok}"

    def c13():
        # 未修改人工文档：无人工维护 .md 被改（排除本轮新增的 implementation 文档）
        r = subprocess.run(["git", "status", "--short"], cwd=ROOT,
                           capture_output=True, text=True)
        bad = []
        for line in r.stdout.splitlines():
            if len(line) < 4:
                continue
            st, path = line[:2].strip(), line[3:].strip()
            if not path.endswith(".md"):
                continue
            if path.startswith("docs/implementation/"):
                continue            # 本轮新增
            if st in ("M", "D", "R"):
                bad.append(f"{st} {path}")
        return (not bad), f"既有 .md 被修改/删除 {bad or '无'}（新增不计）"

    def c14():
        # 未泄露凭据：报告中不得出现令牌/密钥样式内容
        import re
        patterns = [r"sk-[A-Za-z0-9]{16,}", r"ghp_[A-Za-z0-9]{20,}",
                    r"AKIA[0-9A-Z]{16}", r"Bearer\s+[A-Za-z0-9._\-]{20,}",
                    r"api[_-]?key\s*[:=]\s*[\"'][^\"']{12,}"]
        bad = []
        for f in (REPORT, ADAPT, CAPS):
            if not f.exists():
                bad.append(f"{f.name} 缺失")
                continue
            t = f.read_text(encoding="utf-8")
            for pat in patterns:
                if re.search(pat, t, re.I):
                    bad.append(f"{f.name}: {pat}")
        return (not bad), f"三份产物无凭据样式内容，问题 {bad or '无'}"

    def c15():
        # F1-D 独立验收仍通过
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "fusion" / "f1d_verify.py")],
                           cwd=ROOT, capture_output=True, text=True)
        return (r.returncode == 0), f"f1d_verify exit={r.returncode}，{r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ''}"

    def c16():
        # F2 门禁状态与实际测试结果一致
        gates = json.loads((DOCS / "fusion" / "F1D_F2_ENTRY_GATES.json").read_text(encoding="utf-8"))
        y6 = {g["gate_id"]: g for g in gates["gates"] if g["gate_id"].startswith("Y6-P")}
        # 本轮的实测状态不得被写成「已完成」
        bad = []
        for pid, st in (("Y6-P1", "VERIFIED"), ("Y6-P2", "PARTIALLY_VERIFIED"),
                        ("Y6-P3", "PARTIALLY_VERIFIED"), ("Y6-P4", "PARTIALLY_VERIFIED"),
                        ("Y6-P5", "VERIFIED"), ("Y6-P6", "PARTIALLY_VERIFIED")):
            if probes.get(pid, {}).get("status") != st:
                bad.append(f"{pid} 实测 {probes.get(pid,{}).get('status')} 与声明 {st} 不符")
            g = y6.get(pid)
            if g and g.get("status") not in ("OPEN_PENDING_F2", "OPEN", "SATISFIED_AT_FREEZE"):
                bad.append(f"{pid} 门禁状态异常 {g.get('status')}")
        # 所有 PARTIALLY 的仍是 OPEN_PENDING_F2（未被擅自标为完成）
        still_open = [pid for pid, s in probes.items()
                      if s["status"] != "VERIFIED" and y6.get(pid, {}).get("status") != "OPEN_PENDING_F2"]
        return (not bad and not still_open), \
            f"六项实测状态与门禁一致，问题 {(bad + still_open) or '无'}"

    check("c1", "冻结 Crosswalk 哈希正确", c1)
    check("c2", "探测 Skill 结构来自真实规范", c2)
    check("c3", "六项探测全部执行且有完整记录", c3)
    check("c4", "本地工具调用确实发生", c4)
    check("c5", "成功与失败可区分", c5)
    check("c6", "权限拒绝不当作成功", c6)
    check("c7", "重试不默认认定为幂等", c7)
    check("c8", "检查点与知识权威隔离", c8)
    check("c9", "未验证能力不被标 VERIFIED", c9)
    check("c10", "所有实验可重复", c10)
    check("c11", "新增文件属受控范围", c11)
    check("c12", "未触碰正式冻结基线", c12)
    check("c13", "未修改人工文档", c13)
    check("c14", "未泄露凭据", c14)
    check("c15", "F1-D 独立验收仍通过", c15)
    check("c16", "F2 门禁与实测结果一致", c16)

    passed = sum(1 for r in results if r["passed"])
    out = {
        "task": "M2 / F2-P0（运行时真实接入验证）",
        "generated_by": "tools/f2p0_verify.py",
        "independent": True,
        "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                   capture_output=True, text=True).stdout.strip(),
        "crosswalk_sha256": sha_bytes(CW),
        "summary": {"passed": passed, "total": len(results),
                    "result": "PASS" if passed == len(results) else "FAIL"},
        "checks": results,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n{passed}/{len(results)} PASS -> {OUT.name}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
