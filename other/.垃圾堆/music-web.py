#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
flac.music.hi.cn Web 控制台 (修复版)
修复: 自动切歌起点异常 / SSE标记截断 / 下载去重 / 搜索缓存污染
启动: python music_web.py
访问: http://localhost:8888
"""

import os, re, sys, json, time, threading, urllib.parse, queue, logging
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor
import requests

try:
    from mutagen.flac import FLAC, Picture
    from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC, USLT
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False

PORT = 8888
COOKIE_FILE = "/storage/emulated/0/termux/音乐Cookie.txt"
SAVE_DIR = "/storage/emulated/0/termux/MusicDownloads"
THREADS = 8
LYRIC_ACTS = ["lyric", "lrc", "getLyric", "getLrc"]
PROGRESS_MARKER = "\x01P\x01"  # 修复2: 短标记防SSE分包截断

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s', datefmt='%H:%M:%S')
log_queue = queue.Queue(maxsize=1000)

class QueueHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            if log_queue.full(): log_queue.get_nowait()
            log_queue.put(msg)
        except Exception: pass

qh = QueueHandler()
logging.getLogger().addHandler(qh)
def log(msg): logging.info(msg)

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

os.makedirs(SAVE_DIR, exist_ok=True)

BASE_SEARCH = "https://flac.music.hi.cn/ajax.php?act=search"
BASE_GETURL = "https://flac.music.hi.cn/ajax.php?act=getUrl"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36",
    "Referer": "https://flac.music.hi.cn/",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Cookie": ""
}

# ================= 下载管理器 (修复3: 去重) =================
class DownloadManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.pending = []
        self.completed = []
        self.executor = ThreadPoolExecutor(max_workers=1)
        self._id_counter = 0
        self._active_keys = set()
        self._cancel_events = {}  # task_id -> threading.Event

    def add_task(self, song, source):
        song_id = str(song.get("id", ""))
        key = (song_id, source)
        with self.lock:
            if key in self._active_keys:
                log(f"[⏭] 已在队列中: {song.get('name')}")
                return None
            self._active_keys.add(key)
            self._id_counter += 1
            task_id = self._id_counter
            cancel_evt = threading.Event()
            self._cancel_events[task_id] = cancel_evt
            self.pending.append({
                "id": task_id, "key": key,
                "name": song.get("name", "未知"),
                "artist": song.get("artist", "未知"),
                "status": "等待中"
            })
        self.executor.submit(self._worker, task_id, key, cancel_evt, song, source)
        return task_id

    def _cancelled(self, cancel_evt, task_id, name, step=""):
        """检查是否被取消，是则清理并返回True"""
        if cancel_evt.is_set():
            log(f"[⏹] 任务已取消: {name} ({step})")
            return True
        return False

    def _worker(self, task_id, key, cancel_evt, song, source):
        artist = song.get("artist", "未知"); name = song.get("name", "未知")
        safe_name = re.sub(r'[\\/*?:"<>|]', "", f"{artist} - {name}")
        filepath_base = os.path.join(SAVE_DIR, safe_name)

        with self.lock:
            for t in self.pending:
                if t["id"] == task_id: t["status"] = "下载中"; break

        if self._cancelled(cancel_evt, task_id, name, "开始"): 
            self._finish(task_id, key, name, artist, None, "已取消"); return

        log(f"🎵 开始处理: {name} - {artist}")

        # === 封面 ===
        pic_url = song.get("pic_url")
        if pic_url and pic_url.startswith("http"):
            cover_path = f"{filepath_base}.jpg"
            if not os.path.exists(cover_path) or os.path.getsize(cover_path) < 1024:
                try:
                    h = {"User-Agent": HEADERS["User-Agent"]}
                    if "kuwo.cn" in pic_url: h["Referer"] = "https://www.kuwo.cn/"
                    elif "126.net" in pic_url: h["Referer"] = "https://music.163.com/"
                    elif "qq.com" in pic_url: h["Referer"] = "https://y.qq.com/"
                    r = requests.get(pic_url, headers=h, timeout=15)
                    if r.status_code == 200 and len(r.content) > 1024:
                        with open(cover_path, "wb") as f: f.write(r.content)
                except: pass

        if self._cancelled(cancel_evt, task_id, name, "封面后"): 
            self._finish(task_id, key, name, artist, None, "已取消"); return

        # === 音频URL ===
        audio_url, ext = get_audio_url(song, source)
        if not audio_url:
            log(f"[-] 跳过(无资源): {name}")
            self._finish(task_id, key, name, artist, None, "无资源"); return

        if self._cancelled(cancel_evt, task_id, name, "获取URL后"): 
            self._finish(task_id, key, name, artist, None, "已取消"); return

        # === 下载音频 ===
        audio_path = f"{filepath_base}.{ext}"
        if not download_file_cancellable(audio_url, audio_path, cancel_evt):
            # 清理可能产生的半截文件
            for suffix in [".part", ".tmp"] + [f".part{i}" for i in range(THREADS)]:
                p = audio_path + suffix
                if os.path.exists(p):
                    try: os.remove(p)
                    except: pass
            if cancel_evt.is_set():
                self._finish(task_id, key, name, artist, None, "已取消")
            else:
                self._finish(task_id, key, name, artist, None, "下载失败")
            return

        if self._cancelled(cancel_evt, task_id, name, "下载后"): 
            # 下载完了但被取消，删除已下载的文件
            if os.path.exists(audio_path):
                try: os.remove(audio_path)
                except: pass
            self._finish(task_id, key, name, artist, None, "已取消"); return

        log(f"[✅] 音频已保存: {safe_name}.{ext}")

        # === 歌词 ===
        lrc_text = get_lyrics(song, source)
        if lrc_text:
            with open(f"{filepath_base}.lrc", "w", encoding="utf-8") as f: f.write(lrc_text)

        if self._cancelled(cancel_evt, task_id, name, "歌词后"): 
            self._finish(task_id, key, name, artist, audio_path, "已取消"); return

        # === 元数据 ===
        if HAS_MUTAGEN: embed_metadata(audio_path, song, lrc_text)
        log(f"[🏁] 完成: {name}")
        self._finish(task_id, key, name, artist, audio_path, "成功")

    def _finish(self, task_id, key, name, artist, path, status):
        with self.lock:
            self._active_keys.discard(key)
            self._cancel_events.pop(task_id, None)
            self.pending = [t for t in self.pending if t["id"] != task_id]
            self.completed.insert(0, {
                "id": task_id, "name": name, "artist": artist,
                "path": path, "status": status, "time": time.strftime("%H:%M:%S")
            })

    def get_status(self):
        with self.lock:
            return {"pending": list(self.pending), "completed": list(self.completed[:50])}

    def remove_pending(self, task_id):
        """核心修复: 设置取消信号，而非仅移除列表记录"""
        with self.lock:
            evt = self._cancel_events.get(task_id)
            if evt:
                evt.set()  # 通知后台线程停止
            for t in self.pending:
                if t["id"] == task_id:
                    self._active_keys.discard(t.get("key"))
            self.pending = [t for t in self.pending if t["id"] != task_id]

    def clear_completed(self):
        with self.lock: self.completed.clear()

def download_file_cancellable(url, filepath, cancel_evt):
    """支持取消的下载函数，在每个chunk写入前检查cancel_evt"""
    dl_headers = {k:v for k,v in HEADERS.items() if k != "Content-Type"}
    total, ranges_ok = 0, False
    try:
        head = requests.head(url, headers=dl_headers, timeout=15, allow_redirects=True)
        total = int(head.headers.get("Content-Length") or 0)
        ranges_ok = (head.headers.get("Accept-Ranges", "none") or "").lower() != "none"
    except: pass

    if total > 2*1024*1024 and ranges_ok:
        log(f"[*] 🚀 {THREADS} 线程分片下载...")
        if _multithread_download_cancellable(url, filepath, total, dl_headers, cancel_evt):
            return True
        if cancel_evt.is_set(): return False
        log("[!] 多线程失败, 回退单线程...")
    log("[*] 🐢 单线程下载...")
    return _single_download_cancellable(url, filepath, dl_headers, cancel_evt)


def _multithread_download_cancellable(url, filepath, total, headers, cancel_evt):
    chunk = max(1024*1024, (total + THREADS - 1) // THREADS)
    ranges, start = [], 0
    while start < total:
        end = min(total - 1, start + chunk - 1); ranges.append((start, end)); start = end + 1
    parts = [f"{filepath}.part{i}" for i in range(len(ranges))]
    prog = Progress(total); ok = True

    def worker(i, s, e):
        nonlocal ok
        if cancel_evt.is_set(): ok = False; return
        h = dict(headers); h["Range"] = f"bytes={s}-{e}"
        try:
            r = requests.get(url, headers=h, stream=True, timeout=30)
            if r.status_code not in (200, 206): ok = False; return
            with open(parts[i], "wb") as f:
                for c in r.iter_content(chunk_size=64*1024):
                    if cancel_evt.is_set(): ok = False; return
                    if c: f.write(c); prog.update(len(c))
        except: ok = False

    with ThreadPoolExecutor(max_workers=len(ranges)) as ex:
        futs = [ex.submit(worker, i, s, e) for i, (s, e) in enumerate(ranges)]
        for f in futs:
            try: f.result()
            except: ok = False
    prog.close()

    if cancel_evt.is_set():
        for p in parts:
            if os.path.exists(p):
                try: os.remove(p)
                except: pass
        return False

    if not ok:
        for p in parts:
            if os.path.exists(p):
                try: os.remove(p)
                except: pass
        return False

    tmp = filepath + ".part"
    with open(tmp, "wb") as out:
        for p in parts:
            with open(p, "rb") as fin:
                while True:
                    b = fin.read(1024*1024)
                    if not b: break
                    out.write(b)
            os.remove(p)
    os.replace(tmp, filepath)
    return True


def _single_download_cancellable(url, filepath, headers, cancel_evt):
    prog = None
    try:
        with requests.get(url, headers=headers, stream=True, timeout=30) as r:
            r.raise_for_status(); t = int(r.headers.get("Content-Length") or 0)
            if t: prog = Progress(t)
            with open(filepath, "wb") as f:
                for c in r.iter_content(chunk_size=64*1024):
                    if cancel_evt.is_set():
                        if prog: prog.close()
                        return False
                    if c: f.write(c); (prog and prog.update(len(c)))
        if prog: prog.close()
        return True
    except Exception as e:
        if prog: prog.close()
        if cancel_evt.is_set(): return False
        log(f"[❌] 下载失败: {e}"); return False

# ================= API 逻辑 =================
def load_cookie():
    if os.path.exists(COOKIE_FILE):
        try:
            with open(COOKIE_FILE, "r", encoding="utf-8") as f: return f.read().strip()
        except: return ""
    return ""

def save_cookie(cookie_str):
    try:
        os.makedirs(os.path.dirname(COOKIE_FILE), exist_ok=True)
        with open(COOKIE_FILE, "w", encoding="utf-8") as f: f.write(cookie_str.strip())
        log("[✅] Cookie 已保存")
    except Exception as e: log(f"[❌] 保存 Cookie 失败: {e}")

def safe_post(url, payload):
    global HEADERS
    clean = {k: str(v).replace('\u3000',' ').replace('\u200b','').strip() for k,v in payload.items() if v is not None}
    data = urllib.parse.urlencode(clean).encode('utf-8')
    res = requests.post(url, data=data, headers=HEADERS, timeout=15)
    if res.status_code == 468 or "challenge" in res.text.lower():
        log("[⚠️ WAF 拦截] Cookie 失效，请在网页更新")
        return None
    return res

def search_music(keyword, source="kuwo", page=1):
    payload = {"keyword": keyword, "type": source, "page": str(page)}
    try:
        res = safe_post(BASE_SEARCH, payload)
        if not res or res.status_code != 200: return [], {}
        j = res.json()
        if j.get("code") != 0: return [], {}
        d = j.get("data", {})
        if isinstance(d, list): return d, {}
        return d.get("list", []), d
    except Exception as e:
        log(f"[-] 搜索异常: {e}")
        return [], {}

def get_audio_url(song_data, source="kuwo", low=False):
    minfo = song_data.get("minfo", [])
    if low:
        for want in ("128", "320"):
            for m in minfo:
                if m.get("format") == "mp3" and str(m.get("bitrate")) == want:
                    payload = {"platform": source, "songid": str(song_data.get("id")), "format": "mp3", "bitrate": want, "time": str(song_data.get("time")), "sign": song_data.get("sign")}
                    res = safe_post(BASE_GETURL, payload)
                    if res and res.status_code == 200:
                        d = res.json().get("data")
                        url = d if isinstance(d, str) else (d.get("url") if isinstance(d, dict) else None)
                        if url: return url, "mp3"
        return None, None
    fmt, br = "flac", "2000"
    found = any(m.get("format") == "flac" for m in minfo)
    if not found and minfo:
        fmt = minfo[0].get("format", "mp3")
        br = minfo[0].get("bitrate", "320")
    payload = {"platform": source, "songid": str(song_data.get("id")), "format": fmt, "bitrate": str(br), "time": str(song_data.get("time")), "sign": song_data.get("sign")}
    res = safe_post(BASE_GETURL, payload)
    if res and res.status_code == 200:
        d = res.json().get("data")
        url = d if isinstance(d, str) else (d.get("url") if isinstance(d, dict) else None)
        if url: return url, fmt
    return None, None

def format_lrc(raw):
    if not raw: return ""
    ts_re = re.compile(r'^\[(\d{1,2}:\d{2}(?:\.\d{1,3})?)\]\s*(.*)$')
    lines = []
    for line in raw.splitlines():
        line = line.strip()
        if not line: continue
        m = ts_re.match(line)
        if m:
            ts, text = m.group(1), m.group(2).strip()
            if text: lines.append([ts, text])
        elif line.startswith('['): lines.append([None, line])
        else:
            if lines and lines[-1][0] is not None: lines[-1][1] += line
    has_kana = lambda t: bool(re.search(r'[\u3040-\u30ff]', t))
    has_han = lambda t: bool(re.search(r'[\u4e00-\u9fff]', t))
    for i in range(1, len(lines)-1):
        tp, tc, tn = lines[i-1][0], lines[i][0], lines[i+1][0]
        if tp and tc and tn and tc == tn and tc != tp:
            a, b = lines[i-1][1], lines[i][1]
            if (has_han(b) and not has_kana(b) and has_kana(a)) or (has_kana(b) and has_han(a) and not has_kana(a)):
                lines[i][0] = tp
    return '\n'.join(t if ts is None else f"[{ts}]{t}" for ts, t in lines)

def get_lyrics(song_data, source="kuwo"):
    payload = {"platform": source, "songid": str(song_data.get("id")), "time": str(song_data.get("time")), "sign": song_data.get("sign")}
    for act in LYRIC_ACTS:
        url = f"https://flac.music.hi.cn/ajax.php?act={act}"
        try:
            res = safe_post(url, payload)
            if not res or res.status_code != 200: continue
            lrc = None
            try:
                j = res.json()
                if j.get("code") == 0:
                    d = j.get("data")
                    lrc = d if isinstance(d, str) else (d.get("lyric") or d.get("lrc") or d.get("content"))
            except: lrc = res.text
            if lrc and isinstance(lrc, str) and not lrc.strip().startswith('{') and '[' in lrc:
                return format_lrc(lrc)
        except: continue
    return None

class Progress:
    def __init__(self, total, desc="下载"):
        self.total = total; self.done = 0; self.desc = desc
        self.lock = threading.Lock(); self.start = time.time()
    def update(self, n):
        with self.lock: self.done += n; self._draw()
    def _draw(self):
        pct = min(self.done / self.total, 1) if self.total else 0
        w = 24; filled = int(w * pct); bar = '█' * filled + '░' * (w - filled)
        elapsed = max(time.time() - self.start, 0.001); speed = self.done / elapsed
        eta = int((self.total - self.done) / speed) if speed > 0 else 0
        sys.stdout.write(f"\r{self.desc} [{bar}] {pct*100:5.1f}% {self.done//1048576}/{self.total//1048576}MB {speed/1048576:.1f}MB/s ETA {eta}s ")
        sys.stdout.flush()
        # 修复2: 使用短标记防SSE分包截断
        log(f"{PROGRESS_MARKER}{self.desc} [{bar}] {pct*100:5.1f}% {self.done//1048576}/{self.total//1048576}MB {speed/1048576:.1f}MB/s ETA {eta}s")
    def close(self): sys.stdout.write("\n"); sys.stdout.flush()

def download_file(url, filepath):
    dl_headers = {k:v for k,v in HEADERS.items() if k != "Content-Type"}
    total, ranges_ok = 0, False
    try:
        head = requests.head(url, headers=dl_headers, timeout=15, allow_redirects=True)
        total = int(head.headers.get("Content-Length") or 0)
        ranges_ok = (head.headers.get("Accept-Ranges", "none") or "").lower() != "none"
    except: pass
    if total > 2*1024*1024 and ranges_ok:
        log(f"[*] 🚀 {THREADS} 线程分片下载...")
        if _multithread_download(url, filepath, total, dl_headers): return True
        log("[!] 多线程失败, 回退单线程...")
    log("[*] 🐢 单线程下载...")
    return _single_download(url, filepath, dl_headers)

def _multithread_download(url, filepath, total, headers):
    chunk = max(1024*1024, (total + THREADS - 1) // THREADS)
    ranges, start = [], 0
    while start < total:
        end = min(total - 1, start + chunk - 1); ranges.append((start, end)); start = end + 1
    parts = [f"{filepath}.part{i}" for i in range(len(ranges))]
    prog = Progress(total); ok = True
    def worker(i, s, e):
        nonlocal ok
        h = dict(headers); h["Range"] = f"bytes={s}-{e}"
        try:
            r = requests.get(url, headers=h, stream=True, timeout=30)
            if r.status_code not in (200, 206): ok = False; return
            with open(parts[i], "wb") as f:
                for c in r.iter_content(chunk_size=64*1024):
                    if c: f.write(c); prog.update(len(c))
        except: ok = False
    with ThreadPoolExecutor(max_workers=len(ranges)) as ex:
        futs = [ex.submit(worker, i, s, e) for i, (s, e) in enumerate(ranges)]
        for f in futs:
            try: f.result()
            except: ok = False
    prog.close()
    if not ok:
        for p in parts:
            if os.path.exists(p):
                try: os.remove(p)
                except: pass
        return False
    tmp = filepath + ".part"
    with open(tmp, "wb") as out:
        for p in parts:
            with open(p, "rb") as fin:
                while True:
                    b = fin.read(1024*1024)
                    if not b: break
                    out.write(b)
            os.remove(p)
    os.replace(tmp, filepath)
    return True

def _single_download(url, filepath, headers):
    prog = None
    try:
        with requests.get(url, headers=headers, stream=True, timeout=30) as r:
            r.raise_for_status(); t = int(r.headers.get("Content-Length") or 0)
            if t: prog = Progress(t)
            with open(filepath, "wb") as f:
                for c in r.iter_content(chunk_size=64*1024):
                    if c: f.write(c); (prog and prog.update(len(c)))
        if prog: prog.close()
        return True
    except Exception as e:
        if prog: prog.close()
        log(f"[❌] 下载失败: {e}"); return False

def embed_metadata(audio_path, song_data, lrc_text=None):
    if not HAS_MUTAGEN or not os.path.exists(audio_path): return
    ext = os.path.splitext(audio_path)[1].lower()
    cover_data = None
    cover_path = audio_path.rsplit(".", 1)[0] + ".jpg"
    if os.path.exists(cover_path):
        with open(cover_path, "rb") as f: cover_data = f.read()
    try:
        if ext == ".flac":
            audio = FLAC(audio_path)
            audio["TITLE"] = song_data.get("name", ""); audio["ARTIST"] = song_data.get("artist", "")
            audio["ALBUM"] = song_data.get("album_name", "")
            if lrc_text: audio["LYRICS"] = lrc_text
            if cover_data:
                pic = Picture(); pic.type = 3; pic.mime = "image/jpeg"; pic.data = cover_data
                audio.clear_pictures(); audio.add_picture(pic)
            audio.save()
        elif ext == ".mp3":
            audio = ID3(audio_path) if os.path.getsize(audio_path) > 0 else ID3()
            audio["TIT2"] = TIT2(encoding=3, text=song_data.get("name",""))
            audio["TPE1"] = TPE1(encoding=3, text=song_data.get("artist",""))
            audio["TALB"] = TALB(encoding=3, text=song_data.get("album_name",""))
            if lrc_text: audio["USLT"] = USLT(encoding=3, lang="eng", desc="", text=lrc_text)
            if cover_data: audio["APIC"] = APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=cover_data)
            audio.save()
    except Exception as e: log(f"[-] 元数据嵌入失败: {e}")
dl_manager = DownloadManager()
# ================= Web UI =================
HTML_PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>FLAC Music Console</title>
<style>
:root{--bg:#1a1a2e;--card:#16213e;--primary:#0f3460;--accent:#e94560;--text:#eee;--sub:#aaa;}
*{margin:0;padding:0;box-sizing:border-box;}body{background:var(--bg);color:var(--text);font-family:-apple-system,sans-serif;padding:20px;padding-bottom:90px;}
.header{display:flex;justify-content:space-between;align-items:center;max-width:700px;margin:0 auto 15px;}
.header h1{color:var(--accent);font-size:1.3em;}
.dl-mgr-btn{padding:6px 12px;border:none;border-radius:6px;background:var(--primary);color:#fff;cursor:pointer;font-size:13px;position:relative;}
.dl-mgr-btn .badge{position:absolute;top:-5px;right:-5px;background:var(--accent);color:#fff;font-size:10px;width:16px;height:16px;border-radius:50%;display:flex;align-items:center;justify-content:center;}
.cookie-bar{max-width:700px;margin:0 auto 12px;display:flex;gap:8px;}
.cookie-bar input{flex:1;padding:8px;border:none;border-radius:6px;background:var(--card);color:#fff;font-size:12px;}
.cookie-bar button{padding:8px 12px;border:none;border-radius:6px;background:var(--accent);color:#fff;cursor:pointer;font-size:12px;}
.search-box{display:flex;gap:10px;max-width:700px;margin:0 auto 15px;}
.search-box input,.search-box button{padding:10px 15px;border:none;border-radius:8px;font-size:14px;}
.search-box input{flex:1;background:var(--card);color:#fff;}
.search-box button{background:var(--accent);color:#fff;cursor:pointer;font-weight:bold;}
.actions{max-width:700px;margin:0 auto 10px;display:flex;gap:10px;align-items:center;flex-wrap:wrap;}
.actions button{padding:6px 14px;border:none;border-radius:6px;background:var(--primary);color:#fff;cursor:pointer;font-size:13px;}
.actions button:hover{background:var(--accent);}.actions button:disabled{opacity:.5;cursor:not-allowed;}
.page-info{font-size:12px;color:var(--sub);margin-left:auto;}
.song-list{max-width:700px;margin:0 auto;display:flex;flex-direction:column;gap:8px;}
.song-item{display:flex;align-items:center;gap:12px;background:var(--card);padding:10px 12px;border-radius:10px;transition:.2s;}
.song-item:hover{background:var(--primary);}.song-item input[type=checkbox]{width:18px;height:18px;accent-color:var(--accent);flex-shrink:0;}
.song-cover{width:40px;height:40px;border-radius:6px;object-fit:cover;background:#333;flex-shrink:0;}
.song-info{flex:1;min-width:0;}.song-name{font-weight:bold;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:14px;}
.song-artist{font-size:12px;color:var(--sub);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.tag{font-size:11px;padding:2px 6px;border-radius:4px;margin-left:6px;}
.tag-flac{background:#2ecc71;color:#000;}.tag-mp3{background:#f39c12;color:#000;}
.btn-sm{padding:5px 10px;border:none;border-radius:5px;font-size:12px;cursor:pointer;color:#fff;flex-shrink:0;}
.btn-preview{background:#3498db;}.btn-dl{background:#2ecc71;}
.toast{position:fixed;top:20px;left:50%;transform:translateX(-50%);background:var(--accent);color:#fff;padding:10px 20px;border-radius:8px;font-size:14px;z-index:300;opacity:0;transition:opacity .3s;pointer-events:none;}
.toast.show{opacity:1;}
.dl-panel{position:fixed;top:0;right:-350px;width:340px;height:100%;background:var(--card);z-index:250;transition:right .3s;box-shadow:-5px 0 20px rgba(0,0,0,.5);display:flex;flex-direction:column;}
.dl-panel.active{right:0;}.dl-panel-header{padding:15px;border-bottom:1px solid var(--primary);display:flex;justify-content:space-between;align-items:center;}
.dl-panel-header h3{font-size:16px;}.dl-panel-close{font-size:22px;cursor:pointer;color:var(--sub);}
.dl-panel-body{flex:1;overflow-y:auto;padding:10px;}.dl-section-title{font-size:12px;color:var(--sub);margin:10px 0 5px;text-transform:uppercase;}
.dl-item{display:flex;align-items:center;gap:8px;padding:8px;border-radius:6px;background:rgba(255,255,255,.03);margin-bottom:4px;font-size:12px;}
.dl-item-name{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}.dl-item-status{color:var(--accent);font-size:11px;flex-shrink:0;}
.dl-item-del{color:#e74c3c;cursor:pointer;font-size:14px;flex-shrink:0;padding:0 4px;}
.dl-clear-btn{margin:10px;padding:8px;border:none;border-radius:6px;background:#e74c3c;color:#fff;cursor:pointer;font-size:12px;width:100%;}
.player-bar{position:fixed;bottom:0;left:0;right:0;background:var(--card);border-top:1px solid var(--primary);padding:10px 20px;display:none;align-items:center;gap:12px;z-index:100;cursor:pointer;}
.player-bar.active{display:flex;}.player-bar-cover{width:45px;height:45px;border-radius:6px;object-fit:cover;background:#333;}
.player-bar-info{flex:1;min-width:0;}.player-bar-title{font-size:14px;font-weight:bold;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.player-bar-sub{font-size:12px;color:var(--sub);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.full-player{position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(10,10,20,.97);z-index:200;display:none;flex-direction:column;align-items:center;padding:20px;backdrop-filter:blur(10px);}
.full-player.active{display:flex;}
.fp-close{position:absolute;top:15px;right:20px;font-size:28px;color:var(--sub);cursor:pointer;z-index:201;line-height:1;}
.fp-cover{width:140px;height:140px;border-radius:12px;object-fit:cover;background:#333;margin-top:30px;box-shadow:0 8px 30px rgba(0,0,0,.5);}
.fp-title{text-align:center;margin-top:12px;font-size:17px;font-weight:bold;max-width:90%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.fp-artist{text-align:center;margin-top:4px;font-size:13px;color:var(--sub);}
.fp-lrc-box{flex:1;width:100%;max-width:600px;margin-top:15px;overflow-y:auto;text-align:center;mask-image:linear-gradient(to bottom,transparent 0%,black 15%,black 85%,transparent 100%);-webkit-mask-image:linear-gradient(to bottom,transparent 0%,black 15%,black 85%,transparent 100%);}
.fp-lrc-line{padding:5px 0;font-size:14px;color:var(--sub);transition:all .3s;line-height:1.6;}
.fp-lrc-line.active{color:var(--accent);font-size:16px;font-weight:bold;transform:scale(1.05);}
.fp-audio{width:100%;max-width:500px;margin-top:10px;margin-bottom:15px;height:36px;}
.log-panel{max-width:700px;margin:15px auto 10px;background:var(--card);border-radius:10px;padding:12px;font-family:monospace;font-size:12px;max-height:120px;overflow-y:auto;color:var(--sub);}
.log-progress{color:#2ecc71;font-weight:bold;}
</style></head><body>
<div class="toast" id="toast"></div>
<div class="header"><h1>🎵 FLAC Music Console</h1><button class="dl-mgr-btn" onclick="toggleDlPanel()">📥 下载管理<span class="badge" id="dlBadge" style="display:none">0</span></button></div>
<div class="cookie-bar"><input id="cookieInput" placeholder="粘贴 WAF Cookie"><button onclick="saveCookie()">💾 保存</button></div>
<div class="search-box"><input id="kw" placeholder="输入歌名或歌手..." onkeydown="if(event.key==='Enter')doSearch()"><button onclick="doSearch()">🔍 搜索</button></div>
<div class="actions">
<button onclick="dlSelected()">⬇️ 下载选中</button><button onclick="toggleAll()">☑️ 全选</button>
<button id="prevBtn" onclick="changePage(-1)" disabled>◀ 上一页</button><button id="nextBtn" onclick="changePage(1)" disabled>下一页 ▶</button>
<span class="page-info" id="pageInfo"></span>
</div>
<div class="song-list" id="list"></div>
<div class="log-panel" id="logs"></div>
<div class="dl-panel" id="dlPanel"><div class="dl-panel-header"><h3>📥 下载管理</h3><div class="dl-panel-close" onclick="toggleDlPanel()">✕</div></div><div class="dl-panel-body" id="dlPanelBody"></div></div>
<div class="player-bar" id="playerBar" onclick="openFullPlayer()"><img class="player-bar-cover" id="pbCover"><div class="player-bar-info"><div class="player-bar-title" id="pbTitle"></div><div class="player-bar-sub" id="pbSub"></div></div><audio id="audio" preload="auto"></audio></div>
<div class="full-player" id="fullPlayer"><div class="fp-close" onclick="closeFullPlayer()">✕</div><img class="fp-cover" id="fpCover"><div class="fp-title" id="fpTitle"></div><div class="fp-artist" id="fpArtist"></div><div class="fp-lrc-box" id="fpLrcBox"></div><audio class="fp-audio" id="fpAudio" controls preload="auto"></audio></div>
<script>
let songs=[],currentLrcLines=[],currentIdx=-1,curPage=1,curKeyword='',curSource='kuwo';
const audioEl=document.getElementById('audio'),fpAudio=document.getElementById('fpAudio');
const LOG_SYNC_INTERVAL=250;

function showToast(msg){let t=document.getElementById('toast');t.textContent=msg;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2000);}

function doSearch(page=1){
  let kw=document.getElementById('kw').value.trim();
  if(!kw&&page===1)return;
  if(page===1)curKeyword=kw;
  curPage=page;
  document.getElementById('pageInfo').textContent=`第 ${page} 页 · 搜索中...`;
  fetch('/api/search',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({keyword:curKeyword,source:curSource,page:page})})
  .then(r=>r.json()).then(d=>{
    songs=d.songs||[];renderList();
    document.getElementById('pageInfo').textContent=`第 ${page} 页 · ${songs.length} 首`;
    document.getElementById('prevBtn').disabled=page<=1;
    document.getElementById('nextBtn').disabled=songs.length<20;
  });
}
function changePage(d){doSearch(curPage+d);}
function renderList(){
  let el=document.getElementById('list');el.innerHTML='';
  songs.forEach((s,i)=>{
    let hasFlac=(s.minfo||[]).some(m=>m.format==='flac');
    let tag=hasFlac?'<span class="tag tag-flac">FLAC</span>':'<span class="tag tag-mp3">MP3</span>';
    el.innerHTML+=`<div class="song-item"><input type="checkbox" data-idx="${i}"><img class="song-cover" src="${esc(s.pic_url||'')}" onerror="this.style.display='none'"><div class="song-info"><div class="song-name">${esc(s.name)}${tag}</div><div class="song-artist">${esc(s.artist)}</div></div><button class="btn-sm btn-preview" onclick="event.stopPropagation();preview(${i})">▶</button><button class="btn-sm btn-dl" onclick="event.stopPropagation();dlOne(${i})">⬇</button></div>`;
  });
}
function esc(s){return(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function toggleAll(){let cbs=document.querySelectorAll('.song-item input[type=checkbox]');let all=[...cbs].every(c=>c.checked);cbs.forEach(c=>c.checked=!all);}
function dlSelected(){let idxs=[...document.querySelectorAll('.song-item input:checked')].map(c=>+c.dataset.idx);if(!idxs.length)return showToast('请先勾选');fetch('/api/download',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({indices:idxs,source:curSource})}).then(()=>showToast(`已加入 ${idxs.length} 首到下载队列`));}
function dlOne(i){fetch('/api/download',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({indices:[i],source:curSource})}).then(()=>showToast('已加入下载队列'));}

// ===== 修复1: 预览与自动切歌 =====
function preview(i){
  currentIdx=i;let s=songs[i];
  document.getElementById('pbTitle').textContent=s.name;
  document.getElementById('pbSub').textContent=s.artist;
  document.getElementById('pbCover').src=s.pic_url||'';
  document.getElementById('playerBar').classList.add('active');
  // 同时设置两个audio的src，避免切歌时src不同步
  fetch('/api/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({index:i,source:curSource})})
  .then(r=>r.json()).then(d=>{
    if(d.url){
      audioEl.src=d.url;audioEl.load();audioEl.play();
      fpAudio.src=d.url;fpAudio.load(); // 预加载全屏audio
    }else{document.getElementById('pbSub').textContent='无预览资源';}
  });
  fetch('/api/lyric',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({index:i,source:curSource})})
  .then(r=>r.json()).then(d=>{currentLrcLines=d.lrc?parseLrc(d.lrc):[];});
}
function parseLrc(text){return text.split('\n').map(l=>{let m=l.match(/^\[(\d+):(\d+\.\d+)\](.*)$/);if(m)return{time:+m[1]*60+parseFloat(m[2]),text:m[3]};return null;}).filter(Boolean).sort((a,b)=>a.time-b.time);}

function openFullPlayer(){
  if(currentIdx<0)return;let s=songs[currentIdx];
  document.getElementById('fpTitle').textContent=s.name;
  document.getElementById('fpArtist').textContent=s.artist;
  document.getElementById('fpCover').src=s.pic_url||'';
  // 修复1: 只在src确实不同时才重新赋值，避免重置播放位置
  if(fpAudio.src!==audioEl.src){fpAudio.src=audioEl.src;}
  fpAudio.currentTime=audioEl.currentTime;
  fpAudio.play().catch(()=>{});audioEl.pause();
  let box=document.getElementById('fpLrcBox');box.innerHTML='';
  currentLrcLines.forEach((l,i)=>{let div=document.createElement('div');div.className='fp-lrc-line';div.textContent=l.text||'♪';box.appendChild(div);});
  document.getElementById('fullPlayer').classList.add('active');
}
function closeFullPlayer(){
  document.getElementById('fullPlayer').classList.remove('active');
  audioEl.currentTime=fpAudio.currentTime;
  audioEl.play().catch(()=>{});fpAudio.pause();
}
fpAudio.addEventListener('timeupdate',()=>{
  if(!currentLrcLines.length)return;let t=fpAudio.currentTime;
  let ai=0;for(let i=currentLrcLines.length-1;i>=0;i--){if(currentLrcLines[i].time<=t){ai=i;break;}}
  document.querySelectorAll('.fp-lrc-line').forEach((el,i)=>{
    if(i===ai){el.classList.add('active');el.scrollIntoView({behavior:'smooth',block:'center'});}else{el.classList.remove('active');}
  });
});
// 修复1: 用canplay确保新src就绪后再播放，移除setTimeout
fpAudio.addEventListener('ended',()=>{
  if(currentIdx<songs.length-1){
    let nextIdx=currentIdx+1;
    preview(nextIdx);
    // 等待fpAudio新src加载完毕后再打开全屏并播放
    fpAudio.oncanplay=function(){
      fpAudio.oncanplay=null;
      openFullPlayer();
    };
  }
});

// ===== 下载管理 =====
function toggleDlPanel(){document.getElementById('dlPanel').classList.toggle('active');refreshDlPanel();}
function refreshDlPanel(){
  fetch('/api/dl-status').then(r=>r.json()).then(d=>{
    let html='<div class="dl-section-title">计划中 ('+d.pending.length+')</div>';
    if(!d.pending.length)html+='<div style="font-size:12px;color:var(--sub);padding:8px;">暂无任务</div>';
    d.pending.forEach(t=>{html+=`<div class="dl-item"><div class="dl-item-name">${esc(t.name)} - ${esc(t.artist)}</div><div class="dl-item-status">${t.status}</div><div class="dl-item-del" onclick="delPending(${t.id})">✕</div></div>`;});
    html+='<div class="dl-section-title">已完成 ('+d.completed.length+')</div>';
    if(!d.completed.length)html+='<div style="font-size:12px;color:var(--sub);padding:8px;">暂无记录</div>';
    d.completed.forEach(t=>{html+=`<div class="dl-item"><div class="dl-item-name">${esc(t.name)} - ${esc(t.artist)}</div><div class="dl-item-status" style="color:${t.status==='成功'?'#2ecc71':'#e74c3c'}">${t.status}</div></div>`;});
    if(d.completed.length)html+='<button class="dl-clear-btn" onclick="clearCompleted()">清空已完成</button>';
    document.getElementById('dlPanelBody').innerHTML=html;
    let badge=document.getElementById('dlBadge');
    if(d.pending.length>0){badge.style.display='flex';badge.textContent=d.pending.length;}else{badge.style.display='none';}
  });
}
function delPending(id){fetch('/api/dl-remove',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:id})}).then(()=>refreshDlPanel());}
function clearCompleted(){fetch('/api/dl-clear',{method:'POST'}).then(()=>refreshDlPanel());}
setInterval(refreshDlPanel,Math.max(LOG_SYNC_INTERVAL*4,1000));

function saveCookie(){let c=document.getElementById('cookieInput').value.trim();if(!c)return;fetch('/api/cookie',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cookie:c})}).then(()=>showToast('Cookie 已保存'));}

// ===== 修复2: SSE日志流支持短标记原地刷新 =====
let evtSource=null;
function connectLogs(){
  if(evtSource)evtSource.close();
  evtSource=new EventSource('/api/logs-stream');
  evtSource.onmessage=function(e){
    let el=document.getElementById('logs');
    let raw=e.data;
    // 检测短标记 \x01P\x01
    if(raw.startsWith('\x01P\x01')){
      let content=raw.substring(3);
      let progLine=el.querySelector('.log-progress');
      if(!progLine){progLine=document.createElement('div');progLine.className='log-progress';el.appendChild(progLine);}
      progLine.textContent=content;
      el.scrollTop=el.scrollHeight;
    }else{
      let progLine=el.querySelector('.log-progress');
      if(progLine)progLine.remove();
      let div=document.createElement('div');div.textContent=raw;el.appendChild(div);
      el.scrollTop=el.scrollHeight;
      while(el.children.length>200)el.removeChild(el.firstChild);
    }
  };
  evtSource.onerror=function(){setTimeout(connectLogs,3000);};
}
connectLogs();
</script></body></html>"""

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length else {}
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode())
        elif self.path == "/api/logs-stream":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            last_send = 0; throttle = 0.25
            try:
                while True:
                    try:
                        msg = log_queue.get(timeout=30)
                        now = time.time()
                        is_progress = PROGRESS_MARKER in msg
                        if is_progress and (now - last_send) < throttle: continue
                        last_send = now
                        # 保留PROGRESS_MARKER传给前端，清除其他\r
                        clean = msg.replace("\r", "").replace(PROGRESS_MARKER, PROGRESS_MARKER)
                        self.wfile.write(f"data: {clean}\n\n".encode("utf-8"))
                        self.wfile.flush()
                    except queue.Empty:
                        self.wfile.write(b": keepalive\n\n"); self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError): pass
        elif self.path == "/api/dl-status":
            self._json(dl_manager.get_status())
        else: self.send_error(404)
    def do_POST(self):
        if self.path == "/api/search":
            body = self._read_body()
            results, meta = search_music(body.get("keyword",""), body.get("source","kuwo"), body.get("page",1))
            self._json({"songs": results, "meta": meta})
        elif self.path == "/api/download":
            body = self._read_body()
            count = 0
            for idx in body.get("indices", []):
                if 0 <= idx < len(_cache_songs):
                    if dl_manager.add_task(_cache_songs[idx], body.get("source","kuwo")) is not None:
                        count += 1
            self._json({"ok": True, "count": count})
        elif self.path == "/api/preview":
            body = self._read_body(); idx = body.get("index", 0)
            if 0 <= idx < len(_cache_songs):
                url, ext = get_audio_url(_cache_songs[idx], body.get("source","kuwo"), low=True)
                self._json({"url": url, "ext": ext})
            else: self._json({"url": None})
        elif self.path == "/api/lyric":
            body = self._read_body(); idx = body.get("index", 0)
            if 0 <= idx < len(_cache_songs):
                self._json({"lrc": get_lyrics(_cache_songs[idx], body.get("source","kuwo"))})
            else: self._json({"lrc": None})
        elif self.path == "/api/cookie":
            body = self._read_body(); save_cookie(body.get("cookie",""))
            HEADERS["Cookie"] = body.get("cookie",""); self._json({"ok": True})
        elif self.path == "/api/dl-remove":
            dl_manager.remove_pending(self._read_body().get("id",0)); self._json({"ok": True})
        elif self.path == "/api/dl-clear":
            dl_manager.clear_completed(); self._json({"ok": True})
        else: self.send_error(404)
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

# 修复4: 搜索缓存管理
# 修复: 保存原始搜索函数的引用，避免被覆盖后产生无限递归
_original_search_music = search_music

_cache_songs = []
def search_music_cached(keyword, source="kuwo", page=1):
    global _cache_songs
    # 核心修复: 这里必须调用 _original_search_music 而不是 search_music
    results, meta = _original_search_music(keyword, source, page)
    if page == 1:
        _cache_songs = results  # 新搜索清空旧缓存
    else:
        _cache_songs.extend(results)
    return results, meta

# 安全地覆盖全局搜索函数
search_music = search_music_cached

def main():
    cookie = load_cookie()
    if cookie: HEADERS["Cookie"] = cookie; log("[✅] Cookie 已加载")
    else: log("[⚠️] 未找到 Cookie，请在网页粘贴")
    log(f"[🚀] Web 控制台: http://localhost:{PORT}")
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    server.daemon_threads = True
    try: server.serve_forever()
    except KeyboardInterrupt: log("\n👋 服务已停止")

if __name__ == "__main__":
    main()