#!/data/data/com.termux/files/usr/bin/bash

# ==========================================
# Termux FolderSync Pro (TUI Edition) v9.0
# 优化: 云端管理器快捷键 (←返回, →进入, TAB菜单)
# 新增: 云端内复制/移动/重命名
# 依赖: rclone, fzf, jq, chafa(可选), coreutils
# ==========================================

CONFIG_DIR="$HOME/.foldersync_pro/plans"
DOWNLOAD_PATHS_FILE="$CONFIG_DIR/download_paths.txt"
mkdir -p "$CONFIG_DIR"
touch "$DOWNLOAD_PATHS_FILE"

RCLONE_OPTS="--transfers 16 --checkers 32 --multi-thread-streams 8 --progress"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

HAS_CHAFA=false
if command -v chafa &> /dev/null; then
    HAS_CHAFA=true
fi

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
            echo -e "${RED}错误: 未安装 $cmd，请先运行 pkg install $cmd${NC}" >&2
            exit 1
        fi
    done
    if [ "$HAS_CHAFA" = false ]; then
        echo -e "${YELLOW}提示: 未安装 chafa，图片预览不可用 (pkg install chafa)${NC}" >&2
        sleep 1
    fi
}

expand_path() {
    local p="$1"
    p="${p/#\~/$HOME}"
    p="${p/#\$HOME/$HOME}"
    echo "$p"
}

choose() {
    echo "$1" | fzf --border --reverse --prompt="$2"
}

natural_sort() {
    sort -V 2>/dev/null || sort
}

is_image() {
    local ext="${1##*.}"
    ext="${ext,,}"
    case "$ext" in
        jpg|jpeg|png|gif|bmp|webp|svg|tiff|tif|ico|avif|heic|heif) return 0 ;;
        *) return 1 ;;
    esac
}

is_text() {
    local ext="${1##*.}"
    ext="${ext,,}"
    case "$ext" in
        txt|md|log|json|xml|html|css|js|sh|py|c|h|cpp|java|ini|conf|cfg|yaml|yml|csv|srt|ass|nfo) return 0 ;;
        *) return 1 ;;
    esac
}

# ==========================================
# 图片画廊预览
# ==========================================
preview_image_gallery() {
    local remote_name="$1"
    local current_path="$2"
    local item_name="$3"

    local images=()
    while IFS= read -r line; do
        [ -n "$line" ] && images+=("$line")
    done < <(rclone lsjson "${remote_name}:${current_path}" 2>/dev/null \
        | jq -r '.[] | select(.IsDir | not) | .Name' \
        | natural_sort \
        | grep -iE '\.(jpg|jpeg|png|gif|bmp|webp|svg|tiff|tif|ico|avif|heic|heif)$')

    if [ ${#images[@]} -eq 0 ]; then
        echo -e "${RED}当前目录没有图片文件${NC}"
        read -p "按回车返回..."
        return
    fi

    local current_index=0
    for i in "${!images[@]}"; do
        if [ "${images[$i]}" == "$item_name" ]; then
            current_index=$i
            break
        fi
    done

    local total=${#images[@]}

    while true; do
        clear
        local current_image="${images[$current_index]}"
        local display_num=$((current_index + 1))

        echo -e "${CYAN}--- ${current_path}/预览: ${current_image} ---${NC}"
        echo -e "${YELLOW}[${display_num}/${total}]  ↑↓换图  ←/ESC返回  q退出${NC}"
        echo "------------------------------------------------"

        local tmp_file="/data/data/com.termux/files/usr/tmp/.gallery_preview_$$"
        rclone copyto "${remote_name}:${current_path}/${current_image}" "$tmp_file" --quiet 2>/dev/null

        if [ -f "$tmp_file" ] && [ -s "$tmp_file" ]; then
            echo ""
            chafa --size=80x40 "$tmp_file" 2>/dev/null
            echo ""
            echo -e "${GREEN}${current_image}${NC}"
        else
            echo -e "\n${RED}加载失败${NC}"
        fi
        rm -f "$tmp_file"

        local key=""
        read -rsn1 key

        if [[ $key == $'\e' ]]; then
            local seq=""
            read -rsn2 -t 0.1 seq
            case "$seq" in
                '[A') 
                    if [ $current_index -gt 0 ]; then ((current_index--)); else current_index=$((total - 1)); fi ;;
                '[B') 
                    if [ $current_index -lt $((total - 1)) ]; then ((current_index++)); else current_index=0; fi ;;
                '[D'|'[C') return 0 ;;
                *) return 0 ;;
            esac
        elif [[ "$key" == "q" || "$key" == "Q" ]]; then
            return 0
        fi
    done
}

