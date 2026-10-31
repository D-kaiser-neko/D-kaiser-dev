#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import sys
import json
import uuid
import os
import re

# 固定的工作根目录
ROOT_DIR = "/storage/emulated/0/termux"

def check_yt_dlp():
    """检查系统是否安装了 yt-dlp"""
    try:
        subprocess.run(['yt-dlp', '--version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def sanitize_filename(name):
    """移除文件名中的非法字符（Windows/Linux通用）"""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def get_video_title(url):
    """通过 yt-dlp --dump-json 获取视频标题"""
    try:
        result = subprocess.run(
            ['yt-dlp', '--dump-json', '--no-playlist', url],
            capture_output=True,
            text=True,
            check=True,
            timeout=30
        )
        data = json.loads(result.stdout.splitlines()[0])  # 可能有多行，取第一行
        title = data.get('title', '').strip()
        if title:
            return sanitize_filename(title)
        else:
            return None
    except Exception as e:
        print(f"警告：无法获取视频标题 ({e})，将使用随机文件名。")
        return None

def download_video(url, filename_template):
    """使用 yt-dlp 下载视频，并实现单行动态进度显示"""
    cmd = [
        'yt-dlp',
        '-f', 'bestvideo+bestaudio/best',  # 最高画质+音质，自动合并
        '--merge-output-format', 'mp4',     # 合并为 mp4（可根据需要修改或删除）
        '--progress',                        # 输出进度信息
        '-o', filename_template,
        url
    ]
    print(f"\n开始下载：{url}")
    print(f"输出模板：{filename_template}\n")

    # 启动子进程，捕获 stderr（yt-dlp 的进度信息默认输出到 stderr）
    process = subprocess.Popen(cmd, stderr=subprocess.PIPE, universal_newlines=True, bufsize=1)

    last_line_was_progress = False  # 标记上一行是否为进度行，用于控制换行

    for line in process.stderr:
        line = line.rstrip('\n')
        # 判断是否为进度行（通常以 [download] 开头）
        if line.startswith('[download]'):
            # 使用回车符覆盖当前行，不换行
            sys.stdout.write(f'\r{line}')
            sys.stdout.flush()
            last_line_was_progress = True
        else:
            # 如果不是进度行，先换行（如果上一行是进度行，则换行后再输出）
            if last_line_was_progress:
                sys.stdout.write('\n')
                last_line_was_progress = False
            print(line)  # 其他信息正常打印

    process.wait()
    # 确保最后有一个换行
    if last_line_was_progress:
        sys.stdout.write('\n')
        sys.stdout.flush()

    if process.returncode == 0:
        print("\n✅ 下载完成！")
    else:
        print(f"\n❌ 下载失败，返回码 {process.returncode}")

def main():
    if not check_yt_dlp():
        print("错误：未找到 yt-dlp，请先安装。")
        print("安装方法：pip install yt-dlp 或参考 https://github.com/yt-dlp/yt-dlp")
        sys.exit(1)

    # 检查根目录是否存在
    if not os.path.isdir(ROOT_DIR):
        print(f"错误：工作根目录不存在或无法访问 -> {ROOT_DIR}")
        sys.exit(1)

    # 获取用户输入的 URL
    url = input("URL=").strip()
    if not url:
        print("未输入 URL，退出。")
        sys.exit(0)

    # 尝试获取视频标题
    title = get_video_title(url)
    if title:
        filename = f"{title}.%(ext)s"
        print(f"使用视频标题作为文件名：{title}")
    else:
        # 生成随机字符串（UUID 的十六进制表示）
        random_str = uuid.uuid4().hex
        filename = f"video_{random_str}.%(ext)s"
        print(f"无法获取标题，使用随机文件名：video_{random_str}")

    # 组合为根目录下的绝对路径
    output_template = os.path.join(ROOT_DIR, filename)

    # 执行下载
    download_video(url, output_template)

if __name__ == "__main__":
    main()