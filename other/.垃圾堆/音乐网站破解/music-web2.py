#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D-kaiser Music Web Console
逆向来源: 暮光工具箱 v4.0.9 APK (com.twilight.toolsapp)
  - 签名: sjb.t0() → MD5("MusicKillerNativeSalt" + ts + "1")
  - 搜索: Luc6.n() → http://119.3.221.4:8002/search
  - 播放: nmobi.kuwo.cn/mobi.s (convert_url_with_sign) [抓包确认]
  - 歌词: mlyric.kuwo.cn/mobi.s (Base64 LRC) [抓包确认]
启动: python music-web.py
访问: http://localhost:8888
"""

import os, re, sys, time, json, math, hashlib, base64, threading, unicodedata
import urllib.parse, shutil, subprocess, queue, logging
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor
import requests

try:
    from mutagen.flac import FLAC, Picture
    from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC, USLT
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False

# ================= 配置 =================
PORT = 8888
SAVE_DIR = "/storage/emulated/0/termux/MusicDownloads"
THREADS = 8
PAGE_SIZE = 20

# 暮光工具箱接口 (APK逆向 + 抓包验证)
MG_SEARCH   = "http://119.3.221.4:8002/search"
MG_PLAY     = "http://nmobi.kuwo.cn/mobi.s"       # 抓包确认的播放接口
MG_LYRIC    = "http://mlyric.kuwo.cn/mobi.s"      # 抓包确认的歌词接口
MG_SALT     = "MusicKillerNativeSalt"              # sjb.t0() 硬编码盐值
MG_SOURCE   = "kwplayerhd_ar_6.6.6.6_tianbao_T1A_qirui.apk"

# flac.music.hi.cn 备用
HI_COOKIE_FILE = "/storage/emulated/0/termux/音乐Cookie.txt"
HI_SEARCH = "https://flac.music.hi.cn/ajax.php?act=search"
HI_GETURL = "https://flac.music.hi.cn/ajax.php?act=getUrl"
HI_LYRIC_ACTS = ["lyric", "lrc", "getLyric", "getLrc"]
HI_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36",
    "Referer": "https://flac.music.hi.cn/",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Cookie": ""
}

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except: pass
try: os.makedirs(SAVE_DIR, exist_ok=True)
except: SAVE_DIR = "./MusicDownloads"; os.makedirs(SAVE_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s', datefmt='%H:%M:%S')
log_queue = queue.Queue(maxsize=1000)
class QH(logging.Handler):
    def emit(self, r):
        try:
            if log_queue.full(): log_queue.get_nowait()
            log_queue.put(self.format(r))
        except: pass
logging.getLogger().addHandler(QH())
def log(m): logging.info(m)

# ================= 暮光签名 (sjb.t0 逆向) =================
def mg_headers():
    ts = str(int(time.time() * 1000))
    sign = hashlib.md5(f"{MG_SALT}{ts}1".encode()).hexdigest()
    return {"Version":"1","Platform":"android","Timestamp":ts,"Sign":sign,"User-Agent":"okhttp/4.11.0"}

# ================= 暮光搜索 (Luc6.n 逆向) =================
def mg_search(keyword, page=1, size=PAGE_SIZE):
    url = f"{MG_SEARCH}?keyword={urllib.parse.quote(keyword)}&pageNo={page}&pageSize={size}"
    try:
        j = requests.get(url, headers=mg_headers(), timeout=15).json()
        if j.get("code") != 200: return [], 0
        d = j.get("data", {})
        songs = []
        for s in d.get("data", []):
            s["pic_url"] = s.get("pic", "")
            s["source_tag"] = "muguang"
            s["minfo"] = [{"format":"flac"}] if s.get("hasLossless") else [{"format":"mp3"}]
            songs.append(s)
        return songs, d.get("total", 0)
    except Exception as e:
        log(f"[-] 暮光搜索异常: {e}"); return [], 0

# ================= 暮光播放链接 (抓包确认: nmobi.kuwo.cn) =================
def mg_play_url(rid, quality="flac"):
    br = {"flac":"2000kflac","320":"320kmp3","128":"128kmp3"}.get(quality,"2000kflac")
    params = {"f":"web","user":"0","source":MG_SOURCE,"type":"convert_url_with_sign","rid":str(rid),"br":br}
    try:
        j = requests.get(MG_PLAY, params=params, headers={"User-Agent":"okhttp/4.11.0","Accept-Encoding":"gzip"}, timeout=15).json()
        if j.get("code") == 200:
            d = j.get("data",{})
            return d.get("url"), d.get("format", quality)
        return None, None
    except Exception as e:
        log(f"[-] 播放链接异常: {e}"); return None, None

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
    has_kana = lambda t: bool(re.search(r'[\u3040-\u30ff]', t))
    has_han  = lambda t: bool(re.search(r'[\u4e00-\u9fff]', t))
    for i in range(1, len(lines)-1):
        tp, tc, tn = lines[i-1][0], lines[i][0], lines[i+1][0]
        if not (tp and tc and tn): continue
        if tc == tn and tc != tp:
            a, b = lines[i-1][1], lines[i][1]
            if (has_han(b) and not has_kana(b) and has_kana(a)) or \
               (has_kana(b) and has_han(a) and not has_kana(a)):
                lines[i][0] = tp
    return '\n'.join(t if ts is None else f"[{ts}]{t}" for ts, t in lines)

# ================= 暮光歌词 (mlyric.kuwo.cn Base64) =================
def mg_lyrics(rid):
    params = {"f":"web","type":"lyric","lrcx":"1","rid":str(rid),"encode":"utf8"}
    try:
        raw = requests.get(MG_LYRIC, params=params, headers={
            "User-Agent":"Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/120.0.6099.144 Mobile Safari/537.36",
            "Accept-Encoding":"gzip"
        }, timeout=15).text.strip()
        if not raw: return None
        # 尝试JSON解析 (抓包显示可能是 {"code":0,"data":"..."})
        lrc_text = None
        try:
            j = json.loads(raw)
            if j.get("code") == 0:
                lrc_text = j.get("data","")
        except:
            pass
        # 如果不是JSON，尝试Base64解码
        if not lrc_text:
            try:
                decoded = base64.b64decode(raw).decode("utf-8", errors="replace")
                idx = decoded.find("[")
                if idx >= 0: lrc_text = decoded[idx:]
            except:
                if "[" in raw and "]" in raw: lrc_text = raw
        if not lrc_text: return None
        return format_lrc(lrc_text)
    except Exception as e:
        log(f"[-] 歌词异常: {e}"); return None

# ================= flac.music.hi.cn 备用 =================
def hi_load_cookie():
    if os.path.exists(HI_COOKIE_FILE):
        try:
            with open(HI_COOKIE_FILE,"r",encoding="utf-8") as f: return f.read().strip()
        except: return ""
    return ""
def hi_save_cookie(c):
    try:
        os.makedirs(os.path.dirname(HI_COOKIE_FILE),exist_ok=True)
        with open(HI_COOKIE_FILE,"w",encoding="utf-8") as f: f.write(c.strip())
    except: pass
def hi_post(url, payload):
    global HI_HEADERS
    clean = {k:str(v).replace('\u3000',' ').replace('\u200b','').strip() for k,v in payload.items() if v is not None}
    res = requests.post(url, data=urllib.parse.urlencode(clean).encode(), headers=HI_HEADERS, timeout=15)
    if res.status_code == 468 or "challenge" in res.text.lower():
        log("[⚠️ WAF拦截] 请在网页更新Cookie"); return None
    return res
def hi_search(keyword, page=1):
    try:
        res = hi_post(HI_SEARCH, {"keyword":keyword,"type":"kuwo","page":str(page)})
        if not res or res.status_code!=200: return [],0
        j = res.json()
        if j.get("code")!=0: return [],0
        return j.get("data",{}).get("list",[]), 0
    except: return [],0
def hi_play_url(song, low=False):
    minfo = song.get("minfo",[])
    fmt, br = "flac", "2000"
    if low:
        for want in ("128","320"):
            for m in minfo:
                if m.get("format")=="mp3" and str(m.get("bitrate"))==want: fmt,br="mp3",want; break
            else: continue; break
        else:
            for m in minfo:
                if m.get("format")=="mp3": fmt,br="mp3",str(m.get("bitrate")); break
            else: return None,None
    else:
        if not any(m.get("format")=="flac" for m in minfo):
            if minfo: fmt,br=minfo[0].get("format","mp3"),minfo[0].get("bitrate","320")
            else: return None,None
    payload = {"platform":"kuwo","songid":str(song.get("id")),"format":fmt,"bitrate":str(br),
               "time":str(song.get("time")),"sign":song.get("sign")}
    try:
        res = hi_post(HI_GETURL, payload)
        if res and res.status_code==200:
            j = res.json()
            if j.get("code")==0:
                d = j.get("data")
                if isinstance(d,str): return d or None, fmt
                if isinstance(d,dict): return d.get("url"), fmt
        return None,None
    except: return None,None
def hi_lyrics(song):
    payload = {"platform":"kuwo","songid":str(song.get("id")),"time":str(song.get("time")),"sign":song.get("sign")}
    for act in HI_LYRIC_ACTS:
        try:
            res = hi_post(f"https://flac.music.hi.cn/ajax.php?act={act}", payload)
            if not res or res.status_code!=200 or not res.text.strip(): continue
            lrc = None
            try:
                j = res.json()
                if j.get("code")==0:
                    d = j.get("data")
                    if isinstance(d,str): lrc=d
                    elif isinstance(d,dict): lrc=d.get("lyric") or d.get("lrc") or d.get("content")
            except ValueError: lrc=res.text
            if lrc and isinstance(lrc,str) and not lrc.strip().startswith('{') and '[' in lrc:
                return format_lrc(lrc)
        except: continue
    return None

# ================= 统一路由 =================
def search_music(kw, src="muguang", pg=1):
    return mg_search(kw,pg) if src=="muguang" else hi_search(kw,pg)

def get_play_url(song, src="muguang", low=False, quality=None):
    if song.get("source_tag")=="muguang" or src=="muguang":
        rid = song.get("id")
        if quality: return mg_play_url(rid, quality)
        if low: return mg_play_url(rid, "128")
        return mg_play_url(rid, "flac" if song.get("hasLossless") else "320")
    return hi_play_url(song, low)

def get_lyrics(song, src="muguang"):
    if song.get("source_tag")=="muguang" or src=="muguang":
        return mg_lyrics(song.get("id"))
    return hi_lyrics(song)

# ================= 下载引擎 =================
class Progress:
    def __init__(s,total,desc="下载"): s.total=total;s.done=0;s.desc=desc;s.lock=threading.Lock();s.start=time.time()
    def update(s,n):
        with s.lock: s.done+=n; s._draw()
    def _draw(s):
        pct=min(s.done/s.total,1) if s.total else 0
        w=24;filled=int(w*pct);bar='█'*filled+'░'*(w-filled)
        el=max(time.time()-s.start,0.001);sp=s.done/el;eta=int((s.total-s.done)/sp) if sp>0 else 0
        sys.stdout.write(f"\r{s.desc} [{bar}] {pct*100:5.1f}% {s.done//1048576}/{s.total//1048576}MB {sp/1048576:.1f}MB/s ETA {eta}s ");sys.stdout.flush()
    def close(s): sys.stdout.write("\n");sys.stdout.flush()

def download_file(url, filepath):
    hd={"User-Agent":"AndroidDownloadManager/10 (Linux; U; Android 10)"}
    total,rok=0,False
    try:
        h=requests.head(url,headers=hd,timeout=15,allow_redirects=True)
        total=int(h.headers.get("Content-Length") or 0)
        rok=(h.headers.get("Accept-Ranges","none") or "").lower()!="none"
    except: pass
    if total>2*1048576 and rok:
        log(f"[*] 🚀 {THREADS}线程分片...")
        chunk=max(1048576,(total+THREADS-1)//THREADS);ranges,s=[],0
        while s<total: e=min(total-1,s+chunk-1);ranges.append((s,e));s=e+1
        parts=[f"{filepath}.part{i}" for i in range(len(ranges))]
        prog=Progress(total);ok=True
        def worker(i,s,e):
            nonlocal ok
            h2=dict(hd);h2["Range"]=f"bytes={s}-{e}"
            try:
                r=requests.get(url,headers=h2,stream=True,timeout=30)
                if r.status_code not in(200,206):ok=False;return
                with open(parts[i],"wb") as f:
                    for c in r.iter_content(65536):
                        if c:f.write(c);prog.update(len(c))
            except:ok=False
        with ThreadPoolExecutor(max_workers=len(ranges)) as ex:
            futs=[ex.submit(worker,i,s,e) for i,(s,e) in enumerate(ranges)]
            for f in futs:
                try:f.result()
                except:ok=False
        prog.close()
        if not ok:
            for p in parts:
                if os.path.exists(p):
                    try:os.remove(p)
                    except:pass
            return False
        tmp=filepath+".part"
        with open(tmp,"wb") as out:
            for p in parts:
                with open(p,"rb") as fin:
                    while True:
                        b=fin.read(1048576)
                        if not b:break
                        out.write(b)
                os.remove(p)
        os.replace(tmp,filepath);return True
    log("[*] 🐢 单线程...")
    prog=None
    try:
        with requests.get(url,headers=hd,stream=True,timeout=30) as r:
            r.raise_for_status();t=int(r.headers.get("Content-Length") or 0)
            if t:prog=Progress(t)
            with open(filepath,"wb") as f:
                for c in r.iter_content(65536):
                    if c:f.write(c);(prog and prog.update(len(c)))
        if prog:prog.close()
        return True
    except Exception as e:
        if prog:prog.close()
        log(f"[❌] 下载失败: {e}");return False

def download_cover(pic_url,base):
    if not pic_url or not pic_url.startswith("http"):return False
    cp=f"{base}.jpg"
    if os.path.exists(cp) and os.path.getsize(cp)>1024:return True
    try:
        h={"User-Agent":"okhttp/4.11.0"}
        if "kuwo.cn" in pic_url:h["Referer"]="https://www.kuwo.cn/"
        r=requests.get(pic_url,headers=h,timeout=15,stream=True)
        if r.status_code==200:
            with open(cp,"wb") as f:
                for c in r.iter_content(8192):f.write(c)
            if os.path.getsize(cp)<1024:os.remove(cp);return False
            return True
    except:pass
    return False

def embed_metadata(path,song,lrc=None):
    if not HAS_MUTAGEN or not os.path.exists(path):return False
    ext=os.path.splitext(path)[1].lower()
    cd=None;cp=path.rsplit(".",1)[0]+".jpg"
    if os.path.exists(cp):
        with open(cp,"rb") as f:cd=f.read()
    try:
        if ext==".flac":
            a=FLAC(path);a["TITLE"]=song.get("name","");a["ARTIST"]=song.get("artist","");a["ALBUM"]=song.get("album","")
            if lrc:a["LYRICS"]=lrc
            if cd:p=Picture();p.type=3;p.mime="image/jpeg";p.data=cd;a.clear_pictures();a.add_picture(p)
            a.save()
        elif ext==".mp3":
            a=ID3(path) if os.path.getsize(path)>0 else ID3()
            a["TIT2"]=TIT2(encoding=3,text=song.get("name",""));a["TPE1"]=TPE1(encoding=3,text=song.get("artist",""))
            a["TALB"]=TALB(encoding=3,text=song.get("album",""))
            if lrc:a["USLT"]=USLT(encoding=3,lang="eng",desc="",text=lrc)
            if cd:a["APIC"]=APIC(encoding=3,mime="image/jpeg",type=3,desc="Cover",data=cd)
            a.save()
        else:return False
        return True
    except:return False

# ================= 下载管理器 =================
class DownloadManager:
    def __init__(s):s.lock=threading.Lock();s.pending=[];s.completed=[];s.executor=ThreadPoolExecutor(max_workers=2);s._id=0;s._keys=set();s._cancel={}
    def add(s,song,src):
        sid=str(song.get("id",""));key=(sid,src)
        with s.lock:
            if key in s._keys:return None
            s._keys.add(key);s._id+=1;tid=s._id;evt=threading.Event();s._cancel[tid]=evt
            s.pending.append({"id":tid,"key":key,"name":song.get("name","?"),"artist":song.get("artist","?"),"status":"等待中"})
        s.executor.submit(s._work,tid,key,evt,song,src);return tid
    def _work(s,tid,key,evt,song,src):
        name=song.get("name","?");artist=song.get("artist","?")
        sn=re.sub(r'[\\/*?:"<>|]',"",f"{artist} - {name}");base=os.path.join(SAVE_DIR,sn)
        with s.lock:
            for t in s.pending:
                if t["id"]==tid:t["status"]="下载中";break
        if evt.is_set():s._fin(tid,key,name,artist,None,"已取消");return
        log(f"🎵 {name} - {artist}")
        download_cover(song.get("pic_url",""),base)
        if evt.is_set():s._fin(tid,key,name,artist,None,"已取消");return
        url,fmt=get_play_url(song,src)
        if not url:
            for q in("320","128"):
                url,fmt=get_play_url(song,src,quality=q);
                if url:break
        if not url:log(f"[-] 无链接: {name}");s._fin(tid,key,name,artist,None,"无链接");return
        ext=".flac" if fmt=="flac" else ".mp3";ap=f"{base}{ext}"
        if not download_file(url,ap):s._fin(tid,key,name,artist,None,"下载失败");return
        log(f"[✅] {sn}{ext}")
        if evt.is_set():
            if os.path.exists(ap):
                try:os.remove(ap)
                except:pass
            s._fin(tid,key,name,artist,None,"已取消");return
        lrc=get_lyrics(song,src)
        if lrc:
            with open(f"{base}.lrc","w",encoding="utf-8") as f:f.write(lrc)
        if HAS_MUTAGEN:embed_metadata(ap,song,lrc)
        log(f"[🏁] {name}");s._fin(tid,key,name,artist,ap,"成功")
    def _fin(s,tid,key,name,artist,path,status):
        with s.lock:s._keys.discard(key);s._cancel.pop(tid,None);s.pending=[t for t in s.pending if t["id"]!=tid]
        s.completed.insert(0,{"id":tid,"name":name,"artist":artist,"path":path,"status":status,"time":time.strftime("%H:%M:%S")})
    def status(s):
        with s.lock:return{"pending":list(s.pending),"completed":list(s.completed[:50])}
    def remove(s,tid):
        with s.lock:
            evt=s._cancel.get(tid)
            if evt:evt.set()
            for t in s.pending:
                if t["id"]==tid:s._keys.discard(t.get("key"))
            s.pending=[t for t in s.pending if t["id"]!=tid]
    def clear_done(s):
        with s.lock:s.completed.clear()

dl_mgr=DownloadManager()

# ================= Web UI =================
HTML=r"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>D-kaiser Music</title>
<style>
:root{--bg:#0f0f1a;--card:#1a1a2e;--pri:#16213e;--acc:#e94560;--txt:#eee;--sub:#888;--grn:#2ecc71;--org:#f39c12;}
*{margin:0;padding:0;box-sizing:border-box;}body{background:var(--bg);color:var(--txt);font-family:-apple-system,sans-serif;padding:15px;padding-bottom:100px;}
.hd{text-align:center;margin-bottom:15px;}.hd h1{color:var(--acc);font-size:1.4em;}
.src-bar{max-width:700px;margin:0 auto 10px;display:flex;gap:8px;align-items:center;justify-content:center;}
.src-bar button{padding:6px 14px;border:2px solid var(--pri);border-radius:20px;background:transparent;color:var(--sub);cursor:pointer;font-size:13px;transition:.2s;}
.src-bar button.active{border-color:var(--acc);color:var(--acc);background:rgba(233,69,96,.1);}
.sb{display:flex;gap:8px;max-width:700px;margin:0 auto 12px;}
.sb input{flex:1;padding:10px 14px;border:none;border-radius:10px;background:var(--card);color:#fff;font-size:14px;}
.sb button{padding:10px 18px;border:none;border-radius:10px;background:var(--acc);color:#fff;cursor:pointer;font-weight:bold;font-size:14px;}
.acts{max-width:700px;margin:0 auto 8px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;}
.acts button{padding:5px 12px;border:none;border-radius:6px;background:var(--pri);color:#fff;cursor:pointer;font-size:12px;}
.acts button:hover{background:var(--acc);}.acts button:disabled{opacity:.4;cursor:not-allowed;}
.pg{font-size:12px;color:var(--sub);margin-left:auto;}
.sl{max-width:700px;margin:0 auto;display:flex;flex-direction:column;gap:6px;}
.si{display:flex;align-items:center;gap:10px;background:var(--card);padding:8px 10px;border-radius:10px;transition:.2s;}
.si:hover{background:var(--pri);}.si input[type=checkbox]{width:16px;height:16px;accent-color:var(--acc);flex-shrink:0;}
.sc{width:38px;height:38px;border-radius:6px;object-fit:cover;background:#333;flex-shrink:0;}
.sf{flex:1;min-width:0;}.sn{font-weight:bold;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:13px;}
.sa{font-size:11px;color:var(--sub);margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.tg{font-size:10px;padding:1px 5px;border-radius:3px;margin-left:4px;}
.tg-f{background:var(--grn);color:#000;}.tg-m{background:var(--org);color:#000;}
.bs{padding:4px 8px;border:none;border-radius:5px;font-size:11px;cursor:pointer;color:#fff;flex-shrink:0;}
.bp{background:#3498db;}.bd{background:var(--grn);}
.toast{position:fixed;top:15px;left:50%;transform:translateX(-50%);background:var(--acc);color:#fff;padding:8px 18px;border-radius:8px;font-size:13px;z-index:300;opacity:0;transition:opacity .3s;pointer-events:none;}
.toast.show{opacity:1;}
.dp{position:fixed;top:0;right:-340px;width:330px;height:100%;background:var(--card);z-index:250;transition:right .3s;box-shadow:-5px 0 20px rgba(0,0,0,.5);display:flex;flex-direction:column;}
.dp.active{right:0;}.dp-h{padding:12px;border-bottom:1px solid var(--pri);display:flex;justify-content:space-between;align-items:center;}
.dp-h h3{font-size:15px;}.dp-x{font-size:20px;cursor:pointer;color:var(--sub);}
.dp-b{flex:1;overflow-y:auto;padding:8px;}.dp-t{font-size:11px;color:var(--sub);margin:8px 0 4px;text-transform:uppercase;}
.di{display:flex;align-items:center;gap:6px;padding:6px;border-radius:5px;background:rgba(255,255,255,.03);margin-bottom:3px;font-size:11px;}
.di-n{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}.di-s{color:var(--acc);font-size:10px;flex-shrink:0;}
.di-d{color:#e74c3c;cursor:pointer;font-size:13px;flex-shrink:0;padding:0 3px;}
.dp-clr{margin:8px;padding:6px;border:none;border-radius:5px;background:#e74c3c;color:#fff;cursor:pointer;font-size:11px;width:calc(100% - 16px);}
.pb{position:fixed;bottom:0;left:0;right:0;background:var(--card);border-top:1px solid var(--pri);padding:8px 15px;display:none;align-items:center;gap:10px;z-index:100;cursor:pointer;}
.pb.active{display:flex;}.pb-c{width:42px;height:42px;border-radius:6px;object-fit:cover;background:#333;}
.pb-i{flex:1;min-width:0;}.pb-t{font-size:13px;font-weight:bold;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.pb-s{font-size:11px;color:var(--sub);margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.fp{position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(10,10,20,.97);z-index:200;display:none;flex-direction:column;align-items:center;padding:15px;backdrop-filter:blur(10px);}
.fp.active{display:flex;}.fp-x{position:absolute;top:12px;right:15px;font-size:26px;color:var(--sub);cursor:pointer;z-index:201;}
.fp-c{width:140px;height:140px;border-radius:12px;object-fit:cover;background:#333;margin-top:25px;box-shadow:0 8px 30px rgba(0,0,0,.5);}
.fp-t{text-align:center;margin-top:10px;font-size:16px;font-weight:bold;max-width:90%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.fp-a{text-align:center;margin-top:3px;font-size:12px;color:var(--sub);}
.fp-l{flex:1;width:100%;max-width:600px;margin-top:12px;overflow-y:auto;text-align:center;mask-image:linear-gradient(to bottom,transparent 0%,black 15%,black 85%,transparent 100%);-webkit-mask-image:linear-gradient(to bottom,transparent 0%,black 15%,black 85%,transparent 100%);}
.fp-li{padding:4px 0;font-size:13px;color:var(--sub);transition:all .3s;line-height:1.5;}
.fp-li.active{color:var(--acc);font-size:15px;font-weight:bold;transform:scale(1.05);}
.fp-au{width:100%;max-width:500px;margin-top:8px;margin-bottom:12px;height:34px;}
.lp{max-width:700px;margin:12px auto 8px;background:var(--card);border-radius:8px;padding:10px;font-family:monospace;font-size:11px;max-height:100px;overflow-y:auto;color:var(--sub);}
.lp-p{color:var(--grn);font-weight:bold;}
.cb{max-width:700px;margin:0 auto 10px;display:flex;gap:6px;}
.cb input{flex:1;padding:6px;border:none;border-radius:5px;background:var(--card);color:#fff;font-size:11px;}
.cb button{padding:6px 10px;border:none;border-radius:5px;background:var(--acc);color:#fff;cursor:pointer;font-size:11px;}
.dl-btn{position:relative;}.dl-btn .badge{position:absolute;top:-4px;right:-4px;background:var(--acc);color:#fff;font-size:9px;width:14px;height:14px;border-radius:50%;display:flex;align-items:center;justify-content:center;}
</style></head><body>
<div class="toast" id="toast"></div>
<div class="hd"><h1>🎵 D-kaiser Music</h1></div>
<div class="src-bar">
<button id="srcMg" class="active" onclick="setSrc('muguang')">kuwo暮光</button>
<button id="srcHi" onclick="setSrc('hi')">酷我聚合</button>
<button class="dl-btn" onclick="toggleDp()">📥 下载管理<span class="badge" id="dlB" style="display:none">0</span></button>
</div>
<div class="cb"><input id="ckIn" placeholder="酷我聚合 Cookie (仅酷我聚合源需要)"><button onclick="saveCk()">💾 保存</button></div>
<div class="sb"><input id="kw" placeholder="输入歌名或歌手..." onkeydown="if(event.key==='Enter')doSearch()"><button onclick="doSearch()">🔍 搜索</button></div>
<div class="acts">
<button onclick="dlSel()">⬇️ 下载选中</button><button onclick="togAll()">☑️ 全选</button>
<button id="prevB" onclick="chgPg(-1)" disabled>◀ 上一页</button><button id="nextB" onclick="chgPg(1)" disabled>下一页 ▶</button>
<span class="pg" id="pgI"></span>
</div>
<div class="sl" id="list"></div>
<div class="lp" id="logs"></div>
<div class="dp" id="dp"><div class="dp-h"><h3>📥 下载管理</h3><div class="dp-x" onclick="toggleDp()">✕</div></div><div class="dp-b" id="dpB"></div></div>
<div class="pb" id="pBar" onclick="openFp()"><img class="pb-c" id="pbC"><div class="pb-i"><div class="pb-t" id="pbT"></div><div class="pb-s" id="pbS"></div></div><audio id="au" preload="auto"></audio></div>
<div class="fp" id="fp"><div class="fp-x" onclick="closeFp()">✕</div><img class="fp-c" id="fpC"><div class="fp-t" id="fpT"></div><div class="fp-a" id="fpA"></div><div class="fp-l" id="fpL"></div><audio class="fp-au" id="fpAu" controls preload="auto"></audio></div>
<script>
let songs=[],lrcLines=[],curIdx=-1,curPg=1,curKw='',curSrc='muguang',total=0;
const au=document.getElementById('au'),fpAu=document.getElementById('fpAu');
function toast(m){let t=document.getElementById('toast');t.textContent=m;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2000);}
function setSrc(s){curSrc=s;document.getElementById('srcMg').className=s==='muguang'?'active':'';document.getElementById('srcHi').className=s==='hi'?'active':'';}
function doSearch(pg=1){
  let kw=document.getElementById('kw').value.trim();
  if(!kw&&pg===1)return;if(pg===1)curKw=kw;curPg=pg;
  document.getElementById('pgI').textContent=`第 ${pg} 页 · 搜索中...`;
  fetch('/api/search',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({keyword:curKw,source:curSrc,page:pg})})
  .then(r=>r.json()).then(d=>{songs=d.songs||[];total=d.total||0;render();
    document.getElementById('pgI').textContent=`第 ${pg} 页 · ${total?Math.ceil(total/20)+'页 ':''}${songs.length} 首`;
    document.getElementById('prevB').disabled=pg<=1;document.getElementById('nextB').disabled=songs.length<20;});
}
function chgPg(d){doSearch(curPg+d);}
function render(){
  let el=document.getElementById('list');el.innerHTML='';
  songs.forEach((s,i)=>{
    let fl=(s.minfo||[]).some(m=>m.format==='flac');
    let tg=fl?'<span class="tg tg-f">FLAC</span>':'<span class="tg tg-m">MP3</span>';
    let dur=s.duration||0;let mn=Math.floor(dur/60),sc=dur%60;
    el.innerHTML+=`<div class="si"><input type="checkbox" data-i="${i}"><img class="sc" src="${esc(s.pic_url||'')}" onerror="this.style.display='none'"><div class="sf"><div class="sn">${esc(s.name)}${tg}</div><div class="sa">${esc(s.artist)} · ${mn}:${String(sc).padStart(2,'0')}</div></div><button class="bs bp" onclick="event.stopPropagation();preview(${i})">▶</button><button class="bs bd" onclick="event.stopPropagation();dlOne(${i})">⬇</button></div>`;
  });
}
function esc(s){return(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function togAll(){let c=[...document.querySelectorAll('.si input[type=checkbox]')];let a=c.every(x=>x.checked);c.forEach(x=>x.checked=!a);}
function dlSel(){let ids=[...document.querySelectorAll('.si input:checked')].map(c=>+c.dataset.i);if(!ids.length)return toast('请先勾选');
  fetch('/api/download',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({indices:ids,source:curSrc})}).then(()=>toast(`已加入 ${ids.length} 首`));}
function dlOne(i){fetch('/api/download',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({indices:[i],source:curSrc})}).then(()=>toast('已加入'));}
function preview(i){
  curIdx=i;let s=songs[i];
  document.getElementById('pbT').textContent=s.name;document.getElementById('pbS').textContent=s.artist;
  document.getElementById('pbC').src=s.pic_url||'';document.getElementById('pBar').classList.add('active');
  fetch('/api/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({index:i,source:curSrc})})
  .then(r=>r.json()).then(d=>{if(d.url){au.src=d.url;au.play();}else{document.getElementById('pbS').textContent='无预览资源';}});
  fetch('/api/lyric',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({index:i,source:curSrc})})
  .then(r=>r.json()).then(d=>{lrcLines=d.lrc?parseLrc(d.lrc):[];});
}
function parseLrc(t){return t.split('\n').map(l=>{let m=l.match(/^\[(\d+):(\d+\.\d+)\](.*)$/);if(m)return{time:+m[1]*60+parseFloat(m[2]),text:m[3]};return null;}).filter(Boolean).sort((a,b)=>a.time-b.time);}
function openFp(){
  if(curIdx<0)return;let s=songs[curIdx];
  document.getElementById('fpT').textContent=s.name;document.getElementById('fpA').textContent=s.artist;
  document.getElementById('fpC').src=s.pic_url||'';
  if(fpAu.src!==au.src)fpAu.src=au.src;fpAu.currentTime=au.currentTime;fpAu.play().catch(()=>{});au.pause();
  let box=document.getElementById('fpL');box.innerHTML='';
  lrcLines.forEach(l=>{let d=document.createElement('div');d.className='fp-li';d.textContent=l.text||'♪';box.appendChild(d);});
  document.getElementById('fp').classList.add('active');
}
function closeFp(){document.getElementById('fp').classList.remove('active');au.currentTime=fpAu.currentTime;au.play().catch(()=>{});fpAu.pause();}
fpAu.addEventListener('timeupdate',()=>{
  if(!lrcLines.length)return;let t=fpAu.currentTime,ai=0;
  for(let i=lrcLines.length-1;i>=0;i--){if(lrcLines[i].time<=t){ai=i;break;}}
  document.querySelectorAll('.fp-li').forEach((el,i)=>{if(i===ai){el.classList.add('active');el.scrollIntoView({behavior:'smooth',block:'center'});}else{el.classList.remove('active');}});
});
fpAu.addEventListener('ended',()=>{if(curIdx<songs.length-1){preview(curIdx+1);setTimeout(openFp,300);}});
function toggleDp(){document.getElementById('dp').classList.toggle('active');refreshDp();}
function refreshDp(){
  fetch('/api/dl-status').then(r=>r.json()).then(d=>{
    let h='<div class="dp-t">计划中 ('+d.pending.length+')</div>';
    if(!d.pending.length)h+='<div style="font-size:11px;color:var(--sub);padding:6px;">暂无任务</div>';
    d.pending.forEach(t=>{h+=`<div class="di"><div class="di-n">${esc(t.name)} - ${esc(t.artist)}</div><div class="di-s">${t.status}</div><div class="di-d" onclick="delP(${t.id})">✕</div></div>`;});
    h+='<div class="dp-t">已完成 ('+d.completed.length+')</div>';
    if(!d.completed.length)h+='<div style="font-size:11px;color:var(--sub);padding:6px;">暂无记录</div>';
    d.completed.forEach(t=>{h+=`<div class="di"><div class="di-n">${esc(t.name)} - ${esc(t.artist)}</div><div class="di-s" style="color:${t.status==='成功'?'var(--grn)':'#e74c3c'}">${t.status}</div></div>`;});
    if(d.completed.length)h+='<button class="dp-clr" onclick="clrDone()">清空已完成</button>';
    document.getElementById('dpB').innerHTML=h;
    let b=document.getElementById('dlB');if(d.pending.length>0){b.style.display='flex';b.textContent=d.pending.length;}else{b.style.display='none';}
  });
}
function delP(id){fetch('/api/dl-remove',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})}).then(()=>refreshDp());}
function clrDone(){fetch('/api/dl-clear',{method:'POST'}).then(()=>refreshDp());}
setInterval(refreshDp,2000);
function saveCk(){let c=document.getElementById('ckIn').value.trim();if(!c)return;fetch('/api/cookie',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cookie:c})}).then(()=>toast('Cookie 已保存'));}
let es=null;
function connectLogs(){
  if(es)es.close();es=new EventSource('/api/logs-stream');
  es.onmessage=function(e){
    let el=document.getElementById('logs'),raw=e.data;
    if(raw.startsWith('\x01P\x01')){
      let c=raw.substring(3),p=el.querySelector('.lp-p');
      if(!p){p=document.createElement('div');p.className='lp-p';el.appendChild(p);}
      p.textContent=c;el.scrollTop=el.scrollHeight;
    }else{
      let p=el.querySelector('.lp-p');if(p)p.remove();
      let d=document.createElement('div');d.textContent=raw;el.appendChild(d);el.scrollTop=el.scrollHeight;
      while(el.children.length>200)el.removeChild(el.firstChild);
    }
  };
  es.onerror=function(){setTimeout(connectLogs,3000);};
}
connectLogs();
</script></body></html>"""

