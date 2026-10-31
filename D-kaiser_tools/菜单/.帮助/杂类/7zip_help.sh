echo '7-Zip [64] 17.05 帮助文档 (中英文对照)
============================================================

7-Zip [64] 17.05 : Copyright (c) 1999-2021 Igor Pavlov : 2017-08-28
p7zip Version 17.05 (locale=utf8, Utf16=on, HugeFiles=on, 64 bits, 8 CPUs LE)

用法 / Usage:
  7z <命令> [<选项>...] <压缩包名> [<文件名>...]
  7z <command> [<switches>...] <archive_name> [<file_names>...]

============================================================
命令列表 / Commands
============================================================

a : Add files to archive
   添加文件到压缩包

b : Benchmark
   性能测试/基准测试

d : Delete files from archive
   从压缩包中删除文件

e : Extract files from archive (without using directory names)
   解压文件（不使用目录名，所有文件平铺到当前目录）

h : Calculate hash values for files
   计算文件的哈希值

i : Show information about supported formats
   显示支持的格式信息

l : List contents of archive
   列出压缩包内容

rn : Rename files in archive
   重命名压缩包内的文件

t : Test integrity of archive
   测试压缩包完整性

u : Update files to archive
   更新压缩包中的文件

x : eXtract files with full paths
   解压文件（保留完整路径）

============================================================
选项列表 / Switches
============================================================

-- : Stop switches parsing
   停止解析选项（后续内容视为文件名）

@listfile : set path to listfile that contains file names
   设置包含文件名的列表文件路径

-ai[r[-|0]]{@listfile|!wildcard} : Include archives
   包含压缩包

-ax[r[-|0]]{@listfile|!wildcard} : eXclude archives
   排除压缩包

-ao{a|s|t|u} : set Overwrite mode
   设置覆盖模式
     a = All (覆盖所有)
     s = Skip (跳过现有文件)
     t = auto-rename existing (自动重命名现有文件)
     u = auto-rename extracting (自动重命名正在解压的文件)

-an : disable archive_name field
   禁用压缩包名字段

-bb[0-3] : set output log level
   设置输出日志级别 (0=无, 1=错误, 2=警告, 3=信息)

-bd : disable progress indicator
   禁用进度指示器

-bs{o|e|p}{0|1|2} : set output stream for output/error/progress line
   设置输出流 (o=输出, e=错误, p=进度; 0=禁用, 1=stdout, 2=stderr)

-bt : show execution time statistics
   显示执行时间统计

-i[r[-|0]]{@listfile|!wildcard} : Include filenames
   包含文件名

-m{Parameters} : set compression Method
   设置压缩方法

  -mmt[N] : set number of CPU threads
     设置CPU线程数 (N=1-最大核心数, 默认=最大)

  -mx[N] : set compression level: -mx1 (fastest) ... -mx9 (ultra)
     设置压缩级别: -mx1 (最快) ... -mx9 (最大压缩)

-o{Directory} : set Output directory
   设置输出目录

-p{Password} : set Password
   设置密码

-r[-|0] : Recurse subdirectories
   递归子目录 (-r开启, -r-关闭)

-sa{a|e|s} : set Archive name mode
   设置压缩包命名模式

-scc{UTF-8|WIN|DOS} : set charset for console input/output
   设置控制台输入/输出字符集

-scs{UTF-8|UTF-16LE|UTF-16BE|WIN|DOS|{id}} : set charset for list files
   设置列表文件字符集

-scrc[CRC32|CRC64|SHA1|SHA256|*] : set hash function for x, e, h commands
   设置哈希函数 (用于x, e, h命令)

-sdel : delete files after compression
   压缩后删除原文件

-seml[.] : send archive by email
   通过邮件发送压缩包

-sfx[{name}] : Create SFX archive
   创建自解压压缩包

-si[{name}] : read data from stdin
   从标准输入(stdin)读取数据

-slp : set Large Pages mode
   设置大页面模式

-slt : show technical information for l (List) command
   显示l(列表)命令的技术信息

-snh : store hard links as links
   将硬链接存储为链接

-snl : store symbolic links as links
   将符号链接存储为链接

-sni : store NT security information
   存储NT安全信息

-sns[-] : store NTFS alternate streams
   存储NTFS备用数据流

-so : write data to stdout
   将数据写入标准输出(stdout)

-spd : disable wildcard matching for file names
   禁用文件名的通配符匹配

-spe : eliminate duplication of root folder for extract command
   消除解压命令的根文件夹重复

-spf : use fully qualified file paths
   使用完整限定文件路径

-ssc[-] : set sensitive case mode
   设置大小写敏感模式

-ssw : compress shared files
   压缩共享文件（可能被其他程序打开）

-stl : set archive timestamp from the most recently modified file
   从最近修改的文件设置压缩包时间戳

-stm{HexMask} : set CPU thread affinity mask (hexadecimal number)
   设置CPU线程亲和性掩码（十六进制数）

-stx{Type} : exclude archive type
   排除压缩包类型

-t{Type} : Set type of archive
   设置压缩包类型 (7z, zip, tar, gz, bz2, xz 等)

-u[-][p#][q#][r#][x#][y#][z#][!newArchiveName] : Update options
   更新选项

-v{Size}[b|k|m|g] : Create volumes
   创建分卷 (b=字节, k=KB, m=MB, g=GB)
   例: -v100m = 每卷100MB

-w[{path}] : assign Work directory. Empty path means a temporary directory
   设置工作目录（空路径表示临时目录）

-x[r[-|0]]{@listfile|!wildcard} : eXclude filenames
   排除文件名

-y : assume Yes on all queries
   对所有询问假设为"是"（自动确认）

============================================================
常用示例 / Common Examples
============================================================

1. 基础压缩（递归所有子目录）
   7z a -r archive.7z ./folder/

2. 最大压缩级别
   7z a -r -mx9 archive.7z ./folder/

3. 快速压缩（1级，多线程）
   7z a -r -mx1 -mmt8 fast.7z ./folder/

4. 解压到当前目录（保留路径）
   7z x archive.7z

5. 解压到指定目录
   7z x archive.7z -o./output/

6. 解压并覆盖所有（不提示）
   7z x archive.7z -o./output/ -aoa

7. 解压平铺（不保留目录结构）
   7z e archive.7z

8. 带密码压缩
   7z a -p -r encrypted.7z ./folder/

9. 分卷压缩（每卷100MB）
   7z a -v100m -r archive.7z ./folder/

10. 排除特定文件
    7z a -r archive.7z ./folder/ -x!*.tmp -x!*.log

11. 测试压缩包完整性
    7z t archive.7z

12. 列出详细内容
    7z l -slt archive.7z

13. 更新压缩包中的文件
    7z u archive.7z newfile.txt

14. 删除压缩包中的文件
    7z d archive.7z file.txt

15. 从stdin创建压缩包
    tar cf - ./folder/ | 7z a -si backup.tar.7z

16. 解压到stdout
    7z x archive.7z -so > output.txt

============================================================
覆盖模式详解 / Overwrite Modes
============================================================

-aoa : 覆盖所有现有文件（不提示）
-aos : 跳过现有文件
-aot : 自动重命名现有文件 (target.txt -> target_1.txt)
-aou : 自动重命名正在解压的文件

============================================================
压缩级别 / Compression Levels
============================================================

-mx0 : 不压缩（仅存储）
-mx1 : 最快（低压缩率）
-mx3 : 快速
-mx5 : 正常（默认）
-mx7 : 最大
-mx9 : 极限（最高压缩率，最慢）

============================================================
文档生成时间: 2024
============================================================
'