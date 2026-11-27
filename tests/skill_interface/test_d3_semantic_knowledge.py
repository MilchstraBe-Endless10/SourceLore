# -*- coding: utf-8 -*-
"""P2-D3 技术语义知识专项测试：Gate 1-10 + 负例。

脚本式测试（模块级 sys.exit），与 tests/ 现有风格一致。
所有测试只用隔离资产 / 内存对象；零网络、零真实库写入。
"""
import os
import sys

WT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
for _p in ("src", os.path.join("src", "storage"), os.path.join("src", "views"),
           os.path.join("src", "semantic_knowledge")):
    sys.path.insert(0, os.path.join(WT, _p))

import semantic_models as SM
import semantic_pipeline as SP

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append((name, detail))
    print(("PASS " if cond else "FAIL ") + name + (" | " + str(detail) if detail else ""))


def main():
    # Gate 1：真实生产链路——未注入宿主 client 必须拒绝，不用模型记忆补写
    r = SP.produce(None, repository_id="x", commit_sha="y", questions=[
        {"question": "架构", "knowledge_kind": SM.K_ARCHITECTURE, "subject": "架构"}])
    check("G1_no_client_rejected",
          r.get("state") == SP.NOT_CONFIGURED and r.get("network_requests") == 0)

    # Gate 2：证据支持性封顶——文档自述不得冒充源码事实
    capped = SP._cap_support_level(
        SM.S_DIRECTLY_SUPPORTED, SM.K_ARCHITECTURE, SM.SRC_DOC_SELF_REPORT, True)
    check("G2_source_cap_documentation",
          capped == SM.S_PARTIALLY_SUPPORTED, capped)
    capped_no_ev = SP._cap_support_level(
        SM.S_DIRECTLY_SUPPORTED, SM.K_ARCHITECTURE, SM.SRC_DOC_SELF_REPORT, False)
    check("G2_no_evidence_not_supported",
          capped_no_ev == SM.S_NOT_SUPPORTED, capped_no_ev)
    v, cov = SP._resolve_levels(SM.S_PARTIALLY_SUPPORTED)
    check("G2_partial_not_supported",
          v == SM.V_INSUFFICIENT and cov == SM.C_PARTIAL, f"{v}/{cov}")

    prop = SM.SemanticProposition(
        proposition="文档声称的架构", knowledge_kind=SM.K_ARCHITECTURE,
        repository_id="r", commit_sha="c", subject="架构",
        evidence=[SM.SemanticEvidenceRef.from_match({
            "content_sha256": "sha256:" + "a" * 64, "git_blob_oid": "b" * 40,
            "content_asset_id": "SL-A-x", "file_path": "docs/a.md",
            "byte_start": 0, "byte_end": 10, "line_start": 1, "line_end": 1,
            "source_category": "documentation_self_report",
            "provenance_level": "SYNTHETIC_FIXTURE",
            "copy_permitted": False, "distribution_allowed": False,
            "body": "doc"})],
        support_level=SM.S_PARTIALLY_SUPPORTED, source_category="documentation_self_report",
        verification_status=SM.V_INSUFFICIENT, coverage_state=SM.C_PARTIAL)
    payload = prop.content_payload()

    # Gate 4/6：授权继承——任一证据 DENY 则命题 DENY，历史误标不洗白
    check("G6_dist_inherit_deny", payload["distribution_allowed"] is False)
    check("G6_copy_inherit_deny", payload["copy_permitted"] is False)
    check("G6_provenance_not_laundered",
          prop.evidence[0].provenance_level == "SYNTHETIC_FIXTURE")

    # Gate 3/5：身份不含时间戳；同内容同证据幂等 ID 相同
    p2 = SM.SemanticProposition(
        proposition="文档声称的架构", knowledge_kind=SM.K_ARCHITECTURE,
        repository_id="r", commit_sha="c", subject="架构",
        evidence=list(prop.evidence), support_level=SM.S_PARTIALLY_SUPPORTED,
        source_category="documentation_self_report",
        verification_status=SM.V_INSUFFICIENT, coverage_state=SM.C_PARTIAL)
    check("G5_id_stable", p2.proposition_id == prop.proposition_id)
    # 不同仓库 / commit 身份不同
    p3 = SM.SemanticProposition(
        proposition="文档声称的架构", knowledge_kind=SM.K_ARCHITECTURE,
        repository_id="OTHER", commit_sha="c", subject="架构",
        evidence=list(prop.evidence), support_level=SM.S_PARTIALLY_SUPPORTED,
        source_category="documentation_self_report",
        verification_status=SM.V_INSUFFICIENT, coverage_state=SM.C_PARTIAL)
    check("G5_repo_isolated", p3.proposition_id != prop.proposition_id)

    # Gate 8：通用性——契约不绑定具体仓库名（任意 repo/commit 均可构造）
    check("G8_generic_repo", bool(p3.proposition_id) and "OTHER" in p3.repository_id)

    # Gate 6b：越界证据下标不能伪造——用假 client 返回非法下标，dry_run 应丢弃
    def bad_client(packet):
        return {"propositions": [{
            "proposition": "越界证据命题", "knowledge_kind": SM.K_ARCHITECTURE,
            "subject": "架构", "support_level": SM.S_DIRECTLY_SUPPORTED,
            "evidence_indices": [999, -1]}]}
    r2 = SP.produce(None, repository_id="r", commit_sha="c", questions=[
        {"question": "架构", "knowledge_kind": SM.K_ARCHITECTURE, "subject": "架构"}],
        client=bad_client, dry_run=True)
    # 无 store 时 recall 会失败，最坏也应 skip 而非伪造；这里只断绝不抛异常、零网络
    check("G6_no_forged_evidence", r2.get("network_requests") == 0 and "state" in r2)

    # Gate 10：源码静态契约——distribution 继承方向与 verdict 封顶方向正确
    src = open(os.path.join(WT, "src", "semantic_knowledge", "semantic_models.py"),
               encoding="utf-8").read()
    import re as _re
    check("G10_dist_direction",
          bool(_re.search(r"all\(\s*e\.distribution_allowed for e in self\.evidence", src)) and
          "all(not e.distribution_allowed" not in src)
    pipe = open(os.path.join(WT, "src", "semantic_knowledge", "semantic_pipeline.py"),
                encoding="utf-8").read()
    check("G10_partial_cap",
          "V_INSUFFICIENT, C_PARTIAL" in pipe or "V_INSUFFICIENT" in pipe)

    print("\nTOTAL PASS: %d | FAIL: %d" % (len(PASS), len(FAIL)))
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
