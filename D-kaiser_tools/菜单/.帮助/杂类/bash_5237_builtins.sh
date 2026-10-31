echo 'Bash 5.2.37 内部命令完整手册 (按字母表顺序排列)
============================================================

版本信息 / Version Info:
  GNU bash, version 5.2.37(1)-release (aarch64-unknown-linux-android)

说明 / Notes:
  - 这些是 Bash 内部定义的命令 (Shell Builtins)
  - 使用 `help 命令名` 查看具体命令详情
  - 使用 `info bash` 了解 Shell 一般信息
  - 使用 `man -k` 或 `info` 查看外部命令
  - 名称旁的星号 (*) 表示该命令已禁用

============================================================
符号类命令 / Symbol Commands
============================================================

. filename [arguments]
  Source/execute commands from file
  从文件读取并执行命令（同 source）

: 
  Null command (do nothing, return true)
  空命令（什么都不做，返回真）

[ arg... ]
  Test condition (same as test command)
  测试条件（同 test 命令）

[[ expression ]]
  Extended test command (supports pattern matching)
  扩展测试命令（支持模式匹配）

(( expression ))
  Evaluate arithmetic expression
  计算算术表达式

{ COMMANDS ; }
  Group commands (execute in current shell)
  命令分组（在当前 shell 中执行）

job_spec [&]
  Run command in background
  在后台运行命令

============================================================
A
============================================================

alias [-p] [name[=value] ... ]
  Define or display aliases
  定义或显示命令别名
  示例: alias ll='ls -la'

============================================================
B
============================================================

bg [job_spec ...]
  Resume suspended job in background
  后台继续执行挂起的作业
  示例: bg %1

bind [-lpsvPSVX] [-m keymap] [-f filename] [-q name] [-u function] [-r keyseq] [-x keyseq:shell-command] [keyseq:readline-function]
  Manage readline key bindings
  管理 readline 键绑定（快捷键设置）

break [n]
  Exit from for/while/until loop (N levels)
  跳出循环（可指定跳出 N 层）
  示例: break 2

builtin [shell-builtin [arg ...]]
  Execute shell builtin bypassing functions
  执行内部命令（绕过同名函数）

============================================================
C
============================================================

caller [expr]
  Return context of subroutine call
  返回子程序调用上下文（用于调试）

case WORD in [PATTERN [| PATTERN]...) COMMANDS ;;] ... esac
  Conditional branching (pattern matching)
  条件分支（多路模式匹配）
  示例:
    case $var in
      a) echo "A" ;;
      b) echo "B" ;;
      *) echo "Other" ;;
    esac

cd [-L|[-P [-e]] [-@]] [dir]
  Change current directory
  切换当前目录
  -L: 跟随符号链接（默认）
  -P: 使用物理目录
  示例: cd -P /tmp

command [-pVv] command [arg ...]
  Execute command bypassing aliases/functions
  执行命令（绕过别名和函数）
  -p: 使用默认 PATH
  -v: 显示命令位置
  -V: 详细显示

compgen [-abcdefgjksuv] [-o option] [-A action] [-G globpat] [-W wordlist] [-F function] [-C command] [-X filterpat] [-P prefix] [-S suffix] [word]
  Generate possible completion matches
  生成可能的补全匹配

complete [-abcdefgjksuv] [-pr] [-DEI] [-o option] [-A action] [-G globpat] [-W wordlist] [-F function] [-C command] [-X filterpat] [-P prefix] [-S suffix] [name ...]
  Specify how arguments are completed
  指定参数如何补全

compopt [-o|+o option] [-DEI] [name ...]
  Modify completion options for each name
  修改每个名称的补全选项

continue [n]
  Resume next iteration of loop (N levels)
  继续下一次循环迭代（可指定层数）

coproc [NAME] command [redirections]
  Create coprocess (background pipeline with I/O)
  创建协程（带输入输出的后台管道）
  示例: coproc MYPROC { while read line; do echo $line; done; }

