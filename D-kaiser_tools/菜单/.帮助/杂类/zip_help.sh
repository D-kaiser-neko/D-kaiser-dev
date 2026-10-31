echo 'Zip 3.0 帮助文档 (中英文对照)
============================================================

Copyright (c) 1990-2008 Info-ZIP - Type 'zip "-L"' for software license.
Zip 3.0 (July 5th 2008). 

用法 / Usage:
zip [-options] [-b path] [-t mmddyyyy] [-n suffixes] [zipfile list] [-xi list]

默认操作是从列表中添加或替换 zipfile 条目，
列表可以包含特殊名称 - 以压缩标准输入。
如果省略 zipfile 和列表，zip 将 stdin 压缩到 stdout。

The default action is to add or replace zipfile entries from list, which
can include the special name - to compress standard input.
If zipfile and list are omitted, zip compresses stdin to stdout.

============================================================
主要选项 / Main Options
============================================================

-f   freshen: only changed files
     刷新：仅处理已更改的文件

-u   update: only changed or new files
     更新：仅处理已更改或新增的文件

-d   delete entries in zipfile
     删除 zipfile 中的条目

-m   move into zipfile (delete OS files)
     移入 zipfile（删除操作系统原文件）

-r   recurse into directories
     递归进入子目录

-j   junk (don"t record) directory names
     忽略（不记录）目录名（所有文件平铺）

============================================================
压缩级别 / Compression Levels
============================================================

-0   store only
     仅存储（不压缩）

-1   compress faster
     快速压缩（压缩率低，速度快）

-9   compress better
     更好压缩（压缩率高，速度慢）

============================================================
输入输出控制 / Input/Output Control
============================================================

-@   read names from stdin
     从标准输入(stdin)读取文件名

-o   make zipfile as old as latest entry
     将 zipfile 时间戳设置为与最新条目相同

-q   quiet operation
     安静模式（不显示输出）

-v   verbose operation/print version info
     详细模式/打印版本信息

============================================================
文件处理 / File Handling
============================================================

-x   exclude the following names
     排除以下名称

-i   include only the following names
     仅包含以下名称

-n   don"t compress these suffixes
     不压缩这些后缀名的文件

-y   store symbolic links as the link instead of the referenced file
     将符号链接存储为链接本身，而不是引用的文件

============================================================
压缩包格式 / Archive Format
============================================================

-l   convert LF to CR LF (-ll CR LF to LF)
     将 LF 转换为 CR LF（-ll 将 CR LF 转换为 LF）
     [用于 Unix/Linux 和 Windows 换行符转换]

============================================================
注释与信息 / Comments and Info
============================================================

-c   add one-line comments
     添加单行注释

-z   add zipfile comment
     添加 zipfile 注释

============================================================
修复与测试 / Repair and Test
============================================================

-F   fix zipfile (-FF try harder)
     修复 zipfile（-FF 尝试更努力修复）

-T   test zipfile integrity
     测试 zipfile 完整性

============================================================
高级选项 / Advanced Options
============================================================

-b path
     指定临时 zip 文件的目录路径

-t mmddyyyy
     不处理早于指定日期的文件（月日年格式）

-D   do not add directory entries
     不添加目录条目

-A   adjust self-extracting exe
     调整自解压 exe 文件

-J   junk zipfile prefix (unzipsfx)
     忽略 zipfile 前缀（用于 unzipsfx）

-X   eXclude eXtra file attributes
     排除额外的文件属性

-e   encrypt
     加密

-h2  show more help
     显示更多帮助

-xi list
     排除/包含列表（与 -x 或 -i 一起使用）

============================================================
常用示例 / Common Examples
============================================================

1. 基础压缩（递归目录）
   zip -r archive.zip ./folder/

2. 快速压缩
   zip -r -1 fast.zip ./folder/

3. 最大压缩
   zip -r -9 best.zip ./folder/

4. 仅存储（不压缩，适合已压缩文件）
   zip -r -0 store.zip ./folder/

5. 排除特定文件
   zip -r archive.zip ./folder/ -x "*.tmp" -x "*.log"

6. 仅包含特定文件
   zip -r archive.zip ./folder/ -i "*.txt" -i "*.doc"

7. 移动文件（压缩后删除原文件）
   zip -r -m archive.zip ./folder/

8. 更新已更改的文件
   zip -r -u archive.zip ./folder/

9. 删除压缩包中的特定文件
   zip -d archive.zip "file.txt"

10. 平铺压缩（忽略目录结构）
    zip -r -j flat.zip ./folder/

11. 加密压缩
    zip -r -e secure.zip ./folder/

12. 测试压缩包完整性
    zip -T archive.zip

13. 修复损坏的压缩包
    zip -F broken.zip --out fixed.zip

14. 添加注释
    zip -z archive.zip
    [然后输入注释内容，按 Ctrl+D 结束]

15. 不压缩特定后缀
    zip -r -n ".jpg:.png:.gif" archive.zip ./folder/

16. 从 stdin 读取文件名列表
    find . -name "*.txt" | zip -@ archive.zip

17. 压缩标准输入到文件
    echo "hello" | zip archive.zip -

18. 设置日期过滤
    zip -r -t 01012024 archive.zip ./folder/
    [仅压缩 2024年1月1日之后修改的文件]

============================================================
选项对比 / Option Comparison
============================================================

添加 vs 更新 vs 刷新:
  无选项 : 添加所有文件（替换现有）
  -u     : 仅添加新文件或已更改的文件
  -f     : 仅更新已更改的文件（不添加新文件）

保留 vs 忽略目录结构:
  无选项 : 保留完整目录结构
  -j     : 忽略目录，所有文件平铺到根目录

保留 vs 删除原文件:
  无选项 : 保留原文件
  -m     : 移动（压缩后删除原文件）

============================================================
与 7z 命令对比 / Comparison with 7z
============================================================

功能                zip 命令                    7z 命令
------------------------------------------------------------
递归压缩            zip -r                      7z a -r
最大压缩            zip -9                      7z a -mx9
排除文件            zip -x                      7z a -x
包含文件            zip -i                      7z a -i
加密                zip -e                      7z a -p
分卷                不支持                      7z a -v
测试                zip -T                      7z t
删除原文件          zip -m                      7z a -sdel

============================================================
文档生成时间: 2024
============================================================
'