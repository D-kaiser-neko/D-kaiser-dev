#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D-kaiser Music Web Console — 启动入口
用法: python main.py
访问: http://localhost:8888
"""
import sys, hashlib
from http.server import ThreadingHTTPServer
from config import PORT, MG_SALT, MG_SEARCH, MG_PLAY, MG_LYRIC, HI_HEADERS, log
from core.kuwo_hi_api import hi_load_cookie
from server.http_handler import Handler


def main():
    ck = hi_load_cookie()
    if ck:
        HI_HEADERS["Cookie"] = ck
        log("[✅] Cookie 已加载")
    else:
        log("[⚠️] 未找到Cookie (仅酷我聚合源需要)")

    test_ts = "1792859066146"
    test_sign = hashlib.md5(f"{MG_SALT}{test_ts}1".encode()).hexdigest()
    expected = "6c8bc9ad59b1cbb100a2e2e72b965eac"
    log(f"[*] 签名验证: {'✅ 通过' if test_sign == expected else '❌ 失败'} ({test_sign})")
    log(f"[*] 盐值: {MG_SALT}")
    log(f"[*] 搜索: {MG_SEARCH}")
    log(f"[*] 播放: {MG_PLAY} (nmobi.kuwo.cn)")
    log(f"[*] 歌词: {MG_LYRIC} (Base64)")
    log(f"[🚀] D-kaiser Music: http://localhost:{PORT}")

    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    srv.daemon_threads = True
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        log("\n👋 已停止")


if __name__ == "__main__":
    main()