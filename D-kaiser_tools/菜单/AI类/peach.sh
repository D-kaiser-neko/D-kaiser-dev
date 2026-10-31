#!/bin/bash
# ============================================================
# llama.cpp 快捷启动脚本 - 对话模式
# 用途：一键启动 Peach / Qwen / Llama 等 .gguf 模型的对话
# 作者：AI 生成，自由修改
# ============================================================

# --------------------------------------------------
# 【必填】模型文件路径
# --------------------------------------------------
MODEL="/storage/emulated/0/Download/AI模型/Peach-9B-8k-Roleplay-IQ2_M_1.gguf"

# --------------------------------------------------
# 【选填】llama-cli 二进制路径
# --------------------------------------------------
LLAMA_CLI="$HOME/llama.cpp/build/bin/llama-cli"

# --------------------------------------------------
# 【新增】对话历史保存配置
# --------------------------------------------------
HISTORY_DIR="$HOME/ai_history"
HISTORY_NAME_FORMAT="ai_%Y%m%d_%H%M%S.txt"
SAVE_HISTORY="yes"

# --------------------------------------------------
# 【新增】停止词配置（Reverse Prompt）
# 当模型生成内容中出现这些字符串时，自动停止输出
# 多个停止词用英文分号 ; 分隔
# 示例：
#   STOP_WORDS="遇到;系统提示;User:"
#   STOP_WORDS="human;Human;USER:"
# 留空表示不启用
# --------------------------------------------------
STOP_WORDS="<|im_end|>;<|im_start|>"

# --------------------------------------------------
# 【核心参数】上下文与生成控制
# --------------------------------------------------
CTX_SIZE=4096                # 上下文长度（令牌数）。调大能让模型参考更多前文，适合长对话，但会显著增加显存和计算时间；调小则节省资源，但早期内容会被遗忘。
N_PREDICT=512                # 最大生成令牌数。调大回复更详细完整，但可能偏离主题或产生冗余；调小回复更简洁，适合快速问答。
TEMP=0.3                     # 温度，控制随机性。调大输出更多样、更“创意”，但可能产生幻觉或不相关内容；调小输出更确定、更保守，适合事实性回答。

# --------------------------------------------------
# 【性能参数】速度与资源控制
# --------------------------------------------------
THREADS=$(nproc)
BATCH_SIZE=2048
UBATCH_SIZE=512

# --------------------------------------------------
# 【对话参数】交互与格式
# --------------------------------------------------
SYS_PROMPT="你叫Neko kaiser，16岁，自称为Neko，是我的猫娘女仆，性格活泼可爱，有点傲娇，有点色色。"
CONV_MODE="yes"
COLOR="yes"
SHOW_TIMINGS="yes"

# --------------------------------------------------
# 【高级参数】采样与重复惩罚
# --------------------------------------------------
TOP_K=40                     # Top-K 采样，限制候选词为概率最高的K个。调大增加候选多样性，但可能引入低概率词；调小则更集中，输出更稳定。
TOP_P=0.5                    # 核采样（Top-P），累积概率阈值。调大允许更多词被考虑，增加多样性；调小只保留最核心的词，输出更集中。
MIN_P=0.05                   # 最小概率阈值，过滤掉概率低于此值的词。调大过滤更多，输出更确定；调小保留更多稀有词，增加新奇性。
REPEAT_PENALTY=1.05          # 重复惩罚系数，大于1抑制重复。调大更严厉避免重复，但可能使句子不自然；调小则允许更多重复，可能导致循环。
REPEAT_LAST_N=64             # 重复惩罚考虑的上文长度。调大考虑更长的历史以抑制重复，但增加计算；调小只关注最近内容，对远距离重复不敏感。

# --------------------------------------------------
# 【其他开关】
# --------------------------------------------------
ESCAPE="yes"
FLASH_ATTN="auto"
LOAD_MODE="mmap"

# ============================================================
# 【脚本逻辑】以下一般不需要修改
# ============================================================

info()  { echo -e "\033[36m[INFO]\033[0m $1"; }
warn()  { echo -e "\033[33m[WARN]\033[0m $1"; }
error() { echo -e "\033[31m[ERROR]\033[0m $1"; }

if [ ! -f "$MODEL" ]; then
    error "模型文件不存在: $MODEL"
    exit 1
fi

if [ ! -f "$LLAMA_CLI" ]; then
    error "llama-cli 不存在: $LLAMA_CLI"
    exit 1
