#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
像素级无损检测工具
用法: python check_lossless.py 文件1 文件2
用于验证格式转换是否无损: 逐像素比较两张图片。
退出码: 0=像素级一致(无损)  1=有差异(有损)  2=错误
"""

import sys
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

try:
    from PIL import Image, ImageChops
except ImportError:
    print("❌ 缺少 Pillow，请运行: pip install Pillow")
    sys.exit(2)

# ─── AVIF 读取支持（三层回退，与转换脚本一致）───
AVIF_METHOD = None
try:
    from PIL import AvifImagePlugin  # noqa: F401
    AVIF_METHOD = "builtin"
except ImportError:
    pass
if AVIF_METHOD is None:
    try:
        import pillow_avif_plugin  # noqa: F401
        AVIF_METHOD = "plugin"
    except ImportError:
        pass
if AVIF_METHOD is None:
    if shutil.which("avifdec"):
        AVIF_METHOD = "cli"


def load_image(path: Path) -> Image.Image:
    """加载图片；AVIF 在无插件时用 avifdec 解码到临时 PNG。"""
    if path.suffix.lower() in (".avif", ".avifs") and AVIF_METHOD == "cli":
        fd, tmp_name = tempfile.mkstemp(suffix=".png")
        tmp = Path(tmp_name)
        try:
            subprocess.run(["avifdec", str(path), str(tmp)],
                           check=True, capture_output=True)
            img = Image.open(tmp)
            img.load()          # 先读入内存, 之后才能删临时文件
            return img
        finally:
            try:
                tmp.unlink()
            except OSError:
                pass
    img = Image.open(path)
    img.load()
    return img


def prep_mode(img: Image.Image) -> Image.Image:
    """把各种 mode 归一化到 RGB / RGBA，便于比较。"""
    if img.mode == "P":
        img = img.convert("RGBA" if "transparency" in img.info else "RGB")
    if img.mode in ("1", "L", "I", "I;16", "CMYK", "YCbCr"):
        img = img.convert("RGB")
    elif img.mode in ("LA", "PA"):
        img = img.convert("RGBA")
    return img


def align_alpha(a: Image.Image, b: Image.Image, notes: list):
    """处理一方有 alpha、一方没有的情况。返回 (a, b, info_loss)。"""
    info_loss = False
    if a.mode == b.mode:
        return a, b, info_loss

    def strip(im, tag):
        nonlocal info_loss
        alpha = im.split()[-1]
        if alpha.getextrema() == (255, 255):
            notes.append(f"{tag} 的 alpha 通道全为不透明，已剥离后比较")
            return im.convert("RGB")
        notes.append(f"⚠️  {tag} 含半透明像素，而另一方没有 alpha 通道 → alpha 信息已丢失")
        info_loss = True
        return im.convert("RGB")

    if a.mode == "RGBA":
        a = strip(a, "文件1")
        b = b.convert("RGB")
    else:
        b = strip(b, "文件2")
        a = a.convert("RGB")
    return a, b, info_loss


def channel_stats(diff_ch, n_pixels: int):
    """单通道: 返回 (非零像素数, 最大差值, 平方和均值)。"""
    hist = diff_ch.histogram()
    nonzero = sum(hist[1:])
    max_diff = diff_ch.getextrema()[1]
    sq_sum = sum(v * i * i for i, v in enumerate(hist))
    return nonzero, max_diff, sq_sum / n_pixels


def compare(a: Image.Image, b: Image.Image):
    """返回结果 dict。"""
    if a.size != b.size:
        return {"identical": False, "size_mismatch": True}

    n = a.size[0] * a.size[1]
    if a.tobytes() == b.tobytes():
        return {"identical": True}

    diff = ImageChops.difference(a, b)
    channels = diff.split()
    max_diff = 0
    mse_acc = 0.0
    diff_pixels = 0
    for ch in channels:
        nz, md, mse_ch = channel_stats(ch, n)
        max_diff = max(max_diff, md)
        mse_acc += mse_ch
        diff_pixels = max(diff_pixels, nz)   # 任一通道有差异即视为该像素有差异(近似)

    mse = mse_acc / len(channels)
    psnr = 99.0 if mse == 0 else 10 * math.log10(255.0 * 255.0 / mse)
    return {
        "identical": False,
        "ratio": diff_pixels / n,
        "max_diff": max_diff,
        "psnr": psnr,
    }


def describe(path: Path, img: Image.Image) -> str:
    fmt = img.format or path.suffix.lstrip(".").upper()
    return f"{path.name}  格式={fmt}  mode={img.mode}  尺寸={img.size[0]}x{img.size[1]}"


def main():
    if len(sys.argv) != 3:
        print("用法: python check_lossless.py 文件1 文件2")
        sys.exit(2)

    p1, p2 = Path(sys.argv[1]), Path(sys.argv[2])
    for p in (p1, p2):
        if not p.is_file():
            print(f"❌ 文件不存在: {p}")
            sys.exit(2)

    try:
        img1 = prep_mode(load_image(p1))
        img2 = prep_mode(load_image(p2))
    except Exception as e:
        print(f"❌ 无法解码图片: {e}")
        sys.exit(2)

    notes = []
    img1, img2, info_loss = align_alpha(img1, img2, notes)

    print("=" * 56)
    print("🔬 像素级无损检测")
    print("-" * 56)
    print("文件1:", describe(p1, img1))
    print("文件2:", describe(p2, img2))
    if AVIF_METHOD and (p1.suffix.lower() == ".avif" or p2.suffix.lower() == ".avif"):
        print(f"AVIF 解码方式: {AVIF_METHOD}")
    for note in notes:
        print("  ·", note)
    print("-" * 56)

    res = compare(img1, img2)

    if res.get("size_mismatch"):
        print("判定: ❌ 有损 (两图尺寸不同，无法构成无损转换)")
        print("=" * 56)
        sys.exit(1)

    if res["identical"] and not info_loss:
        print("判定: ✅ 无损 (像素级完全一致)")
        print("=" * 56)
        sys.exit(0)

    if res["identical"] and info_loss:
        print("判定: ❌ 有损 (RGB 像素一致，但 alpha/通道信息丢失)")
        print("=" * 56)
        sys.exit(1)

    print("判定: ❌ 有损 (像素不一致)")
    print(f"  差异像素占比 : {res['ratio']*100:.2f}%")
    print(f"  单通道最大差 : {res['max_diff']}")
    print(f"  PSNR         : {res['psnr']:.2f} dB")
    if res["psnr"] >= 50 and res["max_diff"] <= 2:
        print("  程度评估     : 视觉近无损 (差异极小, 但数学上非无损)")
    elif res["psnr"] >= 40:
        print("  程度评估     : 轻微损失 (细心观察可能可见)")
    else:
        print("  程度评估     : 明显损失")
    print("=" * 56)
    sys.exit(1)


if __name__ == "__main__":
    main()