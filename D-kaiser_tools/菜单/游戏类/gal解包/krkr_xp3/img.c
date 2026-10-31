/*
 * 统一图片提取器 (C语言版)
 * 功能1: TLG5/TLG6 真格式解码 -> PNG
 * 功能2: 伪 TLG 文件 RIFF WebP 提取
 * 功能3: .pimg 文件 RIFF WebP 提取
 * Termux 编译: gcc img.c -o img -O2 -lpng -lz -lpthread
 */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <dirent.h>
#include <sys/stat.h>
#include <pthread.h>
#include <unistd.h>
#include <ctype.h>
#include <png.h>

/* ========== 配置 ========== */
#define ROOT_DIR "/storage/emulated/0/termux/"
#define MAX_PATH_LEN 4096
#define DEFAULT_WORKERS 8

/* ========== 全局参数 ========== */
static uint8_t g_xor_key = 0;
static int     g_keep    = 0;
static int     g_workers = DEFAULT_WORKERS;

/* ========== TLG6 常量 ========== */
#define TVP_TLG6_H_BLOCK_SIZE 8
#define TVP_TLG6_W_BLOCK_SIZE 8
#define TVP_TLG6_GOLOMB_N_COUNT  4
#define TVP_TLG6_LeadingZeroTable_BITS 12
#define TVP_TLG6_LeadingZeroTable_SIZE  (1 << TVP_TLG6_LeadingZeroTable_BITS)

/* ========== TLG6 全局表 ========== */
static uint8_t  TVPTLG6LeadingZeroTable[TVP_TLG6_LeadingZeroTable_SIZE];
static int8_t   TVPTLG6GolombBitLengthTable[128][TVP_TLG6_GOLOMB_N_COUNT];
static const int16_t TVPTLG6GolombCompressed[TVP_TLG6_GOLOMB_N_COUNT][9] = {
    {3, 7, 15, 27, 63, 108, 223, 448, 130},
    {3, 5, 13, 24, 51, 95, 192, 384, 257},
    {2, 5, 12, 21, 39, 86, 155, 320, 384},
    {2, 3, 9, 18, 33, 61, 129, 258, 511}
};
static int tlg6_tables_initialized = 0;

/* ========== 辅助函数 ========== */
static uint32_t read_u32_le(const uint8_t *p) {
    return p[0] | (p[1] << 8) | (p[2] << 16) | (p[3] << 24);
}

static void init_tlg6_tables(void) {
    if (tlg6_tables_initialized) return;
    size_t i, j;
    for (i = 0; i < TVP_TLG6_LeadingZeroTable_SIZE; i++) {
        size_t cnt = 0;
        size_t k = 1;
        while (k != TVP_TLG6_LeadingZeroTable_SIZE && !(i & k)) {
            k <<= 1;
            cnt++;
        }
        cnt++;
        if (k == TVP_TLG6_LeadingZeroTable_SIZE) cnt = 0;
        TVPTLG6LeadingZeroTable[i] = (uint8_t)cnt;
    }
    memset(TVPTLG6GolombBitLengthTable, 0, sizeof(TVPTLG6GolombBitLengthTable));
    for (int n = 0; n < TVP_TLG6_GOLOMB_N_COUNT; n++) {
        size_t a = 0;
        for (i = 0; i < 9; i++) {
            for (j = 0; j < (size_t)TVPTLG6GolombCompressed[n][i]; j++) {
                if (a < 128)
                    TVPTLG6GolombBitLengthTable[a][n] = (int8_t)i;
                a++;
            }
        }
    }
    tlg6_tables_initialized = 1;
}

/* ========== LZSS 解压 ========== */
static uint32_t decomp_lzss(uint8_t *dst, const uint8_t *src, size_t src_size,
                            uint8_t *dictionary, uint32_t initial_r) {
    uint32_t r = initial_r & 0xFFF;
    uint32_t flags = 0;
    const uint8_t *src_end = src + src_size;
    while (src < src_end) {
        flags >>= 1;
        if ((flags & 0x100) == 0) {
            if (src >= src_end) break;
            flags = (*src++) | 0xFF00;
        }
        if (flags & 1) {
            if (src + 2 > src_end) break;
            uint32_t mpos = src[0] | ((src[1] & 0x0F) << 8);
            uint32_t mlen = (src[1] & 0xF0) >> 4;
            src += 2;
            mlen += 3;
            if (mlen == 18) {
                if (src >= src_end) break;
                mlen += *src++;
            }
            while (mlen--) {
                uint8_t c = dictionary[mpos & 0xFFF];
                *dst++ = c;
                dictionary[r] = c;
                r = (r + 1) & 0xFFF;
                mpos = (mpos + 1) & 0xFFF;
            }
        } else {
            if (src >= src_end) break;
            uint8_t c = *src++;
            *dst++ = c;
            dictionary[r] = c;
            r = (r + 1) & 0xFFF;
        }
    }
    return r;
}

/* ========== TLG5 颜色合成 ========== */
static void compose_colors(uint8_t *dst, const uint8_t *upper,
                           const uint8_t **buffers, uint32_t width, uint32_t colors) {
    uint32_t x, i;
    int c[4] = {0,0,0,0};
    int pc[4] = {0,0,0,0};
    for (x = 0; x < width; x++) {
        for (i = 0; i < colors; i++) c[i] = buffers[i][x];
        if (colors >= 3) {
            c[0] += c[1];
            c[2] += c[1];
        }
        for (i = 0; i < colors; i++) {
            pc[i] += c[i];
            dst[x * colors + i] = (pc[i] + upper[x * colors + i]) & 0xFF;
        }
    }
}

