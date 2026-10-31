#!/usr/bin/env python3
"""
批量提取 PDF 中的图片，自动检测原格式并统一输出为 PNG（无损）
功能：
- 自动检测指定目录下的所有 .pdf 文件
- 为每个 PDF 在 output 根目录下创建以该文件命名的子文件夹
- 智能分析 PDF 中图片的原始格式，选择最优提取参数：
    - 存在 JPEG/JPEG2000 时自动使用 `-j`（直接存为 .jpg，避免解码）
    - 否则不使用 `-j`，以 PPM/PBM 等无损格式提取
- 将提取的所有图片转换为 PNG 格式，转换后删除原始中间文件
- 提供 `--no-png` 选项，禁用转换，保留原始提取格式
- 显示整体处理进度条，格式为 "a/b[n%]"（a=已提取图片数，b=总图片数，n=百分比，保留两位小数），同时保留默认进度条图形
- **新增**：每个 PDF 转换图片时，显示独立的转换进度条（格式相同），完成后自动消失
依赖：
- poppler-utils（提供 pdfimages 命令，需支持 -list 选项）
- Pillow（用于图片格式转换）
- tqdm（用于进度条）
"""

import os
import sys
import subprocess
import argparse
import shutil
import re
from pathlib import Path

# 固定的工作根目录
ROOT_DIR = "/storage/emulated/0/termux"

try:
    from tqdm import tqdm
except ImportError:
    print("错误：未找到 tqdm 库。请先安装：pip install tqdm")
    sys.exit(1)

try:
    from PIL import Image
except ImportError:
    print("错误：未找到 Pillow 库。请先安装：pip install Pillow")
    sys.exit(1)

def check_pdfimages():
    """检查 pdfimages 命令是否可用"""
    if shutil.which("pdfimages") is None:
        tqdm.write("错误：未找到 pdfimages 命令。请先安装 poppler-utils。")
        tqdm.write("  Termux: pkg install poppler-utils")
        tqdm.write("  Linux:  sudo apt install poppler-utils")
        tqdm.write("  macOS:  brew install poppler")
        sys.exit(1)

def resolve_path(path: str) -> str:
    """
    将给定路径转换为基于 ROOT_DIR 的绝对路径。
    如果已经是绝对路径，则直接返回；否则相对于 ROOT_DIR 解析。
    """
    if os.path.isabs(path):
        return path
    return os.path.join(ROOT_DIR, path)

