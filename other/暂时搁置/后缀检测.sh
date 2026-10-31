#!/bin/sh
# ============================================================
# 文件后缀自动纠正工具 (Shell 重构版 / MT 管理器兼容)
# 用法:
#   sh fix_ext.sh                  扫描当前目录及子目录(直接执行)
#   sh fix_ext.sh /sdcard/xxx      扫描指定目录
#   sh fix_ext.sh -n               预览模式, 不实际改名
#   sh fix_ext.sh --no-recursive   只扫当前目录
#   sh fix_ext.sh -l my.log        指定日志文件
# ============================================================

# ===================== 配置区 =====================
READ_BYTES=64                      # 每个文件只读头部多少字节
BAR_WIDTH=30                       # 进度条宽度
LOG_NAME="rename_log.txt"          # 默认日志文件名(放在扫描目录下)

# ZIP 系白名单: 本质是 ZIP 但不改后缀
ZIP_BASED_EXTS=" .docx .xlsx .pptx .jar .apk .ods .odt .ott .odp .odg .epub .cbz .xpi .ipa .docm .xlsm .pptm .aab "

# OLE2 系白名单: 文件头相同但保留原后缀
OLE2_SAFE_EXTS=" .doc .xls .ppt .msi .msg "
# ==================================================

usage() {
    echo "用法: sh fix_ext.sh [目录] [-n|--dry-run] [--no-recursive] [-l 日志路径]"
}

# ---------- 工具函数 ----------

in_list() {
    # $1=待查项 $2=空格包围的列表
    case "$2" in
        *" $1 "*) return 0 ;;
    esac
    return 1
}

get_suffix() {
    # 模拟 Python Path.suffix: .bashrc 视为无后缀
    name=$1
    case "$name" in
        .*)
            rest=${name#.}
            case "$rest" in
                *.*) printf '.%s' "${rest##*.}" ;;
                *)   printf '' ;;
            esac
            ;;
        *.*) printf '.%s' "${name##*.}" ;;
        *)   printf '' ;;
    esac
}

read_hex() {
    # 读文件头, 输出连续大写十六进制
    if [ "$HEX_TOOL" = "xxd" ]; then
        xxd -p -l "$READ_BYTES" "$1" 2>/dev/null | tr -d '\n ' | tr 'a-f' 'A-F'
    else
        od -An -v -tx1 -N "$READ_BYTES" "$1" 2>/dev/null | tr -d '\n ' | tr 'a-f' 'A-F'
    fi
}

detect_type() {
    # 输入大写hex串, 输出扩展名; 无法识别输出空
    hex=$1
    [ -z "$hex" ] && return 0
    case "$hex" in
        89504E470D0A1A0A*)                 echo ".png";  return ;;
        FFD8FFE0*|FFD8FFE1*|FFD8FFE2*|FFD8FFE3*|FFD8FFE8*|FFD8FFDB*)
                                           echo ".jpg";  return ;;
        474946383961*|474946383761*)       echo ".gif";  return ;;
        424D*)                             echo ".bmp";  return ;;
        52494646????????57454250*)         echo ".webp"; return ;;
        52494646????????41564920*)         echo ".avi";  return ;;
        52494646????????57415645*)         echo ".wav";  return ;;
        00000100*)                         echo ".ico";  return ;;
        49492A00*|4D4D002A*)               echo ".tiff"; return ;;
        0000001866747970*)                 echo ".mov";  return ;;
        ????????66747970*)
            # ISOBMFF 容器: 读取 ftyp 的 brand 区域(offset 8~31)再细分
            region=$(printf '%s' "$hex" | cut -c17-64)
            case "$region" in
                # avif / avis
                *61766966*|*61766973*)
                    echo ".avif" ;;
                # heic / heix / hevc / hevx / heim / heis
                *68656963*|*68656978*|*68657663*|*68657678*|*6865696D*|*68656973*)
                    echo ".heic" ;;
                # heif / mif1
                *68656966*|*6D696631*)
                    echo ".heif" ;;
                # crx  (Canon RAW)
                *63727820*)
                    echo ".cr3" ;;
                # M4A
                *4D344120*)
                    echo ".m4a" ;;
                # M4V
                *4D345620*)
                    echo ".m4v" ;;
                # qt
                *71742020*)
                    echo ".mov" ;;
                *)
                    echo ".mp4" ;;
            esac
            return ;;
        0000000C6A50*)                     echo ".jp2";  return ;;
        25504446*)                         echo ".pdf";  return ;;
        D0CF11E0A1B11AE1*)                 echo ".ole2"; return ;;
        504B0304*|504B0506*|504B0708*)     echo ".zip";  return ;;
        7F454C46*)                         echo ".elf";  return ;;
        CAFEBABE*)                         echo ".class"; return ;;
        526172211A0700*|526172211A070100*) echo ".rar";  return ;;
        377ABCAF271C*)                     echo ".7z";   return ;;
        1F8B08*)                           echo ".gz";   return ;;
        425A68*)                           echo ".bz2";  return ;;
        FD377A585A00*)                     echo ".xz";   return ;;
        494433*|FFFB*|FFF3*|FFF2*)         echo ".mp3";  return ;;
        664C6143*)                         echo ".flac"; return ;;
        4F676753*)                         echo ".ogg";  return ;;
        1A45DFA3*)                         echo ".mkv";  return ;;
        3026B2758E66CF11*)                 echo ".wmv";  return ;;
    esac
}

