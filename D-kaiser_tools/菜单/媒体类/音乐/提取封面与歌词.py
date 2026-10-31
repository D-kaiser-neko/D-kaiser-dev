#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
音频封面与歌词提取脚本（集中输出）
支持格式：.mp3, .flac, .ogg
输入目录：/storage/emulated/0/termux/输入/
输出目录：/storage/emulated/0/termux/输出/output_jpg/原文件名.jpg
         /storage/emulated/0/termux/输出/output_txt/原文件名.txt
自动检测真实格式并修正错误扩展名
"""

import os
import sys
import base64
from mutagen import File, MutagenError
from mutagen.id3 import ID3, USLT
from mutagen.flac import FLAC, Picture
from mutagen.oggvorbis import OggVorbis
from mutagen.oggopus import OggOpus

INPUT_DIR = "/storage/emulated/0/termux/"
OUTPUT_BASE = "/storage/emulated/0/termux/"

COVER_DIR = os.path.join(OUTPUT_BASE, "output_jpg")
LYRICS_DIR = os.path.join(OUTPUT_BASE, "output_txt")

renamed_files = []   # 扩展名修正记录
failed_files = []    # 无法解析的文件

def ensure_dir(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

def detect_real_audio_type(file_path):
    """通过文件头检测真实音频类型，返回扩展名如'.mp3','.flac','.ogg'"""
    try:
        with open(file_path, 'rb') as f:
            header = f.read(32)
        if len(header) >= 4 and header[:4] == b'fLaC':
            return '.flac'
        if len(header) >= 4 and header[:4] == b'OggS':
            return '.ogg'
        if header[:3] == b'ID3':
            return '.mp3'
        if len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xE0) == 0xE0:
            return '.mp3'
        return None
    except Exception:
        return None

def fix_file_extension(file_path):
    """若扩展名与实际格式不符则重命名，返回新路径和是否改名"""
    current_ext = os.path.splitext(file_path)[1].lower()
    real_ext = detect_real_audio_type(file_path)
    if real_ext is None:
        return file_path, False
    if current_ext == real_ext:
        return file_path, False

    new_path = os.path.splitext(file_path)[0] + real_ext
    try:
        os.rename(file_path, new_path)
        renamed_files.append((file_path, new_path))
        print(f"♻️  扩展名修正：{os.path.basename(file_path)} → {os.path.basename(new_path)}")
        return new_path, True
    except OSError as e:
        print(f"❌ 无法重命名 {file_path}: {e}")
        return file_path, False

def get_ogg_pictures(audio):
    """从 OGG Vorbis/Opus 中提取图片列表"""
    pictures = []
    # metadata_block_picture 是 base64 编码的 FLAC Picture 块
    for key in ['metadata_block_picture', 'METADATA_BLOCK_PICTURE']:
        if key in audio:
            raw_list = audio[key]
            for raw_item in raw_list:
                try:
                    decoded = base64.b64decode(raw_item)
                    picture = Picture(decoded)
                    pictures.append(picture)
                except Exception:
                    continue
    # 也尝试直接 coverart 字段（较少见）
    if not pictures and 'coverart' in audio:
        try:
            # coverart 通常是 base64 编码的原始图像数据
            raw = base64.b64decode(audio['coverart'][0])
            # 构造一个简单的 Picture 对象
            picture = Picture()
            picture.data = raw
            pictures.append(picture)
        except Exception:
            pass
    return pictures

def extract_cover_and_lyrics(file_path):
    ensure_dir(COVER_DIR)
    ensure_dir(LYRICS_DIR)

    base_name = os.path.splitext(os.path.basename(file_path))[0]
    cover_path = os.path.join(COVER_DIR, base_name + ".jpg")
    lyrics_path = os.path.join(LYRICS_DIR, base_name + ".txt")

    # 安全加载
    try:
        audio = File(file_path)
    except Exception as e:
        print(f"⚠️  无法解析文件（已损坏或格式不支持）: {file_path} -> {e}")
        failed_files.append(file_path)
        return

    if audio is None:
        print(f"⚠️  无法识别文件类型: {file_path}")
        failed_files.append(file_path)
        return

    # ----- 提取封面 -----
    cover_extracted = False
    try:
        # MP3
        if isinstance(audio, ID3) or (hasattr(audio, 'tags') and isinstance(audio.tags, ID3)):
            tags = audio if isinstance(audio, ID3) else audio.tags
            for tag in tags.values():
                if tag.FrameID == 'APIC':
                    with open(cover_path, 'wb') as f:
                        f.write(tag.data)
                    print(f"✅ 封面已提取: {cover_path}")
                    cover_extracted = True
                    break
        # FLAC
        elif isinstance(audio, FLAC) and audio.pictures:
            with open(cover_path, 'wb') as f:
                f.write(audio.pictures[0].data)
            print(f"✅ 封面已提取: {cover_path}")
            cover_extracted = True
        # OGG (Vorbis / Opus)
        elif isinstance(audio, (OggVorbis, OggOpus)):
            pics = get_ogg_pictures(audio)
            if pics:
                with open(cover_path, 'wb') as f:
                    f.write(pics[0].data)
                print(f"✅ 封面已提取: {cover_path}")
                cover_extracted = True

        if not cover_extracted:
            print(f"📭 未找到封面: {file_path}")
    except Exception as e:
        print(f"❌ 提取封面出错 {file_path}: {e}")

    # ----- 提取歌词 -----
    lyrics_extracted = False
    try:
        # MP3 USLT
        if isinstance(audio, ID3) or (hasattr(audio, 'tags') and isinstance(audio.tags, ID3)):
            tags = audio if isinstance(audio, ID3) else audio.tags
            uslt_frames = [t for t in tags.values() if isinstance(t, USLT)]
            if uslt_frames:
                with open(lyrics_path, 'w', encoding='utf-8') as f:
                    f.write(uslt_frames[0].text)
                print(f"✅ 歌词已提取: {lyrics_path}")
                lyrics_extracted = True
        # FLAC
        elif isinstance(audio, FLAC):
            if 'LYRICS' in audio:
                with open(lyrics_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(audio['LYRICS']))
                print(f"✅ 歌词已提取: {lyrics_path}")
                lyrics_extracted = True
        # OGG (Vorbis / Opus) 歌词
        elif isinstance(audio, (OggVorbis, OggOpus)):
            lyrics_tags = [key for key in ('LYRICS', 'UNSYNCEDLYRICS') if key in audio]
            if lyrics_tags:
                text = '\n'.join(audio[lyrics_tags[0]])
                with open(lyrics_path, 'w', encoding='utf-8') as f:
                    f.write(text)
                print(f"✅ 歌词已提取: {lyrics_path}")
                lyrics_extracted = True

        if not lyrics_extracted:
            print(f"📭 未找到歌词: {file_path}")
    except Exception as e:
        print(f"❌ 提取歌词出错 {file_path}: {e}")

def main():
    if len(sys.argv) > 1:
        targets = sys.argv[1:]
    else:
        targets = [INPUT_DIR]

    # 扩展名列表现在包含 .ogg
    valid_exts = ['.mp3', '.flac', '.ogg']
    files_to_process = []
    for target in targets:
        if os.path.isfile(target):
            ext = os.path.splitext(target)[1].lower()
            if ext in valid_exts:
                files_to_process.append(target)
            else:
                print(f"⏭️  跳过非音频文件: {target}")
        elif os.path.isdir(target):
            for root, dirs, files in os.walk(target):
                for file in files:
                    ext = os.path.splitext(file)[1].lower()
                    if ext in valid_exts:
                        files_to_process.append(os.path.join(root, file))
        else:
            print(f"❌ 无效路径: {target}")

    if not files_to_process:
        print("未找到任何支持的音频文件（.mp3, .flac, .ogg）。")
        return

    print(f"🔍 找到 {len(files_to_process)} 个音频文件，开始处理...\n")
    for file_path in files_to_process:
        fixed_path, was_renamed = fix_file_extension(file_path)
        extract_cover_and_lyrics(fixed_path)

    # 汇总
    if renamed_files:
        print("\n========== 假格式文件重命名记录 ==========")
        for old, new in renamed_files:
            print(f"  {os.path.basename(old)} → {os.path.basename(new)}")
        print("==========================================")

    if failed_files:
        print("\n========== 无法解析的文件（已跳过）==========")
        for f in failed_files:
            print(f"  {f}")
        print("==========================================")

if __name__ == "__main__":
    main()