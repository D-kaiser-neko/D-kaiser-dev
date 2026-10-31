#!/usr/bin/env python3
"""暮光工具箱 API（签名 / 搜索 / 播放链接 / 歌词）"""
import time, hashlib, json, base64, urllib.parse, zlib
import requests
from config import MG_SEARCH, MG_PLAY, MG_LYRIC, MG_SALT, MG_SOURCE, PAGE_SIZE, log
from core.lrc_parser import format_lrc


def mg_headers():
    ts = str(int(time.time() * 1000))
    sign = hashlib.md5(f"{MG_SALT}{ts}1".encode()).hexdigest()
    return {
        "Version": "1", "Platform": "android",
        "Timestamp": ts, "Sign": sign,
        "User-Agent": "okhttp/4.11.0"
    }


def mg_search(keyword, page=1, size=PAGE_SIZE):
    url = f"{MG_SEARCH}?keyword={urllib.parse.quote(keyword)}&pageNo={page}&pageSize={size}"
    try:
        j = requests.get(url, headers=mg_headers(), timeout=15).json()
        if j.get("code") != 200:
            return [], 0
        d = j.get("data", {})
        songs = []
        for s in d.get("data", []):
            s["pic_url"] = s.get("pic", "")
            s["source_tag"] = "muguang"
            s["minfo"] = [{"format": "flac"}] if s.get("hasLossless") else [{"format": "mp3"}]
            songs.append(s)
        return songs, d.get("total", 0)
    except Exception as e:
        log(f"[-] 暮光搜索异常: {e}")
        return [], 0


def mg_play_url(rid, quality="flac"):
    br = {"flac": "2000kflac", "320": "320kmp3", "128": "128kmp3"}.get(quality, "2000kflac")
    params = {
        "f": "web", "user": "0", "source": MG_SOURCE,
        "type": "convert_url_with_sign", "rid": str(rid), "br": br
    }
    try:
        j = requests.get(MG_PLAY, params=params, headers={
            "User-Agent": "okhttp/4.11.0", "Accept-Encoding": "gzip"
        }, timeout=15).json()
        if j.get("code") == 200:
            d = j.get("data", {})
            return d.get("url"), d.get("format", quality)
        return None, None
    except Exception as e:
        log(f"[-] 播放链接异常: {e}")
        return None, None


def mg_lyrics(rid):
    """酷我歌词: 明文头 -> zlib解压 -> Base64解码 -> 真实文本/JSON"""
    import zlib
    import base64
    
    params = {"f": "web", "type": "lyric", "lrcx": "1", "rid": str(rid), "encode": "utf8"}
    try:
        r = requests.get(MG_LYRIC, params=params, headers={
            "User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/120.0.6099.144 Mobile Safari/537.36",
            "Accept-Encoding": "identity"  # 关键：禁止 requests 自动处理 gzip
        }, timeout=15)
        
        data = r.content
        sep = b"\r\n\r\n"
        pos = data.find(sep)
        
        if pos != -1:
            payload = data[pos + len(sep):]
        else:
            payload = data
            
        # 1. zlib 解压
        decompressed_bytes = zlib.decompress(payload)
        
        # 2. 尝试将解压结果作为 Base64 字符串解码
        try:
            b64_string = decompressed_bytes.decode('utf-8').strip()
            final_bytes = base64.b64decode(b64_string)
            raw_text = final_bytes.decode('utf-8', errors='replace')
        except Exception:
            # 兜底：如果解压出来直接就是文本，则直接使用
            raw_text = decompressed_bytes.decode('utf-8', errors='replace')
            
        if not raw_text or not raw_text.strip():
            return None
            
        lrc_text = None
        
        # 3. 尝试解析 JSON (酷我有时会返回 {"code":0, "data": {"lrclist": [...]}})
        try:
            j = json.loads(raw_text)
            if isinstance(j, dict):
                if j.get("code") in (0, 200):
                    d = j.get("data", "")
                    if isinstance(d, str) and "[" in d:
                        lrc_text = d
                    elif isinstance(d, dict):
                        arr = d.get("lrclist")
                        if isinstance(arr, list) and arr:
                            out = []
                            for it in arr:
                                if not isinstance(it, dict): continue
                                t = float(it.get("time", 0) or 0)
                                mm, ss = divmod(t, 60)
                                lyric = it.get("lineLyric") or it.get("lyric") or ""
                                if lyric.strip():
                                    out.append(f"[{int(mm):02d}:{ss:05.2f}]{lyric}")
                            lrc_text = "\n".join(out)
                        else:
                            for key in ("content", "lyric", "lrc"):
                                v = d.get(key)
                                if isinstance(v, str) and len(v) > 10 and "[" in v:
                                    lrc_text = v
                                    break
        except (ValueError, TypeError):
            pass
            
        # 4. 如果 JSON 解析失败，直接使用 raw_text (它应该已经是 LRC 格式)
        if not lrc_text:
            if "[" in raw_text and "]" in raw_text:
                lrc_text = raw_text
                
        if not lrc_text:
            log(f"[-] 未找到有效歌词内容 rid={rid}")
            return None
            
        result = format_lrc(lrc_text)
        if result:
            log(f"[✅] 歌词已解析 rid={rid} 长度={len(result)}")
            return result
            
        log(f"[-] 歌词格式化后为空 rid={rid}")
        return lrc_text[:2000] # 兜底返回原始文本

    except Exception as e:
        log(f"[-] 歌词请求异常: {e}")
        return None