safe_rename() {
    # $1=原路径 $2=新扩展名; 输出不冲突的新路径
    src=$1; ext=$2
    dir=${src%/*}
    [ "$dir" = "$src" ] && dir="."
    name=${src##*/}
    suf=$(get_suffix "$name")
    if [ -n "$suf" ]; then stem=${name%"$suf"}; else stem=$name; fi
    dst="$dir/$stem$ext"
    if [ ! -e "$dst" ]; then printf '%s' "$dst"; return; fi
    i=1
    while :; do
        dst="$dir/${stem}_$i$ext"
        if [ ! -e "$dst" ]; then printf '%s' "$dst"; return; fi
        i=$((i + 1))
    done
}

draw_progress() {
    # $1=已完成 $2=总数
    done_n=$1; total_n=$2
    [ "$total_n" -le 0 ] && return
    pct=$((done_n * 100 / total_n))
    filled=$((pct * BAR_WIDTH / 100))
    empty=$((BAR_WIDTH - filled))
    bar=""
    i=0; while [ "$i" -lt "$filled" ]; do bar="${bar}#"; i=$((i + 1)); done
    i=0; while [ "$i" -lt "$empty" ];  do bar="${bar}-"; i=$((i + 1)); done
    printf '\r[%s] %3d%% (%d/%d)' "$bar" "$pct" "$done_n" "$total_n" >&2
}

# ---------- 参数解析 ----------
TARGET=""
DRY_RUN=0
RECURSIVE=1
LOG_FILE=""

while [ $# -gt 0 ]; do
    case "$1" in
        -n|--dry-run)     DRY_RUN=1 ;;
        --no-recursive)   RECURSIVE=0 ;;
        -l|--log)         shift; LOG_FILE=$1 ;;
        -h|--help)        usage; exit 0 ;;
        -*)               echo "未知选项: $1"; usage; exit 1 ;;
        *)                if [ -z "$TARGET" ]; then TARGET=$1; else echo "多余参数: $1"; exit 1; fi ;;
    esac
    shift
done

[ -z "$TARGET" ] && TARGET=$(pwd)
TARGET=${TARGET%/}
[ -z "$TARGET" ] && TARGET="/"

if [ ! -d "$TARGET" ]; then
    echo "[错误] 目录不存在: $TARGET"
    exit 1
fi

[ -z "$LOG_FILE" ] && LOG_FILE="$TARGET/$LOG_NAME"

# ---------- 环境检测 ----------
if command -v xxd >/dev/null 2>&1; then
    HEX_TOOL=xxd
elif command -v od >/dev/null 2>&1; then
    HEX_TOOL=od
else
    echo "[错误] 需要 xxd 或 od 其中之一"
    exit 1
fi

LIST_FILE=$(mktemp 2>/dev/null) || LIST_FILE="/tmp/.fixext_list.$$"
LOG_TMP=$(mktemp 2>/dev/null)   || LOG_TMP="/tmp/.fixext_log.$$"
trap 'rm -f "$LIST_FILE" "$LOG_TMP"' EXIT

# ---------- 横幅 ----------
if [ "$DRY_RUN" = 1 ]; then MODE="预览模式"; else MODE="执行模式"; fi
if [ "$RECURSIVE" = 1 ]; then RECMODE="递归"; else RECMODE="仅当前目录"; fi
echo "🔍 文件后缀自动纠正工具 (Shell版)"
echo "   目录: $TARGET"
echo "   模式: $MODE | $RECMODE"
echo "   日志: $LOG_FILE"
echo "    hex工具: $HEX_TOOL"
echo "--------------------------------------------------"

# ---------- 生成文件清单 ----------
if [ "$RECURSIVE" = 1 ]; then
    find "$TARGET" -type f 2>/dev/null | sort > "$LIST_FILE"
