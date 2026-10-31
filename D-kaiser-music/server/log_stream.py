#!/usr/bin/env python3
"""SSE 日志推送"""
import time, queue as _queue

PROGRESS_MARKER = "\x01P\x01"


def stream_logs(wfile, lq):
    last = 0
    throttle = 0.25
    try:
        while True:
            try:
                msg = lq.get(timeout=30)
                now = time.time()
                is_prog = PROGRESS_MARKER in msg
                if is_prog and (now - last) < throttle:
                    continue
                last = now
                clean = msg.replace(PROGRESS_MARKER, "").replace("\r", "")
                wfile.write(f"data: {clean}\n\n".encode("utf-8"))
                wfile.flush()
            except _queue.Empty:
                wfile.write(b": keepalive\n\n")
                wfile.flush()
    except (BrokenPipeError, ConnectionResetError):
        pass