#!/data/data/com.termux/files/usr/bin/bash

# ==========================================
# Termux FolderSync Pro (TUI Edition) v10.1
# 修复: 文件列表换行异常 / 插件菜单注入失败
# 依赖: rclone, fzf, jq, chafa(可选), coreutils
# ==========================================

CONFIG_DIR="$HOME/.foldersync_pro"
PLANS_DIR="$CONFIG_DIR/plans"
PLUGIN_DIR="$CONFIG_DIR/插件"
PLUGIN_CACHE_FILE="$CONFIG_DIR/.plugin_cache"
LOCAL_ROOTS_FILE="$CONFIG_DIR/local_roots.json"
DOWNLOAD_PATHS_FILE="$CONFIG_DIR/download_paths.txt"
SETTINGS_FILE="$CONFIG_DIR/settings.json"

mkdir -p "$PLANS_DIR" "$PLUGIN_DIR"
touch "$DOWNLOAD_PATHS_FILE"
[ ! -f "$LOCAL_ROOTS_FILE" ] && echo '[]' > "$LOCAL_ROOTS_FILE"
[ ! -f "$SETTINGS_FILE" ] && echo '{"skip_cert_verify": false}' > "$SETTINGS_FILE"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

HAS_CHAFA=false
command -v chafa &> /dev/null && HAS_CHAFA=true
RCLONE_OPTS=""

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

# ==========================================
# 插件系统核心引擎 (重构版)
# ==========================================
load_plugins() {
    > "$PLUGIN_CACHE_FILE"
    # 使用 find 扫描，比 for 循环通配符更稳定，完美支持中文目录名
    while IFS= read -r manifest; do
        local plugin_dir=$(dirname "$manifest")
        local name=$(jq -r '.name // empty' "$manifest" 2>/dev/null)
        local scope=$(jq -r '.scope // empty' "$manifest" 2>/dev/null)
        local target=$(jq -r '.target // "all"' "$manifest" 2>/dev/null)
        local match=$(jq -r '(.match // ["*"]) | join(",")' "$manifest" 2>/dev/null)
        local position=$(jq -r '.position // "bottom"' "$manifest" 2>/dev/null)
        local entry=$(jq -r '.entry // "run.sh"' "$manifest" 2>/dev/null)
        local entry_path="$plugin_dir/$entry"
        
        if [ -n "$name" ] && [ -n "$scope" ] && [ -f "$entry_path" ]; then
            echo "$name|$scope|$target|$match|$position|$entry_path" >> "$PLUGIN_CACHE_FILE"
        fi
    done < <(find "$PLUGIN_DIR" -name "manifest.json" 2>/dev/null)
}

# 【核心重构】纯字符串拼接，彻底解决数组和换行符兼容问题
build_tab_menu() {
    local item_type="$1"
    local item_name="$2"
    local ext="${item_name##*.}"
    ext="${ext,,}"
    [ "$item_type" == "[DIR]" ] && ext="dir"
    
    # 1. 定义基础菜单 (使用真实换行)
    local base_menu=""
    if [[ "$item_type" == "[DIR]" ]]; then
        base_menu="进入该文件夹
下载整个文件夹到本地
云端内复制 (Copy to)
云端内移动 (Move to)
重命名 (Rename)
删除该文件夹(包含子文件)"
    else
        base_menu="预览文件
下载此文件到本地
云端内复制 (Copy to)
云端内移动 (Move to)
重命名 (Rename)
删除此文件"
    fi
    
    local top_plugins="" bottom_plugins="" after_preview="" before_delete=""
    
    # 2. 扫描并过滤插件
    if [ -f "$PLUGIN_CACHE_FILE" ]; then
        while IFS='|' read -r p_name p_scope p_target p_match p_position p_entry; do
            [ "$p_scope" != "menu" ] && continue
            
            # 目标类型过滤 (file/dir/all)
            if [ "$p_target" != "all" ]; then
                if [[ "$item_type" == "[DIR]" && "$p_target" != "dir" ]]; then continue; fi
                if [[ "$item_type" == "[FILE]" && "$p_target" != "file" ]]; then continue; fi
            fi
            
            # 文件后缀过滤
            local matched=false
            IFS=',' read -ra MATCH_ARRAY <<< "$p_match"
            for m in "${MATCH_ARRAY[@]}"; do
                m="${m,,}" 
                m="${m// /}" # 去除空格
                if [ "$m" == "*" ] || [ "$m" == "*.$ext" ] || [ "$m" == "$ext" ]; then
                    matched=true; break
                fi
            done
            [ "$matched" = false ] && continue
            
            local plugin_item="${p_name} (插件)"
            case "$p_position" in
                top) top_plugins+="$plugin_item"$'\n' ;;
                bottom) bottom_plugins+="$plugin_item"$'\n' ;;
                after:预览文件) after_preview+="$plugin_item"$'\n' ;;
                before:删除*) before_delete+="$plugin_item"$'\n' ;;
                *) bottom_plugins+="$plugin_item"$'\n' ;;
            esac
        done < "$PLUGIN_CACHE_FILE"
    fi
    
    # 3. 组装最终菜单 (按行读取基础菜单并注入插件)
    local final_menu=""
    [ -n "$top_plugins" ] && final_menu+="$top_plugins"
    
    while IFS= read -r line; do
        [ -z "$line" ] && continue
        final_menu+="$line"$'\n'
        # 在特定菜单项后注入插件
        if [[ "$line" == "预览文件" ]]; then 
            [ -n "$after_preview" ] && final_menu+="$after_preview"
        fi
        if [[ "$line" == 删除* ]]; then 
            [ -n "$before_delete" ] && final_menu+="$before_delete"
        fi
    done <<< "$base_menu"
    
    [ -n "$bottom_plugins" ] && final_menu+="$bottom_plugins"
    final_menu+="取消"
    
    printf "%s" "$final_menu"
}

