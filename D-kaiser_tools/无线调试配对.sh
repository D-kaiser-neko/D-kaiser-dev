#!/data/data/com.termux/files/usr/bin/bash
# D-Kaiser 无线调试工具（nmap 极速版）
# 配置文件：~/D-kaiser_tools/dk配置.conf

# ========== 安装 nmap ==========
# pkg install nmap

# ========== 第 0 步：自动获取本机局域网 IP ==========

get_local_ip() {
    local ip=""

    if command -v ip &> /dev/null; then
        ip=$(ip route get 1.1.1.1 2>/dev/null | grep -oE 'src [0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' | awk '{print $2}')
    fi

    if [ -z "$ip" ] && command -v ifconfig &> /dev/null; then
        ip=$(ifconfig 2>/dev/null | grep -Eo 'inet [0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' | grep -v '127.0.0.1' | awk '{print $2}' | head -1)
    fi

    if [ -z "$ip" ] && command -v hostname &> /dev/null; then
        ip=$(hostname -I 2>/dev/null | awk '{print $1}')
    fi

    if [ -z "$ip" ] && command -v ip &> /dev/null; then
        ip=$(ip addr show wlan0 2>/dev/null | grep -oE 'inet [0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' | awk '{print $2}' | head -1)
    fi

    echo "$ip"
}

CONF_FILE="$HOME/D-kaiser_tools/dk配置.conf"

if [ ! -f "$CONF_FILE" ]; then
    echo "错误：配置文件不存在：$CONF_FILE"
    exit 1
fi

# 获取并更新本机 IP
auto_ip=$(get_local_ip)
if [ -n "$auto_ip" ]; then
    echo "检测到本机局域网 IP：$auto_ip"
    sed -i 's/^\s*局域网ip\s*=\s*".*"/局域网ip="'"$auto_ip"'"/' "$CONF_FILE"
    if [ $? -eq 0 ]; then
        echo "已自动更新配置文件中的局域网ip"
    else
        echo "警告：自动更新局域网ip失败"
    fi
else
    echo "警告：未能自动获取本机局域网 IP，将使用配置文件中的值"
fi

# 检查 adb
if ! command -v adb &> /dev/null; then
    echo "错误：未找到 adb，请先安装 android-tools"
    echo "运行：pkg install android-tools"
    exit 1
fi

# 读取配置
target_ip=$(grep -E '^\s*局域网ip\s*=\s*"' "$CONF_FILE" | head -1 | sed 's/.*"\([^"]*\)".*/\1/')
if [ -z "$target_ip" ]; then
    echo "错误：配置文件中未找到 '局域网ip' 或格式不正确"
    exit 1
fi

connect_port=$(grep -E '^\s*无线调试连接端口\s*=\s*"' "$CONF_FILE" | head -1 | sed 's/.*"\([^"]*\)".*/\1/')

echo ""
echo "============================================"
echo "  D-Kaiser 无线调试工具（nmap 极速版）"
echo "============================================"
echo "目标设备 IP：$target_ip"
if [ -n "$connect_port" ]; then
    echo "配置中的连接端口：$connect_port"
fi
echo ""

# ========== 快速连接 ==========

if [ -n "$connect_port" ]; then
    echo "【快速连接】尝试使用配置中的连接端口：$connect_port"
    connect_addr="${target_ip}:${connect_port}"
    result=$(adb connect "$connect_addr" 2>&1)
    if echo "$result" | grep -qi "connected to"; then
        echo "连接成功！"
        echo ""
        echo "当前连接设备："
        adb devices -l
        exit 0
    else
        echo "快速连接失败：$result"
        echo "开始完整自动发现流程..."
        echo ""
    fi
fi

# ========== 工具函数 ==========

discover_via_mdns() {
    local service_type="$1"
    local found_port=""

    if command -v avahi-browse &> /dev/null; then
        found_port=$(timeout 5 avahi-browse -r "$service_type" 2>/dev/null | grep -oE 'port = \[[0-9]+\]' | grep -oE '[0-9]+' | head -1)
        if [ -n "$found_port" ]; then
            echo "$found_port"
            return 0
        fi
    fi

    if command -v dns-sd &> /dev/null; then
        found_port=$(timeout 5 dns-sd -B "$service_type" 2>/dev/null | grep -oE '[0-9]+' | head -1)
        if [ -n "$found_port" ]; then
            echo "$found_port"
            return 0
        fi
    fi

    return 1
}

