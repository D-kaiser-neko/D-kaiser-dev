#!/usr/bin/env python3
"""交互式图片格式转换工具：PNG/JPG/WebP/AVIF 互转，成功后删除原图。（多线程+防刷屏版）
目标目录：/storage/emulated/0/termux
"""

import sys
import shutil
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from PIL import Image
except ImportError:
    print("❌ 缺少 Pillow，请运行: pip install Pillow")
    sys.exit(1)

try:
    from tqdm import tqdm
except ImportError:
    print("❌ 缺少 tqdm，请运行: pip install tqdm")
    sys.exit(1)

# ─── AVIF 支持检测（三层回退）──────────────────────────────────
AVIF_METHOD = None  # "builtin" | "plugin" | "cli" | None

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
    _enc = shutil.which("avifenc")
    _dec = shutil.which("avifdec")
    if _enc and _dec:
        AVIF_METHOD = "cli"

AVIF_AVAILABLE = AVIF_METHOD is not None

# ─── 格式配置表 ───────────────────────────────────────────────
FORMAT_MAP = {
    "1": {"ext": ".png",  "pil_fmt": "PNG",  "label": "PNG"},
    "2": {"ext": ".jpg",  "pil_fmt": "JPEG", "label": "JPG"},
    "3": {"ext": ".webp", "pil_fmt": "WEBP", "label": "WebP"},
    "4": {"ext": ".avif", "pil_fmt": "AVIF", "label": "AVIF"},
}

SAVE_PARAMS = {
    "PNG":  {"compress_level": 6},
    "JPEG": {"quality": 100},
    "WEBP": {"quality": 100, "method": 4},
    "AVIF": {"quality": 100, "speed": 6},
}


def show_menu(title: str) -> str:
    """显示选择菜单并返回用户输入编号。"""
    print(f"\n{'='*40}")
    print(f"  {title}")
    print(f"{'='*40}")
    for key, info in FORMAT_MAP.items():
        avail = ""
        if info["label"] == "AVIF":
            if not AVIF_AVAILABLE:
                avail = " (❌ 未安装)"
            elif AVIF_METHOD == "cli":
                avail = " (⚡ 命令行模式)"
            elif AVIF_METHOD == "builtin":
                avail = " (✅ 内置)"
            elif AVIF_METHOD == "plugin":
                avail = " (✅ 插件)"
        print(f"  {key}. {info['label']}{avail}")
    print(f"{'='*40}")
    while True:
        choice = input("请输入编号: ").strip()
        if choice in FORMAT_MAP:
            if choice == "4" and not AVIF_AVAILABLE:
                print("⚠️  AVIF 支持不可用，请在 Termux 中运行:")
                print("    pkg install libavif")
                print("    pip install --upgrade --force-reinstall Pillow")
                print("    # 或: pip install pillow-avif-plugin")
                continue
            return choice
        print("❌ 无效输入，请重新选择")


def ask_workers(default: int = 8) -> int:
    """询问并发线程数，直接回车使用默认值，非法输入自动回退到默认值。"""
    raw = input(f"⚙️  请输入并发线程数 (直接回车默认 {default}): ").strip()
    if not raw:
        return default
    try:
        val = int(raw)
        if val < 1:
            print(f"⚠️  线程数不能小于 1，已自动使用默认值 {default}")
            return default
        return val
    except ValueError:
        print(f"⚠️  无效数字，已自动使用默认值 {default}")
        return default


def collect_files(directory: Path, ext: str) -> list[Path]:
    """递归收集本目录及子目录中指定扩展名的图片文件（大小写兼容 + 去重）。"""
    seen = set()
    files = []
    for pattern in [f"**/*{ext}", f"**/*{ext.upper()}"]:
        for f in sorted(directory.glob(pattern)):
            if not f.is_file():
                continue
            resolved = f.resolve()
            if resolved not in seen:
                seen.add(resolved)
                files.append(f)
    return files


def _cli_avif_decode(src: Path, dst: Path, dst_fmt: dict) -> None:
    """用 avifdec 解码 AVIF → 临时 PNG，再用 Pillow 转为目标格式。"""
    tmp_png = dst.with_suffix(".tmp_decode.png")
    try:
        subprocess.run(
            ["avifdec", str(src), str(tmp_png)],
            check=True, capture_output=True
        )
        img = Image.open(tmp_png)
        needs_rgb = dst_fmt["pil_fmt"] == "JPEG"
        if needs_rgb and img.mode in ("RGBA", "LA", "PA"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1])
            img = bg
        elif needs_rgb and img.mode != "RGB":
            img = img.convert("RGB")
        params = SAVE_PARAMS.get(dst_fmt["pil_fmt"], {})
        img.save(dst, dst_fmt["pil_fmt"], **params)
    finally:
        tmp_png.unlink(missing_ok=True)


def _cli_avif_encode(src: Path, dst: Path, quality: int = 80, speed: int = 6) -> None:
    """用 Pillow 将源图转为临时 PNG，再用 avifenc 编码为 AVIF。"""
    tmp_png = dst.with_suffix(".tmp_encode.png")
    try:
        img = Image.open(src)
        img.save(tmp_png, "PNG")
        subprocess.run(
            ["avifenc", "-q", str(quality), "-s", str(speed),
             str(tmp_png), str(dst)],
            check=True, capture_output=True
        )
    finally:
        tmp_png.unlink(missing_ok=True)