def count_images_in_pdf(pdf_path):
    """
    使用 pdfimages -list 统计 PDF 中的图片数量。
    返回图片数量，如果出错返回 0。
    """
    try:
        result = subprocess.run(
            ["pdfimages", "-list", str(pdf_path)],
            capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            tqdm.write(f"警告：无法获取 {pdf_path.name} 的图片数量，将按 0 计")
            return 0
        lines = result.stdout.splitlines()
        count = 0
        start_parsing = False
        for line in lines:
            # 查找分隔行（由连字符组成），之后开始解析数据
            if re.match(r'^-+\s+-+\s+-+\s+-+\s+-+\s+-+', line):
                start_parsing = True
                continue
            if not start_parsing:
                continue
            if line.strip():
                count += 1
        return count
    except Exception as e:
        tqdm.write(f"警告：统计 {pdf_path.name} 图片数时出错：{e}")
        return 0

def detect_image_formats(pdf_path):
    """
    使用 pdfimages -list 检测 PDF 中所有图片的原始格式。
    返回一个集合，包含所有图片的格式名称（如 'jpeg', 'jp2', 'png', 'tiff', 'ccitt' 等）。
    如果 pdfimages 不支持 -list，返回空集合并打印警告。
    """
    try:
        result = subprocess.run(
            ["pdfimages", "-list", str(pdf_path)],
            capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            tqdm.write(f"警告：无法获取图片格式信息，将使用保守提取模式。错误：{result.stderr.strip()}")
            return set()

        lines = result.stdout.splitlines()
        formats = set()
        start_parsing = False
        for line in lines:
            if re.match(r'^-+\s+-+\s+-+\s+-+\s+-+\s+-+', line):
                start_parsing = True
                continue
            if not start_parsing:
                continue
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) < 4:
                continue
            for part in parts:
                lower_part = part.lower()
                if lower_part in ('jpeg', 'jp2', 'png', 'tiff', 'ccitt', 'gif', 'bmp', 'ppm', 'pgm', 'pbm'):
                    formats.add(lower_part)
                    break
        return formats
    except Exception as e:
        tqdm.write(f"警告：执行 pdfimages -list 时出错：{e}")
        return set()

def should_use_jpeg(pdf_path, force_no_jpeg=False):
    """
    判断是否应该使用 -j 参数。
    如果 force_no_jpeg 为 True，则始终返回 False。
    否则，检测 PDF 中是否包含 JPEG/JP2 格式，包含则返回 True。
    """
    if force_no_jpeg:
        return False
    formats = detect_image_formats(pdf_path)
    return any(fmt in formats for fmt in ('jpeg', 'jp2'))

def convert_to_png(image_path):
    """
    将单个图片文件转换为 PNG 格式，转换后删除原文件。
    返回转换后的 PNG 文件路径，如果转换失败则返回 None。
    """
    try:
        with Image.open(image_path) as img:
            png_path = image_path.with_suffix('.png')
            img.save(png_path, 'PNG')
        image_path.unlink()
        return png_path
    except Exception as e:
        tqdm.write(f"    转换失败 {image_path.name}: {e}")
        return None

def convert_images_in_dir(dir_path, total=None, desc=None):
    """
    扫描目录下的常见图片格式（由 pdfimages 产生），将其转换为 PNG。
    支持扩展名：.ppm, .pgm, .pbm, .jpg, .jpeg, .jp2, .tif, .tiff
    如果 total 为 None，则不显示进度条；否则显示进度条，total 应为该目录下需要转换的图片总数。
    desc 为进度条描述（如 "转换 XXX"）。
    返回转换成功的文件数量。
    """
    image_extensions = {'.ppm', '.pgm', '.pbm', '.jpg', '.jpeg', '.jp2', '.tif', '.tiff'}
    # 收集需要转换的文件列表
    to_convert = []
    for file_path in dir_path.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in image_extensions:
            to_convert.append(file_path)
    if not to_convert:
        return 0
    converted = 0
    # 如果提供了 total，则使用进度条，否则直接循环
    if total is not None:
        # 使用实际需要转换的文件数作为进度条总数（避免传入的 total 不准确）
        actual_total = len(to_convert)
        # 自定义进度条格式，与主进度条保持一致
        bar_format = '{desc}: {n_fmt}/{total_fmt}[{percentage:.2f}%]|{bar}| {r_bar}'
        pbar = tqdm(total=actual_total, desc=desc or f"转换 {dir_path.name}", unit="张",
                    bar_format=bar_format, leave=False)
        for img_path in to_convert:
            if convert_to_png(img_path):
                converted += 1
            pbar.update(1)
        pbar.close()
    else:
        for img_path in to_convert:
            if convert_to_png(img_path):
                converted += 1
    return converted

def extract_images_from_pdf(pdf_path, output_root="output", use_jpeg=None, to_png=True):
    """
    对单个 PDF 提取图片。
    use_jpeg: None 表示自动判断；True 强制使用 -j；False 强制不使用。
    to_png: 是否将提取的图片转换为 PNG（转换后删除原始文件）。
    返回该 PDF 提取的图片数量（转换前的原始图片数）。
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        tqdm.write(f"跳过：文件不存在 {pdf_path}")
        return 0

    pdf_stem = pdf_path.stem
    out_dir = Path(output_root) / pdf_stem
    out_dir.mkdir(parents=True, exist_ok=True)

    if use_jpeg is None:
        use_jpeg = should_use_jpeg(pdf_path, force_no_jpeg=False)
    cmd = ["pdfimages"]
    if use_jpeg:
        cmd.append("-j")
    cmd.append(str(pdf_path))
    prefix = str(out_dir / pdf_stem)
    cmd.append(prefix)

    jpeg_flag = "是" if use_jpeg else "否"
    tqdm.write(f"处理：{pdf_path.name} (使用 -j: {jpeg_flag}) -> {out_dir}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            files = list(out_dir.glob(f"{pdf_stem}-*"))
            image_count = len(files)
            tqdm.write(f"  ✔ 提取完成，生成 {image_count} 个文件")
            if to_png and image_count > 0:
                # 调用转换函数，传入图片数量用于进度条，描述为 "转换 {pdf_stem}"
                num = convert_images_in_dir(out_dir, total=image_count, desc=f"转换 {pdf_stem}")
                tqdm.write(f"  ✔ 转换为 PNG ({num} 个文件)")
            return image_count
        else:
            tqdm.write(f"  ✘ 提取失败，错误信息：{result.stderr.strip()}")
            return 0
    except Exception as e:
        tqdm.write(f"  ✘ 执行命令时出错：{e}")
        return 0

def main():
    parser = argparse.ArgumentParser(description="批量提取 PDF 中的图片，自动检测原格式并输出 PNG（可选）")
    parser.add_argument("input", nargs="?", default=".", help="输入目录或单个 PDF 文件（默认当前目录）")
    parser.add_argument("-o", "--output", default="output", help="输出根目录（默认 ./output）")
    parser.add_argument("--no-jpeg", action="store_true", help="强制不使用 -j 参数（所有图片均提取为 PPM/PBM 等无损格式）")
    parser.add_argument("--no-png", action="store_true", help="禁用 PNG 转换，保留提取的原始格式")
    args = parser.parse_args()

    # 检查根目录是否存在
    if not os.path.isdir(ROOT_DIR):
        tqdm.write(f"错误：工作根目录不存在或无法访问 -> {ROOT_DIR}")
        sys.exit(1)

    check_pdfimages()

    # 将输入和输出路径转换到根目录下（如果它们是相对路径）
    input_arg = resolve_path(args.input)
    output_arg = resolve_path(args.output)

    input_path = Path(input_arg)
    if input_path.is_file():
        # 单个 PDF 文件，不显示主进度条
        if input_path.suffix.lower() == ".pdf":
            extract_images_from_pdf(
                input_path,
                output_arg,
                use_jpeg=(not args.no_jpeg if args.no_jpeg else None),
                to_png=not args.no_png
            )
        else:
            tqdm.write("错误：输入文件不是 PDF 格式")
            sys.exit(1)
    elif input_path.is_dir():
        # 目录，查找所有 PDF 文件
        pdf_files = list(input_path.glob("*.pdf")) + list(input_path.glob("*.PDF"))
        if not pdf_files:
            tqdm.write(f"在目录 {input_path} 中未找到 PDF 文件。")
            return

        tqdm.write(f"找到 {len(pdf_files)} 个 PDF 文件，正在统计图片总数...")
        # 预先统计每个 PDF 的图片数量
        pdf_image_counts = {}
        total_images = 0
        for pdf in pdf_files:
            cnt = count_images_in_pdf(pdf)
            pdf_image_counts[pdf] = cnt
            total_images += cnt

        if total_images == 0:
            tqdm.write("警告：未检测到任何图片，可能 pdfimages -list 不支持或所有 PDF 无图片。仍将尝试提取。")
            use_file_count = True
            total = len(pdf_files)
            desc = "处理PDF"
            unit = "个文件"
            bar_fmt = '{desc}: {n_fmt}/{total_fmt}[{percentage:.2f}%]|{bar}| {r_bar}'
        else:
            use_file_count = False
            total = total_images
            desc = "提取图片"
            unit = "张"
            bar_fmt = '{desc}: {n_fmt}/{total_fmt}[{percentage:.2f}%]|{bar}| {r_bar}'

        # 创建主进度条
        pbar = tqdm(total=total, desc=desc, unit=unit, bar_format=bar_fmt)

        for pdf in pdf_files:
            extracted = extract_images_from_pdf(
                pdf,
                output_arg,
                use_jpeg=(not args.no_jpeg if args.no_jpeg else None),
                to_png=not args.no_png
            )
            if use_file_count:
                pbar.update(1)
            else:
                pbar.update(extracted)
        pbar.close()
        tqdm.write("\n全部处理完成！")
    else:
        tqdm.write(f"错误：路径不存在 {input_path}")
        sys.exit(1)

if __name__ == "__main__":
    main()