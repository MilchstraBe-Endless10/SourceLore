#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 Facts 包取纯函数，保持"内容哈希算法只有一份"。"""
import sys
from pathlib import Path

_FACTS = Path(__file__).resolve().parent.parent / "facts"
if str(_FACTS) not in sys.path:
    sys.path.insert(0, str(_FACTS))

from models import make_content_hash  # noqa: E402

FACT_ASSET_TYPE = "extracted_fact"

def fact_content_hash_of(*, observation, observed_value, unknown_reason,
                         commit_sha, completeness_status):
    """与 Facts 入库时同一算法 —— 独立复算用。"""
    return make_content_hash(
        observation=observation, observed_value=observed_value,
        unknown_reason=unknown_reason, commit_sha=commit_sha,
        completeness_status=completeness_status)