update_rclone_opts() {
    RCLONE_OPTS="--transfers 16 --checkers 32 --multi-thread-streams 8 --progress"
    local skip_cert=$(jq -r '.skip_cert_verify // false' "$SETTINGS_FILE" 2>/dev/null)
    if [ "$skip_cert" == "true" ]; then
        RCLONE_OPTS="$RCLONE_OPTS --no-check-certificate"
    fi
}

expand_path() {
    local p="$1"
    p="${p/#\~/$HOME}"
    p="${p/#\$HOME/$HOME}"
    echo "$p"
}

choose() {
    # 使用 printf "%b\n" 确保无论是 \n 字面量还是真实换行都能完美处理
    printf "%b\n" "$1" | fzf --border --reverse --prompt="$2"
}

natural_sort() { sort -V 2>/dev/null || sort; }

is_image() {
    local ext="${1##*.}"; ext="${ext,,}"
    case "$ext" in jpg|jpeg|png|gif|bmp|webp|svg|tiff|tif|ico|avif|heic|heif) return 0 ;; *) return 1 ;; esac
}

is_text() {
    local ext="${1##*.}"; ext="${ext,,}"
    case "$ext" in txt|md|log|json|xml|html|css|js|sh|py|c|h|cpp|java|ini|conf|cfg|yaml|yml|csv|srt|ass|nfo) return 0 ;; *) return 1 ;; esac
}

choose_local_root() {
    local roots=$(jq -r '.[] | "[\(.alias)] \(.path)"' "$LOCAL_ROOTS_FILE" 2>/dev/null)
    local menu="${roots}\n[新增] 添加新的本地根路径"
    local selection=$(printf "%b" "$menu" | fzf --border --reverse --prompt="选择本地根路径 (ESC取消): ")
    [ -z "$selection" ] && return 1
    if [[ "$selection" == "[新增]"* ]]; then
        read -p "输入别名: " alias_name; [ -z "$alias_name" ] && return 1
        read -p "输入绝对路径: " root_path; [ -z "$root_path" ] && return 1
        root_path=$(expand_path "$root_path")
        jq --arg a "$alias_name" --arg p "$root_path" '. += [{"alias": $a, "path": $p}]' "$LOCAL_ROOTS_FILE" > tmp.json && mv tmp.json "$LOCAL_ROOTS_FILE"
        echo "$root_path"
    else
        echo "$selection" | sed 's/^\[[^]]*\] //'
    fi
}

