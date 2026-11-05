#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""卡片与报告：复用 F2-P4A Safe Renderer，输出到受控内部目录。"""

from pathlib import Path

from paths import ensure_import_path, DEFAULT_DATA_ROOT
from result import SkillError
from knowledge import open_store

ensure_import_path()

PREVIEW_SUBDIR = "preview"


def _find_verification_for_claim(store, claim_id, repository_id):
    """★ KVA 只接受 verification_id；按 claim_id 反查是 CLI 层的职责。"""
    rows = store.conn.execute(
        "SELECT asset_id FROM index_rows WHERE asset_type='claim_verification' "
        "AND repository_id=? ORDER BY asset_version DESC, asset_id",
        (repository_id,)).fetchall()
    for r in rows:
        got = store.get_asset(r["asset_id"], verify=True)
        if not got.get("ok"):
            continue
        pl = (got["asset"] or {}).get("payload") or {}
        if pl.get("claim_id") == claim_id:
            return pl.get("verification_id")
    return None


def _view_of(store, *, claim_id=None, verification_id=None, repository_id=None):
    import knowledge_view_assembler as KVA
    if not verification_id and claim_id:
        verification_id = _find_verification_for_claim(store, claim_id,
                                                       repository_id)
        if not verification_id:
            raise SkillError(f"找不到该 Claim 的 Verification：{claim_id}",
                             code="VERIFICATION_NOT_FOUND")
    if not verification_id:
        raise SkillError("需要 --claim-id 或 --verification-id",
                         code="MISSING_TARGET")
    got = KVA.assemble_from_verification(
        store, verification_id=verification_id, repository_id=repository_id)
    if not got.get("ok"):
        raise SkillError(f"视图装配失败：{got.get('error_code')}",
                         code=got.get("error_code") or "VIEW_FAILED",
                         detail={"detail": got.get("detail")})
    return got["view"]


def render_card(*, claim_id=None, verification_id=None, repository_id,
                data_root=None) -> dict:
    import card_models as CM
    import card_renderer as CRD

    store = open_store(data_root)
    try:
        view = _view_of(store, claim_id=claim_id,
                        verification_id=verification_id,
                        repository_id=repository_id)
        card = CM.build_card(view)
        html = CRD.render_card_html(card)
        js = CRD.render_json(card)
    finally:
        store.close()

    outdir = Path(data_root or DEFAULT_DATA_ROOT) / PREVIEW_SUBDIR
    outdir.mkdir(parents=True, exist_ok=True)
    stem = card["card_id"]
    hpath = outdir / f"{stem}.html"
    jpath = outdir / f"{stem}.json"
    hpath.write_text(html, encoding="utf-8")
    jpath.write_text(js, encoding="utf-8")

    return {
        "card_id": card["card_id"],
        "html_path": str(hpath),
        "json_path": str(jpath),
        "preview_allowed": True,
        "distribution_allowed": False,
        "note": "本地内部预览产物，不是对外发布的正式知识",
    }


def render_report(*, cards_payload, title="SourceLore 知识报告",
                  data_root=None) -> dict:
    import report_renderer as RPT

    if not cards_payload:
        raise SkillError("报告至少需要一张卡片", code="EMPTY_REPORT")
    html = RPT.render_report_html(cards_payload, title=title)

    outdir = Path(data_root or DEFAULT_DATA_ROOT) / PREVIEW_SUBDIR
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / "report.html"
    path.write_text(html, encoding="utf-8")
    return {"report_path": str(path),
            "card_count": len(cards_payload),
            "distribution_allowed": False,
            "note": "内部预览报告，不得对外发布"}
