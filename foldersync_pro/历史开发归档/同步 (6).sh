#!/data/data/com.termux/files/usr/bin/bash

# ==========================================
# Termux FolderSync Pro (TUI Edition) v7.0
# 新增: chafa 图片预览
# 依赖: rclone, fzf, jq, chafa(可选)
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

# 检测 chafa 是否可用
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
        echo -e "${YELLOW}提示: 未安装 chafa，图片预览不可用。可运行 pkg install chafa${NC}" >&2
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

# 判断文件是否为图片
is_image() {
    local ext="${1##*.}"
    ext="${ext,,}"  # 转小写
    case "$ext" in
        jpg|jpeg|png|gif|bmp|webp|svg|tiff|tif|ico|avif|heic|heif)
            return 0 ;;
        *)
            return 1 ;;
    esac
}

# 判断文件是否为文本
is_text() {
    local ext="${1##*.}"
    ext="${ext,,}"
    case "$ext" in
        txt|md|log|json|xml|html|css|js|sh|py|c|h|cpp|java|ini|conf|cfg|yaml|yml|csv|srt|ass|nfo)
            return 0 ;;
        *)
            return 1 ;;
    esac
}

# ==========================================
# 预览文件（智能判断类型）
# ==========================================
preview_file() {
    local remote_name="$1"
    local target_path="$2"
    local item_name="$3"

    clear
    echo -e "${CYAN}--- 预览: $item_name ---${NC}"
    echo ""

    if is_image "$item_name"; then
        if [ "$HAS_CHAFA" = true ]; then
            echo -e "${YELLOW}正在下载图片用于预览...${NC}"
            local tmp_file=$(mktemp /data/data/com.termux/files/usr/tmp/preview_XXXXXX)
            rclone copyto "${remote_name}:${target_path}" "$tmp_file" --quiet 2>/dev/null
            if [ -f "$tmp_file" ] && [ -s "$tmp_file" ]; then
                echo ""
                chafa --size=80x40 "$tmp_file" 2>/dev/null
                echo ""
                echo -e "${GREEN}图片预览完成${NC}"
            else
                echo -e "${RED}下载失败，无法预览${NC}"
            fi
            rm -f "$tmp_file"
        else
            echo -e "${RED}未安装 chafa，无法预览图片${NC}"
            echo -e "${YELLOW}请运行: pkg install chafa${NC}"
        fi

    elif is_text "$item_name"; then
        echo -e "${YELLOW}文本内容 (前50行):${NC}"
        echo "----------------------------------------"
        rclone cat "${remote_name}:${target_path}" 2>/dev/null | head -n 50
        echo ""
        echo "----------------------------------------"
        echo -e "${GREEN}文本预览完成${NC}"

    else
        echo -e "${YELLOW}无法识别的文件类型，仅显示文件信息${NC}"
        echo ""
        rclone lsl "${remote_name}:${target_path}" 2>/dev/null
        echo ""
        echo -e "${YELLOW}提示: 可下载后使用本地工具查看${NC}"
    fi

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
            menu="${menu}
[${i}] ${line}"
            ((i++))
        fi
    done < "$DOWNLOAD_PATHS_FILE"

    menu="${menu}
[新建] 添加新的下载路径"

    local selection
    selection=$(echo "$menu" | fzf \
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

# ==========================================
# 1. 配置管理 - 创建
# ==========================================
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
    echo ""

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
            echo -e "${GREEN}已更新为: $new_val${NC}"
            ;;
        "修改远程端")
            echo -e "\n${YELLOW}可用的 Rclone 远程端:${NC}"
            rclone listremotes
            read -p "新远程端名称: " new_val
            [ -z "$new_val" ] && return
            jq --arg v "$new_val" '.remote_name = $v' "$plan_file" > "${plan_file}.tmp" && mv "${plan_file}.tmp" "$plan_file"
            echo -e "${GREEN}已更新为: $new_val${NC}"
            ;;
        "修改远程路径")
            read -p "新远程路径: " new_val
            [ -z "$new_val" ] && return
            jq --arg v "$new_val" '.remote_path = $v' "$plan_file" > "${plan_file}.tmp" && mv "${plan_file}.tmp" "$plan_file"
            echo -e "${GREEN}已更新为: $new_val${NC}"
            ;;
        "删除此配置")
            local confirm
            confirm=$(choose "确认删除
取消" "确定要删除 '$name' 吗？")
            if [ "$confirm" == "确认删除" ]; then
                rm -f "$plan_file"
                echo -e "${GREEN}已删除！${NC}"
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

    local_path=$(expand_path "$local_path")

    echo -e "\n${CYAN}计划: $name${NC}"
    echo -e "本地: ${GREEN}$local_path${NC}"
    echo -e "云端: ${GREEN}$remote_full${NC}"
    echo ""

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
            dir_action=$(choose "进入该文件夹
下载整个文件夹到本地
删除该文件夹(包含子文件)
取消" "操作 (ESC取消): ")
            [ -z "$dir_action" ] && continue

            case "$dir_action" in
                "进入该文件夹")
                    current_path="$target_path"
                    ;;
                "下载整个文件夹到本地")
                    local dl_path
                    dl_path=$(choose_download_path ".")
                    [ -z "$dl_path" ] && continue
                    mkdir -p "$dl_path"
                    echo -e "${GREEN}正在下载到: $dl_path/${item_name}${NC}"
                    rclone copy "${remote_name}:${target_path}" "${dl_path}/${item_name}" $RCLONE_OPTS
                    echo -e "${GREEN}下载完成！${NC}"
                    read -p "按回车继续..."
                    ;;
                "删除该文件夹(包含子文件)")
                    local confirm
                    confirm=$(choose "确认删除
取消" "确定要删除 $item_name 吗？")
                    if [ "$confirm" == "确认删除" ]; then
                        rclone purge "${remote_name}:${target_path}"
                        echo "已删除！"
                        sleep 1
                    fi
                    ;;
            esac
        else
            # 【智能菜单】根据文件类型显示不同预览选项
            local menu_options="下载此文件到本地"
            if is_image "$item_name"; then
                menu_options="${menu_options}
预览图片 (chafa)"
            elif is_text "$item_name"; then
                menu_options="${menu_options}
预览文本内容"
            else
                menu_options="${menu_options}
查看文件信息"
            fi
            menu_options="${menu_options}
删除此文件
取消"

            local action
            action=$(choose "$menu_options" "操作 (ESC取消): ")
            [ -z "$action" ] && continue

            case "$action" in
                "下载此文件到本地")
                    local dl_path
                    dl_path=$(choose_download_path ".")
                    [ -z "$dl_path" ] && continue
                    mkdir -p "$dl_path"
                    echo "正在下载到: $dl_path/"
                    rclone copy "${remote_name}:${target_path}" "$dl_path" $RCLONE_OPTS
                    echo "下载完成！"
                    read -p "按回车继续..."
                    ;;
                "预览图片 (chafa)"|"预览文本内容"|"查看文件信息")
                    preview_file "$remote_name" "$target_path" "$item_name"
                    ;;
                "删除此文件")
                    local confirm
                    confirm=$(choose "确认删除
取消" "确定要删除 $item_name 吗？")
                    if [ "$confirm" == "确认删除" ]; then
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