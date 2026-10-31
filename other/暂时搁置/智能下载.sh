#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# 通用并发批量下载脚本 (Termux 环境)
#
# 用法:
#   dl <链接>
#     例: dl "https://momon-ga.com/fanzine/mo3376976/1*.webp"
#         dl "z2.momon-ga.com/galleries/3376976/*.jpg"   # 自动补 https://
#
# 注意: 链接含 * 时必须加引号, 否则 zsh 会按通配符展开报错.
#
# 规则:
#   1. 链接带 "*"     -> wget 并发批量下载, * 依次替换为 0,1,2,...
#   2. 链接为 .m3u8   -> yt-dlp + aria2c
#   3. 其余普通链接   -> aria2c
#   4. 链接缺少协议   -> 自动补 https:// 再下载
# ============================================================

# ---------- 配置区 (可调) ----------
CONCURRENCY=8            # wget 并发数(批量下载)
RETRY_TIMES=3             # 单文件失败重试次数
MAX_CONSECUTIVE_FAIL=3    # 连续失败多少张视为末页
TIMEOUT=15                # wget 超时(秒)
DL_DIR="/storage/emulated/0/termux/dl/"   # 下载目录
#BATCH_START=0             # * 替换的起始数字
# ---------------------------------

# ---------- 读取命令行参数(只取第 1 个) ----------
if [ -z "$1" ]; then
    echo "用法: dl <链接>"
    echo "  例: dl \"https://momon-ga.com/fanzine/mo3376976/1*.webp\""
    echo "  注意: 链接含 * 时必须加引号."
    exit 1
fi
PAGE_URL="$1"

# ---------- 链接缺少协议时自动补 https:// ----------
case "$PAGE_URL" in
    http://*|https://*) ;;      # 已有协议, 不动
    *) PAGE_URL="https://$PAGE_URL"; echo "[补全协议] 已自动添加 https:// -> $PAGE_URL" ;;
esac

mkdir -p "$DL_DIR"
cd "$DL_DIR" || exit 1

# ============================================================
# 分支1: 链接带 "*" -> wget 并发批量下载
# ============================================================
if [[ "$PAGE_URL" == *"*"* ]]; then
    echo "[批量下载] 链接含 '*', 使用 wget ($CONCURRENCY 并发)"
    echo 输入起始
    read -r BATCH_START
    echo "  将 * 依次替换为 $BATCH_START, $((BATCH_START+1)), ..."
    echo "======================================"

    # ---------- 单文件下载函数(含重试) ----------
    download_page() {
        local num=$1
        local url="${PAGE_URL//\*/$num}"
        local attempt
        attempt=0
        while [ "$attempt" -lt "$RETRY_TIMES" ]; do
            if wget -c -q --timeout="$TIMEOUT" "$url" 2>/dev/null; then
                echo "[$num] 下载成功: $url"
                return 0
            fi
            attempt=$((attempt+1))
            echo "[$num] 下载失败, 重试 ($attempt/$RETRY_TIMES)"
            sleep 1
        done
        return 1
    }

    # ---------- 并发下载主循环 ----------
    RESULT_FILE="$DL_DIR/.result_$$"
    : > "$RESULT_FILE"
    export PAGE_URL RETRY_TIMES TIMEOUT RESULT_FILE

    dl_task() {
        local num=$1
        if download_page "$num" 2>/dev/null; then
            echo "$num 0" >> "$RESULT_FILE"
        else
            echo "$num 1" >> "$RESULT_FILE"
        fi
    }

    num=$BATCH_START
    next_report=$BATCH_START
    consecutive_fail=0

    while true; do
        # 并发控制: 后台任务数达到上限则等待
        while :; do
            running=$(jobs -r -p | wc -l)
            [ "$running" -lt "$CONCURRENCY" ] && break
            sleep 0.3
        done

        dl_task "$num" &
        num=$((num+1))

        # 按序号顺序读取已完成结果, 更新连续失败计数
        while :; do
            line=$(grep -E "^${next_report} " "$RESULT_FILE" | head -n1)
            [ -z "$line" ] && break
            status=${line##* }
            if [ "$status" = "0" ]; then
                consecutive_fail=0
            else
                consecutive_fail=$((consecutive_fail+1))
            fi
            next_report=$((next_report+1))
        done

        # 连续失败达上限 => 判定末页, 停止
        if [ "$consecutive_fail" -ge "$MAX_CONSECUTIVE_FAIL" ]; then
            echo "连续 ${MAX_CONSECUTIVE_FAIL} 个序号下载失败, 判定已到末页, 停止发起新请求。"
            break
        fi
    done

    wait
    rm -f "$RESULT_FILE"
    echo "======================================"
    echo "批量下载结束。文件保存在: $DL_DIR/"
    exit 0
fi

# ============================================================
# 分支2: .m3u8 -> yt-dlp + aria2c
# ============================================================
case "$PAGE_URL" in
    *.m3u8|*\.m3u8\?*)
        echo "[m3u8] 使用 yt-dlp + aria2c ($ARIA2_THREADS 线程)"
        yt-dlp \
            --downloader aria2c \
            --downloader-args "aria2c:-x $ARIA2_THREADS -s $ARIA2_THREADS" \
            -o "%(title)s.%(ext)s" \
            "$PAGE_URL"
        exit $?
        ;;
esac

# ============================================================
# 分支3: 普通链接 -> wget
# ============================================================
echo "[普通下载] 使用 wget "
wget "$PAGE_URL"
ls
exit $?