/* ========== TLG5 解码 ========== */
static int decode_tlg5(const uint8_t *src, size_t src_len, uint8_t **out_rgba,
                       int *out_w, int *out_h) {
    size_t pos = 0;
    if (src_len >= 11 && memcmp(src, "TLG0.0\x00sds\x1a", 11) == 0)
        pos += 15;
    if (pos + 15 > src_len || memcmp(src + pos, "TLG5.0\x00raw\x1a", 11) != 0)
        return -1;
    pos += 11;

    uint8_t colors = src[pos++];
    uint32_t width  = read_u32_le(src + pos); pos += 4;
    uint32_t height = read_u32_le(src + pos); pos += 4;
    uint32_t block_height = read_u32_le(src + pos); pos += 4;

    if (colors != 3 && colors != 4) return -1;
    if (width == 0 || height == 0) return -1;

    uint32_t block_count = ((height - 1) / block_height) + 1;
    if (pos + block_count * 4 > src_len) return -1;
    pos += block_count * 4;

    uint32_t dst_size = width * height * colors;
    uint8_t *dst = (uint8_t *)malloc(dst_size);
    if (!dst) return -1;
    memset(dst, 0, dst_size);

    uint8_t dictionary[4096];
    memset(dictionary, 0, sizeof(dictionary));
    uint32_t r = 0;

    uint8_t *out_buffers[4];
    uint32_t buf_size = block_height * width + 10;
    for (int i = 0; i < 4; i++) {
        out_buffers[i] = (uint8_t *)malloc(buf_size);
        if (!out_buffers[i]) return -1;
        memset(out_buffers[i], 0, buf_size);
    }

    const uint8_t *prev_line = dst;
    uint8_t *dst_ptr = dst;

    for (uint32_t y_blk = 0; y_blk < height; y_blk += block_height) {
        for (uint32_t c = 0; c < colors; c++) {
            if (pos + 5 > src_len) { free(dst); return -1; }
            uint8_t comp = src[pos++];
            uint32_t size = read_u32_le(src + pos); pos += 4;
            if (pos + size > src_len) { free(dst); return -1; }
            if (comp == 0) {
                r = decomp_lzss(out_buffers[c], src + pos, size, dictionary, r);
            } else {
                memcpy(out_buffers[c], src + pos, size < buf_size ? size : buf_size);
            }
            pos += size;
        }
        uint32_t y_lim = y_blk + block_height;
        if (y_lim > height) y_lim = height;
        const uint8_t *buf_ptrs[4];
        for (int c = 0; c < 4; c++) buf_ptrs[c] = out_buffers[c];
        for (uint32_t y = y_blk; y < y_lim; y++) {
            compose_colors(dst_ptr, prev_line, buf_ptrs, width, colors);
            prev_line = dst_ptr;
            dst_ptr += width * colors;
            for (int i = 0; i < colors; i++) buf_ptrs[i] += width;
        }
    }
    for (int i = 0; i < 4; i++) free(out_buffers[i]);

    uint8_t *rgba = (uint8_t *)malloc(width * height * 4);
    if (!rgba) { free(dst); return -1; }
    if (colors == 4) {
        for (uint32_t i = 0; i < width * height; i++) {
            uint8_t b = dst[i*4+0], g = dst[i*4+1], r_ = dst[i*4+2], a = dst[i*4+3];
            rgba[i*4+0] = r_; rgba[i*4+1] = g; rgba[i*4+2] = b; rgba[i*4+3] = a;
        }
    } else {
        for (uint32_t i = 0; i < width * height; i++) {
            uint8_t b = dst[i*3+0], g = dst[i*3+1], r_ = dst[i*3+2];
            rgba[i*4+0] = r_; rgba[i*4+1] = g; rgba[i*4+2] = b; rgba[i*4+3] = 0xFF;
        }
    }
    free(dst);
    *out_rgba = rgba;
    *out_w = (int)width;
    *out_h = (int)height;
    return 0;
}

/* ========== TLG6 辅助 ========== */
static uint32_t make_gt_mask(uint32_t a, uint32_t b) {
    uint32_t tmp2 = ~b;
    uint32_t tmp = ((a & tmp2) + (((a ^ tmp2) >> 1) & 0x7f7f7f7f)) & 0x80808080;
    tmp = ((tmp >> 7) + 0x7f7f7f7f) ^ 0x7f7f7f7f;
    return tmp;
}

static uint32_t packed_bytes_add(uint32_t a, uint32_t b) {
    uint32_t tmp = (((a & b) << 1) + ((a ^ b) & 0xfefefefe)) & 0x01010100;
    return a + b - tmp;
}

static uint32_t med2(uint32_t a, uint32_t b, uint32_t c) {
    uint32_t aa_gt_bb = make_gt_mask(a, b);
    uint32_t a_xor_b_and = ((a ^ b) & aa_gt_bb);
    uint32_t aa = a_xor_b_and ^ a;
    uint32_t bb = a_xor_b_and ^ b;
    uint32_t n = make_gt_mask(c, bb);
    uint32_t nn = make_gt_mask(aa, c);
    uint32_t m = ~(n | nn);
    return (n & aa) | (nn & bb) | ((bb & m) - (c & m) + (aa & m));
}

