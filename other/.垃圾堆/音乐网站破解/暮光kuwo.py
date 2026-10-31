#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
暮光工具箱音乐下载器 (全接口破解版)
接口来源: 暮光工具箱 v4.0.9 APK 逆向
  - 搜索: 119.3.221.4:8002/search (签名已破解)
  - 播放: nmobi.kuwo.cn/mobi.s (convert_url_with_sign)
  - 歌词: mlyric.kuwo.cn/mobi.s (Base64 LRC)
用法:
  python mg.py                         交互模式
  python mg.py 关键词                   搜索 + 选择菜单
  python mg.py 关键词 作者              直接下载匹配的第一首
  python mg.py list.txt                 批量下载
  python mg.py list.txt lrc             批量并行歌词 (4核)
依赖: pip install mutagen requests
"""

import os, re, sys, time, shutil, subprocess, threading, unicodedata
import urllib.parse, base64, json, math
from concurrent.futures import ThreadPoolExecutor
import requests

try:
    from mutagen.flac import FLAC, Picture
    from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC, USLT
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False

# ================= 配置 =================
SAVE_DIR = "/storage/emulated/0/termux/MusicDownloads"
THREADS = 8
PAGE_SIZE = 20

SEARCH_URL = "http://119.3.221.4:8002/search"
PLAY_URL   = "http://nmobi.kuwo.cn/mobi.s"
LYRIC_URL  = "http://mlyric.kuwo.cn/mobi.s"
SALT       = "MusicKillerNativeSalt"
SOURCE_TAG = "kwplayerhd_ar_6.6.6.6_tianbao_T1A_qirui.apk"

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except: pass
try: os.makedirs(SAVE_DIR, exist_ok=True)
except: SAVE_DIR = "./MusicDownloads"; os.makedirs(SAVE_DIR, exist_ok=True)

# ================= 签名 =================
import hashlib
def make_headers():
    ts = str(int(time.time() * 1000))
    sign = hashlib.md5(f"{SALT}{ts}1".encode()).hexdigest()
    return {
        "Version": "1", "Platform": "android",
        "Timestamp": ts, "Sign": sign,
        "User-Agent": "okhttp/4.11.0",
    }

# ================= 搜索 =================
def search(keyword, page=1, size=PAGE_SIZE):
    encoded = urllib.parse.quote(keyword)
    url = f"{SEARCH_URL}?keyword={encoded}&pageNo={page}&pageSize={size}"
    try:
        r = requests.get(url, headers=make_headers(), timeout=15)
        j = r.json()
        if j.get("code") != 200: return [], 0
        d = j.get("data", {})
        return d.get("data", []), d.get("total", 0)
    except Exception as e:
        print(f"[-] 搜索异常: {e}"); return [], 0

# ================= 播放链接 =================
def get_play_url(rid, quality="flac"):
    br = {"flac": "2000kflac", "320": "320kmp3", "128": "128kmp3"}.get(quality, "2000kflac")
    params = {
        "f": "web", "user": "0", "source": SOURCE_TAG,
        "type": "convert_url_with_sign", "rid": str(rid), "br": br
    }
    try:
        r = requests.get(PLAY_URL, params=params, headers={
            "User-Agent": "okhttp/4.11.0", "Accept-Encoding": "gzip"
        }, timeout=15)
        j = r.json()
        if j.get("code") == 200:
            d = j.get("data", {})
            return d.get("url"), d.get("format", quality)
        return None, None
    except Exception as e:
        print(f"[-] 获取播放链接异常: {e}"); return None, None

# ================= 歌词 =================
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
    has_kana = lambda t: bool(re.search(r'[\u3040-\u30ff]', t))
    has_han  = lambda t: bool(re.search(r'[\u4e00-\u9fff]', t))
    for i in range(1, len(lines) - 1):
        tp, tc, tn = lines[i-1][0], lines[i][0], lines[i+1][0]
        if not (tp and tc and tn): continue
        if tc == tn and tc != tp:
            a, b = lines[i-1][1], lines[i][1]
            if (has_han(b) and not has_kana(b) and has_kana(a)) or \
               (has_kana(b) and has_han(a) and not has_kana(a)):
                lines[i][0] = tp
    return '\n'.join(t if ts is None else f"[{ts}]{t}" for ts, t in lines)

def get_lyrics(rid):
    params = {"f": "web", "type": "lyric", "lrcx": "1", "rid": str(rid), "encode": "utf8"}
    try:
        r = requests.get(LYRIC_URL, params=params, headers={
            "User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/120.0.6099.144 Mobile Safari/537.36",
            "Accept-Encoding": "gzip"
        }, timeout=15)
        raw = r.text.strip()
        if not raw: return None
        try:
            decoded = base64.b64decode(raw).decode("utf-8", errors="replace")
            idx = decoded.find("[")
            if idx >= 0: decoded = decoded[idx:]
            return format_lrc(decoded) if decoded.strip() else None
        except:
            if "[" in raw and "]" in raw: return format_lrc(raw)
            return None
    except Exception as e:
        print(f"[-] 歌词异常: {e}"); return None

# ================= 下载引擎 =================
class Progress:
    def __init__(self, total, desc="下载"):
        self.total = total; self.done = 0; self.desc = desc
        self.lock = threading.Lock(); self.start = time.time()
    def update(self, n):
        with self.lock: self.done += n; self._draw()
    def _draw(self):
        pct = min(self.done / self.total, 1) if self.total else 0
        w = 24; filled = int(w * pct); bar = '█' * filled + '░' * (w - filled)
        el = max(time.time() - self.start, 0.001); sp = self.done / el
        eta = int((self.total - self.done) / sp) if sp > 0 else 0
        sys.stdout.write(f"\r{self.desc} [{bar}] {pct*100:5.1f}% {self.done//1048576}/{self.total//1048576}MB {sp/1048576:.1f}MB/s ETA {eta}s ")
        sys.stdout.flush()
    def close(self): sys.stdout.write("\n"); sys.stdout.flush()

def download_file(url, filepath):
    hd = {"User-Agent": "AndroidDownloadManager/10 (Linux; U; Android 10)"}
    total, rok = 0, False
    try:
        h = requests.head(url, headers=hd, timeout=15, allow_redirects=True)
        total = int(h.headers.get("Content-Length") or 0)
        rok = (h.headers.get("Accept-Ranges", "none") or "").lower() != "none"
    except: pass
    if total > 2*1048576 and rok:
        print(f"[*] 🚀 {THREADS} 线程分片...")
        chunk = max(1048576, (total + THREADS - 1) // THREADS)
        ranges, s = [], 0
        while s < total:
            e = min(total-1, s+chunk-1); ranges.append((s,e)); s = e+1
        parts = [f"{filepath}.part{i}" for i in range(len(ranges))]
        prog = Progress(total); ok = True
        def worker(i, s, e):
            nonlocal ok
            h2 = dict(hd); h2["Range"] = f"bytes={s}-{e}"
            try:
                r = requests.get(url, headers=h2, stream=True, timeout=30)
                if r.status_code not in (200,206): ok=False; return
                with open(parts[i],"wb") as f:
                    for c in r.iter_content(65536):
                        if c: f.write(c); prog.update(len(c))
            except: ok = False
        with ThreadPoolExecutor(max_workers=len(ranges)) as ex:
            futs = [ex.submit(worker,i,s,e) for i,(s,e) in enumerate(ranges)]
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
        with open(tmp,"wb") as out:
            for p in parts:
                with open(p,"rb") as fin:
                    while True:
                        b = fin.read(1048576)
                        if not b: break
                        out.write(b)
                os.remove(p)
        os.replace(tmp, filepath); return True
    print("[*] 🐢 单线程...")
    prog = None
    try:
        with requests.get(url, headers=hd, stream=True, timeout=30) as r:
            r.raise_for_status(); t = int(r.headers.get("Content-Length") or 0)
            if t: prog = Progress(t)
            with open(filepath,"wb") as f:
                for c in r.iter_content(65536):
                    if c: f.write(c); (prog and prog.update(len(c)))
        if prog: prog.close()
        return True
    except Exception as e:
        if prog: prog.close()
        print(f"\n[❌] 下载失败: {e}"); return False

# ================= 封面 =================
def download_cover(pic_url, base):
    if not pic_url or not pic_url.startswith("http"): return False
    cp = f"{base}.jpg"
    if os.path.exists(cp) and os.path.getsize(cp) > 1024:
        print("[⏭] 封面已存在"); return True
    print("[*] 下载封面...")
    try:
        h = {"User-Agent": "okhttp/4.11.0"}
        if "kuwo.cn" in pic_url: h["Referer"] = "https://www.kuwo.cn/"
        r = requests.get(pic_url, headers=h, timeout=15, stream=True)
        if r.status_code == 200:
            with open(cp,"wb") as f:
                for c in r.iter_content(8192): f.write(c)
            if os.path.getsize(cp) < 1024: os.remove(cp); return False
            print(f"[✅] 封面: {cp}"); return True
    except: pass
    return False

# ================= 元数据嵌入 =================
def embed_metadata(path, song, lrc=None):
    if not HAS_MUTAGEN or not os.path.exists(path): return False
    ext = os.path.splitext(path)[1].lower()
    cd = None; cp = path.rsplit(".",1)[0]+".jpg"
    if os.path.exists(cp):
        with open(cp,"rb") as f: cd = f.read()
    try:
        if ext == ".flac":
            a = FLAC(path)
            a["TITLE"]=song.get("name",""); a["ARTIST"]=song.get("artist","")
            a["ALBUM"]=song.get("album","")
            if lrc: a["LYRICS"]=lrc
            if cd:
                p=Picture(); p.type=3; p.mime="image/jpeg"; p.data=cd
                a.clear_pictures(); a.add_picture(p)
            a.save()
        elif ext == ".mp3":
            a = ID3(path) if os.path.getsize(path)>0 else ID3()
            a["TIT2"]=TIT2(encoding=3,text=song.get("name",""))
            a["TPE1"]=TPE1(encoding=3,text=song.get("artist",""))
            a["TALB"]=TALB(encoding=3,text=song.get("album",""))
            if lrc: a["USLT"]=USLT(encoding=3,lang="eng",desc="",text=lrc)
            if cd: a["APIC"]=APIC(encoding=3,mime="image/jpeg",type=3,desc="Cover",data=cd)
            a.save()
        else: return False
        print(f"[✅] 元数据嵌入 ({ext.upper()})"); return True
    except Exception as e:
        print(f"[-] 嵌入失败: {e}"); return False

# ================= 预览 =================
def preview_song(song):
    name=song.get("name","?"); artist=song.get("artist","?"); rid=song.get("id")
    print(f"\n🎧 预览: {name} - {artist}")
    url, _ = get_play_url(rid, "128")
    if not url: url, _ = get_play_url(rid, "320")
    if not url: print("[-] 无预览链接"); return False
    player = None
    for cn, cmd in [("mpv",["mpv","--no-video","--quiet","--term-osd-bar","--no-resume-playback"]),
                     ("ffplay",["ffplay","-nodisp","-autoexit","-stats"])]:
        if shutil.which(cn): player=cmd; break
    if not player: print("[!] 未检测到播放器 (pkg install mpv)"); return False
    print(f"[*] {player[0]} (按 q 退出)")
    try: subprocess.run(player+[url])
    except KeyboardInterrupt: print("\n[⏹] 结束")
    return True

# ================= 核心流程 =================
def process_song(song):
    name=song.get("name","未知"); artist=song.get("artist","未知")
    rid=song.get("id"); pic=song.get("pic","")
    dur=song.get("duration",0); flac=song.get("hasLossless",False)
    sn = re.sub(r'[\\/*?:"<>|]',"",f"{artist} - {name}")
    base = os.path.join(SAVE_DIR, sn)
    mins, secs = divmod(dur, 60)
    print(f"\n🎵 {name} - {artist} (id={rid}, {mins}:{secs:02d}, {'FLAC' if flac else 'MP3'})")

    download_cover(pic, base)

    quality = "flac" if flac else "320"
    print(f"[*] 获取链接 ({quality})...")
    url, fmt = get_play_url(rid, quality)
    if not url and quality == "flac":
        print("[!] FLAC 失败, 尝试 320k...")
        url, fmt = get_play_url(rid, "320")
    if not url: print("[-] 无法获取链接"); return False
    print(f"[*] {url[:80]}...")

    ext = ".flac" if fmt == "flac" else ".mp3"
    ap = f"{base}{ext}"
    print(f"[*] 下载 ({ext.upper()})...")
    if not download_file(url, ap): return False
    print(f"[✅] 音频: {ap}")

    print("[*] 获取歌词...")
    lrc = get_lyrics(rid)
    if lrc:
        lp = f"{base}.lrc"
        with open(lp,"w",encoding="utf-8") as f: f.write(lrc)
        print(f"[✅] 歌词: {lp}")
    else:
        print("[-] 无歌词")

    if HAS_MUTAGEN:
        print("[*] 嵌入元数据...")
        embed_metadata(ap, song, lrc)
    return True

# ================= TUI =================
def clear(): sys.stdout.write("\033[2J\033[H"); sys.stdout.flush()
def dw(s): return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)
def fit(s, w):
    if dw(s)<=w: return s
    o,ww=[],0
    for c in s:
        cw=2 if unicodedata.east_asian_width(c) in "WF" else 1
        if ww+cw>w-1: break
        o.append(c); ww+=cw
    return "".join(o)+"…"

def render(songs, total, page, kw, msg=""):
    clear(); cols=shutil.get_terminal_size((80,24)).columns
    tp = math.ceil(total/PAGE_SIZE) if total else "?"
    print("="*62)
    print(f"🔍 {kw}   [暮光工具箱]   📄 第 {page}/{tp} 页 (共 {total} 首)")
    print("="*62)
    base = (page-1)*PAGE_SIZE
    for i, s in enumerate(songs):
        fl = "✅FLAC" if s.get("hasLossless") else "⚠️MP3 "
        dur = s.get("duration",0); m,sc = divmod(dur,60)
        pre = f"[{base+i+1:<3}] {fl} | "
        txt = fit(f"{s.get('artist','?')} - {s.get('name','?')} ({m}:{sc:02d})", cols-dw(pre))
        print(pre+txt)
    print("-"*62)
    print("命令: 序号=下载  v序号=预览  n=下一页  p=上一页  a=全下本页  q=退出")
    if msg: print(f">>> {msg}")

def result_loop(kw):
    page = 1
    songs, total = search(kw, page)
    if not songs: print("[-] 无结果"); return
    msg = ""
    while True:
        render(songs, total, page, kw, msg)
        ch = input("👉 命令: ").strip().lower().replace(" ","")
        if ch == 'q': return
        elif ch == 'n':
            if len(songs) < PAGE_SIZE: msg = "[-] 最后一页"
            else: page+=1; songs,total=search(kw,page); msg=""
        elif ch == 'p':
            if page<=1: msg="[-] 第一页"
            else: page-=1; songs,total=search(kw,page); msg=""
        elif ch == 'a':
            af = input("🔍 筛选作者 (留空全下): ").strip().lower()
            tg = [s for s in songs if not af or af in s.get("artist","").lower()]
            if not tg: msg="[-] 无匹配"; continue
            done=0
            for i,s in enumerate(tg):
                print(f"\n🚀 [{i+1}/{len(tg)}]")
                if process_song(s): done+=1
            msg=f"✅ 完成: {done}/{len(tg)}"
        elif ch.startswith('v') and ch[1:].isdigit():
            idx=int(ch[1:])-(page-1)*PAGE_SIZE-1
            if 0<=idx<len(songs): preview_song(songs[idx]); msg=f"🎧 {songs[idx].get('name')}"
            else: msg="[-] 无效"
        elif ch.isdigit():
            idx=int(ch)-(page-1)*PAGE_SIZE-1
            if 0<=idx<len(songs):
                ok=process_song(songs[idx])
                msg=f"✅ {songs[idx].get('name')}" if ok else "[-] 失败"
            else: msg="[-] 无效"
        else: msg="[-] 无效"

# ================= 批量 =================
def batch_mode(fp, only_lrc=False):
    print(f"[*] 批量: {fp}")
    with open(fp,"r",encoding="utf-8") as f: raw=f.readlines()
    tasks=[]
    for line in raw:
        line=line.strip()
        if not line or line.startswith("#"): continue
        if "---" in line: q,a=[x.strip() for x in line.split("---",1)]
        else: q,a=line,""
        q=re.sub(r'\.(mp3|flac|wav|ogg|m4a|aac)$','',q,flags=re.IGNORECASE).strip()
        if q: tasks.append((q,a))
    total=len(tasks)
    if only_lrc:
        print(f"[*] 📋 {total} 任务, 4核并行歌词\n")
        lock=threading.Lock(); ok_n=fail_n=0
        def lw(task):
            nonlocal ok_n,fail_n; q,a=task
            songs,_=search(q)
            if not songs:
                with lock: print(f"[-] 无结果: {q}"); fail_n+=1; return
            tgt=None
            if a:
                for s in songs:
                    if a.lower() in s.get("artist","").lower(): tgt=s; break
            else: tgt=songs[0]
            if not tgt:
                with lock: print(f"[-] 未匹配: {q}"); fail_n+=1; return
            sn=re.sub(r'[\\/*?:"<>|]',"",f"{tgt.get('artist','?')} - {tgt.get('name','?')}")
            lp=os.path.join(SAVE_DIR,f"{sn}.lrc")
            if os.path.exists(lp) and os.path.getsize(lp)>0:
                with lock: print(f"[⏭] 已有: {sn}.lrc"); return
            lt=get_lyrics(tgt.get("id"))
            if lt:
                with open(lp,"w",encoding="utf-8") as f: f.write(lt)
                with lock: print(f"[✅] {sn}.lrc"); ok_n+=1
            else:
                with lock: print(f"[-] 无歌词: {sn}"); fail_n+=1
        with ThreadPoolExecutor(max_workers=4) as ex: list(ex.map(lw,tasks))
        print(f"\n🎉 歌词完成! 成功:{ok_n} 失败:{fail_n}"); return

    print(f"[*] 📋 {total} 任务\n")
    ok_n=fail_n=0
    for i,(q,a) in enumerate(tasks,1):
        print(f"\n🚀 [{i}/{total}] 成功:{ok_n} 失败:{fail_n}")
        print(f"🔍 {q} (作者: {a or '无'})")
        songs,_=search(q)
        if not songs: fail_n+=1; continue
        dl=False
        if a:
            for s in songs:
                if a.lower() in s.get("artist","").lower():
                    if process_song(s): dl=True; break
            if not dl: print(f"[-] 未匹配 '{a}'")
        else:
            if process_song(songs[0]): dl=True
        if dl: ok_n+=1
        else: fail_n+=1
    print(f"\n🎉 完成! 成功:{ok_n} 失败:{fail_n}")

# ================= 入口 =================
def main():
    print("="*55)
    print(" 🎵 暮光工具箱音乐下载器 (全接口破解版)")
    print(f" 搜索: {SEARCH_URL}")
    print(f" 播放: nmobi.kuwo.cn (convert_url_with_sign)")
    print(f" 歌词: mlyric.kuwo.cn (Base64 LRC)")
    print(f" 签名: MD5(\"{SALT}\" + ts + \"1\")")
    print(f" 输出: {SAVE_DIR}")
    print(f" 元数据: {'✅ mutagen' if HAS_MUTAGEN else '❌ 未安装'}")
    print("="*55)

    # 签名验证
    test_ts = "1792859066146"
    test_sign = hashlib.md5(f"{SALT}{test_ts}1".encode()).hexdigest()
    expected = "6c8bc9ad59b1cbb100a2e2e72b965eac"
    print(f"\n[*] 签名验证: {'✅ 通过' if test_sign==expected else '❌ 失败'}")

    args = sys.argv[1:]
    if not args:
        while True:
            kw = input("\n🔍 搜索 (q退出): ").strip()
            if kw.lower()=='q': break
            result_loop(kw)
    elif os.path.isfile(args[0]):
        only_lrc = len(args)>1 and args[1].lower()=='lrc'
        batch_mode(args[0], only_lrc)
    else:
        kw = args[0]
        artist = args[1].strip() if len(args)>1 else ""
        if artist:
            print(f"[*] 直下: {kw} ({artist})")
            songs,_ = search(kw)
            matched = [s for s in songs if artist.lower() in s.get("artist","").lower()]
            if matched: process_song(matched[0])
            else: print(f"[-] 未匹配 '{artist}'")
        else:
            result_loop(kw)

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: print("\n👋 已中断")