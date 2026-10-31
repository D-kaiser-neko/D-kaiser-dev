#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全局配置 + 日志"""
import os, queue, logging

PORT = 8888
SAVE_DIR = "/storage/emulated/0/termux/MusicDownloads"
THREADS = 8
PAGE_SIZE = 20

# 暮光工具箱接口
MG_SEARCH = "http://119.3.221.4:8002/search"
MG_PLAY   = "http://nmobi.kuwo.cn/mobi.s"
MG_LYRIC  = "http://mlyric.kuwo.cn/mobi.s"
MG_SALT   = "MusicKillerNativeSalt"
MG_SOURCE = "kwplayerhd_ar_6.6.6.6_tianbao_T1A_qirui.apk"

# flac.music.hi.cn 备用
HI_COOKIE_FILE = "/storage/emulated/0/termux/音乐Cookie.txt"
HI_SEARCH      = "https://flac.music.hi.cn/ajax.php?act=search"
HI_GETURL      = "https://flac.music.hi.cn/ajax.php?act=getUrl"
HI_LYRIC_ACTS  = ["lyric", "lrc", "getLyric", "getLrc"]
HI_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36",
    "Referer": "https://flac.music.hi.cn/",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Cookie": ""
}

# 目录初始化
try:
    os.makedirs(SAVE_DIR, exist_ok=True)
except Exception:
    SAVE_DIR = "./MusicDownloads"
    os.makedirs(SAVE_DIR, exist_ok=True)

# 日志系统
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s', datefmt='%H:%M:%S')
log_queue = queue.Queue(maxsize=1000)

class _QH(logging.Handler):
    def emit(self, r):
        try:
            if log_queue.full():
                log_queue.get_nowait()
            log_queue.put(self.format(r))
        except Exception:
            pass

logging.getLogger().addHandler(_QH())

def log(m):
    logging.info(m)