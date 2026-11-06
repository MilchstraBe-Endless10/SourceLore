#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""源码命题裁决编排：Fact → Claim → Verification。

★ 只编排，不改裁决语义。裁决仍在 source_claim_adapter.verify_source_claim。
★ 只写入，不改已冻结 A 层资产。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("content_persistence", "evidence_claims", "storage", "facts",
           "source_analysis", "content"):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

# ★ 五档显示分层（任务书 §8）
OBSERVED_SOURCE_FACT = "OBSERVED_SOURCE_FACT"
SUPPORTED_SOURCE_CLAIM = "SUPPORTED_SOURCE_CLAIM"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
UNSUPPORTED_SEMANTIC_FORM = "UNSUPPORTED_SEMANTIC_FORM"
NOT_ANALYZED = "NOT_ANALYZED"


def build_export_claim(*, repository_id, commit_sha, file_path,
                       exported_name, export_kind, expected_present=True):
    """导出声明命题。★ 复用同一条 EC 契约，不新开类型。

    `source_export_declared` 已在 ec_models.SOURCE_CLAIM_TYPES 里，
    此处只补构建器（原先只有 symbol/import/local_module）。
    """
    import ec_models as M
    import source_claim_adapter as SCA

    params = {"file_path": file_path, "exported_name": exported_name,
              "export_kind": export_kind,
              "expected_present": bool(expected_present)}
    cid = M.make_claim_id(repository_id=str(repository_id),
                          commit_sha=str(commit_sha),
                          claim_type=SCA.CLAIM_EXPORT,
                          normalized_parameters=params)
    claim = M.Claim(
        claim_id=cid, claim_type=SCA.CLAIM_EXPORT,
        repository_id=str(repository_id), commit_sha=str(commit_sha),
        normalized_path=file_path, expected_exists=bool(expected_present),
        claim_scope="single_file_source", claim_origin="source_extraction")
    return claim, {"exported_name": exported_name, "export_kind": export_kind}


def judge(*, store, repository_id, commit_sha, file_path, claim, binding,
          facts, content_available=True, completeness_status="COMPLETE",
          parser_ok=True, evidence_refs=None):
    """裁决并持久化。返回分层结论 + 三层身份。"""
    import source_claim_adapter as SCA
    import content_claim_ingest as CCI
    import ec_models as M

    verdict = SCA.verify_source_claim(
        claim=claim, facts=facts, content_available=content_available,
        completeness_status=completeness_status, parser_ok=parser_ok,
        subject_binding=binding)

    res = CCI.ingest_content_claim(
        store, claim=claim, verdict=verdict,
        facts_payload=facts, repository_id=str(repository_id),
        evidence_refs=evidence_refs or [])

    st = verdict.get("status")
    if st == M.SUPPORTED:
        level = SUPPORTED_SOURCE_CLAIM
    elif st == M.REFUTED:
        level = "REFUTED_SOURCE_CLAIM"
    else:
        level = INSUFFICIENT_EVIDENCE

    return {
        "claim_id": claim.claim_id,
        "claim_type": claim.claim_type,
        "verification_id": (res.get("verification_result") or {}).get(
            "verification_id"),
        "verdict": st,
        "reason_code": verdict.get("reason_code"),
        "detail": verdict.get("detail"),
        "fact_ids": list(verdict.get("supported_fact_ids") or []),
        "display_level": level,
        "persisted": bool(res.get("ok")),
        "persist_error": None if res.get("ok") else res.get("error"),
    }


def describe_symbol(subject):
    """把符号 subject 翻译成用户能懂的一句话。

    ★ 任务书 §6：`qualified_name=isPlainObject.prototype` 不得被读成
      「isPlainObject 函数对象的 prototype 属性被声明或赋值」。

    `a.b` 在 JS 里既可能是嵌套作用域，也可能是属性访问。这里用
    symbol_kind 与声明节点类型区分，而不是靠字符串猜。
    """
    if not isinstance(subject, dict):
        return {"text": "未知符号", "scope_kind": None}
    kind = subject.get("symbol_kind")
    qn = subject.get("qualified_name") or subject.get("symbol_name") or ""
    name = subject.get("symbol_name") or qn
    owner = qn.rsplit(".", 1)[0] if "." in qn else None

    if kind in ("js_function", "js_async_function", "js_generator_function",
                "js_arrow_function", "js_function_expression",
                "js_anonymous_function", "js_method", "js_object_method"):
        return {"text": "函数声明 %s" % name, "scope_kind": "declaration"}
    if kind in ("js_variable", "js_let", "js_const"):
        if owner:
            return {"text": "%s 函数作用域中的局部变量 %s" % (owner, name),
                    "scope_kind": "function_local",
                    "owner": owner}
        return {"text": "模块级变量 %s" % name, "scope_kind": "module_local"}
    if kind == "js_class":
        return {"text": "类声明 %s" % name, "scope_kind": "declaration"}
    return {"text": "符号 %s（%s）" % (name, kind), "scope_kind": kind}
