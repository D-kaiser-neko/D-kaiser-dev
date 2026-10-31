#!/data/data/com.termux/files/usr/bin/bash
# 生成停止应用命令列表
# 依赖：aapt (pkg install aapt)

APK_DIR="/storage/emulated/0/termux"
OUT_FILE="/storage/emulated/0/termux/packages.txt"

mkdir -p "$(dirname "$OUT_FILE")"

if ! command -v aapt &>/dev/null; then
    echo "错误：未找到 aapt，请先执行 pkg install aapt" >&2
    exit 1
fi

# 统计 APK 总数
total=$(find "$APK_DIR" -maxdepth 1 -name "*.apk" -type f 2>/dev/null | wc -l)
if [ "$total" -eq 0 ]; then
    echo "警告：在 $APK_DIR 下未找到任何 .apk 文件" >&2
    exit 1
fi

echo "共找到 $total 个 APK 文件" >&2

> "$OUT_FILE"
count=0

for apk in "$APK_DIR"/*.apk; do
    [ -e "$apk" ] || continue
    ((count++))
    apk_name=$(basename "$apk")

    # 提取包名
    pkg=$(aapt dump badging "$apk" 2>/dev/null | grep "^package: name=" | head -1 | sed "s/^package: name='\([^']*\)'.*/\1/")
    if [ -z "$pkg" ]; then
        echo "[$count/$total] $apk_name 失败：无法提取包名" >&2
        continue
    fi

    # 提取应用名称
    app_label=$(aapt dump badging "$apk" 2>/dev/null | grep "^application-label:" | head -1 | sed "s/^application-label://")
    if [ -z "$app_label" ]; then
        app_label=$(aapt dump badging "$apk" 2>/dev/null | grep "^application: label=" | head -1 | sed "s/^application: label='\([^']*\)'.*/\1/")
    fi
    [ -z "$app_label" ] && app_label="UNKNOWN"

    # 写入结果文件：应用名称前加 #，下一行为停止命令，组间空行
    echo "#$app_label" >> "$OUT_FILE"
    echo "adb shell am force-stop $pkg" >> "$OUT_FILE"
    echo "" >> "$OUT_FILE"

    # 终端日志：显示处理进度
    echo "[$count/$total] $apk_name -> $app_label ($pkg)" >&2
done

echo "完成。结果已写入：$OUT_FILE" >&2