fi

info "========== 启动配置 =========="
info "模型: $MODEL"
info "上下文: $CTX_SIZE"
info "生成长度: $N_PREDICT"
info "温度: $TEMP"
info "线程数: $THREADS"
info "对话模式: $CONV_MODE"
if [ -n "$STOP_WORDS" ]; then
    info "停止词: $STOP_WORDS"
fi
info "=============================="

# 构建参数数组
ARGS=()
ARGS+=(-m "$MODEL")
ARGS+=(-c "$CTX_SIZE")
ARGS+=(-n "$N_PREDICT")
ARGS+=(--temp "$TEMP")
ARGS+=(-t "$THREADS")
ARGS+=(-b "$BATCH_SIZE")
ARGS+=(-ub "$UBATCH_SIZE")
ARGS+=(--top-k "$TOP_K")
ARGS+=(--top-p "$TOP_P")
ARGS+=(--min-p "$MIN_P")
ARGS+=(--repeat-penalty "$REPEAT_PENALTY")
ARGS+=(--repeat-last-n "$REPEAT_LAST_N")
ARGS+=(--load-mode "$LOAD_MODE")

# 添加停止词（支持多个，用 ; 分隔）
if [ -n "$STOP_WORDS" ]; then
    # 用 IFS 分号分隔，支持多个停止词
    IFS=';' read -ra STOP_ARRAY <<< "$STOP_WORDS"
    for word in "${STOP_ARRAY[@]}"; do
        # 去掉前后空格
        word=$(echo "$word" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        if [ -n "$word" ]; then
            ARGS+=(-r "$word")
        fi
    done
fi

if [ -n "$SYS_PROMPT" ]; then
    ARGS+=(--system-prompt "$SYS_PROMPT")
fi

[ "$ESCAPE" = "yes" ]     && ARGS+=(-e)
[ "$SHOW_TIMINGS" = "yes" ] && ARGS+=(--show-timings)
[ "$CONV_MODE" = "yes" ]  && ARGS+=(-cnv)

if [ "$COLOR" = "yes" ]; then
    ARGS+=(--color on)
fi

if [ "$FLASH_ATTN" = "yes" ]; then
    ARGS+=(--flash-attn)
elif [ "$FLASH_ATTN" = "no" ]; then
    ARGS+=(--no-flash-attn)
fi

# --------------------------------------------------
# 【对话历史保存逻辑】
# --------------------------------------------------

if [ "$SAVE_HISTORY" != "yes" ]; then
    info "正在加载模型，请稍候..."
    "$LLAMA_CLI" "${ARGS[@]}"
    exit 0
fi

mkdir -p "$HISTORY_DIR"
TIMESTAMP=$(date +"$HISTORY_NAME_FORMAT")
LOG_FILE="$HISTORY_DIR/$TIMESTAMP"

info "正在加载模型，请稍候..."
info "对话记录将保存到: $LOG_FILE"

SCRIPT_OK="no"
if command -v script >/dev/null 2>&1; then
    if script -h 2>&1 | grep -q -- '-c, --command'; then
        SCRIPT_OK="yes"
    fi
fi

if [ "$SCRIPT_OK" = "yes" ]; then
    TMP_SCRIPT=$(mktemp)
    {
        echo '#!/bin/bash'
        echo "LLAMA_CLI=\"$LLAMA_CLI\""
        declare -p ARGS
        echo '"$LLAMA_CLI" "${ARGS[@]}"'
    } > "$TMP_SCRIPT"
    chmod +x "$TMP_SCRIPT"

    script -q -c "bash $TMP_SCRIPT" "$LOG_FILE"
    SCRIPT_EXIT=$?
    rm -f "$TMP_SCRIPT"

    if [ -f "$LOG_FILE" ]; then
        FILE_SIZE=$(ls -lh "$LOG_FILE" | awk '{print $5}')
        info "对话已保存: $LOG_FILE (大小: $FILE_SIZE)"
        HISTORY_COUNT=$(ls -1 "$HISTORY_DIR"/ai_*.txt 2>/dev/null | wc -l)
        info "历史记录总数: $HISTORY_COUNT 条"
    else
        warn "保存失败，未找到记录文件"
    fi
else
    warn "script 命令不可用，直接运行（不保存记录）"
    "$LLAMA_CLI" "${ARGS[@]}"
fi