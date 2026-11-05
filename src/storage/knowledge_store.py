#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SourceLore 权威知识存储（A 层 + B 层 + C 层索引，单库）。

契约：SL-CAP-0062 / 0063 / 0064 / 0065 / 0067。

**为什么是单个库文件（重要设计决定）：**
  实测过 ATTACH 两个独立库的跨库事务。虽然 WAL 主库下 COMMIT 可通过主库日志
  一次原子化，但 **SQLite 不承诺两个各自为 WAL 的库的跨库原子提交**。
  本模块因此把 A/B/C 放在**同一个库文件**里，用**一个事务**同时约束三层。
  这解决了 A/B 同事务提交（题面 W-4/W-5），且不依赖未经证明的跨库 ACID。

**与 checkpoint 库的关系：**
  完全独立的物理文件 + 独立事务边界。
  两者之间**没有**全局事务保证 —— 由 operation_id 对账来收敛（见 operation_ledger / coordinator）。
"""

import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Optional

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from asset_models import (
    Asset, AssetDraft, ModelError, SourceSnapshot,
    canonical_json, content_hash_of,
)

SCHEMA_VERSION = 1

# 知识库根不得落在这些位置（仅是**辅助**防线，主防线是内部生成 ID）
FORBIDDEN_ROOT_MARKERS = (
    "/.git/", "CAPABILITY_CROSSWALK", "/docs/fusion/",
)

# 合法 pointer 状态
POINTER_OK = "ok"
POINTER_DANGLING = "dangling_pointer"     # 指向的资产不存在
POINTER_INVALID = "pointer_invalid"       # 指针结构不自洽（如版本回退）


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _asset_id_for(repository_id: str, logical_identity: str,
                  asset_version: int, content_hash: str) -> str:
    """资产 ID **由内部计算**，绝不由用户提供的路径或名称决定。

    这样用户可以随便传 repository_id / logical_identity 的字符，
    真正的文件与行 ID 永远是安全的自生成串。

    **必须包含 repository_id**：跨仓库同名 logical_identity 是不同知识，
    若 ID 只由 (logical_identity, version, hash) 决定，两条记录会算出同一个
    asset_id 并撞主键 —— 这是本轮实测抓到的真实缺陷。
    """
    raw = f"{repository_id}\x00{logical_identity}\x00{asset_version}\x00{content_hash}"
    return "SL-A-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


class KnowledgeStore:
    """权威知识存储。

    硬规则：
      K1 A 层只追加，永不原地覆盖（UPDATE/DELETE 在 A 表上被禁止）
      K2 同 (logical_identity, asset_version) 内容不同 → CONFLICT
      K3 同内容可按明确作用域幂等
      K4 B 指针推进必须带 expected_version（CAS）
      K5 A/B 提交在同一事务；postcondition 在**提交前**执行
      K6 C 层可删除重建，重建不改 A/B
      K7 内容哈希不等于逻辑身份
    """

    def __init__(self, db_path: str | Path, *, create: bool = True):
        self.path = Path(db_path)
        self._guard_root()
        if not create and not self.path.exists():
            raise FileNotFoundError(f"知识库不存在: {self.path}")

        self.conn = sqlite3.connect(str(self.path), timeout=5.0, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        # 顺序：busy_timeout 必须在 WAL 之前（F2-P1A 已实证）
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.conn.execute("PRAGMA synchronous=FULL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._enable_wal_with_retry()
        self.fts5_available = self._detect_fts5()
        if create:
            self._init_schema()
        else:
            self._check_integrity()

    # ── 基础 ────────────────────────────────────────────────
    def _guard_root(self):
        resolved = str(self.path.resolve())
        for m in FORBIDDEN_ROOT_MARKERS:
            if m in resolved:
                raise PermissionError(f"知识库拒绝落在受保护位置（{m}）：{resolved}")

    def _enable_wal_with_retry(self, attempts: int = 12):
        last = None
        for _ in range(attempts):
            try:
                mode = self.conn.execute("PRAGMA journal_mode=WAL").fetchone()
                if mode and str(mode[0]).lower() == "wal":
                    return
                last = f"journal_mode={mode[0] if mode else None}"
            except sqlite3.OperationalError as e:
                last = str(e)
            time.sleep(0.05)
        raise RuntimeError(f"CHECKPOINT_CORRUPT: WAL 切换失败: {last}")

    def _detect_fts5(self) -> bool:
        try:
            self.conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS _fts5_probe USING fts5(x)")
            self.conn.execute("DROP TABLE IF EXISTS _fts5_probe")
            return True
        except sqlite3.OperationalError:
            return False

    def _init_schema(self):
        self.conn.executescript(f"""
        CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT NOT NULL);

        -- A 层：不可变权威历史
        CREATE TABLE IF NOT EXISTS assets (
            asset_id          TEXT PRIMARY KEY,
            asset_type        TEXT NOT NULL,
            logical_identity  TEXT NOT NULL,
            repository_id     TEXT NOT NULL,
            subject_id        TEXT,
            asset_version     INTEGER NOT NULL CHECK(asset_version >= 1),
            content_hash      TEXT NOT NULL,
            payload_json      TEXT NOT NULL,
            commit_sha        TEXT,
            root_tree_sha     TEXT,
            tree_query_ref    TEXT,
            operation_id      TEXT,
            created_at        TEXT NOT NULL,
            UNIQUE(repository_id, logical_identity, asset_version)
        );

        -- A 表禁止原地修改：用触发器硬拦
        CREATE TRIGGER IF NOT EXISTS assets_no_update
        BEFORE UPDATE ON assets
        BEGIN SELECT RAISE(ABORT, 'A_LAYER_IMMUTABLE'); END;

        CREATE TRIGGER IF NOT EXISTS assets_no_delete
        BEFORE DELETE ON assets
        BEGIN SELECT RAISE(ABORT, 'A_LAYER_IMMUTABLE'); END;

        -- B 层：当前视图（只存指针）
        CREATE TABLE IF NOT EXISTS current_view (
            logical_identity TEXT NOT NULL,
            repository_id    TEXT NOT NULL,
            current_asset_id TEXT NOT NULL,
            pointer_version  INTEGER NOT NULL CHECK(pointer_version >= 1),
            last_known_good  TEXT,
            updated_at       TEXT NOT NULL,
            PRIMARY KEY (repository_id, logical_identity)
        );

        -- C 层：派生索引（可删除重建，不是事实权威）
        CREATE TABLE IF NOT EXISTS index_rows (
            asset_id         TEXT PRIMARY KEY,
            asset_type       TEXT NOT NULL,
            logical_identity TEXT NOT NULL,
            repository_id    TEXT NOT NULL,
            subject_id       TEXT,
            commit_sha       TEXT,
            asset_version    INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_repo  ON index_rows(repository_id);
        CREATE INDEX IF NOT EXISTS idx_subj  ON index_rows(subject_id);
        CREATE INDEX IF NOT EXISTS idx_type  ON index_rows(asset_type);
        CREATE INDEX IF NOT EXISTS idx_commit ON index_rows(commit_sha);
        CREATE INDEX IF NOT EXISTS idx_li    ON index_rows(logical_identity);

        -- 跨仓库身份：repo_binding（Subject ↔ 仓库关联，带证据）
        CREATE TABLE IF NOT EXISTS repo_bindings (
            binding_id       TEXT PRIMARY KEY,
            subject_id       TEXT NOT NULL,
            repository_id    TEXT NOT NULL,
            evidence_ref     TEXT NOT NULL,
            created_at       TEXT NOT NULL,
            UNIQUE(subject_id, repository_id, evidence_ref)
        );

        -- 操作账本：跨库协调的锚点
        CREATE TABLE IF NOT EXISTS operation_log (
            operation_id     TEXT PRIMARY KEY,
            kind             TEXT NOT NULL,
            logical_identity TEXT,
            asset_id         TEXT,
            pointer_version  INTEGER,
            result_hash      TEXT,
            committed_at     TEXT NOT NULL
        );
        """)
        if self.fts5_available:
            self.conn.executescript("""
            CREATE VIRTUAL TABLE IF NOT EXISTS asset_fts USING fts5(
                asset_id UNINDEXED, logical_identity, asset_type, payload_text,
                tokenize='unicode61 remove_diacritics 2'
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
            raise RuntimeError(f"CHECKPOINT_CORRUPT: {e}")
        if r is None or r[0] != "ok":
            raise RuntimeError(f"CHECKPOINT_CORRUPT: integrity_check={r[0] if r else None}")

    def schema_version(self) -> int:
        r = self.conn.execute("SELECT v FROM meta WHERE k='schema_version'").fetchone()
        if r is None:
            raise RuntimeError("CHECKPOINT_CORRUPT: 缺少 schema_version")
        return int(r["v"])

    # ── 读 A 层 ─────────────────────────────────────────────
    def _row_to_asset(self, row) -> Asset:
        return Asset(
            asset_id=row["asset_id"], asset_type=row["asset_type"],
            logical_identity=row["logical_identity"], repository_id=row["repository_id"],
            asset_version=row["asset_version"], content_hash=row["content_hash"],
            payload=json.loads(row["payload_json"]), created_at=row["created_at"],
            operation_id=row["operation_id"], subject_id=row["subject_id"],
            source_snapshot={"commit_sha": row["commit_sha"],
                             "root_tree_sha": row["root_tree_sha"],
                             "tree_query_ref": row["tree_query_ref"]},
        )

    def get_asset(self, asset_id: str, *, verify: bool = True) -> dict:
        row = self.conn.execute("SELECT * FROM assets WHERE asset_id=?", (asset_id,)).fetchone()
        if row is None:
            return {"ok": False, "error": "NOT_FOUND", "detail": asset_id}
        a = self._row_to_asset(row)
        if verify and not a.verify_integrity():
            return {"ok": False, "error": "CHECKPOINT_CORRUPT",
                    "detail": f"资产内容哈希校验失败: {asset_id}"}
        return {"ok": True, "asset": a.to_dict()}

    def history(self, logical_identity: str, repository_id: str | None = None) -> dict:
        if repository_id is None:
            rows = self.conn.execute(
                "SELECT asset_id, asset_version, content_hash, created_at, repository_id "
                "FROM assets WHERE logical_identity=? ORDER BY repository_id, asset_version",
                (logical_identity,)).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT asset_id, asset_version, content_hash, created_at, repository_id "
                "FROM assets WHERE repository_id=? AND logical_identity=? "
                "ORDER BY asset_version", (repository_id, logical_identity)).fetchall()
        return {"ok": True, "versions": [dict(r) for r in rows]}

    # ── 写：A/B 同事务 ─────────────────────────────────────
    def append_asset_and_advance(self, draft: AssetDraft, *,
                                 expected_version: Optional[int],
                                 operation_id: Optional[str] = None,
                                 postcondition=None) -> dict:
        """W-1..W-5 的完整实现。

        expected_version=None 表示首次发布（要求 B 中不存在该 logical_identity）。
        否则必须与 B 当前 pointer_version 完全相等，否则 CONFLICT。

        postcondition(cursor, ctx) 在**事务内、COMMIT 之前**执行；
        抛异常即回滚，**绝不先提交再检查**。
        """
        op_id = operation_id or draft.operation_id
        chash = draft.content_hash
        aid = _asset_id_for(draft.repository_id, draft.logical_identity,
                            draft.asset_version, chash)
        snap = draft.source_snapshot.to_dict() if draft.source_snapshot else {}

        try:
            self.conn.execute("BEGIN IMMEDIATE")

            # 幂等：同一 operation_id 已提交过 → 不重复写
            if op_id:
                prev = self.conn.execute(
                    "SELECT asset_id, pointer_version, result_hash FROM operation_log "
                    "WHERE operation_id=?", (op_id,)).fetchone()
                if prev is not None:
                    self.conn.execute("ROLLBACK")
                    return {"ok": True, "idempotent": True,
                            "asset_id": prev["asset_id"],
                            "pointer_version": prev["pointer_version"],
                            "result_hash": prev["result_hash"],
                            "detail": "operation_id 已提交，未重复写入"}

            # K2：同 (logical_identity, asset_version) 内容不同 → CONFLICT
            dup = self.conn.execute(
                "SELECT asset_id, content_hash FROM assets "
                "WHERE repository_id=? AND logical_identity=? AND asset_version=?",
                (draft.repository_id, draft.logical_identity,
                 draft.asset_version)).fetchone()
            if dup is not None:
                self.conn.execute("ROLLBACK")
                if dup["content_hash"] == chash:
                    return {"ok": True, "idempotent": True, "asset_id": dup["asset_id"],
                            "detail": "同版本同内容，按幂等处理"}
                return {"ok": False, "error": "CONFLICT",
                        "detail": f"同版本内容不同：已有 {dup['content_hash'][:12]}…，"
                                  f"提交 {chash[:12]}…"}

            # K4：CAS 校验 B 指针
            cur = self.conn.execute(
                "SELECT pointer_version, current_asset_id, last_known_good "
                "FROM current_view WHERE repository_id=? AND logical_identity=?",
                (draft.repository_id, draft.logical_identity)).fetchone()
            if expected_version is None:
                if cur is not None:
                    self.conn.execute("ROLLBACK")
                    return {"ok": False, "error": "CONFLICT",
                            "current_version": cur["pointer_version"],
                            "detail": "已存在当前视图，首次发布需要 expected_version=None 但记录已存在"}
            else:
                if cur is None:
                    self.conn.execute("ROLLBACK")
                    return {"ok": False, "error": "NOT_FOUND",
                            "detail": f"无当前视图: {draft.logical_identity}"}
                if cur["pointer_version"] != expected_version:
                    self.conn.execute("ROLLBACK")
                    return {"ok": False, "error": "CONFLICT",
                            "current_version": cur["pointer_version"],
                            "expected_version": expected_version}

            # 写 A 层
            self.conn.execute(
                """INSERT INTO assets(asset_id, asset_type, logical_identity, repository_id,
                     subject_id, asset_version, content_hash, payload_json,
                     commit_sha, root_tree_sha, tree_query_ref, operation_id, created_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (aid, draft.asset_type, draft.logical_identity, draft.repository_id,
                 draft.subject_id, draft.asset_version, chash,
                 canonical_json(draft.payload),
                 snap.get("commit_sha"), snap.get("root_tree_sha"),
                 snap.get("tree_query_ref"), op_id, _now()))

            # 推进 B 指针
            if cur is None:
                self.conn.execute(
                    """INSERT INTO current_view(logical_identity, repository_id,
                         current_asset_id, pointer_version, last_known_good, updated_at)
                       VALUES(?,?,?,1,?,?)""",
                    (draft.logical_identity, draft.repository_id, aid, aid, _now()))
                new_pv = 1
            else:
                new_pv = cur["pointer_version"] + 1
                self.conn.execute(
                    """UPDATE current_view SET current_asset_id=?, pointer_version=?,
                         last_known_good=?, updated_at=?
                       WHERE repository_id=? AND logical_identity=? AND pointer_version=?""",
                    (aid, new_pv, cur["current_asset_id"], _now(),
                     draft.repository_id, draft.logical_identity, cur["pointer_version"]))

            # postcondition 必须在 COMMIT **之前**
            if postcondition is not None:
                postcondition(self.conn, {"asset_id": aid, "logical_identity": draft.logical_identity,
                                          "pointer_version": new_pv})

            # C 层增补（与 A/B 同事务）
            self._index_asset(aid, draft)

            if op_id:
                self.conn.execute(
                    """INSERT INTO operation_log(operation_id, kind, logical_identity,
                         asset_id, pointer_version, result_hash, committed_at)
                       VALUES(?,?,?,?,?,?,?)""",
                    (op_id, "append_asset", draft.logical_identity, aid, new_pv,
                     chash, _now()))

            self.conn.execute("COMMIT")
            return {"ok": True, "asset_id": aid, "pointer_version": new_pv,
                    "content_hash": chash}
        except (sqlite3.IntegrityError, sqlite3.DatabaseError, ModelError, RuntimeError, ValueError) as e:
            try: self.conn.execute("ROLLBACK")
            except Exception: pass
            code = "CHECKPOINT_CORRUPT" if isinstance(e, sqlite3.DatabaseError) else "PERMISSION_DENIED"
            return {"ok": False, "error": code, "detail": f"{type(e).__name__}: {str(e)[:200]}"}

    @staticmethod
    def _resolve_index_commit_sha(draft: AssetDraft) -> Optional[str]:
        """从 draft 的可用信息里解析 commit_sha。

        ★ 只读 payload、不改资产、不改哈希 —— 索引是 C 层，可从权威数据重建。
        """
        if draft.source_snapshot is not None:
            cs = getattr(draft.source_snapshot, "commit_sha", None)
            if cs:
                return cs
        pl = draft.payload or {}
        cs = pl.get("commit_sha")
        if isinstance(cs, str) and cs:
            return cs
        snap = pl.get("source_snapshot")
        if isinstance(snap, dict):
            for k in ("commit_sha", "baseline_commit_sha", "observed_commit_sha"):
                v = snap.get(k)
                if isinstance(v, str) and v:
                    return v
        return None

    def _index_asset(self, aid: str, draft: AssetDraft):
        text = canonical_json(draft.payload)
        # ★ 索引的 commit_sha 不能只依赖 draft.source_snapshot。
        #   ingest 各路径常年不传 source_snapshot（实测该列因此全为 NULL），
        #   而 payload 里本来就有 commit_sha / snapshot 身份。三级回退：
        #   1) draft.source_snapshot  2) payload["commit_sha"]
        #   3) payload["source_snapshot"]["commit_sha"] / baseline_commit_sha
        commit_sha = self._resolve_index_commit_sha(draft)
        self.conn.execute(
            """INSERT INTO index_rows(asset_id, asset_type, logical_identity, repository_id,
                 subject_id, commit_sha, asset_version) VALUES(?,?,?,?,?,?,?)""",
            (aid, draft.asset_type, draft.logical_identity, draft.repository_id,
             draft.subject_id, commit_sha, draft.asset_version))
        if self.fts5_available:
            self.conn.execute(
                "INSERT INTO asset_fts(asset_id, logical_identity, asset_type, payload_text) "
                "VALUES(?,?,?,?)", (aid, draft.logical_identity, draft.asset_type, text))

    # ── 读 B 层 ─────────────────────────────────────────────
    def current_pointer(self, logical_identity: str, repository_id: str) -> dict:
        """读当前指针。**不把希望当事实**：指针坏就明说，不给空结果。

        repository_id 必填 —— 跨仓库同名的 logical_identity 是**不同知识**，
        只给 logical_identity 会静默合并，这是本轮实测抓到的真实缺陷。
        """
        ptr = self.conn.execute(
            "SELECT * FROM current_view WHERE repository_id=? AND logical_identity=?",
            (repository_id, logical_identity)).fetchone()
        if ptr is None:
            return {"ok": False, "error": "NOT_FOUND", "detail": logical_identity}

        asset = self.conn.execute(
            "SELECT asset_id FROM assets WHERE asset_id=?", (ptr["current_asset_id"],)).fetchone()
        if asset is None:
            return {"ok": False, "error": "CHECKPOINT_CORRUPT",
                    "state": POINTER_DANGLING,
                    "last_known_good": ptr["last_known_good"],
                    "pointer_version": ptr["pointer_version"],
                    "detail": f"指针指向不存在的资产 {ptr['current_asset_id']}；"
                              "last_known_good 保留供诊断，但**不得**当作当前值返回"}

        return {"ok": True, "state": POINTER_OK,
                "logical_identity": logical_identity,
                "current_asset_id": ptr["current_asset_id"],
                "pointer_version": ptr["pointer_version"],
                "last_known_good": ptr["last_known_good"],
                "repository_id": ptr["repository_id"]}

    # ── 跨仓库身份 ─────────────────────────────────────────
    def bind_repo(self, *, subject_id: str, repository_id: str, evidence_ref: str) -> dict:
        """显式建立 Subject ↔ 仓库关联。**不自动推断**，必须有证据引用。"""
        from asset_models import validate_id
        validate_id(subject_id, "subject_id")
        validate_id(repository_id, "repository_id")
        if not evidence_ref:
            return {"ok": False, "error": "PERMISSION_DENIED",
                    "detail": "必须提供 evidence_ref，不接受无证据的自动合并"}
        bid = "SL-B-" + hashlib.sha256(
            f"{subject_id}\x00{repository_id}\x00{evidence_ref}".encode()).hexdigest()[:32]
        try:
            self.conn.execute(
                "INSERT INTO repo_bindings(binding_id, subject_id, repository_id, "
                "evidence_ref, created_at) VALUES(?,?,?,?,?)",
                (bid, subject_id, repository_id, evidence_ref, _now()))
            return {"ok": True, "binding_id": bid}
        except sqlite3.IntegrityError:
            return {"ok": True, "binding_id": bid, "idempotent": True}

    def same_subject_across_repos(self, subject_id: str) -> dict:
        """列出同一 Subject 在哪些仓库有绑定 —— **不合并身份**，只列关系。"""
        rows = self.conn.execute(
            "SELECT repository_id, evidence_ref FROM repo_bindings WHERE subject_id=? "
            "ORDER BY repository_id", (subject_id,)).fetchall()
        return {"ok": True, "subject_id": subject_id,
                "bindings": [dict(r) for r in rows]}

    def close(self):
        try: self.conn.close()
        except Exception: pass

    def __enter__(self): return self

    def __exit__(self, *a): self.close()
