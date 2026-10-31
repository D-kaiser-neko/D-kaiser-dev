#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TLG 图片批量提取脚本 (KiriKiri 引擎)
支持 TLG5 / TLG6 格式 → PNG（保留透明通道）
"""

import os
import sys
import struct
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from PIL import Image
from tqdm import tqdm


# ==================== TLG5/TLG6 解码核心 ====================

def decomp_lzss(src: bytes, dst_size: int, dictionary: bytearray = None, initial_r: int = 0):
    """TLG5/TLG6 改进型 LZSS 解压（字典 4096）"""
    if dictionary is None:
        dictionary = bytearray(4096)
    r = initial_r & 0xFFF
    flags = 0
    src_pos = 0
    dst = bytearray(dst_size)
    dst_pos = 0
    src_len = len(src)

    while src_pos < src_len and dst_pos < dst_size:
        flags >>= 1
        if (flags & 0x100) == 0:
            if src_pos >= src_len:
                break
            flags = src[src_pos] | 0xFF00
            src_pos += 1

        if flags & 1:
            if src_pos + 2 > src_len:
                break
            mpos = src[src_pos] | ((src[src_pos + 1] & 0x0F) << 8)
            mlen = (src[src_pos + 1] & 0xF0) >> 4
            src_pos += 2
            mlen += 3
            if mlen == 18:
                if src_pos >= src_len:
                    break
                mlen += src[src_pos]
                src_pos += 1
            for _ in range(mlen):
                if dst_pos >= dst_size:
                    break
                c = dictionary[mpos & 0xFFF]
                dst[dst_pos] = c
                dictionary[r] = c
                r = (r + 1) & 0xFFF
                mpos = (mpos + 1) & 0xFFF
                dst_pos += 1
        else:
            if src_pos >= src_len:
                break
            c = src[src_pos]
            src_pos += 1
            dst[dst_pos] = c
            dictionary[r] = c
            r = (r + 1) & 0xFFF
            dst_pos += 1

    return bytes(dst), dictionary, r


def compose_colors(dst: bytearray, dst_off: int, upper: bytes, upper_off: int,
                   buffers: list, width: int, colors: int):
    """TLG5 颜色合成：BGRA 通道去相关 + 行预测"""
    c = [0, 0, 0, 0]
    pc = [0, 0, 0, 0]

    for x in range(width):
        for i in range(colors):
            c[i] = buffers[i][x]

        if colors >= 3:
            c[0] += c[1]
            c[2] += c[1]

        for i in range(colors):
            pc[i] += c[i]
            dst[dst_off + x * colors + i] = (pc[i] + upper[upper_off + x * colors + i]) & 0xFF


def decode_tlg5(data: bytes) -> Image.Image:
    """解码 TLG5.0 → PIL RGBA/RGB"""
    src = bytearray(data)
    pos = 0

    if src[:11] == b'TLG0.0\x00sds\x1a':
        pos += 15

    if src[pos:pos+11] != b'TLG5.0\x00raw\x1a':
        raise ValueError("不是 TLG5 格式")
    pos += 11

    colors = src[pos]; pos += 1
    width = struct.unpack('<I', bytes(src[pos:pos+4]))[0]; pos += 4
    height = struct.unpack('<I', bytes(src[pos:pos+4]))[0]; pos += 4
    block_height = struct.unpack('<I', bytes(src[pos:pos+4]))[0]; pos += 4

    if colors not in (3, 4):
        raise ValueError(f"TLG5: 不支持的通道数 {colors}")
    if width == 0 or height == 0:
        raise ValueError("TLG5: 非法图像尺寸")

    block_count = ((height - 1) // block_height) + 1
    pos += block_count * 4

    dst_size = width * height * colors
    dst = bytearray(dst_size)
    dst_ptr = 0

    dictionary = bytearray(4096)
    r = 0
    out_buffers = [bytearray(block_height * width + 10) for _ in range(colors)]
    prev_line = bytes(width * colors)

    for y_blk in range(0, height, block_height):
        y_lim = min(y_blk + block_height, height)

        for c in range(colors):
            if pos + 5 > len(src):
                raise ValueError("TLG5: 数据截断")
            comp = src[pos]; pos += 1
            size = struct.unpack('<I', bytes(src[pos:pos+4]))[0]; pos += 4

            if pos + size > len(src):
                raise ValueError("TLG5: 压缩数据越界")

            if comp == 0:
                dec, dictionary, r = decomp_lzss(bytes(src[pos:pos+size]),
                                                  block_height * width,
                                                  dictionary, r)
                out_buffers[c][:len(dec)] = dec
            else:
                out_buffers[c][:size] = src[pos:pos+size]
            pos += size

        out_ptrs = [0] * colors
        for y in range(y_blk, y_lim):
            compose_colors(dst, dst_ptr, prev_line, 0,
                          [buf[out_ptrs[i]:] for i, buf in enumerate(out_buffers)],
                          width, colors)
            prev_line = bytes(dst[dst_ptr:dst_ptr + width * colors])
            dst_ptr += width * colors
            for i in range(colors):
                out_ptrs[i] += width

    # BGRA → RGBA
    if colors == 4:
        rgba = bytearray(width * height * 4)
        for i in range(width * height):
            b, g, r, a = dst[i*4:(i+1)*4]
            rgba[i*4:(i+1)*4] = bytes([r, g, b, a])
        return Image.frombytes('RGBA', (width, height), bytes(rgba))
    else:
        rgb = bytearray(width * height * 3)
        for i in range(width * height):
            b, g, r = dst[i*3:(i+1)*3]
            rgb[i*3:(i+1)*3] = bytes([r, g, b])
        return Image.frombytes('RGB', (width, height), bytes(rgb))


# ==================== TLG6 解码表 ====================

TLG6_GOLOMB_N_COUNT = 4
TLG6_LeadingZeroTable_BITS = 12
TLG6_LeadingZeroTable_SIZE = 1 << TLG6_LeadingZeroTable_BITS

TVPTLG6LeadingZeroTable = [0] * TLG6_LeadingZeroTable_SIZE
for i in range(TLG6_LeadingZeroTable_SIZE):
    cnt = 0
    j = 1
    while j != TLG6_LeadingZeroTable_SIZE and not (i & j):
        j <<= 1
        cnt += 1
    cnt += 1
    if j == TLG6_LeadingZeroTable_SIZE:
        cnt = 0
    TVPTLG6LeadingZeroTable[i] = cnt

TVPTLG6GolombCompressed = [
    [3, 3, 4, 9, 19, 33, 35, 14, 8],
    [33, 25, 15, 9, 5, 3, 2, 2, 34],
    [2, 3, 5, 9, 15, 25, 33, 14, 22],
    [22, 14, 33, 25, 15, 9, 5, 3, 2],
]

TVPTLG6GolombBitLengthTable = [[0] * TLG6_GOLOMB_N_COUNT for _ in range(128)]
for n in range(TLG6_GOLOMB_N_COUNT):
    a = 0
    for i in range(9):
        for _ in range(TVPTLG6GolombCompressed[n][i]):
            if a < 128:
                TVPTLG6GolombBitLengthTable[a][n] = i
            a += 1


def tlg6_decode_golomb_values(pixelbuf: bytearray, pixel_count: int, bit_pool: bytes, color: int):
    n = TLG6_GOLOMB_N_COUNT - 1
    a = 0
    bit_pos = 1
    zero = 0 if (bit_pool[0] & 1) else 1
    bp = bytearray(bit_pool)
    bpos = 0
    limit = pixel_count * 4
    idx = 0

    while idx < limit:
        t = int.from_bytes(bp[bpos:bpos+4], 'little') >> bit_pos
        b = TVPTLG6LeadingZeroTable[t & (TLG6_LeadingZeroTable_SIZE - 1)]
        bit_count = b
        while not b:
            bit_count += TLG6_LeadingZeroTable_BITS
            bit_pos += TLG6_LeadingZeroTable_BITS
            bpos += bit_pos >> 3
            bit_pos &= 7
            t = int.from_bytes(bp[bpos:bpos+4], 'little') >> bit_pos
            b = TVPTLG6LeadingZeroTable[t & (TLG6_LeadingZeroTable_SIZE - 1)]
            bit_count += b

        bit_pos += b
        bpos += bit_pos >> 3
        bit_pos &= 7
        bit_count -= 1
        count = 1 << bit_count
        count += (int.from_bytes(bp[bpos:bpos+4], 'little') >> bit_pos) & (count - 1)
        bit_pos += bit_count
        bpos += bit_pos >> 3
        bit_pos &= 7

        if zero:
            for _ in range(count):
                if idx >= limit:
                    break
                if color == 0:
                    pixelbuf[idx:idx+4] = b'\x00\x00\x00\x00'
                else:
                    pixelbuf[idx + color] = 0
                idx += 4
            zero ^= 1
        else:
            for _ in range(count):
                if idx >= limit:
                    break
                t = int.from_bytes(bp[bpos:bpos+4], 'little') >> bit_pos
                if t:
                    b = TVPTLG6LeadingZeroTable[t & (TLG6_LeadingZeroTable_SIZE - 1)]
                    bit_count = b
                    while not b:
                        bit_count += TLG6_LeadingZeroTable_BITS
                        bit_pos += TLG6_LeadingZeroTable_BITS
                        bpos += bit_pos >> 3
                        bit_pos &= 7
                        t = int.from_bytes(bp[bpos:bpos+4], 'little') >> bit_pos
                        b = TVPTLG6LeadingZeroTable[t & (TLG6_LeadingZeroTable_SIZE - 1)]
                        bit_count += b
                    bit_count -= 1
                else:
                    bpos += 5
                    bit_count = bp[bpos - 1]
                    bit_pos = 0
                    t = int.from_bytes(bp[bpos:bpos+4], 'little')
                    b = 0

                k = TVPTLG6GolombBitLengthTable[a][n] if a < 128 else 0
                v = (bit_count << k) + ((t >> b) & ((1 << k) - 1))
                sign = (v & 1) - 1
                v >>= 1
                a += v
                val = ((v ^ sign) + sign + 1) & 0xFF

                if color == 0:
                    struct.pack_into('<I', pixelbuf, idx, val)
                else:
                    pixelbuf[idx + color] = val

                idx += 4
                bit_pos += b
                bit_pos += k
                bpos += bit_pos >> 3
                bit_pos &= 7

                n -= 1
                if n < 0:
                    a >>= 1
                    n = TLG6_GOLOMB_N_COUNT - 1
            zero ^= 1


def tlg6_med2(a: int, b: int, c: int) -> int:
    aa_gt_bb = ((a & ~b) + (((a ^ ~b) >> 1) & 0x7f7f7f7f)) & 0x80808080
    aa_gt_bb = ((aa_gt_bb >> 7) + 0x7f7f7f7f) ^ 0x7f7f7f7f
    a_xor_b_and = ((a ^ b) & aa_gt_bb)
    aa = a_xor_b_and ^ a
    bb = a_xor_b_and ^ b
    n = (((c & ~bb) + (((c ^ ~bb) >> 1) & 0x7f7f7f7f)) & 0x80808080)
    n = ((n >> 7) + 0x7f7f7f7f) ^ 0x7f7f7f7f
    nn = (((aa & ~c) + (((aa ^ ~c) >> 1) & 0x7f7f7f7f)) & 0x80808080)
    nn = ((nn >> 7) + 0x7f7f7f7f) ^ 0x7f7f7f7f
    m = ~(n | nn)
    return (n & aa) | (nn & bb) | ((bb & m) - (c & m) + (aa & m))


def tlg6_packed_add(a: int, b: int) -> int:
    tmp = (((a & b) << 1) + ((a ^ b) & 0xfefefefe)) & 0x01010100
    return (a + b - tmp) & 0xFFFFFFFF


def tlg6_med(a: int, b: int, c: int, v: int) -> int:
    return tlg6_packed_add(tlg6_med2(a, b, c), v)


def tlg6_avg(a: int, b: int, c: int, v: int) -> int:
    avg = ((a & b) + (((a ^ b) & 0xfefefefe) >> 1) + ((a ^ b) & 0x01010101))
    return tlg6_packed_add(avg & 0xFFFFFFFF, v)


def tlg6_decode_line(prev_line: bytearray, current_line: bytearray, width: int,
                     start_block: int, block_limit: int, filter_types: bytes,
                     skip_block_bytes: int, in_buf: bytearray, initial_p: int,
                     odd_skip: int, dir_val: int, colors: int):
    W_BLOCK = 8

    if start_block:
        prev_off = start_block * W_BLOCK
        cur_off = start_block * W_BLOCK
        p = int.from_bytes(current_line[cur_off*4-4:cur_off*4], 'little') if cur_off > 0 else initial_p
        up = int.from_bytes(prev_line[prev_off*4-4:prev_off*4], 'little') if prev_off > 0 else initial_p
    else:
        prev_off = 0
        cur_off = 0
        p = up = initial_p

    in_off = skip_block_bytes * start_block
    step = 1 if (dir_val & 1) else -1

    for i in range(start_block, block_limit):
        w = width - i * W_BLOCK
        if w > W_BLOCK:
            w = W_BLOCK
        ww = w

        if step == -1:
            in_off += ww - 1
        if i & 1:
            in_off += odd_skip * ww

        ft = filter_types[i] if i < len(filter_types) else 0

        for _ in range(w):
            if in_off * 4 + 4 > len(in_buf):
                break
            pix = int.from_bytes(in_buf[in_off*4:in_off*4+4], 'little')

            a = (pix >> 24) & 0xFF
            r = (pix >> 16) & 0xFF
            g = (pix >> 8) & 0xFF
            b = pix & 0xFF

            filters = [
                (b, g, r), (b+g, g, r+g), (b, g+b, r+b+g),
                (b+r+g, g+r, r), (b+r, g+b+r, r+b+r+g),
                (b+r, g+b+r, r), (b+g, g, r), (b, g+b, r),
                (b, g, r+g), (b+g+r+b, g+r+b, r+b),
                (b+r, g+r, r), (b, g+b, r+b),
                (b, g+r+b, r+b), (b+g, g+r+b+g, r+b+g),
                (b+g+r, g+r, r+b+g+r), (b, g+(b<<1), r+(b<<1))
            ]

            if ft < len(filters):
                fb, fg, fr = filters[ft]
            else:
                fb, fg, fr = b, g, r

            if colors == 3:
                pix_val = (0xff000000 | (fr << 16) | (fg << 8) | fb)
            else:
                pix_val = ((a << 24) | (fr << 16) | (fg << 8) | fb)

            if ft & 1:
                p = tlg6_avg(p, up, up, pix_val)
            else:
                p = tlg6_med(p, up, up, pix_val)

            up = int.from_bytes(prev_line[prev_off*4:prev_off*4+4], 'little') if prev_off + 4 <= len(prev_line) else 0
            struct.pack_into('<I', current_line, cur_off*4, p)

            prev_off += 1
            cur_off += 1
            if step == 1:
                in_off += 1
            else:
                in_off -= 1

        if step == 1:
            in_off += skip_block_bytes - ww
        else:
            in_off += skip_block_bytes + 1
        if i & 1:
            in_off -= odd_skip * ww


def decode_tlg6(data: bytes) -> Image.Image:
    src = bytearray(data)
    pos = 0

    if src[:11] == b'TLG0.0\x00sds\x1a':
        pos += 15

    if src[pos:pos+11] != b'TLG6.0\x00raw\x1a':
        raise ValueError("不是 TLG6 格式")
    pos += 11

    colors = src[pos]; pos += 1
    _ = src[pos]; pos += 1  # data_flag
    _ = src[pos]; pos += 1  # color_type
    _ = src[pos]; pos += 1  # external_golomb

    width = struct.unpack('<I', bytes(src[pos:pos+4]))[0]; pos += 4
    height = struct.unpack('<I', bytes(src[pos:pos+4]))[0]; pos += 4
    max_bit_length = struct.unpack('<I', bytes(src[pos:pos+4]))[0]; pos += 4

    if colors not in (1, 3, 4):
        raise ValueError(f"TLG6: 不支持的通道数 {colors}")

    H_BLOCK = 8
    W_BLOCK = 8
    x_block_count = (width - 1) // W_BLOCK + 1
    y_block_count = (height - 1) // H_BLOCK + 1
    main_count = width // W_BLOCK
    fraction = width - main_count * W_BLOCK

    dst_size = width * height * 4
    dst = bytearray(dst_size)

    bit_pool = bytearray(max_bit_length // 8 + 5)
    pixel_buffer = bytearray(4 * width * H_BLOCK + 1)
    filter_types = bytearray(x_block_count * y_block_count)
    zero_line = bytearray(width * 4)
    if colors == 3:
        for i in range(width):
            struct.pack_into('<I', zero_line, i*4, 0xff000000)

    lzss_dic = bytearray(4096)
    p = 0
    for i in range(0, 0x01010101 << 5, 0x01010101):
        for j in range(0, 0x01010101 << 4, 0x01010101):
            struct.pack_into('<I', lzss_dic, p, i)
            struct.pack_into('<I', lzss_dic, p+4, j)
            p += 8

    ft_size = struct.unpack('<I', bytes(src[pos:pos+4]))[0]; pos += 4
    ft_dec, _, _ = decomp_lzss(bytes(src[pos:pos+ft_size]), len(filter_types),
                                bytearray(lzss_dic), 0)
    filter_types[:len(ft_dec)] = ft_dec
    pos += ft_size

    pdst = 0
    prev_line = zero_line

    for y in range(0, height, H_BLOCK):
        ylim = min(y + H_BLOCK, height)
        pixel_count = (ylim - y) * width

        for c in range(colors):
            bit_length = struct.unpack('<I', bytes(src[pos:pos+4]))[0]; pos += 4
            method = (bit_length >> 30) & 3
            bit_length &= 0x3fffffff

            byte_length = bit_length // 8
            if bit_length % 8:
                byte_length += 1

            bit_pool[:byte_length] = src[pos:pos+byte_length]
            pos += byte_length

            if method == 0:
                tlg6_decode_golomb_values(pixel_buffer, pixel_count, bytes(bit_pool[:byte_length]), c)
            else:
                raise ValueError(f"TLG6: 不支持的编码方法 {method}")

        ft_off = (y // H_BLOCK) * x_block_count
        skip_bytes = (ylim - y) * W_BLOCK

        for yy in range(y, ylim):
            current_line = bytearray(width * 4)
            dir_val = (yy & 1) ^ 1
            odd_skip = (ylim - yy - 1) - (yy - y)

            if main_count > 0:
                start = (min(width, W_BLOCK) * (yy - y))
                tlg6_decode_line(prev_line, current_line, width, 0, main_count,
                                filter_types, skip_bytes, pixel_buffer[start:],
                                0xff000000 if colors == 3 else 0, odd_skip, dir_val, colors)

            if main_count != x_block_count:
                ww = min(fraction, W_BLOCK)
                start = ww * (yy - y)
                tlg6_decode_line(prev_line, current_line, width, main_count, x_block_count,
                                filter_types, skip_bytes, pixel_buffer[start:],
                                0xff000000 if colors == 3 else 0, odd_skip, dir_val, colors)

            dst[pdst:pdst+width*4] = current_line
            prev_line = current_line
            pdst += width * 4

    rgba = bytearray(width * height * 4)
    for i in range(width * height):
        b, g, r, a = dst[i*4:(i+1)*4]
        rgba[i*4:(i+1)*4] = bytes([r, g, b, a])
    return Image.frombytes('RGBA', (width, height), bytes(rgba))


# ==================== 统一入口 ====================

def decode_tlg(data: bytes) -> Image.Image:
    if data[:11] == b'TLG0.0\x00sds\x1a':
        sig = data[15:26]
    else:
        sig = data[:11]

    if sig == b'TLG5.0\x00raw\x1a':
        return decode_tlg5(data)
    elif sig == b'TLG6.0\x00raw\x1a':
        return decode_tlg6(data)
    else:
        raise ValueError("不支持的 TLG 格式或文件已损坏")


# ==================== 多进程处理 ====================

def process_file(args: tuple) -> dict:
    src_path, dst_path = args
    result = {'src': str(src_path), 'dst': str(dst_path), 'ok': False, 'error': ''}

    try:
        with open(src_path, 'rb') as f:
            data = f.read()

        img = decode_tlg(data)
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)

        # ✅ 修正：检查 alpha 最小值是否为 255（全部不透明才转 RGB）
        if img.mode == 'RGBA':
            alpha = img.split()[-1]
            if alpha.getextrema()[0] == 255:  # min == 255 → 全部不透明
                img = img.convert('RGB')

        img.save(dst_path, 'PNG')
        result['ok'] = True
        os.remove(src_path)

    except Exception as e:
        result['error'] = str(e)

    return result


def scan_tlg_files(root_dir: str) -> list:
    root = Path(root_dir)
    files = []
    for path in root.rglob('*.tlg'):
        if path.is_file():
            dst = path.with_suffix('.png')
            files.append((str(path), str(dst)))
    return files


def main():
    TARGET_DIR = '/storage/emulated/0/termux/'
    MAX_WORKERS = 8

    if not os.path.isdir(TARGET_DIR):
        print(f"错误: 目录不存在 {TARGET_DIR}")
        sys.exit(1)

    print(f"[*] 扫描目录: {TARGET_DIR}")
    tasks = scan_tlg_files(TARGET_DIR)
    total = len(tasks)

    if total == 0:
        print("[*] 未找到任何 .tlg 文件")
        sys.exit(0)

    print(f"[*] 发现 {total} 个 TLG 文件，启动 {MAX_WORKERS} 核并行解码...")

    success = 0
    failed = 0

    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_file, task): task for task in tasks}
        pbar = tqdm(as_completed(futures), total=total, desc="解码进度", unit="file")

        for future in pbar:
            result = future.result()
            if result['ok']:
                success += 1
            else:
                failed += 1
                # tqdm.write(f"[FAIL] {result['src']}: {result['error']}")
            pbar.set_postfix_str(f"OK:{success} FAIL:{failed}")

    print(f"\n[+] 完成! 成功: {success}, 失败: {failed}")


if __name__ == '__main__':
    multiprocessing.set_start_method('spawn', force=True)
    main()
