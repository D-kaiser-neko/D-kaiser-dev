#!/usr/bin/env python3
"""flac.music.hi.cn 备用源"""
import os, urllib.parse
import requests
from config import (HI_COOKIE_FILE, HI_SEARCH, HI_GETURL, HI_LYRIC_ACTS,
                    HI_HEADERS, log)
from core.lrc_parser import format_lrc


def hi_load_cookie():
    if os.path.exists(HI_COOKIE_FILE):
        try:
            with open(HI_COOKIE_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            return ""
    return ""


def hi_save_cookie(c):
    try:
        os.makedirs(os.path.dirname(HI_COOKIE_FILE), exist_ok=True)
        with open(HI_COOKIE_FILE, "w", encoding="utf-8") as f:
            f.write(c.strip())
    except Exception:
        pass


def hi_set_cookie(c):
    HI_HEADERS["Cookie"] = c
    hi_save_cookie(c)


def hi_post(url, payload):
    clean = {k: str(v).replace('\u3000', ' ').replace('\u200b', '').strip()
             for k, v in payload.items() if v is not None}
    try:
        res = requests.post(url, data=urllib.parse.urlencode(clean).encode(),
                            headers=HI_HEADERS, timeout=15)
        if res.status_code == 468 or "challenge" in res.text.lower():
            log("[⚠️ WAF拦截] 请在网页更新Cookie")
            return None
        return res
    except Exception:
        return None


def hi_search(keyword, page=1):
    try:
        res = hi_post(HI_SEARCH, {"keyword": keyword, "type": "kuwo", "page": str(page)})
        if not res or res.status_code != 200:
            return [], 0
        j = res.json()
        if j.get("code") != 0:
            return [], 0
        return j.get("data", {}).get("list", []), 0
    except Exception:
        return [], 0


def hi_play_url(song, low=False):
    minfo = song.get("minfo", [])
    fmt, br = "flac", "2000"
    if low:
        fmt, br = None, None
        for want in ("128", "320"):
            for m in minfo:
                if m.get("format") == "mp3" and str(m.get("bitrate")) == want:
                    fmt, br = "mp3", want
                    break
            if fmt:
                break
        if not fmt:
            for m in minfo:
                if m.get("format") == "mp3":
                    fmt, br = "mp3", str(m.get("bitrate"))
                    break
            else:
                return None, None
    else:
        if not any(m.get("format") == "flac" for m in minfo):
            if minfo:
                fmt, br = minfo[0].get("format", "mp3"), minfo[0].get("bitrate", "320")
            else:
                return None, None
    payload = {
        "platform": "kuwo", "songid": str(song.get("id")),
        "format": fmt, "bitrate": str(br),
        "time": str(song.get("time")), "sign": song.get("sign")
    }
    try:
        res = hi_post(HI_GETURL, payload)
        if res and res.status_code == 200:
            j = res.json()
            if j.get("code") == 0:
                d = j.get("data")
                if isinstance(d, str):
                    return d or None, fmt
                if isinstance(d, dict):
                    return d.get("url"), fmt
        return None, None
    except Exception:
        return None, None


def hi_lyrics(song):
    payload = {
        "platform": "kuwo", "songid": str(song.get("id")),
        "time": str(song.get("time")), "sign": song.get("sign")
    }
    for act in HI_LYRIC_ACTS:
        try:
            res = hi_post(f"https://flac.music.hi.cn/ajax.php?act={act}", payload)
            if not res or res.status_code != 200 or not res.text.strip():
                continue
            lrc = None
            try:
                j = res.json()
                if j.get("code") == 0:
                    d = j.get("data")
                    if isinstance(d, str):
                        lrc = d
                    elif isinstance(d, dict):
                        lrc = d.get("lyric") or d.get("lrc") or d.get("content")
            except ValueError:
                lrc = res.text
            if lrc and isinstance(lrc, str) and not lrc.strip().startswith('{') and '[' in lrc:
                return format_lrc(lrc)
        except Exception:
            continue
    return None