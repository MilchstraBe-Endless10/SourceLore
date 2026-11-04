#!/usr/bin/env python3
"""受控失败工具：非零退出码 + 明确错误。"""
import json, sys
code = int(sys.argv[1]) if len(sys.argv) > 1 else 1
print(json.dumps({"tool": "fail_tool", "intentional": True, "exit_code": code}))
sys.exit(code)
