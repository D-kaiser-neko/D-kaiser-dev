#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import asyncio
import subprocess
import edge_tts

# ================= 核心配置 =================
OUTPUT_DIR = "test_media/audio"
TEMP_MP3 = os.path.join(OUTPUT_DIR, "_temp_base.mp3")

# 选择微软的高质量英文神经语音 (Andrew 声音沉稳专业)
VOICE = "en-US-AndrewMultilingualNeural"

FORMATS = {
    "WAV": {
        "ext": "wav",
        "text": "This is a wave audio file. It is an uncompressed format developed by I B M and Microsoft in 1991. It offers high quality but large file size."
    },
    "MP3": {
        "ext": "mp3",
        "text": "This is an M P 3 audio file. Developed in 1993, it uses lossy compression. It is the most popular audio format for music and podcasts."
    },
    "OGG": {
        "ext": "ogg",
        "text": "This is an O G G Vorbis audio file. Created in 1998 as a free and open alternative to M P 3. It provides better sound quality at similar bitrates."
    },
    "FLAC": {
        "ext": "flac",
        "text": "This is a F L A C audio file. It stands for Free Lossless Audio Codec, released in 2001. It compresses audio without any quality loss."
    },
    "M4A": {
        "ext": "m4a",
        "text": "This is an M 4 A audio file using A A C compression. Standardized in 1997. It is the default audio format for Apple devices and offers excellent quality."
    }
}
# ============================================

async def generate_base_mp3(text, out_file):
    """使用 edge-tts 生成基础 MP3 文件"""
    communicate = edge_tts.Communicate(text, VOICE, rate="+5%")
    await communicate.save(out_file)

def convert_audio(ext, out_file):
    """使用 ffmpeg 将基础 MP3 转换为目标格式"""
    cmd = ["ffmpeg", "-y", "-i", TEMP_MP3, "-loglevel", "error"]
    
    if ext == "wav":
        cmd.extend(["-c:a", "pcm_s16le", out_file])
    elif ext == "mp3":
        cmd.extend(["-b:a", "128k", out_file])
    elif ext == "ogg":
        cmd.extend(["-c:a", "libvorbis", "-q:a", "4", out_file])
    elif ext == "flac":
        cmd.extend(["-c:a", "flac", out_file])
    elif ext == "m4a":
        cmd.extend(["-c:a", "aac", "-b:a", "128k", out_file])
        
    subprocess.run(cmd, check=True)

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"[*] Generating high-quality spoken audio in '{OUTPUT_DIR}' ...")
    print("[!] Using Microsoft Edge TTS (Requires internet connection)")
    
    for fmt_name, config in FORMATS.items():
        ext = config["ext"]
        out_file = os.path.join(OUTPUT_DIR, f"sample.{ext}")
        
        try:
            # 1. 生成基础 MP3 (如果是 MP3 则直接作为最终文件)
            if ext == "mp3":
                asyncio.run(generate_base_mp3(config["text"], out_file))
            else:
                # 生成临时 MP3，然后转换
                asyncio.run(generate_base_mp3(config["text"], TEMP_MP3))
                convert_audio(ext, out_file)
                
                # 清理临时文件
                if os.path.exists(TEMP_MP3):
                    os.remove(TEMP_MP3)
                    
            size_kb = os.path.getsize(out_file) / 1024
            print(f"    [+] {fmt_name:<5} -> sample.{ext} ({size_kb:.1f} KB)")
            
        except FileNotFoundError as e:
            print(f"\n[!] Error: Command not found ({e.filename}).")
            print("    Please run: pkg install ffmpeg")
            break
        except Exception as e:
            print(f"\n[!] Error generating {fmt_name}: {e}")
            break

    print("\n[*] Done! High-quality spoken audio generated successfully.")

if __name__ == "__main__":
    main()