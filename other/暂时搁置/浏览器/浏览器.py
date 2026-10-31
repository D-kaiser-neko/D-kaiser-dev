#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import json
import math
import re
import sys
import time
from collections import defaultdict, Counter, deque
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urljoin, urlunparse, urldefrag
from urllib.robotparser import RobotFileParser

try:
    import requests
    from bs4 import BeautifulSoup
    import jieba
except ImportError as e:
    print("缺少依赖:", e)
    print("请先执行: python -m pip install requests beautifulsoup4 jieba")
    sys.exit(1)


# =====================
# 基础配置 (升级版：防 403)
# =====================

BASE_DIR = Path.home() / ".minisearch"
DOCS_FILE = BASE_DIR / "docs.json"
INDEX_FILE = BASE_DIR / "index.json"

BASE_DIR.mkdir(parents=True, exist_ok=True)

# 尝试使用 cloudscraper 绕过基础反爬，如果没安装则退回普通 requests
try:
    import cloudscraper
    SESSION = cloudscraper.create_scraper()
    print("[提示] 已启用 cloudscraper 绕过基础反爬")
except ImportError:
    SESSION = requests.Session()
    print("[警告] 未安装 cloudscraper，容易被 403 拦截。建议执行: pip install cloudscraper")

# 伪装成真实的 Chrome 浏览器
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0"
})

# 常见停用词
STOPWORDS = {
    "的", "了", "是", "在", "和", "与", "及", "或", "也", "都", "就",
    "而", "又", "对", "于", "从", "到", "为", "以", "按", "把", "被",
    "让", "向", "往", "这", "那", "这些", "那些", "有", "无", "没",
    "我们", "你们", "他们", "她们", "它们", "自己", "什么", "怎么",
    "如何", "可以", "可能", "需要", "因为", "所以", "但是", "如果",
    "虽然", "然后", "因此", "以及", "并", "并且", "还", "很", "更",
    "最", "请", "你", "我", "他", "她", "它", "大家", "一个", "一些",
    "一样", "这样", "那样", "就是", "不是", "没有", "知道", "觉得",
    "时候", "东西", "问题", "内容", "页面", "网站",

    "the", "a", "an", "of", "to", "in", "on", "for", "and", "or",
    "is", "are", "was", "were", "be", "with", "as", "by", "at",
    "this", "that", "it", "its", "from", "but", "not", "you",
    "we", "they", "he", "she", "i"
}

# 默认跳过这些文件类型
SKIP_EXT = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg",
    ".pdf", ".zip", ".gz", ".tar", ".rar", ".7z",
    ".mp3", ".mp4", ".avi", ".mov", ".wav", ".flac",
    ".exe", ".apk", ".dmg", ".iso",
    ".css", ".js"
}

ROBOTS_CACHE = {}


# =====================
# 工具函数
# =====================

def load_json(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"读取 {path} 失败: {e}")
            return default
    return default


def save_json(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    tmp.replace(path)


def clean_text(text):
    if not text:
        return ""
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_url(url):
    """
    规范化 URL。
    默认去掉 #锚点 和 ?查询参数，避免爬到很多重复参数页。
    如果你需要保留查询参数，可以自己修改。
    """
    if not url:
        return None

    url, _ = urldefrag(url)
    p = urlparse(url)

    if p.scheme not in ("http", "https") or not p.netloc:
        return None

    path = p.path or "/"
    if len(path) > 1:
        path = path.rstrip("/")

    if not path:
        path = "/"

    return urlunparse((
        p.scheme.lower(),
        p.netloc.lower(),
        path,
        "",
        "",
        ""
    ))


def has_skip_ext(url):
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in SKIP_EXT)


def can_fetch(url):
    """
    简单检查 robots.txt。
    如果获取 robots.txt 失败，则默认允许。
    """
    p = urlparse(url)
    robots_url = f"{p.scheme}://{p.netloc}/robots.txt"

    if robots_url not in ROBOTS_CACHE:
        try:
            r = SESSION.get(robots_url, timeout=10)
            if r.status_code == 200:
                rp = RobotFileParser()
                rp.parse(r.text.splitlines())
                ROBOTS_CACHE[robots_url] = rp
            else:
                ROBOTS_CACHE[robots_url] = None
        except Exception:
            ROBOTS_CACHE[robots_url] = None

    rp = ROBOTS_CACHE.get(robots_url)
    if rp is None:
        return True

    try:
        return rp.can_fetch(UA, url)
    except Exception:
        return True


def tokenize(text):
    """
    中文分词。
    这里使用 jieba。
    """
    if not text:
        return []

    words = jieba.lcut(text.lower())
    result = []

    for w in words:
        w = w.strip()
        if not w:
            continue

        if w in STOPWORDS:
            continue

        # 至少包含中文、英文或数字
        if not re.search(r"[\u4e00-\u9fffA-Za-z0-9]", w):
            continue

        result.append(w)

    return result


