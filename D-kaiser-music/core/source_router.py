#!/usr/bin/env python3
"""统一音源路由 + 搜索缓存"""
from core.muguang_api import mg_search, mg_play_url, mg_lyrics
from core.kuwo_hi_api import hi_search, hi_play_url, hi_lyrics

_cache = []


def search_music(kw, src="muguang", pg=1):
    global _cache
    if src == "muguang":
        songs, tot = mg_search(kw, pg)
    else:
        songs, tot = hi_search(kw, pg)
    if pg == 1:
        _cache = songs
    else:
        _cache.extend(songs)
    return songs, tot


def get_play_url(song, src="muguang", low=False, quality=None):
    if song.get("source_tag") == "muguang" or src == "muguang":
        rid = song.get("id")
        if quality:
            return mg_play_url(rid, quality)
        if low:
            return mg_play_url(rid, "128")
        return mg_play_url(rid, "flac" if song.get("hasLossless") else "320")
    return hi_play_url(song, low)


def get_lyrics(song, src="muguang"):
    if song.get("source_tag") == "muguang" or src == "muguang":
        return mg_lyrics(song.get("id"))
    return hi_lyrics(song)