#!/data/data/com.termux/files/usr/bin/bash

REL_PATH="$1"
FILE_NAME="$2"
REMOTE_NAME="$3"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

for cmd in mpv rclone fzf jq; do
    if ! command -v $cmd &> /dev/null; then
        printf '%b\n' "${RED}错误: 未安装 $cmd${NC}"
        read -p "按回车返回..."
        exit 1
    fi
done

# ==========================================
# 播放器状态
# ==========================================
PLAY_MODE="顺序播放"
PLAY_SPEED="1.0"
TIMER_MINUTES=0
TIMER_START=0

# ==========================================
# 获取播放列表
# ==========================================
CURRENT_DIR=$(dirname "$REL_PATH")
[ "$CURRENT_DIR" == "." ] && CURRENT_DIR=""

printf '%b\n' "${YELLOW}正在扫描目录下的音频文件...${NC}"

PLAYLIST=()
while IFS= read -r line; do
    [ -n "$line" ] && PLAYLIST+=("$line")
done < <(rclone lsjson "${REMOTE_NAME}:${CURRENT_DIR}" 2>/dev/null \
    | jq -r '.[] | select(.IsDir | not) | select(.Name != null and .Name != "") | .Name' \
    | sort -V \
    | grep -iE '\.(mp3|flac|wav|ogg|m4a|aac|wma|opus|ape|aiff|alac)$')

TOTAL=${#PLAYLIST[@]}

if [ $TOTAL -eq 0 ]; then
    printf '%b\n' "${RED}当前目录没有音频文件！${NC}"
    read -p "按回车返回..."
    exit 0
fi

CURRENT_INDEX=0
for i in "${!PLAYLIST[@]}"; do
    if [ "${PLAYLIST[$i]}" == "$FILE_NAME" ]; then
        CURRENT_INDEX=$i
        break
    fi
done

# ==========================================
# 播放器菜单 (TAB 键呼出)
# ==========================================
show_player_menu() {
    while true; do
        clear
        printf '%b\n' "${CYAN}========================================${NC}"
        printf '%b\n' "${CYAN}🎵 播放器菜单${NC}"
        printf '%b\n' "${CYAN}========================================${NC}"
        printf '%b\n' "当前: ${GREEN}[${DISPLAY_NUM}/${TOTAL}] ${CURRENT_FILE}${NC}"
        printf '%b\n' "模式: ${GREEN}${PLAY_MODE}${NC} | 速度: ${GREEN}${PLAY_SPEED}x${NC}"
        [ $TIMER_MINUTES -gt 0 ] && printf '%b\n' "定时: ${GREEN}${TIMER_MINUTES}分钟后关闭${NC}"
        printf '%s\n' "----------------------------------------"

        MENU="📋 当前列表 (选择歌曲)
▶ 顺序播放
🔀 随机播放
🔂 单曲循环
🔁 列表循环
⏰ 定时播放 (分钟)
⏩ 倍速调节
↩ 返回播放"

        CHOICE=$(printf '%b\n' "$MENU" | fzf --border --reverse --prompt="选择操作 (ESC返回): ")
        [ -z "$CHOICE" ] && return

        case "$CHOICE" in
            "📋 当前列表"*)
                SELECTED=$(printf '%s\n' "${PLAYLIST[@]}" | fzf \
                    --border --reverse \
                    --prompt="选择歌曲 (ESC返回): " \
                    --default="${PLAYLIST[$CURRENT_INDEX]}")
                if [ -n "$SELECTED" ]; then
                    for i in "${!PLAYLIST[@]}"; do
                        if [ "${PLAYLIST[$i]}" == "$SELECTED" ]; then
                            CURRENT_INDEX=$i
                            break
                        fi
                    done
                fi
                return
                ;;
            "▶ 顺序播放")   PLAY_MODE="顺序播放" ;;
            "🔀 随机播放")   PLAY_MODE="随机播放" ;;
            "🔂 单曲循环")   PLAY_MODE="单曲循环" ;;
            "🔁 列表循环")   PLAY_MODE="列表循环" ;;
            "⏰ 定时播放"*)
                printf '%b\n' "${YELLOW}输入定时分钟数 (0取消):${NC}"
                read -r TIMER_MINUTES
                [[ ! "$TIMER_MINUTES" =~ ^[0-9]+$ ]] && TIMER_MINUTES=0
                [ $TIMER_MINUTES -gt 0 ] && TIMER_START=$(date +%s)
                ;;
            "⏩ 倍速调节")
                SPEED=$(printf '0.25\n0.5\n0.75\n1.0\n1.25\n1.5\n2.0\n3.0\n4.0' | fzf --border --reverse --prompt="选择倍速: ")
                [ -n "$SPEED" ] && PLAY_SPEED="$SPEED"
                ;;
            "↩ 返回播放") return ;;
        esac
    done
}

