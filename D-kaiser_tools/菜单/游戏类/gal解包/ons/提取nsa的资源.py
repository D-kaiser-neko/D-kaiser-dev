import os
import re
import struct
import sys
import glob

# 固定的工作根目录
ROOT_DIR = "/storage/emulated/0/termux"

# 尝试导入PIL用于验证
try:
    from PIL import Image
    import io
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("提示: 未安装Pillow，将使用基础验证，可能不够准确。")


def resolve_path(path: str) -> str:
    """如果路径是相对路径，则相对于 ROOT_DIR 返回绝对路径；否则直接返回"""
    if os.path.isabs(path):
        return path
    return os.path.join(ROOT_DIR, path)


# -------------------- 文件名清理函数 --------------------
def sanitize_filename(name):
    name = re.sub(r'[\\/*?:"<>|]', '_', name)
    name = ''.join(c if ord(c) >= 32 else '_' for c in name)
    name = name.strip('. ')
    if not name:
        return "unnamed"
    return name


# -------------------- PNG 提取（每个文件后加处理进度） --------------------
def extract_pngs(input_file, output_dir='output_png', file_prefix=''):
    os.makedirs(output_dir, exist_ok=True)

    png_signature = b'\x89PNG\r\n\x1a\n'

    with open(input_file, 'rb') as f:
        data = f.read()

    positions = []
    pos = 0
    while True:
        pos = data.find(png_signature, pos)
        if pos == -1:
            break
        positions.append(pos)
        pos += 1

    if not positions:
        print(f"{input_file}: 未找到任何PNG文件头。")
        return

    total = len(positions)
    print(f"{input_file}: 找到 {total} 个可能的PNG图像。")

    for idx, start in enumerate(positions):
        current = start + 8
        end = None
        while current < len(data):
            if current + 4 > len(data):
                break
            length = int.from_bytes(data[current:current+4], byteorder='big')
            if current + 8 > len(data):
                break
            chunk_type = data[current+4:current+8]

            if chunk_type == b'IEND':
                end = current + 12
                break

            current += 12 + length
        else:
            print(f"{input_file}: 警告: 无法找到第 {idx+1} 个PNG的结束位置，跳过。")
            continue

        png_data = data[start:end]

        if file_prefix:
            out_filename = f"{file_prefix}_image_{idx+1:03d}.png"
        else:
            out_filename = f"image_{idx+1:03d}.png"

        output_path = os.path.join(output_dir, out_filename)
        with open(output_path, 'wb') as out_f:
            out_f.write(png_data)

        percent = idx * 100 // total
        print(f"已保存: {output_path}处理进度: {idx}/{total} [{percent}%]...")


# -------------------- OGG 提取（每个文件后加处理进度） --------------------
def extract_oggs(input_file, output_dir='output_ogg', file_prefix=''):
    os.makedirs(output_dir, exist_ok=True)

    with open(input_file, 'rb') as f:
        data = f.read()
    d = data
    data_len = len(d)

    ogg_marker = b'OggS'
    positions = []
    pos = 0
    while True:
        pos = d.find(ogg_marker, pos)
        if pos == -1:
            break
        positions.append(pos)
        pos += 4

    total = len(positions)
    print(f"{input_file}: 找到 {total} 个可能的OGG起始位置")

    saved_count = 0
    processed_starts = set()
    log_path = os.path.join(output_dir, f"{file_prefix}_ogg_log.txt")
    with open(log_path, 'w') as log:
        for idx, start in enumerate(positions):
            if start in processed_starts:
                continue

            if start + 27 > data_len:
                continue
            if d[start:start+4] != ogg_marker:
                continue
            version = d[start+4]
            if version != 0:
                continue
            segments = d[start+26]
            header_end = start + 27 + segments
            if header_end > data_len:
                continue

            stream_serial = int.from_bytes(d[start+14:start+18], 'little')
            seg_table = d[start+27:start+27+segments]
            page_size = 27 + segments + sum(seg_table)

            end = start + page_size
            current_pos = end

            max_search = start + 10 * 1024 * 1024
            if max_search > data_len:
                max_search = data_len

            try:
                start_idx = positions.index(start)
            except ValueError:
                continue

            next_idx = start_idx + 1
            while next_idx < total and positions[next_idx] < max_search:
                next_pos = positions[next_idx]
                if next_pos < current_pos:
                    next_idx += 1
                    continue
                if next_pos > max_search:
                    break
                if next_pos + 27 > data_len:
                    break
                if d[next_pos:next_pos+4] != ogg_marker:
                    break
                next_segments = d[next_pos+26]
                if next_pos + 27 + next_segments > data_len:
                    break
                next_serial = int.from_bytes(d[next_pos+14:next_pos+18], 'little')
                if next_serial != stream_serial:
                    break
                header_type = d[next_pos+5]
                next_seg_table = d[next_pos+27:next_pos+27+next_segments]
                next_page_size = 27 + next_segments + sum(next_seg_table)
                end = next_pos + next_page_size
                current_pos = end
                if header_type & 0x04:
                    break
                next_idx += 1

            if end > start:
                ogg_data = d[start:end]

                if len(ogg_data) < 100 or not ogg_data.startswith(ogg_marker):
                    print(f"  警告: 第 {saved_count+1} 个OGG数据太短或头部错误，跳过。")
                    continue

                if file_prefix:
                    out_filename = f"{file_prefix}_audio_{saved_count+1:03d}.ogg"
                else:
                    out_filename = f"audio_{saved_count+1:03d}.ogg"

                out_path = os.path.join(output_dir, out_filename)
                with open(out_path, 'wb') as out_f:
                    out_f.write(ogg_data)

                percent = idx * 100 // total
                print(f"已保存: {out_path}处理进度: {idx}/{total} [{percent}%]...")
                saved_count += 1
                log.write(f"{out_filename}\tstart={start}\tend={end}\tsize={len(ogg_data)}\n")

                pos2 = start
                while pos2 < end:
                    if pos2 in positions:
                        processed_starts.add(pos2)
                    next_ogg = d.find(ogg_marker, pos2 + 1)
                    if next_ogg == -1 or next_ogg >= end:
                        break
                    pos2 = next_ogg

    print(f"{input_file}: 提取完成，共保存 {saved_count} 个OGG文件。")


