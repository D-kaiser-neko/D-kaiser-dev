#!/data/data/com.termux/files/usr/bin/bash

REMOTE_NAME="$1"
REMOTE_PATH="$2"
LOCAL_PATHS="$3"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# 依赖检查
for cmd in fzf rclone; do
    if ! command -v $cmd &> /dev/null; then
        echo -e "${RED}错误: 未安装 $cmd${NC}"
        exit 1
    fi
done

choose() {
    printf "%b\n" "$1" | fzf --border --reverse --prompt="$2"
}

# ==========================================
# 1. 选择云端目标目录
# ==========================================
echo -e "${YELLOW}正在获取云端目录列表...${NC}"
REMOTE_DIRS=$(rclone lsd "${REMOTE_NAME}:${REMOTE_PATH}" 2>/dev/null | awk '{for(i=5;i<=NF;i++) printf "%s ", $i; print ""}' | sed 's/ *$//')

DIR_MENU="[根目录] ${REMOTE_PATH}"
if [ -n "$REMOTE_DIRS" ]; then
    while IFS= read -r d; do
        [ -n "$d" ] && DIR_MENU="${DIR_MENU}\n${d}"
    done <<< "$REMOTE_DIRS"
fi
DIR_MENU="${DIR_MENU}\n[新建] 手动输入目录"

TARGET=$(choose "$DIR_MENU" "选择云端目标目录 (ESC取消): ")
[ -z "$TARGET" ] && exit 0

if [[ "$TARGET" == "[根目录]"* ]]; then
    TARGET_DIR="$REMOTE_PATH"
