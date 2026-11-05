#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Renderer 测试夹具：真实视图 + 真实卡片。"""
import sys, tempfile, pathlib, importlib.util as iu, importlib
ROOT = pathlib.Path(__file__).resolve().parents[2]
for p in ("src/lifecycle", "src/storage", "src/collector", "src/facts",
          "src/evidence_claims", "src/runtime", "src/views", "src/renderer",
          "tests/views", "tests/evidence_claims"):
    if (ROOT/p).exists() and str(ROOT/p) not in sys.path:
        sys.path.insert(0, str(ROOT/p))

import vfx  # 复用 P3D 的视图夹具
import knowledge_view_assembler as KVA
import card_models as CM
import card_renderer as CRD
import report_renderer as RPT
import pre_publish_check as PPC
import view_integrity as VI

REPO = vfx.REPO


def fresh(tmpdir):
    return vfx.fresh(tmpdir)


def make_view(ks, **kw):
    """跑完整链路并返回 (source, target_view, result)。"""
    src, cand, res, ad = vfx.run_full(ks, **kw)
    target = KVA.assemble_from_verification(
        ks, verification_id=res.payload["target_verification_id"],
        repository_id=REPO)
    return src, target, res


def make_cards(ks, **kw):
    src, target, res = make_view(ks, **kw)
    a = KVA.assemble_from_verification(
        ks, verification_id=src["verification_id"], repository_id=REPO)
    cards = []
    for v in (a, target):
        if v.get("ok"):
            cards.append(CM.build_card(v["view"]))
    return cards, src, res


def render_bundle(card, *, stamped=""):
    return {
        "json": json_loads(CRD.render_json(card)),
        "json_text": CRD.render_json(card),
        "html": CRD.render_card_html(card, assembled_at=stamped),
    }


def json_loads(s):
    import json
    return json.loads(s)