# -------------------- 增强版 JPEG 提取（每个文件后加处理进度） --------------------
def extract_jpegs(input_file, output_dir='output_jpg', file_prefix=''):
    os.makedirs(output_dir, exist_ok=True)

    with open(input_file, 'rb') as f:
        data = f.read()

    start_marker = b'\xff\xd8\xff'
    end_marker = b'\xff\xd9'

    start_positions = []
    pos = 0
    while True:
        pos = data.find(start_marker, pos)
        if pos == -1:
            break
        start_positions.append(pos)
        pos += 3

    total = len(start_positions)
    print(f"{input_file}: 找到 {total} 个可能的 JPEG 起始位置。")

    saved_count = 0
    log_path = os.path.join(output_dir, f"{file_prefix}_jpg_log.txt")
    with open(log_path, 'w') as log:
        for idx, start in enumerate(start_positions):
            max_search = start + 10 * 1024 * 1024
            if max_search > len(data):
                max_search = len(data)

            search_pos = start + 2
            end = -1
            attempt = 0
            max_attempts = 100

            while attempt < max_attempts and search_pos < max_search:
                end = data.find(end_marker, search_pos, max_search)
                if end == -1:
                    break

                next_pos = end + 2
                if next_pos + 3 <= max_search and data[next_pos:next_pos+3] == start_marker:
                    break
                search_pos = end + 2
                attempt += 1
            else:
                print(f"{input_file}: 警告: 第 {idx+1} 个 JPEG 无法找到合理的结束标志，跳过。")
                continue

            if end == -1:
                continue

            jpeg_data = data[start:end+2]

            if HAS_PIL:
                try:
                    with Image.open(io.BytesIO(jpeg_data)) as img:
                        img.verify()
                except Exception as e:
                    print(f"  第 {idx+1} 个 JPEG 验证失败，跳过。错误: {e}")
                    continue

            if file_prefix:
                out_filename = f"{file_prefix}_image_{saved_count+1:03d}.jpg"
            else:
                out_filename = f"image_{saved_count+1:03d}.jpg"

            out_path = os.path.join(output_dir, out_filename)
            with open(out_path, 'wb') as out_f:
                out_f.write(jpeg_data)

            percent = idx * 100 // total
            print(f"已保存: {out_path}处理进度: {idx}/{total} [{percent}%]...")
            saved_count += 1
            log.write(f"{out_filename}\tstart={start}\tend={end}\tsize={len(jpeg_data)}\n")

    print(f"{file_prefix}: 提取完成，共保存 {saved_count} 张图片。")


# -------------------- 主程序 --------------------
if __name__ == '__main__':
    # 检查根目录是否存在
    if not os.path.isdir(ROOT_DIR):
        print(f"错误：工作根目录不存在或无法访问 -> {ROOT_DIR}")
        sys.exit(1)

    if len(sys.argv) > 1:
        # 用户通过命令行指定的文件，将它们解析到根目录下
        file_list = [resolve_path(f) for f in sys.argv[1:]]
        print(f"将处理指定的文件: {file_list}")
    else:
        # 在根目录下搜索 arc*.nsa
        search_pattern = os.path.join(ROOT_DIR, 'arc*.nsa')
        file_list = sorted(glob.glob(search_pattern))
        if not file_list:
            print(f"在 {ROOT_DIR} 下未找到任何 arc*.nsa 文件，请确保文件存在或指定文件名。")
            sys.exit(1)
        print(f"自动匹配到文件: {file_list}")

    print("请选择要提取的内容：")
    print("0 = 全部 (jpg + png + ogg)")
    print("1 = 仅 jpg")
    print("2 = 仅 png")
    print("3 = 仅 ogg")
    choice = input("请输入数字 (0/1/2/3): ").strip()

    for file_name in file_list:
        if not os.path.exists(file_name):
            print(f"文件不存在，跳过: {file_name}")
            continue

        base = os.path.splitext(os.path.basename(file_name))[0]
        print(f"\n====== 处理文件: {file_name} ======")

        # 输出目录也放到根目录下
        if choice == '0' or choice == '1':
            extract_jpegs(file_name, output_dir=os.path.join(ROOT_DIR, 'output_jpg'), file_prefix=base)
        if choice == '0' or choice == '2':
            extract_pngs(file_name, output_dir=os.path.join(ROOT_DIR, 'output_png'), file_prefix=base)
        if choice == '0' or choice == '3':
            extract_oggs(file_name, output_dir=os.path.join(ROOT_DIR, 'output_ogg'), file_prefix=base)

    print("\n所有文件处理完毕。")