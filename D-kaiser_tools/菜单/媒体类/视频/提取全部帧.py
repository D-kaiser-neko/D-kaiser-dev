import os
import subprocess
import sys
import re

# ====== 配置区域 ======
ROOT_DIR = "/storage/emulated/0/termux"  # 工作根目录
search_path = ROOT_DIR                   # 视频搜索路径
output_base = os.path.join(ROOT_DIR, 'output_png')  # 输出根文件夹
video_extensions = ('.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.3gp', '.m4v')
# =====================

def check_ffmpeg():
    """检查 ffmpeg 和 ffprobe 是否可用"""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        subprocess.run(['ffprobe', '-version'], capture_output=True, check=True)
        return True
    except:
        return False

def get_total_frames(video_path):
    """使用 ffprobe 获取视频总帧数"""
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-select_streams', 'v:0',
        '-count_packets',
        '-show_entries', 'stream=nb_read_packets',
        '-of', 'default=nokey=1:noprint_wrappers=1',
        video_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        frames = int(result.stdout.strip())
        return frames
    except:
        return None  # 无法获取帧数

def find_video_files(path):
    """递归搜索目录下所有视频文件"""
    video_files = []
    for root, dirs, files in os.walk(path):
        for file in files:
            if file.lower().endswith(video_extensions):
                full_path = os.path.join(root, file)
                video_files.append(full_path)
    return video_files

def extract_frames(video_path, output_dir):
    """调用 FFmpeg 提取所有帧为 PNG，并显示进度"""
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    out_folder = os.path.join(output_dir, video_name)
    os.makedirs(out_folder, exist_ok=True)

    print(f"🎬 处理视频: {video_name}")
    print(f"📁 输出目录: {out_folder}")

    # 获取总帧数（用于百分比）
    total_frames = get_total_frames(video_path)
    if total_frames:
        print(f"📊 总帧数: {total_frames}")
    else:
        print("⚠️ 无法获取总帧数，将只显示已处理帧数")

    # 构建 ffmpeg 命令
    cmd = [
        'ffmpeg',
        '-i', video_path,
        '-vsync', '0',              # 避免丢帧
        os.path.join(out_folder, 'frame_%06d.png')
    ]

    # 启动进程并捕获 stderr
    process = subprocess.Popen(cmd, stderr=subprocess.PIPE, universal_newlines=True, bufsize=1)

    # 解析 stderr 中的进度信息
    frame_pattern = re.compile(r'frame=\s*(\d+)')
    current_frame = 0

    for line in process.stderr:
        match = frame_pattern.search(line)
        if match:
            current_frame = int(match.group(1))
            if total_frames:
                percent = (current_frame / total_frames) * 100
                bar = '█' * int(percent // 2) + '░' * (50 - int(percent // 2))  # 简单进度条
                sys.stdout.write(f'\r⏳ 进度: {bar} {percent:.1f}% ({current_frame}/{total_frames})')
            else:
                sys.stdout.write(f'\r⏳ 已提取帧数: {current_frame}')
            sys.stdout.flush()

    process.wait()
    print()  # 换行
    if process.returncode == 0:
        print(f"✅ 完成: {video_name} 帧提取完毕\n")
    else:
        print(f"❌ 处理失败: {video_name} (ffmpeg 返回错误)\n")

def main():
    if not check_ffmpeg():
        print("❌ ffmpeg 或 ffprobe 未安装或无法运行，请先安装 FFmpeg")
        return

    # 检查根目录是否存在
    if not os.path.isdir(ROOT_DIR):
        print(f"❌ 工作根目录不存在或无法访问: {ROOT_DIR}")
        return

    videos = find_video_files(search_path)
    if not videos:
        print(f"🔍 在 {search_path} 中未找到任何视频文件")
        return

    print(f"🔍 找到 {len(videos)} 个视频文件：")
    for v in videos:
        print(f"   {v}")

    ans = input("\n是否开始提取所有视频帧？(y/n): ").strip().lower()
    if ans != 'y':
        print("已取消")
        return

    os.makedirs(output_base, exist_ok=True)

    for video in videos:
        extract_frames(video, output_base)

    print("🎉 全部任务完成！")

if __name__ == '__main__':
    main()