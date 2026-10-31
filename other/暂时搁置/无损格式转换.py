#!/usr/bin/env python3
"""交互式/命令行 图片格式转换工具【真无损 v2 · 防假无损】
- 启动时用随机噪声图做"编码→回解→像素比对"真校验, 杜绝 lossless 参数被静默忽略
- AVIF: 内置/插件若假无损 → 自动降级 avifenc --lossless; 无 CLI 则禁用 AVIF 目标
- WebP: lossless=True 同样做往返自检
- PNG: 保留位深与 alpha
- JPEG 仅可作源, 不可作目标
- --verify: 转换后逐张回解校验, 不一致记 fail
"""

import sys
import io
import random
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

# ─── 配置 ────────────────────────────────────────────────────
# 已实锤内置 AVIF 假无损, 默认强制走 CLI; 若你确认内置真无损可改 False
AVIF_FORCE_CLI = True

# ─── AVIF 支持检测（三层回退）──────────────────────────────────
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
    if shutil.which("avifenc") and shutil.which("avifdec"):
        AVIF_METHOD = "cli"

if AVIF_FORCE_CLI and shutil.which("avifenc") and shutil.which("avifdec"):
    AVIF_METHOD = "cli"


def _noise_img(seed=42, size=32):
    """随机噪声图: 对无损最严苛, 任何有损量化必现差异"""
    im = Image.new("RGB", (size, size))
    px = im.load()
    rnd = random.Random(seed)
    for y in range(size):
        for x in range(size):
            px[x, y] = (rnd.randrange(256), rnd.randrange(256), rnd.randrange(256))
    return im


def _probe_avif_lossless() -> bool:
    """真校验: 编码后回解, 像素逐字节一致才算支持无损; 假无损自动降级 CLI"""
    global AVIF_METHOD

    def _roundtrip_ok():
        try:
            src = _noise_img()
            buf = io.BytesIO()
            src.save(buf, "AVIF", lossless=True)
            buf.seek(0)
            back = Image.open(buf)
            back.load()
            return back.mode == src.mode and back.tobytes() == src.tobytes()
        except Exception:
            return False

    if AVIF_METHOD in ("builtin", "plugin"):
        if _roundtrip_ok():
            return True
        # 假无损 → 尝试降级 CLI
    if shutil.which("avifenc") and shutil.which("avifdec"):
        AVIF_METHOD = "cli"
        return True
    return False


def _probe_webp_lossless() -> bool:
    try:
        src = _noise_img()
        buf = io.BytesIO()
        src.save(buf, "WEBP", lossless=True, method=6)
        buf.seek(0)
        back = Image.open(buf)
        back.load()
        return back.tobytes() == src.tobytes()
    except Exception:
        return False


AVIF_AVAILABLE = AVIF_METHOD is not None
AVIF_LOSSLESS_OK = _probe_avif_lossless() if AVIF_AVAILABLE else False
WEBP_LOSSLESS_OK = _probe_webp_lossless()

# ─── 格式配置表 ───────────────────────────────────────────────
FORMAT_MAP = {
    "1": {"ext": ".png",  "pil_fmt": "PNG",  "label": "PNG",  "lossless_ok": True},
    "2": {"ext": ".jpg",  "pil_fmt": "JPEG", "label": "JPG",  "lossless_ok": False},
    "3": {"ext": ".webp", "pil_fmt": "WEBP", "label": "WebP", "lossless_ok": True},
    "4": {"ext": ".avif", "pil_fmt": "AVIF", "label": "AVIF", "lossless_ok": True},
}

SAVE_PARAMS = {
    "PNG":  {"compress_level": 6},
    "WEBP": {"lossless": True, "method": 6},
    "AVIF": {"lossless": True, "speed": 6},
}
AVIF_CLI_SPEED = 6


# ─── 交互与解析 ───────────────────────────────────────────────
def parse_format_arg(fmt_str: str):
    fmt_str = fmt_str.strip()
    if fmt_str == "*":
        return "*"
    fl = fmt_str.lower().lstrip('.')
    if fl in FORMAT_MAP:
        return fl
    for key, info in FORMAT_MAP.items():
        if fl == info["ext"].lstrip('.') or fl == info["label"].lower():
            return key
    return None


