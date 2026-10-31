#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <errno.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <limits.h>

#define PROGRAM     "file_inject"
#define VERSION     "1.1.0"
#define COPY_BUFSZ  65536

static int g_color   = 0;
static int g_verbose = 0;
static int g_quiet   = 0;

#define A_RESET   "\033[0m"
#define A_BLUE    "\033[1;34m"
#define A_CYAN    "\033[1;36m"
#define A_GREEN   "\033[1;32m"
#define A_YELLOW  "\033[1;33m"
#define A_RED     "\033[1;31m"

#define MSG(...)   do { if (g_color) fputs(A_BLUE   "==>" A_RESET " ", stderr); else fputs("==> ", stderr); fprintf(stderr, __VA_ARGS__); fputc('\n', stderr); } while (0)
#define INFO(...)  do { if (g_color) fputs("  " A_CYAN "->" A_RESET " ", stderr); else fputs("  -> ", stderr); fprintf(stderr, __VA_ARGS__); fputc('\n', stderr); } while (0)
#define OK(...)    do { if (g_color) fputs(A_GREEN  "==>" A_RESET " ", stderr); else fputs("==> ", stderr); fprintf(stderr, __VA_ARGS__); fputc('\n', stderr); } while (0)
#define WARN(...)  do { if (g_color) fputs(A_YELLOW "==> 警告:" A_RESET " ", stderr); else fputs("==> 警告: ", stderr); fprintf(stderr, __VA_ARGS__); fputc('\n', stderr); } while (0)
#define ERR(...)   do { if (g_color) fputs(A_RED    "==> 错误:" A_RESET " ", stderr); else fputs("==> 错误: ", stderr); fprintf(stderr, __VA_ARGS__); fputc('\n', stderr); } while (0)

static void usage(FILE *out) {
    fprintf(out,
        "用法: " PROGRAM " [选项] <注入文件> <目标文件> [起始位置] [结束位置 | 输出文件] [输出文件]\n"
        "\n"
        "在目标文件的指定字节偏移处插入或替换数据，结果写入输出文件。\n"
        "本工具不会修改目标文件。\n"
        "\n"
        "位置参数语义:\n"
        "  2 个参数  注入 目标                     追加到末尾 → in_<目标文件名>\n"
        "  3 个参数  注入 目标 起始位置            插入        → in_<目标文件名>\n"
        "  4 个参数  注入 目标 起始位置 结束位置   替换        → in_<目标文件名>\n"
        "            注入 目标 起始位置 输出文件   插入        → 指定输出文件\n"
        "  5 个参数  注入 目标 起始位置 结束位置 输出文件\n"
        "            (4 参数时以能否解析为偏移决定第 4 项语义,偏移优先)\n"
        "\n"
        "偏移格式:\n"
        "  123          十进制字节偏移\n"
        "  0x7B         十六进制字节偏移\n"
        "  1K 2M 1G     带二进制单位 (K/M/G/T)\n"
        "  end / eof    文件末尾\n"
        "  end-10       距文件末尾 10 字节 (支持 end-1K 等)\n"
        "  -10          同上，需以 -- 分隔选项和位置参数\n"
        "\n"
        "选项:\n"
        "  -f, --force        覆盖已存在的输出文件\n"
        "  -v, --verbose      显示详细进度\n"
        "  -q, --quiet        仅输出错误\n"
        "      --color=WHEN   颜色: auto (默认), always, never\n"
        "  -h, --help         显示此帮助\n"
        "  -V, --version      显示版本\n"
        "\n"
        "退出码:\n"
        "  0  成功\n"
        "  1  运行时错误\n"
        "  2  用法错误\n"
        "\n"
        "示例:\n"
        "  " PROGRAM " patch.png fw.bin                          # 追加到末尾 → in_fw.bin\n"
        "  " PROGRAM " patch.png fw.bin 0x1000                   # 插入 @ 0x1000 → in_fw.bin\n"
        "  " PROGRAM " patch.png fw.bin 0x1000 0x2000            # 替换 [0x1000,0x2000) → in_fw.bin\n"
        "  " PROGRAM " patch.png fw.bin 0x1000 out.bin           # 插入 @ 0x1000 → out.bin\n"
        "  " PROGRAM " patch.png fw.bin 0x1000 0x2000 out.bin    # 替换 → out.bin\n"
        "  " PROGRAM " -f data.bin fw.bin end-4 out.bin          # 替换末尾 4 字节\n"
        "  " PROGRAM " -- data.bin fw.bin -4 out.bin             # 负数偏移写法\n"
    );
}

static void version(void) { printf("%s %s\n", PROGRAM, VERSION); }

