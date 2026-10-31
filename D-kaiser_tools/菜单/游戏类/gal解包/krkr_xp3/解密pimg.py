import os
import struct
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm

# 固定的工作根目录
ROOT_DIR = "/storage/emulated/0/termux"

def process_one_pimg(pimg_path):
    """
    处理单个 .pimg 文件：
    - 提取所有 RIFF (WebP) 块
    - 保存到同目录下，命名为 原文件名_编号.webp
    - 若成功提取至少一张图像，删除原 .pimg 文件
    返回提取的图像数量
    """
    with open(pimg_path, 'rb') as f:
        data = f.read()

    dirname = os.path.dirname(pimg_path)
    base = os.path.splitext(os.path.basename(pimg_path))[0]
    idx = 1
    pos = 0
    extracted = 0

    while True:
        pos = data.find(b'RIFF', pos)
        if pos == -1:
            break
        size = struct.unpack('<I', data[pos+4:pos+8])[0]
        chunk = data[pos:pos+size+8]
        out_name = f"{base}_{idx:02d}.webp"
        out_path = os.path.join(dirname, out_name)
        # 避免重名（若文件已存在则递增编号）
        while os.path.exists(out_path):
            idx += 1
            out_name = f"{base}_{idx:02d}.webp"
            out_path = os.path.join(dirname, out_name)
        with open(out_path, 'wb') as out:
            out.write(chunk)
        extracted += 1
        idx += 1
        pos += size + 8

    # 仅当成功提取了至少一个 WebP 时才删除原文件
    if extracted > 0:
        os.remove(pimg_path)

    return extracted


def find_pimg_files(root_dir):
    """查找指定目录及一级子目录下的所有 .pimg 文件（不区分大小写）"""
    root = Path(root_dir)
    if not root.exists():
        print(f"目录不存在: {root_dir}")
        return []
    files = []
    files.extend(root.glob("*.pimg"))
    files.extend(root.glob("*.PIMG"))
    for sub in root.iterdir():
        if sub.is_dir():
            files.extend(sub.glob("*.pimg"))
            files.extend(sub.glob("*.PIMG"))
    # 去重并返回字符串路径
    return list({str(p) for p in files})


def main():
    # 检查根目录是否存在
    if not os.path.isdir(ROOT_DIR):
        print(f"错误：根目录不存在或不可访问 -> {ROOT_DIR}")
        return

    pimg_files = find_pimg_files(ROOT_DIR)
    if not pimg_files:
        print(f"在 {ROOT_DIR} 及其子目录中未找到任何 .pimg 文件")
        return

    print(f"在 {ROOT_DIR} 中找到 {len(pimg_files)} 个 .pimg 文件，开始提取（8核并行）...")
    total_images = 0

    # 使用进程池并行处理（最多 8 个进程）
    with ProcessPoolExecutor(max_workers=8) as executor:
        # 提交所有任务
        futures = {executor.submit(process_one_pimg, f): f for f in pimg_files}

        # 动态进度条
        with tqdm(total=len(pimg_files), desc="处理进度", unit="file") as pbar:
            for future in as_completed(futures):
                file_path = futures[future]
                try:
                    count = future.result()
                    total_images += count
                except Exception as e:
                    print(f"处理 {file_path} 时出错: {e}")
                pbar.update(1)

    print(f"\n全部完成！共提取 {total_images} 张图像。")
    print("（每个文件提取成功后会删除原始 .pimg 文件）")


if __name__ == "__main__":
    main()