PROGRESS_MARKER="\x01P\x01"

class Handler(BaseHTTPRequestHandler):
    def log_message(s,*a):pass
    def _json(s,d,c=200):
        s.send_response(c);s.send_header("Content-Type","application/json; charset=utf-8")
        s.send_header("Access-Control-Allow-Origin","*");s.end_headers()
        s.wfile.write(json.dumps(d,ensure_ascii=False).encode())
    def _body(s):
        l=int(s.headers.get("Content-Length",0))
        return json.loads(s.rfile.read(l)) if l else {}
    def do_GET(s):
        if s.path in("/","/index.html"):
            s.send_response(200);s.send_header("Content-Type","text/html; charset=utf-8")
            s.end_headers();s.wfile.write(HTML.encode())
        elif s.path=="/api/logs-stream":
            s.send_response(200);s.send_header("Content-Type","text/event-stream; charset=utf-8")
            s.send_header("Cache-Control","no-cache");s.send_header("Access-Control-Allow-Origin","*")
            s.end_headers()
            last=0;throttle=0.25
            try:
                while True:
                    try:
                        msg=log_queue.get(timeout=30);now=time.time()
                        is_prog=PROGRESS_MARKER in msg
                        if is_prog and(now-last)<throttle:continue
                        last=now
                        clean=msg.replace(PROGRESS_MARKER,PROGRESS_MARKER).replace("\r","")
                        s.wfile.write(f"data: {clean}\n\n".encode("utf-8"));s.wfile.flush()
                    except queue.Empty:
                        s.wfile.write(b": keepalive\n\n");s.wfile.flush()
            except(BrokenPipeError,ConnectionResetError):pass
        elif s.path=="/api/dl-status":s._json(dl_mgr.status())
        else:s.send_error(404)
    def do_POST(s):
        if s.path=="/api/search":
            b=s._body();src=b.get("source","muguang");pg=b.get("page",1)
            songs,tot=search_music(b.get("keyword",""),src,pg)
            s._json({"songs":songs,"total":tot})
        elif s.path=="/api/download":
            b=s._body();cnt=0
            for idx in b.get("indices",[]):
                if 0<=idx<len(_cache):
                    if dl_mgr.add(_cache[idx],b.get("source","muguang")) is not None:cnt+=1
            s._json({"ok":True,"count":cnt})
        elif s.path=="/api/preview":
            b=s._body();idx=b.get("index",0);src=b.get("source","muguang")
            if 0<=idx<len(_cache):
                song=_cache[idx]
                if song.get("source_tag")=="muguang" or src=="muguang":
                    url,fmt=mg_play_url(song.get("id"),"128")
                    if not url:url,fmt=mg_play_url(song.get("id"),"320")
                else:url,fmt=get_play_url(song,src,low=True)
                s._json({"url":url,"ext":fmt})
            else:s._json({"url":None})
        elif s.path=="/api/lyric":
            b=s._body();idx=b.get("index",0);src=b.get("source","muguang")
            if 0<=idx<len(_cache):s._json({"lrc":get_lyrics(_cache[idx],src)})
            else:s._json({"lrc":None})
        elif s.path=="/api/cookie":
            b=s._body();c=b.get("cookie","")
            hi_save_cookie(c);HI_HEADERS["Cookie"]=c;s._json({"ok":True})
        elif s.path=="/api/dl-remove":dl_mgr.remove(s._body().get("id",0));s._json({"ok":True})
        elif s.path=="/api/dl-clear":dl_mgr.clear_done();s._json({"ok":True})
        else:s.send_error(404)
    def do_OPTIONS(s):
        s.send_response(200);s.send_header("Access-Control-Allow-Origin","*")
        s.send_header("Access-Control-Allow-Methods","GET, POST, OPTIONS")
        s.send_header("Access-Control-Allow-Headers","Content-Type");s.end_headers()

