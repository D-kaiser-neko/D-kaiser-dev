#!/data/data/com.termux/files/usr/bin/bash

# ====== 配置 ======
CAMERA_ID=1                              # 1=前置摄像头，0=后置
SAVE_DIR="/storage/emulated/0/termux"   # 照片保存目录
INTERVAL=6                               # DC间隔（秒），也是倒计时时长
# =================

mkdir -p "$SAVE_DIR"

echo "开始循环DC（前，间隔 ${INTERVAL} 秒）"
echo "文件保存至: $SAVE_DIR"
echo "按 Ctrl+C 停止"
echo "=============================="

while true; do
    FILENAME="$(date '+%m.%d-%H：%M：%S').jpg"
    FILEPATH="$SAVE_DIR/$FILENAME"

    echo "[$(date '+%H:%M:%S')] 正在启动DC → $FILENAME"

    # 后台执行DC
    termux-camera-photo -c "$CAMERA_ID" "$FILEPATH" &
    PID=$!

    # 动态倒计时（覆盖同一行）
    for ((i=INTERVAL; i>=1; i--)); do
        printf "\r倒计时: %d 秒 " "$i"
        sleep 1
    done
    echo ""   # 倒计时结束后换行

    # 等待DC结束
    wait $PID
    if [ $? -eq 0 ] && [ -f "$FILEPATH" ]; then
        echo ">DC成功 → $FILENAME"
    else
        echo ">DC失败，请检查 Termux:API权限"
    fi

    echo "----------------------------"
done