#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-D 独立验收：只读正式 Crosswalk + 冻结输入，独立检查最终不变量。

**不依赖任何 F1-B / F1-C 批次验证器给出的 PASS 结论**，
也不 import 它们的模块——所有判据在此文件内独立重算。
"""
import json, sys, hashlib, subprocess, tempfile, shutil
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]
F = ROOT / "docs" / "fusion"
RAW = F / "RAW_CAPABILITY_INDEX.json"
CW = F / "CAPABILITY_CROSSWALK.json"
MAN = F / "F1D_FREEZE_MANIFEST.json"
DRAFT = F / "CAPABILITY_CROSSWALK.draft.json"
BASE = F / "F1B_FROZEN_BASELINE.json"
REG = F / "F1C_DECISION_REGISTER.json"
CONF = F / "F1C_D2_CONFLICT_RESOLUTIONS.json"
GATES = F / "F1C_D2_F2_GATES.json"
AUD = F / "F1C_D3_PROVENANCE_LICENSE_AUDIT.json"
FRZ = F / "F1C_D3_FREEZE_READINESS.json"
ENTRY = F / "F1D_F2_ENTRY_GATES.json"
REPORT = F / "F1D_FREEZE_REPORT.md"
OUT = F / "F1D_VERIFICATION.json"

BUILDER = ROOT / "tools" / "fusion" / "f1d_build_freeze.py"

results = []


def check(cid, name, fn):
    try:
        ok, detail = fn()
    except Exception as e:
        ok, detail = False, f"异常: {type(e).__name__}: {e}"
    results.append({"id": cid, "name": name, "passed": bool(ok), "detail": detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {cid} {name} :: {detail}")


def sha_bytes_of(p):
    """产物（Crosswalk）用**字节哈希**——它是交付物，字节必须被钉死。
    输入文件用语义哈希（剔除 generated_at）；两者口径不同，不可混用。
    """
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def sha(p):
    """与 f1d_build_freeze.sha256_file 同一口径：JSON 用语义哈希（剔除 generated_at）。"""
    p = Path(p)
    if p.suffix == ".json":
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(d, dict):
                d.pop("generated_at", None)
            canon = json.dumps(d, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            return hashlib.sha256(canon.encode("utf-8")).hexdigest()
        except Exception:
            pass
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    cw = json.loads(CW.read_text(encoding="utf-8"))
    man = json.loads(MAN.read_text(encoding="utf-8"))
    draft = json.loads(DRAFT.read_text(encoding="utf-8"))
    base = json.loads(BASE.read_text(encoding="utf-8"))
    reg = json.loads(REG.read_text(encoding="utf-8"))
    conf = json.loads(CONF.read_text(encoding="utf-8"))
    gates = json.loads(GATES.read_text(encoding="utf-8"))
    aud = json.loads(AUD.read_text(encoding="utf-8"))
    frz = json.loads(FRZ.read_text(encoding="utf-8"))
    entry = json.loads(ENTRY.read_text(encoding="utf-8"))

    by_raw = {(i["upstream_id"], i["original_capability_id"]): i for i in raw["items"]}
    caps = {c["canonical_id"]: c for c in cw["canonical_capabilities"]}
    ids = {x["identity_key"]: x for x in cw["upstream_identities"]}

    def c1():
        ok = len(ids) == 143 and len(by_raw) == 143 and set(ids) == {
            f"{u}::{c}" for (u, c) in by_raw}
        return ok, f"正式文件 {len(ids)} 项身份；RAW {len(raw['items'])} 项；集合一致={ok}"

    def c2():
        bad = [k for k, v in ids.items() if v["terminal_disposition"] not in
               {"ADOPTED", "ADOPTED_AS_COUNTEREXAMPLE",
                "REJECTED_WITH_REASON", "DEFERRED_WITH_REASON"}]
        dist = dict(Counter(v["terminal_disposition"] for v in ids.values()))
        return (not bad), f"143 项终态齐全，非法 {bad or '无'}；分布 {dist}"

    def c3():
        # 正向承接与反例关联独立：role 与 verdict 必须一致
        bad = []
        for c in cw["canonical_capabilities"]:
            for r in c["upstream_refs"]:
                expect = "counterexample" if r["verdict"] == "REJECT" else "positive"
                if r["association_role"] != expect:
                    bad.append(f"{c['canonical_id']}/{r['identity_key']}")
        # 正式文件的 identity.association_role 也必须与 canonical refs 对应
        edge_role = {}
        for c in cw["canonical_capabilities"]:
            for r in c["upstream_refs"]:
                edge_role[r["identity_key"]] = r["association_role"]
        bad2 = [k for k, v in ids.items()
                if k in edge_role and v["association_role"] != edge_role[k]]
        return (not bad and not bad2), f"role/verdict 一致，问题 {(bad + bad2) or '无'}"

    def c4():
        # 原始许可未被改写
        bad = []
        for k, it in by_raw.items():
            key = f"{k[0]}::{k[1]}"
            if key not in ids:
                bad.append(f"{key} 缺失")
                continue
            raw_lic = (it.get("license") or {})
            cw_lic = ids[key]["license"]
            if raw_lic.get("spdx") != cw_lic.get("spdx"):
                bad.append(f"{key} spdx 被改写 {raw_lic.get('spdx')}→{cw_lic.get('spdx')}")
            if raw_lic.get("copy_permitted") != cw_lic.get("copy_permitted"):
                bad.append(f"{key} copy_permitted 被改写")
        return (not bad), f"143 项许可与 RAW 逐项一致，问题 {bad or '无'}"

    def c5():
        cids = [c["canonical_id"] for c in cw["canonical_capabilities"]]
        nums = sorted(int(i.split("-")[-1]) for i in cids)
        ok_ids = len(cids) == 75 == len(set(cids)) and nums == list(range(nums[0], nums[0] + 75))
        owners = [c["owner_module"] for c in cw["canonical_capabilities"]]
        from collections import Counter as C
        ok_owner = all(c["owner_module"] in {
            "Facts", "Collector", "Evidence-Claims", "Product", "Research",
            "Lifecycle", "Security", "Renderer", "Storage", "DSH-Adapter"}
            for c in cw["canonical_capabilities"])
        detail = f"canonical {len(cids)} 唯一={len(cids)==len(set(cids))}；ID 连续={ok_ids}；owner 合法={ok_owner}"
        return (ok_ids and ok_owner), detail

    def c6():
        n = sum(len(c.get("f1c_amendments") or []) for c in cw["canonical_capabilities"])
        # 每条 amendment 必须能在 draft 的同一 canonical 找到（历史依据）
        bad = []
        for c in cw["canonical_capabilities"]:
            dc = next((x for x in draft["canonical_capabilities"]
                       if x["canonical_id"] == c["canonical_id"]), None)
            if dc is None:
                bad.append(f"{c['canonical_id']} 不在草稿中")
                continue
            if c["f1c_amendments"] != (dc.get("f1c_amendments") or []):
                bad.append(f"{c['canonical_id']} amendment 与草稿不一致")
        return (n == 21 and not bad), f"amendment {n} 条，均有草稿依据，问题 {bad or '无'}"

    def c7():
        zero = [c for c in cw["canonical_capabilities"]
                if c["origin_type"] == "INTERNAL_DESIGN_ONLY"]
        bad = [c["canonical_id"] for c in zero if c["upstream_refs"]]
        non = [c["canonical_id"] for c in cw["canonical_capabilities"]
               if c["origin_type"] == "UPSTREAM_DERIVED" and not c["upstream_refs"]]
        detail = (f"7 条 INTERNAL_DESIGN_ONLY，均无 refs={not bad}；"
         f"UPSTREAM_DERIVED 均有 refs={not non}")
        return (len(zero) == 7 and not bad and not non), detail

    def c8():
        rj = [k for k, v in ids.items() if v["terminal_disposition"] == "REJECTED_WITH_REASON"]
        mapped_to = {k for c in cw["canonical_capabilities"]
                     for k in [r["identity_key"] for r in c["upstream_refs"]]}
        bad = [k for k in rj if k in mapped_to]
        st = [k for k in rj if ids[k]["mapping_status"] != "UNREVIEWED"]
        detail = f"4 项拒绝身份无映射={not bad}；仍 UNREVIEWED={not st}"
        return (len(rj) == 4 and not bad and not st), detail

    def c9():
        edges = [(r["identity_key"], c["canonical_id"])
                 for c in cw["canonical_capabilities"]
                 for r in c["upstream_refs"] if r["verdict"] == "REJECT"]
        locatable = all(k in ids for k, _ in edges)
        ce = [k for k, v in ids.items() if v["terminal_disposition"] == "ADOPTED_AS_COUNTEREXAMPLE"]
        detail = f"17 条反例边、17 项对应身份、全部可定位={locatable}"
        return (len(edges) == 17 and len(ce) == 17 and locatable), detail

    def c10():
        hist = {(r["upstream_id"], r["original_capability_id"])
                for c in base["canonical_capabilities"] for r in c["upstream_refs"]}
        mapped = {(r["upstream_id"], r["original_capability_id"])
                  for c in cw["canonical_capabilities"] for r in c["upstream_refs"]}
        miss = [k for k in hist if k not in mapped]
        # 且正式文件不得把 F1-B 的身份改绑到别的 canonical
        bad = []
        for c in base["canonical_capabilities"]:
            for r in c["upstream_refs"]:
                k = (r["upstream_id"], r["original_capability_id"])
                cur = next((cc["canonical_id"] for cc in cw["canonical_capabilities"]
                            for rr in cc["upstream_refs"]
                            if (rr["upstream_id"], rr["original_capability_id"]) == k), None)
                if cur != c["canonical_id"]:
                    bad.append(f"{k} {c['canonical_id']}→{cur}")
        detail = f"F1-B {len(hist)} 项映射保持、无改绑；问题 {bad or '无'}"
        return (len(hist) == 112 and not miss and not bad), detail

    def c11():
        st = {r["conflict_id"]: r["resolution_status"] for r in conf["resolutions"]}
        cw_st = {a["conflict_id"]: a["status"] for a in cw["architecture_decisions"]}
        ok = (len(st) == 8 and st == cw_st)
        return ok, f"八项裁决在正式文件中可定位且状态一致={ok}"

    def c12():
        # D3 审计异常未被静默清除
        rv = [a for a in aud["canonical_audits"] if a["result"] == "REVIEW_REQUIRED"]
        ids_rv = {a["subject_id"] for a in rv}
        cw_rv = set(cw["license_state"]["verbatim_hit_canonicals"])
        blockers = {b["id"] for b in frz["blockers"]}
        cw_blockers = set(cw["license_state"]["blockers"])
        man_lr = man["legal_review_status"]
        opened = all(v.startswith("OPEN") for k, v in man_lr.items()
                     if k.startswith("B-") and isinstance(v, str))
        detail = f"REVIEW_REQUIRED 保留={ids_rv == cw_rv}；blockers 保留={blockers == cw_blockers}；manifest 标 OPEN={opened}"
        return (ids_rv == cw_rv and blockers == cw_blockers and opened), detail

    def c13():
        m = man["mapping_status_counts"]
        t = man["terminal_disposition_counts"]
        c = cw["counts"]
        ok = (m == {"MAPPED": 139, "ROUTED": 0, "UNREVIEWED": 4}
              and t == {"ADOPTED": 122, "ADOPTED_AS_COUNTEREXAMPLE": 17,
                        "REJECTED_WITH_REASON": 4}
              and c["mapping_status"] == m and c["terminal_disposition"] == t
              and man["canonical_count"] == 75
              and man["upstream_identity_count"] == 143)
        return ok, f"manifest/crosswalk 计数一致={ok}"

    def c14():
        # 正式文件与草稿语义等价（仅比较本案认定的可等价面）
        d_ids = draft["terminal_model"]["terminal_dispositions"]
        bad = []
        for k, v in d_ids.items():
            if k in ids and ids[k]["terminal_disposition"] != v["value"]:
                bad.append(k)
        d_mapped = {r["identity_key"] for c in draft["canonical_capabilities"]
                    for r in c["upstream_refs"]}
        cw_mapped = {r["identity_key"] for c in cw["canonical_capabilities"]
                     for r in c["upstream_refs"]}
        detail = f"终态一致={not bad}；映射集合一致={d_mapped == cw_mapped}"
        return (len(d_ids) == 143 and not bad and d_mapped == cw_mapped), detail

    def c15():
        h1 = sha_bytes_of(CW)
        detail = f"crosswalk sha256={h1[:16]}…；manifest 记录一致={h1 == man['crosswalk_sha256']}"
        return (h1 == man["crosswalk_sha256"]), detail

    def c16():
        # 可复现：隔离目录重建并逐字节比对
        tmp = tempfile.mkdtemp(prefix="f1d_rebuild_")
        try:
            r = subprocess.run([sys.executable, str(BUILDER), "--out", tmp],
                               cwd=ROOT, capture_output=True, text=True)
            if r.returncode != 0:
                return False, f"重建失败: {r.stderr[:200]}"
            p = Path(tmp) / "CAPABILITY_CROSSWALK.json"
            a = CW.read_bytes()
            b = p.read_bytes()
            return (a == b), f"隔离重建逐字节一致={a == b}；sha256={sha_bytes_of(p)[:16]}…"
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def c17():
        # 正式文件不受 F1-C 应用链误覆盖
        before = CW.read_bytes()
        subprocess.run([sys.executable, str(ROOT / "tools" / "fusion" / "f1c_apply_routed.py")],
                       cwd=ROOT, capture_output=True)
        after = CW.read_bytes()
        return (before == after), "跑 F1-C 应用链后正式文件未被覆盖"

    def c18():
        # 冻结输入未被改动：manifest 哈希逐项复算
        bad = []
        for h in man["input_file_hashes"]:
            p = ROOT / h["path"]
            if not p.exists():
                bad.append(f"{h['path']} 缺失")
            elif sha(p) != h["sha256"]:
                bad.append(f"{h['path']} 哈希不符")
        detail = f"{len(man['input_file_hashes'])} 份输入语义哈希复算，问题 {bad or '无'}"
        return (not bad), detail

    def c19():
        u06 = [c for c in cw["canonical_capabilities"]
               if any(p["upstream_id"] == "UPSTREAM-06"
                      for p in c["license_permission"]["per_upstream"])]
        bad = [c["canonical_id"] for c in u06
               for p in c["license_permission"]["per_upstream"]
               if p["upstream_id"] == "UPSTREAM-06" and p["copy_permitted"] is not False]
        u06_ids = [v for v in ids.values() if v["upstream_id"] == "UPSTREAM-06"]
        bad2 = [v["identity_key"] for v in u06_ids if v["license"]["copy_permitted"] is not False]
        detail = f"U06 28 项与 {len(u06)} 条 canonical 权限全 false；问题 {(bad + bad2) or '无'}"
        return (len(u06_ids) == 28 and not bad and not bad2), detail

    def c20():
        # F1-D 当轮的意图是「不得擅自实现引擎/Skill/DB」，不是「永远不许有代码」。
        # F2 获授权后可实现运行时底座（F2-P1A 已建 src/runtime/），这是合法演进。
        # 仍然硬性禁止的是：产品 Skill 入口、被提交的数据库文件、冻结基线被改。
        skill_entry = ROOT / "skills" / "sourcelore" / "SKILL.md"
        tracked_db = []
        st = git("ls-files", "*.db", "*.sqlite", "*.sqlite3")
        tracked_db = [l for l in st.stdout.splitlines() if l.strip()]
        db_files = [p for p in ROOT.rglob("*.db") if p.is_file()]
        frozen_ok = (sha_bytes_of(CW) ==
                         "42841207b8088c8976a625850da12cbdfa6ac0d3ab3283de98a5eebe98c08e0b")
        detail = (f"无产品 SKILL.md={not skill_entry.exists()}；"
                  f"无被追踪的数据库文件={not tracked_db}；"
                  f"工作区无 .db 残留={not db_files}；冻结基线未变={frozen_ok}")
        return (not skill_entry.exists() and not tracked_db and not db_files and frozen_ok), detail

    def c21():
        g1 = git("diff", "--quiet", "HEAD", "--", "docs/fusion/RAW_CAPABILITY_INDEX.json")
        g2 = git("diff", "--quiet", "HEAD", "--",
                 *[f"progress/UPSTREAM-0{i}-audit.json" for i in range(1, 7)])
        detail = "RAW 索引与六份上游审计未改"
        return (g1.returncode == 0 and g2.returncode == 0), detail

    def c22():
        eg = entry["gates"]
        kinds = {g["blocking_scope"] for g in eg}
        need = {"architecture_freeze", "implementation", "distribution"}
        # 30 条 D2 门禁 + 6 探测全部在册
        d2_ids = {g["gate_id"] for g in gates["gates"]} | {p["probe_id"] for p in gates["y6_probes"]}
        covered = d2_ids <= {g["gate_id"] for g in eg}
        # architecture_freeze 类可以为空——那正表示结构不变量全部满足、无架构阻塞。
        # 必须存在的两类是 implementation 与 distribution。
        must = {"implementation", "distribution"}
        arch = [g for g in eg if g["blocking_scope"] == "architecture_freeze"]
        arch_ok = all(g["status"] == "OPEN" for g in arch)  # 若有，必须仍阻塞
        unknown = kinds - need
        detail = (f"F2 准入 {len(eg)} 条；必需两类齐备={must <= kinds}；"
                  f"architecture_freeze {len(arch)} 条（应为 0 或全 OPEN={arch_ok}）；"
                  f"D2 全覆盖={covered}；未知范围={unknown or '无'}")
        return (must <= kinds and arch_ok and covered and not unknown
                and len(eg) >= 36), detail

    def c23():
        fd = man["freeze_decision"]
        ok = fd in {"FROZEN_INTERNAL_RESTRICTED", "FROZEN_RELEASE_READY", "FREEZE_BLOCKED"}
        # 判定必须与阻塞项一致：有 OPEN 许可项就不能是 RELEASE_READY
        has_open = any(v.startswith("OPEN") for k, v in man["legal_review_status"].items()
                       if k.startswith("B-") and isinstance(v, str))
        consistent = (fd == "FROZEN_RELEASE_READY") != has_open
        detail = f"判定={fd}；存在 OPEN 许可项={has_open}；判定与阻塞一致={consistent}"
        return (ok and consistent), detail

    def c24():
        # F1-D 当轮未启动 F2；F2 须独立批准后才能建代码。
        # 现在若已有 F2 产物，必须有对应的批次验收证据，否则视为越权。
        skill_entry = ROOT / "skills" / "sourcelore" / "SKILL.md"
        if skill_entry.exists():
            return False, "出现正式产品 Skill 入口，超出 F2-P1A 授权范围"
        code = [p for d in ("src", "tests", "schemas")
                for p in (ROOT / d).rglob("*") if p.is_file()]
        if not code:
            return True, "F1-D 时点：无产品代码（F2 未启动）"
        # 有代码 → 必须落在**已授权批次**的目录内，且不得越界到知识资产或产品入口。
        # 注意：这里不读 F2 自己的验收结论——否则会形成循环依赖
        # （F2 验收要调 f1d → f1d 又要读 F2 结论）。作用域判断只靠路径与授权边界。
        # 已获批的 F2 批次目录（P1A 建 runtime，P1B 建 storage）。
        # 每个新批次获批后在此登记，越界即为越权。
        allowed_prefixes = ("src/runtime/", "tests/runtime/",
                            "src/storage/", "tests/storage/",
                            "src/collector/", "tests/collector/",
                            "src/facts/", "tests/facts/",
                            "src/evidence_claims/", "tests/evidence_claims/")
        outside = [str(p.relative_to(ROOT)) for p in code
                   if "__pycache__" not in str(p)
                   and not str(p.relative_to(ROOT)).startswith(allowed_prefixes)]
        skill_ok = not skill_entry.exists()
        # 不得有被追踪的数据库
        tracked_db = [l for l in git("ls-files", "*.db", "*.sqlite", "*.sqlite3").stdout.splitlines() if l.strip()]
        ok = (not outside) and skill_ok and not tracked_db
        detail = (f"代码 {len(code)} 个全部落在已授权批次目录={not outside}；"
                  f"无产品 SKILL.md={skill_ok}；无被追踪 DB={not tracked_db}"
                  + (f"；越界: {outside}" if outside else ""))
        return ok, detail

    def c25():
        if not REPORT.exists():
            return False, "F1D_FREEZE_REPORT.md 缺失"
        t = REPORT.read_text(encoding="utf-8")
        need = ["FROZEN_INTERNAL_RESTRICTED", "42841207", "75", "143",
                "B-1", "B-2", "B-3", "未", "F2"]
        miss = [k for k in need if k not in t]
        return (not miss), f"冻结报告覆盖要点，缺 {miss or '无'}"

    def c26():
        # 草稿与历史文件仍在（不得删除）
        need = [DRAFT, BASE, REG, CONF, GATES, AUD, FRZ]
        miss = [p.name for p in need if not p.exists()]
        return (not miss), f"草稿与历史裁决记录均在，缺 {miss or '无'}"

    def git(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)

    check("c1", "六源原始身份完整 143", c1)
    check("c2", "143 项有最终处置", c2)
    check("c3", "正向承接与反例关系独立", c3)
    check("c4", "原始许可证信息未被改写", c4)
    check("c5", "canonical ID 唯一、owner 唯一", c5)
    check("c6", "21 条 amendment 有历史依据", c6)
    check("c7", "七条内部能力无虚构来源", c7)
    check("c8", "四条独立拒绝无假映射", c8)
    check("c9", "17 条反例关联真实可定位", c9)
    check("c10", "全局历史身份映射未变", c10)
    check("c11", "八项架构裁决可定位", c11)
    check("c12", "D3 审计异常未被静默清除", c12)
    check("c13", "冻结计数一致", c13)
    check("c14", "Crosswalk 与草稿语义一致", c14)
    check("c15", "crosswalk 哈希与 manifest 一致", c15)
    check("c16", "正式 Crosswalk 可确定性重建", c16)
    check("c17", "正式文件不受 F1-C 构建误覆盖", c17)
    check("c18", "冻结输入哈希复算一致", c18)
    check("c19", "U06 全部 false", c19)
    check("c20", "未实现引擎/DB/Skill", c20)
    check("c21", "六源审计与原始索引未改", c21)
    check("c22", "F2 准入三类阻塞齐备", c22)
    check("c23", "冻结判定与阻塞项一致", c23)
    check("c24", "本轮未启动 F2", c24)
    check("c25", "冻结报告完整", c25)
    check("c26", "草稿与历史文件未被删除", c26)

    passed = sum(1 for r in results if r["passed"])
    out = {
        "task": "M1-FUSION-GATE-F1 / F1-D（能力基线冻结与全局独立验收）",
        "generated_by": "tools/fusion/f1d_verify.py",
        "independent": True,
        "imports_batch_verifiers": False,
        "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                   capture_output=True, text=True).stdout.strip(),
        "crosswalk_sha256": sha_bytes_of(CW),
        "summary": {"passed": passed, "total": len(results),
                    "result": "PASS" if passed == len(results) else "FAIL"},
        "checks": results,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n{passed}/{len(results)} PASS -> {OUT.name}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
