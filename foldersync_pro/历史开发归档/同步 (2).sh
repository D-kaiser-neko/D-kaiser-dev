#!/data/data/com.termux/files/usr/bin/bash

# ==========================================
# Termux FolderSync Pro (TUI Edition) v4.0
# 修复路径展开 / 新增配置管理编辑
# 依赖: rclone, fzf, jq
# ==========================================

CONFIG_DIR="$HOME/.foldersync_pro/plans"
mkdir -p "$CONFIG_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

show_header() {
    clear
    echo -e "${CYAN}======================================${NC}"
    echo -e "${CYAN}      Termux FolderSync Pro TUI       ${NC}"
    echo -e "${CYAN}======================================${NC}"
    echo ""
}

check_deps() {
    for cmd in rclone fzf jq; do
        if ! command -v $cmd &> /dev/null; then
            echo -e "${RED}错误: 未安装 $cmd，请先运行 pkg install $cmd${NC}"
            exit 1
        fi
    done
}

# 【修复】路径展开函数：将 ~ 和 $HOME 替换为真实路径
expand_path() {
    local p="$1"
    p="${p/#\~/$HOME}"
    p="${p/#\$HOME/$HOME}"
    echo "$p"
}

# ==========================================
# 1. 配置管理 - 创建
# ==========================================
create_plan() {
    show_header
    echo -e "${YELLOW}--- 创建新的同步/下载计划 ---${NC}"
    read -p "计划名称 (例如: 相册备份): " plan_name
    plan_file="$CONFIG_DIR/$(echo $plan_name | tr ' ' '_').json"

    if [ -f "$plan_file" ]; then
        echo -e "${RED}错误: 该计划已存在！${NC}"
        read -p "按回车返回..."
        return
    fi

    read -p "本地路径 (例如: $HOME/storage/shared/DCIM): " local_path
    local_path=$(expand_path "$local_path")

    echo -e "\n${YELLOW}可用的 Rclone 远程端:${NC}"
    rclone listremotes
    read -p "远程端名称 (不需要冒号): " remote_name
    read -p "远程目录路径 (例如: /backup/phone): " remote_path

    jq -n \
        --arg name "$plan_name" \
        --arg local "$local_path" \
        --arg remote "$remote_name" \
        --arg rpath "$remote_path" \
        '{name: $name, local_path: $local, remote_name: $remote, remote_path: $rpath}' > "$plan_file"

    echo -e "${GREEN}计划 '$plan_name' 创建成功！${NC}"
    echo -e "本地路径已解析为: ${CYAN}$local_path${NC}"
    read -p "按回车返回..."
}

# ==========================================
# 2. 配置管理 - 编辑/删除
# ==========================================
manage_plans() {
    show_header
    echo -e "${YELLOW}--- 管理/编辑已有配置 ---${NC}"
    local plan_file=$(select_plan)
    [ -z "$plan_file" ] && return

    local name=$(jq -r '.name' "$plan_file")
    local local_path=$(jq -r '.local_path' "$plan_file")
    local remote_name=$(jq -r '.remote_name' "$plan_file")
    local remote_path=$(jq -r '.remote_path' "$plan_file")

    echo -e "\n${CYAN}当前配置: $name${NC}"
    echo -e "本地路径: ${GREEN}$local_path${NC}"
    echo -e "远程端:   ${GREEN}$remote_name${NC}"
    echo -e "远程路径: ${GREEN}$remote_path${NC}"

    echo -e "\n选择操作:"
    echo "1) 修改本地路径"
    echo "2) 修改远程端"
    echo "3) 修改远程路径"
    echo "4) 删除此配置"
    echo "5) 取消"
    read -p "选择 [1-5]: " action

    case $action in
        1)
            read -p "新本地路径: " new_val
            new_val=$(expand_path "$new_val")
            jq --arg v "$new_val" '.local_path = $v' "$plan_file" > "${plan_file}.tmp" && mv "${plan_file}.tmp" "$plan_file"
            echo -e "${GREEN}已更新为: $new_val${NC}"
            ;;
        2)
            echo -e "\n${YELLOW}可用的 Rclone 远程端:${NC}"
            rclone listremotes
            read -p "新远程端名称: " new_val
            jq --arg v "$new_val" '.remote_name = $v' "$plan_file" > "${plan_file}.tmp" && mv "${plan_file}.tmp" "$plan_file"
            echo -e "${GREEN}已更新为: $new_val${NC}"
            ;;
        3)
            read -p "新远程路径: " new_val
            jq --arg v "$new_val" '.remote_path = $v' "$plan_file" > "${plan_file}.tmp" && mv "${plan_file}.tmp" "$plan_file"
            echo -e "${GREEN}已更新为: $new_val${NC}"
            ;;
        4)
            read -p "确定要删除配置 '$name' 吗？(y/n): " confirm
            if [ "$confirm" == "y" ]; then
                rm -f "$plan_file"
                echo -e "${GREEN}已删除！${NC}"
            fi
            ;;
        *)
            echo "已取消。"
            ;;
    esac
    read -p "按回车返回..."
}

