#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""恢复协调器：把 checkpoint 状态翻译成"能不能继续跑"。

契约：SL-CAP-0071（任务恢复）与 Y-4 裁决（检查点是执行状态，不是知识）。
**核心立场：任务可以恢复 ≠ 模型自动记得任务。** 恢复只依据持久化记录。

本模块不做 I/O 之外的事：不调模型、不碰知识资产、不推测缺失状态。
"""

import sys, sqlite3
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import execution_result as ER
from checkpoint_store import CheckpointStore

# 可自动续跑的判定理由
RESUME_CLEAN = "CLEAN"
# 必须人工介入 / 重新观测的理由
NEEDS_RECONCILE = "UNKNOWN_NEEDS_RECONCILE"
BLOCKED_SIDE_EFFECT = "TIMEOUT_SIDE_EFFECT_RISK"
BLOCKED_CORRUPT = "CHECKPOINT_CORRUPT"

AUTO_RESUMABLE_REASONS = frozenset({RESUME_CLEAN})


def open_store(db_path: str, *, create: bool = False) -> tuple[Optional[CheckpointStore], dict]:
    """安全打开：库损坏时返回结构化错误，不抛出。

    这样调用方（BotHarness / CLI / 恢复流程）拿到的永远是可判定的结果，
    而不是一个需要 try/except 猜类型的异常。
    """
    try:
        return CheckpointStore(db_path, create=create), {}
    except (RuntimeError, sqlite3.DatabaseError) as e:
        return None, {"ok": False, "error": "CHECKPOINT_CORRUPT",
                      "detail": f"库不可用: {str(e)[:200]}"}
    except FileNotFoundError as e:
        return None, {"ok": False, "error": "NOT_FOUND", "detail": str(e)}
    except PermissionError as e:
        return None, {"ok": False, "error": "PERMISSION_DENIED", "detail": str(e)}


def plan_resume(store: CheckpointStore, *, task_id: str, run_id: str) -> dict:
    """给出恢复计划。

    返回：
      {
        "ok": bool,               # 查询本身是否成功（区别于"能否续跑"）
        "auto_resume": bool,      # 是否允许**无人值守**自动续跑
        "reason": str,
        "from_stage": str | None,
        "expected_version": int | None,
        "requires_human": bool,
        "detail": str,
      }
    """
    r = store.resume_checkpoint(task_id=task_id, run_id=run_id)

    if not r["ok"]:
        err = r.get("error")
        if err == "CHECKPOINT_CORRUPT":
            return {"ok": False, "auto_resume": False, "reason": BLOCKED_CORRUPT,
                    "from_stage": None, "expected_version": None,
                    "requires_human": True,
                    "detail": "库损坏；不当作空库、不自动重建，需人工恢复"}
        # NOT_FOUND：不得凭空造一条
        return {"ok": False, "auto_resume": False, "reason": "NOT_FOUND",
                "from_stage": None, "expected_version": None,
                "requires_human": True,
                "detail": "无此 checkpoint；不得从热记忆或对话历史推断"}

    if not r["resumable"]:
        return {"ok": True, "auto_resume": False, "reason": r["reason"],
                "from_stage": r["checkpoint"]["stage"],
                "expected_version": r["checkpoint"]["checkpoint_version"],
                "requires_human": True,
                "detail": r.get("detail", "")}

    return {"ok": True, "auto_resume": True, "reason": RESUME_CLEAN,
            "from_stage": r["checkpoint"]["stage"],
            "expected_version": r["checkpoint"]["checkpoint_version"],
            "requires_human": False,
            "detail": f"从 {r['checkpoint']['stage']} 续跑，版本 {r['checkpoint']['checkpoint_version']}"}


def advance_stage(store: CheckpointStore, *, task_id: str, run_id: str,
                  expected_version: int, next_stage: str) -> dict:
    """按 CAS 推进阶段。失败返回 CONFLICT/NOT_FOUND，**不重试、不覆盖**。"""
    return store.update_checkpoint_if_version(
        task_id=task_id, run_id=run_id,
        expected_version=expected_version, stage=next_stage)


def finish(store: CheckpointStore, *, task_id: str, run_id: str,
           result: ER.ExecutionResult, result_payload: Optional[dict] = None) -> dict:
    """把执行结果写入 checkpoint。UNKNOWN 不会被写成 SUCCESS/FAILED。"""
    return store.record_result(
        task_id=task_id, run_id=run_id,
        state=result.state, exit_code=result.exit_code,
        side_effect_possible=result.side_effect_possible,
        detail=result.detail, result_payload=result_payload)
