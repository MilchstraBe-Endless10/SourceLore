#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-B / Facts 模块 12 条验收检查。每条独立跑出真实退出码。"""
import json, subprocess, sys, re, hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
F = ROOT / "docs" / "fusion"
RAW = F / "RAW_CAPABILITY_INDEX.json"
DRAFT = F / "CAPABILITY_CROSSWALK.draft.json"
PROG = F / "CROSSWALK_PROGRESS.json"
DOC = F / "F1B_FACTS_DECISIONS.md"

results = []
def check(no, title, fn):
    try:
        ok, detail = fn()
    except Exception as e:
        ok, detail = False, f"异常: {type(e).__name__}: {e}"
    results.append((no, title, ok, detail))
    print(("PASS" if ok else "FAIL"), f"[{no}]", title)
    print("     ", detail)

raw = json.loads(RAW.read_text(encoding="utf-8"))
draft = json.loads(DRAFT.read_text(encoding="utf-8"))
prog = json.loads(PROG.read_text(encoding="utf-8"))
items = raw["items"]
canon = draft["canonical_capabilities"]
redir = draft["cross_module_redirections"]

# 1
def c1():
    n = len(items)
    keys = [i["identity_key"] for i in items]
    ok = n == 143 and len(set(keys)) == 143 and raw["counts"]["total_raw_capabilities"] == 143
    return ok, f"项数={n}, 唯一身份键={len(set(keys))}, counts.total={raw['counts']['total_raw_capabilities']}"
# Facts 批次自己的 canonical 编号范围（后续模块批次的条目不在本验证器职责内）
FACTS_IDS = {f"SL-CAP-{n:04d}" for n in range(1, 11)}

check(1, "原始索引仍为 143 且身份键唯一", c1)

# 2
def c2():
    ids = [c["canonical_id"] for c in canon]
    ok = len(set(ids)) == len(ids) and all(re.fullmatch(r"SL-CAP-\d{4}", i) for i in ids)
    return ok, f"canonical 数={len(ids)}, 唯一={len(set(ids))}, 形态={all(re.fullmatch(r'SL-CAP-.{4}',i) for i in ids)}"
check(2, "Facts canonical ID 唯一且形态合规", c2)

# 3
def c3():
    seen = {}
    bad = []
    for c in canon:
        for r in c["upstream_refs"]:
            k = r["identity_key"]
            if k in seen:
                bad.append(f"{k} 属 {seen[k]} 又属 {c['canonical_id']}")
            seen[k] = c["canonical_id"]
    return not bad, f"已映射原始身份={len(seen)}，重复归属={bad or '无'}"
check(3, "每项已映射原始能力只映射到一个 canonical ID", c3)

# 4
def c4():
    # 本验证器只对 Facts 批次自己的能力负责；其余模块的 owner 由各自批次的验证器判定
    owners = {c["canonical_id"]: c["owner_module"] for c in canon if c["canonical_id"] in FACTS_IDS}
    bad = [k for k, v in owners.items() if v != "Facts"]
    return not bad, f"owner_module 全为 Facts={not bad}，异常={bad or '无'}，共 {len(owners)} 条"
check(4, "每个 canonical 能力恰有一个主 owner", c4)

# 5
def c5():
    bad = []
    for c in canon:
        if "disposition" not in c or "license_permission" not in c:
            bad.append(f"{c['canonical_id']} 缺字段")
            continue
        per = c["license_permission"]["per_upstream"]
        if len(per) != len(c["upstream_refs"]):
            bad.append(f"{c['canonical_id']} 许可未逐源记录")
        for p in per:
            if p["upstream_id"] == "UPSTREAM-06" and p.get("copy_permitted") is not False:
                bad.append(f"{c['canonical_id']} 给了 U06 复制许可")
    return not bad, f"逐源许可条目={sum(len(c['license_permission']['per_upstream']) for c in canon)}，问题={bad or '无'}"
check(5, "最终处置与许可权限独立且逐源记录", c5)

# 6
def c6():
    known = {i["identity_key"] for i in items}
    refs = [r["identity_key"] for c in canon for r in c["upstream_refs"]]
    refs += [r["identity_key"] for r in redir]
    missing = [k for k in refs if k not in known]
    return not missing, f"引用总数={len(refs)}，在原始索引中不可定位={missing or '无'}"
check(6, "全部映射引用可在原始索引中定位", c6)

# 7
def c7():
    h = hashlib.sha256(RAW.read_bytes()).hexdigest()
    ok = h == draft["source_index_sha256"] and h == prog.get("source_index_sha256", h)
    r = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", "docs/fusion/RAW_CAPABILITY_INDEX.json"],
                       cwd=ROOT, capture_output=True)
    return ok and r.returncode == 0, f"sha256={h[:16]}… 与草稿一致={h==draft['source_index_sha256']}，git diff 退出码={r.returncode}"
check(7, "原始索引未被意外修改", c7)

# 8
def c8():
    r = subprocess.run(["git", "diff", "--quiet", "HEAD", "--"] +
                       [f"progress/UPSTREAM-0{i}-audit.json" for i in range(1, 7)],
                       cwd=ROOT, capture_output=True)
    return r.returncode == 0, f"六份审计文件 git diff 退出码={r.returncode}"
