#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""内容知识卡片：CLI 唯一入口。★ 只读，不联网，不写库。"""

import sys
from pathlib import Path

from paths import ensure_import_path, db_path
from result import SkillError

ensure_import_path()

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("renderer", "content_persistence"):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)


def render_content_card(*, repository_id, commit_sha, file_path=None,
                        content_fact_id=None, content_claim_id=None,
                        data_root=None, out_dir=None):
    """生成内容卡片 HTML。返回 {ok, card_id, card_type, html_path, ...}。"""
    import content_knowledge_query as KQ
    import content_card_models as CM
    import content_card_renderer as CR
    from paths import DEFAULT_DATA_ROOT

    if not commit_sha:
        raise SkillError("内容卡片需要 --commit", code="MISSING_COMMIT", exit_code=3)

    q = KQ.content_query(repository_id=repository_id, commit_sha=commit_sha,
                         file_path=file_path, fact_id=content_fact_id,
                         data_root=data_root or DEFAULT_DATA_ROOT)
    if content_claim_id:
        q["claims"] = [c for c in (q.get("claims") or [])
                       if c.get("claim_id") == content_claim_id]

    card = CM.build_content_card(q)
    htm = CR.render_content_card_html(card)

    root = Path(data_root or DEFAULT_DATA_ROOT)
    out = Path(out_dir) if out_dir else (root / "cards")
    out.mkdir(parents=True, exist_ok=True)
    path = out / (card["card_id"] + ".html")
    path.write_text(htm, encoding="utf-8")

    return {"ok": True, "card_id": card["card_id"],
            "card_type": card["card_type"],
            "html_path": str(path),
            "html_bytes": len(htm.encode("utf-8")),
            "state": q.get("state"),
            "facts_count": len(card.get("facts") or []),
            "network_requests": q.get("network_requests", 0),
            "distribution_restrictions": card.get("distribution_restrictions"),
            "limitations": card.get("limitations")}
