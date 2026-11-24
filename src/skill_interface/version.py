#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单一可信版本来源（Single source of truth for SourceLore versioning).

对外语义版本（Semantic Versioning）与内部研发代号分开管理：
  - RELEASE_VERSION：对外发行版本，用于 CLI --version、安装器、Release、Tag、CHANGELOG。
  - DEV_CODENAME：内部研发阶段代号，不再作为对外版本号使用。
  - SKILL_VERSION：向后兼容别名，等于 RELEASE_VERSION（旧调用方仍可读）。

任何文件都不得再硬编码版本号，统一从本模块读取。
"""
from __future__ import annotations

# 对外语义版本（预发布）。正式稳定发行前保持 beta 后缀。
RELEASE_VERSION = "0.1.0-beta.1"

# 对外 Tag / Release 标题使用的带 v 前缀形式。
RELEASE_TAG = "v" + RELEASE_VERSION

# 内部研发阶段代号（历史 f2p5a 阶段），仅用于说明，不作版本号。
DEV_CODENAME = "f2p5a"

# 兼容别名：旧代码读 paths.SKILL_VERSION，值现为对外语义版本。
SKILL_VERSION = RELEASE_VERSION

# 数据库 Schema 兼容性标记（升级/迁移判断用）。
SCHEMA_VERSION = "1"

__all__ = [
    "RELEASE_VERSION",
    "RELEASE_TAG",
    "DEV_CODENAME",
    "SKILL_VERSION",
    "SCHEMA_VERSION",
]
