#!/usr/bin/env python3
"""API 路由处理"""
from config import log
from core import source_router
from core.source_router import search_music, get_play_url, get_lyrics
from core.kuwo_hi_api import hi_set_cookie
from core.muguang_api import mg_play_url
from core.task_manager import dl_mgr


def handle_search(body):
    src = body.get("source", "muguang")
    pg = body.get("page", 1)
    songs, tot = search_music(body.get("keyword", ""), src, pg)
    return {"songs": songs, "total": tot}


def handle_download(body):
    cnt = 0
    for idx in body.get("indices", []):
        if 0 <= idx < len(source_router._cache):
            if dl_mgr.add(source_router._cache[idx],
                          body.get("source", "muguang")) is not None:
                cnt += 1
    return {"ok": True, "count": cnt}


def handle_preview(body):
    idx = body.get("index", 0)
    src = body.get("source", "muguang")
    if 0 <= idx < len(source_router._cache):
        song = source_router._cache[idx]
        if song.get("source_tag") == "muguang" or src == "muguang":
            url, fmt = mg_play_url(song.get("id"), "128")
            if not url:
                url, fmt = mg_play_url(song.get("id"), "320")
        else:
            url, fmt = get_play_url(song, src, low=True)
        return {"url": url, "ext": fmt}
    return {"url": None}


def handle_lyric(body):
    idx = body.get("index", 0)
    src = body.get("source", "muguang")
    if 0 <= idx < len(source_router._cache):
        return {"lrc": get_lyrics(source_router._cache[idx], src)}
    return {"lrc": None}


def handle_cookie(body):
    c = body.get("cookie", "")
    hi_set_cookie(c)
    return {"ok": True}


def handle_dl_remove(body):
    dl_mgr.remove(body.get("id", 0))
    return {"ok": True}


def handle_dl_clear(body):
    dl_mgr.clear_done()
    return {"ok": True}


def handle_dl_status():
    return dl_mgr.status()