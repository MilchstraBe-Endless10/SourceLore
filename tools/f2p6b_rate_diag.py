#!/usr/bin/env python3
"""F2-P6B GitHub 限流诊断：单请求、读完整响应头、不重试。

★ 不打印任何 token；只报请求是否携带身份（布尔）。
★ 仅一次请求，不做探测循环。
"""
import json, sys, urllib.error, urllib.request
from datetime import datetime, timezone

URL = "https://api.github.com/rate_limit"
HEADERS = {"User-Agent": "SourceLore-P6B-rate-diag",
           "Accept": "application/vnd.github+json"}
HDR_KEYS = ("X-RateLimit-Limit", "X-RateLimit-Remaining",
            "X-RateLimit-Reset", "X-RateLimit-Resource",
            "X-RateLimit-Used", "Retry-After", "X-GitHub-Request-Id")


def main():
    req = urllib.request.Request(URL, headers=HEADERS)
    out = {"requested_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "url": URL, "authenticated": False}
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            out["status"] = r.status
            hdrs = dict(r.headers)
            body = r.read(4096).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        out["status"] = e.code
        hdrs = dict(e.headers)
        body = (e.read(4096) or b"").decode("utf-8", "replace")
    except Exception as e:
        out["status"] = None
        out["transport_error"] = f"{type(e).__name__}: {e}"
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 2

    out["headers"] = {k: hdrs.get(k) for k in HDR_KEYS if hdrs.get(k)}
    reset = hdrs.get("X-RateLimit-Reset")
    if reset and reset.isdigit():
        dt = datetime.fromtimestamp(int(reset), tz=timezone.utc)
        out["reset_at_utc"] = dt.isoformat(timespec="seconds")
        out["seconds_until_reset"] = max(0, int(int(reset)
                                                - datetime.now(timezone.utc).timestamp()))
    try:
        parsed = json.loads(body)
        if "message" in parsed:
            out["message"] = parsed["message"]
        if "resources" in parsed:
            out["resources"] = {k: {"limit": v.get("limit"),
                                    "remaining": v.get("remaining"),
                                    "reset": v.get("reset")}
                                for k, v in parsed["resources"].items()}
    except Exception:
        out["body_head"] = body[:200]
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