# ========== 核心优化：nmap 极速扫描 ==========
# 原理：
#   -sT      TCP 连接扫描（Termux 无 root，不能用 -sS SYN 扫描）
#   -p       指定端口范围
#   --open   只显示开放端口
#   -T5      最激进时序（5 级），每秒发更多包
#   --max-retries 0   不重试，一次失败直接跳过
#   --max-rtt-timeout 200ms   200ms 没响应就放弃
#   --min-rate 1000   每秒至少发 1000 个包
#   -oG -    输出 grepable 格式，方便解析
scan_port_nmap() {
    local ip="$1"
    local start_port="$2"
    local end_port="$3"
    local exclude_port="${4:-}"

    if ! command -v nmap &> /dev/null; then
        echo "" >&2
        echo "错误：未找到 nmap，请先安装" >&2
        echo "运行：pkg install nmap" >&2
        return 1
    fi

    echo "使用 nmap 极速扫描 ${start_port}-${end_port}..." >&2

    # 核心命令，扫描 30000-50000 约 5-10 秒
    local nmap_output
    nmap_output=$(nmap -sT \
        -p"${start_port}-${end_port}" \
        --open \
        -T5 \
        --max-retries 0 \
        --max-rtt-timeout 200ms \
        --min-rate 1000 \
        -oG - \
        "$ip" 2>/dev/null)

    # 解析 grepable 输出，提取开放端口号
    # 格式: Host: IP ()    Ports: 40187/open/tcp/////
    local found_port
    found_port=$(echo "$nmap_output" | grep -oE "Ports: [0-9]+/open" | awk -F'[ /]' '{print $2}' | head -1)

    # 如果要求排除某个端口
    if [ -n "$exclude_port" ] && [ "$found_port" = "$exclude_port" ]; then
        found_port=$(echo "$nmap_output" | grep -oE "Ports: [0-9]+/open" | awk -F'[ /]' '{print $2}' | grep -v "^${exclude_port}$" | head -1)
    fi

    if [ -n "$found_port" ]; then
        echo "$found_port"
        return 0
    fi

    return 1
}

# 回退扫描（nmap 不可用时）
scan_port_fallback() {
    local ip="$1"
    local start_port="$2"
    local end_port="$3"
    local exclude_port="${4:-}"
    local batch_size=30
    local found_port=""

    local tmp_dir="$HOME/.cache"
    local tmp_file="$tmp_dir/.dk_scan_results_$$"
    mkdir -p "$tmp_dir"
    rm -f "$tmp_file"

    local probe_cmd=""
    if command -v nc &> /dev/null; then
        probe_cmd="nc"
    elif [ -e /dev/tcp/localhost/1 ] 2>/dev/null; then
        probe_cmd="bash_tcp"
    else
        probe_cmd="none"
    fi

    local current=$start_port
    while [ $current -le $end_port ]; do
        local batch_end=$((current + batch_size - 1))
        [ $batch_end -gt $end_port ] && batch_end=$end_port

        printf "\r扫描进度：%d/%d (%d%%)" "$current" "$end_port" $((current * 100 / end_port)) >&2

        for port in $(seq $current $batch_end); do
            [ "$port" = "$exclude_port" ] && continue
            if [ "$probe_cmd" = "nc" ]; then
                ( nc -z -w1 "$ip" "$port" 2>/dev/null && echo "$port" >> "$tmp_file" ) &
            elif [ "$probe_cmd" = "bash_tcp" ]; then
                ( timeout 1 bash -c "echo >/dev/tcp/$ip/$port" 2>/dev/null && echo "$port" >> "$tmp_file" ) &
            else
                ( timeout 1 adb connect "${ip}:${port}" >/dev/null 2>&1 && echo "$port" >> "$tmp_file" ) &
            fi
        done
        wait

        if [ -f "$tmp_file" ]; then
            found_port=$(sort -u "$tmp_file" | head -1)
            if [ -n "$found_port" ]; then
                printf "\r\033[K" >&2
                rm -f "$tmp_file"
                echo "$found_port"
                return 0
            fi
        fi

        current=$((batch_end + 1))
    done

    printf "\r\033[K" >&2
    rm -f "$tmp_file"
    return 1
}

# 统一扫描入口
scan_port() {
    if command -v nmap &> /dev/null; then
        scan_port_nmap "$@"
    else
        scan_port_fallback "$@"
    fi
}

# ========== 第 1 步：获取连接端口 ==========

echo "【第 1 步】获取连接端口（adb connect 用的端口）"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "提示：保持无线调试主界面打开"
echo "      如果有配对弹窗，请先点击【取消】关闭它！"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -n "请输入连接端口（直接回车自动扫描）："
read user_connect_port

if [ -n "$user_connect_port" ]; then
    if echo "$user_connect_port" | grep -qE '^[0-9]+$'; then
        new_connect_port="$user_connect_port"
        echo "使用手动输入的连接端口：$new_connect_port"
    else
        echo "错误：端口必须为数字"
        exit 1
    fi
