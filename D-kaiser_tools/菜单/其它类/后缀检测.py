#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件后缀自动纠正工具
- 无后缀文件：识别类型并添加扩展名
- 有后缀文件：识别实际类型，若与当前后缀不符则修正
- 将全部修改记录写入日志文件
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

# 固定的工作根目录
ROOT_DIR = "/storage/emulated/0/termux"

# 日志文件路径（默认存放在工作根目录下）
LOG_FILE = str(Path(ROOT_DIR) / "rename_log.txt")

# ============================================================
# 文件签名数据库
# ============================================================
FILE_SIGNATURES = [
    # 图片格式
    ("89504E470D0A1A0A", 0, ".png"),       # PNG
    ("FFD8FFE0",         0, ".jpg"),       # JPEG (JFIF)
    ("FFD8FFE1",         0, ".jpg"),       # JPEG (EXIF)
    ("FFD8FFE2",         0, ".jpg"),       # JPEG (SPIFF)
    ("FFD8FFE3",         0, ".jpg"),       # JPEG
    ("FFD8FFE8",         0, ".jpg"),       # JPEG
    ("FFD8FFDB",         0, ".jpg"),       # JPEG
    ("474946383961",     0, ".gif"),       # GIF89a
    ("474946383761",     0, ".gif"),       # GIF87a
    ("424D",             0, ".bmp"),       # BMP
    ("52494646",         0, ".webp_check"),# WEBP/AVI/WAV (需二次检查)
    ("00000100",         0, ".ico"),       # ICO
    ("49492A00",         0, ".tiff"),      # TIFF (little-endian)
    ("4D4D002A",         0, ".tiff"),      # TIFF (big-endian)
    ("66747970",         4, ".mp4"),       # MP4/MOV (ftyp at offset 4)
    ("0000000C6A50",     0, ".jp2"),       # JPEG 2000

    # 文档格式
    ("25504446",         0, ".pdf"),       # PDF
    ("D0CF11E0A1B11AE1", 0, ".doc"),      # OLE2 (doc/xls/ppt)
    ("504B0304",         0, ".zip_check"), # ZIP/DOCX/XLSX/PPTX/JAR/APK
    ("7F454C46",         0, ".elf"),       # ELF executable
    ("CAFEBABE",         0, ".class"),     # Java class

    # 压缩/归档格式
    ("526172211A0700",   0, ".rar"),       # RAR v1.5+
    ("526172211A070100", 0, ".rar"),       # RAR v5.0
    ("377ABCAF271C",     0, ".7z"),        # 7-Zip
    ("1F8B08",           0, ".gz"),        # GZIP
    ("425A68",           0, ".bz2"),       # BZIP2
    ("FD377A585A00",     0, ".xz"),        # XZ
    ("504B0506",         0, ".zip"),       # Empty ZIP archive
    ("504B0708",         0, ".zip"),       # Spanned ZIP archive

    # 音视频格式
    ("494433",           0, ".mp3"),       # MP3 (ID3v2)
    ("FFFB",             0, ".mp3"),       # MP3 (no ID3)
    ("FFF3",             0, ".mp3"),       # MP3
    ("FFF2",             0, ".mp3"),       # MP3
    ("664C6143",         0, ".flac"),      # FLAC
    ("4F676753",         0, ".ogg"),       # OGG
    ("52494646",         0, ".wav_check"), # WAV (RIFF....WAVE)
    ("1A45DFA3",         0, ".mkv"),       # MKV/WebM
    ("0000001866747970", 0, ".mov"),       # MOV (some variants)
    ("3026B2758E66CF11", 0, ".wmv"),       # WMV/WMA
]

# 基于ZIP格式但不应被改为 .zip 的常用扩展名
ZIP_BASED_EXTS = {".docx", ".xlsx", ".pptx", ".jar", ".apk", ".ods", ".odt", ".ott", ".odp", ".odg"}


def build_signature_tree():
    """构建签名查找表"""
    sigs = []
    for hex_sig, offset, ext in FILE_SIGNATURES:
        try:
            byte_sig = bytes.fromhex(hex_sig)
            sigs.append((byte_sig, offset, ext))
        except ValueError as e:
            print(f"[警告] 无效签名 '{hex_sig}': {e}")
    # 按 (offset + len) 降序排列，更长/更精确的签名优先
    sigs.sort(key=lambda x: x[1] + len(x[0]), reverse=True)
    return sigs


SIGNATURES = build_signature_tree()


def detect_file_type(filepath: str, read_size: int = 512) -> str | None:
    """通过读取文件头部字节检测真实文件类型，返回扩展名或 None"""
    try:
        with open(filepath, 'rb') as f:
            header = f.read(read_size)
    except (IOError, PermissionError) as e:
        print(f"  [错误] 无法读取: {filepath} ({e})")
        return None

    if len(header) < 2:
        return None

    for byte_sig, offset, ext in SIGNATURES:
        end = offset + len(byte_sig)
        if len(header) >= end and header[offset:end] == byte_sig:
            # 需要二次检查的容器格式
            if ext == ".webp_check":
                if len(header) >= 12:
                    subtype = header[8:12]
                    if subtype == b'WEBP':
                        return ".webp"
                    elif subtype == b'AVI ':
                        return ".avi"
                    elif subtype == b'WAVE':
                        return ".wav"
                continue
            if ext == ".wav_check":
                if len(header) >= 12 and header[8:12] == b'WAVE':
                    return ".wav"
                continue
            if ext == ".zip_check":
                # ZIP 格式，但我们只返回 .zip，具体修正逻辑放在主程序里处理
                return ".zip"
            return ext
    return None


