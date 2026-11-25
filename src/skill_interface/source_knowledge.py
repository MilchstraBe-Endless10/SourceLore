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


def _d3_supplement_relations(store, repository_id, commit_sha, *,
                             importing_file_path, module_specifier,
                             data_root):
    """D3 可信来源解析：把经严格验证的本地补充源关系证据附上。

    ★ 不冒充在线采集：每条都带 source_repository_id / evidence_ref /
      source_role=verified_local_supplement；失败时静默返回 []。
    """
    if not str(repository_id).isdigit():
        return []
    try:
        _td = str(Path(__file__).resolve().parents[1] / "trust")
        if _td not in sys.path:
            sys.path.insert(0, _td)
        import source_provenance as SP
        resolved = SP.resolve_supplement(store, str(repository_id), commit_sha)
    except Exception:
        return []
    out = []
    import module_relation_query as MQ
    for sup in resolved.get("supplements", []):
        q = MQ.query_relations(
            repository_id=sup["repository_id"],
            commit_sha=sup.get("commit_sha") or commit_sha,
            importing_file_path=importing_file_path,
            module_specifier=module_specifier,
            data_root=data_root)
        for r in (q.get("relations") or []):
            x = dict(r)
            x["source_repository_id"] = sup["repository_id"]
            x["evidence_ref"] = sup.get("evidence_ref")
            x["source_role"] = "verified_local_supplement"
            out.append(x)
    return out


def query_module_relations(*, repository_id, commit_sha=None,
                           importing_file_path=None, module_specifier=None,
                           data_root=None, include_supplements=True):
    """查询静态模块关系。★ 只读，零网络。

    include_supplements=True 时复用 D3 可信来源解析，附加本地补充源关系，
    并保留每条证据的来源身份（不冒充在线采集）。
    """
    import module_relation_query as MQ
    from paths import DEFAULT_DATA_ROOT
    from knowledge_store import KnowledgeStore
    from paths import db_path
    root = data_root or DEFAULT_DATA_ROOT
    q = MQ.query_relations(
        repository_id=repository_id, commit_sha=commit_sha,
        importing_file_path=importing_file_path,
        module_specifier=module_specifier,
        data_root=root)
    if not include_supplements:
        return q
    try:
        store = KnowledgeStore(str(db_path(root)), create=False)
        sup = _d3_supplement_relations(
            store, repository_id, commit_sha,
            importing_file_path=importing_file_path,
            module_specifier=module_specifier,
            data_root=root)
        if sup:
            q["supplement_relations"] = sup
            q["supplement_count"] = len(sup)
    except Exception:
        pass
    return q


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
