#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SourceLore 执行结果契约。

**这不是 Harness 原生枚举。** 这是 SourceLore 自己的契约，定义在
SL-CAP-0071（执行状态与检查点）之中。

两类错误必须分开，不得混成一个状态：
  执行期状态：SUCCESS / FAILED / TIMEOUT / CANCELLED / UNKNOWN
  存储与授权错误：NOT_FOUND / CONFLICT / PERMISSION_DENIED / CHECKPOINT_CORRUPT

硬规则：
  R-1 超时不能自动证明工具没有执行 —— TIMEOUT 只说明调用方放弃了等待。
  R-2 UNKNOWN 不是 FAILED，也不是 NOT_FOUND —— 它是"无可判定证据"。
  R-3 只要外部副作用可能已发生而回执缺失，就必须记 UNKNOWN，不得擅自重做。
"""

from dataclasses import dataclass, asdict
from typing import Optional


# ── 执行期状态 ──────────────────────────────────────────────
SUCCESS = "SUCCESS"
FAILED = "FAILED"
TIMEOUT = "TIMEOUT"
CANCELLED = "CANCELLED"
UNKNOWN = "UNKNOWN"

EXECUTION_STATES = frozenset({SUCCESS, FAILED, TIMEOUT, CANCELLED, UNKNOWN})

# ── 存储 / 授权错误（与执行状态正交）────────────────────────
NOT_FOUND = "NOT_FOUND"
CONFLICT = "CONFLICT"
PERMISSION_DENIED = "PERMISSION_DENIED"
CHECKPOINT_CORRUPT = "CHECKPOINT_CORRUPT"

STORAGE_ERRORS = frozenset({NOT_FOUND, CONFLICT, PERMISSION_DENIED, CHECKPOINT_CORRUPT})

TERMINAL_EXECUTION = frozenset({SUCCESS, FAILED, TIMEOUT, CANCELLED})
# UNKNOWN 是**非终态**：结果可能已知但回执缺失，需要人工或重新观测才能收敛。

# 副作用可能已发生、但回执缺失 → 只允许 UNKNOWN
SIDE_EFFECT_RISK_STATES = frozenset({TIMEOUT, UNKNOWN})


@dataclass
class ExecutionResult:
    """一次工具/脚本执行的判定结果。

    区分 `state` 与 `error`：
      - 执行期判定放 `state`（EXECUTION_STATES）
      - 存储/授权问题放 `error`（STORAGE_ERRORS）
    两者不得同时填，避免"用执行状态掩盖存储错误"。
    """
    state: str
    exit_code: Optional[int] = None
    detail: str = ""
    side_effect_possible: bool = False
    evidence_ref: Optional[str] = None

    def __post_init__(self):
        if self.state not in EXECUTION_STATES:
            raise ValueError(f"非法执行状态: {self.state!r}（合法: {sorted(EXECUTION_STATES)}）")
        # 只要状态属于"副作用可能已发生"，必须显式标注风险
        if self.state in SIDE_EFFECT_RISK_STATES and not self.side_effect_possible:
            raise ValueError(
                f"{self.state} 必须先声明 side_effect_possible=True —— "
                "否则调用方可能误以为可以安全重做"
            )

    def is_terminal(self) -> bool:
        return self.state in TERMINAL_EXECUTION

    def retry_allowed(self) -> bool:
        """只有确定"没发生副作用"时才允许自动重试。"""
        return self.state in (FAILED, CANCELLED) and not self.side_effect_possible

    def to_dict(self) -> dict:
        return asdict(self)


def from_exit_code(exit_code: int, *, cancelled: bool = False) -> ExecutionResult:
    """把子进程退出码映射为执行状态。

    SIGTERM 取消 → CANCELLED（显式标记，不从退出码猜）。
    SIGKILL（137/-9）**不等于**正常取消，归 UNKNOWN。
    """
    if cancelled:
        return ExecutionResult(state=CANCELLED, exit_code=exit_code,
                               detail="调用方显式取消（SIGTERM）",
                               side_effect_possible=True)
    if exit_code == 0:
        return ExecutionResult(state=SUCCESS, exit_code=0)
    if exit_code == 124:
        # timeout(1) 的超时退出码
        return ExecutionResult(state=TIMEOUT, exit_code=124,
                               detail="超时终止；不能据此断定工具未执行",
                               side_effect_possible=True)
    if exit_code in (137, -9):
        return ExecutionResult(state=UNKNOWN, exit_code=exit_code,
                               detail="SIGKILL 非正常取消，副作用状态不可判定",
                               side_effect_possible=True)
    if exit_code < 0:
        return ExecutionResult(state=UNKNOWN, exit_code=exit_code,
                               detail=f"被信号 {-exit_code} 终止，状态不可判定",
                               side_effect_possible=True)
    return ExecutionResult(state=FAILED, exit_code=exit_code)


def storage_error(code: str, detail: str = "") -> dict:
    """存储/授权错误统一返回形状。**永不**伪装成执行状态。"""
    if code not in STORAGE_ERRORS:
        raise ValueError(f"非法存储错误码: {code!r}")
    return {"ok": False, "error": code, "detail": detail}
