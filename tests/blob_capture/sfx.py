import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]
for p in ("runtime","storage","collector","facts","evidence_claims","lifecycle",
          "views","renderer","research","skill_interface","content"):
    if str(ROOT/"src"/p) not in sys.path:
        sys.path.insert(0, str(ROOT/"src"/p))

def fake_resp(*, ok=True, data=None, status=200, error_code=None):
    class _E:
        def __init__(s, c): s.error_code = c
    class _R:
        pass
    r = _R(); r.ok = ok; r.data = data; r.status = status
    r.error = _E(error_code) if error_code else None
    return r