preview_image_gallery() {
    local remote_name="$1" current_path="$2" item_name="$3"
    local images=()
    while IFS= read -r line; do [ -n "$line" ] && images+=("$line"); done < <(rclone lsjson "${remote_name}:${current_path}" 2>/dev/null | jq -r '.[] | select(.IsDir | not) | .Name' | natural_sort | grep -iE '\.(jpg|jpeg|png|gif|bmp|webp|svg|tiff|tif|ico|avif|heic|heif)$')
    [ ${#images[@]} -eq 0 ] && return
    local current_index=0
    for i in "${!images[@]}"; do [ "${images[$i]}" == "$item_name" ] && current_index=$i && break; done
    local total=${#images[@]}
    while true; do
        clear
        local current_image="${images[$current_index]}"
        echo -e "${CYAN}--- ${current_path}/预览: ${current_image} ---${NC}"
        echo -e "${YELLOW}[$((current_index + 1))/${total}]  ↑↓换图  ←/ESC返回  q退出${NC}"
        local tmp_file="/data/data/com.termux/files/usr/tmp/.gallery_preview_$$"
        rclone copyto "${remote_name}:${current_path}/${current_image}" "$tmp_file" --quiet 2>/dev/null
        if [ -f "$tmp_file" ] && [ -s "$tmp_file" ]; then echo ""; chafa --size=80x40 "$tmp_file" 2>/dev/null; echo -e "\n${GREEN}${current_image}${NC}"; fi
        rm -f "$tmp_file"
        local key=""; read -rsn1 key
        if [[ $key == $'\e' ]]; then
            local seq=""; read -rsn2 -t 0.1 seq
            case "$seq" in '[A') [ $current_index -gt 0 ] && ((current_index--)) || current_index=$((total - 1)) ;; '[B') [ $current_index -lt $((total - 1)) ] && ((current_index++)) || current_index=0 ;; *) return 0 ;; esac
        elif [[ "$key" == "q" || "$key" == "Q" ]]; then return 0; fi
    done
}

preview_text() {
    clear; echo -e "${CYAN}--- ${2}/预览: ${3} ---${NC}\n"
    rclone cat "${1}:${2}/${3}" 2>/dev/null | head -n 50
    read -p "按回车返回..."
}

preview_info() {
    clear; echo -e "${CYAN}--- ${2}/预览: ${3} ---${NC}\n"
    rclone lsl "${1}:${2}/${3}" 2>/dev/null
    read -p "按回车返回..."
}

choose_download_path() {
    local default_path="$1" menu="[0] 默认路径: ${1}" i=1
    while IFS= read -r line; do [ -n "$line" ] && menu="${menu}\n[${i}] ${line}" && ((i++)); done < "$DOWNLOAD_PATHS_FILE"
    menu="${menu}\n[新建] 添加新的下载路径"
    local selection=$(printf "%b" "$menu" | fzf --border --reverse --prompt="选择下载位置 (ESC取消): ")
    [ -z "$selection" ] && return 1
    if [[ "$selection" == "[新建]"* ]]; then
        read -p "输入新路径 (q取消): " new_path; [ "$new_path" == "q" ] || [ -z "$new_path" ] && return 1
        new_path=$(expand_path "$new_path"); mkdir -p "$new_path"; echo "$new_path" >> "$DOWNLOAD_PATHS_FILE"; echo "$new_path"
    elif [[ "$selection" == "[0]"* ]]; then echo "$default_path"
    else echo "$selection" | sed 's/^\[[0-9]*\] //'; fi
}

create_plan() {
    show_header; echo -e "${YELLOW}--- 创建新的同步计划 ---${NC}"
    read -p "计划名称 (q取消): " plan_name; [ "$plan_name" == "q" ] && return
    plan_file="$PLANS_DIR/$(echo $plan_name | tr ' ' '_').json"
    [ -f "$plan_file" ] && echo -e "${RED}已存在！${NC}" && read -p "回车返回..." && return
    local remotes=$(rclone listremotes | sed 's/://g')
    local remote_name=$(printf "%b" "$remotes" | fzf --border --reverse --prompt="选择云端远程端: ")
    [ -z "$remote_name" ] && return
    read -p "远程目录路径: " remote_path
    local local_paths="[]"
    while true; do
        echo -e "\n${CYAN}已添加本地路径:${NC}"; echo "$local_paths" | jq -r '.[] | "[\(.alias)] \(.path)"'
        local add_more=$(choose "添加新路径\n完成创建" "操作: ")
        [ "$add_more" == "完成创建" ] && break
        local root_path=$(choose_local_root); [ -z "$root_path" ] && continue
        read -p "设置别名: " alias_name; [ -z "$alias_name" ] && alias_name="路径$(( $(echo "$local_paths" | jq length) + 1 ))"
        local_paths=$(echo "$local_paths" | jq --arg a "$alias_name" --arg p "$root_path" '. += [{"alias": $a, "path": $p}]')
    done
    jq -n --arg name "$plan_name" --arg remote "$remote_name" --arg rpath "$remote_path" --argjson lpaths "$local_paths" '{name: $name, remote_name: $remote, remote_path: $rpath, local_paths: $lpaths}' > "$plan_file"
    echo -e "${GREEN}创建成功！${NC}"; read -p "按回车返回..."
}