============================================================
D
============================================================

declare [-aAfFgiIlnrtux] [name[=value] ...]
  Declare variables with attributes
  声明带属性的变量
  -a: 数组  -i: 整数  -r: 只读  -x: 导出  
  -f: 函数  -F: 仅函数名  -g: 全局

dirs [-clpv] [+N] [-N]
  Display directory stack
  显示目录栈
  -c: 清空  -l: 长格式  -p: 每行一个  -v: 带编号
  +N: 显示第N个（从左）  -N: 显示第N个（从右）

disown [-h] [-ar] [jobspec ... | pid ...]
  Remove job from job table
  从作业表移除作业（使作业不受 shell 控制）
  -h: 标记为不接收 SIGHUP  -a: 所有  -r: 运行中的

============================================================
E
============================================================

echo [-neE] [arg ...]
  Display arguments (output text)
  显示参数（输出文本）
  -n: 不换行  -e: 解释转义  -E: 不解释转义
  示例: echo -e "Line1\nLine2"

enable [-a] [-dnps] [-f filename] [name ...]
  Enable/disable shell builtins
  启用/禁用内部命令
  -a: 显示所有  -d: 禁用  -n: 禁用  -p: 显示  
  -s: 仅特殊  -f: 从文件加载

eval [arg ...]
  Evaluate arguments as shell command
  将参数作为 shell 命令执行
  示例: eval "echo $var"

exec [-cl] [-a name] [command [arguments ...]]
  Replace shell with command
  用命令替换当前 shell（不创建新进程）
  -c: 清空环境  -l: 作为登录 shell  -a name: 使用 name 作为 argv[0]
  示例: exec ls（执行后退出 shell）

exit [n]
  Exit shell with status N
  退出 shell（返回状态码 N，0=成功）
  示例: exit 0

export [-fn] [name[=value] ...] or export -p
  Set export attribute for variables (make environment variables)
  设置变量导出属性（使之成为环境变量）
  -f: 导出函数  -n: 移除导出属性  -p: 显示所有导出变量
  示例: export PATH=$PATH:/new/path

============================================================
F
============================================================

false
  Return failure status (1)
  返回失败状态（退出码 1，用于条件判断）
  示例: while false; do ...; done（永不执行）

fc [-e ename] [-lnr] [first] [last] or fc -s [pat=rep] [command]
  Fix/edit command history
  编辑/显示历史命令
  -e: 使用编辑器  -l: 列出  -n: 无编号  -r: 反向
  -s: 重新执行  first/last: 命令范围
  示例: fc -l -10（显示最近10条）

fg [job_spec]
  Resume job in foreground
  前台继续执行作业
  示例: fg %1

for NAME [in WORDS ... ] ; do COMMANDS; done
  Loop over list of words
  遍历单词列表循环
  示例: for i in 1 2 3; do echo $i; done

for (( exp1; exp2; exp3 )); do COMMANDS; done
  Arithmetic for loop (C-style)
  算术 for 循环（C语言风格）
  示例: for ((i=0; i<10; i++)); do echo $i; done

function name { COMMANDS ; } or name () { COMMANDS ; }
  Define shell function
  定义 shell 函数
  示例: function hello() { echo "Hello $1"; }

============================================================
G
============================================================

getopts optstring name [arg ...]
  Parse positional parameters (for options)
  解析位置参数（用于处理命令行选项）
  示例: while getopts "ab:c" opt; do case $opt in ... esac; done

============================================================
H
============================================================

hash [-lr] [-p pathname] [-dt] [name ...]
  Remember/forget command locations (PATH lookup cache)
  记住/忘记命令位置（PATH 查找缓存）
  -l: 显示  -r: 清空  -p: 指定路径  -d: 删除  -t: 显示路径
  示例: hash -r（清空缓存）

