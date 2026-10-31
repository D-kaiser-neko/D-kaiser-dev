#!/usr/bin/env python3
"""多线程分片下载引擎"""
import os, sys, time, threading
import requests
from concurrent.futures import ThreadPoolExecutor
from config import THREADS, log


class Progress:
    def __init__(self, total, desc="下载"):
        self.total = total
        self.done = 0
        self.desc = desc
        self.lock = threading.Lock()
        self.start = time.time()

    def update(self, n):
        with self.lock:
            self.done += n
            self._draw()

    def _draw(self):
        pct = min(self.done / self.total, 1) if self.total else 0
        w = 24
        filled = int(w * pct)
        bar = '█' * filled + '░' * (w - filled)
        el = max(time.time() - self.start, 0.001)
        sp = self.done / el
        eta = int((self.total - self.done) / sp) if sp > 0 else 0
        sys.stdout.write(
            f"\r{self.desc} [{bar}] {pct*100:5.1f}% "
            f"{self.done//1048576}/{self.total//1048576}MB "
            f"{sp/1048576:.1f}MB/s ETA {eta}s ")
        sys.stdout.flush()

    def close(self):
        sys.stdout.write("\n")
        sys.stdout.flush()


def download_file(url, filepath):
    hd = {"User-Agent": "AndroidDownloadManager/10 (Linux; U; Android 10)"}
    total, rok = 0, False
    try:
        h = requests.head(url, headers=hd, timeout=15, allow_redirects=True)
        total = int(h.headers.get("Content-Length") or 0)
        rok = (h.headers.get("Accept-Ranges", "none") or "").lower() != "none"
    except Exception:
        pass

    if total > 2 * 1048576 and rok:
        log(f"[*] 🚀 {THREADS}线程分片...")
        chunk = max(1048576, (total + THREADS - 1) // THREADS)
        ranges, s = [], 0
        while s < total:
            e = min(total - 1, s + chunk - 1)
            ranges.append((s, e))
            s = e + 1
        parts = [f"{filepath}.part{i}" for i in range(len(ranges))]
        prog = Progress(total)
        ok = True

        def worker(i, s, e):
            nonlocal ok
            h2 = dict(hd)
            h2["Range"] = f"bytes={s}-{e}"
            try:
                r = requests.get(url, headers=h2, stream=True, timeout=30)
                if r.status_code not in (200, 206):
                    ok = False
                    return
                with open(parts[i], "wb") as f:
                    for c in r.iter_content(65536):
                        if c:
                            f.write(c)
                            prog.update(len(c))
            except Exception:
                ok = False

        with ThreadPoolExecutor(max_workers=len(ranges)) as ex:
            futs = [ex.submit(worker, i, s, e) for i, (s, e) in enumerate(ranges)]
            for f in futs:
                try:
                    f.result()
                except Exception:
                    ok = False
        prog.close()
        if not ok:
            for p in parts:
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass
            return False
        tmp = filepath + ".part"
        with open(tmp, "wb") as out:
            for p in parts:
                with open(p, "rb") as fin:
                    while True:
                        b = fin.read(1048576)
                        if not b:
                            break
                        out.write(b)
                os.remove(p)
        os.replace(tmp, filepath)
        return True

    log("[*] 🐢 单线程...")
    prog = None
    try:
        with requests.get(url, headers=hd, stream=True, timeout=30) as r:
            r.raise_for_status()
            t = int(r.headers.get("Content-Length") or 0)
            if t:
                prog = Progress(t)
            with open(filepath, "wb") as f:
                for c in r.iter_content(65536):
                    if c:
                        f.write(c)
                        if prog:
                            prog.update(len(c))
        if prog:
            prog.close()
        return True
    except Exception as e:
        if prog:
            prog.close()
        log(f"[❌] 下载失败: {e}")
        return False