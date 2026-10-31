#!/data/data/com.termux/files/usr/bin/bash

# ==========================================
# Termux FolderSync Pro (TUI Edition) v2.0
# 修复日志预览，增强文件夹下载功能
# 依赖: rclone, fzf, jq, tree
# ==========================================

CONFIG_DIR="$HOME/.foldersync_pro/plans"
LOG_DIR="$HOME/.foldersync_pro/logs"
mkdir -p "$CONFIG_DIR" "$LOG_DIR"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ==========================================
# 工具函数
# ==========================================
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

# ==========================================
# 1. 配置管理模块 (JSON 格式)
# ==========================================
create_plan() {
    show_header
    echo -e "${YELLOW}--- 创建新的同步/下载计划 ---${NC}"
    read -p "计划名称 (例如: 相册备份WebDAV): " plan_name
    plan_file="$CONFIG_DIR/$(echo $plan_name | tr ' ' '_').json"
    
    if [ -f "$plan_file" ]; then
        echo -e "${RED}错误: 该计划已存在！${NC}"
        read -p "按回车返回..."
        return
    fi

    read -p "本地路径 (例如: $HOME/storage/shared/DCIM): " local_path
    # 展开 ~ 符号
    local_path="${local_path/#\~/$HOME}"
    
    echo -e "\n${YELLOW}可用的 Rclone 远程端:${NC}"
    rclone listremotes
    read -p "远程端名称 (不需要冒号, 例如: mywebdav): " remote_name
    
    read -p "远程目录路径 (例如: /backup/phone): " remote_path
    
    echo -e "\n${YELLOW}默认方向:${NC}"
    echo "1) 上传 (本地 -> 云端)"
    echo "2) 下载 (云端 -> 本地)"
    read -p "选择默认方向 [1/2]: " dir_choice
    
    case $dir_choice in
        1) direction="upload" ;;
        2) direction="download" ;;
        *) direction="upload" ;;
    esac

    # 写入 JSON
    jq -n \
        --arg name "$plan_name" \
        --arg local "$local_path" \
        --arg remote "$remote_name" \
        --arg rpath "$remote_path" \
        --arg dir "$direction" \
        '{name: $name, local_path: $local, remote_name: $remote, remote_path: $rpath, direction: $dir}' > "$plan_file"
        
    echo -e "${GREEN}计划 '$plan_name' 创建成功！${NC}"
    read -p "按回车返回..."
}

