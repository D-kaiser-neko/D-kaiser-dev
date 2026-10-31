#!/usr/bin/env python3
"""交互式/命令行 图片格式转换工具：PNG/JPG/WebP/AVIF 互转（多线程+防刷屏版）
支持自定义来源目录与保存目录，保留子目录结构。支持源格式为 '*' (所有格式)。
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
    "JPEG": {"quality": 10},
    "WEBP": {"quality": 100, "method": 4},
    "AVIF": {"quality": 100, "speed": 6},
}


# ─── 交互与解析工具函数 ───────────────────────────────────────
def parse_format_arg(fmt_str: str) -> str | None:
    """将命令行输入的格式字符串转换为 FORMAT_MAP 的 key (1-4) 或 '*'。"""
    fmt_str = fmt_str.strip()
    if fmt_str == "*":
        return "*"
    
    fmt_lower = fmt_str.lower().lstrip('.')
    if fmt_lower in FORMAT_MAP:
        return fmt_lower
        
    for key, info in FORMAT_MAP.items():
        if fmt_lower == info["ext"].lstrip('.') or fmt_lower == info["label"].lower():
            return key
    return None


def get_valid_directory(prompt: str) -> Path:
    """交互获取有效的目录路径，支持 ~ 展开，不存在时可自动创建。"""
    while True:
        path_str = input(prompt).strip()
        if not path_str:
            print("⚠️  路径不能为空，请重新输入。")
            continue

        path = Path(path_str).expanduser().resolve()

        if path.is_dir():
            return path

        choice = input(f"⚠️  目录不存在: {path}\n   是否创建？(y/n): ").strip().lower()
        if choice == "y":
            try:
                path.mkdir(parents=True, exist_ok=True)
                print(f"✅ 已创建目录: {path}\n")
                return path
            except Exception as e:
                print(f"❌ 创建失败: {e}\n")
        else:
            print("请重新输入。\n")


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
    print(f"  *. 所有支持的格式 (仅限源格式)")
    print(f"{'='*40}")
    while True:
        choice = input("请输入编号: ").strip()
        if choice == "*":
            return "*"
        if choice in FORMAT_MAP:
            if choice == "4" and not AVIF_AVAILABLE:
                print("⚠️  AVIF 支持不可用，请在 Termux 中运行:")
                print("    pkg install libavif")
                print("    pip install --upgrade --force-reinstall Pillow")
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


# ─── 文件收集 ─────────────────────────────────────────────────
def collect_files(directory: Path, ext: str) -> list[Path]:
    """递归收集指定扩展名的图片文件。"""
    seen = set()
    files = []
    for pattern in [f"**/*{ext}", f"**/*{ext.upper()}"]:
        for f in sorted(directory.glob(pattern)):
            if not f.is_file(): continue
            resolved = f.resolve()
            if resolved not in seen:
                seen.add(resolved)
                files.append(f)
    return files

def collect_all_files(directory: Path) -> list[tuple[Path, dict]]:
    """递归收集所有支持格式的图片文件，返回 (文件路径, 格式字典) 列表。"""
    files_with_fmt = []
    seen = set()
    for key, fmt_info in FORMAT_MAP.items():
        ext = fmt_info["ext"]
        for pattern in [f"**/*{ext}", f"**/*{ext.upper()}"]:
            for f in sorted(directory.glob(pattern)):
                if not f.is_file(): continue
                resolved = f.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    files_with_fmt.append((f, fmt_info))
    return files_with_fmt


# ─── 转换核心 ────────────────────────────────────────────────
def _cli_avif_decode(src: Path, dst: Path, dst_fmt: dict) -> None:
    tmp_png = dst.with_suffix(".tmp_decode.png")
    try:
        subprocess.run(["avifdec", str(src), str(tmp_png)], check=True, capture_output=True)
        img = Image.open(tmp_png)
        if dst_fmt["pil_fmt"] == "JPEG" and img.mode in ("RGBA", "LA", "PA"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1])
            img = bg
        elif dst_fmt["pil_fmt"] == "JPEG" and img.mode != "RGB":
            img = img.convert("RGB")
        img.save(dst, dst_fmt["pil_fmt"], **SAVE_PARAMS.get(dst_fmt["pil_fmt"], {}))
    finally:
        tmp_png.unlink(missing_ok=True)

def _cli_avif_encode(src: Path, dst: Path) -> None:
    tmp_png = dst.with_suffix(".tmp_encode.png")
    try:
        img = Image.open(src)
        img.save(tmp_png, "PNG")
        subprocess.run(
            ["avifenc", "-q", str(SAVE_PARAMS["AVIF"]["quality"]), 
             "-s", str(SAVE_PARAMS["AVIF"]["speed"]), str(tmp_png), str(dst)],
            check=True, capture_output=True
        )
    finally:
        tmp_png.unlink(missing_ok=True)

def convert_image(src: Path, dst: Path, src_fmt: dict, dst_fmt: dict) -> None:
    is_src_avif = src_fmt["pil_fmt"] == "AVIF"
    is_dst_avif = dst_fmt["pil_fmt"] == "AVIF"

    if AVIF_METHOD == "cli" and (is_src_avif or is_dst_avif):
        if is_src_avif:
            _cli_avif_decode(src, dst, dst_fmt)
        else:
            _cli_avif_encode(src, dst)
        return

    img = Image.open(src)
    if dst_fmt["pil_fmt"] == "JPEG":
        if img.mode in ("RGBA", "LA", "PA"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1])
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")

    img.save(dst, dst_fmt["pil_fmt"], **SAVE_PARAMS.get(dst_fmt["pil_fmt"], {}))

def _process_one(src_path: Path, dst_path: Path, src_fmt: dict, dst_fmt: dict) -> tuple[Path, bool, str]:
    try:
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        if dst_path.exists():
            raise FileExistsError(f"{dst_path.name} 已存在")
        convert_image(src_path, dst_path, src_fmt, dst_fmt)
        return (src_path, True, "")
    except Exception as e:
        return (src_path, False, str(e))


# ─── 主流程 ──────────────────────────────────────────────────
def main():
    # 判断是否使用命令行参数模式
    if len(sys.argv) >= 5:
        print("⚡ 检测到命令行参数，跳过交互模式...")
        
        src_dir = Path(sys.argv[1]).expanduser().resolve()
        if not src_dir.is_dir():
            print(f"❌ 来源目录不存在: {src_dir}"); sys.exit(1)

        dst_dir = Path(sys.argv[2]).expanduser().resolve()
        if not dst_dir.is_dir():
            try:
                dst_dir.mkdir(parents=True, exist_ok=True)
                print(f"✅ 已自动创建目标目录: {dst_dir}")
            except Exception as e:
                print(f"❌ 创建目标目录失败: {e}"); sys.exit(1)

        src_choice = parse_format_arg(sys.argv[3])
        if not src_choice:
            print(f"❌ 无效的原格式: {sys.argv[3]} (支持: png, jpg, webp, avif, * 或 1-4)"); sys.exit(1)

        dst_choice = parse_format_arg(sys.argv[4])
        if not dst_choice or dst_choice == "*":
            print(f"❌ 无效的目标格式: {sys.argv[4]} (不支持目标格式为 *)"); sys.exit(1)

        max_workers = 8
        if len(sys.argv) > 5:
            try:
                max_workers = int(sys.argv[5])
                if max_workers < 1: max_workers = 8
            except ValueError:
                max_workers = 8

    else:
        # 交互模式
        print()
        src_dir = get_valid_directory("📂 请输入【图片来源】目录路径: ")
        dst_dir = get_valid_directory("📂 请输入【图片保存】目录路径: ")
        src_choice = show_menu("📥 选择【源】图片格式")
        dst_choice = show_menu("📤 选择【目标】图片格式")
        max_workers = ask_workers(default=8)

    # ─── 公共执行逻辑 ────────────────────────────────────────
    if (src_choice == "4" or dst_choice == "4") and not AVIF_AVAILABLE:
        print("❌ 涉及 AVIF 格式，但当前环境不支持！请安装依赖。"); sys.exit(1)

    dst_fmt = FORMAT_MAP[dst_choice]
    tasks = []

    # 构建任务列表
    if src_choice == "*":
        files_with_fmt = collect_all_files(src_dir)
        if not files_with_fmt:
            print(f"⚠️ 目录 {src_dir} 及其子目录下未找到任何支持的图片文件"); return
        
        for src_path, actual_src_fmt in files_with_fmt:
            rel = src_path.relative_to(src_dir)
            # 如果源格式和目标格式相同，添加 _converted 后缀防止覆盖
            if actual_src_fmt["ext"] == dst_fmt["ext"]:
                new_name = f"{src_path.stem}_converted{dst_fmt['ext']}"
                dst_path = dst_dir / rel.with_name(new_name)
            else:
                dst_path = dst_dir / rel.with_suffix(dst_fmt["ext"])
            tasks.append((src_path, dst_path, actual_src_fmt, dst_fmt))
        desc = f"🖼️  所有格式 → {dst_fmt['label']}"
    else:
        src_fmt = FORMAT_MAP[src_choice]
        files = collect_files(src_dir, src_fmt["ext"])
        if not files:
            print(f"⚠️ 目录 {src_dir} 及其子目录下未找到任何 {src_fmt['label']} 文件"); return
        
        for src_path in files:
            rel = src_path.relative_to(src_dir)
            if src_fmt["ext"] == dst_fmt["ext"]:
                new_name = f"{src_path.stem}_converted{dst_fmt['ext']}"
                dst_path = dst_dir / rel.with_name(new_name)
            else:
                dst_path = dst_dir / rel.with_suffix(dst_fmt["ext"])
            tasks.append((src_path, dst_path, src_fmt, dst_fmt))
        desc = f"🖼️  {src_fmt['label']} → {dst_fmt['label']}"

    print(f"\n🔄 转换任务 | 共 {len(tasks)} 张 | 线程数: {max_workers}")
    print(f"📁 来源: {src_dir}")
    print(f"📁 保存: {dst_dir}\n")

    # 多线程批量转换 + 进度条
    success, failed = 0, 0
    errors = []

    with tqdm(total=len(tasks), desc=desc, unit="img", dynamic_ncols=True, leave=True) as pbar:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(_process_one, src, dst, s_fmt, d_fmt): src
                for src, dst, s_fmt, d_fmt in tasks
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
                    if len(err_name) > 25: err_name = err_name[:22] + "..."
                    pbar.set_postfix(ok=success, fail=failed, err=err_name)
                pbar.update(1)

    # 结果汇总
    print(f"\n✅ 完成！成功: {success}, 失败: {failed}")
    if failed > 0:
        log_file = Path("convert_errors.log")
        with open(log_file, "w", encoding="utf-8") as f:
            for src_path, err_msg in errors:
                f.write(f"❌ {src_path}\n   -> {err_msg}\n\n")
        print(f"📝 详细错误日志已保存至: {log_file.resolve()}")


if __name__ == "__main__":
    main()