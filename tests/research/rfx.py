#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Research 测试夹具（复用 P3D/P4A 的真实链路）。"""
import sys, pathlib, importlib.util as iu
ROOT = pathlib.Path(__file__).resolve().parents[2]
for p in ("src/research", "src/views", "src/renderer", "src/lifecycle",
          "src/storage", "src/collector", "src/facts", "src/evidence_claims",
          "src/runtime", "tests/views", "tests/research"):
    if (ROOT/p).exists() and str(ROOT/p) not in sys.path:
        sys.path.insert(0, str(ROOT/p))

import vfx
import query_models as QM
import research_engine as RE
import retriever as RT
import evidence_selector as ES
import coverage_evaluator as CE
import research_packet as RP
import view_integrity as VI

REPO = vfx.REPO
A = vfx.A
B = vfx.B


def fresh(tmpdir):
    return vfx.fresh(tmpdir)


def q_path(**kw):
    kw.setdefault("repository_id", REPO)
    kw.setdefault("commit_sha", A)
    kw.setdefault("path", "README")
    return QM.build_query(question_type=QM.Q_PATH_CLAIM, **kw)


def q_claims(**kw):
    kw.setdefault("repository_id", REPO)
    kw.setdefault("commit_sha", A)
    return QM.build_query(question_type=QM.Q_KNOWN_CLAIMS, **kw)


def q_version(**kw):
    kw.setdefault("repository_id", REPO)
    kw.setdefault("commit_sha", A)
    kw.setdefault("compare_commit_sha", B)
    kw.setdefault("path", "README")
    return QM.build_query(question_type=QM.Q_VERSION_COMPARE, **kw)


def run(ks, q, **kw):
    return RE.run_research(ks, q, **kw)