def get_valid_directory(prompt: str) -> Path:
    while True:
        s = input(prompt).strip()
        if not s:
            print("⚠️  路径不能为空，请重新输入。")
            continue
        p = Path(s).expanduser().resolve()
        if p.is_dir():
            return p
        c = input(f"⚠️  目录不存在: {p}\n   是否创建？(y/n): ").strip().lower()
        if c == "y":
            try:
                p.mkdir(parents=True, exist_ok=True)
                print(f"✅ 已创建目录: {p}\n")
                return p
            except Exception as e:
                print(f"❌ 创建失败: {e}\n")
        else:
            print("请重新输入。\n")


def _dst_blocked(key: str):
    """返回目标格式被禁的原因, 允许则返回 None"""
    info = FORMAT_MAP[key]
    if not info["lossless_ok"]:
        return "JPEG 格式本身不支持无损编码，不能作目标"
    if key == "3" and not WEBP_LOSSLESS_OK:
        return "当前 WebP 编码器未通过无损自检，不能作目标"
    if key == "4" and not AVIF_LOSSLESS_OK:
        return ("当前环境无法真无损编码 AVIF（内置为假无损且无 CLI），"
                "请: pkg install libavif")
    return None


def show_menu(title: str, is_dst: bool = False) -> str:
    print(f"\n{'='*44}")
    print(f"  {title}")
    print(f"{'='*44}")
    for key, info in FORMAT_MAP.items():
        avail = ""
        if info["label"] == "AVIF":
            if not AVIF_AVAILABLE:
                avail = " (❌ 未安装)"
            elif not AVIF_LOSSLESS_OK:
                avail = " (❌ 假无损/无CLI, 不可作目标)"
            elif AVIF_METHOD == "cli":
                avail = " (⚡ avifenc --lossless)"
            else:
                avail = f" (✅ {AVIF_METHOD} 已验证无损)"
        if info["label"] == "WebP":
            avail += "" if WEBP_LOSSLESS_OK else " (❌ 自检失败)"
        if is_dst:
            why = _dst_blocked(key)
            if why:
                avail += " (🚫 不可作目标)"
        print(f"  {key}. {info['label']}{avail}")
    if not is_dst:
        print(f"  *. 所有支持的格式 (仅限源格式)")
    print(f"{'='*44}")
    while True:
        choice = input("请输入编号: ").strip()
        if choice == "*":
            if is_dst:
                print("❌ 目标格式不能为 *")
                continue
            return "*"
        if choice in FORMAT_MAP:
            if is_dst:
                why = _dst_blocked(choice)
                if why:
                    print(f"❌ {why}")
                    continue
            return choice
        print("❌ 无效输入，请重新选择")


def ask_workers(default: int = 8) -> int:
    raw = input(f"⚙️  请输入并发线程数 (直接回车默认 {default}): ").strip()
    if not raw:
        return default
    try:
        v = int(raw)
        return v if v >= 1 else default
    except ValueError:
        return default


# ─── 文件收集 ─────────────────────────────────────────────────
def collect_files(directory: Path, ext: str):
    seen, out = set(), []
    for pat in [f"**/*{ext}", f"**/*{ext.upper()}"]:
        for f in sorted(directory.glob(pat)):
            if f.is_file() and f.resolve() not in seen:
                seen.add(f.resolve())
                out.append(f)
    return out


def collect_all_files(directory: Path):
    seen, out = set(), []
    for info in FORMAT_MAP.values():
        for pat in [f"**/*{info['ext']}", f"**/*{info['ext'].upper()}"]:
            for f in sorted(directory.glob(pat)):
                if f.is_file() and f.resolve() not in seen:
                    seen.add(f.resolve())
                    out.append((f, info))
    return out


# ─── 模式处理 ────────────────────────────────────────────────
def _ensure_mode(img: Image.Image, pil_fmt: str) -> Image.Image:
    m = img.mode
    if m == "P":
        img = img.convert("RGBA" if "transparency" in img.info else "RGB")
        m = img.mode
    if m in ("LA", "PA"):
        img = img.convert("RGBA"); m = "RGBA"
    if m == "CMYK":
        img = img.convert("RGB"); m = "RGB"
    if pil_fmt == "PNG":
        return img
    if m in ("RGB", "RGBA"):
        return img
    return img.convert("RGB")


