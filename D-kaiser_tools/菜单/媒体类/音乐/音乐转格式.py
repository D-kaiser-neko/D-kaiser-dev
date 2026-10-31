#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音频批量转换工具 (pydub, 8线程) - v3
- 自动扫描 /storage/emulated/0/termux/ 及所有子目录
- 输入格式: 直接用格式名选择 (可多选, 空格/逗号分隔), 或输入 any
- 输出格式: mp3, wav, flac, m4a, aac, ogg, opus, wma
- 进度条 + 彩色美化
- 原格式 == 输出格式 时自动跳过
"""

import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pydub import AudioSegment

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

# ---------- 配色 ----------
C_RESET = "\033[0m"
C_CYAN  = "\033[96m"
C_GREEN = "\033[92m"
C_YELL  = "\033[93m"
C_RED   = "\033[91m"
C_BOLD  = "\033[1m"

BASE_DIR   = "/storage/emulated/0/termux"
OUTPUT_DIR = os.path.join(BASE_DIR, "输出")

AUDIO_EXTENSIONS = {
    "mp3":  [".mp3", ".MP3"],
    "wav":  [".wav", ".WAV"],
    "flac": [".flac", ".FLAC"],
    "m4a":  [".m4a", ".M4A", ".aac", ".mp4"],
    "aac":  [".aac", ".AAC"],
    "ogg":  [".ogg", ".OGG", ".oga"],
    "opus": [".opus", ".OPUS"],
    "wma":  [".wma", ".WMA"],
}

ALL_FORMATS = list(AUDIO_EXTENSIONS.keys())


def color(text, code=C_CYAN):
    return f"{code}{text}{C_RESET}"


def banner():
    print(color("=" * 62, C_CYAN))
    print(color(C_BOLD + "  音频批处理转换工具 · pydub · 8线程" + C_RESET, C_CYAN))
    print(color("=" * 62, C_CYAN))


def get_input_formats():
    fmt_list = " / ".join(ALL_FORMATS)
    print(color(f"\n[1/4] 可用 输入 格式: {fmt_list}  (any=全部)", C_BOLD))
    print(color("  可多选，用空格或逗号分隔，例如: mp3 wav", C_YELL))
    while True:
        choice = input(color("  请输入格式 (例如 mp3): ", C_YELL)).strip().lower()
        if choice == "any":
            return ALL_FORMATS.copy()
        # 支持空格/逗号分隔的多选
        parts = [p.strip() for p in choice.replace(",", " ").split() if p.strip()]
        if parts and all(p in ALL_FORMATS for p in parts):
            return list(dict.fromkeys(parts))  # 去重保序
        print(color(f"  输入无效，可用的格式: {', '.join(ALL_FORMATS)} 或 any", C_RED))


def get_output_format():
    fmt_list = " / ".join(ALL_FORMATS)
    print(color(f"\n[2/4] 可用 输出 格式: {fmt_list}", C_BOLD))
    while True:
        fmt = input(color(f"  请输入输出格式 (例如 wav): ", C_YELL)).strip().lower()
        if fmt in ALL_FORMATS:
            return fmt
        print(color("  格式不支持，请重新输入。", C_RED))


def get_all_audio_files(base_dir, input_formats):
    allowed_exts = set()
    for fmt in input_formats:
        allowed_exts.update(AUDIO_EXTENSIONS.get(fmt, []))

    files = []
    for root, _, fnames in os.walk(base_dir):
        if os.path.abspath(root).startswith(os.path.abspath(OUTPUT_DIR)):
            continue
        for fname in fnames:
            if os.path.splitext(fname)[1] in allowed_exts:
                files.append(os.path.join(root, fname))
    return files


def convert_file(src_path, output_format, output_dir):
    name_no_ext = os.path.splitext(os.path.basename(src_path))[0]
    src_ext = os.path.splitext(src_path)[1].lstrip(".").lower()
    dst_path = os.path.join(output_dir, name_no_ext + "." + output_format)

    if src_ext == output_format:          # 格式相同：跳过
        return (src_path, dst_path, "SKIP")

    try:
        audio = AudioSegment.from_file(src_path)
        audio.export(dst_path, format=output_format)
        return (src_path, dst_path, "OK")
    except Exception as e:
        return (src_path, None, str(e))


def main():
    banner()
    input_formats = get_input_formats()
    output_format = get_output_format()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(color(f"\n[3/4] 正在扫描 {BASE_DIR} ...", C_BOLD))
    print(color(f"       输入格式: {', '.join(input_formats)}", C_YELL))
    print(color(f"       输出格式: {output_format}", C_YELL))
    audio_files = get_all_audio_files(BASE_DIR, input_formats)
    if not audio_files:
        print(color("  未找到匹配的音频文件。", C_RED))
        sys.exit(0)
    print(color(f"  找到 {len(audio_files)} 个音频文件。", C_GREEN))

    success, failed, skipped = 0, 0, 0
    lock = threading.Lock()
    desc = f"转换 ({output_format.upper()})"

    if HAS_TQDM:
        bar = tqdm(total=len(audio_files), desc=desc, unit="file",
                   bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]")
    else:
        bar = None
        print(color("\n[4/4] 开始转换...", C_BOLD))

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(convert_file, f, output_format, OUTPUT_DIR): f
                   for f in audio_files}
        for fut in as_completed(futures):
            src, dst, status = fut.result()
            if status == "OK":
                success += 1
            elif status == "SKIP":
                skipped += 1
            elif bar is None:
                with lock:
                    print(color(f"  [失败] {os.path.basename(src)} -> {status}", C_RED))
            else:
                failed += 1

            if bar:
                with lock:
                    bar.set_postfix(ok=success, skip=skipped, fail=failed)
                    bar.update(1)

    if bar:
        bar.close()

    print(color("\n" + "=" * 62, C_CYAN))
    print(color(C_BOLD + "  转换完成" + C_RESET, C_GREEN))
    print(color(f"   成功: {success}   跳过(格式相同): {skipped}   失败: {failed}", C_BOLD))
    print(color(f"   输出目录: {OUTPUT_DIR}", C_BOLD))
    print(color("=" * 62, C_CYAN))


if __name__ == "__main__":
    main()