preview_text() {
    local remote_name="$1"
    local current_path="$2"
    local item_name="$3"
    local target_path="${current_path}/${item_name}"
    clear
    echo -e "${CYAN}--- ${current_path}/预览: ${item_name} ---${NC}"
    echo ""
    echo -e "${YELLOW}文本内容 (前50行):${NC}"
    echo "----------------------------------------"
    rclone cat "${remote_name}:${target_path}" 2>/dev/null | head -n 50
    echo ""
    echo "----------------------------------------"
    read -p "按回车返回..."
}

preview_info() {
    local remote_name="$1"
    local current_path="$2"
    local item_name="$3"
    local target_path="${current_path}/${item_name}"
    clear
    echo -e "${CYAN}--- ${current_path}/预览: ${item_name} ---${NC}"
    echo ""
    rclone lsl "${remote_name}:${target_path}" 2>/dev/null
    echo ""
    read -p "按回车返回..."
}

# ==========================================
# 下载位置选择器
# ==========================================
choose_download_path() {
    local default_path="$1"
    local menu="[0] 默认路径: ${default_path}"
    local i=1
    while IFS= read -r line; do
        if [ -n "$line" ]; then
            menu="${menu}\n[${i}] ${line}"
            ((i++))
        fi
    done < "$DOWNLOAD_PATHS_FILE"
    menu="${menu}\n[新建] 添加新的下载路径"

    local selection
    selection=$(echo -e "$menu" | fzf \
        --border --reverse \
        --prompt="选择下载位置 (ESC取消): " \
        --header="选择目标文件夹，或新建常用路径")
    [ -z "$selection" ] && return 1

    if [[ "$selection" == "[新建]"* ]]; then
        echo -e "${YELLOW}输入新路径 (输入 q 取消):${NC}" >&2
        read -r new_path
        [ -z "$new_path" ] && return 1
        [ "$new_path" == "q" ] && return 1
        new_path=$(expand_path "$new_path")
        mkdir -p "$new_path"
        echo "$new_path" >> "$DOWNLOAD_PATHS_FILE"
        echo -e "${GREEN}已保存为常用路径！${NC}" >&2
        echo "$new_path"
    elif [[ "$selection" == "[0]"* ]]; then
        echo "$default_path"
    else
        echo "$selection" | sed 's/^\[[0-9]*\] //'
    fi
}