manage_plans() {
    show_header; local plan_file=$(select_plan); [ -z "$plan_file" ] && return
    while true; do
        clear; local name=$(jq -r '.name' "$plan_file") remote_name=$(jq -r '.remote_name' "$plan_file") remote_path=$(jq -r '.remote_path' "$plan_file")
        echo -e "${CYAN}计划: $name${NC}\n云端: ${GREEN}${remote_name}:${remote_path}${NC}\n${YELLOW}本地路径:${NC}"
        jq -r '.local_paths[] | "[\(.alias)] \(.path)"' "$plan_file"
        local action=$(choose "修改云端配置\n管理本地路径 (TAB操作)\n删除此计划\n返回" "操作: ")
        [ -z "$action" ] || [ "$action" == "返回" ] && return
        if [ "$action" == "修改云端配置" ]; then
            local remotes=$(rclone listremotes | sed 's/://g')
            local new_remote=$(printf "%b" "$remotes" | fzf --border --reverse --prompt="新远程端: ")
            [ -n "$new_remote" ] && jq --arg v "$new_remote" '.remote_name = $v' "$plan_file" > tmp && mv tmp "$plan_file"
            read -p "新远程路径: " new_rpath; [ -n "$new_rpath" ] && jq --arg v "$new_rpath" '.remote_path = $v' "$plan_file" > tmp && mv tmp "$plan_file"
        elif [ "$action" == "管理本地路径 (TAB操作)" ]; then
            local paths_menu=$(jq -r '.local_paths[] | "[\(.alias)] \(.path)"' "$plan_file")
            local path_action=$(printf "%b" "$paths_menu\n[新增] 添加新路径" | fzf --border --reverse --expect=tab,enter --prompt="TAB操作/Enter预览: ")
            local key=$(head -n 1 <<< "$path_action") sel=$(tail -n +2 <<< "$path_action")
            if [ "$key" == "tab" ] && [ -n "$sel" ]; then
                if [[ "$sel" == "[新增]"* ]]; then
                    local root_path=$(choose_local_root)
                    [ -n "$root_path" ] && read -p "别名: " alias_name && jq --arg a "$alias_name" --arg p "$root_path" '.local_paths += [{"alias": $a, "path": $p}]' "$plan_file" > tmp && mv tmp "$plan_file"
                else
                    local op=$(choose "重命名别名\n修改路径\n删除此路径" "操作: ")
                    local idx=$(printf "%b" "$paths_menu" | grep -n "^$sel$" | cut -d: -f1); idx=$((idx - 1))
                    if [ "$op" == "重命名别名" ]; then read -p "新别名: " new_alias; jq --argjson i $idx --arg v "$new_alias" '.local_paths[$i].alias = $v' "$plan_file" > tmp && mv tmp "$plan_file"
                    elif [ "$op" == "修改路径" ]; then local new_path=$(choose_local_root); [ -n "$new_path" ] && jq --argjson i $idx --arg v "$new_path" '.local_paths[$i].path = $v' "$plan_file" > tmp && mv tmp "$plan_file"
                    elif [ "$op" == "删除此路径" ]; then jq --argjson i $idx 'del(.local_paths[$i])' "$plan_file" > tmp && mv tmp "$plan_file"; fi
                fi
            fi
        elif [ "$action" == "删除此计划" ]; then
            local confirm=$(choose "确认删除\n取消" "确定吗？"); [ "$confirm" == "确认删除" ] && rm -f "$plan_file" && return
        fi
    done
}