elif [[ "$TARGET" == "[新建]"* ]]; then
    read -p "输入云端目录路径 (例如 /backup/archives): " TARGET_DIR
    [ -z "$TARGET_DIR" ] && exit 0
    [[ "$TARGET_DIR" != /* ]] && TARGET_DIR="/$TARGET_DIR"
else
    TARGET_DIR="${REMOTE_PATH}/${TARGET}"
fi

# ==========================================
# 2. 输入名称 + 自动加日期
# ==========================================
DATE_STR=$(date '+%Y%m%d_%H%M%S')
read -p "输入归档名称 (将自动添加日期后缀): " BASE_NAME
[ -z "$BASE_NAME" ] && BASE_NAME="archive"
ARCHIVE_NAME="${BASE_NAME}_${DATE_STR}"

# ==========================================
# 3. 选择压缩种类
# ==========================================
FORMAT=$(choose "zip\ntar.gz\ntar.xz\n7z\ntar (仅打包,无压缩)" "选择压缩格式: ")
[ -z "$FORMAT" ] && exit 0

# 检查对应工具
case "$FORMAT" in
    zip) command -v zip &>/dev/null || { echo -e "${RED}错误: 未安装 zip (pkg install zip)${NC}"; exit 1; } ;;
    7z) command -v 7z &>/dev/null || { echo -e "${RED}错误: 未安装 7z (pkg install p7zip)${NC}"; exit 1; } ;;
    tar.xz) command -v xz &>/dev/null || { echo -e "${RED}错误: 未安装 xz (pkg install xz-utils)${NC}"; exit 1; } ;;
esac

# ==========================================
# 4. 选择压缩程度
# ==========================================
LEVEL=$(choose "仅存储\n极速\n快速\n标准\n最大\n极限" "选择压缩程度: ")
[ -z "$LEVEL" ] && exit 0

# ==========================================
# 5. 构建压缩参数并执行
# ==========================================
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

# 将本地路径转为数组
mapfile -t PATH_ARRAY <<< "$LOCAL_PATHS"
# 过滤空行和不存在的路径
VALID_PATHS=()
for p in "${PATH_ARRAY[@]}"; do
    [ -n "$p" ] && [ -e "$p" ] && VALID_PATHS+=("$p")
done

if [ ${#VALID_PATHS[@]} -eq 0 ]; then
    echo -e "${RED}错误: 没有有效的本地路径！${NC}"
    exit 1
fi

echo -e "\n${CYAN}========================================${NC}"
echo -e "归档名称: ${GREEN}${ARCHIVE_NAME}${NC}"
echo -e "格式:     ${GREEN}${FORMAT}${NC}"
echo -e "程度:     ${GREEN}${LEVEL}${NC}"
echo -e "路径数:   ${GREEN}${#VALID_PATHS[@]}${NC}"
echo -e "目标:     ${GREEN}${REMOTE_NAME}:${TARGET_DIR}/${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

echo -e "${YELLOW}⏳ 正在压缩...${NC}"

case "$FORMAT" in
    zip)
        OUTPUT_FILE="$TEMP_DIR/${ARCHIVE_NAME}.zip"
        case "$LEVEL" in
            "仅存储") ZIP_OPT="-0" ;;
            "极速")   ZIP_OPT="-1" ;;
            "快速")   ZIP_OPT="-3" ;;
            "标准")   ZIP_OPT="-6" ;;
            "最大")   ZIP_OPT="-9" ;;
            "极限")   ZIP_OPT="-9" ;;
        esac
        zip -r $ZIP_OPT "$OUTPUT_FILE" "${VALID_PATHS[@]}" -q
        ;;
    tar.gz)
        OUTPUT_FILE="$TEMP_DIR/${ARCHIVE_NAME}.tar.gz"
        case "$LEVEL" in
            "仅存储") OUTPUT_FILE="$TEMP_DIR/${ARCHIVE_NAME}.tar"; tar -cf "$OUTPUT_FILE" "${VALID_PATHS[@]}" ;;
            "极速")   GZIP="-1" tar -czf "$OUTPUT_FILE" "${VALID_PATHS[@]}" ;;
            "快速")   GZIP="-3" tar -czf "$OUTPUT_FILE" "${VALID_PATHS[@]}" ;;
            "标准")   GZIP="-6" tar -czf "$OUTPUT_FILE" "${VALID_PATHS[@]}" ;;
            "最大")   GZIP="-9" tar -czf "$OUTPUT_FILE" "${VALID_PATHS[@]}" ;;
            "极限")   GZIP="-9" tar -czf "$OUTPUT_FILE" "${VALID_PATHS[@]}" ;;
        esac
        ;;
    tar.xz)
        OUTPUT_FILE="$TEMP_DIR/${ARCHIVE_NAME}.tar.xz"
        case "$LEVEL" in
            "仅存储") OUTPUT_FILE="$TEMP_DIR/${ARCHIVE_NAME}.tar"; tar -cf "$OUTPUT_FILE" "${VALID_PATHS[@]}" ;;
            "极速")   XZ_OPT="-1" tar -cJf "$OUTPUT_FILE" "${VALID_PATHS[@]}" ;;
            "快速")   XZ_OPT="-3" tar -cJf "$OUTPUT_FILE" "${VALID_PATHS[@]}" ;;
            "标准")   XZ_OPT="-6" tar -cJf "$OUTPUT_FILE" "${VALID_PATHS[@]}" ;;
            "最大")   XZ_OPT="-9" tar -cJf "$OUTPUT_FILE" "${VALID_PATHS[@]}" ;;
            "极限")   XZ_OPT="-9 -e" tar -cJf "$OUTPUT_FILE" "${VALID_PATHS[@]}" ;;
        esac
        ;;
    7z)
        OUTPUT_FILE="$TEMP_DIR/${ARCHIVE_NAME}.7z"
        case "$LEVEL" in
            "仅存储") 7Z_OPT="-mx=0" ;;
            "极速")   7Z_OPT="-mx=1" ;;
            "快速")   7Z_OPT="-mx=3" ;;
            "标准")   7Z_OPT="-mx=5" ;;
            "最大")   7Z_OPT="-mx=7" ;;
            "极限")   7Z_OPT="-mx=9" ;;
        esac
        7z a $7Z_OPT "$OUTPUT_FILE" "${VALID_PATHS[@]}" > /dev/null 2>&1
        ;;
    "tar (仅打包,无压缩)")
        OUTPUT_FILE="$TEMP_DIR/${ARCHIVE_NAME}.tar"
        tar -cf "$OUTPUT_FILE" "${VALID_PATHS[@]}"
        ;;
esac

if [ ! -f "$OUTPUT_FILE" ]; then
    echo -e "${RED}❌ 压缩失败！${NC}"
    exit 1
fi

# 显示压缩结果
FILE_SIZE=$(du -h "$OUTPUT_FILE" | awk '{print $1}')
echo -e "${GREEN}✅ 压缩完成！大小: ${FILE_SIZE}${NC}"

# ==========================================
# 6. 上传到云端
# ==========================================
echo -e "\n${YELLOW}⏳ 正在上传到 ${REMOTE_NAME}:${TARGET_DIR}/ ...${NC}"
rclone copy "$OUTPUT_FILE" "${REMOTE_NAME}:${TARGET_DIR}/" --progress

if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}✅ 上传完成！${NC}"
    echo -e "文件: ${CYAN}${TARGET_DIR}/$(basename "$OUTPUT_FILE")${NC}"
else
    echo -e "\n${RED}❌ 上传失败！${NC}"
    exit 1
fi
