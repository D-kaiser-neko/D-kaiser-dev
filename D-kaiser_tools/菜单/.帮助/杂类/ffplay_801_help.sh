echo 'FFplay 8.0.1 帮助文档 (中英文对照)
============================================================

ffplay version 8.0.1 Copyright (c) 2003-2025 the FFmpeg developers
FFplay 版本 8.0.1 版权所有 (c) 2003-2025 FFmpeg 开发者

built with Android (13624864, +pgo, +bolt, +lto, +mlgo, based on r530567e) 
clang version 19.0.1
使用 Android clang 19.0.1 编译

configuration: --prefix=/data/data/com.termux/files/usr/opt/ffplay 
--enable-cross-compile --target-os=android --enable-sdl --enable-xlib 
--enable-libpulse --enable-libxcb --enable-ffplay
配置: 支持 SDL 显示, X11, PulseAudio, XCB

============================================================
基本用法 / Basic Usage
============================================================

ffplay [options] input_file

简单媒体播放器
Simple media player

============================================================
常用示例 / Common Examples
============================================================

1. 播放视频 / Play video
   ffplay /storage/emulated/0/Movies/video.mp4

2. 指定窗口标题 / Set window title
   ffplay -window_title "My Video" video.mp4

3. 自动退出（播放完关闭）/ Auto exit
   ffplay -autoexit video.mp4

4. 循环播放 / Loop playback
   ffplay -loop 0 video.mp4

5. 全屏播放 / Fullscreen
   ffplay -fs video.mp4

6. 指定显示驱动（X11）/ Set video driver
   export SDL_VIDEODRIVER=x11
   ffplay video.mp4

7. 静音播放 / Mute
   ffplay -an video.mp4

8. 只播放视频（无音频）/ Video only
   ffplay -vn video.mp4

9. 指定分辨率 / Set resolution
   ffplay -x 1280 -y 720 video.mp4

10. 从指定位置开始播放 / Seek to position
    ffplay -ss 00:01:30 video.mp4

11. 播放网络流 / Play network stream
    ffplay http://example.com/stream.m3u8
    ffplay rtmp://example.com/live/stream

12. 播放时显示信息 / Show info
    ffplay -showmode 1 video.mp4

============================================================
常用选项 / Common Options
============================================================

基本选项 / Basic:
  -window_title <title>    设置窗口标题 / Set window title
  -autoexit                播放完自动退出 / Auto exit after playback
  -loop <number>           循环次数（0=无限）/ Loop count (0=infinite)
  -fs                      全屏 / Fullscreen
  -an                      禁用音频 / Disable audio
  -vn                      禁用视频 / Disable video
  -sn                      禁用字幕 / Disable subtitles
  -ss <position>           开始位置 / Start position (00:00:10 或 10s)
  -t <duration>            播放时长 / Duration
  -volume <n>              音量（0-100）/ Volume
  -f <fmt>                 强制格式 / Force format
  -codec <name>            强制编解码器 / Force codec
  -seek_interval <sec>     快进/后退间隔 / Seek interval

窗口选项 / Window:
  -x <width>               窗口宽度 / Window width
  -y <height>              窗口高度 / Window height
  -noborder                无边框窗口 / No window border
  -alwaysontop             置顶 / Always on top
  -left <x>                窗口X位置 / Window X position
  -top <y>                 窗口Y位置 / Window Y position

显示模式 / Display Mode (-showmode):
  -showmode 0              视频（默认）/ Video (default)
  -showmode 1              波形图 / Waveform
  -showmode 2              频谱图 / Spectrum

滤镜选项 / Filters:
  -vf <filter>             视频滤镜 / Video filter
  -af <filter>             音频滤镜 / Audio filter
  -sync <type>             同步类型（audio/video/ext）/ Sync type

调试选项 / Debug:
  -v <level>               日志级别 / Log level (quiet, panic, fatal, error, warning, info, verbose, debug)
  -stats                   显示统计信息 / Show statistics
  -debug <category>        调试类别 / Debug category
  -report                  生成报告 / Generate report

============================================================
播放控制快捷键 / Keyboard Shortcuts
============================================================

播放控制 / Playback:
  q, ESC                   退出 / Quit
  空格                     暂停/播放 / Pause/Play
  →                        快进10秒 / Seek forward 10s
  ←                        后退10秒 / Seek backward 10s
  ↑                        快进1分钟 / Seek forward 1min
  ↓                        后退1分钟 / Seek backward 1min
  PageUp                   快进10分钟 / Seek forward 10min
  PageDown                 后退10分钟 / Seek backward 10min

