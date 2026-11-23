#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SourceLore 统一身份与证据准入（P0 trust contract）。

本包提供**唯一**一套可信性判定逻辑，供以下环节共同调用：
  Asset Ingest / Index Rebuild / Current View / Knowledge Query /
  Evidence Resolver / Claim Verifier / Derived Views。

设计铁律：
  1. A 层不可变；本包只读 A 层，所有结论作用于 C 索引、B 指针与查询结果。
  2. 身份 = (repository_id, commit_sha, source_snapshot, logical_identity,
             asset_version, provenance)。任何一项冲突即拒绝，不靠文件名或
             symbol_name 合并跨仓库数据。
  3. Commit 真实性分级：格式合法 ≠ 已绑定仓库 ≠ 有经核验快照。
  4. 当前查询默认只认 B 层 current_view 采纳的资产；历史版本只能显式查询。
  5. 证据准入：verdict 原始状态与"当前可采信 finding"是两件事；证据链不完整
     必须降级，且不创造新 reason_code。
"""
