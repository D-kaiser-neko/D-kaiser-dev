echo 'FFmpeg 8.0.1 帮助文档 (中英文对照)
============================================================

ffmpeg version 8.0.1 Copyright (c) 2000-2025 the FFmpeg developers
FFmpeg 版本 8.0.1 版权所有 (c) 2000-2025 FFmpeg 开发者

built with Android (13989888, +pgo, +bolt, +lto, +mlgo, based on r563880c) 
clang version 21.0.0
使用 Android clang 21.0.0 编译

configuration: --arch=aarch64 --enable-cross-compile --enable-gpl 
--enable-version3 --enable-jni --enable-mediacodec --enable-vulkan ...
配置: 支持 aarch64 架构, 交叉编译, GPL协议, 第3版, JNI, 
MediaCodec硬解, Vulkan, 以及众多编解码器

============================================================
基本用法 / Basic Usage
============================================================

ffmpeg [options] [[infile options] -i infile]... {[outfile options] outfile}...

通用媒体转换器
Universal media converter

使用 -h 获取完整帮助
Use -h to get full help

============================================================
常用示例 / Common Examples
============================================================

1. 视频格式转换 / Convert video format
   ffmpeg -i input.mp4 output.avi

2. 提取音频 / Extract audio
   ffmpeg -i video.mp4 -vn -acodec copy audio.aac
   ffmpeg -i video.mp4 -vn audio.mp3

3. 提取视频（无声）/ Extract video (no audio)
   ffmpeg -i input.mp4 -an -vcodec copy output.mp4

4. 压缩视频 / Compress video
   ffmpeg -i input.mp4 -crf 23 output.mp4
   ffmpeg -i input.mp4 -b:v 1M output.mp4

5. 改变分辨率 / Change resolution
   ffmpeg -i input.mp4 -s 1280x720 output.mp4
   ffmpeg -i input.mp4 -vf "scale=1920:1080" output.mp4

6. 改变帧率 / Change frame rate
   ffmpeg -i input.mp4 -r 30 output.mp4

7. 截取视频片段 / Cut video segment
   ffmpeg -i input.mp4 -ss 00:01:00 -t 30 -c copy output.mp4
   ffmpeg -i input.mp4 -ss 00:01:00 -to 00:02:00 -c copy output.mp4

8. 合并视频 / Concatenate videos
   ffmpeg -f concat -i filelist.txt -c copy output.mp4
   # filelist.txt 格式:
   # file 'video1.mp4'
   # file 'video2.mp4'

9. 添加水印 / Add watermark
   ffmpeg -i input.mp4 -i logo.png -filter_complex "overlay=10:10" output.mp4

10. 旋转视频 / Rotate video
    ffmpeg -i input.mp4 -vf "transpose=1" output.mp4
    # 0=90度逆时针, 1=90度顺时针, 2=90度顺时针+垂直翻转, 3=90度逆时针+垂直翻转

11. 截图 / Screenshot
    ffmpeg -i input.mp4 -ss 00:00:10 -vframes 1 output.jpg
    ffmpeg -i input.mp4 -vf fps=1/10 output_%03d.jpg

12. 录制屏幕（Android需root）/ Record screen
    ffmpeg -f android_camera -i 0:0 output.mp4

13. 视频转GIF / Video to GIF
    ffmpeg -i input.mp4 -vf "fps=10,scale=480:-1:flags=lanczos" output.gif

14. 添加字幕 / Add subtitles
    ffmpeg -i input.mp4 -vf "subtitles=subtitle.srt" output.mp4

15. 调整音量 / Adjust volume
    ffmpeg -i input.mp4 -af "volume=2.0" output.mp4

============================================================
常用选项 / Common Options
============================================================