check(8, "六份上游审计文件未修改", c8)

# 9
def c9():
    mapped = {r["identity_key"] for c in canon for r in c["upstream_refs"]}
    redirected = {r["identity_key"] for r in redir}
    pending = [i for i in items if i["identity_key"] not in mapped | redirected]
    still_unmapped_in_index = all(i["crosswalk"]["mapping_status"] == "UNMAPPED" for i in pending)
    n_pending = len(pending)
    ok = n_pending == 143 - len(mapped) - len(redirected) and still_unmapped_in_index
    return ok, f"未处理={n_pending}，其中索引内仍标 UNMAPPED={still_unmapped_in_index}"
check(9, "未映射能力仍为待处理（不视为已裁决）", c9)

# 10
def c10():
    # 作用域收窄：只判定 Facts 自己的条目与其分流记录不越界。C03 在后续批次
    # 被 Evidence-Claims 正式承接属于正常推进，不能因此判 Facts 越界；判据改成
    # 「Facts 的 canonical 不得占用这两项」，而不是「全局无人引用它们」。
    allowed = {"Collector", "Facts", "Evidence-Claims", "Product", "Research", "Lifecycle",
               "Security", "Renderer", "Storage", "DSH-Adapter"}
    bad = [c["canonical_id"] for c in canon
           if c["canonical_id"] in FACTS_IDS and c["owner_module"] != "Facts"]
    bad += [r["identity_key"] for r in redir if r["owner_module"] not in allowed or r["owner_module"] == "Facts"]
    reserved = {("UPSTREAM-01", "C03"), ("UPSTREAM-01", "C10")}
    facts_refs = {(r["upstream_id"], r["original_capability_id"])
                  for c in canon if c["canonical_id"] in FACTS_IDS for r in c["upstream_refs"]}
    wrong = [k for k in reserved if k in facts_refs]
    return not bad and not wrong, f"越界={bad or '无'}；C03/C10 未被 Facts 占用={not wrong}；跨模块去向={len(redir)} 项"
check(10, "Facts 未与 Collector/Evidence/Renderer 混同", c10)

# 11
def c11():
    if not DOC.exists():
        return False, f"决策文档不存在: {DOC.name}"
    txt = DOC.read_text(encoding="utf-8")
    missing = [c["canonical_id"] for c in canon
               if c["canonical_id"] in FACTS_IDS and c["canonical_id"] not in txt]
    # 统计契约修订后：batch_summary 只是「最后完成的批次」，对本文档（Facts）必须
    # 取 batches[] 里 module==Facts 的条目；raw_mapped_to_facts / raw_remaining_unmapped
    # 已废除。全局口径从 global_state_counts 取（累计视图，随批次推进）。
    bs = next(b for b in draft["batches"] if b["module"] == "Facts")
    nums = [bs["raw_mapped_to_this_module"], len(bs["canonical_ids"]),
            bs["raw_redirected_to_other_modules"]]
    g = draft["global_state_counts"]
    nums_ok = all(str(n) in txt for n in nums)
    # 累计口径判定改为「文档内自洽 + 原始总数正确」，不再要求等于当前全局值：
    # Facts 决策文档记录的是该批次验收当时的快照，后续批次推进会让二者必然不等，
    # 拿当前值去卡历史文档等于要求篡改历史，且每推进一批就要改一次旧文档。
    def snap(label):
        m = re.search(r"累计 " + label + r"[^|\n]*\|\s*(\d+)\s*\|", txt)
        return int(m.group(1)) if m else None
    sm, sr, su = snap("MAPPED"), snap("ROUTED"), snap("UNREVIEWED")
    total_ok = str(g["raw_total"]) in txt
    snap_ok = None not in (sm, sr, su) and (sm + sr + su == g["raw_total"])
    return (not missing and nums_ok and total_ok and snap_ok,
            f"文档缺失的 ID={missing or '无'}；批次数字 {nums} 出现={nums_ok}；"
            f"累计快照 MAPPED/ROUTED/UNREVIEWED={sm}/{sr}/{su} 自洽={snap_ok}；raw_total={g['raw_total']} 出现={total_ok}")
check(11, "JSON 与决策文档一致", c11)

# 12
def c12():
    r = subprocess.run(["git", "status", "--short", "--", "src/", "tests/", "schemas/"],
                       cwd=ROOT, capture_output=True, text=True)
    changed = [l for l in r.stdout.strip().splitlines() if l.strip()]
    return not changed, f"src/tests/schemas 变更={changed or '无'}"
check(12, "未改动生产分析引擎/schema/测试目录", c12)

passed = sum(1 for r in results if r[2])
total = len(results)
print(f"\n汇总: {passed}/{total} PASS")
json.dump({"passed": passed, "total": total,
           "checks": [{"no": n, "title": t, "ok": o, "detail": d} for n, t, o, d in results]},
          open(F / "F1B_FACTS_VERIFICATION.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
sys.exit(0 if passed == total else 1)
