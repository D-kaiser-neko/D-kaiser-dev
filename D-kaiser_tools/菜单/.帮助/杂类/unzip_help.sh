echo 'UnZip 6.00 帮助文档 (中英文对照)
============================================================

UnZip 6.00 of 20 April 2009, by Info-ZIP.  Maintained by C. Spieler.  Send
bug reports using http://www.info-zip.org/zip-bug.html; see README for details.

版本信息：UnZip 6.00（2009年4月20日），由 Info-ZIP 开发，C. Spieler 维护。
发送错误报告请访问：http://www.info-zip.org/zip-bug.html；详情请参阅 README。

============================================================
用法 / Usage
============================================================

unzip [-Z] [-opts[modifiers]] file[.zip] [list] [-x xlist] [-d exdir]

Default action is to extract files in list, except those in xlist, to exdir;
file[.zip] may be a wildcard.  -Z => ZipInfo mode ("unzip -Z" for usage).

默认操作是解压列表中的文件（xlist 中的除外）到 exdir 目录；
file[.zip] 可以使用通配符。-Z => ZipInfo 模式（使用 "unzip -Z" 查看用法）。

============================================================
主要选项 / Main Options
============================================================

-p  extract files to pipe, no messages
    解压文件到管道，不显示消息（输出到 stdout）

-l  list files (short format)
    列出文件（简短格式）

-f  freshen existing files, create none
    刷新现有文件（更新已存在的），不创建新文件

-u  update files, create if necessary
    更新文件，必要时创建新文件

-t  test compressed archive data
    测试压缩包数据完整性

-z  display archive comment only
    仅显示压缩包注释

-v  list verbosely/show version info
    详细列出/显示版本信息

-T  timestamp archive to latest
    将压缩包时间戳设置为最新文件的时间

-x  exclude files that follow (in xlist)
    排除后续列出的文件（在 xlist 中）

-d  extract files into exdir
    解压文件到 exdir 目录

============================================================
修饰符 / Modifiers
============================================================

-n  never overwrite existing files
    从不覆盖现有文件

-o  overwrite files WITHOUT prompting
    覆盖文件而不提示确认

-q  quiet mode (-qq => quieter)
    安静模式（-qq 更安静）

-a  auto-convert any text files
    自动转换任何文本文件（换行符）

-aa treat ALL files as text
    将所有文件视为文本文件

-j  junk paths (do not make directories)
    忽略路径（不创建目录，所有文件平铺）

-U  use escapes for all non-ASCII Unicode
    对所有非 ASCII Unicode 字符使用转义序列

-UU ignore any Unicode fields
    忽略任何 Unicode 字段

-C  match filenames case-insensitively
    文件名匹配时不区分大小写

-L  make (some) names lowercase
    将（某些）文件名转换为小写

-X  restore UID/GID info
    恢复 UID/GID 信息（Unix/Linux 用户/组ID）

-V  retain VMS version numbers
    保留 VMS 版本号

-K  keep setuid/setgid/tacky permissions
    保留 setuid/setgid/sticky 权限

-M  pipe through "more" pager
    通过 "more" 分页器显示

============================================================
常用示例 / Common Examples
============================================================

1. 基础解压
   unzip archive.zip

2. 解压到指定目录
   unzip archive.zip -d ./output/

3. 列出压缩包内容（简短）
   unzip -l archive.zip

4. 列出压缩包内容（详细）
   unzip -v archive.zip

5. 测试压缩包完整性
   unzip -t archive.zip

6. 覆盖解压（不提示）
   unzip -o archive.zip

7. 从不覆盖（保留现有文件）
   unzip -n archive.zip

8. 更新模式（仅更新已存在的文件）
   unzip -u archive.zip

9. 刷新模式（仅更新已存在且较新的文件）
   unzip -f archive.zip

10. 排除特定文件
    unzip archive.zip -x "*.tmp" -x "*.log"

11. 仅解压特定文件
    unzip archive.zip "*.txt" "*.doc"

12. 平铺解压（忽略目录结构）
    unzip -j archive.zip

13. 解压到管道（查看文件内容）
    unzip -p archive.zip file.txt | cat

14. 仅显示压缩包注释
    unzip -z archive.zip

15. 安静解压
    unzip -q archive.zip

16. 转换文本文件换行符
    unzip -a archive.zip

17. 不区分大小写匹配
    unzip -C archive.zip "readme*"

18. 转换为小写文件名
    unzip -L archive.zip

19. 保留权限信息（Unix/Linux）
    unzip -X archive.zip

20. 通过 more 查看内容
    unzip -M archive.zip

============================================================
选项详解 / Option Details
============================================================

【解压模式对比】

无选项    : 解压所有文件，提示是否覆盖
-o        : 解压所有文件，覆盖现有文件（不提示）
-n        : 解压所有文件，从不覆盖现有文件
-u        : 更新模式：更新现有文件 + 创建新文件
-f        : 刷新模式：仅更新现有文件（不创建新文件）

【路径处理】

无选项    : 保留原始目录结构
-j        : 忽略所有路径，所有文件解压到当前目录
-d <dir>  : 解压到指定目录（保留目录结构）

【列表查看】

-l        : 简短列表（文件名、大小、时间）
-v        : 详细列表（包含压缩率、CRC等）
-z        : 仅显示压缩包注释

【文本处理】

无选项    : 不解压为文本文件
-a        : 自动识别并转换文本文件（CRLF/LF）
-aa       : 将所有文件视为文本文件进行转换

============================================================
与 7z/Zip 对比 / Comparison
============================================================

功能                unzip 命令                  7z/zip 对应命令
--------------------------------------------------------------------------------
基础解压            unzip file.zip              7z x file.7z / unzip file.zip
解压到指定目录      unzip -d ./dir/             7z x -o./dir/
列出内容            unzip -l/-v                 7z l / zip -l
测试完整性          unzip -t                    7z t / zip -T
覆盖不提示          unzip -o                    7z x -aoa
从不覆盖            unzip -n                    7z x -aos
更新模式            unzip -u                    7z x -ou
排除文件            unzip -x                    7z x -x / zip -x
忽略路径            unzip -j                    7z e / zip -j
安静模式            unzip -q                    7z -bd / zip -q

============================================================
ZipInfo 模式 / ZipInfo Mode
============================================================

使用 unzip -Z 进入 ZipInfo 模式，可查看压缩包详细信息：

unzip -Z archive.zip          # 显示文件列表
unzip -Z -l archive.zip       # 详细列表
unzip -Z -h                   # ZipInfo 帮助

============================================================
注意事项 / Notes
============================================================

1. 通配符使用：
   unzip archive.zip "*.txt"    # 仅解压 txt 文件
   unzip "*.zip"                # 解压所有 zip 文件

2. 特殊字符处理：
   如果文件名包含空格或特殊字符，使用引号包裹：
   unzip archive.zip "my file.txt"

3. 覆盖提示：
   默认情况下，unzip 会提示是否覆盖现有文件。
   使用 -o 自动覆盖，-n 从不覆盖，避免交互式提示。

4. 大文件处理：
   对于大压缩包，使用 -q 安静模式或 -M 分页模式提高可读性。

5. 权限保留：
   在 Unix/Linux 系统上，使用 -X 保留文件权限信息。

============================================================
文档生成时间: 2024
============================================================
'