static uint32_t tlg6_med(uint32_t a, uint32_t b, uint32_t c, uint32_t v) {
    return packed_bytes_add(med2(a, b, c), v);
}

static uint32_t tlg6_avg(uint32_t a, uint32_t b, uint32_t c, uint32_t v) {
    uint32_t avg = ((a & b) + (((a ^ b) & 0xfefefefe) >> 1) + ((a ^ b) & 0x01010101));
    return packed_bytes_add(avg & 0xFFFFFFFF, v);
}

/* ========== TLG6 Golomb 解码 ========== */
static void tlg6_decode_golomb_values(uint8_t *pixelbuf, uint32_t pixel_count,
                                      const uint8_t *bit_pool, uint8_t color) {
    int n = TVP_TLG6_GOLOMB_N_COUNT - 1;
    int a = 0;
    int bit_pos = 1;
    uint8_t zero = (bit_pool[0] & 1) ? 0 : 1;
    const uint8_t *bp = bit_pool;
    int bpos = 0;
    uint8_t *limit = pixelbuf + pixel_count * 4;

    while (pixelbuf < limit) {
        uint32_t t = read_u32_le(bp + bpos) >> bit_pos;
        int b = TVPTLG6LeadingZeroTable[t & (TVP_TLG6_LeadingZeroTable_SIZE - 1)];
        int bit_count = b;
        while (!b) {
            bit_count += TVP_TLG6_LeadingZeroTable_BITS;
            bit_pos += TVP_TLG6_LeadingZeroTable_BITS;
            bpos += bit_pos >> 3;
            bit_pos &= 7;
            t = read_u32_le(bp + bpos) >> bit_pos;
            b = TVPTLG6LeadingZeroTable[t & (TVP_TLG6_LeadingZeroTable_SIZE - 1)];
            bit_count += b;
        }
        bit_pos += b;
        bpos += bit_pos >> 3;
        bit_pos &= 7;
        bit_count--;
        int count = 1 << bit_count;
        count += (read_u32_le(bp + bpos) >> bit_pos) & (count - 1);
        bit_pos += bit_count;
        bpos += bit_pos >> 3;
        bit_pos &= 7;

        if (zero) {
            while (count--) {
                if (pixelbuf >= limit) break;
                if (color == 0) memset(pixelbuf, 0, 4);
                else pixelbuf[color] = 0;
                pixelbuf += 4;
            }
            zero ^= 1;
        } else {
            while (count--) {
                if (pixelbuf >= limit) break;
                uint32_t t2 = read_u32_le(bp + bpos) >> bit_pos;
                int bit_count2, b2;
                if (t2) {
                    b2 = TVPTLG6LeadingZeroTable[t2 & (TVP_TLG6_LeadingZeroTable_SIZE - 1)];
                    bit_count2 = b2;
                    while (!b2) {
                        bit_count2 += TVP_TLG6_LeadingZeroTable_BITS;
                        bit_pos += TVP_TLG6_LeadingZeroTable_BITS;
                        bpos += bit_pos >> 3;
                        bit_pos &= 7;
                        t2 = read_u32_le(bp + bpos) >> bit_pos;
                        b2 = TVPTLG6LeadingZeroTable[t2 & (TVP_TLG6_LeadingZeroTable_SIZE - 1)];
                        bit_count2 += b2;
                    }
                    bit_count2--;
                } else {
                    bpos += 5;
                    bit_count2 = bp[bpos - 1];
                    bit_pos = 0;
                    t2 = read_u32_le(bp + bpos);
                    b2 = 0;
                }
                int k = (a < 128) ? TVPTLG6GolombBitLengthTable[a][n] : 0;
                int v = (bit_count2 << k) + ((t2 >> b2) & ((1 << k) - 1));
                int sign = (v & 1) - 1;
                v >>= 1;
                a += v;
                uint8_t val = (uint8_t)((v ^ sign) + sign + 1);
                if (color == 0) memset(pixelbuf, val, 4);
                else pixelbuf[color] = val;
                pixelbuf += 4;
                bit_pos += b2;
                bit_pos += k;
                bpos += bit_pos >> 3;
                bit_pos &= 7;
                n--;
                if (n < 0) {
                    a >>= 1;
                    n = TVP_TLG6_GOLOMB_N_COUNT - 1;
                }
            }
            zero ^= 1;
        }
    }
}

