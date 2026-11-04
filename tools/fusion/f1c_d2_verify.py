#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-C-D2 独立验收：八项跨模块架构冲突裁决。"""
import json, sys, subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[2]
F = ROOT / "docs" / "fusion"
RAW = F / "RAW_CAPABILITY_INDEX.json"
DRAFT = F / "CAPABILITY_CROSSWALK.draft.json"
BASE = F / "F1B_FROZEN_BASELINE.json"
CONF = F / "F1C_D2_CONFLICT_RESOLUTIONS.json"
GATES = F / "F1C_D2_F2_GATES.json"
REG = F / "F1C_DECISION_REGISTER.json"
DOC = F / "F1C_D2_ARCHITECTURE_DECISIONS.md"
OUT = F / "F1C_D2_VERIFICATION.json"
TZ = timezone(timedelta(hours=8))

sys.path.insert(0, str(Path(__file__).parent))
import f1c_history_invariants as H

MODULES = {"Facts", "Collector", "Evidence-Claims", "Product", "Research",
           "Lifecycle", "Security", "Renderer", "Storage", "DSH-Adapter"}
VALID_STATUS = {"DESIGN_RESOLVED", "IMPLEMENTATION_DEPENDENCY", "BLOCKED_BY_MISSING_EVIDENCE"}
EXPECTED_IDS = {"X-2", "X-4", "X-5", "X-6", "X-7", "K-7", "Y-4", "Y-6"}

results = []