# ==========================================
# 获取下一首索引
# ==========================================
get_next_index() {
    case "$PLAY_MODE" in
        "随机播放") echo $(( RANDOM % TOTAL )) ;;
        "单曲循环") echo "$CURRENT_INDEX" ;;
        *)          echo $(( (CURRENT_INDEX + 1) % TOTAL )) ;;
    esac
}

# ==========================================
# 检查定时器
# ==========================================
check_timer() {
    if [ $TIMER_MINUTES -gt 0 ]; then
        ELAPSED=$(( $(date +%s) - TIMER_START ))
        REMAINING=$(( TIMER_MINUTES * 60 - ELAPSED ))
        if [ $REMAINING -le 0 ]; then
            return 1
        fi
    fi
    return 0
}

# ==========================================
# 主播放循环
# ==========================================
while true; do
    if ! check_timer; then
        clear
        printf '%b\n' "${YELLOW}⏰ 定时播放结束！${NC}"
        break
    fi

    CURRENT_FILE="${PLAYLIST[$CURRENT_INDEX]}"
    DISPLAY_NUM=$((CURRENT_INDEX + 1))

    if [ -z "$CURRENT_DIR" ] || [ "$CURRENT_DIR" == "/" ] || [ "$CURRENT_DIR" == "." ]; then
        FULL_PATH="/${CURRENT_FILE}"
    else
        FULL_PATH="${CURRENT_DIR}/${CURRENT_FILE}"
    fi

    clear
    printf '%b\n' "${CYAN}========================================${NC}"
    printf '%b\n' "${CYAN}🎵 音乐播放器${NC}"
    printf '%b\n' "${CYAN}========================================${NC}"
    printf '%b\n' "曲目: ${GREEN}[${DISPLAY_NUM}/${TOTAL}] ${CURRENT_FILE}${NC}"
    printf '%b\n' "${YELLOW}正在加载音频流...${NC}"
    printf '\n'
    printf '%b\n' "${GREEN}空格${NC}暂停 ${GREEN}←→${NC}±5秒 ${GREEN}↑↓${NC}±60秒"
    printf '%b\n' "${GREEN}9/0${NC}音量 ${GREEN}m${NC}静音 ${GREEN}q${NC}退出本曲"
    printf '%s\n' "----------------------------------------"

    rclone cat "${REMOTE_NAME}:${FULL_PATH}" | mpv \
        --ao=opensles \
        --no-video \
        --cache=auto \
        --speed="$PLAY_SPEED" \
        -

    NEXT_INDEX=$(get_next_index)
    NEXT_FILE="${PLAYLIST[$NEXT_INDEX]}"

    clear
    printf '%b\n' "${GREEN}✅ [${DISPLAY_NUM}/${TOTAL}] ${CURRENT_FILE}${NC}"
    printf '\n'
    printf '%b\n' "下一首: ${CYAN}$((NEXT_INDEX + 1))/${TOTAL} ${NEXT_FILE}${NC}"
    printf '\n'

    if [ $TIMER_MINUTES -gt 0 ]; then
        ELAPSED=$(( $(date +%s) - TIMER_START ))
        REMAINING=$(( TIMER_MINUTES * 60 - ELAPSED ))
        if [ $REMAINING -gt 0 ]; then
            printf '%b\n' "${YELLOW}⏰ 定时关闭: 剩余 $((REMAINING / 60))分$((REMAINING % 60))秒${NC}"
        fi
    fi

    printf '%b\n' "${YELLOW}3秒后自动播放 | ${GREEN}TAB${NC}菜单 | ${GREEN}q${NC}退出 | ${GREEN}p${NC}上一首"

    KEY=""
    read -t 3 -rsn1 KEY

    case "$KEY" in
        $'\t')
            show_player_menu
            NEXT_INDEX=$(get_next_index)
            CURRENT_INDEX=$NEXT_INDEX
            ;;
        q|Q) break ;;
        p|P) CURRENT_INDEX=$(( (CURRENT_INDEX - 1 + TOTAL) % TOTAL )) ;;
        r|R) ;;
        *)   CURRENT_INDEX=$NEXT_INDEX ;;
    esac
done

clear
printf '%b\n' "${GREEN}播放列表结束。${NC}"
read -p "按回车返回..."