# extract_tlg.py
# 从 .tlg（及指定扩展名）文件中提取 RIFF....WEBP 图片
# 默认提取后删除原文件，加 --keep 可保留
# 工作根目录固定为 /storage/emulated/0/termux/

import os
import sys
import binascii
import argparse

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

# 固定的工作根目录
ROOT_DIR = "/storage/emulated/0/termux"


def simple_progress(iterable, desc="处理中"):
    """内置简单进度条"""
    total = len(iterable)
    for i, item in enumerate(iterable, 1):
        yield item
        if total:
            percent = (i / total) * 100
            sys.stdout.write(f"\r{desc}: [{i}/{total}] {percent:.1f}%")
            sys.stdout.flush()
    sys.stdout.write("\n")


def hex_str_to_bytes(hex_str: str) -> bytes:
    """去除空白字符后将十六进制字符串转换为字节"""
    clean = ''.join(hex_str.split())
    return binascii.unhexlify(clean)


def is_hex_text(content: bytes) -> bool:
    """判断文件内容是否为纯十六进制文本（允许空格、换行）"""
    try:
        text = content.decode('ascii')
    except UnicodeDecodeError:
        return False
    clean = ''.join(text.split())
    if not clean:
        return False
    return all(c in "0123456789abcdefABCDEF" for c in clean)


def find_webp_chunks(data: bytes):
    """返回 data 中所有 RIFF....WEBP 块的起始和结束位置"""
    chunks = []
    pos = 0
    while True:
        riff = data.find(b'RIFF', pos)
        if riff == -1:
            break
        if riff + 12 > len(data):
            break

        size = int.from_bytes(data[riff + 4:riff + 8], 'little')
        if data[riff + 8:riff + 12] != b'WEBP':
            pos = riff + 4
            continue

        end = riff + 8 + size
        if end > len(data) or end <= riff:
            pos = riff + 4
            continue

        chunks.append((riff, end))
        pos = end

    return chunks


def extract_chunks(data: bytes, chunks, out_dir: str, base_name: str) -> int:
    """将每个块写入独立的 .webp 文件，返回提取数量"""
    count = 0
    for i, (start, end) in enumerate(chunks):
        webp_data = data[start:end]
        out_path = os.path.join(out_dir, f"{base_name}_{i:03d}.webp")
        with open(out_path, 'wb') as f:
            f.write(webp_data)
        count += 1
    return count


def process_file(filepath: str, xor_key: int = 0, delete: bool = True) -> int:
    """
    处理单个文件，返回提取出的图片数量
    delete=True 表示提取成功后删除原文件
    """
    dir_name = os.path.dirname(filepath)
    base_name = os.path.splitext(os.path.basename(filepath))[0]

    with open(filepath, 'rb') as f:
        raw = f.read()

    # 如果文件内容是十六进制文本，转成二进制
    if is_hex_text(raw):
        try:
            raw = hex_str_to_bytes(raw.decode('ascii'))
        except Exception:
            return 0

    # 异或解密（如果提供了密钥）
    if xor_key:
        raw = bytes(b ^ xor_key for b in raw)

    chunks = find_webp_chunks(raw)
    if not chunks:
        return 0

    count = extract_chunks(raw, chunks, dir_name, base_name)

    if delete:
        try:
            os.remove(filepath)
        except OSError:
            pass

    return count


def main():
    parser = argparse.ArgumentParser(
        description="从 .tlg 文件中提取 WebP 图片（默认提取后删除原文件）"
    )
    parser.add_argument(
        "--xor",
        type=lambda x: int(x, 0),
        default=0,
        help="异或解密密钥，如 --xor 0xa3"
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="保留原 .tlg 文件（默认会删除）"
    )
    parser.add_argument(
        "--ext",
        nargs="+",
        default=[".tlg"],
        help="要处理的扩展名，默认 .tlg，如 --ext .tlg .pimg"
    )

    args = parser.parse_args()

    exts = tuple(
        e.lower() if e.startswith('.') else f'.{e.lower()}'
        for e in args.ext
    )

    # 检查根目录是否存在
    if not os.path.isdir(ROOT_DIR):
        print(f"错误：工作根目录不存在或无法访问 -> {ROOT_DIR}")
        sys.exit(1)

    # 收集所有匹配的文件（从根目录递归搜索）
    files = []
    for dirpath, _, filenames in os.walk(ROOT_DIR):
        for fname in filenames:
            if fname.lower().endswith(exts):
                files.append(os.path.join(dirpath, fname))

    if not files:
        print(f"在 {ROOT_DIR} 及其子目录中未找到需要处理的文件。")
        return

    total_files = len(files)
    total_extracted = 0
    total_deleted = 0
    failed = []

    # 进度条
    if HAS_TQDM:
        iterator = tqdm(files, desc="提取图片", unit="file")
    else:
        print("提示：安装 tqdm 可显示更美观进度条 -> pip install tqdm")
        iterator = simple_progress(files, desc="提取进度")

    for fp in iterator:
        # delete = not args.keep  → 默认删除，加 --keep 则保留
        count = process_file(fp, xor_key=args.xor, delete=(not args.keep))
        if count > 0:
            total_extracted += count
            if not args.keep:
                total_deleted += 1
        else:
            failed.append(os.path.basename(fp))

    # 输出统计
    print(f"\n✅ 完成！共处理 {total_files} 个文件")
    print(f"   - 提取出 {total_extracted} 张 WebP 图片")
    if not args.keep:
        print(f"   - 已删除 {total_deleted} 个原文件")
    else:
        print("   - 原文件已保留（--keep 生效）")
    if failed:
        print(f"   - ⚠️ 未能提取图片的文件（已保留）：{', '.join(failed[:10])}")


if __name__ == "__main__":
    main()