create_plan() {
    show_header
    echo -e "${YELLOW}--- 创建新的同步/下载计划 ---${NC}"
    read -p "计划名称 (输入 q 取消): " plan_name
    [ "$plan_name" == "q" ] && return
    plan_file="$CONFIG_DIR/$(echo $plan_name | tr ' ' '_').json"

    if [ -f "$plan_file" ]; then
        echo -e "${RED}错误: 该计划已存在！${NC}"
        read -p "按回车返回..."
        return
    fi

    read -p "本地路径 (例如: $HOME/storage/shared/DCIM): " local_path
    [ "$local_path" == "q" ] && return
    local_path=$(expand_path "$local_path")

    echo -e "\n${YELLOW}可用的 Rclone 远程端:${NC}"
    rclone listremotes
    read -p "远程端名称 (不需要冒号): " remote_name
    [ "$remote_name" == "q" ] && return
    read -p "远程目录路径 (例如: /backup/phone): " remote_path
    [ "$remote_path" == "q" ] && return

    jq -n \
        --arg name "$plan_name" \
        --arg local "$local_path" \
        --arg remote "$remote_name" \
        --arg rpath "$remote_path" \
        '{name: $name, local_path: $local, remote_name: $remote, remote_path: $rpath}' > "$plan_file"

    echo -e "${GREEN}计划 '$plan_name' 创建成功！${NC}"
    read -p "按回车返回..."
}

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
    echo -e "本地: ${GREEN}$local_path${NC}"
    echo -e "云端: ${GREEN}${remote_name}:${remote_path}${NC}\n"

    local action
    action=$(choose "修改本地路径
修改远程端
修改远程路径
删除此配置
取消" "选择操作 (ESC取消): ")
    [ -z "$action" ] && return

    case "$action" in
        "修改本地路径")
            read -p "新本地路径: " new_val
            [ -z "$new_val" ] && return
            new_val=$(expand_path "$new_val")
            jq --arg v "$new_val" '.local_path = $v' "$plan_file" > "${plan_file}.tmp" && mv "${plan_file}.tmp" "$plan_file"
            ;;
        "修改远程端")
            rclone listremotes
            read -p "新远程端名称: " new_val
            [ -z "$new_val" ] && return
            jq --arg v "$new_val" '.remote_name = $v' "$plan_file" > "${plan_file}.tmp" && mv "${plan_file}.tmp" "$plan_file"
            ;;
        "修改远程路径")
            read -p "新远程路径: " new_val
            [ -z "$new_val" ] && return
            jq --arg v "$new_val" '.remote_path = $v' "$plan_file" > "${plan_file}.tmp" && mv "${plan_file}.tmp" "$plan_file"
            ;;
        "删除此配置")
            local confirm
            confirm=$(choose "确认删除
取消" "确定要删除 '$name' 吗？")
            if [ "$confirm" == "确认删除" ]; then
                rm -f "$plan_file"
            fi
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
    [ -z "$selected_file" ] && return 1
    echo "$selected_file"
}

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
    local_path=$(expand_path "$local_path")

    echo -e "\n${CYAN}计划: $name${NC}"
    echo -e "本地: ${GREEN}$local_path${NC}"
    echo -e "云端: ${GREEN}$remote_full${NC}\n"

    local direction
    direction=$(choose "上传 (本地 -> 云端)
下载 (云端 -> 本地)" "选择传输方向 (ESC取消): ")
    [ -z "$direction" ] && return

    local mode
    mode=$(choose "增量复制 (Copy): 仅传输新/修改文件
镜像同步 (Sync): 完全一致，会删除多余文件" "选择传输模式 (ESC取消): ")
    [ -z "$mode" ] && return

    local rclone_cmd=""
    if [[ "$direction" == *"上传"* ]]; then
        if [ ! -d "$local_path" ]; then
            echo -e "\n${RED}错误: 本地目录不存在: $local_path${NC}"
            read -p "按回车返回..."
            return
        fi
        if [[ "$mode" == *"镜像"* ]]; then
            rclone_cmd="rclone sync '$local_path' '$remote_full' $RCLONE_OPTS"
        else
            rclone_cmd="rclone copy '$local_path' '$remote_full' $RCLONE_OPTS"
        fi
    elif [[ "$direction" == *"下载"* ]]; then
        local download_path
        download_path=$(choose_download_path "$local_path")
        [ -z "$download_path" ] && return
        mkdir -p "$download_path"
        echo -e "\n${CYAN}下载目标: ${GREEN}${download_path}${NC}"
        if [[ "$mode" == *"镜像"* ]]; then
            rclone_cmd="rclone sync '$remote_full' '$download_path' $RCLONE_OPTS"
        else
            rclone_cmd="rclone copy '$remote_full' '$download_path' $RCLONE_OPTS"
        fi
    fi

    echo -e "\n${GREEN}开始执行... (按 Ctrl+C 可中断)${NC}"
    eval "$rclone_cmd"
    echo -e "\n${GREEN}✅ 任务完成！${NC}"
    read -p "按回车返回主菜单..."
}

# ==========================================
# 4. 云端文件管理器 (核心重构)
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

        local dirs=$(rclone lsjson "${remote_name}:${current_path}" 2>/dev/null \
            | jq -r '.[] | select(.IsDir) | .Name' | natural_sort | sed 's/^/[DIR] /')
        local files=$(rclone lsjson "${remote_name}:${current_path}" 2>/dev/null \
            | jq -r '.[] | select(.IsDir | not) | .Name' | natural_sort | sed 's/^/[FILE] /')

        local menu_items="[..] 返回上一级
${dirs}
${files}"

        # 【核心优化】使用 --expect 捕获特定按键
        local fzf_out
        fzf_out=$(echo "$menu_items" | fzf \
            --expect=enter,tab,right,left \
            --border --reverse \
            --prompt="浏览云端 (ESC退出): " \
            --header="←:返回上级 | →/Enter:进入/预览 | TAB:操作菜单")

        local key=$(echo "$fzf_out" | head -n 1)
        local selection=$(echo "$fzf_out" | tail -n +2)

        if [ -z "$selection" ]; then
            break # ESC 退出
        fi

        # 解析选中项
        local item_type=$(echo "$selection" | awk '{print $1}')
        local item_name=$(echo "$selection" | cut -d' ' -f2-)
        local target_path="${current_path}/${item_name}"
        [ "$current_path" == "/" ] && target_path="/${item_name}"

        # 【处理 ← 键】直接返回上一级
        if [ "$key" == "left" ]; then
            if [ "$current_path" != "/" ] && [ "$current_path" != "." ]; then
                current_path=$(dirname "$current_path")
                [ "$current_path" == "." ] && current_path="/"
            fi
            continue
        fi

        # 【处理 → 或 Enter 键】进入文件夹或预览文件
        if [ "$key" == "right" ] || [ "$key" == "enter" ] || [ -z "$key" ]; then
            if [[ "$selection" == "[..] 返回上一级" ]]; then
                if [ "$current_path" != "/" ] && [ "$current_path" != "." ]; then
                    current_path=$(dirname "$current_path")
                    [ "$current_path" == "." ] && current_path="/"
                fi
                continue
            elif [[ "$item_type" == "[DIR]" ]]; then
                current_path="$target_path"
                continue
            elif [[ "$item_type" == "[FILE]" ]]; then
                # 文件按 Enter 直接触发预览
                if is_image "$item_name" && [ "$HAS_CHAFA" = true ]; then
                    preview_image_gallery "$remote_name" "$current_path" "$item_name"
                elif is_text "$item_name"; then
                    preview_text "$remote_name" "$current_path" "$item_name"
                else
                    preview_info "$remote_name" "$current_path" "$item_name"
                fi
                continue
            fi
        fi

        # 【处理 TAB 键】打开操作菜单
        if [ "$key" == "tab" ]; then
            if [[ "$selection" == "[..] 返回上一级" ]]; then
                continue
            fi

            local menu_options=""
            if [[ "$item_type" == "[DIR]" ]]; then
                menu_options="进入该文件夹
下载整个文件夹到本地
云端内复制 (Copy to)
云端内移动 (Move to)
重命名 (Rename)
删除该文件夹(包含子文件)
取消"
            else
                menu_options="预览文件
下载此文件到本地
云端内复制 (Copy to)
云端内移动 (Move to)
重命名 (Rename)
删除此文件
取消"
            fi

            local action
            action=$(choose "$menu_options" "操作菜单 (ESC取消): ")
            [ -z "$action" ] && continue

            case "$action" in
                "进入该文件夹")
                    current_path="$target_path"
                    ;;
                "下载整个文件夹到本地"|"下载此文件到本地")
                    local dl_path
                    dl_path=$(choose_download_path ".")
                    [ -z "$dl_path" ] && continue
                    mkdir -p "$dl_path"
                    echo -e "${GREEN}正在下载到: $dl_path/${item_name}${NC}"
                    rclone copy "${remote_name}:${target_path}" "${dl_path}/${item_name}" $RCLONE_OPTS
                    echo -e "${GREEN}下载完成！${NC}"
                    read -p "按回车继续..."
                    ;;
                "预览文件")
                    if is_image "$item_name" && [ "$HAS_CHAFA" = true ]; then
                        preview_image_gallery "$remote_name" "$current_path" "$item_name"
                    elif is_text "$item_name"; then
                        preview_text "$remote_name" "$current_path" "$item_name"
                    else
                        preview_info "$remote_name" "$current_path" "$item_name"
                    fi
                    ;;
                "云端内复制 (Copy to)"|"云端内移动 (Move to)")
                    echo -e "${YELLOW}当前路径: ${remote_name}:${target_path}${NC}"
                    read -p "输入云端目标路径 (例如 /backup/new_folder): " dest_path
                    [ -z "$dest_path" ] && continue
                    [[ "$dest_path" != /* ]] && dest_path="/$dest_path"
                    
                    if [[ "$action" == *"复制"* ]]; then
                        echo -e "${GREEN}正在云端复制...${NC}"
                        rclone copy "${remote_name}:${target_path}" "${remote_name}:${dest_path}" $RCLONE_OPTS
                    else
                        echo -e "${GREEN}正在云端移动...${NC}"
                        rclone moveto "${remote_name}:${target_path}" "${remote_name}:${dest_path}" $RCLONE_OPTS
                    fi
                    echo -e "${GREEN}操作完成！${NC}"
                    read -p "按回车继续..."
                    ;;
                "重命名 (Rename)")
                    read -p "输入新名称: " new_name
                    [ -z "$new_name" ] && continue
                    local new_target_path="${current_path}/${new_name}"
                    [ "$current_path" == "/" ] && new_target_path="/${new_name}"
                    
                    echo -e "${GREEN}正在重命名...${NC}"
                    rclone moveto "${remote_name}:${target_path}" "${remote_name}:${new_target_path}"
                    echo -e "${GREEN}重命名完成！${NC}"
                    read -p "按回车继续..."
                    ;;
                "删除该文件夹(包含子文件)"|"删除此文件")
                    local confirm
                    confirm=$(choose "确认删除
取消" "确定要删除 $item_name 吗？")
                    if [ "$confirm" == "确认删除" ]; then
                        if [[ "$item_type" == "[DIR]" ]]; then
                            rclone purge "${remote_name}:${target_path}"
                        else
                            rclone delete "${remote_name}:${target_path}"
                        fi
                        echo "已删除！"
                        sleep 1
                    fi
                    ;;
            esac
        fi
    done
}

main_menu() {
    while true; do
        show_header
        local choice
        choice=$(choose "执行同步/下载计划
管理/编辑已有配置
管理云端文件(浏览/下载/删除)
创建新计划
退出程序" "主菜单 (ESC退出): ")

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