select_plan() {
    local selected_file
    selected_file=$(ls -1 "$CONFIG_DIR"/*.json 2>/dev/null | fzf \
        --border --reverse \
        --prompt="选择计划 (ESC退出): " \
        --preview 'jq -r "\"\n计划: \(.name)\n本地: \(.local_path)\n云端: \(.remote_name):\(.remote_path)\n\"" {}' \
        --preview-window=up:40%:wrap)

    if [ -z "$selected_file" ]; then
        return 1
    fi
    echo "$selected_file"
}

# ==========================================
# 3. 同步/下载执行
# ==========================================
run_sync() {
    show_header
    echo -e "${YELLOW}--- 执行同步/下载任务 ---${NC}"
    local plan_file=$(select_plan)
    [ -z "$plan_file" ] && return

    local name=$(jq -r '.name' "$plan_file")
    local local_path=$(jq -r '.local_path' "$plan_file")
    local remote_name=$(jq -r '.remote_name' "$plan_file")
    local remote_path=$(jq -r '.remote_path' "$plan_file")
    local remote_full="${remote_name}:${remote_path}"

    # 【修复】执行前再次确保路径展开
    local_path=$(expand_path "$local_path")

    echo -e "\n${CYAN}计划: $name${NC}"
    echo -e "本地: ${GREEN}$local_path${NC}"
    echo -e "云端: ${GREEN}$remote_full${NC}"

    # 【修复】检查本地路径是否存在
    if [ ! -d "$local_path" ]; then
        echo -e "\n${RED}错误: 本地目录不存在: $local_path${NC}"
        read -p "按回车返回..."
        return
    fi

    echo -e "\n选择传输方向:"
    echo "1) 上传 (本地 -> 云端)"
    echo "2) 下载 (云端 -> 本地)"
    read -p "选择 [1/2]: " dir_choice

    local direction=""
    case $dir_choice in
        1) direction="upload" ;;
        2) direction="download" ;;
        *) direction="upload" ;;
    esac

    echo -e "\n选择传输模式:"
    echo "1) 增量复制 (Copy): 仅传输新/修改文件"
    echo "2) 镜像同步 (Sync): 完全一致，会删除多余文件"
    read -p "选择 [1/2]: " mode

    local opts="--transfers 16 --checkers 32 --multi-thread-streams 8 --progress"

    local rclone_cmd=""
    if [ "$direction" == "upload" ]; then
        if [ "$mode" == "2" ]; then
            rclone_cmd="rclone sync '$local_path' '$remote_full' $opts"
        else
            rclone_cmd="rclone copy '$local_path' '$remote_full' $opts"
        fi
    elif [ "$direction" == "download" ]; then
        # 下载时自动创建本地目录
        mkdir -p "$local_path"
        if [ "$mode" == "2" ]; then
            rclone_cmd="rclone sync '$remote_full' '$local_path' $opts"
        else
            rclone_cmd="rclone copy '$remote_full' '$local_path' $opts"
        fi
    fi

    echo -e "\n${GREEN}开始执行... (按 Ctrl+C 可中断)${NC}"
    eval "$rclone_cmd"

    echo -e "\n${GREEN}✅ 任务完成！${NC}"
    read -p "按回车返回主菜单..."
}

# ==========================================
# 4. 云端文件管理器
# ==========================================
cloud_browser() {
    show_header
    echo -e "${YELLOW}--- 云端文件管理器 ---${NC}"
    local plan_file=$(select_plan)
    [ -z "$plan_file" ] && return

    local remote_name=$(jq -r '.remote_name' "$plan_file")
    local current_path=$(jq -r '.remote_path' "$plan_file")

    while true; do
        clear
        echo -e "${CYAN}当前云端路径:${NC} ${YELLOW}${remote_name}:${current_path}${NC}"
        echo "------------------------------------------------"

        local items=$(rclone lsjson "${remote_name}:${current_path}" 2>/dev/null | jq -r '
            sort_by(.IsDir) | reverse |
            .[] |
            if .IsDir then "[DIR] " + .Name
            else "[FILE] " + .Name
            end')

        local menu_items="[..] 返回上一级
$items"

        local selection
        selection=$(echo "$menu_items" | fzf \
            --border --reverse \
            --prompt="浏览云端 (ESC退出): " \
            --header="方向键选择, Enter操作")

        if [ -z "$selection" ]; then
            break
        fi

        if [[ "$selection" == "[..] 返回上一级" ]]; then
            if [ "$current_path" != "/" ] && [ "$current_path" != "." ]; then
                current_path=$(dirname "$current_path")
                [ "$current_path" == "." ] && current_path="/"
            fi
            continue
        fi

        local item_type=$(echo "$selection" | awk '{print $1}')
        local item_name=$(echo "$selection" | cut -d' ' -f2-)
        local target_path="${current_path}/${item_name}"
        [ "$current_path" == "/" ] && target_path="/${item_name}"

        if [[ "$item_type" == "[DIR]" ]]; then
            local dir_action
            dir_action=$(echo -e "进入该文件夹\n下载整个文件夹到本地\n删除该文件夹(包含子文件)\n取消" | fzf --border --prompt="操作: ")
            case "$dir_action" in
                "进入该文件夹")
                    current_path="$target_path"
                    ;;
                "下载整个文件夹到本地")
                    echo -e "${GREEN}正在下载...${NC}"
                    rclone copy "${remote_name}:${target_path}" "./${item_name}" --progress
                    echo -e "${GREEN}下载完成！保存在 ./${item_name}${NC}"
                    read -p "按回车继续..."
                    ;;
                "删除该文件夹(包含子文件)")
                    read -p "确定要删除 $item_name 吗？(y/n): " confirm
                    if [ "$confirm" == "y" ]; then
                        rclone purge "${remote_name}:${target_path}"
                        echo "已删除！"
                        sleep 1
                    fi
                    ;;
            esac
        else
            local action
            action=$(echo -e "下载此文件到本地\n预览文件内容(仅文本)\n删除此文件\n取消" | fzf --border --prompt="操作: ")
            case "$action" in
                "下载此文件到本地")
                    echo "正在下载..."
                    rclone copy "${remote_name}:${target_path}" "." --progress
                    echo "下载完成！"
                    read -p "按回车继续..."
                    ;;
                "预览文件内容(仅文本)")
                    clear
                    echo -e "${CYAN}--- 预览: $item_name ---${NC}"
                    rclone cat "${remote_name}:${target_path}" 2>/dev/null | head -n 50
                    echo -e "\n${CYAN}--- 预览结束 ---${NC}"
                    read -p "按回车返回..."
                    ;;
                "删除此文件")
                    read -p "确定要删除 $item_name 吗？(y/n): " confirm
                    if [ "$confirm" == "y" ]; then
                        rclone delete "${remote_name}:${target_path}"
                        echo "已删除！"
                        sleep 1
                    fi
                    ;;
            esac
        fi
    done
}

# ==========================================
# 主菜单
# ==========================================
main_menu() {
    while true; do
        show_header
        local choice
        choice=$(echo -e "执行同步/下载计划\n管理/编辑已有配置\n管理云端文件(浏览/下载/删除)\n创建新计划\n退出程序" | fzf \
            --border --reverse \
            --prompt="主菜单 (ESC退出): " \
            --header="Termux FolderSync Pro v4.0")

        case "$choice" in
            "执行同步/下载计划") run_sync ;;
            "管理/编辑已有配置") manage_plans ;;
            "管理云端文件(浏览/下载/删除)") cloud_browser ;;
            "创建新计划") create_plan ;;
            "退出程序") exit 0 ;;
            *) exit 0 ;;
        esac
    done
}

check_deps
main_menu