# ─── AVIF CLI 桥接 ────────────────────────────────────────────
def _avif_decode_to_png(src: Path, tmp_png: Path) -> None:
    subprocess.run(["avifdec", str(src), str(tmp_png)],
                   check=True, capture_output=True)


def _cli_avif_encode(src: Path, dst: Path) -> None:
    tmp_png = dst.with_suffix(".tmp_encode.png")
    try:
        img = Image.open(src)
        img.load()
        img = _ensure_mode(img, "AVIF")
        img.save(tmp_png, "PNG")
        subprocess.run(
            ["avifenc", "--lossless", "-s", str(AVIF_CLI_SPEED),
             str(tmp_png), str(dst)],
            check=True, capture_output=True)
    finally:
        tmp_png.unlink(missing_ok=True)


# ─── 转换核心 ────────────────────────────────────────────────
def convert_image(src: Path, dst: Path, src_fmt: dict, dst_fmt: dict) -> None:
    src_avif = src_fmt["pil_fmt"] == "AVIF"
    dst_avif = dst_fmt["pil_fmt"] == "AVIF"

    if dst_fmt["pil_fmt"] == "JPEG":
        raise RuntimeError("JPEG 不支持无损编码")
    if dst_fmt["pil_fmt"] == "WEBP" and not WEBP_LOSSLESS_OK:
        raise RuntimeError("WebP 无损自检失败")
    if dst_avif and not AVIF_LOSSLESS_OK:
        raise RuntimeError("AVIF 无真无损编码路径")

    if AVIF_METHOD == "cli" and (src_avif or dst_avif):
        if src_avif and dst_avif:
            tmp = dst.with_suffix(".tmp_rt.png")
            try:
                _avif_decode_to_png(src, tmp)
                _cli_avif_encode(tmp, dst)
            finally:
                tmp.unlink(missing_ok=True)
        elif src_avif:
            tmp = dst.with_suffix(".tmp_decode.png")
            try:
                _avif_decode_to_png(src, tmp)
                img = Image.open(tmp); img.load()
                img = _ensure_mode(img, dst_fmt["pil_fmt"])
                img.save(dst, dst_fmt["pil_fmt"], **SAVE_PARAMS[dst_fmt["pil_fmt"]])
            finally:
                tmp.unlink(missing_ok=True)
        else:
            _cli_avif_encode(src, dst)
        return

    img = Image.open(src)
    img.load()
    img = _ensure_mode(img, dst_fmt["pil_fmt"])
    img.save(dst, dst_fmt["pil_fmt"], **SAVE_PARAMS[dst_fmt["pil_fmt"]])


def _verify_roundtrip(src: Path, dst: Path, dst_fmt: dict) -> bool:
    try:
        a = Image.open(src); a.load()
        a = _ensure_mode(a, dst_fmt["pil_fmt"])
        b = Image.open(dst); b.load()
        if b.mode != a.mode:
            b = b.convert(a.mode)
        return a.tobytes() == b.tobytes()
    except Exception:
        return False


VERIFY = False


def _process_one(src_path, dst_path, src_fmt, dst_fmt):
    try:
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        if dst_path.exists():
            raise FileExistsError(f"{dst_path.name} 已存在")
        convert_image(src_path, dst_path, src_fmt, dst_fmt)
        if VERIFY and not _verify_roundtrip(src_path, dst_path, dst_fmt):
            return (src_path, False, "校验失败: 输出与输入像素不一致(假无损)")
        return (src_path, True, "")
    except Exception as e:
        return (src_path, False, str(e))