def convert_image(src: Path, dst: Path, src_fmt: dict, dst_fmt: dict) -> None:
    """单张图片转换核心逻辑。"""
    is_src_avif = src_fmt["pil_fmt"] == "AVIF"
    is_dst_avif = dst_fmt["pil_fmt"] == "AVIF"

    if AVIF_METHOD == "cli" and (is_src_avif or is_dst_avif):
        if is_src_avif:
            _cli_avif_decode(src, dst, dst_fmt)
        else:
            _cli_avif_encode(src, dst,
                             quality=SAVE_PARAMS["AVIF"].get("quality", 80),
                             speed=SAVE_PARAMS["AVIF"].get("speed", 6))
        return

    img = Image.open(src)
    needs_rgb = dst_fmt["pil_fmt"] == "JPEG"
    if needs_rgb and img.mode in ("RGBA", "LA", "PA"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        img = bg
    elif needs_rgb and img.mode != "RGB":
        img = img.convert("RGB")

    params = SAVE_PARAMS.get(dst_fmt["pil_fmt"], {})
    img.save(dst, dst_fmt["pil_fmt"], **params)


def _process_one(src_path: Path, dst_path: Path, src_fmt: dict, dst_fmt: dict) -> tuple[Path, bool, str]:
    """单张图片转换任务（供线程池调用）。"""
    try:
        if dst_path.exists():
            raise FileExistsError(f"{dst_path.name} 已存在")
        convert_image(src_path, dst_path, src_fmt, dst_fmt)
        src_path.unlink()
        return (src_path, True, "")
    except Exception as e:
        return (src_path, False, str(e))


def main():
    # 固定目标目录
    TARGET_DIR = Path("/storage/emulated/0/termux")
    if not TARGET_DIR.is_dir():
        print(f"❌ 目标目录不存在: {TARGET_DIR}")
        sys.exit(1)

    if AVIF_AVAILABLE:
        method_desc = {
            "builtin": "Pillow 内置 AvifImagePlugin",
            "plugin":  "pillow-avif-plugin",
            "cli":     "avifenc/avifdec 命令行工具",
        }
        print(f"ℹ️  AVIF 支持: {method_desc[AVIF_METHOD]}")
    else:
        print("⚠️  AVIF 不可用，安装方法:")
        print("    pkg install libavif && pip install --upgrade Pillow")

    # 1. 交互选择格式
    src_choice = show_menu("📥 选择【源】图片格式")
    dst_choice = show_menu("📤 选择【目标】图片格式")

    if src_choice == dst_choice:
        print("⚠️  源格式与目标格式相同，无需转换")
        return

    # 2. 询问线程数（默认 8）
    max_workers = ask_workers(default=8)

    src_fmt = FORMAT_MAP[src_choice]
    dst_fmt = FORMAT_MAP[dst_choice]

    # 3. 扫描固定目录下的文件
    directory = TARGET_DIR
    files = collect_files(directory, src_fmt["ext"])
    if not files:
        print(f"⚠️  目录 {directory} 及其子目录下未找到任何 {src_fmt['label']} 文件")
        return

    print(f"\n🔄 {src_fmt['label']} → {dst_fmt['label']} | 共 {len(files)} 张 | "
          f"线程数: {max_workers} | 成功后删除原图\n")

    # 4. 多线程批量转换 + 动态防刷屏进度条
    success, failed = 0, 0
    errors = []
    desc = f"🖼️  {src_fmt['label']} → {dst_fmt['label']}"

    tasks = [(src_path, src_path.with_suffix(dst_fmt["ext"])) for src_path in files]

    with tqdm(total=len(tasks), desc=desc, unit="img", dynamic_ncols=True, leave=True) as pbar:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(_process_one, src, dst, src_fmt, dst_fmt): src
                for src, dst in tasks
            }

            for future in as_completed(future_map):
                src_path, ok, err_msg = future.result()
                if ok:
                    success += 1
                    pbar.set_postfix(ok=success, fail=failed)
                else:
                    failed += 1
                    errors.append((src_path, err_msg))
                    err_name = src_path.name
                    if len(err_name) > 25:
                        err_name = err_name[:22] + "..."
                    pbar.set_postfix(ok=success, fail=failed, err=err_name)

                pbar.update(1)

    # 5. 结果汇总与日志落盘
    print(f"\n✅ 完成！成功: {success}, 失败: {failed}")
    if failed == 0:
        print(f"🗑️  所有原始 {src_fmt['label']} 文件已安全删除")
    else:
        print(f"⚠️  {failed} 张转换失败，对应原文件已保留")
        log_file = Path("convert_errors.log")
        with open(log_file, "w", encoding="utf-8") as f:
            for src_path, err_msg in errors:
                f.write(f"❌ {src_path}\n   -> {err_msg}\n\n")
        print(f"📝 详细错误日志已保存至: {log_file.resolve()}")


if __name__ == "__main__":
    main()