_cache=[]
_orig=search_music
def search_cached(kw,src="muguang",pg=1):
    global _cache
    songs,tot=_orig(kw,src,pg)
    if pg==1:_cache=songs
    else:_cache.extend(songs)
    return songs,tot
search_music=search_cached

def main():
    global HI_HEADERS
    ck=hi_load_cookie()
    if ck:HI_HEADERS["Cookie"]=ck;log("[✅] Cookie 已加载")
    else:log("[⚠️] 未找到Cookie (仅酷我聚合源需要)")
    test_ts="1792859066146"
    test_sign=hashlib.md5(f"{MG_SALT}{test_ts}1".encode()).hexdigest()
    expected="6c8bc9ad59b1cbb100a2e2e72b965eac"
    log(f"[*] 签名验证: {'✅ 通过' if test_sign==expected else '❌ 失败'} ({test_sign})")
    log(f"[*] 盐值: {MG_SALT}")
    log(f"[*] 搜索: {MG_SEARCH}")
    log(f"[*] 播放: {MG_PLAY} (nmobi.kuwo.cn)")
    log(f"[*] 歌词: {MG_LYRIC} (Base64)")
    log(f"[🚀] D-kaiser Music: http://localhost:{PORT}")
    srv=ThreadingHTTPServer(("0.0.0.0",PORT),Handler)
    srv.daemon_threads=True
    try:srv.serve_forever()
    except KeyboardInterrupt:log("\n👋 已停止")

if __name__=="__main__":
    main()