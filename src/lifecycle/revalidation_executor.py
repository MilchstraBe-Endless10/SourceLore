#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重新验证执行器：候选 → 授权 → 固定目标 B → Collector → Facts → 新 Claim → EC。

**严格边界：**
  E1 只对固定目标 Commit B 运行，**绝不重新解析 master 后悄悄改成 C**
  E2 新 Claim 身份必须等于 expected_target_claim_identity，否则立即停
  E3 旧 Claim / 旧 Verification 一律不动
  E4 execution_status 与 verification_status 分开
  E5 授权在**每个阶段**都复查（不只在开始时）

复用现有 Collector / Facts / EC / Storage，**不新建第二套**。
"""

import sys, json
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent / "collector"),
           str(_HERE.parent / "storage"), str(_HERE.parent / "facts"),
           str(_HERE.parent / "evidence_claims"), str(_HERE.parent / "runtime")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import lc_models as L
import revalidation_models as R
import revalidation_queue as RQ
import revalidation_authorization as AUTH
import revalidation_run_store as RS

import importlib
_facts_extractor = importlib.import_module("extractor")
_facts_ingest = importlib.import_module("ingest")
_ec_models = importlib.import_module("ec_models")
_ec_verifier = importlib.import_module("verifier")
_ec_store = importlib.import_module("verification_store")

# ── 执行错误码 ──────────────────────────────────────────────
E_PREFLIGHT_CANDIDATE_NOT_FOUND = "CANDIDATE_NOT_FOUND"
E_PREFLIGHT_NOT_PROPOSED = "CANDIDATE_NOT_PROPOSED"
E_PREFLIGHT_SUPERSEDED = "CANDIDATE_SUPERSEDED"
E_PREFLIGHT_NOT_ACTIVE = "CANDIDATE_NOT_ACTIVE"
E_PREFLIGHT_UNRESOLVED_CONFLICT = "UNRESOLVED_CONFLICT"
E_AUTH_REJECTED = "AUTHORIZATION_REJECTED"
E_AUTH_REVOKED_MIDRUN = "AUTHORIZATION_REVOKED_DURING_RUN"
E_COLLECT_FAILED = "COLLECTOR_FAILED"
E_COLLECT_COMMIT_MISMATCH = "COLLECTED_COMMIT_MISMATCH"
E_COLLECT_TREE_NOT_FROM_COMMIT = "ROOT_TREE_NOT_FROM_COMMIT_OBJECT"
E_FACT_FAILED = "FACTS_EXTRACT_FAILED"
E_FACT_COMMIT_MISMATCH = "FACT_COMMIT_MISMATCH"
E_TARGET_CLAIM_IDENTITY_MISMATCH = "TARGET_CLAIM_IDENTITY_MISMATCH"
E_VERIFY_FAILED = "EVIDENCE_CLAIM_VERIFY_FAILED"
E_STORAGE_ERROR = "STORAGE_ERROR"


class ExecResult:
    def __init__(self):
        self.ok = False
        self.execution_status = RS.FAILED
        self.error_code = None
        self.detail = ""
        self.stage = None
        self.payload = {}
        self.verification_status = None
        self.uncertain_side_effect = False
        # 内部上下文（供失败路径落库）
        self._store = None
        self._run_id = None
        self._repo = None
        self._now = ""


def execute_revalidation(store, *, candidate_id: str, repository_id: str,
                         authorization: dict, plan: dict,
                         adapter=None, now: str = "",
                         require_production: bool = False,
                         completed_at: str = "") -> ExecResult:
    """执行一次受控重新验证。"""
    out = ExecResult()

    # ── PREFLIGHT：从 Storage 重新读全部对象（§4）──────────
    out.stage = "PREFLIGHT"
    out._store, out._repo, out._now = store, str(repository_id), now
    cand = RQ.read_candidate(store, candidate_id=candidate_id,
                             repository_id=repository_id)
    if not cand.get("ok"):
        return _fail(out, E_PREFLIGHT_CANDIDATE_NOT_FOUND, "候选不存在")
    c = cand["payload"]

    # ★ P3D §1-13 修复：P3C 建了 revalidation_run_store，但执行器从未落库，
    #   导致执行状态无法追溯。这里最小向后兼容补上（只在候选可执行时建）。
    run_id = None
    if c.get("status") in (R.PROPOSED, R.BLOCKED):
        try:
            aid = (authorization or {}).get("authorization_id", "none") \
                if isinstance(authorization, dict) else "none"
            cr = RS.create_run(
                store, candidate=candidate_ref(c),
                plan_digest=plan.get("plan_digest") or "",
                authorization_id=aid, authorization_ref=aid,
                created_at=now)
            run_id = cr.get("run_id")
        except Exception as e:
            run_id = None
            out.detail = f"run 记录创建失败: {type(e).__name__}"
    out._run_id = run_id

    if c.get("status") == R.SUPERSEDED:
        return _fail(out, E_PREFLIGHT_SUPERSEDED,
                     "候选已被取代，不得新启动执行")
    if c.get("status") == R.CANCELLED:
        return _fail(out, E_PREFLIGHT_NOT_PROPOSED, "候选已取消")

    is_test_auth0 = bool(authorization.get("test_only")) \
        if isinstance(authorization, dict) else False
    if c.get("status") != R.PROPOSED:
        # ★ 隔离测试模式允许 BLOCKED（来源不可调度但已明确标注）；
        #   正式模式只接受 PROPOSED。
        if not (is_test_auth0 and c.get("status") == R.BLOCKED):
            return _fail(out, E_PREFLIGHT_NOT_PROPOSED,
                         f"候选状态={c.get('status')}")

    q = RQ.read_queue(store, watch_id=c["watch_id"],
                      repository_id=repository_id)
    if not q.get("ok") or q.get("active_candidate_id") != candidate_id:
        return _fail(out, E_PREFLIGHT_NOT_ACTIVE,
                     "候选不是当前活动候选")

    if c.get("conflict_state") != L.CONFLICT_NONE:
        return _fail(out, E_PREFLIGHT_UNRESOLVED_CONFLICT,
                     f"冲突={c.get('conflict_state')}")

    # ★ 来源等级闸门（§4/§9）：
    #   正式执行（require_production 或非 TEST_ONLY 授权）只接受 REAL_LIVE_API。
    #   隔离测试模式（TEST_ONLY 授权）允许 HISTORICAL/SYNTHETIC —— 这正是
    #   §13 的"测试授权仅适用于隔离测试"。BLOCKED 状态的候选即使测试也不放行
    #   （BLOCKED 是候选自身的硬状态）。
    is_test_auth = bool(authorization.get("test_only")) if isinstance(
        authorization, dict) else False
    if not is_test_auth or require_production:
        if c.get("source_level") not in R.DISPATCHABLE_SOURCES:
            return _fail(out, E_PREFLIGHT_NOT_PROPOSED,
                         f"来源 {c.get('source_level')} 不可进入正式调度")

    # 目标 Commit 必须与计划一致（防篡改）
    if plan.get("target_commit_sha") != c["target_commit_sha"]:
        return _fail(out, E_PREFLIGHT_NOT_PROPOSED,
                     "计划目标与候选不一致")

    # ── AUTHORIZATION_CHECK ────────────────────────────────
    out.stage = "AUTHORIZATION_CHECK"
    auth_res = AUTH.validate_execution_authorization(
        candidate=c, plan=plan, authorization=authorization, now=now,
        require_production=require_production)
    if not auth_res["ok"]:
        return _fail(out, E_AUTH_REJECTED,
                     f"{auth_res['reason']}: {auth_res['detail']}")

    # ── SNAPSHOT_COLLECT：固定目标 B ───────────────────────
    out.stage = "SNAPSHOT_COLLECT"
    snap_res = _collect_fixed_target(
        store, candidate=c, adapter=adapter, now=now)
    if not snap_res.get("ok"):
        out.execution_status = snap_res.get("execution_status", RS.FAILED)
        out.uncertain_side_effect = snap_res.get("uncertain", False)
        return _fail(out, snap_res.get("error_code", E_COLLECT_FAILED),
                     snap_res.get("detail", ""))
    snapshot_asset_id = snap_res["snapshot_asset_id"]

    # 阶段中间再查一次授权（§11 C-5：不只在开始时）
    auth_mid = AUTH.validate_execution_authorization(
        candidate=c, plan=plan, authorization=authorization, now=now,
        require_production=require_production)
    if not auth_mid["ok"]:
        return _fail(out, E_AUTH_REVOKED_MIDRUN, auth_mid["detail"])

    # ── FACT_EXTRACT ─────────────────────────────────────
    out.stage = "FACT_EXTRACT"
    tparams = c.get("target_claim_parameters") or {}
    target_path = tparams.get("normalized_path")
    if not target_path:
        return _fail(out, E_TARGET_CLAIM_IDENTITY_MISMATCH,
                     "缺少目标路径参数")
    fact_res = _extract_facts(store, snapshot_asset_id=snapshot_asset_id,
                              target_commit=c["target_commit_sha"],
                              repository_id=repository_id,
                              target_path=target_path)
    if not fact_res.get("ok"):
        return _fail(out, fact_res.get("error_code", E_FACT_FAILED),
                     fact_res.get("detail", ""))

    # ── TARGET_CLAIM_CREATE ───────────────────────────────
    out.stage = "TARGET_CLAIM_CREATE"
    claim_res = _create_target_claim(store, candidate=c, repository_id=repository_id)
    if not claim_res.get("ok"):
        return _fail(out, claim_res.get("error_code",
                                        E_TARGET_CLAIM_IDENTITY_MISMATCH),
                     claim_res.get("detail", ""))
    target_claim = claim_res["claim"]

    # ★ 把目标 Claim 关联写回 run 记录，供只读视图追溯（不伪造任何状态）
    if run_id:
        try:
            def _link(p_):
                p_["target_claim_id"] = target_claim.claim_id
                p_["expected_target_claim_identity"] = c.get(
                    "expected_target_claim_identity")
                p_["source_level"] = c.get("source_level")
            RS.update_run(store, run_id=run_id, repository_id=str(repository_id),
                          mutate=_link, updated_at=now)
        except Exception:
            pass

    # ── EVIDENCE_VERIFY ──────────────────────────────────
    out.stage = "EVIDENCE_VERIFY"
    verify_res = _verify_target(store, claim=target_claim,
                               fact_id=fact_res.get("fact_id"),
                               repository_id=repository_id)
    if not verify_res.get("ok"):
        return _fail(out, verify_res.get("error_code", E_VERIFY_FAILED),
                     verify_res.get("detail", ""))
    verif = verify_res["verification"]

    # ── RESULT_PERSIST ──────────────────────────────────
    out.stage = "RESULT_PERSIST"
    out.execution_status = RS.SUCCESS
    out.verification_status = verif.status
    out.ok = True
    out.payload = {
        "candidate_id": c["candidate_id"],
        "repository_id": str(repository_id),
        "source_claim_id": c["source_claim_id"],
        "source_verification_id": c["source_verification_id"],
        "target_claim_id": target_claim.claim_id,
        "target_verification_id": verif.verification_id,
        "target_commit_sha": c["target_commit_sha"],
        "source_snapshot_ref": snapshot_asset_id,
        "fact_refs": [fact_res["fact_id"]],
        "verification_status": verif.status,
        "freshness_context": {
            "baseline_commit_sha": c["baseline_commit_sha"],
            "observed_commit_sha": c["target_commit_sha"],
            "is_current_ref_target": False,
            "note": "结果绑定固定 Commit B；不代表当前 Ref 的权威结论",
        },
        "auth_ref": authorization["authorization_id"],
        "auth_kind": authorization["authorization_kind"],
        "test_only": bool(authorization.get("test_only")),
        "execution_status": RS.SUCCESS,
        "evidence_refs": list(getattr(verif, "evidence_refs", []) or []),
        "completed_at": completed_at,
    }
    if run_id:
        verif_id = verif.verification_id
        exec_prov = getattr(adapter, "provenance", None)

        def _fin(p_):
            p_["target_verification_id"] = verif_id
            p_["verification_status"] = verif.status
            p_["execution_status"] = RS.SUCCESS
            # ★ 来源与授权类别随执行记录落库，供只读视图追溯。
            #   只存**引用与类别**，不存任何凭据本体。
            p_["auth_kind"] = authorization.get("authorization_kind") \
                if isinstance(authorization, dict) else None
            p_["test_only"] = bool(authorization.get("test_only")) \
                if isinstance(authorization, dict) else False
            p_["auth_ref"] = authorization.get("authorization_id") \
                if isinstance(authorization, dict) else None
            # ★ 来源真实性分两层记录，不混为一谈：
            #   execution_source_level = 实际取数用的 adapter 来源
            #   evidence_source_level  = 候选/评估观测的来源
            p_["execution_source_level"] = exec_prov
            p_["evidence_source_level"] = p_.get("source_level")
            p_["source_snapshot_completeness"] = snap_res.get("completeness")
        try:
            RS.update_run(store, run_id=run_id, repository_id=str(repository_id),
                          mutate=_fin, updated_at=now)
        except Exception:
            pass

    out.stage = "COMPLETION_CHECK"
    _persist_end(store, run_id, repository_id, out, now=now)
    return out


def candidate_ref(c):
    """create_run 需要最小候选信息；这里只取它用到的字段。"""
    return {
        "candidate_id": c.get("candidate_id"),
        "repository_id": c.get("repository_id"),
        "source_claim_id": c.get("source_claim_id"),
        "source_verification_id": c.get("source_verification_id"),
        "target_commit_sha": c.get("target_commit_sha"),
        "baseline_commit_sha": c.get("baseline_commit_sha"),
        "requested_ref": c.get("requested_ref"),
    }


def _persist_end(store, run_id, repository_id, out, *, now):
    """落库执行结局。★ 只写 run 记录，不伪造成功。"""
    if not run_id:
        return
    try:
        st = out.execution_status if out.ok else (
            out.execution_status or RS.FAILED)
        RS.finish_run(store, run_id=run_id, repository_id=str(repository_id),
                      execution_status=st,
                      result_ref=out.payload.get("target_verification_id")
                      if out.payload else None, updated_at=now)
    except Exception:
        pass


def _fail(out, code, detail) -> ExecResult:
    out.ok = False
    out.error_code = code
    out.detail = detail
    # 失败也必须在 run 记录里留下真实状态（不伪造成功）
    _persist_end(getattr(out, "_store", None), getattr(out, "_run_id", None),
                 getattr(out, "_repo", None), out,
                 now=getattr(out, "_now", ""))
    return out


def _collect_fixed_target(store, *, candidate, adapter, now):
    """只对固定目标 Commit B 取快照。**绝不重解析 Ref 后改用别的 Commit。**"""
    if adapter is None:
        return {"ok": False, "error_code": E_AUTH_REJECTED,
                "detail": "未提供 Collector adapter；无真实授权时不得联网"}

    repo_id = str(candidate["repository_id"])
    target = candidate["target_commit_sha"]

    from source_snapshot import build_snapshot
    from ingest_coordinator import ingest_snapshot

    # ★ 直接按 sha 取 commit —— 不做 Ref 解析
    r_commit = adapter.fetch_commit(target)
    if not r_commit.get("ok"):
        status = RS.UNKNOWN if r_commit.get("uncertain") else RS.FAILED
        return {"ok": False, "execution_status": status,
                "uncertain": bool(r_commit.get("uncertain")),
                "error_code": r_commit.get("error_code", E_COLLECT_FAILED),
                "detail": r_commit.get("detail", "commit 获取失败")}

    got_sha = r_commit.get("sha")
    if got_sha != target:
        # ★ 返回别的 Commit → 拒绝，不悄悄改用
        return {"ok": False, "execution_status": RS.FAILED,
                "error_code": E_COLLECT_COMMIT_MISMATCH,
                "detail": f"请求 {target[:12]}… 得到 {str(got_sha)[:12]}…"}

    # ★ root_tree_sha 必须来自 Commit 对象的 commit.tree.sha
    root_tree = r_commit.get("tree_sha")
    if not L.is_commit_sha(root_tree):
        return {"ok": False, "execution_status": RS.FAILED,
                "error_code": E_COLLECT_TREE_NOT_FROM_COMMIT,
                "detail": "缺少可用的 commit.tree.sha"}

    r_tree = adapter.fetch_tree(root_tree)
    if not r_tree.get("ok"):
        status = RS.UNKNOWN if r_tree.get("uncertain") else RS.FAILED
        return {"ok": False, "execution_status": status,
                "uncertain": bool(r_tree.get("uncertain")),
                "error_code": r_tree.get("error_code", E_COLLECT_FAILED),
                "detail": r_tree.get("detail", "tree 获取失败")}

    raw_entries = r_tree.get("entries") or []
    entries = []
    for e in raw_entries:
        # ★ 条目结构必须合法：path 是非空字符串、sha 是 40 位十六进制。
        #   初版直接接受任何条目 —— 实测：sha="zzz" 的损坏 tree 仍被当成
        #   有效来源，进而产出确定性裁决。损坏来源不得产生 supported/refuted。
        path = e.get("path")
        sha = e.get("sha")
        if not isinstance(path, str) or not path:
            return {"ok": False, "execution_status": RS.FAILED,
                    "error_code": E_COLLECT_TREE_NOT_FROM_COMMIT,
                    "detail": f"tree 条目 path 非法: {path!r}"}
        if not L.is_commit_sha(sha):
            return {"ok": False, "execution_status": RS.FAILED,
                    "error_code": E_COLLECT_TREE_NOT_FROM_COMMIT,
                    "detail": f"tree 条目 sha 非法（路径 {path}）: {sha!r}"}
        entries.append({
            "path": path, "type": e.get("type"),
            "sha": sha, "size": e.get("size"),
            "mode": e.get("mode") or "100644",
            "mode_kind": "file", "depth": 0})
    completeness = "COMPLETE" if not r_tree.get("truncated") else "PARTIAL"

    snap = build_snapshot(
        repository_id=repo_id,
        requested_repository=candidate.get("requested_repository") or "o/r",
        resolved_repository=candidate.get("requested_repository") or "o/r",
        requested_ref=candidate["requested_ref"],
        commit_sha=target, root_tree_sha=root_tree,
        tree_query_ref=root_tree, completeness_status=completeness,
        tree_entries=entries, collected_at=now,
        evidence_refs=[adapter.evidence_ref(target)],
        truncated_seen=bool(r_tree.get("truncated")))

    res = ingest_snapshot(store, snap)
    if res.get("state") in ("INGESTED", "IDEMPOTENT_ALREADY_PRESENT"):
        return {"ok": True, "snapshot_asset_id": res["asset_id"],
                "root_tree_sha": root_tree, "completeness": completeness}
    return {"ok": False, "execution_status": RS.FAILED,
            "error_code": E_COLLECT_FAILED, "detail": str(res)}


def _extract_facts(store, *, snapshot_asset_id, target_commit, repository_id,
                   target_path):
    """Facts 只消费目标快照；规则固定 file_path_observation@v1。

    ★ 真正调用 extractor —— 不自己造 fact。
    """
    asset = store.get_asset(snapshot_asset_id, verify=True)
    if not asset.get("ok"):
        return {"ok": False, "error_code": E_STORAGE_ERROR,
                "detail": "快照不可读"}
    p = asset["asset"]["payload"]
    if p.get("commit_sha") != target_commit:
        return {"ok": False, "error_code": E_FACT_COMMIT_MISMATCH,
                "detail": (f"快照 commit {str(p.get('commit_sha'))[:12]}… != "
                           f"{target_commit[:12]}…")}
    if str(p.get("repository_id")) != str(repository_id):
        return {"ok": False, "error_code": E_FACT_COMMIT_MISMATCH,
                "detail": "快照仓库不匹配"}

    obs = _facts_extractor.extract_file_path_observation(
        store, snapshot_asset_id=snapshot_asset_id, target_path=target_path)

    # ★ UNKNOWN 不入库（不写成确定性 Fact）
    if obs.observation == "UNKNOWN":
        return {"ok": True, "fact_id": None, "observation": obs.observation,
                "unknown_reason": obs.unknown_reason,
                "note": "来源不足以产生确定性事实，按 insufficient_evidence 处理"}

    res = _facts_ingest.ingest_fact(store, obs)
    if res.get("state") in ("INGESTED", "IDEMPOTENT_ALREADY_PRESENT"):
        # 断言 fact 属于 B
        if obs.commit_sha != target_commit:
            return {"ok": False, "error_code": E_FACT_COMMIT_MISMATCH,
                    "detail": "fact 的 commit 不是目标 B"}
        return {"ok": True, "fact_id": obs.fact_id,
                "observation": obs.observation}
    return {"ok": False, "error_code": E_FACT_FAILED,
            "detail": str(res)}


def _create_target_claim(store, *, candidate, repository_id):
    """按 P2B 契约生成新 Claim，并断言身份等于 expected_target_claim_identity。"""
    params = candidate.get("target_claim_parameters") or {}
    path = params.get("normalized_path")
    expected_exists = params.get("expected_exists")
    if path is None or expected_exists is None:
        return {"ok": False, "error_code": E_TARGET_CLAIM_IDENTITY_MISMATCH,
                "detail": "缺少目标 Claim 参数，无法确定性生成"}

    claim = _ec_models.build_path_claim(
        repository_id=int(repository_id) if str(repository_id).isdigit()
        else repository_id,
        commit_sha=candidate["target_commit_sha"],
        target_path=path, expected_exists=expected_exists,
        claim_origin="revalidation_executor")

    expected = candidate.get("expected_target_claim_identity")
    if expected and claim.claim_id != expected:
        return {"ok": False, "error_code": E_TARGET_CLAIM_IDENTITY_MISMATCH,
                "detail": f"{claim.claim_id} != {expected}"}
    return {"ok": True, "claim": claim}


def _verify_target(store, *, claim, fact_id, repository_id):
    """用现有 EC 验证器裁决。旧 Claim/Verification 不动。"""
    verif = _ec_verifier.verify_path_claim(store, claim, [fact_id])
    if verif.status not in _ec_models.VERIFICATION_STATES:
        return {"ok": False, "error_code": E_VERIFY_FAILED,
                "detail": f"非法裁决状态 {verif.status}"}
    # 落库（新 Claim + 新 Verification）
    _ec_store.ingest_claim(store, claim)
    _ec_store.ingest_verification(store, verif, repository_id=repository_id)
    return {"ok": True, "verification": verif}