def safe_rename(src: Path, ext: str) -> Path:
    """安全重命名，避免覆盖已有文件"""
    dst = src.with_suffix(ext)
    if not dst.exists():
        return dst
    counter = 1
    while True:
        dst = src.parent / f"{src.stem}_{counter}{ext}"
        if not dst.exists():
            return dst
        counter += 1


def log_change(log_entries: list, timestamp: str, old: Path, new: Path, reason: str):
    """将一次修改记录添加到日志列表"""
    entry = f"{timestamp} | {old} → {new} | {reason}"
    log_entries.append(entry)
    print(f"  {reason}: {old.name} → {new.name}")


def scan_and_correct(root_dir: str, dry_run: bool = False, recursive: bool = True,
                     log_file: str = LOG_FILE):
    """扫描目录，纠正文件后缀，并输出日志"""
    root = Path(root_dir).resolve()
    stats = {"scanned": 0, "fixed": 0, "skipped": 0, "errors": 0}
    log_entries = []   # 存放所有修改记录
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    iterator = root.rglob("*") if recursive else root.glob("*")

    for filepath in sorted(iterator):
        if not filepath.is_file():
            continue

        stats["scanned"] += 1
        current_suffix = filepath.suffix.lower()
        detected_ext = detect_file_type(str(filepath))

        # 情况1：无法识别类型，跳过
        if detected_ext is None:
            stats["skipped"] += 1
            continue

        # 判断是否需要修改
        need_rename = False
        reason = ""

        if not current_suffix:
            # 无后缀，添加检测到的扩展名
            need_rename = True
            reason = "添加后缀"
        else:
            # 有后缀，检查是否与检测类型一致
            if current_suffix == detected_ext:
                stats["skipped"] += 1
                continue

            # 特殊处理：检测为 .zip 但原始后缀是已知的 ZIP 系格式（如 .docx）
            if detected_ext == ".zip" and current_suffix in ZIP_BASED_EXTS:
                stats["skipped"] += 1
                continue

            # 其他不匹配情况，修正后缀
            need_rename = True
            reason = f"纠正后缀 ({current_suffix} → {detected_ext})"

        if need_rename:
            new_path = safe_rename(filepath, detected_ext)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if not dry_run:
                try:
                    filepath.rename(new_path)
                    log_change(log_entries, timestamp, filepath, new_path, reason)
                    stats["fixed"] += 1
                except OSError as e:
                    print(f"  [失败] {filepath.name}: {e}")
                    stats["errors"] += 1
            else:
                log_change(log_entries, timestamp, filepath, new_path, reason)
                stats["fixed"] += 1  # 预览模式也计入

    # 写入日志文件
    if log_entries:
        log_header = f"文件后缀纠正日志 - {now_str}\n" + "=" * 60
        log_content = "\n".join([log_header] + log_entries + ["=" * 60])
        if not dry_run:
            try:
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(log_content + "\n\n")
                print(f"\n📄 日志已写入: {log_file}")
            except IOError as e:
                print(f"\n[错误] 无法写入日志文件: {e}")
        else:
            print("\n[预览模式] 不会写入日志文件，以下为将要记录的内容：")
            print(log_content)

    # 统计输出
    print("\n" + "=" * 50)
    print("📊 统计结果:")
    print(f"   扫描文件: {stats['scanned']}")
    print(f"   修正/添加: {stats['fixed']}")
    print(f"   跳过(正确/无法识别): {stats['skipped']}")
    print(f"   错误: {stats['errors']}")
    if dry_run:
        print("   ⚠️  以上为预览模式，未实际修改任何文件")
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(
        description="根据文件头魔数自动纠正文件后缀（添加或修正）"
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=ROOT_DIR,
        help=f"要扫描的目录路径 (默认: {ROOT_DIR})"
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="预览模式，仅显示将要执行的操作而不实际重命名"
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="不递归扫描子目录"
    )
    parser.add_argument(
        "--log", "-l",
        default=LOG_FILE,
        help=f"日志文件路径 (默认: {LOG_FILE})"
    )

    args = parser.parse_args()

    # 检查根目录
    if not os.path.isdir(ROOT_DIR):
        print(f"[错误] 工作根目录不存在或无法访问: {ROOT_DIR}")
        sys.exit(1)

    # 解析目标目录
    if os.path.isabs(args.directory):
        target = Path(args.directory).resolve()
    else:
        target = (Path(ROOT_DIR) / args.directory).resolve()

    if not target.is_dir():
        print(f"[错误] 路径不存在或不是目录: {target}")
        sys.exit(1)

    mode = "预览模式" if args.dry_run else "执行模式"
    recurse = "递归" if not args.no_recursive else "仅当前目录"
    print("🔍 文件后缀自动纠正工具")
    print(f"   目录: {target}")
    print(f"   模式: {mode} | {recurse}")
    print(f"   日志: {args.log}")
    print("-" * 50)

    scan_and_correct(
        str(target),
        dry_run=args.dry_run,
        recursive=not args.no_recursive,
        log_file=args.log
    )


if __name__ == "__main__":
    main()