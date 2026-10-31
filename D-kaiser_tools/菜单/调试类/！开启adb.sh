#!/bin/bash
# 无线调试连接脚本（通过输出判断连接成功）
cd
CONFIG="D-kaiser_tools/dk配置.conf"

if [ ! -f "$CONFIG" ]; then
    echo "配置文件 $CONFIG 不存在"
    exit 1
fi

# 清理可能的 BOM 和 Windows 换行
clean_config=$(sed '1s/^\xEF\xBB\xBF//; s/\r$//' "$CONFIG")

# 提取 IP 和端口
target_ip=$(echo "$clean_config" | grep -E '^\s*局域网ip\s*=\s*"' | head -1 | sed 's/.*"\([^"]*\)".*/\1/')
connect_port=$(echo "$clean_config" | grep -E '^\s*无线调试连接端口\s*=\s*"' | head -1 | sed 's/.*"\([^"]*\)".*/\1/')

if [ -z "$target_ip" ] || [ -z "$connect_port" ]; then
    echo "错误：未从配置文件读取到有效的 IP 或端口"
    echo "请检查 $CONFIG 中是否包含如下格式内容："
    echo '局域网ip="192.168.0.104"'
    echo '无线调试连接端口="37967"'
    exit 1
fi

echo "配置读取成功：IP=$target_ip  端口=$connect_port"

ADDR="${target_ip}:${connect_port}"
echo "正在连接 $ADDR ..."

# 执行连接并捕获输出和退出码
result=$(adb connect "$ADDR" 2>&1)
exit_code=$?

# 通过输出内容判断是否真正成功（包含 "connected to" 即视为成功）
if [ $exit_code -eq 0 ] && echo "$result" | grep -qi "connected to"; then
    echo "连接成功！"
    echo "$result"
    echo "adb已开启，正在退出"
    exit
else
    echo "连接失败，详细信息："
    echo "$result"
    echo "执行 adb.sh"
    bash D-kaiser_tools/无线调试配对.sh
fi