select_plan() {
    # 使用 fzf 选择配置，并带有实时预览
    local selected_file=$(ls -1 "$CONFIG_DIR"/*.json 2>/dev/null | fzf \
        --height 40% --border --reverse \
        --prompt="选择同步计划 (ESC退出): " \
        --preview 'jq -r "\"\n计划: \(.name)\n本地: \(.local_path)\n云端: \(.remote_name):\(.remote_path)\n默认方向: \(.direction)\n\"" {}' \
        --preview-window=up:40%:wrap)
        
    if [ -z "$selected_file" ]; then
        return 1
    fi
    echo "$selected_file"
}

# ==========================================
# 2. 同步/下载执行引擎
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
    local default_dir=$(jq -r '.direction' "$plan_file")
    local remote_full="${remote_name}:${remote_path}"
    
    echo -e "\n${CYAN}即将执行计划: $name${NC}"
    
    # 允许临时覆盖方向
    echo -e "\n选择本次执行的方向 (默认为: ${GREEN}$default_dir${NC}):"
    echo "1) 使用默认方向"
    echo "2) 强制上传 (本地 -> 云端)"
    echo "3) 强制下载 (云端 -> 本地)"
    read -p "选择 [1/2/3]: " dir_override
    
    local direction="$default_dir"
    case $dir_override in
        2) direction="upload" ;;
        3) direction="download" ;;
    esac

    # 选择同步模式
    echo -e "\n选择传输模式:"
    echo "1) 增量复制 (Copy): 仅传输新/修改文件，不删除目标端多余文件 (推荐)"
    echo "2) 镜像同步 (Sync): 使目标端与源端完全一致，会【删除】目标端多余文件"
    read -p "选择 [1/2]: " mode
    
    local rclone_cmd=""
    local log_file="$LOG_DIR/$(date +%Y%m%d_%H%M%S)_${name}.log"
        # 高性能参数配置 + 实时进度条：
    # --transfers 16       : 同时传输 16 个文件（大幅提升大量小文件的下载速度）
    # --checkers 32        : 同时检查 32 个文件（加快本地与云端的对比速度）
    # --multi-thread-streams 8 : 下载大文件（如视频）时，将文件切成 8 块同时下载
    # --progress           : 恢复实时进度条显示
    local opts="--transfers 16 --checkers 32 --multi-thread-streams 8 --progress --log-file $log_file"

    if [ "$direction" == "upload" ]; then
        if [ "$mode" == "2" ]; then
            rclone_cmd="rclone sync '$local_path' '$remote_full' $opts"
        else
            rclone_cmd="rclone copy '$local_path' '$remote_full' $opts"
        fi
    elif [ "$direction" == "download" ]; then
        if [ "$mode" == "2" ]; then
            rclone_cmd="rclone sync '$remote_full' '$local_path' $opts"
        else
            rclone_cmd="rclone copy '$remote_full' '$local_path' $opts"
        fi
    fi

    echo -e "\n${GREEN}开始执行... (按 Ctrl+C 可中断)${NC}"
    eval "$rclone_cmd"
    
    echo -e "\n${GREEN}任务完成！${NC}"
    echo -e "日志已保存至: ${YELLOW}$log_file${NC}"
    read -p "按回车返回主菜单..."
}

# ==========================================
# 3. 云端文件管理器 (TUI Browser) - 增强下载
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
        
        # 获取目录内容
        local items=$(rclone lsjson "${remote_name}:${current_path}" 2>/dev/null | jq -r '
            sort_by(.IsDir) | reverse | 
            .[] | 
            if .IsDir then "[DIR] " + .Name 
            else "[FILE] " + .Name 
            end')
            
        local menu_items="[..] 返回上一级
$items"
        
        local selection=$(echo "$menu_items" | fzf \
            --height 80% --border --reverse \
            --prompt="浏览云端 (ESC退出): " \
            --header="方向键选择, Enter进入/操作")
            
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
            # 文件夹操作菜单 (新增下载整个文件夹)
            local dir_action=$(echo -e "进入该文件夹\n下载整个文件夹到本地(Termux当前目录)\n删除该文件夹(包含子文件)\n取消" | fzf --height 20% --border --prompt="操作: ")
            case "$dir_action" in
                "进入该文件夹")
                    current_path="$target_path"
                    ;;
                "下载整个文件夹到本地(Termux当前目录)")
                    echo -e "${GREEN}正在下载整个文件夹到本地...${NC}"
                    # 下载到运行脚本时所在的目录，并自动创建同名文件夹
                    rclone copy "${remote_name}:${target_path}" "./${item_name}" --progress
                    echo -e "${GREEN}下载完成！保存在 Termux 当前目录的 ./${item_name} 中。${NC}"
                    read -p "按回车继续..."
                    ;;
                "删除该文件夹(包含子文件)")
                    read -p "确定要彻底删除文件夹 $item_name 吗？(y/n): " confirm
                    if [ "$confirm" == "y" ]; then
                        rclone purge "${remote_name}:${target_path}"
                        echo "已删除！"
                        sleep 1
                    fi
                    ;;
            esac
        else
            # 文件操作菜单
            local action=$(echo -e "下载此文件到本地(Termux当前目录)\n预览文件内容 (仅限文本)\n删除此文件\n取消" | fzf --height 20% --border --prompt="操作: ")
            case "$action" in
                "下载此文件到本地(Termux当前目录)")
                    echo "正在下载..."
                    rclone copy "${remote_name}:${target_path}" "." --progress
                    echo "下载完成！"
                    read -p "按回车继续..."
                    ;;
                "预览文件内容 (仅限文本)")
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
# 主菜单循环
# ==========================================
main_menu() {
    while true; do
        show_header
        local choice=$(echo -e "执行同步/下载计划\n管理云端文件(浏览/下载/删除)\n创建新计划\n查看同步日志\n退出程序" | fzf \
            --height 40% --border --reverse \
            --prompt="主菜单 (ESC退出): " \
            --header="Termux FolderSync Pro v2.0")
            
        case "$choice" in
            "执行同步/下载计划") run_sync ;;
            "管理云端文件(浏览/下载/删除)") cloud_browser ;;
            "创建新计划") create_plan ;;
                        "查看同步日志") 
                # 获取所有日志，按时间倒序排列
                local logs=$(ls -1t "$LOG_DIR"/*.log 2>/dev/null)
                if [ -z "$logs" ]; then
                    echo "暂无同步日志。"
                    read -p "按回车返回..."
                else
                    # 优化：右侧显示预览，支持 Shift+上下滚动，回车进入 less 全屏阅读
                    echo "$logs" | fzf \
                        --height 90% \
                        --border \
                        --prompt="选择日志 (Enter阅读, ESC返回): " \
                        --preview 'cat {}' \
                        --preview-window=right:60%:wrap \
                        --bind 'shift-up:preview-page-up,shift-down:preview-page-down' \
                        | xargs -r less
                fi
                ;;
            "退出程序") exit 0 ;;
            *) exit 0 ;; # ESC pressed
        esac
    done
}

# 启动
check_deps
main_menu