#!/usr/bin/env python3
"""封面下载"""
import os
import requests


def download_cover(pic_url, base):
    if not pic_url or not pic_url.startswith("http"):
        return False
    cp = f"{base}.jpg"
    if os.path.exists(cp) and os.path.getsize(cp) > 1024:
        return True
    try:
        h = {"User-Agent": "okhttp/4.11.0"}
        if "kuwo.cn" in pic_url:
            h["Referer"] = "https://www.kuwo.cn/"
        r = requests.get(pic_url, headers=h, timeout=15, stream=True)
        if r.status_code == 200:
            with open(cp, "wb") as f:
                for c in r.iter_content(8192):
                    f.write(c)
            if os.path.getsize(cp) < 1024:
                os.remove(cp)
                return False
            return True
    except Exception:
        pass
    return False