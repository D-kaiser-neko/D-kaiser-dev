#!/bin/bash
# ===========================================
# 菜单导航脚本 (fzf) - 修复空选项闪退 + 根目录退出/返回
# ===========================================
chmod +x ./*
set -euo pipefail

BASE="菜单"
if [ ! -d "$BASE" ]; then
    BASE="$(dirname "$0")/菜单"
    if [ ! -d "$BASE" ]; then
        echo "❌ 未找到“菜单”目录" >&2; exit 1
    fi
fi
cd "$BASE" || exit 1
BASE_DIR="$PWD"
cd - > /dev/null
current="$BASE_DIR"

while true; do
    [ -d "$current" ] || { echo "❌ 目录失效: $current" >&2; exit 1; }
    cd "$current" || exit 1

    # 获取子目录和脚本（排除空行）
    dirs=$(find . -maxdepth 1 -mindepth 1 -type d -printf '%f\n' 2>/dev/null | sort)
    scripts=$(find . -maxdepth 1 -type f \( -name "*.sh" -o -name "*.py" \) -printf '%f\n' 2>/dev/null | sort)

    # 构建菜单（适配 reverse 布局）
    menu=()
    menu+=("🔙 返回")

    # 添加脚本（仅当非空）
    if [ -n "$scripts" ]; then
        while IFS= read -r s; do
            [ -n "$s" ] && menu+=("$s")
        done < <(echo "$scripts" | sort -r)
    fi

    # 添加目录（仅当非空）
    if [ -n "$dirs" ]; then
        while IFS= read -r d; do
            [ -n "$d" ] && menu+=("$d")
        done < <(echo "$dirs" | sort -r)
    fi

    # 始终显示退出键（修复根目录无退出）
    menu+=("❌ 退出")

    # 两者都空时提示
    if [ -z "$dirs" ] && [ -z "$scripts" ]; then
        echo "⚠️ 该目录没有子目录或脚本文件"
        read -p "按回车返回..." -r
        [ "$current" != "$BASE_DIR" ] && current=$(dirname "$current") || { echo "再见！"; exit 0; }
        continue
    fi

    choice=$(printf '%s\n' "${menu[@]}" | fzf \
        --prompt="📂 ${current#$BASE_DIR}/ > " \
        --header="ENTER:进入/执行  |  ESC:返回" \
        --layout=reverse \
        --no-mouse)

    if [ -z "$choice" ]; then
        [ "$current" != "$BASE_DIR" ] && current=$(dirname "$current") || { echo "再见！"; exit 0; }
    elif [ "$choice" = "🔙 返回" ]; then
        # 修复：根目录按返回直接退出，不再 dirname 越界
        if [ "$current" = "$BASE_DIR" ]; then
            echo "再见！"; exit 0
        else
            current=$(dirname "$current")
        fi
    elif [ "$choice" = "❌ 退出" ]; then
        echo "再见！"; exit 0
    elif [[ "$choice" == *.sh ]] || [[ "$choice" == *.py ]]; then
        # 执行脚本
        clear
        echo -e "\033[1;32m▶ 执行: $choice\033[0m"
        echo "--------------------------------"
        if [[ "$choice" == *.sh ]]; then
            bash "$current/$choice"
        elif [[ "$choice" == *.py ]]; then
            if command -v python3 &>/dev/null; then
                python3 "$current/$choice"
            else
                python "$current/$choice"
            fi
        fi
        echo "--------------------------------"
        echo -e "\033[1;32m✅ 脚本执行完毕，按回车返回...\033[0m"
        read -r
    else
        # 进入子目录
        current="$current/$choice"
    fi
done
