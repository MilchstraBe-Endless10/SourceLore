import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]
for p in ("runtime","storage","collector","facts","evidence_claims","lifecycle",
          "views","renderer","research","skill_interface","content","content_persistence"):
    if str(ROOT/"src"/p) not in sys.path:
        sys.path.insert(0, str(ROOT/"src"/p))
