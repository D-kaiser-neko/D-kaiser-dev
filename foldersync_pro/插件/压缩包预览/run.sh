#!/data/data/com.termux/files/usr/bin/bash

REL_PATH="$1"
FILE_NAME="$2"
REMOTE_NAME="$3"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

# ==========================================
# 引擎 1: WebDAV 极速模式 (HTTP Range)
# ==========================================
use_webdav_range() {
    # 获取 rclone 配置中的 URL
    local URL=$(rclone config show "$REMOTE_NAME" 2>/dev/null | grep "^url = " | awk '{print $3}')
    [ -z "$URL" ] && return 1

    # 尝试从 rclone 获取认证头 (利用 dump headers 捕获)
    # 注意：这需要一个存在的文件来触发请求，我们直接用根目录
    local AUTH=$(rclone ls "$REMOTE_NAME:" --max-depth 1 --dump headers 2>&1 | grep -i "Authorization:" | head -n 1 | sed 's/Authorization: //')
    
    if [ -z "$AUTH" ]; then
        return 1
    fi

    # 清理 URL 末尾的 /
    URL="${URL%/}"
    # 构建完整文件 URL
    local FULL_URL="${URL}/${REL_PATH#/}"

    echo -e "${YELLOW}检测到 WebDAV，正在使用极速模式 (仅获取目录)...${NC}"
    
    # 发送 HEAD 请求获取文件大小
    local SIZE=$(curl -s -I -H "Authorization: $AUTH" "$FULL_URL" | grep -i "Content-Length" | awk '{print $2}' | tr -d '\r')
    
    if [ -z "$SIZE" ] || [ "$SIZE" -eq 0 ]; then
        return 1
    fi

    # 计算偏移量：只下载最后 100000 字节
    local OFFSET=$((SIZE - 100000))
    [ $OFFSET -lt 0 ] && OFFSET=0

    local TAIL_FILE="$TEMP_DIR/tail.zip"
    
    # 使用 Range 请求下载末尾
    curl -s -H "Authorization: $AUTH" -r "$OFFSET-" "$FULL_URL" -o "$TAIL_FILE"

    # 尝试用 Python 解析被截断的 ZIP 目录
    # 注意：标准的 unzip 无法处理截断文件，这里我们用 python 的 zipfile 尝试
    if command -v python3 &> /dev/null; then
        python3 -c "
import zipfile, sys
try:
    with zipfile.ZipFile(sys.argv[1]) as zf:
        for name in zf.namelist():
            print(name)
except Exception as e:
    sys.exit(1)
" "$TAIL_FILE" > "$TEMP_DIR/list.txt" 2>/dev/null
        if [ $? -eq 0 ] && [ -s "$TEMP_DIR/list.txt" ]; then
            echo "WEBDAV_OK"
            return 0
        fi
    fi
    
    return 1
}

# ==========================================
# 引擎 2: 通用全量下载模式 (回退方案)
# ==========================================
use_full_download() {
    echo -e "${YELLOW}正在全量下载压缩包...${NC}"
    local TEMP_FILE="$TEMP_DIR/$FILE_NAME"
    rclone copyto "${REMOTE_NAME}:${REL_PATH}" "$TEMP_FILE" --quiet 2>/dev/null
    
    if [ ! -f "$TEMP_FILE" ]; then
        return 1
    fi

    local EXT="${FILE_NAME##*.}"
    EXT="${EXT,,}"
    [[ "$FILE_NAME" == *.tar.gz ]] && EXT="tar.gz"

    case "$EXT" in
        zip) unzip -Z1 "$TEMP_FILE" 2>/dev/null > "$TEMP_DIR/list.txt" ;;
        tar.gz|tgz) tar -tzf "$TEMP_FILE" 2>/dev/null > "$TEMP_DIR/list.txt" ;;
        *) return 1 ;;
    esac
    echo "FULL_OK"
    return 0
}

# ==========================================
# 主流程
# ==========================================
MODE="FULL"
if [[ "$FILE_NAME" == *.zip ]]; then
    if use_webdav_range; then
        MODE="WEBDAV"
    else
        echo -e "${YELLOW}极速模式不可用，回退到全量下载...${NC}"
        sleep 1
        if ! use_full_download; then
            echo -e "${RED}无法读取压缩包！${NC}"
            read -p "回车返回..."
            exit 1
        fi
    fi
else
    # 非 ZIP 文件直接走全量下载
    if ! use_full_download; then
        echo -e "${RED}不支持该格式或下载失败！${NC}"
        read -p "回车返回..."
        exit 1
    fi
fi

# 过滤垃圾目录
grep -v '^$' "$TEMP_DIR/list.txt" | grep -v '__MACOSX' > "$TEMP_DIR/clean_list.txt"

# 交互式浏览
while true; do
    clear
    echo -e "${CYAN}📦 压缩包预览: ${FILE_NAME}${NC}"
    [ "$MODE" == "WEBDAV" ] && echo -e "${GREEN}⚡ 极速模式已激活${NC}"
    echo "------------------------------------------------"
    
    SELECTED=$(fzf --border --reverse --prompt="搜索/选择 (ESC退出): " < "$TEMP_DIR/clean_list.txt")
    [ -z "$SELECTED" ] && break

    if [[ "$SELECTED" == */ ]]; then
        echo "这是一个目录，请输入目录名过滤。"
        read -p "回车继续..."
        continue
    fi

    OP=$(echo -e "预览文本内容 (前100行)\n返回" | fzf --border --reverse --prompt="操作: ")
    if [ "$OP" == "预览文本内容 (前100行)" ]; then
        clear
        echo -e "${CYAN}--- 预览: ${SELECTED} ---${NC}"
        if [ "$MODE" == "WEBDAV" ]; then
            # WebDAV 模式下预览文件，需要再次发起 Range 请求
            # 这里简化处理：提示用户暂不支持极速预览单文件内容（需要解析偏移量，太复杂）
            echo "极速模式下预览单文件功能开发中..."
            echo "请使用全量下载模式预览。"
        else
            # 全量模式下直接读取
            local TEMP_FILE="$TEMP_DIR/$FILE_NAME"
            if [[ "$FILE_NAME" == *.zip ]]; then
                unzip -p "$TEMP_FILE" "$SELECTED" 2>/dev/null | head -n 100
            else
                tar -xzf "$TEMP_FILE" -O "$SELECTED" 2>/dev/null | head -n 100
            fi
        fi
        echo "------------------------------------------------"
        read -p "回车返回..."
    fi
done
