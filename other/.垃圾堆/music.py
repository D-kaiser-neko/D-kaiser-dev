#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
flac.music.hi.cn 音乐下载器 (元数据嵌入版)
用法:
  python music.py                         交互模式
  python music.py 关键词                   搜索 + 选择菜单 (n/p 翻页, v序号 预览)
  python music.py 关键词 作者              直接下载作者匹配的第一首
  python music.py list.txt                 批量下载 (音频+歌词+封面+嵌入元数据)
  python music.py list.txt lrc             批量并行下载歌词 (4核)
依赖: pip install mutagen requests
"""

import os
import re
import sys
import time
import shutil
import subprocess
import threading
import unicodedata
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import requests

# 尝试导入 mutagen，如果未安装则给出提示
try:
    from mutagen.flac import FLAC, Picture
    from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC, USLT
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False
    print("[!] 未检测到 mutagen 库，元数据嵌入功能将被禁用。")
    print("    请运行: pip install mutagen\n")

# ================= 配置区 =================
COOKIE_FILE = "/storage/emulated/0/termux/音乐Cookie.txt"
SAVE_DIR = "/storage/emulated/0/termux/MusicDownloads"
PAGE_SIZE = 30
THREADS = 8

SOURCE_ALIASES = {
    "kuwo": "kuwo", "kw": "kuwo", "酷我": "kuwo",
    "netease": "netease", "wyy": "netease", "wy": "netease", "网易": "netease", "163": "netease",
    "qq": "qq", "tencent": "qq", "腾讯": "qq",
    "kugou": "kugou", "kg": "kugou", "酷狗": "kugou",
}

def normalize_source(s):
    s = (s or "").strip().lower()
    return SOURCE_ALIASES.get(s, s or "kuwo")

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

try: os.makedirs(SAVE_DIR, exist_ok=True)
except Exception:
    SAVE_DIR = "./MusicDownloads"
    os.makedirs(SAVE_DIR, exist_ok=True)
    print(f"[!] 无法写入默认目录, 回退到: {SAVE_DIR}")

BASE_SEARCH = "https://flac.music.hi.cn/ajax.php?act=search"
BASE_GETURL = "https://flac.music.hi.cn/ajax.php?act=getUrl"
LYRIC_ACTS = ["lyric", "lrc", "getLyric", "getLrc"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Referer": "https://flac.music.hi.cn/",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Cookie": ""
}

def load_cookie():
    if os.path.exists(COOKIE_FILE):
        try:
            with open(COOKIE_FILE, "r", encoding="utf-8") as f: return f.read().strip()
        except Exception: return ""
    return ""

def save_cookie(cookie_str):
    try:
        os.makedirs(os.path.dirname(COOKIE_FILE), exist_ok=True)
        with open(COOKIE_FILE, "w", encoding="utf-8") as f: f.write(cookie_str.strip())
        print(f"[✅] Cookie 已保存至 {COOKIE_FILE}")
    except Exception as e: print(f"[❌] 保存 Cookie 失败: {e}")

def safe_post(url, payload):
    global HEADERS
    clean = {k: str(v).replace('\u3000', ' ').replace('\u200b', '').strip() for k, v in payload.items() if v is not None}
    data = urllib.parse.urlencode(clean).encode('utf-8')
    res = requests.post(url, data=data, headers=HEADERS, timeout=15)
    if res.status_code == 468 or "challenge" in res.text.lower():
        print("\n[⚠️ WAF 拦截] Cookie 已失效或被风控拦截。")
        new_cookie = input("👉 请粘贴最新的 Cookie (直接回车跳过本次请求): ").strip()
        if new_cookie:
            save_cookie(new_cookie)
            HEADERS["Cookie"] = new_cookie
            res = requests.post(url, data=data, headers=HEADERS, timeout=15)
    return res

def search_music(keyword, source="kuwo", page=1):
    print(f"[*] 正在搜索: {keyword} (源: {source}, 第{page}页)...")
    payload = {"keyword": keyword, "type": source, "page": str(page)}
    try:
        res = safe_post(BASE_SEARCH, payload)
        if res.status_code == 468 or "challenge" in res.text.lower(): return None
        if res.status_code != 200: return None
        j = res.json()
        if j.get("code") != 0: return None
        return j.get("data", {}).get("list", [])
    except Exception as e:
        print(f"[-] 搜索异常: {e}")
        return None

def get_audio_url(song_data, source="kuwo", low=False):
    print(f"[*] 正在解析《{song_data.get('name')}》的链接...")
    minfo = song_data.get("minfo", [])
    if low:
        format_type = bitrate = None
        for want in ("128", "320"):
            for m in minfo:
                if m.get("format") == "mp3" and str(m.get("bitrate")) == want:
                    format_type, bitrate = "mp3", want; break
            if format_type: break
        if not format_type:
            for m in minfo:
                if m.get("format") == "mp3": format_type, bitrate = "mp3", str(m.get("bitrate")); break
        if not format_type:
            for m in minfo:
                if m.get("format") == "flac": format_type, bitrate = "flac", str(m.get("bitrate", "2000")); break
        if not format_type: return None, None
    else:
        format_type, bitrate = "flac", "2000"
        found_flac = any(m.get("format") == "flac" for m in minfo)
        if not found_flac:
            if minfo:
                format_type = minfo[0].get("format", "mp3")
                bitrate = minfo[0].get("bitrate", "320")
                print(f"[!] 未找到 FLAC 资源，自动降级为 {bitrate}k MP3")
            else: return None, None

    payload = {
        "platform": source, "songid": str(song_data.get("id")),
        "format": format_type, "bitrate": str(bitrate),
        "time": str(song_data.get("time")), "sign": song_data.get("sign")
    }
    try:
        res = safe_post(BASE_GETURL, payload)
        if res.status_code == 200:
            j = res.json()
            if j.get("code") == 0:
                d = j.get("data")
                if isinstance(d, str): return d or None, format_type
                if isinstance(d, dict): return d.get("url"), format_type
        return None, None
    except Exception as e:
        print(f"[-] 请求异常: {e}")
        return None, None

# ================= 封面下载 =================
def download_cover(song_data, filepath_base):
    pic_url = song_data.get("pic_url")
    if not pic_url or not pic_url.startswith("http"): return False
    cover_path = f"{filepath_base}.jpg"
    if os.path.exists(cover_path) and os.path.getsize(cover_path) > 1024:
        print("[⏭] 封面已存在")
        return True
    print("[*] 正在下载封面...")
    try:
        headers = {"User-Agent": HEADERS["User-Agent"]}
        if "kuwo.cn" in pic_url: headers["Referer"] = "https://www.kuwo.cn/"
        elif "126.net" in pic_url or "netease" in pic_url: headers["Referer"] = "https://music.163.com/"
        elif "qq.com" in pic_url or "qpic.cn" in pic_url: headers["Referer"] = "https://y.qq.com/"
        res = requests.get(pic_url, headers=headers, timeout=15, stream=True)
        if res.status_code == 200:
            with open(cover_path, "wb") as f:
                for chunk in res.iter_content(8192): f.write(chunk)
            if os.path.getsize(cover_path) < 1024:
                os.remove(cover_path); print("[-] 封面文件过小"); return False
            print(f"[✅] 封面保存: {cover_path}")
            return True
        print(f"[-] 封面下载失败 (HTTP {res.status_code})"); return False
    except Exception as e: print(f"[-] 封面下载异常: {e}"); return False

# ================= 元数据嵌入 (核心新增) =================
def embed_metadata(audio_path, song_data, lrc_text=None):
    """将标题、艺术家、专辑、封面、歌词嵌入音频文件"""
    if not HAS_MUTAGEN or not os.path.exists(audio_path): return False
    
    ext = os.path.splitext(audio_path)[1].lower()
    title = song_data.get("name", "")
    artist = song_data.get("artist", "")
    album = song_data.get("album_name", "")
    pic_url = song_data.get("pic_url", "")
    
    # 读取已下载的封面图片
    cover_data = None
    cover_path = audio_path.rsplit(".", 1)[0] + ".jpg"
    if os.path.exists(cover_path):
        with open(cover_path, "rb") as f: cover_data = f.read()
        
    try:
        if ext == ".flac":
            audio = FLAC(audio_path)
            audio["TITLE"] = title
            audio["ARTIST"] = artist
            audio["ALBUM"] = album
            if lrc_text: audio["LYRICS"] = lrc_text
            
            if cover_data:
                pic = Picture()
                pic.type = 3  # Cover (front)
                pic.mime = "image/jpeg"
                pic.desc = "Cover"
                pic.data = cover_data
                audio.clear_pictures()
                audio.add_picture(pic)
            audio.save()
            
        elif ext == ".mp3":
            audio = ID3(audio_path) if os.path.getsize(audio_path) > 0 else ID3()
            audio["TIT2"] = TIT2(encoding=3, text=title)
            audio["TPE1"] = TPE1(encoding=3, text=artist)
            audio["TALB"] = TALB(encoding=3, text=album)
            if lrc_text:
                audio["USLT"] = USLT(encoding=3, lang="eng", desc="", text=lrc_text)
            if cover_data:
                audio["APIC"] = APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=cover_data)
            audio.save()
        else:
            return False
            
        print(f"[✅] 元数据已嵌入 ({ext.upper()})")
        return True
    except Exception as e:
        print(f"[-] 元数据嵌入失败: {e}")
        return False

# ================= 在线预览 =================
def detect_player():
    for name, cmd in (
        ("mpv", ["mpv", "--no-video", "--quiet", "--term-osd-bar", "--no-resume-playback"]),
        ("ffplay", ["ffplay", "-nodisp", "-autoexit", "-stats"]),
        ("mpg123", ["mpg123"]),
    ):
        if shutil.which(name): return cmd
    return None

def preview_song(song, source):
    artist = song.get("artist", "未知"); name = song.get("name", "未知")
    print(f"\n🎧 预览: {name} - {artist}")
    url, ext = get_audio_url(song, source, low=True)
    if not url: print("[-] 无可用预览资源"); return False
    cmd = detect_player()
    if not cmd: print("[!] 未检测到播放器, 请先运行: pkg install mpv"); return False
    print(f"[*] 播放器: {cmd[0]} (按 q 退出预览)")
    try: subprocess.run(cmd + [url])
    except KeyboardInterrupt: print("\n[⏹] 预览已结束")
    return True

# ================= 歌词清洗 =================
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
            if not text: continue
            lines.append([ts, text])
        elif line.startswith('['): lines.append([None, line])
        else:
            if lines and lines[-1][0] is not None: lines[-1][1] += line
    has_kana = lambda t: re.search(r'[\u3040-\u30ff]', t) is not None
    has_han = lambda t: re.search(r'[\u4e00-\u9fff]', t) is not None
    is_jp = has_kana
    is_cn = lambda t: has_han(t) and not has_kana(t)
    for i in range(1, len(lines) - 1):
        tp, tc, tn = lines[i-1][0], lines[i][0], lines[i+1][0]
        if not (tp and tc and tn): continue
        if tc == tn and tc != tp:
            a, b = lines[i-1][1], lines[i][1]
            if (is_cn(b) and is_jp(a)) or (is_jp(b) and is_cn(a)): lines[i][0] = tp
    return '\n'.join(text if ts is None else f"[{ts}]{text}" for ts, text in lines)

def get_lyrics(song_data, source="kuwo"):
    payload = {"platform": source, "songid": str(song_data.get("id")), "time": str(song_data.get("time")), "sign": song_data.get("sign")}
    for act in LYRIC_ACTS:
        url = f"https://flac.music.hi.cn/ajax.php?act={act}"
        try:
            res = safe_post(url, payload)
            if res.status_code != 200 or not res.text.strip(): continue
            lrc = None
            try:
                j = res.json()
                if j.get("code") == 0:
                    d = j.get("data")
                    if isinstance(d, str): lrc = d
                    elif isinstance(d, dict): lrc = d.get("lyric") or d.get("lrc") or d.get("content")
            except ValueError: lrc = res.text
            if lrc and isinstance(lrc, str) and not lrc.strip().startswith('{') and '[' in lrc and ']' in lrc:
                return format_lrc(lrc)
        except Exception: continue
    return None

# ================= 多线程下载 =================
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
    def close(self): sys.stdout.write("\n"); sys.stdout.flush()

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
        except Exception: ok = False
    with ThreadPoolExecutor(max_workers=len(ranges)) as ex:
        futs = [ex.submit(worker, i, s, e) for i, (s, e) in enumerate(ranges)]
        for f in futs:
            try: f.result()
            except Exception: ok = False
    prog.close()
    if not ok:
        for p in parts:
            if os.path.exists(p):
                try: os.remove(p)
                except OSError: pass
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
        print(f"\n[❌] 下载失败: {e}"); return False

def download_file(url, filepath):
    dl_headers = {k: v for k, v in HEADERS.items() if k != "Content-Type"}
    total, ranges_ok = 0, False
    try:
        head = requests.head(url, headers=dl_headers, timeout=15, allow_redirects=True)
        total = int(head.headers.get("Content-Length") or 0)
        ranges_ok = (head.headers.get("Accept-Ranges", "none") or "").lower() != "none"
    except Exception: pass
    if total > 2*1024*1024 and ranges_ok:
        print(f"[*] 🚀 Python {THREADS} 线程分片下载...")
        if _multithread_download(url, filepath, total, dl_headers): return True
        print("[!] 多线程失败, 回退单线程...")
    print("[*] 🐢 单线程下载...")
    return _single_download(url, filepath, dl_headers)

# ================= 核心处理流程 =================
def process_song(song, source):
    artist = song.get("artist", "未知"); name = song.get("name", "未知")
    safe_name = re.sub(r'[\\/*?:"<>|]', "", f"{artist} - {name}")
    filepath_base = os.path.join(SAVE_DIR, safe_name)
    
    print(f"\n🎵 {name} - {artist}")
    
    # 1. 下载封面
    download_cover(song, filepath_base)
    
    # 2. 下载音频
    audio_url, ext = get_audio_url(song, source)
    if not audio_url: print("[-] 跳过 (无任何可用资源)"); return False
    print(f"[*] 下载音频 ({ext.upper()})...")
    audio_path = f"{filepath_base}.{ext}"
    if not download_file(audio_url, audio_path): return False
    print(f"[✅] 音频保存: {audio_path}")
    
    # 3. 下载歌词
    print("[*] 尝试获取歌词...")
    lrc_text = get_lyrics(song, source)
    if lrc_text:
        lrc_path = f"{filepath_base}.lrc"
        with open(lrc_path, "w", encoding="utf-8") as f: f.write(lrc_text)
        print(f"[✅] 歌词保存: {lrc_path}")
    else:
        print("[-] 未找到歌词")
    
    # 4. 嵌入元数据 (保留原始 jpg/lrc 文件)
    if HAS_MUTAGEN:
        print("[*] 正在嵌入元数据...")
        embed_metadata(audio_path, song, lrc_text)
    
    return True

# ================= TUI & 批量模式 (保持原样) =================
def clear_screen(): sys.stdout.write("\033[2J\033[H"); sys.stdout.flush()
def disp_width(s): return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)
def fit(s, width):
    if disp_width(s) <= width: return s
    out, w = [], 0
    for c in s:
        cw = 2 if unicodedata.east_asian_width(c) in "WF" else 1
        if w + cw > width - 1: break
        out.append(c); w += cw
    return "".join(out) + "…"

def render_page(songs, page, keyword, source, msg=""):
    clear_screen(); cols = shutil.get_terminal_size((80, 24)).columns
    print("="*62); print(f"🔍 {keyword}   [源: {source}]   📄 第 {page} 页"); print("="*62)
    base = (page - 1) * PAGE_SIZE
    for i, song in enumerate(songs):
        has_flac = any(m.get("format") == "flac" for m in song.get("minfo", []))
        mark = "✅FLAC" if has_flac else "⚠️MP3 "
        prefix = f"[{base+i+1:<3}] {mark} | "
        text = fit(f"{song.get('artist','未知')} - {song.get('name','未知')}", cols - disp_width(prefix))
        print(prefix + text)
    print("-"*62); print("命令: 序号=下载  v序号=预览  n=下一页  p=上一页  a=全下本页  q=返回搜索")
    if msg: print(f">>> {msg}")

def result_loop(keyword, source):
    page = 1; songs = search_music(keyword, source, page)
    if not songs: print("[-] 未找到结果。"); return
    msg = ""
    while True:
        render_page(songs, page, keyword, source, msg)
        choice = input("👉 请输入命令: ").strip().lower().replace(" ", "")
        if choice == 'q': return
        elif choice == 'n':
            nxt = search_music(keyword, source, page + 1)
            if nxt: page += 1; songs = nxt; msg = ""
            else: msg = "[-] 已经是最后一页了"
        elif choice == 'p':
            if page > 1:
                prv = search_music(keyword, source, page - 1)
                if prv: page -= 1; songs = prv; msg = ""
            else: msg = "[-] 已经是第一页了"
        elif choice == 'a':
            af = input("🔍 筛选作者 (留空则全下本页): ").strip().lower()
            targets = [s for s in songs if not af or af in s.get("artist", "").lower()]
            if not targets: msg = "[-] 没有符合条件的歌曲。"; continue
            done = 0
            for i, s in enumerate(targets):
                print(f"\n🚀 批量进度: [{i+1}/{len(targets)}]")
                if process_song(s, source): done += 1
            msg = f"✅ 本页批量完成: {done}/{len(targets)} 首"
        elif choice.startswith('v') and choice[1:].isdigit():
            idx = int(choice[1:]) - (page - 1) * PAGE_SIZE - 1
            if 0 <= idx < len(songs): preview_song(songs[idx], source); msg = f"🎧 已预览: {songs[idx].get('name')}"
            else: msg = "[-] 序号无效！"
        elif choice.isdigit():
            idx = int(choice) - (page - 1) * PAGE_SIZE - 1
            if 0 <= idx < len(songs):
                ok = process_song(songs[idx], source)
                msg = f"✅ 已下载: {songs[idx].get('name')}" if ok else "[-] 下载失败/无资源"
            else: msg = "[-] 序号无效！"
        else: msg = "[-] 输入无效！"

def interactive_mode():
    while True:
        kw = input("\n🔍 请输入歌名或歌手 (输入 q 退出): ").strip()
        if kw.lower() == 'q': break
        src = normalize_source(input("🎵 请输入音源 (默认 kuwo): ").strip() or "kuwo")
        result_loop(kw, src)

def batch_mode(file_path, only_lrc=False):
    print(f"[*] 批量模式启动，读取文件: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f: raw_lines = f.readlines()
    tasks = []
    for line in raw_lines:
        line = line.strip()
        if not line or line.startswith("#"): continue
        if "---" in line: q, a = [x.strip() for x in line.split("---", 1)]
        else: q, a = line, ""
        q = re.sub(r'\.(mp3|flac|wav|ogg|m4a|aac)$', '', q, flags=re.IGNORECASE).strip()
        if q: tasks.append((q, a))
    total = len(tasks)
    if only_lrc:
        print(f"[*] 📋 解析完成，共 {total} 个任务。启动 4 核并行下载歌词模式。\n")
        lock = threading.Lock(); ok_n = fail_n = 0
        def worker(task):
            nonlocal ok_n, fail_n; q, a = task
            songs = search_music(q, "kuwo")
            if not songs: 
                with lock: print(f"[-] 未找到结果: {q}"); fail_n += 1; return
            target = None
            if a:
                for s in songs:
                    if a.lower() in s.get("artist", "").lower(): target = s; break
            else: target = songs[0]
            if not target:
                with lock: print(f"[-] 未匹配作者 '{a}': {q}"); fail_n += 1; return
            sn = re.sub(r'[\\/*?:"<>|]', "", f"{target.get('artist','未知')} - {target.get('name','未知')}")
            lp = os.path.join(SAVE_DIR, f"{sn}.lrc")
            if os.path.exists(lp) and os.path.getsize(lp) > 0:
                with lock: print(f"[⏭] 歌词已存在: {sn}.lrc"); return
            lt = get_lyrics(target, "kuwo")
            if lt:
                with open(lp, "w", encoding="utf-8") as f: f.write(lt)
                with lock: print(f"[✅] {sn}.lrc"); ok_n += 1
            else:
                with lock: print(f"[-] 无歌词: {sn}"); fail_n += 1
        with ThreadPoolExecutor(max_workers=4) as ex: list(ex.map(worker, tasks))
        print(f"\n🎉 歌词批量完成！成功: {ok_n}, 失败/跳过: {fail_n}"); return

    print(f"[*] 📋 解析完成，共发现 {total} 个有效下载任务。\n")
    ok_n = fail_n = 0
    for i, (q, a) in enumerate(tasks, 1):
        print(f"\n🚀 批量进度: [{i}/{total}] 已成功 {ok_n} / 已失败 {fail_n}")
        print(f"🔍 处理: {q} (目标作者: {a or '无'})")
        songs = search_music(q, "kuwo")
        if not songs: fail_n += 1; continue
        downloaded = False
        if a:
            for song in songs:
                if a.lower() in song.get("artist", "").lower():
                    if process_song(song, "kuwo"): downloaded = True; break
            if not downloaded: print(f"[-] ⚠️ 未找到作者包含 '{a}' 的歌曲。")
        else:
            print("[*] 💡 未指定作者，自动下载搜索结果的第一首。")
            if process_song(songs[0], "kuwo"): downloaded = True
        if downloaded: ok_n += 1
        else: fail_n += 1
    print(f"\n🎉 批量下载完成！成功: {ok_n} 首, 失败/跳过: {fail_n} 首。")

def main():
    global HEADERS
    print("="*50)
    print(" 🎵 FLAC 无损音乐批量下载器 (元数据嵌入版) ")
    print(f" 下载内核: Python {THREADS} 线程分片 + 单行进度条")
    print(f" 附加功能: 自动封面 | mpv预览 | 4核并行歌词 | 元数据嵌入")
    print("="*50)
    cookie = load_cookie()
    if cookie: print("[✅] 成功读取本地 Cookie。"); HEADERS["Cookie"] = cookie
    else: print(f"[⚠️] 未找到 Cookie 文件: {COOKIE_FILE}")
    args = sys.argv[1:]
    if not args: interactive_mode()
    elif os.path.isfile(args[0]):
        only_lrc = (len(args) > 1 and args[1].lower() == 'lrc')
        batch_mode(args[0], only_lrc=only_lrc)
    else:
        keyword = args[0]; artist = args[1].strip() if len(args) > 1 and args[1].lower() != 'lrc' else ""
        if artist:
            print(f"[*] CLI 直下模式: 歌名='{keyword}', 作者='{artist}'")
            songs = search_music(keyword, "kuwo", 1)
            matched = [s for s in (songs or []) if artist.lower() in s.get("artist", "").lower()]
            if matched: process_song(matched[0], "kuwo")
            else: print(f"[-] 未在搜索结果中找到作者包含 '{artist}' 的歌曲。")
        else: result_loop(keyword, "kuwo")

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: print("\n👋 已中断")