#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跨库协调：知识资产库 ↔ checkpoint 库。

**这是本轮最高风险处，先说清立场：**

  两个库是**独立的物理文件、独立的事务边界**。
  它们之间**没有**全局 ACID 事务。实测过的 ATTACH 跨 WAL 提交
  不构成可依赖的保证，所以本模块不用它。

  能依赖的只有一个事实：**知识库里的 operation_log 是幂等锚点**。
  资产事务一旦提交，operation_id 就落库了。checkpoint 那边落后多少，
  都可以靠"查 operation_log 有没有这条"来对账。

**三种状态必须能区分：**
  - checkpoint 落后、operations 已提交  → 对账补齐（RECONCILED）
  - checkpoint 落后、operations 未提交   → 可安全重试（RETRY_SAFE）
  - 无法判定（库读不出来 / 两边矛盾）    → UNKNOWN，交人工，绝不自动重做
"""

import sys, sqlite3, time
from pathlib import Path
from typing import Optional

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent / "storage")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import execution_result as ER
from knowledge_store import KnowledgeStore

# checkpoint 库的安全打开（结构错误 → 结构化返回，不抛出）
def open_store(db_path, *, create: bool = False):
    """安全打开 checkpoint 库。损坏返回 (None, err)，供对账判定 NEEDS_HUMAN。"""
    from checkpoint_store import CheckpointStore
    try:
        return CheckpointStore(db_path, create=create), {}
    except (RuntimeError, sqlite3.DatabaseError) as e:
        return None, {"ok": False, "error": "CHECKPOINT_CORRUPT",
                      "detail": f"库不可用: {str(e)[:200]}"}
    except FileNotFoundError as e:
        return None, {"ok": False, "error": "NOT_FOUND", "detail": str(e)}
    except PermissionError as e:
        return None, {"ok": False, "error": "PERMISSION_DENIED", "detail": str(e)}

# 对账判定
RECONCILED = "RECONCILED"           # 资产已提交，checkpoint 需补齐
RETRY_SAFE = "RETRY_SAFE"           # 资产确认未提交，可幂等重试
NEEDS_HUMAN = "NEEDS_HUMAN"         # 无法判定
NOTHING_TO_DO = "NOTHING_TO_DO"     # checkpoint 已是最新


def reconcile(store: KnowledgeStore, checkpoint_store, *,
              task_id: str, run_id: str, operation_id: str) -> dict:
    """对账：以**知识库的 operation_log 为唯一事实源**。

    绝不从模型上下文推断，绝不用"我记得好像提交了"。
    """
    # 1) 先问知识库：这条 operation 提交了吗？
    try:
        op = store.conn.execute(
            "SELECT * FROM operation_log WHERE operation_id=?", (operation_id,)).fetchone()
    except Exception as e:
        return {"state": NEEDS_HUMAN, "reason": "KNOWLEDGE_DB_UNREADABLE",
                "detail": f"{type(e).__name__}: {str(e)[:150]}",
                "auto_retry": False}

    # 2) 读 checkpoint 现状
    cp = checkpoint_store.read_checkpoint(task_id=task_id, run_id=run_id)
    if not cp.get("ok") and cp.get("error") == "CHECKPOINT_CORRUPT":
        return {"state": NEEDS_HUMAN, "reason": "CHECKPOINT_CORRUPT",
                "detail": cp.get("detail", ""), "auto_retry": False}
    cp_missing = (not cp.get("ok"))

    # 3) 分支判定
    if op is None:
        # 资产侧没有提交记录
        if cp_missing:
            return {"state": RETRY_SAFE, "reason": "NO_OPERATION_NO_CHECKPOINT",
                    "detail": "两侧均无记录，可按幂等规则重试", "auto_retry": True}
        return {"state": RETRY_SAFE, "reason": "NO_OPERATION_COMMITTED",
                "detail": "资产未提交、checkpoint 已存在 → 可按幂等规则重试",
                "auto_retry": True}

    # 资产已提交
    worker = {"asset_id": op["asset_id"], "pointer_version": op["pointer_version"],
              "logical_identity": op["logical_identity"],
              "result_hash": op["result_hash"]}

    if cp_missing:
        # 关键漏窗：资产已提交，checkpoint 没写
        return {"state": RECONCILED, "reason": "ASSET_COMMITTED_CHECKPOINT_MISSING",
                "detail": "资产事务已提交但 checkpoint 缺失，需按 operation 补齐（不重复写资产）",
                "auto_retry": False, "committed": worker}

    # 两侧都在：比较 checkpoint 记录的资产是否正确
    ck = cp["checkpoint"]

    # 关键分支：checkpoint 存在但**未记录结果**（如停在 asset_pending 阶段）。
    # 这仍然是漏窗 —— 资产已提交，checkpoint 只写了意图，尚未写回执。
    # 曾在此误判为 NOTHING_TO_DO（result_digest 为 None 被当成"一致"），已修。
    if not ck.get("result_digest"):
        return {"state": RECONCILED, "reason": "ASSET_COMMITTED_RESULT_NOT_RECORDED",
                "detail": "资产已提交但 checkpoint 只有意图没有回执，需按 operation 补齐",
                "auto_retry": False, "committed": worker}

    if ck["result_digest"] != op["result_hash"]:
        return {"state": NEEDS_HUMAN, "reason": "DIGEST_MISMATCH",
                "detail": "checkpoint 记录的摘要与资产库不一致，需人工核对",
                "auto_retry": False, "committed": worker}

    return {"state": NOTHING_TO_DO, "reason": "ALREADY_CONSISTENT",
            "detail": "两侧一致，无需动作", "auto_retry": False,
            "committed": worker}


def write_after_asset_commit(checkpoint_store, *, task_id: str, run_id: str,
                             op_record: dict) -> dict:
    """资产已提交后，补写 checkpoint。**幂等**：已写就跳过。"""
    if op_record.get("pointer_version") is None:
        return {"ok": False, "error": "PERMISSION_DENIED", "detail": "缺少 pointer_version"}

    cp = checkpoint_store.read_checkpoint(task_id=task_id, run_id=run_id)
    if cp.get("ok") and cp["checkpoint"].get("result_digest") == op_record.get("result_hash"):
        return {"ok": True, "already_recorded": True}

    if not cp.get("ok"):
        # checkpoint 不存在 → 建一条（带 expected_version=None 语义由 store 负责）
        make = checkpoint_store.create_checkpoint(
            task_id=task_id, run_id=run_id, stage="asset_committed")
        if not make.get("ok") and make.get("error") != "CONFLICT":
            return {"ok": False, "error": make.get("error"),
                    "detail": f"create checkpoint 失败: {make.get('detail')}"}

    # **摘要口径必须与 operation_log 完全一致**，否则下次对账会误报 DIGEST_MISMATCH。
    # 曾在此用 {asset_id, pointer_version} 作为 result_payload，而 operation_log 存的是
    # 资产 content_hash —— 两个不同口径的 sha256 必然不等。已修：直接从 op 取 result_hash 写回。
    import hashlib, json as _json
    digest = op_record.get("result_hash")
    if digest is None:
        return {"ok": False, "error": "PERMISSION_DENIED",
                "detail": "op_record 缺少 result_hash，无法对齐摘要口径"}

    # 直接写 result_digest（口径 = operation_log.result_hash），不走 record_result 的 payload 哈希
    try:
        checkpoint_store.conn.execute("BEGIN IMMEDIATE")
        checkpoint_store.conn.execute(
            "UPDATE checkpoints SET status='SUCCESS', result_digest=?, updated_at=? "
            "WHERE task_id=? AND run_id=?",
            (digest, time.strftime("%Y-%m-%dT%H:%M:%S%z"), task_id, run_id))
        checkpoint_store.conn.execute("COMMIT")
    except Exception as e:
        try: checkpoint_store.conn.execute("ROLLBACK")
        except Exception: pass
        return {"ok": False, "error": "CHECKPOINT_CORRUPT", "detail": str(e)[:150]}
    return {"ok": True, "result_digest": digest}


def assert_no_version_double_advance(store: KnowledgeStore, operation_id: str) -> dict:
    """同一次操作不得重复推进版本。**

    这是判断"对账过程有没有副作用"的硬检查。
    """
    rows = store.conn.execute(
        "SELECT pointer_version FROM operation_log WHERE operation_id=?",
        (operation_id,)).fetchall()
    n = len(rows)
    return {"ok": (n <= 1), "occurrences": n,
            "detail": f"operation_id={operation_id} 出现 {n} 次（必须 ≤1）"}