select_plan() {
    local selected_file=$(ls -1 "$PLANS_DIR"/*.json 2>/dev/null | fzf --border --reverse --prompt="选择计划 (ESC退出): " --preview 'jq -r "\"\n计划: \(.name)\n云端: \(.remote_name):\(.remote_path)\n本地路径数: \(.local_paths | length)\n\"" {}' --preview-window=down:40%:wrap)
    [ -z "$selected_file" ] && return 1; echo "$selected_file"
}

run_sync() {
    show_header; local plan_file=$(select_plan); [ -z "$plan_file" ] && return
    local name=$(jq -r '.name' "$plan_file") remote_full="$(jq -r '.remote_name' "$plan_file"):$(jq -r '.remote_path' "$plan_file")"
    echo -e "${CYAN}计划: $name${NC} -> ${GREEN}$remote_full${NC}"
    local direction=$(choose "上传 (本地 -> 云端)\n下载 (云端 -> 本地)" "方向: "); [ -z "$direction" ] && return
    local mode=$(choose "增量复制 (Copy)\n镜像同步 (Sync)" "模式: "); [ -z "$mode" ] && return
    local cmd="copy"; [[ "$mode" == *"镜像"* ]] && cmd="sync"
    if [[ "$direction" == *"上传"* ]]; then
        local paths=$(jq -r '.local_paths[].path' "$plan_file") count=$(echo "$paths" | grep -c .) i=1
        while IFS= read -r local_path; do
            [ -z "$local_path" ] && continue; echo -e "\n${YELLOW}[$i/$count] 上传: $local_path${NC}"
            [ ! -d "$local_path" ] && echo -e "${RED}不存在，跳过！${NC}" || eval "rclone $cmd '$local_path' '$remote_full' $RCLONE_OPTS"; ((i++))
        done <<< "$paths"
    else
        local dl_path=$(choose_download_path "$HOME/storage/shared/Download"); [ -z "$dl_path" ] && return
        mkdir -p "$dl_path"; echo -e "\n${YELLOW}下载到: $dl_path${NC}"; eval "rclone $cmd '$remote_full' '$dl_path' $RCLONE_OPTS"
    fi
    echo -e "\n${GREEN}✅ 完成！${NC}"; read -p "按回车返回..."
}

cloud_browser() {
    show_header; local plan_file=$(select_plan); [ -z "$plan_file" ] && return
    local remote_name=$(jq -r '.remote_name' "$plan_file") current_path=$(jq -r '.remote_path' "$plan_file")
    while true; do
        clear; echo -e "${CYAN}当前云端路径:${NC} ${YELLOW}${remote_name}:${current_path}${NC}\n------------------------------------------------"
        local dirs=$(rclone lsjson "${remote_name}:${current_path}" 2>/dev/null | jq -r '.[] | select(.IsDir) | .Name' | natural_sort | sed 's/^/[DIR] /')
        local files=$(rclone lsjson "${remote_name}:${current_path}" 2>/dev/null | jq -r '.[] | select(.IsDir | not) | .Name' | natural_sort | sed 's/^/[FILE] /')
        
        # 【修复】使用真实的换行符拼接，彻底解决 \n 显示异常
        local menu_items="[..] 返回上一级
${dirs}
${files}"

        local fzf_out
        fzf_out=$(printf "%s\n" "$menu_items" | fzf \
            --expect=enter,tab,right,left \
            --border --reverse \
            --prompt="浏览云端 (ESC退出): " \
            --header="←:返回 | →/Enter:进入/预览 | TAB:操作菜单")

        local key=$(echo "$fzf_out" | head -n 1) selection=$(echo "$fzf_out" | tail -n +2)
        [ -z "$selection" ] && break
        local item_type=$(echo "$selection" | awk '{print $1}') item_name=$(echo "$selection" | cut -d' ' -f2-)
        local target_path="${current_path}/${item_name}"; [ "$current_path" == "/" ] && target_path="/${item_name}"
        
        if [ "$key" == "left" ]; then [ "$current_path" != "/" ] && [ "$current_path" != "." ] && current_path=$(dirname "$current_path"); continue; fi
        if [ "$key" == "right" ] || [ "$key" == "enter" ] || [ -z "$key" ]; then
            if [[ "$selection" == "[..] 返回上一级" ]]; then [ "$current_path" != "/" ] && [ "$current_path" != "." ] && current_path=$(dirname "$current_path")
            elif [[ "$item_type" == "[DIR]" ]]; then current_path="$target_path"
            elif [[ "$item_type" == "[FILE]" ]]; then
                if is_image "$item_name" && [ "$HAS_CHAFA" = true ]; then preview_image_gallery "$remote_name" "$current_path" "$item_name"
                elif is_text "$item_name"; then preview_text "$remote_name" "$current_path" "$item_name"
                else preview_info "$remote_name" "$current_path" "$item_name"; fi
            fi; continue
        fi
        
        if [ "$key" == "tab" ]; then
            [ "$selection" == "[..] 返回上一级" ] && continue
            
            # 动态构建包含插件的菜单
            local menu_options=$(build_tab_menu "$item_type" "$item_name")
            local action=$(choose "$menu_options" "操作菜单 (ESC取消): ")
            [ -z "$action" ] && continue

            # 拦截并执行插件
            if [[ "$action" == *" (插件)" ]]; then
                local p_name="${action% (插件)}"
                local p_entry=$(grep "^${p_name}|" "$PLUGIN_CACHE_FILE" | cut -d'|' -f6)
                if [ -n "$p_entry" ] && [ -f "$p_entry" ]; then
                    clear
                    echo -e "${YELLOW}执行插件: $p_name${NC}"
                    echo "----------------------------------------"
                    bash "$p_entry" "$target_path" "$item_name" "$remote_name"
                    echo "----------------------------------------"
                    read -p "插件执行完毕，按回车返回..."
                fi
                continue
            fi

            case "$action" in
                "进入该文件夹") current_path="$target_path" ;;
                "下载整个文件夹到本地"|"下载此文件到本地")
                    local dl_path=$(choose_download_path "."); [ -z "$dl_path" ] && continue
                    mkdir -p "$dl_path"; echo -e "${GREEN}下载到: $dl_path/${item_name}${NC}"
                    rclone copy "${remote_name}:${target_path}" "${dl_path}/${item_name}" $RCLONE_OPTS; read -p "完成..." ;;
                "预览文件")
                    if is_image "$item_name" && [ "$HAS_CHAFA" = true ]; then preview_image_gallery "$remote_name" "$current_path" "$item_name"
                    elif is_text "$item_name"; then preview_text "$remote_name" "$current_path" "$item_name"
                    else preview_info "$remote_name" "$current_path" "$item_name"; fi ;;
                "云端内复制 (Copy to)"|"云端内移动 (Move to)")
                    read -p "输入云端目标路径: " dest_path; [ -z "$dest_path" ] && continue; [[ "$dest_path" != /* ]] && dest_path="/$dest_path"
                    if [[ "$action" == *"复制"* ]]; then rclone copy "${remote_name}:${target_path}" "${remote_name}:${dest_path}" $RCLONE_OPTS
                    else rclone moveto "${remote_name}:${target_path}" "${remote_name}:${dest_path}" $RCLONE_OPTS; fi; read -p "完成..." ;;
                "重命名 (Rename)")
                    read -p "输入新名称: " new_name; [ -z "$new_name" ] && continue
                    rclone moveto "${remote_name}:${target_path}" "${remote_name}:${current_path}/${new_name}"; read -p "完成..." ;;
                "删除该文件夹(包含子文件)"|"删除此文件")
                    local confirm=$(choose "确认删除\n取消" "确定吗？")
                    if [ "$confirm" == "确认删除" ]; then
                        if [[ "$item_type" == "[DIR]" ]]; then rclone purge "${remote_name}:${target_path}"; else rclone delete "${remote_name}:${target_path}"; fi
                        sleep 1; fi ;;
            esac
        fi
    done
}

settings_menu() {
    while true; do
        show_header; local skip_cert=$(jq -r '.skip_cert_verify // false' "$SETTINGS_FILE" 2>/dev/null) status_text="关闭"
        [ "$skip_cert" == "true" ] && status_text="开启"
        local action=$(choose "跳过证书验证: ${status_text} (点击切换)\n返回主菜单" "设置: ")
        [ -z "$action" ] || [ "$action" == "返回主菜单" ] && return
        if [[ "$action" == *"跳过证书验证"* ]]; then
            if [ "$skip_cert" == "true" ]; then jq '.skip_cert_verify = false' "$SETTINGS_FILE" > tmp.json && mv tmp.json "$SETTINGS_FILE"
            else jq '.skip_cert_verify = true' "$SETTINGS_FILE" > tmp.json && mv tmp.json "$SETTINGS_FILE"; fi
            update_rclone_opts; sleep 1
        fi
    done
}

main_menu() {
    while true; do
        show_header
        local choice=$(choose "执行同步/下载计划\n管理/编辑已有配置\n管理云端文件(浏览/下载/删除)\n创建新计划\n设置\n退出程序" "主菜单 (ESC退出): ")
        case "$choice" in
            "执行同步/下载计划") run_sync ;;
            "管理/编辑已有配置") manage_plans ;;
            "管理云端文件(浏览/下载/删除)") cloud_browser ;;
            "创建新计划") create_plan ;;
            "设置") settings_menu ;;
            "退出程序") exit 0 ;;
            *) exit 0 ;;
        esac
    done
}

check_deps
load_plugins  # 启动时加载插件
update_rclone_opts
main_menu