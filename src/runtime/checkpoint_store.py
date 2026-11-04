#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SourceLore 本地 checkpoint 存储（SQLite）。

契约来源：SL-CAP-0071（执行状态与检查点）、SL-CAP-0064（CAS 与恢复）、
SL-CAP-0067（根目录与路径隔离）、SL-CAP-0072（授权边界）。

**边界声明（必须读懂再用）：**
  本模块只管**执行状态**，不管知识资产。
  checkpoint 数据**不得**写入知识资产 A/B/C 层命名空间（Y-4 裁决）。
  本模块不自称"已验证事务原子性"—— 它只是把 SQLite 的事务用对了；
  真正的崩溃注入测试在 tests/runtime/test_crash_recovery.py 里真实执行。
"""

import sqlite3
import os
import json
import hashlib
import time
from pathlib import Path
from typing import Optional

SCHEMA_VERSION = 1

# 知识资产命名空间黑名单：checkpoint 根不得落在这些路径下（防止污染权威资产）
FORBIDDEN_ROOT_PREFIXES = (
    "docs/fusion/",
    "knowledge/",
    "assets/",
    "CAPABILITY_CROSSWALK",
)

# 绝不持久化的敏感字段名（按名拦截，不靠调用方自觉）
FORBIDDEN_FIELDS = (
    "api_key", "apikey", "api-key", "token", "cookie", "secret",
    "password", "passwd", "credential", "private_key", "authorization",
    "env", "environ", "envvars",
)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _sha(obj) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _reject_sensitive(fields: dict, where: str):
    low = {str(k).lower() for k in fields}
    hit = [f for f in FORBIDDEN_FIELDS if any(f in l for l in low)]
    if hit:
        raise PermissionError(f"{where}: 拒绝持久化敏感字段 {hit}")


class CheckpointStore:
    """最小可靠 checkpoint 存储。

    硬规则：
      K-1 task_id / run_id / subject_id 不可互换（三者独立列）。
      K-2 更新必须带 expected_version；无版本覆盖一律拒绝。
      K-3 版本不匹配 → CONFLICT；记录不存在 → NOT_FOUND；库损坏 → CHECKPOINT_CORRUPT。
      K-4 重复 idempotency_key 不重复登记已成功提交的操作。
      K-5 损坏的库不当作空库，不自动重建。
    """

    def __init__(self, db_path: str | Path, *, create: bool = True):
        self.path = Path(db_path)
        self._verify_root_isolation()
        if not create and not self.path.exists():
            raise FileNotFoundError(f"数据库不存在: {self.path}")

        self.conn = sqlite3.connect(str(self.path), timeout=5.0,
                                    isolation_level=None)  # 手动控制事务
        self.conn.row_factory = sqlite3.Row
        # PRAGMA 顺序很关键：**先设 busy_timeout，再切 journal_mode**。
        # 反过来会在多进程同时首开新库时直接 database is locked —— 实测踩过。
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.conn.execute("PRAGMA synchronous=FULL")   # 崩溃安全优先于吞吐
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._enable_wal_with_retry()
        if create:
            self._init_schema()
        else:
            self._check_integrity()

    # ── 隔离与完整性 ────────────────────────────────────────
    def _enable_wal_with_retry(self, attempts: int = 12):
        """切换 WAL。多进程同时首开新库时可能短时抢锁，按 busy_timeout 退让重试。

        WAL 是**幂等**的：已经是 WAL 时再设一次直接返回。所以重试安全。
        """
        last = None
        for _ in range(attempts):
            try:
                mode = self.conn.execute("PRAGMA journal_mode=WAL").fetchone()
                if mode and str(mode[0]).lower() == "wal":
                    return
                last = f"journal_mode 返回 {mode[0] if mode else None}"
            except sqlite3.OperationalError as e:
                last = str(e)
            time.sleep(0.05)
        raise RuntimeError(f"CHECKPOINT_CORRUPT: WAL 切换失败: {last}")

    def _verify_root_isolation(self):
        """checkpoint 根不得位于知识资产命名空间。"""
        abs_path = self.path.resolve()
        parts = str(abs_path)
        for pref in FORBIDDEN_ROOT_PREFIXES:
            if pref in parts:
                raise PermissionError(
                    f"checkpoint 路径落在知识资产命名空间内（{pref}）：{abs_path}"
                )

    def _init_schema(self):
        self.conn.executescript(f"""
        CREATE TABLE IF NOT EXISTS meta (
            k TEXT PRIMARY KEY,
            v TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS checkpoints (
            task_id            TEXT NOT NULL,
            run_id             TEXT NOT NULL,
            stage              TEXT NOT NULL,
            status             TEXT NOT NULL,
            checkpoint_version INTEGER NOT NULL CHECK(checkpoint_version >= 1),
            checkpoint_ref     TEXT,
            attempt_count      INTEGER NOT NULL DEFAULT 0,
            idempotency_key    TEXT,
            input_digest       TEXT,
            result_digest      TEXT,
            updated_at         TEXT NOT NULL,
            PRIMARY KEY (task_id, run_id)
        );
        CREATE TABLE IF NOT EXISTS attempts (
            task_id         TEXT NOT NULL,
            run_id          TEXT NOT NULL,
            attempt_no      INTEGER NOT NULL,
            state           TEXT NOT NULL,
            exit_code       INTEGER,
            side_effect_possible INTEGER NOT NULL DEFAULT 0,
            detail          TEXT,
            recorded_at     TEXT NOT NULL,
            PRIMARY KEY (task_id, run_id, attempt_no)
        );
        CREATE TABLE IF NOT EXISTS idempotency (
            idempotency_key TEXT PRIMARY KEY,
            task_id         TEXT NOT NULL,
            run_id          TEXT NOT NULL,
            result_digest   TEXT NOT NULL,
            committed_at    TEXT NOT NULL
        );
        """)
        row = self.conn.execute("SELECT v FROM meta WHERE k='schema_version'").fetchone()
        if row is None:
            self.conn.execute("INSERT INTO meta(k,v) VALUES('schema_version',?)",
                              (str(SCHEMA_VERSION),))
        elif int(row["v"]) != SCHEMA_VERSION:
            raise RuntimeError(f"schema_version 不匹配：库={row['v']} 代码={SCHEMA_VERSION}")

    def _check_integrity(self):
        try:
            r = self.conn.execute("PRAGMA integrity_check").fetchone()
        except sqlite3.DatabaseError as e:
            raise RuntimeError(f"CHECKPOINT_CORRUPT: 无法执行完整性检查: {e}")
        if r is None or r[0] != "ok":
            got = r[0] if r else "no-result"
            raise RuntimeError(f"CHECKPOINT_CORRUPT: integrity_check={got}")

    def schema_version(self) -> int:
        r = self.conn.execute("SELECT v FROM meta WHERE k='schema_version'").fetchone()
        if r is None:
            raise RuntimeError("CHECKPOINT_CORRUPT: 缺少 schema_version")
        return int(r["v"])

    # ── 写：创建 ────────────────────────────────────────────
    def create_checkpoint(self, *, task_id: str, run_id: str, stage: str,
                          status: str = "in_progress",
                          subject_id: Optional[str] = None,
                          idempotency_key: Optional[str] = None,
                          input_digest: Optional[str] = None,
                          payload: Optional[dict] = None) -> dict:
        """创建一条唯一 checkpoint。

        task_id 与 run_id 必须都提供且互不替代（K-1）。
        重复创建同一 (task_id, run_id) → CONFLICT（不静默覆盖）。
        """
        if not task_id or not run_id:
            return {"ok": False, "error": "PERMISSION_DENIED",
                    "detail": "task_id 与 run_id 必填且不可互换"}
        if subject_id is not None:
            _reject_sensitive({"subject_id": subject_id}, "create_checkpoint")
        if payload:
            _reject_sensitive(payload, "create_checkpoint.payload")

        ck = _sha({"task_id": task_id, "run_id": run_id, "stage": stage,
                   "idempotency_key": idempotency_key})
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            self.conn.execute(
                """INSERT INTO checkpoints
                   (task_id, run_id, stage, status, checkpoint_version,
                    checkpoint_ref, attempt_count, idempotency_key,
                    input_digest, result_digest, updated_at)
                   VALUES (?,?,?,?,1,?,0,?,?,NULL,?)""",
                (task_id, run_id, stage, status, ck, idempotency_key,
                 input_digest, _now()))
            self.conn.execute("COMMIT")
        except sqlite3.IntegrityError:
            self.conn.execute("ROLLBACK")
            return {"ok": False, "error": "CONFLICT",
                    "detail": f"checkpoint 已存在: {task_id}/{run_id}"}
        except sqlite3.DatabaseError as e:
            self.conn.execute("ROLLBACK")
            return {"ok": False, "error": "CHECKPOINT_CORRUPT", "detail": str(e)}

        return {"ok": True, "checkpoint_version": 1, "checkpoint_ref": ck}

    # ── 读 ─────────────────────────────────────────────────
    def read_checkpoint(self, *, task_id: str, run_id: str) -> dict:
        try:
            row = self.conn.execute(
                "SELECT * FROM checkpoints WHERE task_id=? AND run_id=?",
                (task_id, run_id)).fetchone()
        except sqlite3.DatabaseError as e:
            return {"ok": False, "error": "CHECKPOINT_CORRUPT", "detail": str(e)}
        if row is None:
            return {"ok": False, "error": "NOT_FOUND",
                    "detail": f"无此 checkpoint: {task_id}/{run_id}"}
        return {"ok": True, "checkpoint": dict(row)}

    def inspect_checkpoint(self, *, task_id: str, run_id: str) -> dict:
        """比 read 更细：带 attempt 历史与幂等登记。"""
        base = self.read_checkpoint(task_id=task_id, run_id=run_id)
        if not base["ok"]:
            return base
        attempts = [dict(r) for r in self.conn.execute(
            "SELECT * FROM attempts WHERE task_id=? AND run_id=? ORDER BY attempt_no",
            (task_id, run_id)).fetchall()]
        idem = None
        if base["checkpoint"].get("idempotency_key"):
            r = self.conn.execute("SELECT * FROM idempotency WHERE idempotency_key=?",
                                  (base["checkpoint"]["idempotency_key"],)).fetchone()
            idem = dict(r) if r else None
        return {"ok": True, "checkpoint": base["checkpoint"],
                "attempts": attempts, "idempotency": idem}

    # ── 写：CAS 更新（核心）─────────────────────────────────
    def update_checkpoint_if_version(self, *, task_id: str, run_id: str,
                                     expected_version: int,
                                     stage: Optional[str] = None,
                                     status: Optional[str] = None,
                                     result_digest: Optional[str] = None,
                                     payload: Optional[dict] = None) -> dict:
        """乐观并发更新。版本不匹配 → CONFLICT，绝不静默覆盖（K-2/K-3）。"""
        if payload:
            _reject_sensitive(payload, "update_checkpoint_if_version.payload")

        sets, args = [], []
        if stage is not None:
            sets.append("stage=?"); args.append(stage)
        if status is not None:
            sets.append("status=?"); args.append(status)
        if result_digest is not None:
            sets.append("result_digest=?"); args.append(result_digest)
        sets.append("checkpoint_version=checkpoint_version+1")
        sets.append("updated_at=?"); args.append(_now())

        try:
            self.conn.execute("BEGIN IMMEDIATE")
            cur = self.conn.execute(
                f"UPDATE checkpoints SET {', '.join(sets)} "
                "WHERE task_id=? AND run_id=? AND checkpoint_version=?",
                (*args, task_id, run_id, expected_version))
            if cur.rowcount == 0:
                exists = self.conn.execute(
                    "SELECT checkpoint_version FROM checkpoints WHERE task_id=? AND run_id=?",
                    (task_id, run_id)).fetchone()
                self.conn.execute("ROLLBACK")
                if exists is None:
                    return {"ok": False, "error": "NOT_FOUND",
                            "detail": f"无此 checkpoint: {task_id}/{run_id}"}
                return {"ok": False, "error": "CONFLICT",
                        "current_version": exists["checkpoint_version"],
                        "expected_version": expected_version}
            newv = self.conn.execute(
                "SELECT checkpoint_version FROM checkpoints WHERE task_id=? AND run_id=?",
                (task_id, run_id)).fetchone()["checkpoint_version"]
            self.conn.execute("COMMIT")
            return {"ok": True, "checkpoint_version": newv}
        except sqlite3.DatabaseError as e:
            try: self.conn.execute("ROLLBACK")
            except Exception: pass
            return {"ok": False, "error": "CHECKPOINT_CORRUPT", "detail": str(e)}

    # ── 写：attempt 与结果 ─────────────────────────────────
    def record_attempt(self, *, task_id: str, run_id: str, state: str,
                       exit_code: Optional[int] = None,
                       side_effect_possible: bool = False,
                       detail: str = "") -> dict:
        """登记一次尝试。状态必须是执行期状态之一。"""
        from execution_result import EXECUTION_STATES, SIDE_EFFECT_RISK_STATES
        if state not in EXECUTION_STATES:
            return {"ok": False, "error": "PERMISSION_DENIED",
                    "detail": f"非法执行状态 {state!r}"}
        if state in SIDE_EFFECT_RISK_STATES and not side_effect_possible:
            return {"ok": False, "error": "PERMISSION_DENIED",
                    "detail": f"{state} 必须声明 side_effect_possible=True"}
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            ck = self.conn.execute(
                "SELECT attempt_count, checkpoint_version FROM checkpoints "
                "WHERE task_id=? AND run_id=?", (task_id, run_id)).fetchone()
            if ck is None:
                self.conn.execute("ROLLBACK")
                return {"ok": False, "error": "NOT_FOUND"}
            n = ck["attempt_count"] + 1
            self.conn.execute(
                """INSERT INTO attempts
                   (task_id, run_id, attempt_no, state, exit_code,
                    side_effect_possible, detail, recorded_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (task_id, run_id, n, state, exit_code,
                 1 if side_effect_possible else 0, detail, _now()))
            self.conn.execute(
                "UPDATE checkpoints SET attempt_count=?, checkpoint_version=checkpoint_version+1, "
                "updated_at=? WHERE task_id=? AND run_id=?",
                (n, _now(), task_id, run_id))
            v = self.conn.execute(
                "SELECT checkpoint_version FROM checkpoints WHERE task_id=? AND run_id=?",
                (task_id, run_id)).fetchone()["checkpoint_version"]
            self.conn.execute("COMMIT")
            return {"ok": True, "attempt_no": n, "checkpoint_version": v}
        except sqlite3.DatabaseError as e:
            try: self.conn.execute("ROLLBACK")
            except Exception: pass
            return {"ok": False, "error": "CHECKPOINT_CORRUPT", "detail": str(e)}

    def record_result(self, *, task_id: str, run_id: str, state: str,
                      exit_code: Optional[int] = None,
                      side_effect_possible: bool = False,
                      detail: str = "",
                      result_payload: Optional[dict] = None) -> dict:
        """登记最终结果。SUCCESS 必须带可校验的 result_digest。"""
        if result_payload:
            _reject_sensitive(result_payload, "record_result.result_payload")
        r = self.record_attempt(task_id=task_id, run_id=run_id, state=state,
                                exit_code=exit_code,
                                side_effect_possible=side_effect_possible,
                                detail=detail)
        if not r["ok"]:
            return r
        digest = _sha(result_payload) if result_payload is not None else None
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            self.conn.execute(
                "UPDATE checkpoints SET status=?, result_digest=COALESCE(?,result_digest), "
                "updated_at=? WHERE task_id=? AND run_id=?",
                (state, digest, _now(), task_id, run_id))
            self.conn.execute("COMMIT")
        except sqlite3.DatabaseError as e:
            try: self.conn.execute("ROLLBACK")
            except Exception: pass
            return {"ok": False, "error": "CHECKPOINT_CORRUPT", "detail": str(e)}
        return {"ok": True, "state": state, "result_digest": digest,
                "checkpoint_version": r["checkpoint_version"]}

    # ── 幂等登记 ────────────────────────────────────────────
    def commit_idempotent(self, *, idempotency_key: str, task_id: str, run_id: str,
                          result_payload: dict) -> dict:
        """按 idempotency_key 登记已成功提交的操作。

        重复键 → 返回 already_committed=True，**不重复登记**（K-4）。
        注意：这只保证**本地登记**幂等，不等于外部工具具备 exactly-once。
        """
        _reject_sensitive(result_payload, "commit_idempotent.result_payload")
        digest = _sha(result_payload)
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            self.conn.execute(
                "INSERT INTO idempotency(idempotency_key, task_id, run_id, "
                "result_digest, committed_at) VALUES(?,?,?,?,?)",
                (idempotency_key, task_id, run_id, digest, _now()))
            self.conn.execute("COMMIT")
            return {"ok": True, "already_committed": False, "result_digest": digest}
        except sqlite3.IntegrityError:
            self.conn.execute("ROLLBACK")
            prev = self.conn.execute(
                "SELECT * FROM idempotency WHERE idempotency_key=?",
                (idempotency_key,)).fetchone()
            return {"ok": True, "already_committed": True,
                    "result_digest": prev["result_digest"] if prev else None,
                    "detail": "该幂等键已提交，未重复登记"}
        except sqlite3.DatabaseError as e:
            try: self.conn.execute("ROLLBACK")
            except Exception: pass
            return {"ok": False, "error": "CHECKPOINT_CORRUPT", "detail": str(e)}

    # ── 恢复 ───────────────────────────────────────────────
    def resume_checkpoint(self, *, task_id: str, run_id: str) -> dict:
        """恢复判定。**只依据持久化记录，不从热记忆推断。**

        返回可恢复/不可恢复，并说明依据；绝不在缺失时凭空造一条。
        """
        r = self.inspect_checkpoint(task_id=task_id, run_id=run_id)
        if not r["ok"]:
            return {"ok": False, "resumable": False,
                    "error": r["error"], "detail": r.get("detail", "")}
        ck = r["checkpoint"]
        last = r["attempts"][-1] if r["attempts"] else None

        # 若最后一次尝试副作用可能已发生且状态未定 → 不得自动续跑
        if last and last["state"] == "UNKNOWN":
            return {"ok": True, "resumable": False, "reason": "UNKNOWN_NEEDS_RECONCILE",
                    "checkpoint": ck, "last_attempt": last,
                    "detail": "上次执行副作用可能已发生但回执缺失，必须人工或重新观测后收敛"}
        if last and last["side_effect_possible"] and last["state"] == "TIMEOUT":
            return {"ok": True, "resumable": False, "reason": "TIMEOUT_SIDE_EFFECT_RISK",
                    "checkpoint": ck, "last_attempt": last,
                    "detail": "超时且副作用可能已发生，不得擅自重做"}
        return {"ok": True, "resumable": True, "reason": "CLEAN",
                "checkpoint": ck, "last_attempt": last,
                "from_stage": ck["stage"],
                "expected_version": ck["checkpoint_version"]}

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()