/* ========== TLG6 行解码 ========== */
static void tlg6_decode_line_generic(const uint32_t *prev_line, uint32_t *current_line,
                                     uint32_t width, uint32_t start_block, uint32_t block_limit,
                                     const uint8_t *filter_types, uint32_t skip_block_bytes,
                                     const uint32_t *in, uint32_t initial_p,
                                     uint32_t odd_skip, uint32_t dir, uint32_t colors) {
    uint32_t p, up;
    if (start_block) {
        prev_line += start_block * TVP_TLG6_W_BLOCK_SIZE;
        current_line += start_block * TVP_TLG6_W_BLOCK_SIZE;
        p  = current_line[-1];
        up = prev_line[-1];
    } else {
        p = up = initial_p;
    }
    const uint32_t *in_ptr = in + skip_block_bytes * start_block;
    int step = (dir & 1) ? 1 : -1;

    for (uint32_t i = start_block; i < block_limit; i++) {
        int w = (int)(width - i * TVP_TLG6_W_BLOCK_SIZE);
        if (w > TVP_TLG6_W_BLOCK_SIZE) w = TVP_TLG6_W_BLOCK_SIZE;
        int ww = w;
        if (step == -1) in_ptr += ww - 1;
        if (i & 1) in_ptr += odd_skip * ww;
        uint8_t ft = filter_types[i];

        while (w--) {
            uint32_t pix = *in_ptr;
            uint8_t a = (pix >> 24) & 0xFF;
            int8_t ir = (int8_t)((pix >> 16) & 0xFF);
            int8_t ig = (int8_t)((pix >> 8) & 0xFF);
            int8_t ib = (int8_t)(pix & 0xFF);
            int fr, fg, fb;
            switch (ft) {
                case 0:  fb=ib;         fg=ig;         fr=ir;         break;
                case 1:  fb=ib+ig;    fg=ig;         fr=ir+ig;    break;
                case 2:  fb=ib;         fg=ig+ib;    fr=ir+ib+ig; break;
                case 3:  fb=ib+ir+ig; fg=ig+ir;  fr=ir;         break;
                case 4:  fb=ib+ir;    fg=ig+ib+ir; fr=ir+ib+ir+ig; break;
                case 5:  fb=ib+ir;    fg=ig+ib+ir; fr=ir;         break;
                case 6:  fb=ib+ig;    fg=ig;         fr=ir;         break;
                case 7:  fb=ib;         fg=ig+ib;    fr=ir;         break;
                case 8:  fb=ib;         fg=ig;         fr=ir+ig;    break;
                case 9:  fb=ib+ig+ir+ib; fg=ig+ir+ib; fr=ir+ib; break;
                case 10: fb=ib+ir;    fg=ig+ir;    fr=ir;         break;
                case 11: fb=ib;         fg=ig+ib;    fr=ir+ib;    break;
                case 12: fb=ib;         fg=ig+ir+ib; fr=ir+ib;  break;
                case 13: fb=ib+ig;    fg=ig+ir+ib+ig; fr=ir+ib+ig; break;
                case 14: fb=ib+ig+ir; fg=ig+ir; fr=ir+ib+ig+ir; break;
                case 15: fb=ib;         fg=ig+(ib<<1); fr=ir+(ib<<1); break;
                default: fb=ib; fg=ig; fr=ir; break;
            }
            uint32_t pix_val;
            if (colors == 3)
                pix_val = 0xFF000000 | ((fr&0xFF)<<16) | ((fg&0xFF)<<8) | (fb&0xFF);
            else
                pix_val = ((a&0xFF)<<24) | ((fr&0xFF)<<16) | ((fg&0xFF)<<8) | (fb&0xFF);
            uint32_t u = *prev_line;
            if (ft & 1) p = tlg6_avg(p, u, up, pix_val);
            else        p = tlg6_med(p, u, up, pix_val);
            up = u;
            *current_line = p;
            current_line++;
            prev_line++;
            if (step == 1) in_ptr++;
            else in_ptr--;
        }
        if (step == 1)
            in_ptr += skip_block_bytes - ww;
        else
            in_ptr += skip_block_bytes + 1;
        if (i & 1)
            in_ptr -= odd_skip * ww;
    }
}