help [-dms] [pattern ...]
  Display help information about builtins
  显示内部命令的帮助信息
  -d: 简短描述  -m: 类似 man 格式  -s: 仅用法概要
  示例: help cd

history [-c] [-d offset] [n] or history -anrw [filename] or history -ps arg [arg...]
  Display/edit command history
  显示/编辑命令历史
  -c: 清空  -d: 删除指定行  -n: 读取新记录  
  -r: 读取文件  -w: 写入文件  -a: 追加  -p: 打印  -s: 添加记录
  示例: history -c（清空历史）

============================================================
I
============================================================

if COMMANDS; then COMMANDS; [ elif COMMANDS; then COMMANDS; ] ... [ else COMMANDS; ] fi
  Conditional execution
  条件执行（如果...那么...否则）
  示例: if [ -f file ]; then echo exists; else echo not found; fi

============================================================
J
============================================================

jobs [-lnprs] [jobspec ...] or jobs -x command [args]
  List active jobs
  列出活动作业
  -l: 显示进程ID  -n: 仅显示状态变化的  
  -p: 仅显示进程ID  -r: 仅运行中的  -s: 仅停止的
  -x: 执行命令前替换作业号
  示例: jobs -l

============================================================
K
============================================================

kill [-s sigspec | -n signum | -sigspec] pid | jobspec ... or kill -l [sigspec | exit_status]
  Send signal to process
  发送信号给进程
  -s: 信号名称  -n: 信号编号  -l: 列出信号
  示例: kill -9 1234（强制终止）

============================================================
L
============================================================

let arg [arg ...]
  Evaluate arithmetic expressions
  计算算术表达式（支持变量赋值）
  示例: let "a=5+3" 或 let a++

local [option] name[=value] ...
  Define local variables (in function)
  定义局部变量（仅在函数内有效）
  选项同 declare
  示例: local var=123

logout [n]
  Exit login shell
  退出登录 shell（非登录 shell 会报错）
  示例: logout

============================================================
M
============================================================

mapfile [-d delim] [-n count] [-O origin] [-s count] [-t] [-u fd] [-C callback] [-c quantum] [array]
  Read lines from input into array
  从输入读取行到数组
  -d: 指定分隔符  -n: 最多读取行数  -O: 起始索引  
  -s: 跳过行数  -t: 移除结尾分隔符  -u: 从文件描述符读取
  示例: mapfile -t lines < file.txt

============================================================
P
============================================================

popd [-n] [+N | -N]
  Remove directory from stack
  从目录栈移除目录并切换
  -n: 不切换目录  +N: 移除第N个（从左）  -N: 移除第N个（从右）
  示例: popd +0（移除当前）

printf [-v var] format [arguments]
  Format and print data (C-style)
  格式化并打印数据（C语言风格）
  -v: 输出到变量而非 stdout
  示例: printf "%s\n" "Hello"

pushd [-n] [+N | -N | dir]
  Add directory to stack and switch to it
  添加目录到栈并切换到该目录
  -n: 不切换目录  +N: 旋转到第N个  -N: 旋转到第N个  dir: 添加并切换
  示例: pushd /tmp

pwd [-LP]
  Print working directory
  打印当前工作目录
  -L: 显示逻辑路径（含符号链接，默认）
  -P: 显示物理路径（解析所有符号链接）

============================================================
R
============================================================

read [-ers] [-a array] [-d delim] [-i text] [-n nchars] [-N nchars] [-p prompt] [-t timeout] [-u fd] [name ...]
  Read line from input into variable(s)
  从输入读取行到变量
  -e: 使用 readline  -r: 不解释反斜杠  -s: 静默（密码输入）
  -a: 读取到数组  -d: 指定分隔符  -n: 读取N个字符  
  -N: 读取N个字符（必须）  -p: 显示提示  -t: 超时秒数  -u: 从文件描述符读取
  示例: read -p "Enter name: " name

