echo '提取视频音频
ffmpeg -i 视频.mp4 -vn -c:a copy 音频.m4a
播放视频
ffplay 路径
'