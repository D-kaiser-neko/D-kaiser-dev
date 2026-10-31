#!/bin/bash
# ============================================
# 菜单导航脚本 (Termux) - 
#Changelog
# V1.1 清屏版，防刷屏
# ============================================
chmod +x ./*
# 查找“菜单”目录
BASE="菜单"
if [ ! -d "$BASE" ]; then
    BASE="$(dirname "$0")/菜单"
    if [ ! -d "$BASE" ]; then
        echo -e "\e[1;31m错误：未找到“菜单”目录\e[0m"
        exit 1
    fi
fi

cd "$BASE" || exit 1
BASE_DIR="$PWD"
cd - > /dev/null

# 目录栈，存绝对路径
stack=("$BASE_DIR")

while true; do
    # 每次循环清屏
    clear

    current="${stack[-1]}"
    if [ ! -d "$current" ]; then
        echo -e "\e[1;31m路径失效: $current\e[0m"
        exit 1
    fi
    cd "$current" || exit 1

    # 相对路径显示
    rel_path="${current#$BASE_DIR}"
    rel_path="${rel_path#/}"
    echo -e "\e[1;36m📍 当前: /菜单/${rel_path}\e[0m"

    # 收集子目录（按名称排序）
    subdirs=()
    if [ -d "$current" ]; then
        for d in "$current"/*/; do
            [ -d "$d" ] && subdirs+=("$(basename "$d")")
        done
    fi
    # 排序（可选）
    IFS=$'\n' subdirs=($(sort <<<"${subdirs[*]}"))
    unset IFS

    if [ ${#subdirs[@]} -gt 0 ]; then
        # ---------- 有子目录：显示导航菜单 ----------
        echo "--------------------------------"
        # [0] 上一级 （仅当不在根目录）
        if [ ${#stack[@]} -gt 1 ]; then
            echo -e " [\e[1;33m0\e[0m] 上一级"
        fi
        # 子目录列表，编号从1开始
        for i in "${!subdirs[@]}"; do
            name="${subdirs[i]}"
            display="${name#主}"   # 去掉"主"前缀美化
            echo -e " [\e[1;33m$((i+1))\e[0m] $display"
        done
        echo -e " [\e[1;33mx\e[0m] 退出"
        echo "--------------------------------"
        read -p "请选择: " choice

        case $choice in
            [xX]) 
                echo "再见！"
                exit 0
                ;;
            0)
                if [ ${#stack[@]} -gt 1 ]; then
                    # 弹出栈顶
                    unset 'stack[${#stack[@]}-1]'
                    # 重新索引（保证数组连续）
                    stack=("${stack[@]}")
                else
                    echo "已在根目录，无法返回。"
                    sleep 1
                fi
                ;;
            *)
                # 检查是否为有效数字
                if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le ${#subdirs[@]} ]; then
                    chosen="${subdirs[$((choice-1))]}"
                    # 拼接新路径，确保无多余斜杠
                    new_path="$current/$chosen"
                    # 推入栈
                    stack+=("$new_path")
                else
                    echo -e "\e[1;31m无效选择，重新输入。\e[0m"
                    sleep 1
                fi
                ;;
        esac
    else
        # ---------- 最内层：处理脚本 ----------
        scripts=()
        for f in "$current"/*.sh "$current"/*.py; do
            [ -f "$f" ] && scripts+=("$(basename "$f")")
        done

        if [ ${#scripts[@]} -eq 0 ]; then
            echo -e "\e[1;33m该目录下没有脚本文件。\e[0m"
            read -p "按回车返回上一级..." -r
            if [ ${#stack[@]} -gt 1 ]; then
                unset 'stack[${#stack[@]}-1]'
                stack=("${stack[@]}")
            else
                echo "已在根目录，退出。"
                exit 0
            fi
        elif [ ${#scripts[@]} -eq 1 ]; then
            # 只有一个脚本，自动执行
            script="${scripts[0]}"
            echo -e "\e[1;32m▶ 自动执行脚本: $script\e[0m"
            echo "--------------------------------"
            if [[ "$script" == *.sh ]]; then
                bash "$current/$script"
            elif [[ "$script" == *.py ]]; then
                if command -v python3 &>/dev/null; then
                    python3 "$current/$script"
                elif command -v python &>/dev/null; then
                    python "$current/$script"
                else
                    echo -e "\e[1;31m未找到 Python，请先安装。\e[0m"
                fi
            fi
            echo "--------------------------------"
            echo -e "\e[1;32m脚本执行完毕。\e[0m"
            # 清空输入缓冲区，再等待回车
            read -t 0.1 -n 10000 discard 2>/dev/null
            read -p "按回车返回上一级..." -r
            if [ ${#stack[@]} -gt 1 ]; then
                unset 'stack[${#stack[@]}-1]'
                stack=("${stack[@]}")
            fi
        else
            # 多个脚本，显示选择菜单
            echo "该目录下有多个脚本："
            echo -e " [\e[1;33m0\e[0m] 返回上一级"
            for i in "${!scripts[@]}"; do
                echo -e " [\e[1;33m$((i+1))\e[0m] ${scripts[i]}"
            done
            read -p "请选择要执行的脚本: " sc
            if [[ "$sc" =~ ^[0-9]+$ ]] && [ "$sc" -ge 1 ] && [ "$sc" -le ${#scripts[@]} ]; then
                script="${scripts[$((sc-1))]}"
                echo -e "\e[1;32m▶ 执行脚本: $script\e[0m"
                if [[ "$script" == *.sh ]]; then
                    bash "$current/$script"
                elif [[ "$script" == *.py ]]; then
                    if command -v python3 &>/dev/null; then
                        python3 "$current/$script"
                    elif command -v python &>/dev/null; then
                        python "$current/$script"
                    else
                        echo -e "\e[1;31m未找到 Python。\e[0m"
                    fi
                fi
                echo "--------------------------------"
                echo -e "\e[1;32m脚本执行完毕。\e[0m"
                read -t 0.1 -n 10000 discard 2>/dev/null
                read -p "按回车返回上一级..." -r
                if [ ${#stack[@]} -gt 1 ]; then
                    unset 'stack[${#stack[@]}-1]'
                    stack=("${stack[@]}")
                fi
            elif [ "$sc" = "0" ]; then
                if [ ${#stack[@]} -gt 1 ]; then
                    unset 'stack[${#stack[@]}-1]'
                    stack=("${stack[@]}")
                fi
            else
                echo -e "\e[1;31m无效选择，返回上一级。\e[0m"
                sleep 1
                if [ ${#stack[@]} -gt 1 ]; then
                    unset 'stack[${#stack[@]}-1]'
                    stack=("${stack[@]}")
                fi
            fi
        fi
    fi
done