else
    echo "开始自动扫描连接端口..."

    # 先尝试 mDNS
    new_connect_port=$(discover_via_mdns "_adb-tls-connect._tcp" 2>/dev/null)
    if [ -n "$new_connect_port" ]; then
        echo "通过 mDNS 发现连接端口：$new_connect_port"
    else
        # 验证配置中的旧端口
        if [ -n "$connect_port" ]; then
            echo "配置中有旧连接端口 $connect_port，验证中..."
            if nc -z -w2 "$target_ip" "$connect_port" 2>/dev/null; then
                echo "旧连接端口可用：$connect_port"
                new_connect_port="$connect_port"
            else
                echo "旧连接端口不可用，重新扫描..."
            fi
        fi

        # nmap 极速扫描 30000-50000
        if [ -z "$new_connect_port" ]; then
            new_connect_port=$(scan_port "$target_ip" 30000 50000)
            if [ -n "$new_connect_port" ]; then
                echo "扫描发现连接端口：$new_connect_port"
            fi
        fi
    fi
fi

if [ -z "$new_connect_port" ]; then
    echo "错误：未能获取连接端口"
    exit 1
fi

echo ""
echo "连接端口：$new_connect_port"

# 写入配置
sed -i 's/^\s*无线调试连接端口\s*=\s*".*"/无线调试连接端口="'"$new_connect_port"'"/' "$CONF_FILE"
if [ $? -ne 0 ]; then
    echo "警告：保存连接端口到配置失败"
else
    echo "已保存连接端口到配置"
fi

# ========== 第 2 步：获取配对端口 ==========

echo ""
echo "【第 2 步】获取配对端口（adb pair 用的端口）"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "提示：请点击【使用配对码配对设备】，保持弹窗打开"
echo "      但不要输入配对码，等脚本扫描完成后再输入"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -n "请输入配对端口（直接回车自动扫描）："
read user_pair_port

if [ -n "$user_pair_port" ]; then
    if echo "$user_pair_port" | grep -qE '^[0-9]+$'; then
        pair_port="$user_pair_port"
        echo "使用手动输入的配对端口：$pair_port"
    else
        echo "错误：端口必须为数字"
        exit 1
    fi
else
    echo "开始自动扫描配对端口..."

    # 先尝试 mDNS
    pair_port=$(discover_via_mdns "_adb-tls-pairing._tcp" 2>/dev/null)
    if [ -n "$pair_port" ]; then
        echo "通过 mDNS 发现配对端口：$pair_port"
    else
        # nmap 极速扫描（排除连接端口）
        pair_port=$(scan_port "$target_ip" 30000 50000 "$new_connect_port")
        if [ -n "$pair_port" ]; then
            echo "扫描发现配对端口：$pair_port"
        fi
    fi
fi

if [ -z "$pair_port" ]; then
    echo "错误：未能获取配对端口"
    exit 1
fi

echo ""
echo "配对端口：$pair_port（仅本次使用，不保存到配置）"

# ========== 第 3 步：输入配对码 ==========

echo ""
echo -n "请输入 6 位配对码："
read pair_code

# 去除首尾空格
pair_code=$(echo "$pair_code" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

case "$pair_code" in
    [0-9][0-9][0-9][0-9][0-9][0-9]) ;;
    *)
        echo "错误：配对码必须为 6 位数字，当前输入：'$pair_code'"
        exit 1
        ;;
esac

# ========== 第 4 步：执行配对 ==========

pair_addr="${target_ip}:${pair_port}"
echo ""
echo "正在配对 $pair_addr ..."
result=$(echo "$pair_code" | adb pair "$pair_addr" 2>&1)
exit_code=$?

if [ $exit_code -ne 0 ] || ! echo "$result" | grep -qi "successfully\|paired"; then
    echo ""
    echo "配对失败，请检查："
    echo "  1. 配对码是否正确（6位数字，注意时效性）"
    echo "  2. 配对端口是否与弹窗显示的一致"
    echo "  3. 设备是否在同一 Wi-Fi 网络"
    echo "  4. 配对弹窗是否保持打开"
    echo ""
    echo "错误输出："
    echo "$result"
    exit 1
fi

echo "配对成功！"

# ========== 第 5 步：用连接端口执行连接 ==========

connect_addr="${target_ip}:${new_connect_port}"
echo ""
echo "正在连接 ${connect_addr} ..."
adb connect "$connect_addr"

# ========== 第 6 步：可选固定端口 ==========

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "【可选】是否固定 adb 端口到 5555？"
echo "  固定后下次无需扫描，直接用 5555 连接"
echo "  运行：adb tcpip 5555"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -n "输入 y 固定端口，直接回车跳过："
read fix_port

if [ "$fix_port" = "y" ] || [ "$fix_port" = "Y" ]; then
    echo "正在将 adbd 固定到 5555 端口..."
    adb tcpip 5555
    if [ $? -eq 0 ]; then
        sed -i 's/^\s*无线调试连接端口\s*=\s*".*"/无线调试连接端口="5555"/' "$CONF_FILE"
        echo "已固定端口到 5555，并更新配置"
        echo "下次可直接用：adb connect ${target_ip}:5555"
    else
        echo "固定端口失败"
    fi
fi

# 显示连接状态
echo ""
echo "当前连接设备："
adb devices -l