/* ========== TLG6 解码 ========== */
static int decode_tlg6(const uint8_t *src, size_t src_len, uint8_t **out_rgba,
                       int *out_w, int *out_h) {
    init_tlg6_tables();
    size_t pos = 0;
    if (src_len >= 11 && memcmp(src, "TLG0.0\x00sds\x1a", 11) == 0)
        pos += 15;
    if (pos + 20 > src_len || memcmp(src + pos, "TLG6.0\x00raw\x1a", 11) != 0)
        return -1;
    pos += 11;

    uint8_t colors = src[pos++];
    uint8_t data_flag = src[pos++];
    uint8_t color_type = src[pos++];
    uint8_t external_golomb = src[pos++];
    (void)data_flag; (void)color_type; (void)external_golomb;

    uint32_t width  = read_u32_le(src + pos); pos += 4;
    uint32_t height = read_u32_le(src + pos); pos += 4;
    uint32_t max_bit_length = read_u32_le(src + pos); pos += 4;

    if (colors != 1 && colors != 3 && colors != 4) return -1;

    uint32_t x_block_count = (width - 1) / TVP_TLG6_W_BLOCK_SIZE + 1;
    uint32_t y_block_count = (height - 1) / TVP_TLG6_H_BLOCK_SIZE + 1;
    uint32_t main_count = width / TVP_TLG6_W_BLOCK_SIZE;
    uint32_t fraction = width - main_count * TVP_TLG6_W_BLOCK_SIZE;

    uint32_t dst_size = width * height * 4;
    uint8_t *dst = (uint8_t *)calloc(1, dst_size);
    if (!dst) return -1;

    uint8_t *bit_pool = (uint8_t *)malloc(max_bit_length / 8 + 5);
    uint32_t *pixel_buffer = (uint32_t *)calloc(1, sizeof(uint32_t) * width * TVP_TLG6_H_BLOCK_SIZE + 4);
    uint8_t *filter_types = (uint8_t *)calloc(1, x_block_count * y_block_count);
    uint32_t *zero_line = (uint32_t *)calloc(width, sizeof(uint32_t));
    if (!bit_pool || !pixel_buffer || !filter_types || !zero_line) {
        free(dst); free(bit_pool); free(pixel_buffer); free(filter_types); free(zero_line);
        return -1;
    }
    if (colors == 3) {
        for (uint32_t i = 0; i < width; i++) zero_line[i] = 0xFF000000;
    }

    uint8_t lzss_dic[4096];
    memset(lzss_dic, 0, sizeof(lzss_dic));
    {
        uint32_t *p = (uint32_t *)lzss_dic;
        for (uint32_t i = 0; i < (0x01010101U << 5); i += 0x01010101U) {
            for (uint32_t j = 0; j < (0x01010101U << 4); j += 0x01010101U) {
                p[0] = i; p[1] = j; p += 2;
            }
        }
    }

    if (pos + 4 > src_len) { free(dst); return -1; }
    uint32_t ft_size = read_u32_le(src + pos); pos += 4;
    decomp_lzss(filter_types, src + pos, ft_size, lzss_dic, 0);
    pos += ft_size;

    uint8_t *pdst = dst;
    uint32_t *prev_line = zero_line;

    for (uint32_t y = 0; y < height; y += TVP_TLG6_H_BLOCK_SIZE) {
        uint32_t ylim = y + TVP_TLG6_H_BLOCK_SIZE;
        if (ylim > height) ylim = height;
        uint32_t pixel_count = (ylim - y) * width;

        for (uint8_t c = 0; c < colors; c++) {
            if (pos + 4 > src_len) { free(dst); return -1; }
            uint32_t bit_length = read_u32_le(src + pos); pos += 4;
            uint32_t method = (bit_length >> 30) & 3;
            bit_length &= 0x3FFFFFFF;
            uint32_t byte_length = bit_length / 8;
            if (bit_length % 8) byte_length++;
            if (pos + byte_length > src_len) { free(dst); return -1; }
            memcpy(bit_pool, src + pos, byte_length);
            pos += byte_length;
            if (method == 0) {
                tlg6_decode_golomb_values((uint8_t *)pixel_buffer + c, pixel_count, bit_pool, c);
            } else {
                free(dst); return -1;
            }
        }
        const uint8_t *ft = filter_types + (y / TVP_TLG6_H_BLOCK_SIZE) * x_block_count;
        uint32_t skip_bytes = (ylim - y) * TVP_TLG6_W_BLOCK_SIZE;
        for (uint32_t yy = y; yy < ylim; yy++) {
            uint32_t *current_line = (uint32_t *)pdst;
            uint32_t dir_val = (yy & 1) ^ 1;
            uint32_t odd_skip = (ylim - yy - 1) - (yy - y);
            if (main_count > 0) {
                uint32_t start = ((width < TVP_TLG6_W_BLOCK_SIZE) ? width : TVP_TLG6_W_BLOCK_SIZE) * (yy - y);
                tlg6_decode_line_generic(prev_line, current_line, width, 0, main_count,
                                         ft, skip_bytes, pixel_buffer + start,
                                         colors == 3 ? 0xFF000000 : 0, odd_skip, dir_val, colors);
            }
            if (main_count != x_block_count) {
                uint32_t ww = fraction;
                if (ww > TVP_TLG6_W_BLOCK_SIZE) ww = TVP_TLG6_W_BLOCK_SIZE;
                uint32_t start = ww * (yy - y);
                tlg6_decode_line_generic(prev_line, current_line, width, main_count, x_block_count,
                                         ft, skip_bytes, pixel_buffer + start,
                                         colors == 3 ? 0xFF000000 : 0, odd_skip, dir_val, colors);
            }
            prev_line = current_line;
            pdst += width * 4;
        }
    }
    free(bit_pool); free(pixel_buffer); free(filter_types); free(zero_line);

    uint8_t *rgba = (uint8_t *)malloc(width * height * 4);
    if (!rgba) { free(dst); return -1; }
    for (uint32_t i = 0; i < width * height; i++) {
        uint8_t b = dst[i*4+0], g = dst[i*4+1], r = dst[i*4+2], a = dst[i*4+3];
        rgba[i*4+0] = r; rgba[i*4+1] = g; rgba[i*4+2] = b; rgba[i*4+3] = a;
    }
    free(dst);
    *out_rgba = rgba;
    *out_w = (int)width;
    *out_h = (int)height;
    return 0;
}

/* ========== 统一 TLG 解码入口 ========== */
static int decode_tlg(const uint8_t *data, size_t len, uint8_t **out_rgba,
                      int *out_w, int *out_h) {
    const uint8_t *sig = data;
    if (len >= 11 && memcmp(data, "TLG0.0\x00sds\x1a", 11) == 0) {
        if (len >= 26) sig = data + 15;
    }
    if (len >= 11 && memcmp(sig, "TLG5.0\x00raw\x1a", 11) == 0)
        return decode_tlg5(data, len, out_rgba, out_w, out_h);
    else if (len >= 11 && memcmp(sig, "TLG6.0\x00raw\x1a", 11) == 0)
        return decode_tlg6(data, len, out_rgba, out_w, out_h);
    else
        return -1;
}