def parse_page(html, base_url):
    """
    解析网页，返回：
    标题、描述、正文、链接列表
    """
    soup = BeautifulSoup(html, "html.parser")

    # 标题
    title = ""
    if soup.title:
        title = soup.title.get_text(strip=True)

    # meta description
    desc = ""
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        desc = meta["content"].strip()

    # 提取链接
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href:
            continue

        low = href.lower()
        if low.startswith(("javascript:", "mailto:", "tel:", "ftp:", "#")):
            continue

        full = urljoin(base_url, href)
        norm = normalize_url(full)
        if norm:
            links.append(norm)

    # 删除无用标签
    for tag in soup.find_all(["script", "style", "noscript", "iframe"]):
        tag.decompose()

    text = soup.get_text(" ", strip=True)
    text = clean_text(text)

    return title, desc, text, links


# =====================
# 数据读取
# =====================

def load_docs():
    return load_json(
        DOCS_FILE,
        {
            "next_id": 1,
            "by_id": {},
            "by_url": {}
        }
    )


def save_docs(docs):
    save_json(DOCS_FILE, docs)


# =====================
# 命令：crawl
# =====================

def cmd_crawl(args):
    start_url = normalize_url(args.url)
    if not start_url:
        print("无效 URL")
        return 1

    allowed_netloc = urlparse(start_url).netloc

    docs = load_docs()

    queue = deque([(start_url, 0)])
    seen = {start_url}
    fetched = 0

    print(f"开始抓取: {start_url}")
    print(f"限制域名: {allowed_netloc}")
    print(f"最大页面数: {args.limit}")
    print(f"最大深度: {args.max_depth}")
    print(f"抓取间隔: {args.delay} 秒")
    print("-" * 50)

    while queue and fetched < args.limit:
        url, depth = queue.popleft()

        if depth > args.max_depth:
            continue

        if has_skip_ext(url):
            continue

        if not can_fetch(url):
            print(f"跳过 robots.txt 不允许的页面: {url}")
            continue

        try:
            r = SESSION.get(
                url,
                timeout=args.timeout,
                allow_redirects=True
            )

            if r.status_code != 200:
                print(f"HTTP {r.status_code}: {url}")
                continue

            content_type = r.headers.get("Content-Type", "")
            if "html" not in content_type.lower():
                continue

            # 尝试修正编码
            if not r.encoding or r.encoding.lower() == "iso-8859-1":
                try:
                    r.encoding = r.apparent_encoding or "utf-8"
                except Exception:
                    r.encoding = "utf-8"

            title, desc, text, links = parse_page(r.text, url)

            if len(text) < args.min_text_len:
                print(f"正文太短，跳过: {url}")
                continue

            if url in docs["by_url"]:
                doc_id = docs["by_url"][url]
            else:
                doc_id = str(docs["next_id"])
                docs["next_id"] += 1
                docs["by_url"][url] = doc_id

            docs["by_id"][doc_id] = {
                "id": doc_id,
                "url": url,
                "title": title,
                "desc": desc,
                "text": text[:args.max_text_len],
                "crawled_at": datetime.now().isoformat(timespec="seconds")
            }

            fetched += 1

            print(f"[{fetched}/{args.limit}] {url}")
            print(f"    标题: {title[:50]}")

            save_docs(docs)

            # 加入新链接
            if depth < args.max_depth:
                for link in links:
                    if urlparse(link).netloc != allowed_netloc:
                        continue

                    if has_skip_ext(link):
                        continue

                    if link not in seen:
                        seen.add(link)
                        queue.append((link, depth + 1))

            if args.delay > 0:
                time.sleep(args.delay)

        except KeyboardInterrupt:
            print("\n用户中断，保存已抓取数据...")
            save_docs(docs)
            return 130

        except Exception as e:
            print(f"抓取失败: {url}")
            print(f"错误: {e}")
            if args.delay > 0:
                time.sleep(args.delay)

    save_docs(docs)

    print("-" * 50)
    print(f"抓取完成，共新增/更新 {fetched} 个页面。")
    print("下一步建立索引:")
    print("python mini_search.py index")

    return 0


# =====================
# 命令：index
# =====================

def cmd_index(args):
    docs = load_docs()

    if not docs["by_id"]:
        print("没有已抓取的文档。")
        print("请先运行:")
        print("python mini_search.py crawl https://example.com")
        return 1

    print("开始建立倒排索引...")

    postings = defaultdict(dict)
    doc_lengths = {}
    total_len = 0

    for doc_id, doc in docs["by_id"].items():
        # 标题重复两次，相当于简单提高标题权重
        boosted_text = " ".join([
            doc.get("title", ""),
            doc.get("title", ""),
            doc.get("desc", ""),
            doc.get("text", "")
        ])

        tokens = tokenize(boosted_text)

        doc_lengths[doc_id] = len(tokens)
        total_len += len(tokens)

        counter = Counter(tokens)

        for word, tf in counter.items():
            postings[word][doc_id] = tf

    index = {
        "meta": {
            "doc_count": len(docs["by_id"]),
            "avgdl": total_len / max(1, len(docs["by_id"])),
            "built_at": datetime.now().isoformat(timespec="seconds")
        },
        "doc_lengths": doc_lengths,
        "postings": postings
    }

    save_json(INDEX_FILE, index)

    print("-" * 50)
    print(f"索引完成。")
    print(f"文档数量: {len(docs['by_id'])}")
    print(f"词表大小: {len(postings)}")
    print(f"索引文件: {INDEX_FILE}")

    return 0


