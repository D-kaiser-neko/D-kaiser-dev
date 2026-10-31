#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from PIL import Image, ImageDraw, ImageFont

# ================= 核心配置 =================
WIDTH, HEIGHT = 400, 300
OUTPUT_DIR = "test_media/images"

FORMATS = {
    "PNG": {
        "ext": "png", "transparent_bg": True,
        "inventor": "PNG Development Group", "year": "1996",
        "meta": {"Color": "32-bit RGBA", "Animation": "No", "Transparency": "Yes", "Compression": "Lossless", "Other": "Gamma & color space support"},
        "purpose": "Lossless compression. Ideal for web graphics, logos, and screenshots."
    },
    "JPG": {
        "ext": "jpg", "transparent_bg": False,
        "inventor": "Joint Photographic Experts Group", "year": "1992",
        "meta": {"Color": "24-bit RGB (YCbCr)", "Animation": "No", "Transparency": "No", "Compression": "Lossy", "Other": "Exif metadata supported"},
        "purpose": "Lossy compression. Excellent for photographs. Best quality/size balance."
    },
    "GIF": {
        "ext": "gif", "transparent_bg": True,
        "inventor": "CompuServe (Steve Wilhite)", "year": "1987",
        "meta": {"Color": "8-bit Indexed (256)", "Animation": "Yes", "Transparency": "Yes (1-bit)", "Compression": "Lossless (LZW)", "Other": "Frame delay control"},
        "purpose": "Supports simple animation. Limited palette. Great for memes and icons."
    },
    "BMP": {
        "ext": "bmp", "transparent_bg": False,
        "inventor": "Microsoft", "year": "1985",
        "meta": {"Color": "24-bit RGB", "Animation": "No", "Transparency": "No", "Compression": "None", "Other": "Device-independent bitmap"},
        "purpose": "Uncompressed format. High quality but large size. Native to Windows."
    },
    "WEBP": {
        "ext": "webp", "transparent_bg": True,
        "inventor": "Google", "year": "2010",
        "meta": {"Color": "32-bit RGBA", "Animation": "Yes", "Transparency": "Yes (8-bit alpha)", "Compression": "Lossy / Lossless", "Other": "Superior compression ratio"},
        "purpose": "Modern web & App first choice. Smaller size, supports transparency & animation."
    },
    "TIFF": {
        "ext": "tiff", "transparent_bg": True,
        "inventor": "Aldus Corp & Microsoft", "year": "1986",
        "meta": {"Color": "32-bit RGBA", "Animation": "No (Multi-page)", "Transparency": "Yes", "Compression": "Lossless", "Other": "Extensible, supports layers"},
        "purpose": "High-quality lossless format. Standard in printing, publishing & medical imaging."
    },
}

COLOR_BARS = ["white", "yellow", "cyan", "green", "magenta", "red", "blue", "black"]
COLOR_HEX  = ["#FFFFFF", "#FFFF00", "#00FFFF", "#00FF00", "#FF00FF", "#FF0000", "#0000FF", "#000000"]
# ============================================

def get_fonts():
    try:
        return ImageFont.load_default(size=30), ImageFont.load_default(size=13)
    except TypeError:
        return ImageFont.load_default(), ImageFont.load_default()

def wrap_text(text, max_chars=50):
    words = text.split()
    lines, current = [], ""
    for word in words:
        if len(current) + len(word) + 1 <= max_chars:
            current += (f" {word}" if current else word)
        else:
            if current: lines.append(current)
            current = word
    if current: lines.append(current)
    return lines

def draw_metadata(draw, meta, start_y, text_kwargs):
    """绘制专业元数据表格"""
    y = start_y
    for label in ["Color", "Animation", "Transparency", "Compression", "Other"]:
        draw.text((20, y), f"{label}:", **text_kwargs)
        val_kwargs = text_kwargs.copy()
        val_kwargs["fill"] = "#333333"
        # 修复：移除重复的 font 参数
        draw.text((130, y), meta.get(label, "N/A"), **val_kwargs)
        y += 18
    return y