readarray [-d delim] [-n count] [-O origin] [-s count] [-t] [-u fd] [-C callback] [-c quantum] [array]
  Read lines from input into array (synonym for mapfile)
  从输入读取行到数组（mapfile 的别名）

readonly [-aAf] [name[=value] ...] or readonly -p
  Mark variables/functions as readonly
  标记变量/函数为只读
  -a: 数组  -A: 关联数组  -f: 函数  -p: 显示所有只读变量
  示例: readonly var=value

return [n]
  Return from function/script with status N
  从函数/脚本返回（状态码 N）
  示例: return 0

============================================================
S
============================================================

select NAME [in WORDS ... ;] do COMMANDS; done
  Menu-driven loop (display numbered menu)
  菜单选择循环（显示编号菜单）
  示例: select choice in A B C; do echo $choice; done

set [-abefhkmnptuvxBCEHPT] [-o option-name] [--] [-] [arg ...]
  Set shell options and positional parameters
  设置 shell 选项和位置参数
  常用: -x（调试）  -e（错误退出）  -u（未定义变量报错）
  示例: set -x（开启调试模式）

shift [n]
  Shift positional parameters (left by N)
  移动位置参数（向左移动 N 个）
  $1 消失，$2 变为 $1，以此类推
  示例: shift 2

shopt [-pqsu] [-o] [optname ...]
  Toggle/set shell options
  切换/设置 shell 选项
  -p: 显示  -q: 静默（用于脚本判断）  -s: 启用  -u: 禁用  -o: 同 set -o
  示例: shopt -s extglob（启用扩展通配符）

source filename [arguments]
  Execute commands from file (same as .)
  从文件执行命令（同 . 命令）
  示例: source ~/.bashrc

============================================================
T
============================================================

suspend [-f]
  Suspend shell execution (send SIGSTOP)
  暂停 shell 执行（发送 SIGSTOP 信号）
  -f: 强制暂停（即使登录 shell）
  示例: suspend

test [expr] or [ expr ]
  Evaluate conditional expression
  评估条件表达式
  文件测试: -e(存在) -f(普通文件) -d(目录) -r(可读) -w(可写) -x(可执行)
  字符串: = != -z(空) -n(非空)
  数值: -eq -ne -lt -le -gt -ge
  逻辑: ! -a(and) -o(or)

time [-p] pipeline
  Time command execution
  计时命令执行
  -p: POSIX 格式输出（秒）
  示例: time ls -la

times
  Print accumulated user/system times
  打印累计用户/系统时间
  显示 shell 及其子进程使用的 CPU 时间

trap [-lp] [[arg] signal_spec ...]
  Set signal handlers
  设置信号处理程序
  -l: 列出信号  -p: 显示当前陷阱
  arg: 命令（空字符串忽略，- 重置默认）
  示例: trap "echo caught" INT

true
  Return success status (0)
  返回成功状态（退出码 0，用于条件判断）
  示例: while true; do ...; done（无限循环）

type [-afptP] name [name ...]
  Display command type
  显示命令类型
  -a: 所有位置  -f: 不查找函数  -p: 显示路径  
  -t: 类型别名  -P: 强制 PATH 搜索
  示例: type ls

typeset [-aAfFgiIlnrtux] name[=value] ...
  Declare variables (synonym for declare, obsolete)
  声明变量（declare 的别名，已过时）

============================================================
U
============================================================

ulimit [-SHabcdefiklmnpqrstuvxPRT] [limit]
  Set/get resource limits
  设置/获取资源限制
  -S: 软限制  -H: 硬限制
  -a: 显示所有  -f: 文件大小  -n: 打开文件数  -u: 最大进程数
  -v: 虚拟内存  -s: 栈大小
  示例: ulimit -n 2048（最大打开文件数）

umask [-p] [-S] [mode]
  Set file creation mask
  设置文件创建掩码（权限反码）
  -p: 可复用格式  -S: 符号格式
  示例: umask 022（文件权限 644，目录 755）

