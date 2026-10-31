#!/usr/bin/env python3
"""元数据嵌入 (mutagen)"""
import os

try:
    from mutagen.flac import FLAC, Picture
    from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC, USLT
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False


def embed_metadata(path, song, lrc=None):
    if not HAS_MUTAGEN or not os.path.exists(path):
        return False
    ext = os.path.splitext(path)[1].lower()
    cd = None
    cp = path.rsplit(".", 1)[0] + ".jpg"
    if os.path.exists(cp):
        with open(cp, "rb") as f:
            cd = f.read()
    try:
        if ext == ".flac":
            a = FLAC(path)
            a["TITLE"] = song.get("name", "")
            a["ARTIST"] = song.get("artist", "")
            a["ALBUM"] = song.get("album", "")
            if lrc:
                a["LYRICS"] = lrc
            if cd:
                p = Picture()
                p.type = 3
                p.mime = "image/jpeg"
                p.data = cd
                a.clear_pictures()
                a.add_picture(p)
            a.save()
        elif ext == ".mp3":
            a = ID3(path) if os.path.getsize(path) > 0 else ID3()
            a["TIT2"] = TIT2(encoding=3, text=song.get("name", ""))
            a["TPE1"] = TPE1(encoding=3, text=song.get("artist", ""))
            a["TALB"] = TALB(encoding=3, text=song.get("album", ""))
            if lrc:
                a["USLT"] = USLT(encoding=3, lang="eng", desc="", text=lrc)
            if cd:
                a["APIC"] = APIC(encoding=3, mime="image/jpeg", type=3,
                                 desc="Cover", data=cd)
            a.save()
        else:
            return False
        return True
    except Exception:
        return False