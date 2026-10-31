#!/usr/bin/env python3
"""下载任务队列管理器"""
import os, re, time, threading
from concurrent.futures import ThreadPoolExecutor
from config import SAVE_DIR, log
from core.source_router import get_play_url, get_lyrics
from core.downloader import download_file
from core.cover import download_cover
from core.metadata import HAS_MUTAGEN, embed_metadata


class DownloadManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.pending = []
        self.completed = []
        self.executor = ThreadPoolExecutor(max_workers=2)
        self._id = 0
        self._keys = set()
        self._cancel = {}

    def add(self, song, src):
        sid = str(song.get("id", ""))
        key = (sid, src)
        with self.lock:
            if key in self._keys:
                return None
            self._keys.add(key)
            self._id += 1
            tid = self._id
            evt = threading.Event()
            self._cancel[tid] = evt
            self.pending.append({
                "id": tid, "key": key,
                "name": song.get("name", "?"),
                "artist": song.get("artist", "?"),
                "status": "等待中"
            })
        self.executor.submit(self._work, tid, key, evt, song, src)
        return tid

    def _work(self, tid, key, evt, song, src):
        name = song.get("name", "?")
        artist = song.get("artist", "?")
        sn = re.sub(r'[\\/*?:"<>|]', "", f"{artist} - {name}")
        base = os.path.join(SAVE_DIR, sn)
        with self.lock:
            for t in self.pending:
                if t["id"] == tid:
                    t["status"] = "下载中"
                    break
        if evt.is_set():
            self._fin(tid, key, name, artist, None, "已取消")
            return
        log(f"🎵 {name} - {artist}")
        download_cover(song.get("pic_url", ""), base)
        if evt.is_set():
            self._fin(tid, key, name, artist, None, "已取消")
            return
        url, fmt = get_play_url(song, src)
        if not url:
            for q in ("320", "128"):
                url, fmt = get_play_url(song, src, quality=q)
                if url:
                    break
        if not url:
            log(f"[-] 无链接: {name}")
            self._fin(tid, key, name, artist, None, "无链接")
            return
        ext = ".flac" if fmt == "flac" else ".mp3"
        ap = f"{base}{ext}"
        if not download_file(url, ap):
            self._fin(tid, key, name, artist, None, "下载失败")
            return
        log(f"[✅] {sn}{ext}")
        if evt.is_set():
            if os.path.exists(ap):
                try:
                    os.remove(ap)
                except OSError:
                    pass
            self._fin(tid, key, name, artist, None, "已取消")
            return
        lrc = get_lyrics(song, src)
        if lrc:
            with open(f"{base}.lrc", "w", encoding="utf-8") as f:
                f.write(lrc)
        if HAS_MUTAGEN:
            embed_metadata(ap, song, lrc)
        log(f"[🏁] {name}")
        self._fin(tid, key, name, artist, ap, "成功")

    def _fin(self, tid, key, name, artist, path, status):
        with self.lock:
            self._keys.discard(key)
            self._cancel.pop(tid, None)
            self.pending = [t for t in self.pending if t["id"] != tid]
            self.completed.insert(0, {
                "id": tid, "name": name, "artist": artist,
                "path": path, "status": status,
                "time": time.strftime("%H:%M:%S")
            })

    def status(self):
        with self.lock:
            return {
                "pending": list(self.pending),
                "completed": list(self.completed[:50])
            }

    def remove(self, tid):
        with self.lock:
            evt = self._cancel.get(tid)
            if evt:
                evt.set()
            for t in self.pending:
                if t["id"] == tid:
                    self._keys.discard(t.get("key"))
            self.pending = [t for t in self.pending if t["id"] != tid]

    def clear_done(self):
        with self.lock:
            self.completed.clear()


dl_mgr = DownloadManager()