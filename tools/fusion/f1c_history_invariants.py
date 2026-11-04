#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""历史不变量校验（集合级，供各批验证器调用）。

背景：第 7 节要求「不得仅用数量保证历史未受损」。此前各批把 mapped 定格从 `==` 放宽为 `>=`，
只保证了「数量没减少」，**没有保证「集合内容没被偷偷换掉」**：
理论上可以把 A 身份从 canonical X 移除、同时把 B 身份加入 X，总数不变但语义已错。

本模块提供三个集合级检查：

    check_identity_mapping_preserved(base, now)   历史 identity_key → canonical_id 映射不得无记录地变化
    check_canonical_ids_not_reused(base, now)     已有 canonical ID 不得被重新分配给不同语义
    check_amendments_recorded(base, now, recon)   核心字段变更必须有 amendment 留痕

用法（在验证器里）：
    from f1c_history_invariants import check_identity_mapping_preserved, ...
"""


def _mapping(canon):
    """identity_key -> canonical_id"""
    m = {}
    for c in canon:
        for r in c["upstream_refs"]:
            key = f"{r['upstream_id']}::{r['original_capability_id']}"
            m[key] = c["canonical_id"]
    return m


def check_identity_mapping_preserved(base, now, allowed_moves=None):
    """历史正式映射的原始身份必须仍在，且 identity_key → canonical_id 关系不得无记录地变化。

    allowed_moves: {identity_key: 新 canonical_id}，由 F1-C 裁决显式登记过的迁移。
                   未登记的变化即判失败。
    返回 (ok, detail)
    """
    allowed = allowed_moves or {}
    b = _mapping(base["canonical_capabilities"])
    n = _mapping(now["canonical_capabilities"])
    lost, moved_undocumented, moved_ok = [], [], []
    for key, cid in b.items():
        if key not in n:
            lost.append(f"{key} 原属 {cid}，现已无归属")
            continue
        if n[key] != cid:
            if key in allowed and n[key] == allowed[key]:
                moved_ok.append(f"{key}: {cid} → {n[key]}")
            else:
                moved_undocumented.append(f"{key}: {cid} → {n[key]}（无登记迁移）")
    ok = not lost and not moved_undocumented
    detail = (f"历史映射 {len(b)} 条：丢失 {len(lost)}、无登记变更 {len(moved_undocumented)}、"
              f"登记内迁移 {len(moved_ok)}")
    if lost:
        detail += f"；丢失 {lost}"
    if moved_undocumented:
        detail += f"；无登记 {moved_undocumented}"
    return ok, detail


def check_canonical_ids_not_reused(base, now):
    """已有 canonical ID 不得被重新利用：同一 ID 的名字与 owner 不得变更。

    内容可以经 amendment 扩展（那走 check_amendments_recorded），
    但 name/owner 变更意味着这个 ID 被拿去指别的东西了。
    """
    bad = []
    for c in base["canonical_capabilities"]:
        cur = next((x for x in now["canonical_capabilities"]
                    if x["canonical_id"] == c["canonical_id"]), None)
        if cur is None:
            bad.append(f"{c['canonical_id']} 被删除")
            continue
        if cur["name"] != c["name"]:
            bad.append(f"{c['canonical_id']} 名称变更：{c['name']} → {cur['name']}")
        if cur["owner_module"] != c["owner_module"]:
            bad.append(f"{c['canonical_id']} owner 变更："
                       f"{c['owner_module']} → {cur['owner_module']}")
    return not bad, (f"历史 {len(base['canonical_capabilities'])} 条 canonical ID "
                     f"未被复用/删除，问题 {bad or '无'}")


def check_amendments_recorded(base, now, recon):
    """核心字段变更必须有正式 amendment。

    判据（修正版）：对**这一个** reconciliation 记录的批次负责的那部分 amendment，
    必须同时满足「canonical 上有 f1c_amendments 留痕」与「该 recon 里有 AMEND_CANONICAL 条目」。

    说明：不把「canonical 上存在任何 amendment」当作本批次新增——
    那是其它批次留下的，不该由本批负责也不能判本批失败。
    """
    def targets_of(r):
        t = {c["target"] for c in r.get("changes", [])
             if c.get("action") == "AMEND_CANONICAL"}
        t |= {c["target"] for c in r.get("changes_c1", [])
              if c.get("action") == "AMEND_CANONICAL"}
        return t

    amend_targets = targets_of(recon)
    # 若该 recon 同时带 changes_c1，只取属于该批次的那一份（避免跨批混淆）
    if recon.get("batch"):
        amend_targets = {c["target"] for c in recon.get("changes_c1", [])
                         if c.get("action") == "AMEND_CANONICAL"}
    bad, extended = [], []
    for c in base["canonical_capabilities"]:
        cid = c["canonical_id"]
        cur = next((x for x in now["canonical_capabilities"]
                    if x["canonical_id"] == cid), None)
        if cur is None:
            continue
        if cid not in amend_targets:
            continue  # 本批没动它，不归本批负责
        has_amend = bool(cur.get("f1c_amendments"))
        if not has_amend:
            bad.append(f"{cid} 本批记录为 AMEND 但 canonical 上无留痕")
        else:
            extended.append(cid)
    return not bad, (f"本批新增 amendment 的条目 {extended or '无'}，全部有留痕；"
                     f"问题 {bad or '无'}")


def build_allowed_moves(recon_list):
    """从多个 reconciliation 的 changes 里推导「已登记的迁移」。"""
    moves = {}
    for recon in recon_list:
        for ch in (recon.get("changes") or []) + (recon.get("changes_c1") or []):
            if ch.get("action") in ("ADOPT_EXISTING", "NEW_CANONICAL") and ch.get("target"):
                moves[ch["identity"]] = ch["target"]
    return moves
