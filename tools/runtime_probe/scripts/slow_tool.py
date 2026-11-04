#!/usr/bin/env python3
"""受控慢工具：用于超时/取消探测。"""
import json, sys, time
secs = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0
time.sleep(secs)
print(json.dumps({"tool": "slow_tool", "slept": secs, "completed": True}))
