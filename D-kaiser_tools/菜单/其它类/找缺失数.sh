#!/usr/bin/env bash
# 查找缺失编号文件，并可生成缺失链接 (Bash 增强版)

fmt=""
start=""
end=""
link_arg=""

# 1. 智能参数解析
if [ "$#" -eq 0 ]; then
    read -p "[1]输入查找格式(如 img1-256.webp 或 img*.webp): " fmt
elif [ "$#" -eq 1 ]; then
    fmt=$1
elif [ "$#" -eq 2 ]; then
    fmt=$1
    # 如果第一个参数能解析出范围(如img1-256.webp)，第二个参数视为链接
    if [[ "$fmt" =~ ^([^0-9]*)([0-9]+)-([0-9]+)(.*)$ ]]; then
        link_arg=$2
    else
        echo "错误: 参数不足。如果是 img*.webp，请提供起始和终止值；如果是 img1-256.webp，第二个参数将被视为链接。" >&2
        exit 1
    fi
elif [ "$#" -ge 3 ]; then
    fmt=$1
    start=$2
    end=$3
    link_arg=${4-}
fi

if [ -z "$fmt" ]; then
    echo "错误: 格式不能为空" >&2
    exit 1
fi

# 2. 格式解析 (自动识别 img1-256.webp 或 img*.webp)
if [[ "$fmt" =~ ^([^0-9]*)([0-9]+)-([0-9]+)(.*)$ ]]; then
    prefix="${BASH_REMATCH[1]}"
    start="${BASH_REMATCH[2]}"
    end="${BASH_REMATCH[3]}"
    suffix="${BASH_REMATCH[4]}"
    fmt="${prefix}*${suffix}"
    echo "提示: 已自动解析 -> 前缀:$prefix, 起始:$start, 终止:$end, 后缀:$suffix" >&2
else
    if [[ "$fmt" == */* ]]; then
        echo "错误: 格式只写文件名模式，不要带目录" >&2
        exit 1
    fi
    if [[ "$fmt" != *'*'* ]]; then
        echo "错误: 格式必须包含一个 *，例如 img*.webp，或者使用 img1-256.webp 格式" >&2
        exit 1
    fi
    
    local_rest="${fmt#*\*}"
    if [[ "$local_rest" == *'*'* ]]; then
        echo "错误: 只支持一个 *" >&2
        exit 1
    fi

    if [ -z "$start" ]; then read -p "[2]输入起始值: " start; fi
    if [ -z "$end" ]; then read -p "[3]输入终止值: " end; fi

    prefix="${fmt%%\**}"
    suffix="${fmt#*\*}"
fi

# 3. 校验数字并去除前导零 (利用 bash 的 10# 强制十进制解析)
if ! [[ "$start" =~ ^[0-9]+$ ]]; then echo "错误: 起始值必须是数字" >&2; exit 1; fi
if ! [[ "$end" =~ ^[0-9]+$ ]]; then echo "错误: 终止值必须是数字" >&2; exit 1; fi

start=$((10#$start))
end=$((10#$end))

if [ "$start" -gt "$end" ]; then
    tmp=$start; start=$end; end=$tmp
    echo "提示: 起始值大于终止值，已自动交换为 $start - $end" >&2
fi

# 4. 查找已存在的文件
have=""
while IFS= read -r -d '' file; do
    name="${file##*/}"
    num="${name#"$prefix"}"
    num="${num%"$suffix"}"

    if [[ "$num" =~ ^[0-9]+$ ]]; then
        num=$((10#$num))
        have="$have $num "
    fi
done < <(find . -type f -name "$fmt" -print0 2>/dev/null)

if [ -z "$have" ]; then
    echo "提示: 未找到匹配 $fmt 的文件，可能全部缺失" >&2
fi

# 5. 计算缺失项
missing=0
missing_list=""
for (( i=start; i<=end; i++ )); do
    if [[ "$have" != *" $i "* ]]; then
        echo "缺少:${prefix}${i}${suffix}" >&2
        missing_list+="${prefix}${i}${suffix}"$'\n'
        ((missing++))
    fi
done

echo "查找范围: $start - $end" >&2
echo "共缺少: $missing" >&2

if [ "$missing" -eq 0 ]; then
    echo "没有缺失文件" >&2
    exit 0
fi

# 6. 链接生成逻辑
if [ -n "$link_arg" ]; then
    if [[ "$link_arg" =~ ^[nN]([oO])?$ ]]; then exit 0; fi
    base=$link_arg
else
    read -p "是否改为链接(Y/n): " ans
    ans=${ans:-y}
    if [[ "$ans" =~ ^[nN] ]]; then exit 0; fi

    read -p "输入基本链接: " base
    if [ -z "$base" ]; then echo "错误: 链接为空，已取消" >&2; exit 1; fi
fi

# 7. 规范链接末尾斜杠 (自动清理多余的 / 并补全)
while [[ "$base" == */ && "$base" != *:// ]]; do
    base="${base%/}"
done
if [[ "$base" != */ ]]; then
    base="$base/"
fi

# 8. 输出最终链接
while IFS= read -r f; do
    [ -n "$f" ] && echo "${base}${f}"
done <<< "$missing_list"