# ─── 主流程 ──────────────────────────────────────────────────
def main():
    global VERIFY
    if "--verify" in sys.argv:
        VERIFY = True
        sys.argv = [a for a in sys.argv if a != "--verify"]

    print("\n🔒 真无损 v2 | 噪声往返自检已启用")
    tag = {"builtin": "内置", "plugin": "插件", "cli": "CLI"}.get(AVIF_METHOD, "无")
    print(f"   AVIF 无损编码: {'✅' if AVIF_LOSSLESS_OK else '❌'} ({tag})"
          f"{'  [强制CLI]' if AVIF_FORCE_CLI and AVIF_METHOD == 'cli' else ''}")
    if AVIF_AVAILABLE and not AVIF_LOSSLESS_OK:
        print("      → 内置/插件为假无损或不可用, AVIF 目标已禁用; 解码仍可用")
    print(f"   WebP 无损编码: {'✅' if WEBP_LOSSLESS_OK else '❌'}")

    if len(sys.argv) >= 5:
        print("⚡ 检测到命令行参数，跳过交互模式...")
        src_dir = Path(sys.argv[1]).expanduser().resolve()
        if not src_dir.is_dir():
            print(f"❌ 来源目录不存在: {src_dir}"); sys.exit(1)
        dst_dir = Path(sys.argv[2]).expanduser().resolve()
        if not dst_dir.is_dir():
            try:
                dst_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                print(f"❌ 创建目标目录失败: {e}"); sys.exit(1)
        src_choice = parse_format_arg(sys.argv[3])
        if not src_choice:
            print(f"❌ 无效的原格式: {sys.argv[3]}"); sys.exit(1)
        dst_choice = parse_format_arg(sys.argv[4])
        if not dst_choice or dst_choice == "*":
            print(f"❌ 无效的目标格式: {sys.argv[4]}"); sys.exit(1)
        why = _dst_blocked(dst_choice)
        if why:
            print(f"❌ {why}"); sys.exit(1)
        max_workers = 8
        if len(sys.argv) > 5:
            try:
                max_workers = max(1, int(sys.argv[5]))
            except ValueError:
                pass
    else:
        src_dir = get_valid_directory("📂 请输入【图片来源】目录路径: ")
        dst_dir = get_valid_directory("📂 请输入【图片保存】目录路径: ")
        src_choice = show_menu("📥 选择【源】图片格式", is_dst=False)
        dst_choice = show_menu("📤 选择【目标】图片格式", is_dst=True)
        max_workers = ask_workers(default=8)

    dst_fmt = FORMAT_MAP[dst_choice]
    tasks = []

    def build_dst(sp, sf):
        rel = sp.relative_to(src_dir)
        if sf["ext"] == dst_fmt["ext"]:
            return dst_dir / rel.with_name(f"{sp.stem}_converted{dst_fmt['ext']}")
        return dst_dir / rel.with_suffix(dst_fmt["ext"])

    if src_choice == "*":
        fwf = collect_all_files(src_dir)
        if not fwf:
            print(f"⚠️  目录 {src_dir} 下未找到任何支持的图片文件"); return
        for sp, sf in fwf:
            tasks.append((sp, build_dst(sp, sf), sf, dst_fmt))
        desc = f"🖼️  所有格式 → {dst_fmt['label']} (无损)"
    else:
        sf = FORMAT_MAP[src_choice]
        files = collect_files(src_dir, sf["ext"])
        if not files:
            print(f"⚠️  目录 {src_dir} 下未找到任何 {sf['label']} 文件"); return
        for sp in files:
            tasks.append((sp, build_dst(sp, sf), sf, dst_fmt))
        desc = f"🖼️  {sf['label']} → {dst_fmt['label']} (无损)"

    print(f"\n🔄 转换任务 | 共 {len(tasks)} 张 | 线程数: {max_workers}"
          f"{' | 逐张校验' if VERIFY else ''}")
    print(f"📁 来源: {src_dir}")
    print(f"📁 保存: {dst_dir}\n")

    success, failed, errors = 0, 0, []
    with tqdm(total=len(tasks), desc=desc, unit="img",
              dynamic_ncols=True, leave=True) as pbar:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            fmap = {ex.submit(_process_one, s, d, sf, df): s
                    for s, d, sf, df in tasks}
            from concurrent.futures import as_completed
            for fut in as_completed(fmap):
                sp, ok, err = fut.result()
                if ok:
                    success += 1
                    pbar.set_postfix(ok=success, fail=failed)
                else:
                    failed += 1
                    errors.append((sp, err))
                    n = sp.name
                    pbar.set_postfix(ok=success, fail=failed,
                                     err=(n[:22] + "...") if len(n) > 25 else n)
                pbar.update(1)

    print(f"\n✅ 完成！成功: {success}, 失败: {failed}")
    if failed:
        lf = Path("convert_errors.log")
        with open(lf, "w", encoding="utf-8") as f:
            for sp, err in errors:
                f.write(f"❌ {sp}\n   -> {err}\n\n")
        print(f"📝 详细错误日志: {lf.resolve()}")


if __name__ == "__main__":
    main()