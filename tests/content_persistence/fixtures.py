"""原创 Git 夹具（AUTHORIZED_LOCAL_FIXTURE）。真实 Git OID 与字节。"""
import json, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"content_persistence"))
import sfx
import blob_fetcher as BF

REPO = "990001"
COMMIT_A = "a"*40
COMMIT_B = "b"*40

README_A = b"""# Demo Project

Intro line.

## Installation

```bash
npm install demo
```

## Usage

Read the docs.
"""

README_B = b"""# Demo Project

Intro line.

## Setup

Different section.
"""

PKG = json.dumps({"name": "demo", "version": "1.0.0",
                  "dependencies": {"lodash": "^4.17.0", "axios": "~1.6.0"}},
                 indent=2).encode("utf-8")

PYPROJECT = b"""[project]
name = "demo"
version = "0.2.0"
dependencies = ["click>=8"]
"""

def oid(raw):
    return BF.git_blob_oid(raw)
