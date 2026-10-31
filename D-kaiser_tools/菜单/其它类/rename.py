import os
from pathlib import Path

# 固定的工作根目录
BASE_DIR = "/storage/emulated/0/termux"

def index_to_5letter(idx):
    """
    将数字索引转换为5位字母组合 (a=0, b=1 ... z=25)
    0 -> aaaaa, 1 -> aaaab, 2 -> aaaac ...
    """
    chars = []
    for _ in range(5):
        chars.append(chr(ord('a') + idx % 26))
        idx //= 26
    return ''.join(reversed(chars))

def is_digit_filename(filename):
    """检查文件名是否为 '纯数字.后缀' 格式"""
    p = Path(filename)
    return p.stem.isdigit() and p.suffix != ''

def process_directory(base_dir, dry_run=True):
    """遍历目录及子目录，查找并重命名文件"""
    dir_files = {}

    for root, dirs, files in os.walk(base_dir):
        matched = []
        for f in files:
            if is_digit_filename(f):
                matched.append(Path(root) / f)
        if matched:
            # 按文件名中的数字排序
            matched.sort(key=lambda p: int(p.stem))
            dir_files[Path(root)] = matched

    if not dir_files:
        print("🔍 未找到任何符合 '数字.后缀' 格式的文件。")
        return 0

    total = 0
    action_word = "【预览】" if dry_run else "【执行】"

    for folder in sorted(dir_files.keys()):
        file_list = dir_files[folder]

        try:
            rel_path = folder.relative_to(base_dir)
        except ValueError:
            rel_path = folder

        print(f"\n📁 {action_word} 目录: {rel_path}")
        print("-" * 50)

        for idx, fpath in enumerate(file_list):
            old_name = fpath.name
            ext = fpath.suffix
            new_name = f"{index_to_5letter(idx)}{ext}"

            total += 1

            if dry_run:
                print(f"  🔄 {old_name:>15}  →  {new_name}")
            else:
                new_path = fpath.parent / new_name
                try:
                    fpath.rename(new_path)
                    print(f"  ✅ {old_name:>15}  →  {new_name}")
                except Exception as e:
                    print(f"  ❌ {old_name}: {e}")

    return total

def main():
    base_dir = BASE_DIR

    print("=" * 55)
    print("🚀 批量文件重命名工具")
    print("   规则: 0→aaaaa, 1→aaaab, 2→aaaac ...")
    print("=" * 55)
    print(f"📂 目标目录:\n   {base_dir}")
    print("-" * 55)

    # 检查目标目录是否存在
    if not os.path.isdir(base_dir):
        print(f"❌ 错误：目标目录不存在或无法访问 -> {base_dir}")
        input("\n按回车键退出...")
        return

    print("🔎 正在扫描并生成预览...\n")
    total = process_directory(base_dir, dry_run=True)

    if total == 0:
        print("\n✅ 没有需要重命名的文件。")
        input("\n按回车键退出...")
        return

    print(f"\n{'=' * 55}")
    print(f"📊 共扫描到 {total} 个需要重命名的文件")

    choice = input("\n⚠️  确认执行重命名？此操作不可撤销！(y/n) [y]: ").strip().lower()

    if choice in ('', 'y', 'yes'):
        print("\n⏳ 正在执行重命名...\n")
        process_directory(base_dir, dry_run=False)
        print(f"\n🎉 重命名完成！共处理 {total} 个文件。")
    else:
        print("\n❌ 已取消操作，文件未做任何修改。")

    input("\n按回车键退出...")

if __name__ == "__main__":
    main()