static int parse_color_mode(const char *s, int *out) {
    if (!strcmp(s, "auto"))   { *out = -1; return 0; }
    if (!strcmp(s, "always") || !strcmp(s, "yes") || !strcmp(s, "force")) { *out = 1; return 0; }
    if (!strcmp(s, "never")  || !strcmp(s, "no")  || !strcmp(s, "none"))  { *out = 0; return 0; }
    return -1;
}

static int is_offset_syntax(const char *s) {
    if (!s || s[0] != '-') return 0;
    return s[1] >= '0' && s[1] <= '9';
}

static int parse_offset(const char *s, off_t file_size, off_t *out) {
    if (!s || !*s) return -1;

    int negative = 0;
    const char *p = s;

    if (!strcmp(p, "end") || !strcmp(p, "eof")) { *out = file_size; return 0; }
    if (!strncmp(p, "end-", 4)) { negative = 1; p += 4; }
    else if (*p == '-')         { negative = 1; p++; }
    if (!*p) return -1;

    errno = 0;
    char *endp = NULL;
    unsigned long long val;
    if (p[0] == '0' && (p[1] == 'x' || p[1] == 'X'))
        val = strtoull(p, &endp, 16);
    else
        val = strtoull(p, &endp, 10);
    if (errno == ERANGE || endp == p) return -1;

    unsigned long long mul = 1;
    if (*endp) {
        switch (*endp) {
            case 'K': case 'k': mul = 1024ULL; break;
            case 'M': case 'm': mul = 1024ULL * 1024; break;
            case 'G': case 'g': mul = 1024ULL * 1024 * 1024; break;
            case 'T': case 't': mul = 1024ULL * 1024 * 1024 * 1024; break;
            default: return -1;
        }
        endp++;
        if (*endp == 'i' || *endp == 'I') endp++;
        if (*endp == 'B' || *endp == 'b') endp++;
        if (*endp) return -1;
    }

    if (val > ULLONG_MAX / mul) return -1;
    unsigned long long total = val * mul;
    if (total > (unsigned long long)LLONG_MAX) return -1;
    if (total > (unsigned long long)file_size) return -1;

    long long abs_off = negative
        ? (long long)file_size - (long long)total
        : (long long)total;
    *out = (off_t)abs_off;
    return 0;
}

static int copy_range(int src_fd, int dst_fd, off_t src_off, off_t count) {
    char buf[COPY_BUFSZ];
    if (lseek(src_fd, src_off, SEEK_SET) == (off_t)-1) return -1;
    while (count > 0) {
        size_t want = (count < (off_t)sizeof(buf)) ? (size_t)count : sizeof(buf);
        ssize_t n;
        do { n = read(src_fd, buf, want); } while (n < 0 && errno == EINTR);
        if (n < 0) return -1;
        if (n == 0) { errno = EIO; return -1; }
        ssize_t off = 0;
        while (off < n) {
            ssize_t w;
            do { w = write(dst_fd, buf + off, (size_t)(n - off)); } while (w < 0 && errno == EINTR);
            if (w < 0) return -1;
            off += w;
        }
        count -= n;
    }
    return 0;
}

static int fsync_parent_dir(const char *path) {
    char *dup = strdup(path);
    if (!dup) return -1;
    char *slash = strrchr(dup, '/');
    const char *dir;
    if (slash) {
        if (slash == dup) slash[1] = '\0';
        else              *slash   = '\0';
        dir = dup;
    } else {
        dir = ".";
    }
    int fd = open(dir, O_RDONLY | O_CLOEXEC | O_DIRECTORY);
    free(dup);
    if (fd < 0) return -1;
    int r = fsync(fd);
    close(fd);
    return r;
}

/* 同目录下: in_<basename> */
static char *make_default_output(const char *target_path) {
    const char *slash = strrchr(target_path, '/');
    const char *base  = slash ? slash + 1 : target_path;
    size_t dir_len    = slash ? (size_t)(slash - target_path) + 1 : 0;
    size_t need       = dir_len + 3 + strlen(base) + 1;
    char *out = malloc(need);
    if (!out) return NULL;
    if (dir_len) memcpy(out, target_path, dir_len);
    memcpy(out + dir_len, "in_", 3);
    strcpy(out + dir_len + 3, base);
    return out;
}

