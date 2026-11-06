#!/usr/bin/env python3
"""F2-P6G：真实源码命题裁决 + 持久化。零网络。"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
for p in ("collector", "content", "content_persistence", "source_analysis",
          "storage", "facts", "evidence_claims", "skill_interface", "renderer"):
    sys.path.insert(0, str(ROOT / "src" / p))

RID = "38923193"
C = "666df7c10035f7e26f27ec214fe5ae3173435f34"
DATA = "/tmp/p6f_real"


def main():
    import source_knowledge_query as Q
    import source_judgement as SJ
    import source_claim_adapter as SCA
    from knowledge_store import KnowledgeStore
    from paths import db_path

    ks = KnowledgeStore(str(db_path(DATA)), create=False)
    r = Q.source_query(repository_id=RID, commit_sha=C, file_path="index.js",
                       data_root=DATA)
    syms = list(r.get("symbols") or [])
    exps = list(r.get("exports") or [])
    out = {"repository_id": RID, "commit_sha": C, "file_path": "index.js",
           "fact_counts": {"symbols": len(syms), "exports": len(exps)},
           "claims": []}

    def do(label, claim, binding, facts):
        res = SJ.judge(store=ks, repository_id=RID, commit_sha=C,
                       file_path="index.js", claim=claim, binding=binding,
                       facts=facts, evidence_refs=["github:blobs"])
        res["label"] = label
        out["claims"].append(res)
        print(json.dumps({k: res[k] for k in
              ("label", "verdict", "reason_code", "claim_id",
               "verification_id", "display_level", "fact_ids")},
              ensure_ascii=False))

    # 命题 A：函数声明
    c, b = SCA.build_symbol_claim(repository_id=RID, commit_sha=C,
                                  file_path="index.js",
                                  qualified_name="isPlainObject",
                                  symbol_kind="js_function")
    do("A_symbol_isPlainObject", c, b, syms)

    # 命题 C：函数作用域局部变量
    c, b = SCA.build_symbol_claim(repository_id=RID, commit_sha=C,
                                  file_path="index.js",
                                  qualified_name="isPlainObject.prototype",
                                  symbol_kind="js_variable")
    do("C_local_prototype", c, b, syms)

    # 命题 B：默认导出
    c, b = SJ.build_export_claim(repository_id=RID, commit_sha=C,
                                 file_path="index.js",
                                 exported_name="isPlainObject",
                                 export_kind="default_export")
    do("B_default_export", c, b, exps)

    # 命题 B2：导出声明
    c, b = SJ.build_export_claim(repository_id=RID, commit_sha=C,
                                 file_path="index.js",
                                 exported_name="isPlainObject",
                                 export_kind="export_declaration")
    do("B2_export_declaration", c, b, exps)

    # 负例 D：不存在的函数
    c, b = SCA.build_symbol_claim(repository_id=RID, commit_sha=C,
                                  file_path="index.js",
                                  qualified_name="doesNotExist",
                                  symbol_kind="js_function")
    do("D_nonexistent", c, b, syms)

    # 负例 E：错 Commit
    c, b = SCA.build_symbol_claim(repository_id=RID, commit_sha="a" * 40,
                                  file_path="index.js",
                                  qualified_name="isPlainObject",
                                  symbol_kind="js_function")
    do("E_wrong_commit", c, b, syms)

    # 负例 F：错仓库
    c, b = SCA.build_symbol_claim(repository_id="24313173", commit_sha=C,
                                  file_path="index.js",
                                  qualified_name="isPlainObject",
                                  symbol_kind="js_function")
    do("F_cross_repo", c, b, syms)

    ks.close()
    Path("/tmp/p6g_judge.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = [x for x in out["claims"] if x["verdict"] == "supported"]
    print(json.dumps({"supported": len(ok),
                      "total": len(out["claims"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
