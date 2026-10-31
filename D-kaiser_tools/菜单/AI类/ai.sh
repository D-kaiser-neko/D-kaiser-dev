#!/bin/bash
while true; do
    echo "----------------------------"
    echo " [1] peach-roleplay"
    echo " [2] peach2-roleplay"
    echo " [3] phi-4-mini"
    echo " [4] qwen2.5-coder"
    echo " [5] qwen3-1.7B"
    echo " [6] SmolLM2"
    echo " [x] 退出"
    echo "----------------------------"
    read -p "请选择: " opt
    case $opt in
        1) bash $HOME/D-kaiser_tools/菜单/AI类/peach.sh ;;
        2) bash $HOME/D-kaiser_tools/菜单/AI类/peach2.sh ;;
        3) bash $HOME/D-kaiser_tools/菜单/AI类/phi.sh ;;
        4) bash $HOME/D-kaiser_tools/菜单/AI类/qwen2.5.sh ;;
        5) bash $HOME/D-kaiser_tools/菜单/AI类/qwen3.sh ;;
        6) bash $HOME/D-kaiser_tools/菜单/AI类/SmolLM2.sh ;;
        x|X) echo "已退出。"; break ;;
        *) echo "无效选项，请重试。" ;;
    esac
    echo ""
done