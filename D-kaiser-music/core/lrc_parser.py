#!/usr/bin/env python3
"""歌词清洗 / 中日文时间轴对齐"""
import re

def format_lrc(raw):
    if not raw:
        return ""
    ts_re = re.compile(r'^\[(\d{1,2}:\d{2}(?:\.\d{1,3})?)\]\s*(.*)$')
    lines = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        m = ts_re.match(line)
        if m:
            ts, text = m.group(1), m.group(2).strip()
            if not text:
                continue
            lines.append([ts, text])
        elif line.startswith('['):
            lines.append([None, line])
        else:
            if lines and lines[-1][0] is not None:
                lines[-1][1] += line
    has_kana = lambda t: bool(re.search(r'[\u3040-\u30ff]', t))
    has_han  = lambda t: bool(re.search(r'[\u4e00-\u9fff]', t))
    for i in range(1, len(lines) - 1):
        tp, tc, tn = lines[i-1][0], lines[i][0], lines[i+1][0]
        if not (tp and tc and tn):
            continue
        if tc == tn and tc != tp:
            a, b = lines[i-1][1], lines[i][1]
            if (has_han(b) and not has_kana(b) and has_kana(a)) or \
               (has_kana(b) and has_han(a) and not has_kana(a)):
                lines[i][0] = tp
    return '\n'.join(t if ts is None else f"[{ts}]{t}" for ts, t in lines)