/* ========== PNG 输出 ========== */
static int save_png(const char *path, const uint8_t *rgba, int width, int height) {
    FILE *fp = fopen(path, "wb");
    if (!fp) return -1;
    png_structp png = png_create_write_struct(PNG_LIBPNG_VER_STRING, NULL, NULL, NULL);
    if (!png) { fclose(fp); return -1; }
    png_infop info = png_create_info_struct(png);
    if (!info) { png_destroy_write_struct(&png, NULL); fclose(fp); return -1; }
    if (setjmp(png_jmpbuf(png))) {
        png_destroy_write_struct(&png, &info);
        fclose(fp);
        return -1;
    }
    png_init_io(png, fp);
    int has_alpha = 0;
    for (int i = 0; i < width * height; i++) {
        if (rgba[i * 4 + 3] != 0xFF) { has_alpha = 1; break; }
    }
    if (has_alpha) {
        png_set_IHDR(png, info, width, height, 8, PNG_COLOR_TYPE_RGBA,
                     PNG_INTERLACE_NONE, PNG_COMPRESSION_TYPE_DEFAULT, PNG_FILTER_TYPE_DEFAULT);
        png_write_info(png, info);
        png_bytep *rows = (png_bytep *)malloc(height * sizeof(png_bytep));
        for (int y = 0; y < height; y++) rows[y] = (png_bytep)(rgba + y * width * 4);
        png_write_image(png, rows);
        free(rows);
    } else {
        png_set_IHDR(png, info, width, height, 8, PNG_COLOR_TYPE_RGB,
                     PNG_INTERLACE_NONE, PNG_COMPRESSION_TYPE_DEFAULT, PNG_FILTER_TYPE_DEFAULT);
        png_write_info(png, info);
        uint8_t *rgb = (uint8_t *)malloc(width * height * 3);
        for (int i = 0; i < width * height; i++) {
            rgb[i*3+0] = rgba[i*4+0];
            rgb[i*3+1] = rgba[i*4+1];
            rgb[i*3+2] = rgba[i*4+2];
        }
        png_bytep *rows = (png_bytep *)malloc(height * sizeof(png_bytep));
        for (int y = 0; y < height; y++) rows[y] = (png_bytep)(rgb + y * width * 3);
        png_write_image(png, rows);
        free(rows);
        free(rgb);
    }
    png_write_end(png, NULL);
    png_destroy_write_struct(&png, &info);
    fclose(fp);
    return 0;
}

/* ========== 十六进制文本检测 ========== */
static int is_hex_text(const uint8_t *data, size_t len) {
    if (len == 0) return 0;
    size_t valid = 0;
    for (size_t i = 0; i < len; i++) {
        char c = data[i];
        if (c == ' ' || c == '\t' || c == '\n' || c == '\r') continue;
        if (!isxdigit((unsigned char)c)) return 0;
        valid++;
    }
    return valid > 0;
}

/* ========== 十六进制转二进制 ========== */
static uint8_t *hex_to_bytes(const uint8_t *text, size_t len, size_t *out_len) {
    size_t count = 0;
    for (size_t i = 0; i < len; i++) {
        if (isxdigit((unsigned char)text[i])) count++;
    }
    *out_len = count / 2;
    uint8_t *out = (uint8_t *)malloc(*out_len);
    if (!out) return NULL;
    size_t j = 0;
    for (size_t i = 0; i < len && j < *out_len * 2; ) {
        while (i < len && !isxdigit((unsigned char)text[i])) i++;
        if (i >= len) break;
        char hex[3] = {text[i], 0, 0};
        i++;
        while (i < len && !isxdigit((unsigned char)text[i])) i++;
        if (i >= len) break;
        hex[1] = text[i];
        i++;
        out[j / 2] = (uint8_t)strtol(hex, NULL, 16);
        j += 2;
    }
    return out;
}

/* ========== RIFF WebP 块提取 ========== */
typedef struct {
    size_t start;
    size_t end;
} chunk_t;

static int find_webp_chunks(const uint8_t *data, size_t len, chunk_t **out_chunks, int *out_count) {
    int capacity = 16;
    int count = 0;
    chunk_t *chunks = (chunk_t *)malloc(capacity * sizeof(chunk_t));
    if (!chunks) return -1;
    size_t pos = 0;
    while (pos + 12 <= len) {
        const uint8_t *p = memchr(data + pos, 'R', len - pos);
        if (!p) break;
        pos = p - data;
        if (pos + 12 > len) break;
        if (memcmp(data + pos, "RIFF", 4) == 0 &&
            memcmp(data + pos + 8, "WEBP", 4) == 0) {
            uint32_t size = read_u32_le(data + pos + 4);
            size_t end = pos + 8 + size;
            if (end <= len && end > pos) {
                if (count >= capacity) {
                    capacity *= 2;
                    chunks = (chunk_t *)realloc(chunks, capacity * sizeof(chunk_t));
                }
                chunks[count].start = pos;
                chunks[count].end = end;
                count++;
                pos = end;
                continue;
            }
        }
        pos++;
    }
    *out_chunks = chunks;
    *out_count = count;
    return 0;
}

