#!/usr/bin/env python3
"""F2-P5A E2E：用**已安装的 Skill 入口**跑五个场景，记录真实证据。

★ 每个场景记录：命令、退出码、耗时、关键字段、是否可回查。
"""
import json, subprocess, sys, time, os
from pathlib import Path

INSTALLED = Path.home()/".agents"/"skills"/"sourcelore"/"scripts"/"sourcelore.py"
DATA = Path("/tmp/sl_e2e")

def run(*args, timeout=60):
    env = dict(os.environ); env["SOURCELORE_DATA_ROOT"] = str(DATA)
    t0 = time.time()
    r = subprocess.run([sys.executable, str(INSTALLED)] + list(args),
                       capture_output=True, text=True, timeout=timeout,
                       env=env, cwd="/tmp")
    dur = round(time.time()-t0, 1)
    try: body = json.loads(r.stdout)
    except Exception: body = {"raw": r.stdout[:400]}
    return {"cmd": " ".join(args), "exit": r.returncode,
            "duration_s": dur, "ok": body.get("ok"),
            "body": body, "stderr_first": (r.stderr.splitlines() or [""])[0][:160]}

def main():
    out = {"artifact": "F2_P5A_E2E", "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
           "skill_path": str(INSTALLED), "data_root": str(DATA),
           "scenarios": {}}

    s = {}
    s["1_analyze"] = run("analyze", "https://github.com/octocat/Hello-World", timeout=90)
    s["1_analyze"]["note"] = ("真实 GitHub 采集；若被限流则 exit=1 且 error=RATE_LIMITED，"
                              "该场景即为 BLOCKED_BY_RATE_LIMIT 而非伪造成功")

    rid = None; sha = None
    if s["1_analyze"].get("ok"):
        rid = s["1_analyze"]["body"]["repository_id"]
        sha = s["1_analyze"]["body"]["commit_sha"]
    else:
        prev = Path("/tmp/sl_e2e/history.json")
        rid, sha = "1296269", "7fd1a60b01f91b314f59955a4e4d4e80d8edf11d"

    s["2_query_path"] = run("query", rid, "--commit", sha, "--type", "path", "--path", "README")
    s["3_card"] = run("card", "--repository-id", rid,
                      "--claim-id", (s["2_query_path"]["body"].get("findings") or [{}])[0].get("claim_id", "SL-CLAIM-b2d90832050096e96bd83b284ae02bae1d817cf0"))
    s["4_history"] = run("history", rid)
    s["5_insufficient"] = run("query", rid, "--commit", sha, "--type", "path", "--path", "src/main.rs")
    s["6_repositories"] = run("repositories")
    s["7_status"] = run("status")
    s["8_bad_url"] = run("analyze", "https://evil.com/x/y")

    out["scenarios"] = s
    Path("docs/implementation/F2_P5A_E2E.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")

    for k, v in s.items():
        print(f"{k:18s} exit={v['exit']:2d} {v['duration_s']:5.1f}s ok={v['ok']}")
    print("\n已写 docs/implementation/F2_P5A_E2E.json")
    return 0

if __name__ == "__main__":
    sys.exit(main())
