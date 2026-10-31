import time
import hashlib
import requests
import json
import re
import os

class MusicKillerAPI:
    def __init__(self):
        # 真实后端 IP 和端口 (从 Smali 代码中提取)
        self.base_url = "http://119.3.221.4:8002"
        self.salt = "MusicKillerNativeSalt"
        self.version = "1"
        self.platform = "android"
        
        # 尝试使用 HAR 包中出现的域名作为 Host 头 (如果报错 400，需要替换为正确的域名)
        self.headers = {
            "User-Agent": "okhttp/4.11.0",
            "Host": "api-music.1fooai.com", # 待验证的 Host
            "Accept-Encoding": "gzip"
        }

    def generate_sign(self, timestamp):
        """
        根据 Smali 代码 t0() 方法还原的签名算法
        推测拼接顺序为: Salt + Timestamp + Version
        """
        raw_str = f"{self.salt}{timestamp}{self.version}"
        # MD5 哈希
        md5_hash = hashlib.md5(raw_str.encode('utf-8')).hexdigest()
        return md5_hash

    def get_headers(self):
        """生成带签名的动态请求头"""
        timestamp = str(int(time.time() * 1000)) # 毫秒级时间戳
        sign = self.generate_sign(timestamp)
        
        headers = self.headers.copy()
        headers.update({
            "Version": self.version,
            "Platform": self.platform,
            "Timestamp": timestamp,
            "Sign": sign
        })
        return headers

    def get_play_url(self, song_id, bridge="wy"):
        """
        获取播放链接 (对应 Smali 中的 g0 方法)
        :param song_id: 歌曲 ID
        :param bridge: 平台或音质标识 (待验证，暂设 wy 代表网易)
        """
        url = f"{self.base_url}/play/info"
        params = {
            "id": song_id,
            "bridge": bridge
        }
        
        print(f"[*] 请求真实 API: {url}?id={song_id}&bridge={bridge}")
        response = requests.get(url, params=params, headers=self.get_headers(), timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"[+] 成功获取 JSON 响应!")
            # 根据 Smali 代码，真实接口返回的是标准 JSON，包含 data -> url
            if data.get("code") == 0 and "data" in data:
                play_info = data["data"]
                if isinstance(play_info, dict) and "url" in play_info:
                    return play_info["url"]
                elif isinstance(play_info, str):
                     # 尝试解析嵌套 JSON
                     try:
                         inner_data = json.loads(play_info)
                         return inner_data.get("url")
                     except:
                         pass
            print("[-] JSON 结构解析失败，原始返回:", data)
        else:
            print(f"[-] 请求失败，状态码: {response.status_code}")
            print("[-] 响应内容:", response.text)
        return None

# ================= 测试代码 =================
if __name__ == "__main__":
    api = MusicKillerAPI()
    
    # 使用 HAR 包中抓到的网易云歌曲 ID 进行测试 (琪露诺的完美算术教室)
    test_id = "29163088" 
    
    print("--- 开始测试真实 API 连通性与签名算法 ---")
    url = api.get_play_url(test_id, bridge="wy")
    
    if url:
        print(f"\n[🎉 成功] 获取到 CDN 下载链接:\n{url}")
        print("\n[提示] 接下来可以使用支持 Range 的下载器 (如 IDM, aria2, 或 Python 多线程) 下载该 MP3/FLAC。")
    else:
        print("\n[❌ 失败] 请检查 Host 头是否正确，或抓包核对 Sign 的拼接顺序。")