int main(int argc, char **argv) {
    int force = 0;
    int color_mode = -1;

    /* ---- 1. 解析选项 ---- */
    int i = 1;
    for (; i < argc; i++) {
        const char *a = argv[i];
        if (!strcmp(a, "--")) { i++; break; }
        if (a[0] != '-' || a[1] == '\0') break;

        if (!strcmp(a, "-h") || !strcmp(a, "--help"))    { usage(stdout); return 0; }
        if (!strcmp(a, "-V") || !strcmp(a, "--version")) { version(); return 0; }
        if (!strcmp(a, "-f") || !strcmp(a, "--force"))   { force = 1; continue; }
        if (!strcmp(a, "-v") || !strcmp(a, "--verbose")) { g_verbose = 1; continue; }
        if (!strcmp(a, "-q") || !strcmp(a, "--quiet"))   { g_quiet = 1; continue; }
        if (!strcmp(a, "--color")) {
            if (i + 1 >= argc) { fputs("错误: --color 需要一个参数\n", stderr); return 2; }
            if (parse_color_mode(argv[++i], &color_mode) < 0) {
                fprintf(stderr, "错误: 无效的颜色模式 '%s'\n", argv[i]); return 2;
            }
            continue;
        }
        if (!strncmp(a, "--color=", 8)) {
            if (parse_color_mode(a + 8, &color_mode) < 0) {
                fprintf(stderr, "错误: 无效的颜色模式 '%s'\n", a + 8); return 2;
            }
            continue;
        }
        if (is_offset_syntax(a)) break;
        fprintf(stderr, "错误: 未知选项 '%s' (使用 --help 查看帮助)\n", a);
        return 2;
    }

    /* ---- 2. 颜色决策 ---- */
    if (color_mode < 0) {
        const char *no   = getenv("NO_COLOR");
        const char *term = getenv("TERM");
        g_color = !((no && *no) || (term && !strcmp(term, "dumb")) || !isatty(STDERR_FILENO));
    } else {
        g_color = color_mode;
    }

    /* ---- 3. 位置参数 ---- */
    int npos = argc - i;
    if (npos < 2 || npos > 5) {
        ERR("需要 2~5 个位置参数,实际 %d 个", npos);
        fputc('\n', stderr);
        usage(stderr);
        return 2;
    }

    const char *inject_path = argv[i];
    const char *target_path = argv[i + 1];
    const char *start_str   = NULL;
    const char *end_str     = NULL;
    const char *output_path = NULL;

    if (npos >= 3) start_str = argv[i + 2];
    if (npos == 5) { end_str = argv[i + 3]; output_path = argv[i + 4]; }
    /* npos == 4 的判定推迟到拿到目标文件大小之后 */

    int inject_fd = -1, target_fd = -1, out_fd = -1;
    int out_created = 0;
    int ret = 1;
    char *default_output = NULL;
    struct stat st_inject, st_target, st_out;

    /* ---- 4. 打开注入文件 ---- */
    inject_fd = open(inject_path, O_RDONLY | O_CLOEXEC);
    if (inject_fd < 0) { ERR("无法打开注入文件 '%s': %s", inject_path, strerror(errno)); goto cleanup; }
    if (fstat(inject_fd, &st_inject) < 0) { ERR("无法读取注入文件状态: %s", strerror(errno)); goto cleanup; }
    if (!S_ISREG(st_inject.st_mode)) { ERR("注入文件不是普通文件: '%s'", inject_path); goto cleanup; }

    /* ---- 5. 打开目标文件 ---- */
    target_fd = open(target_path, O_RDONLY | O_CLOEXEC);
    if (target_fd < 0) { ERR("无法打开目标文件 '%s': %s", target_path, strerror(errno)); goto cleanup; }
    if (fstat(target_fd, &st_target) < 0) { ERR("无法读取目标文件状态: %s", strerror(errno)); goto cleanup; }
    if (!S_ISREG(st_target.st_mode)) { ERR("目标文件不是普通文件: '%s'", target_path); goto cleanup; }

    /* ---- 6. 处理 4 参数歧义(偏移优先) ---- */
    if (npos == 4) {
        off_t dummy;
        if (parse_offset(argv[i + 3], st_target.st_size, &dummy) == 0) {
            end_str = argv[i + 3];
        } else {
            output_path = argv[i + 3];
        }
    }

    /* ---- 7. 解析起止偏移 ---- */
    off_t start_off, end_off;
    if (!start_str) {
        start_off = end_off = st_target.st_size;   /* 追加到末尾 */
    } else {
        if (parse_offset(start_str, st_target.st_size, &start_off) < 0) {
            ERR("无效的起始位置: '%s' (目标文件大小 %lld 字节)",
                start_str, (long long)st_target.st_size);
            goto cleanup;
        }
        if (!end_str) {
            end_off = start_off;                   /* 插入 */
        } else {
            if (parse_offset(end_str, st_target.st_size, &end_off) < 0) {
                ERR("无效的结束位置: '%s'", end_str);
                goto cleanup;
            }
            if (end_off < start_off) {
                ERR("结束位置 (%lld) 小于起始位置 (%lld)",
                    (long long)end_off, (long long)start_off);
                goto cleanup;
            }
        }
    }

    /* ---- 8. 默认输出 ---- */
    if (!output_path) {
        default_output = make_default_output(target_path);
        if (!default_output) { ERR("内存不足"); goto cleanup; }
        output_path = default_output;
        if (!g_quiet) INFO("未指定输出文件,默认使用: %s", output_path);
    }

    /* ---- 9. 检查输出文件 ---- */
    if (stat(output_path, &st_out) == 0) {
        if (st_out.st_dev == st_target.st_dev && st_out.st_ino == st_target.st_ino) {
            ERR("输出文件与目标文件是同一个文件: '%s'", output_path);
            goto cleanup;
        }
        if (S_ISDIR(st_out.st_mode)) { ERR("输出路径是目录: '%s'", output_path); goto cleanup; }
        if (!force) { ERR("输出文件已存在: '%s' (使用 -f 覆盖)", output_path); goto cleanup; }
    }

    /* ---- 10. 大小计算与溢出检查 ---- */
    off_t removed = end_off - start_off;
    off_t kept    = st_target.st_size - removed;
    if (st_inject.st_size > 0 && kept > (off_t)LLONG_MAX - st_inject.st_size) {
        ERR("输出文件大小将溢出"); goto cleanup;
    }
    off_t new_size = kept + st_inject.st_size;

    /* ---- 11. 创建输出文件 ---- */
    int oflags = O_WRONLY | O_CREAT | O_CLOEXEC | (force ? O_TRUNC : O_EXCL);
    out_fd = open(output_path, oflags, 0644);
    if (out_fd < 0) {
        if (errno == EEXIST && !force) ERR("输出文件已存在: '%s' (使用 -f 覆盖)", output_path);
        else                           ERR("无法创建输出文件 '%s': %s", output_path, strerror(errno));
        goto cleanup;
    }
    out_created = 1;

    /* ---- 12. 摘要 ---- */
    if (!g_quiet) {
        const char *mode;
        if (!start_str)                               mode = "追加到末尾";
        else if (end_str && end_off > start_off)      mode = "替换";
        else                                          mode = "插入";
        MSG("%s %s", PROGRAM, VERSION);
        INFO("操作模式: %s", mode);
        INFO("注入文件: %s (%lld 字节)", inject_path, (long long)st_inject.st_size);
        INFO("目标文件: %s (%lld 字节)", target_path, (long long)st_target.st_size);
        if (!start_str) {
            INFO("追加位置: %lld", (long long)start_off);
        } else if (end_str && end_off > start_off) {
            INFO("替换区间: [%lld, %lld) 共 %lld 字节",
                 (long long)start_off, (long long)end_off, (long long)removed);
        } else {
            INFO("插入位置: %lld", (long long)start_off);
        }
        INFO("输出文件: %s (预期 %lld 字节)", output_path, (long long)new_size);
        MSG("正在写入...");
    }

    /* ---- 13. 三段写入 ---- */
    if (start_off > 0) {
        if (g_verbose) INFO("复制目标 [0, %lld)", (long long)start_off);
        if (copy_range(target_fd, out_fd, 0, start_off) < 0) {
            ERR("复制目标文件前半段失败: %s", strerror(errno)); goto cleanup;
        }
    }
    if (st_inject.st_size > 0) {
        if (g_verbose) INFO("写入注入文件 (%lld 字节)", (long long)st_inject.st_size);
        if (copy_range(inject_fd, out_fd, 0, st_inject.st_size) < 0) {
            ERR("写入注入文件失败: %s", strerror(errno)); goto cleanup;
        }
    }
    if (end_off < st_target.st_size) {
        if (g_verbose) INFO("复制目标 [%lld, %lld)",
                            (long long)end_off, (long long)st_target.st_size);
        if (copy_range(target_fd, out_fd, end_off, st_target.st_size - end_off) < 0) {
            ERR("复制目标文件后半段失败: %s", strerror(errno)); goto cleanup;
        }
    }

    /* ---- 14. 持久化与校验 ---- */
    if (fsync(out_fd) < 0) { ERR("fsync 失败: %s", strerror(errno)); goto cleanup; }
    if (fstat(out_fd, &st_out) < 0) { ERR("无法读取输出文件状态: %s", strerror(errno)); goto cleanup; }
    if (st_out.st_size != new_size)
        WARN("输出大小 %lld 与预期 %lld 不符",
             (long long)st_out.st_size, (long long)new_size);

    if (close(out_fd) < 0) {
        ERR("关闭输出文件失败: %s", strerror(errno));
        out_fd = -1; goto cleanup;
    }
    out_fd = -1;

    if (fsync_parent_dir(output_path) < 0 && g_verbose)
        WARN("目录 fsync 失败(已忽略): %s", strerror(errno));

    out_created = 0;
    if (!g_quiet) OK("完成: %s (%lld 字节)", output_path, (long long)new_size);
    ret = 0;

cleanup:
    if (out_fd    >= 0) close(out_fd);
    if (out_created)    unlink(output_path);
    if (target_fd >= 0) close(target_fd);
    if (inject_fd >= 0) close(inject_fd);
    free(default_output);
    return ret;
}