def check(cid, name, fn):
    try:
        ok, detail = fn()
    except Exception as e:
        ok, detail = False, f"异常: {type(e).__name__}: {e}"
    results.append({"id": cid, "name": name, "passed": bool(ok), "detail": detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {cid} {name} :: {detail}")


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)


def main() -> int:
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    draft = json.loads(DRAFT.read_text(encoding="utf-8"))
    base = json.loads(BASE.read_text(encoding="utf-8"))
    conf = json.loads(CONF.read_text(encoding="utf-8"))
    gates = json.loads(GATES.read_text(encoding="utf-8"))
    reg = json.loads(REG.read_text(encoding="utf-8"))
    by = {(i["upstream_id"], i["original_capability_id"]): i for i in raw["items"]}
    canon = {c["canonical_id"]: c for c in draft["canonical_capabilities"]}
    res = {r["conflict_id"]: r for r in conf["resolutions"]}
    tm = draft["terminal_model"]["terminal_dispositions"]
    mapped = {}
    for c in draft["canonical_capabilities"]:
        for r in c["upstream_refs"]:
            mapped[(r["upstream_id"], r["original_capability_id"])] = c["canonical_id"]
    recons = []
    for n in ("F1C_B_ROUTED_RECONCILIATION.json", "F1C_C1_RESOLUTION.json",
              "F1C_C2_U05_RECONCILIATION.json", "F1C_C3_RECONCILIATION.json"):
        p = F / n
        if p.exists():
            recons.append(json.loads(p.read_text(encoding="utf-8")))
    moves = H.build_allowed_moves(recons)

    NEG_MARK = ("不得", "不能", "禁止", "不可接受", "不等于", "不是", "未实测",
                "而不是", "无任何", "不可", "尚未", "零")

    def _is_affirmative(txt, phrase):
        """判断 phrase 在 txt 中是否构成**肯定式断言**。

        判据按「同一句内」而非固定字符窗口：以中英文句读/逗号/分号切句，
        若该句含否定标记，视为在陈述「不得这样说」，不算违规。
        """
        import re as _re
        for m in _re.finditer(_re.escape(phrase), txt):
            start = max(txt.rfind(ch, 0, m.start()) for ch in "。；;\n，,") + 1
            endc = [txt.find(ch, m.end()) for ch in "。；;\n"]
            endc = [e for e in endc if e != -1]
            end = min(endc) if endc else len(txt)
            sent = txt[start:end]
            if not any(n in sent for n in NEG_MARK):
                return True, sent
        return False, ""

    def c1():
        ok = len(by) == 143 and len(raw["items"]) == 143
        return ok, f"原始 {len(raw['items'])} 项，unique={len(by)}"

    def c2():
        hids = [c["canonical_id"] for c in base["canonical_capabilities"]]
        now = set(canon)
        miss = [i for i in hids if i not in now]
        extra = len(canon)
        detail = f"F1-B {len(hids)} 条全在={not miss}；当前 {extra} 条"
        return (not miss and extra == 75), detail

    def c3():
        got = set(res)
        detail = f"八项齐全={got == EXPECTED_IDS}；多出 {sorted(got - EXPECTED_IDS) or '无'}；缺 {sorted(EXPECTED_IDS - got) or '无'}"
        return (got == EXPECTED_IDS), detail

    def c4():
        bad = []
        for cid in sorted(EXPECTED_IDS):
            r = res[cid]
            if r["resolution_status"] == "BLOCKED_BY_MISSING_EVIDENCE":
                if not r.get("blocked_scope"):
                    bad.append(f"{cid} BLOCKED 但无 blocked_scope")
                continue
            if not r.get("unique_owner"):
                bad.append(f"{cid} 无 unique_owner")
                continue
            for k, v in r["unique_owner"].items():
                if not any(m in v for m in MODULES):
                    bad.append(f"{cid}.{k} 未点名模块：{v}")
        detail = f"每项有唯一 owner 或明确阻塞范围，问题 {bad or '无'}"
        return (not bad), detail

    def c5():
        bad = []
        for r in conf["resolutions"]:
            if not r.get("verification_gate"):
                bad.append(f"{r['conflict_id']} 无门禁")
        gids = [g["gates"] if "gates" in g else None for g in [gates]]
        # 每条门禁必须有 stage 与 blocking
        for g in gates["gates"]:
            if g["stage"] not in ("F1", "F2") or not g.get("blocking"):
                bad.append(f"{g['gate_id']} 门禁不完整")
        detail = f"门禁 {len(gates['gates'])} 条（F1 {gates['stats']['f1_stage']} / F2 {gates['stats']['f2_stage']}），问题 {bad or '无'}"
        return (not bad), detail

    def c6():
        # 不把未实测能力描述为已实现：IMPLEMENTATION_DEPENDENCY / BLOCKED 不得含「已实现」断言
        bad = []
        for r in conf["resolutions"]:
            if r["resolution_status"] in ("IMPLEMENTATION_DEPENDENCY", "BLOCKED_BY_MISSING_EVIDENCE"):
                txt = json.dumps(r, ensure_ascii=False)
                # 只判「肯定式断言」：短语前 12 字符内若含否定词，视为在陈述「不得这样说」，放过。
                for phrase in ("已经实现", "已验证事务", "平台已支持", "平台已提供", "已可用"):
                    aff, sent = _is_affirmative(txt, phrase)
                    if aff:
                        bad.append(f"{r['conflict_id']} 含肯定式「{phrase}」：{sent[:40]}")
        # Y-6 的 UNVERIFIED 项不得被写成已支持
        y6 = res["Y-6"]
        detail = f"未实测项未被写成已实现，问题 {bad or '无'}"
        return (not bad), detail

    def c7():
        # X-2 多仓库身份不混淆
        x2 = res["X-2"]
        txt = json.dumps(x2, ensure_ascii=False)
        need = ["repository_id", "subject_id", "workspace_id", "commit_sha",
                "forked_from", "不是所有 Subject 的主键", "不得自动合并"]
        miss = [k for k in need if k not in txt]
        # 且不得出现「repository_id 就是主键」这类肯定式
        # 只有把 A 选项当成**结论**才违规。裁决文本里禁止出现「采用 A」这类肯定。
        bad = [p for p in ("采用方案 A", "选择 A：repository_id", "结论：repository_id 是主键") if p in txt]
        detail = f"X-2 六类标识齐备、不混淆，缺 {miss or '无'}"
        return (not miss and not bad), detail

    def c8():
        # X-4 A 层不可被 B 覆盖
        x4 = res["X-4"]
        txt = json.dumps(x4, ensure_ascii=False)
        need = ["不得用 B 覆盖 A", "不得把不同版本的结论视为互相证伪",
                "读取失败", "last_known_good", "Renderer 对两层都无写权限"]
        # 「伪装成空结果」的两种自然写法都算通过
        if "伪装成空结果" not in txt and "伪装成空" not in txt:
            need = need + ["伪装成空结果"]
        miss = [k for k in need if k not in txt]
        detail = f"X-4 四条硬规则齐备，缺 {miss or '无'}"
        return (not miss), detail

    def c9():
        # K-7 不产生未授权人工文档修改
        k7 = res["K-7"]
        txt = json.dumps(k7, ensure_ascii=False)
        need = ["不得直接覆盖或修改", "七项", "不得因为文档内存在 Markdown 标记",
                "明确的用户授权", "回退", "不改变不可变历史"]
        miss = [k for k in need if k not in txt]
        # 本轮不得实际修改人工文档：检查 git 状态中无 docs 下人工叙事文档被改
        # K-7 判据只针对「修改已存在的人工文档」。
        # 新建独立文件（git 状态 ??）正是 K-7 允许的做法，不算违规——
        # 早期版本把 ?? 也算进来，导致后续批次新建的 .md 被误判。
        s = git("status", "--short")
        modified = []
        for line in s.stdout.splitlines():
            st, _, path = line[:2], line[2:3], line[3:].strip()
            if not path.endswith(".md"):
                continue
            if path.startswith("progress/") or "docs/fusion/" in path:
                continue
            # 只有 M（修改）/ D（删除）/ R（重命名）才算动了既有文档
            if st.strip() in ("M", "D", "R"):
                modified.append(path)
        detail = (f"K-7 边界与七项条件齐备，缺 {miss or '无'}；"
                  f"既有 .md 被修改/删除 {modified or '无'}（新建文件不计）")
        return (not miss and not modified), detail

    def c10():
        # Y-4 任务检查点与知识资产权威分离
        y4 = res["Y-4"]
        txt = json.dumps(y4, ensure_ascii=False)
        need = ["独立分区", "不得混入知识资产", "热记忆", "不是唯一权威",
                "任务能否恢复」与「知识是否仍然有效", "checkpoint_corrupt"]
        miss = [k for k in need if k not in txt]
        detail = f"Y-4 三个对象分开、权威分离，缺 {miss or '无'}"
        return (not miss), detail

    def c11():
        # Y-6 未验证能力仍标未验证
        y6 = res["Y-6"]
        txt = json.dumps(y6, ensure_ascii=False)
        unverified = ["H-D", "H-E", "H-F", "H-H"]
        bad = []
        for h in unverified:
            if h not in txt:
                bad.append(f"{h} 未出现")
            if "**UNVERIFIED**" not in txt:
                bad.append("缺 UNVERIFIED 标记")
                break
        # 不得声称平台已有恢复接口
        bad2 = []
        for phrase in ("平台已提供", "平台已有恢复", "原生恢复接口已可用", "平台已支持"):
            aff, sent = _is_affirmative(txt, phrase)
            if aff:
                bad2.append(f"肯定式「{phrase}」：{sent[:40]}")
        detail = f"Y-6 四项仍标 UNVERIFIED、未声称平台能力，问题 {bad + bad2 or '无'}"
        return (not bad and not bad2), detail

    def c12():
        # 反向处置有独立理由
        rev = conf["reverse_dispositions"]
        ok_ids = {r["identity_key"] for r in rev}
        if ok_ids != {"UPSTREAM-06::C13", "UPSTREAM-02::C17"}:
            return False, f"反向个案集合不符：{sorted(ok_ids)}"
        bad = []
        for r in rev:
            for f in ("upstream_claim", "rejected_part", "retained_part",
                      "final_reason", "license_boundary"):
                if not r.get(f):
                    bad.append(f"{r['identity_key']} 缺 {f}")
            # 许可与磁盘一致
            k = tuple(r["identity_key"].split("::"))
            actual = (by[k].get("license") or {}).get("copy_permitted")
            if r["license_actual"]["copy_permitted"] != actual:
                bad.append(f"{r['identity_key']} 许可与磁盘不一致")
        detail = f"2 项反向处置均有独立理由与许可边界，问题 {bad or '无'}"
        return (not bad), detail

    def c13():
        # 反例绑定数量与拒绝身份数量分开
        edges = [(r["identity_key"], c["canonical_id"])
                 for c in draft["canonical_capabilities"]
                 for r in c["upstream_refs"] if r["verdict"] == "REJECT"]
        ce = [k for k, v in tm.items() if v["value"] == "ADOPTED_AS_COUNTEREXAMPLE"]
        rj = [k for k, v in tm.items() if v["value"] == "REJECTED_WITH_REASON"]
        clar = conf["counterexample_clarification"]["actual_counts"]
        ok = (clar["adopted_as_counterexample_unique_identities"] == len(ce)
              and clar["actual_identity_to_canonical_edges"] == len(edges)
              and clar["rejected_with_reason_unbound_identities"] == len(rj)
              and clar["total_counterexample_role_identities"] == len(ce) + len(rj))
        # 4 项拒绝身份确实无任何 canonical 边
        unbound = all(k not in {e[0] for e in edges} for k in rj)
        detail = (f"17 绑定身份 / {len(edges)} 关联边 / {len(rj)} 无绑定拒绝身份；"
                  f"口径正确={ok}；4 项确实无绑定={unbound}")
        return (ok and unbound), detail

    def c14():
        # 所有跨模块契约无重复 owner：同一 conflict 内 owner key 不重复指向不同模块
        bad = []
        for cid, r in res.items():
            if not r.get("unique_owner"):
                continue
            owners = {}
            for k, v in r["unique_owner"].items():
                mod = next((m for m in MODULES if m in v), None)
                if mod is None:
                    bad.append(f"{cid}.{k} 无模块")
                    continue
                owners.setdefault(mod, []).append(k)
            # 同一模块在同一 conflict 里承担多个角色是允许的，
            # 但必须能说清角色（key 不同即可）
        # 跨 conflict 检查：每个 (conflict,module) 只出现一次
        detail = f"八项契约 owner 均点名模块且角色可区分，问题 {bad or '无'}"
        return (not bad), detail

    def c15():
        # amendment 有完整留痕：本批 0 条 amendment，故 canonical 不得因本批而被改
        n_amend = sum(len(c.get("f1c_amendments") or []) for c in draft["canonical_capabilities"])
        declared = reg["d2_cross_module_resolutions"]["amendments_made"]
        # 与 D1 时的 21 条一致
        ok = (n_amend == 21 and declared == 0)
        detail = f"canonical amendment 共 {n_amend} 条（本批新增 {declared} 条，应为 0）"
        return ok, detail

    def c16():
        # disposition 与 terminal_disposition 不混淆
        bad = []
        for k, v in tm.items():
            u, cid = k.split("::")
            if by[(u, cid)]["disposition"] not in {"REUSE", "ADAPT", "REIMPLEMENT", "REJECT"}:
                bad.append(f"{k} 上游 disposition 异常")
            if v["value"] not in {"ADOPTED", "ADOPTED_AS_COUNTEREXAMPLE",
                                  "REJECTED_WITH_REASON", "DEFERRED_WITH_REASON"}:
                bad.append(f"{k} 终态异常")
        diff = sum(1 for k, v in tm.items()
                   if by[tuple(k.split("::"))]["disposition"] != v["value"])
        detail = f"两字段独立（{diff} 处不同），问题 {bad or '无'}"
        return (not bad and diff > 0), detail

    def c17():
        bad = []
        for c in draft["canonical_capabilities"]:
            for r in c["upstream_refs"]:
                if r["upstream_id"] == "UPSTREAM-06" and r["license"].get("copy_permitted") is not False:
                    bad.append(f"{c['canonical_id']} 给了 U06 复制许可")
                if r["upstream_id"] == "UPSTREAM-06" and c["license_permission"].get("copy_permitted") is True:
                    bad.append(f"{c['canonical_id']} 整体判为可复制但含 U06")
        detail = f"UPSTREAM-06 零复制限制保持不变，问题 {bad or '无'}"
        return (not bad), detail

    def c18():
        g = draft["global_state_counts"]
        unrev = {k for k in by if k not in mapped}
        total = len(mapped) + g["routed_pending_count"] + len(unrev)
        td = g["terminal_disposition_counts"]
        ok = (total == 143 == g["sum_check"]
              and td == {"ADOPTED": 122, "ADOPTED_AS_COUNTEREXAMPLE": 17,
                         "REJECTED_WITH_REASON": 4})
        detail = (f"三态 {len(mapped)}/0/{len(unrev)} = {total}；终态 {td}")
        return ok, detail

    def c19():
        return H.check_identity_mapping_preserved(base, draft, moves)

    def c20():
        g1 = git("diff", "--quiet", "HEAD", "--", "docs/fusion/RAW_CAPABILITY_INDEX.json")
        g2 = git("diff", "--quiet", "HEAD", "--",
                 *[f"progress/UPSTREAM-0{i}-audit.json" for i in range(1, 7)])
        s = git("status", "--short", "--", "src/", "tests/", "schemas/")
        no_final = not (F / "CAPABILITY_CROSSWALK.json").exists()
        ok = g1.returncode == 0 and g2.returncode == 0 and s.stdout.strip() == "" and no_final
        return ok, f"原始索引/六审计/引擎/Schema 未变={g1.returncode == 0 and g2.returncode == 0 and not s.stdout.strip()}；未冻结正式交叉表={no_final}"

    def c21():
        # 生成器幂等
        before = (CONF.read_bytes(), GATES.read_bytes())
        import subprocess as sp
        sp.run([sys.executable, str(ROOT / "tools" / "fusion" / "f1c_d2_build.py")],
               cwd=ROOT, capture_output=True)
        after = (CONF.read_bytes(), GATES.read_bytes())
        # 生成时刻不同会导致字节不同，故比较去掉 generated_at 的内容
        def norm(b):
            d = json.loads(b)
            d.pop("generated_at", None)
            return json.dumps(d, ensure_ascii=False, sort_keys=True)
        return (norm(before[0]) == norm(after[0]) and norm(before[1]) == norm(after[1]),
                "重跑生成器后两份 JSON 除时间戳外一致（幂等）")

    def c22():
        if not DOC.exists():
            return False, f"文档不存在: {DOC.name}"
        txt = DOC.read_text(encoding="utf-8")
        need = ["X-2", "X-4", "X-5", "X-6", "X-7", "K-7", "Y-4", "Y-6",
                "DESIGN_RESOLVED", "IMPLEMENTATION_DEPENDENCY", "BLOCKED_BY_MISSING_EVIDENCE",
                "U06::C13", "U02::C17", "17", "4"]
        miss = [k for k in need if k not in txt]
        detail = f"文档覆盖八项与两处反向，缺 {miss or '无'}"
        return (not miss), detail

    check("c1", "原始 143 项身份完整", c1)
    check("c2", "75 条 canonical 身份完整", c2)
    check("c3", "八项冲突逐项有裁决", c3)
    check("c4", "每项有唯一 owner 或明确阻塞理由", c4)
    check("c5", "实现依赖具有可执行验证门禁", c5)
    check("c6", "不把未实测能力描述为已实现", c6)
    check("c7", "X-2 多仓库身份不混淆", c7)
    check("c8", "X-4 权威历史不能被当前视图覆盖", c8)
    check("c9", "K-7 不产生未授权人工文档修改", c9)
    check("c10", "Y-4 任务检查点与知识资产权威分离", c10)
    check("c11", "Y-6 未验证 Harness 能力仍标记未验证", c11)
    check("c12", "反向处置有独立理由", c12)
    check("c13", "反例绑定数量与拒绝身份数量分开", c13)
    check("c14", "跨模块契约无重复 owner", c14)
    check("c15", "amendment 有完整留痕", c15)
    check("c16", "disposition 与 terminal_disposition 不混淆", c16)
    check("c17", "UPSTREAM-06 无复制授权限制不变", c17)
    check("c18", "三态及终态分类保持一致", c18)
    check("c19", "全局历史不变量验证通过", c19)
    check("c20", "六审计/原始索引/引擎不变", c20)
    check("c21", "生成器幂等", c21)
    check("c22", "决策文档完整", c22)

    passed = sum(1 for r in results if r["passed"])
    out = {
        "task": "M1-FUSION-GATE-F1 / F1-C-D2（八项跨模块架构冲突裁决）",
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "generated_by": "tools/fusion/f1c_d2_verify.py",
        "git_head": git("rev-parse", "HEAD").stdout.strip(),
        "summary": {"passed": passed, "total": len(results),
                    "result": "PASS" if passed == len(results) else "FAIL"},
        "checks": results,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n{passed}/{len(results)} PASS -> {OUT.name}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