else
    find "$TARGET" -maxdepth 1 -type f 2>/dev/null | sort > "$LIST_FILE"
fi

total=$(wc -l < "$LIST_FILE" | tr -d ' ')
echo "   待扫描文件: $total"
echo

# ---------- 主循环 ----------
scanned=0; fixed=0; skipped=0; errors=0; processed=0

while IFS= read -r file; do
    [ -z "$file" ] && continue
    [ "$file" = "$LOG_FILE" ] && continue

    scanned=$((scanned + 1))
    processed=$((processed + 1))
    draw_progress "$processed" "$total"

    name=${file##*/}
    suf=$(get_suffix "$name")
    suf_lc=$(printf '%s' "$suf" | tr 'A-Z' 'a-z')

    hex=$(read_hex "$file")
    det=$(detect_type "$hex")

    if [ -z "$det" ]; then
        skipped=$((skipped + 1))
        continue
    fi

    need=0; reason=""; newext=""

    if [ -z "$suf_lc" ]; then
        # 无后缀: 添加
        case "$det" in
            .ole2) newext=".doc" ;;
            *)     newext="$det" ;;
        esac
        need=1; reason="添加后缀"
    else
        case "$det" in
            .ole2)
                if [ "$suf_lc" = ".doc" ] || in_list "$suf_lc" "$OLE2_SAFE_EXTS"; then
                    skipped=$((skipped + 1)); continue
                fi
                newext=".doc"; need=1; reason="纠正后缀 ($suf_lc → .doc)"
                ;;
            .zip)
                if [ "$suf_lc" = ".zip" ] || in_list "$suf_lc" "$ZIP_BASED_EXTS"; then
                    skipped=$((skipped + 1)); continue
                fi
                newext=".zip"; need=1; reason="纠正后缀 ($suf_lc → .zip)"
                ;;
            *)
                if [ "$suf_lc" = "$det" ]; then
                    skipped=$((skipped + 1)); continue
                fi
                newext="$det"; need=1; reason="纠正后缀 ($suf_lc → $det)"
                ;;
        esac
    fi

    if [ "$need" = 1 ]; then
        dst=$(safe_rename "$file" "$newext")
        ts=$(date '+%Y-%m-%d %H:%M:%S')
        if [ "$DRY_RUN" = 1 ]; then
            echo ""
            echo "  $reason: $name → ${dst##*/}"
            printf '%s | %s → %s | %s\n' "$ts" "$file" "$dst" "$reason" >> "$LOG_TMP"
            fixed=$((fixed + 1))
        else
            err=$(mv "$file" "$dst" 2>&1)
            if [ $? -eq 0 ]; then
                echo ""
                echo "  $reason: $name → ${dst##*/}"
                printf '%s | %s → %s | %s\n' "$ts" "$file" "$dst" "$reason" >> "$LOG_TMP"
                fixed=$((fixed + 1))
            else
                echo ""
                echo "  [失败] $name: $err"
                errors=$((errors + 1))
            fi
        fi
    fi
done < "$LIST_FILE"

# 进度条收尾
printf '\r' >&2
i=0; while [ "$i" -lt $((BAR_WIDTH + 20)) ]; do printf ' ' >&2; i=$((i + 1)); done
printf '\r' >&2
draw_progress "$total" "$total"
printf '\n' >&2

# ---------- 日志 ----------
if [ -s "$LOG_TMP" ]; then
    header="文件后缀纠正日志 - $(date '+%Y-%m-%d %H:%M:%S')"
    if [ "$DRY_RUN" = 1 ]; then
        echo ""
        echo "[预览模式] 不会写入日志文件, 以下为将要记录的内容:"
        echo "$header"
        echo "============================================================"
        cat "$LOG_TMP"
        echo "============================================================"
    else
        {
            echo "$header"
            echo "============================================================"
            cat "$LOG_TMP"
            echo "============================================================"
            echo ""
        } >> "$LOG_FILE" && echo "📄 日志已写入: $LOG_FILE" || echo "[错误] 无法写入日志: $LOG_FILE"
    fi
fi

# ---------- 统计 ----------
echo ""
echo "=================================================="
echo "📊 统计结果:"
echo "   扫描文件: $scanned"
echo "   修正/添加: $fixed"
echo "   跳过(正确/无法识别): $skipped"
echo "   错误: $errors"
if [ "$DRY_RUN" = 1 ]; then
    echo "   ⚠️  以上为预览模式, 未实际修改任何文件"
fi
echo "=================================================="