#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TS 项目知识 CLI 入口。★ 只读。"""

import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
for _p in ("content_persistence", "renderer", "source_analysis",
           "skill_interface"):
    _sp = str(_root / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)


def query_projects(*, repository_id, commit_sha=None, config_path=None,
                   file_path=None, show_references=False, data_root=None):
    import ts_project_query as Q
    from paths import DEFAULT_DATA_ROOT
    return Q.query_projects(
        repository_id=repository_id, commit_sha=commit_sha,
        config_path=config_path, file_path=file_path,
        show_references=show_references,
        data_root=data_root or DEFAULT_DATA_ROOT)


def query_membership(*, repository_id, file_path, commit_sha=None,
                     data_root=None):
    import ts_project_query as Q
    from paths import DEFAULT_DATA_ROOT
    return Q.resolve_file_membership(
        repository_id=repository_id, file_path=file_path,
        commit_sha=commit_sha, data_root=data_root or DEFAULT_DATA_ROOT)


def render_ts_project_card(*, repository_id, commit_sha=None,
                           config_path=None, file_path=None,
                           card_type="project", data_root=None, out_dir=None):
    import ts_project_query as Q
    import ts_project_card_models as CM
    import ts_project_card_renderer as CR
    from paths import DEFAULT_DATA_ROOT

    q = Q.query_projects(repository_id=repository_id, commit_sha=commit_sha,
                         config_path=config_path, file_path=file_path,
                         show_references=True,
                         data_root=data_root or DEFAULT_DATA_ROOT)
    if card_type == "reference":
        card = CM.build_reference_card(q)
    elif card_type == "membership":
        card = CM.build_membership_card(q, file_path=file_path)
    else:
        card = CM.build_project_card(q)

    htm = CR.render_ts_card_html(card)
    root = Path(data_root or DEFAULT_DATA_ROOT)
    out = Path(out_dir) if out_dir else (root / "cards")
    out.mkdir(parents=True, exist_ok=True)
    path = out / (card["card_id"] + ".html")
    path.write_text(htm, encoding="utf-8")
    return {"ok": True, "card_id": card["card_id"],
            "card_type": card["card_type"], "html_path": str(path),
            "html_bytes": len(htm.encode("utf-8")),
            "state": q.get("state"), "network_requests": 0}