-i <file>          输入文件 / Input file
-o <file>          输出文件 / Output file
-c copy            直接复制，不重新编码 / Copy without re-encoding
-c:v <codec>       视频编解码器 / Video codec (libx264, libx265, copy)
-c:a <codec>       音频编解码器 / Audio codec (aac, mp3, copy)
-vn                禁用视频 / Disable video
-an                禁用音频 / Disable audio
-sn                禁用字幕 / Disable subtitles
-ss <time>         开始时间 / Start time (00:00:10 或 10s)
-to <time>         结束时间 / End time
-t <duration>      持续时间 / Duration
-r <fps>           帧率 / Frame rate
-s <WxH>           分辨率 / Resolution
-b:v <bitrate>     视频比特率 / Video bitrate (1M, 500k)
-b:a <bitrate>     音频比特率 / Audio bitrate (128k, 192k)
-ar <rate>         音频采样率 / Audio sample rate (44100, 48000)
-ac <channels>     音频通道数 / Audio channels (1, 2)
-vf <filter>       视频滤镜 / Video filter
-af <filter>       音频滤镜 / Audio filter
-preset <preset>   编码预设 / Encoding preset (ultrafast, fast, medium, slow)
-crf <value>       恒定质量 / Constant quality (0-51, 越小越好, 23默认)
-y                 覆盖输出文件 / Overwrite output
-n                 不覆盖 / Do not overwrite
-threads <n>       线程数 / Number of threads
-hwaccel <method>  硬件加速 / Hardware acceleration (mediacodec, vulkan)

============================================================
视频滤镜 / Video Filters (-vf)
============================================================

scale=1920:1080           缩放 / Scale
scale=1280:-1             按比例缩放 / Scale keeping aspect
crop=1280:720:0:0         裁剪 / Crop
rotate=PI/2               旋转 / Rotate
transpose=1               转置 / Transpose
fps=30                    改变帧率 / Change FPS
format=pix_fmts=yuv420p   像素格式 / Pixel format
hue=s=0                   去色（黑白）/ Desaturate
lutyuv=y=negval           反色 / Negate
hflip                     水平翻转 / Horizontal flip
vflip                     垂直翻转 / Vertical flip
drawtext=text='Hello'     添加文字 / Add text
overlay=10:10             叠加图片 / Overlay

============================================================
音频滤镜 / Audio Filters (-af)
============================================================

volume=2.0                音量加倍 / Double volume
volume=0.5                音量减半 / Half volume
atempo=2.0                加速2倍 / Speed up 2x
atempo=0.5                减速一半 / Slow down
highpass=f=200            高通滤波 / High pass
lowpass=f=3000            低通滤波 / Low pass
aecho=0.8:0.9:1000:0.3   回声 / Echo

============================================================
编解码器 / Codecs
============================================================

视频 / Video:
  libx264       H.264/AVC (最常用)
  libx265       H.265/HEVC (高效压缩)
  libvpx-vp9    VP9 (Google)
  libaom-av1    AV1 (新一代)
  mpeg4         MPEG-4
  copy          直接复制

音频 / Audio:
  aac           AAC (推荐)
  libmp3lame    MP3
  libopus       Opus (高效)
  libvorbis     Vorbis
  flac          FLAC (无损)
  copy          直接复制

容器 / Container:
  mp4           MP4
  mkv           Matroska
  avi           AVI
  mov           QuickTime
  webm          WebM
  flv           FLV
  gif           GIF

============================================================
硬件加速 / Hardware Acceleration
============================================================

Android MediaCodec:
  ffmpeg -hwaccel mediacodec -i input.mp4 output.mp4
  ffmpeg -c:v h264_mediacodec -i input.mp4 output.mp4

Vulkan:
  ffmpeg -hwaccel vulkan -i input.mp4 output.mp4

============================================================
实用技巧 / Tips
============================================================

1. 快速查看视频信息
   ffmpeg -i video.mp4

2. 只查看时长（配合grep）
   ffmpeg -i video.mp4 2>&1 | grep Duration

3. 批量转换
   for f in *.mp4; do ffmpeg -i "$f" "${f%.mp4}.avi"; done

4. 压制高质量视频
   ffmpeg -i input.mp4 -c:v libx264 -preset slow -crf 18 output.mp4

5. 压制小体积视频
   ffmpeg -i input.mp4 -c:v libx264 -preset fast -crf 28 -s 1280x720 output.mp4

6. 提取封面图
   ffmpeg -i input.mp4 -ss 00:00:01 -vframes 1 cover.jpg

7. 转换音频格式
   ffmpeg -i input.mp3 -c:a aac output.m4a

8. 去除水印（模糊处理）
   ffmpeg -i input.mp4 -vf "delogo=x=10:y=10:w=100:h=50" output.mp4

============================================================
文档生成时间: 2025
============================================================
'