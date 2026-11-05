#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""运行状态：只读，不输出凭据。"""

from pathlib import Path

from paths import (ensure_import_path, db_path, DEFAULT_DATA_ROOT,
                   SKILL_VERSION, PROJECT_ROOT)

ensure_import_path()

LAST_OP_BASENAME = "last_operation.json"


def status(data_root=None) -> dict:
    p = db_path(data_root)
    root = Path(data_root or DEFAULT_DATA_ROOT)
    info = {
        "skill_version": SKILL_VERSION,
        "project_root": str(PROJECT_ROOT),
        "data_root": str(root),
        "db_path": str(p),
        "db_exists": p.exists(),
        "db_size_bytes": p.stat().st_size if p.exists() else 0,
        "storage_available": False,
        "repository_count": 0,
        "last_operation": None,
        "note": "不输出任何凭据或敏感配置",
    }
    if p.exists():
        try:
            from knowledge_store import KnowledgeStore
            store = KnowledgeStore(str(p), create=False)
            try:
                n = store.conn.execute(
                    "SELECT COUNT(DISTINCT repository_id) AS n "
                    "FROM index_rows").fetchone()["n"]
                info["repository_count"] = int(n)
                info["storage_available"] = True
                info["schema_version"] = store.schema_version()
            finally:
                store.close()
        except Exception as e:
            info["storage_error"] = f"{type(e).__name__}"
    last = root / LAST_OP_BASENAME
    if last.exists():
        try:
            import json
            info["last_operation"] = json.loads(last.read_text(encoding="utf-8"))
        except Exception:
            info["last_operation"] = {"note": "无法解析"}
    return info


def record_operation(name: str, payload: dict) -> None:
    import json, datetime
    tz = datetime.timezone(datetime.timedelta(hours=8))
    root = DEFAULT_DATA_ROOT
    root.mkdir(parents=True, exist_ok=True)
    body = {"operation": name,
            "at": datetime.datetime.now(tz).isoformat(timespec="seconds"),
            "ok": bool(payload.get("ok", True)),
            "summary": {k: payload.get(k) for k in
                        ("repository_id", "commit_sha", "coverage_state",
                         "completeness_status") if k in payload}}
    (root / LAST_OP_BASENAME).write_text(
        json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