# =====================
# 命令：search
# =====================

def make_snippet(text, query_words, width=140):
    text = clean_text(text)
    if not text:
        return ""

    low = text.lower()
    pos = -1

    for w in query_words:
        pos = low.find(w.lower())
        if pos != -1:
            break

    if pos == -1:
        if len(text) <= width:
            return text
        return text[:width] + "..."

    start = max(0, pos - width // 2)
    end = min(len(text), start + width)

    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""

    return prefix + text[start:end] + suffix


def cmd_search(args):
    index = load_json(INDEX_FILE, None)

    if not index:
        print("没有索引文件。")
        print("请先运行:")
        print("python mini_search.py index")
        return 1

    docs = load_docs()

    query_words = tokenize(args.query)
    if not query_words:
        print("查询词为空。")
        return 1

    N = index["meta"]["doc_count"]
    avgdl = index["meta"]["avgdl"]

    postings = index.get("postings", {})
    doc_lengths = index.get("doc_lengths", {})

    scores = defaultdict(float)

    # BM25 参数
    k1 = 1.5
    b = 0.75

    for word in set(query_words):
        plist = postings.get(word)
        if not plist:
            continue

        df = len(plist)

        # BM25 的 IDF
        idf = math.log((N - df + 0.5) / (df + 0.5) + 1.0)

        for doc_id, tf in plist.items():
            dl = float(doc_lengths.get(doc_id, 0))

            denominator = tf + k1 * (
                1 - b + b * dl / max(1.0, avgdl)
            )

            scores[doc_id] += idf * tf * (k1 + 1) / max(1e-9, denominator)

    if not scores:
        print("未找到相关结果。")
        return 0

    ranked = sorted(
        scores.items(),
        key=lambda x: x[1],
        reverse=True
    )[:args.top]

    print(f"搜索: {args.query}")
    print(f"分词: {' / '.join(query_words)}")
    print(f"匹配文档数: {len(scores)}")
    print("=" * 60)

    for i, (doc_id, score) in enumerate(ranked, 1):
        doc = docs["by_id"].get(doc_id, {})

        title = doc.get("title") or "(无标题)"
        url = doc.get("url", "")
        snippet = make_snippet(doc.get("text", ""), query_words)

        print(f"{i}. {title}")
        print(f"   分数: {score:.4f}")
        print(f"   链接: {url}")

        if snippet:
            print(f"   摘要: {snippet}")

        print()

    return 0


# =====================
# 命令：status
# =====================

def cmd_status(args):
    docs = load_docs()
    index = load_json(INDEX_FILE, None)

    print("MiniSearch 状态")
    print("-" * 50)
    print(f"文档数量: {len(docs.get('by_id', {}))}")
    print(f"URL 数量: {len(docs.get('by_url', {}))}")

    if index:
        print(f"索引词数: {len(index.get('postings', {}))}")
        print(f"索引时间: {index.get('meta', {}).get('built_at', '未知')}")
    else:
        print("索引状态: 未建立")

    print(f"数据目录: {BASE_DIR}")

    return 0


# =====================
# 命令行入口
# =====================

def main():
    parser = argparse.ArgumentParser(
        description="Termux 迷你中文搜索引擎"
    )

    sub = parser.add_subparsers(dest="command")

    # crawl
    p_crawl = sub.add_parser(
        "crawl",
        help="抓取一个网站，默认只抓同域名"
    )
    p_crawl.add_argument("url", help="起始 URL")
    p_crawl.add_argument("--limit", type=int, default=20, help="最多抓取页面数")
    p_crawl.add_argument("--delay", type=float, default=1.0, help="每次请求间隔秒数")
    p_crawl.add_argument("--max-depth", type=int, default=2, help="最大抓取深度")
    p_crawl.add_argument("--timeout", type=float, default=15.0, help="请求超时时间")
    p_crawl.add_argument("--min-text-len", type=int, default=30, help="正文最短字数")
    p_crawl.add_argument("--max-text-len", type=int, default=200000, help="正文最大保存长度")
    p_crawl.set_defaults(func=cmd_crawl)

    # index
    p_index = sub.add_parser(
        "index",
        help="建立倒排索引"
    )
    p_index.set_defaults(func=cmd_index)

    # search
    p_search = sub.add_parser(
        "search",
        help="搜索"
    )
    p_search.add_argument("query", help="搜索关键词")
    p_search.add_argument("--top", type=int, default=10, help="最多返回结果数")
    p_search.set_defaults(func=cmd_search)

    # status
    p_status = sub.add_parser(
        "status",
        help="查看状态"
    )
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        return 1

    return args.func(args) or 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已退出")
        sys.exit(130)