显示 / Display:
  f                        全屏切换 / Toggle fullscreen
  w                        切换显示模式 / Toggle show mode
  s                        激活帧步进 / Activate frame step
  鼠标右键                  切换显示模式 / Toggle show mode

音频 / Audio:
  a                        切换音频流 / Cycle audio stream
  v                        切换视频流 / Cycle video stream
  t                        切换字幕流 / Cycle subtitle stream
  m                        静音切换 / Toggle mute
  9, 0                     音量减/增 / Volume down/up
  /, *                     音量减/增 / Volume down/up

其他 / Others:
  p, S                     激活帧步进 / Activate frame step
  鼠标左键                  显示当前位置 / Show current position

============================================================
环境变量 / Environment Variables
============================================================

SDL_VIDEODRIVER            视频驱动（x11, wayland, android）
                           Video driver (x11, wayland, android)

SDL_AUDIODRIVER            音频驱动（pulseaudio, alsa, opensl）
                           Audio driver

DISPLAY                    X11 显示（:0）
                           X11 display

============================================================
视频滤镜示例 / Video Filter Examples
============================================================

1. 缩放 / Scale
   ffplay -vf "scale=1280:720" video.mp4

2. 旋转 / Rotate
   ffplay -vf "transpose=1" video.mp4

3. 裁剪 / Crop
   ffplay -vf "crop=800:600:100:100" video.mp4

4. 调整亮度/对比度 / Adjust brightness/contrast
   ffplay -vf "eq=brightness=0.1:contrast=1.2" video.mp4

5. 去色（黑白）/ Grayscale
   ffplay -vf "hue=s=0" video.mp4

6. 水平翻转 / Horizontal flip
   ffplay -vf "hflip" video.mp4

7. 垂直翻转 / Vertical flip
   ffplay -vf "vflip" video.mp4

8. 添加文字 / Add text
   ffplay -vf "drawtext=text='Hello':x=10:y=10" video.mp4

9. 模糊 / Blur
   ffplay -vf "boxblur=2:1" video.mp4

10. 锐化 / Sharpen
    ffplay -vf "unsharp" video.mp4

============================================================
音频滤镜示例 / Audio Filter Examples
============================================================

1. 调整音量 / Adjust volume
   ffplay -af "volume=2.0" video.mp4

2. 淡入淡出 / Fade in/out
   ffplay -af "afade=t=in:ss=0:d=5" video.mp4

3. 变速不变调 / Speed up without pitch change
   ffplay -af "atempo=2.0" video.mp4

4. 高通滤波 / High pass filter
   ffplay -af "highpass=f=200" video.mp4

5. 低通滤波 / Low pass filter
   ffplay -af "lowpass=f=3000" video.mp4

6. 回声 / Echo
   ffplay -af "aecho=0.8:0.9:1000:0.3" video.mp4

============================================================
实用技巧 / Tips
============================================================

1. 在 XFCE 中播放（推荐）
   export DISPLAY=:0
   export SDL_VIDEODRIVER=x11
   ffplay -window_title "Video" -autoexit video.mp4

2. 播放时隐藏控制台信息
   ffplay -loglevel quiet video.mp4
   ffplay -v quiet video.mp4

3. 强制指定格式
   ffplay -f mp4 video.mp4

4. 播放原始数据
   ffplay -f rawvideo -pixel_format yuv420p -video_size 1920x1080 input.yuv

5. 测试视频源（彩条）
   ffplay -f lavfi testsrc=duration=10:size=1280x720:rate=30

6. 测试音频源（正弦波）
   ffplay -f lavfi sine=frequency=1000:duration=5

7. 播放摄像头（需权限）
   ffplay -f android_camera -i 0:0

8. 播放屏幕录制（需root）
   ffplay -f x11grab -i :0.0

============================================================
与 FFmpeg 配合使用 / Work with FFmpeg
============================================================

1. 实时预览 FFmpeg 输出
   ffmpeg -i input.mp4 -f nut - | ffplay -

2. 录制同时预览
   ffmpeg -f x11grab -i :0.0 -f mp4 - | ffplay -

3. 转换时预览
   ffmpeg -i input.mp4 -vf "scale=640:360" -f nut - | ffplay -

============================================================
文档生成时间: 2025
============================================================
'