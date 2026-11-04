#!/usr/bin/env python3
"""确定性 echo 工具：输入 token → 固定输出。用于验证「真实调用 vs 模型模拟」。"""
import json, sys, hashlib, os

def main():
    token = sys.argv[1] if len(sys.argv) > 1 else ""
    # 固定运算：sha256 前 12 位。模型无法凭空知道正确值，除非真跑了工具
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]
    print(json.dumps({
        "tool": "echo_tool",
        "input": token,
        "input_len": len(token),
        "sha256_12": digest,
        "pid": os.getpid(),
        "cwd": os.getcwd(),
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