def create_raster_image(fmt_name, config, font_large, font_small):
    if config["transparent_bg"]:
        img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        text_kwargs = {"fill": "black", "font": font_small, "stroke_width": 2, "stroke_fill": "white"}
        title_kwargs = {"fill": "black", "font": font_large, "stroke_width": 2, "stroke_fill": "white"}
    else:
        img = Image.new("RGB", (WIDTH, HEIGHT), "white")
        text_kwargs = {"fill": "black", "font": font_small}
        title_kwargs = {"fill": "black", "font": font_large}
        
    draw = ImageDraw.Draw(img)
    
    # 色块
    bar_w = WIDTH // len(COLOR_BARS)
    for i, color in enumerate(COLOR_BARS):
        draw.rectangle([i * bar_w, 0, (i + 1) * bar_w, 50], fill=color, outline="gray")
        
    # 格式名
    draw.text((20, 60), fmt_name, **title_kwargs)
    
    # 元数据 (已修复参数冲突)
    y_after_meta = draw_metadata(draw, config["meta"], 105, text_kwargs)
    
    # 发明人 & 年份
    draw.text((20, y_after_meta + 10), f"Inventor: {config['inventor']}", **text_kwargs)
    draw.text((20, y_after_meta + 28), f"Year: {config['year']}", **text_kwargs)
    
    # 作用/优点
    draw.text((20, y_after_meta + 55), "Purpose / Advantages:", **text_kwargs)
    y_text = y_after_meta + 73
    for line in wrap_text(config["purpose"]):
        draw.text((20, y_text), line, **text_kwargs)
        y_text += 18
        
    return img

def create_svg(fmt_name, config):
    bar_w = WIDTH / len(COLOR_BARS)
    rects = "".join([
        f'<rect x="{i*bar_w}" y="0" width="{bar_w}" height="50" fill="{COLOR_HEX[i]}" stroke="#888" stroke-width="1"/>\n'
        for i in range(len(COLOR_BARS))
    ])
    
    stroke_style = 'stroke="white" stroke-width="2.5" paint-order="stroke"'
    
    meta_lines = ""
    y = 105
    for label in ["Color", "Animation", "Transparency", "Compression", "Other"]:
        val = config["meta"].get(label, "N/A")
        meta_lines += f'<text x="20" y="{y}" font-family="monospace" font-size="13" fill="black" {stroke_style}>{label}:</text>\n'
        meta_lines += f'<text x="130" y="{y}" font-family="monospace" font-size="13" fill="#333" {stroke_style}>{val}</text>\n'
        y += 18
        
    y += 10
    meta_lines += f'<text x="20" y="{y}" font-family="sans-serif" font-size="13" fill="black" {stroke_style}>Inventor: {config["inventor"]}</text>\n'
    y += 18
    meta_lines += f'<text x="20" y="{y}" font-family="sans-serif" font-size="13" fill="black" {stroke_style}>Year: {config["year"]}</text>\n'
    
    y += 25
    meta_lines += f'<text x="20" y="{y}" font-family="sans-serif" font-size="13" fill="black" {stroke_style}>Purpose / Advantages:</text>\n'
    y += 18
    for line in wrap_text(config["purpose"]):
        meta_lines += f'<text x="20" y="{y}" font-family="sans-serif" font-size="12" fill="black" {stroke_style}>{line}</text>\n'
        y += 16
        
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{WIDTH}" height="{HEIGHT}" xmlns="http://www.w3.org/2000/svg">
  {rects}
  <text x="20" y="85" font-family="sans-serif" font-size="30" font-weight="bold" fill="black" {stroke_style}>{fmt_name}</text>
  {meta_lines}
</svg>'''

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    font_large, font_small = get_fonts()
    print(f"[*] Generating test images (with text stroke for transparency) ...")
    
    for fmt, config in FORMATS.items():
        img = create_raster_image(fmt, config, font_large, font_small)
        filepath = os.path.join(OUTPUT_DIR, f"sample.{config['ext']}")
        
        if config['ext'] == 'gif':
            img = img.convert('P', palette=Image.ADAPTIVE)
            img.save(filepath, transparency=0)
        else:
            img.save(filepath)
            
        size_kb = os.path.getsize(filepath) / 1024
        print(f"    [+] {fmt:<5} -> {filepath} ({size_kb:.1f} KB)")
        
    # SVG
    svg_config = {
        "inventor": "W3C", "year": "2001",
        "meta": {"Color": "Vector (XML/CSS)", "Animation": "Yes (SMIL/CSS)", "Transparency": "Yes", "Compression": "None (Text)", "Other": "Resolution independent"},
        "purpose": "Scalable vector graphic. Perfect for icons, logos, and responsive web design."
    }
    svg_path = os.path.join(OUTPUT_DIR, "sample.svg")
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(create_svg("SVG", svg_config))
    print(f"    [+] SVG   -> {svg_path} ({os.path.getsize(svg_path)/1024:.1f} KB)")
    
    print("\n[*] Done! Text now has white stroke for perfect readability on transparent backgrounds.")

if __name__ == "__main__":
    main()