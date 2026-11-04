#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""共享判定：正式交叉表是否处于「合法的未冻结」或「已由 F1-D 正式冻结」状态。

历史批次验证器（F1-B / F1-C-*）的断言是「本批时点不得提前冻结」。
F1-D 是**获授权**的冻结批次，因此它之后「已冻结」也是合法状态。
本模块把这条判定集中一处，避免各验证器各写一份、口径漂移。
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
F = ROOT / "docs" / "fusion"

VALID_FREEZE_DECISIONS = ("FROZEN_INTERNAL_RESTRICTED", "FROZEN_RELEASE_READY")


def freeze_state():
    """返回 (ok, detail)。

    ok=True 的两种情形：
      1) 正式文件不存在 → 尚未冻结（历史批次的正常时点）
      2) 正式文件存在且 manifest 的 freeze_decision 合法 → 已由 F1-D 正式冻结
    ok=False：存在正式文件但没有合法 manifest → 属于「无记录的冻结」，必须报错
    """
    cw = F / "CAPABILITY_CROSSWALK.json"
    man = F / "F1D_FREEZE_MANIFEST.json"
    if not cw.exists():
        return True, "本批时点未冻结（符合分批纪律）"
    if not man.exists():
        return False, "正式交叉表存在但无 F1D_FREEZE_MANIFEST.json（无记录的冻结）"
    m = json.loads(man.read_text(encoding="utf-8"))
    fd = m.get("freeze_decision")
    if fd not in VALID_FREEZE_DECISIONS:
        return False, f"freeze_decision={fd!r} 非法"
    return True, (f"已由 F1-D 正式冻结（{fd}），"
                  f"crosswalk sha256={str(m.get('crosswalk_sha256',''))[:16]}…")