/* ========== 伪 TLG / 通用 WebP 提取 ========== */
static int extract_webp_generic(const char *filepath, uint8_t xor_key, int delete_src) {
    char dir_name[MAX_PATH_LEN];
    char base_name[256];
    strncpy(dir_name, filepath, MAX_PATH_LEN - 1);
    dir_name[MAX_PATH_LEN - 1] = '\0';
    char *last_slash = strrchr(dir_name, '/');
    if (last_slash) {
        *last_slash = '\0';
        strncpy(base_name, last_slash + 1, 255);
    } else {
        strncpy(base_name, filepath, 255);
    }
    base_name[255] = '\0';
    char *dot = strrchr(base_name, '.');
    if (dot) *dot = '\0';

    FILE *fp = fopen(filepath, "rb");
    if (!fp) return 0;
    fseek(fp, 0, SEEK_END);
    long size = ftell(fp);
    fseek(fp, 0, SEEK_SET);
    uint8_t *raw = (uint8_t *)malloc(size);
    if (!raw) { fclose(fp); return 0; }
    fread(raw, 1, size, fp);
    fclose(fp);

    uint8_t *data = raw;
    size_t data_len = size;
    int need_free_data = 0;
    if (is_hex_text(raw, size)) {
        uint8_t *bin = hex_to_bytes(raw, size, &data_len);
        if (bin) { data = bin; need_free_data = 1; }
    }
    if (xor_key) {
        for (size_t i = 0; i < data_len; i++) data[i] ^= xor_key;
    }

    chunk_t *chunks = NULL;
    int chunk_count = 0;
    find_webp_chunks(data, data_len, &chunks, &chunk_count);

    int extracted = 0;
    for (int i = 0; i < chunk_count; i++) {
        char out_path[MAX_PATH_LEN];
        char safe_base[256];
        strncpy(safe_base, base_name, 255);
        safe_base[255] = '\0';
        int n = snprintf(out_path, sizeof(out_path), "%s/%s_%03d.webp",
                 dir_name, safe_base, i);
        if (n < 0 || (size_t)n >= sizeof(out_path)) continue;
        FILE *out = fopen(out_path, "wb");
        if (!out) continue;
        fwrite(data + chunks[i].start, 1, chunks[i].end - chunks[i].start, out);
        fclose(out);
        extracted++;
    }
    free(chunks);
    if (need_free_data) free(data);
    free(raw);
    if (extracted > 0 && delete_src) remove(filepath);
    return extracted;
}

/* ========== PIMG 提取（编号从01开始，避免重名） ========== */
static int extract_pimg(const char *filepath, int delete_src) {
    char dir_name[MAX_PATH_LEN];
    char base_name[256];
    strncpy(dir_name, filepath, MAX_PATH_LEN - 1);
    dir_name[MAX_PATH_LEN - 1] = '\0';
    char *last_slash = strrchr(dir_name, '/');
    if (last_slash) {
        *last_slash = '\0';
        strncpy(base_name, last_slash + 1, 255);
    } else {
        strncpy(base_name, filepath, 255);
    }
    base_name[255] = '\0';
    char *dot = strrchr(base_name, '.');
    if (dot) *dot = '\0';

    FILE *fp = fopen(filepath, "rb");
    if (!fp) return 0;
    fseek(fp, 0, SEEK_END);
    long size = ftell(fp);
    fseek(fp, 0, SEEK_SET);
    uint8_t *data = (uint8_t *)malloc(size);
    if (!data) { fclose(fp); return 0; }
    fread(data, 1, size, fp);
    fclose(fp);

    int extracted = 0;
    int idx = 1;
    size_t pos = 0;
    while (pos + 12 <= (size_t)size) {
        uint8_t *p = memchr(data + pos, 'R', size - pos);
        if (!p) break;
        pos = p - data;
        if (pos + 12 > (size_t)size) break;
        if (memcmp(data + pos, "RIFF", 4) == 0 &&
            memcmp(data + pos + 8, "WEBP", 4) == 0) {
            uint32_t chunk_size = read_u32_le(data + pos + 4);
            size_t end = pos + 8 + chunk_size;
            if (end <= (size_t)size && end > pos) {
                char out_path[MAX_PATH_LEN];
                int n;
                while (1) {
                    n = snprintf(out_path, sizeof(out_path), "%s/%s_%02d.webp",
                                 dir_name, base_name, idx);
                    if (n < 0 || (size_t)n >= sizeof(out_path)) break;
                    struct stat st;
                    if (stat(out_path, &st) != 0) break;
                    idx++;
                }
                if (n > 0 && (size_t)n < sizeof(out_path)) {
                    FILE *out = fopen(out_path, "wb");
                    if (out) {
                        fwrite(data + pos, 1, end - pos, out);
                        fclose(out);
                        extracted++;
                    }
                }
                idx++;
                pos = end;
                continue;
            }
        }
        pos++;
    }
    free(data);
    if (extracted > 0 && delete_src) remove(filepath);
    return extracted;
}

/* ========== 任务队列 ========== */
typedef struct {
    char src[MAX_PATH_LEN];
} task_t;

static task_t *g_tasks = NULL;
static int g_task_count = 0;
static int g_task_capacity = 0;
static int g_next_task = 0;
static int g_success = 0;
static int g_failed = 0;
static int g_processed = 0;
static pthread_mutex_t g_mutex = PTHREAD_MUTEX_INITIALIZER;

static void add_task(const char *src) {
    if (g_task_count >= g_task_capacity) {
        g_task_capacity = g_task_capacity ? g_task_capacity * 2 : 256;
        g_tasks = (task_t *)realloc(g_tasks, g_task_capacity * sizeof(task_t));
    }
    snprintf(g_tasks[g_task_count].src, MAX_PATH_LEN, "%s", src);
    g_task_count++;
}

/* ========== 递归扫描所有子目录 ========== */
static void scan_files_recursive(const char *root) {
    DIR *dir = opendir(root);
    if (!dir) return;
    struct dirent *entry;
    while ((entry = readdir(dir)) != NULL) {
        if (strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0)
            continue;
        char path[MAX_PATH_LEN];
        snprintf(path, sizeof(path), "%s/%s", root, entry->d_name);
        struct stat st;
        if (stat(path, &st) != 0) continue;
        if (S_ISDIR(st.st_mode)) {
            scan_files_recursive(path);
        } else {
            size_t len = strlen(path);
            if (len > 5 && strcasecmp(path + len - 5, ".pimg") == 0) {
                add_task(path);
            } else if (len > 4 && strcasecmp(path + len - 4, ".tlg") == 0) {
                add_task(path);
            }
        }
    }
    closedir(dir);
}