unalias [-a] name [name ...]
  Remove alias definitions
  移除别名定义
  -a: 移除所有
  示例: unalias ll

unset [-f] [-v] [-n] [name ...]
  Remove variable/function
  移除变量/函数
  -f: 函数  -v: 变量（默认）  -n: 变量引用
  示例: unset var

until COMMANDS; do COMMANDS-2; done
  Loop until condition is true
  直到条件为真时循环（至少执行一次）
  示例: until [ -f file ]; do sleep 1; done

============================================================
V
============================================================

variables
  Show some variable names and meanings
  显示一些变量名称和含义

============================================================
W
============================================================

wait [-fn] [-p var] [id ...]
  Wait for job completion
  等待作业完成
  -f: 等待直到作业被信号终止  
  -n: 等待任意作业状态变化
  -p: 将进程ID存入变量
  id: 作业号或进程ID
  示例: wait %1

while COMMANDS; do COMMANDS-2; done
  Loop while condition is true
  当条件为真时循环（可能一次都不执行）
  示例: while [ $i -lt 10 ]; do echo $i; ((i++)); done

============================================================
常用示例合集 / Common Examples
============================================================

1. 条件判断
   if [ -f file.txt ]; then
       echo "File exists"
   elif [ -d dir ]; then
       echo "Directory exists"
   else
       echo "Not found"
   fi

2. 循环
   # For 循环
   for i in 1 2 3; do echo $i; done
   for ((i=0; i<10; i++)); do echo $i; done

   # While 循环
   while [ $count -lt 10 ]; do
       ((count++))
   done

   # Until 循环
   until [ -f done.txt ]; do sleep 1; done

3. 函数定义
   myfunc() {
       local var="local value"
       echo "Parameter: $1"
       return 0
   }
   myfunc "argument"

4. Case 多路分支
   case $OSTYPE in
       linux*) echo "Linux" ;;
       darwin*) echo "macOS" ;;
       msys*|cygwin*) echo "Windows" ;;
       *) echo "Unknown" ;;
   esac

5. 数组操作
   declare -a arr=("a" "b" "c")
   echo ${arr[0]}      # 第一个元素
   echo ${arr[@]}      # 所有元素
   echo ${#arr[@]}     # 数组长度
   for item in "${arr[@]}"; do echo $item; done

6. 关联数组（Bash 4.0+）
   declare -A dict
   dict["name"]="John"
   dict["age"]=30
   echo ${dict["name"]}
   for key in "${!dict[@]}"; do echo "$key: ${dict[$key]}"; done

7. 输入输出重定向
   command > file.txt    # 覆盖输出
   command >> file.txt   # 追加输出
   command 2> error.log  # 错误输出
   command &> all.log    # 全部输出
   command < input.txt   # 输入重定向

8. 管道与进程替换
   cat file.txt | grep "pattern"
   grep "pattern" <(ls -la)
   diff <(sort file1) <(sort file2)

9. 后台与作业控制
   command &             # 后台运行
   jobs                  # 查看作业
   fg %1                 # 前台继续
   bg %1                 # 后台继续
   kill %1               # 终止作业
   wait                  # 等待所有后台作业

10. 调试脚本
    set -x               # 开启调试（显示执行的每条命令）
    set +x               # 关闭调试
    bash -x script.sh    # 调试运行脚本

============================================================
特殊变量 / Special Variables
============================================================

$0       脚本名称
$1-$9    位置参数（第1-9个参数）
${10}+   第10个及以上参数（需大括号）
$#       参数个数
$@       所有参数（数组形式，推荐）
$*       所有参数（字符串形式）
$?       上一个命令的退出状态
$$       当前进程ID
$!       最后一个后台进程ID
$-       当前shell选项
$_       上一个命令的最后一个参数

============================================================
文档生成时间: 2024
============================================================
'