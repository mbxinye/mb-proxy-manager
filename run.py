#!/usr/bin/env python3
import sys
import io

# Windows 控制台默认 GBK 编码，强制 UTF-8 输出
if sys.platform == "win32":
    # TextIOWrapper 默认全缓冲，导致 print 无输出；line_buffering 让每行末尾自动刷新
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="backslashreplace", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="backslashreplace", line_buffering=True)

from scripts.main import run

if __name__ == "__main__":
    run()