static void print_progress(int current, int total, const char *desc) {
    if (total == 0) return;
    double percent = (current / (double)total) * 100.0;
    int bar_width = 30;
    int filled = (int)((current / (double)total) * bar_width);
    
    fprintf(stderr, "\r%s [", desc);
    for (int i = 0; i < bar_width; i++) {
        if (i < filled) fprintf(stderr, "=");
        else if (i == filled) fprintf(stderr, ">");
        else fprintf(stderr, " ");
    }
    fprintf(stderr, "] %d/%d (%.1f%%)", current, total, percent);
    fflush(stderr);
}

/* ========== 工作线程 ========== */
static void *worker_thread(void *arg) {
    (void)arg;
    while (1) {
        pthread_mutex_lock(&g_mutex);
        int idx = g_next_task++;
        pthread_mutex_unlock(&g_mutex);
        if (idx >= g_task_count) break;

        task_t *t = &g_tasks[idx];
        const char *ext = strrchr(t->src, '.');
        int count = 0;
        int is_pimg = (ext && strcasecmp(ext, ".pimg") == 0);

        if (is_pimg) {
            count = extract_pimg(t->src, !g_keep);
        } else {
            /* 先尝试真 TLG 解码 */
            FILE *fp = fopen(t->src, "rb");
            if (fp) {
                fseek(fp, 0, SEEK_END);
                long sz = ftell(fp);
                fseek(fp, 0, SEEK_SET);
                uint8_t *data = (uint8_t *)malloc(sz);
                if (data) {
                    fread(data, 1, sz, fp);
                    fclose(fp);
                    uint8_t *rgba = NULL;
                    int w, h;
                    if (decode_tlg(data, sz, &rgba, &w, &h) == 0) {
                        /* 真 TLG，保存 PNG */
                        char out_path[MAX_PATH_LEN];
                        char base[256];
                        strncpy(base, t->src, 255); base[255] = '\0';
                        char *d = strrchr(base, '.');
                        if (d) *d = '\0';
                        snprintf(out_path, sizeof(out_path), "%s.png", base);
                        if (save_png(out_path, rgba, w, h) == 0) {
                            count = 1;
                            if (!g_keep) remove(t->src);
                        }
                        free(rgba);
                    } else {
                        /* 伪 TLG，提取 WebP */
                        count = extract_webp_generic(t->src, g_xor_key, !g_keep);
                    }
                    free(data);
                } else {
                    fclose(fp);
                }
            }
        }
        pthread_mutex_lock(&g_mutex);
        g_processed++;
        /* 清掉进度条行，打印结果，再恢复进度条 */
        fprintf(stderr, "\r\033[K");
        if (count > 0) {
            g_success += count;
            printf("[OK] %s -> %d item(s)\n", t->src, count);
        } else {
            g_failed++;
            fprintf(stderr, "[FAIL] %s\n", t->src);
        }
        print_progress(g_processed, g_task_count, "Progress");
        pthread_mutex_unlock(&g_mutex);
    }
    return NULL;
}

/* ========== 用法说明 ========== */
static void print_usage(const char *prog) {
    printf("Usage: %s [options]\n", prog);
    printf("Options:\n");
    printf("  --xor <key>    XOR decryption key for pseudo-TLG (e.g. 0xA3)\n");
    printf("  --keep         Keep original files after extraction\n");
    printf("  -j <n>         Number of worker threads (default: 8)\n");
    printf("  -h, --help     Show this help\n");
}

/* ========== 主函数 ========== */
int main(int argc, char *argv[]) {
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--xor") == 0 && i + 1 < argc) {
            g_xor_key = (uint8_t)strtol(argv[++i], NULL, 0);
        } else if (strcmp(argv[i], "--keep") == 0) {
            g_keep = 1;
        } else if (strcmp(argv[i], "-j") == 0 && i + 1 < argc) {
            g_workers = atoi(argv[++i]);
            if (g_workers < 1) g_workers = 1;
        } else if (strcmp(argv[i], "-h") == 0 || strcmp(argv[i], "--help") == 0) {
            print_usage(argv[0]);
            return 0;
        }
    }

    struct stat st;
    if (stat(ROOT_DIR, &st) != 0 || !S_ISDIR(st.st_mode)) {
        fprintf(stderr, "Error: directory not found: %s\n", ROOT_DIR);
        return 1;
    }

    printf("[*] Scanning: %s\n", ROOT_DIR);
    scan_files_recursive(ROOT_DIR);

    if (g_task_count == 0) {
        printf("[*] No .tlg or .pimg files found.\n");
        return 0;
    }

    if (g_workers > g_task_count) g_workers = g_task_count;
    printf("[*] Found %d files, using %d worker(s)...\n", g_task_count, g_workers);

    pthread_t *threads = (pthread_t *)malloc(g_workers * sizeof(pthread_t));
    for (int i = 0; i < g_workers; i++) {
        pthread_create(&threads[i], NULL, worker_thread, NULL);
    }
    for (int i = 0; i < g_workers; i++) {
        pthread_join(threads[i], NULL);
    }
    free(threads);

    fprintf(stderr, "\n");
    printf("[+] Done! Success: %d images, Failed: %d files\n", g_success, g_failed);
    free(g_tasks);
    return 0;
}
