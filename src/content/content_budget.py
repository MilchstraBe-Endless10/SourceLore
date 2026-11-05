#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""内容采集预算：第一版安全上限，可测可调，但不许无限读。"""

from dataclasses import dataclass

@dataclass(frozen=True)
class Budget:
    max_blob_bytes: int = 256 * 1024          # 256 KiB
    max_batch_bytes: int = 2 * 1024 * 1024    # 2 MiB
    max_paths: int = 32
    max_facts_per_file: int = 100
    max_line_len: int = 8192                  # 极长单行保护

DEFAULT = Budget()


class BudgetError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class BatchBudget:
    """★ 批级累加器：单 blob 与总量都要守。"""

    def __init__(self, budget: Budget = DEFAULT):
        self.b = budget
        self.used_bytes = 0
        self.paths_seen = 0

    def admit_path(self):
        if self.paths_seen >= self.b.max_paths:
            raise BudgetError("BATCH_PATH_LIMIT",
                              f"单次候选路径超过 {self.b.max_paths}")
        self.paths_seen += 1

    def check_blob(self, size: int):
        if size > self.b.max_blob_bytes:
            raise BudgetError("BLOB_TOO_LARGE",
                              f"Blob {size} > {self.b.max_blob_bytes}")
        if self.used_bytes + size > self.b.max_batch_bytes:
            raise BudgetError("BATCH_BYTE_LIMIT",
                              f"批次累计将超过 {self.b.max_batch_bytes}")
        self.used_bytes += size

    def remaining(self) -> int:
        return self.b.max_batch_bytes - self.used_bytes
