#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""源码结构知识：CLI 入口。★ 只读，零网络。"""

from paths import ensure_import_path
ensure_import_path()

_ROOT = None
import sys
from pathlib import Path
_root = Path(__file__).resolve().parents[1]
for _p in ("content_persistence", "renderer", "source_analysis"):
    _sp = str(_root / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)


def query_code(*, repository_id, commit_sha=None, file_path=None,
               symbol_name=None, symbol_kind=None, module_name=None,
               data_root=None):
    import source_knowledge_query as Q
    from paths import DEFAULT_DATA_ROOT
    return Q.source_query(
        repository_id=repository_id, commit_sha=commit_sha,
        file_path=file_path, symbol_name=symbol_name,
        symbol_kind=symbol_kind, module_name=module_name,
        data_root=data_root or DEFAULT_DATA_ROOT)


def query_module_relations(*, repository_id, commit_sha=None,
                           importing_file_path=None, module_specifier=None,
                           data_root=None):
    """查询静态模块关系。★ 只读。"""
    import module_relation_query as MQ
    from paths import DEFAULT_DATA_ROOT
    return MQ.query_relations(
        repository_id=repository_id, commit_sha=commit_sha,
        importing_file_path=importing_file_path,
        module_specifier=module_specifier,
        data_root=data_root or DEFAULT_DATA_ROOT)


def render_relation_card(*, repository_id, commit_sha=None,
                         importing_file_path=None, module_specifier=None,
                         data_root=None, out_dir=None):
    import module_relation_query as MQ
    import module_relation_card_models as MCM
    import module_relation_card_renderer as MCR
    from paths import DEFAULT_DATA_ROOT

    q = MQ.query_relations(
        repository_id=repository_id, commit_sha=commit_sha,
        importing_file_path=importing_file_path,
        module_specifier=module_specifier,
        data_root=data_root or DEFAULT_DATA_ROOT)
    card = MCM.build_relation_card(q)
    htm = MCR.render_relation_card_html(card)
    root = Path(data_root or DEFAULT_DATA_ROOT)
    out = Path(out_dir) if out_dir else (root / "cards")
    out.mkdir(parents=True, exist_ok=True)
    path = out / (card["card_id"] + ".html")
    path.write_text(htm, encoding="utf-8")
    return {"ok": True, "card_id": card["card_id"],
            "card_type": card["card_type"], "html_path": str(path),
            "html_bytes": len(htm.encode("utf-8")),
            "state": q.get("state"), "network_requests": 0}


def render_source_card(*, repository_id, commit_sha=None, file_path=None,
                       data_root=None, out_dir=None, card_type=None):
    import source_knowledge_query as Q
    import source_card_models as CM
    import source_card_renderer as CR
    from paths import DEFAULT_DATA_ROOT

    q = Q.source_query(repository_id=repository_id, commit_sha=commit_sha,
                       file_path=file_path,
                       data_root=data_root or DEFAULT_DATA_ROOT)
    card = CM.build_source_card(q, card_type=card_type)
    htm = CR.render_source_card_html(card)
    root = Path(data_root or DEFAULT_DATA_ROOT)
    out = Path(out_dir) if out_dir else (root / "cards")
    out.mkdir(parents=True, exist_ok=True)
    path = out / (card["card_id"] + ".html")
    path.write_text(htm, encoding="utf-8")
    return {"ok": True, "card_id": card["card_id"],
            "card_type": card["card_type"], "html_path": str(path),
            "html_bytes": len(htm.encode("utf-8")),
            "state": q.get("state"), "network_requests": 0}
