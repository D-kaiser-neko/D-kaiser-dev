#!/usr/bin/env python3
"""
NS2/NSA 解包/打包工具
coder by qwen3.8
"""
import os, sys, struct, glob, time, shutil

VERSION = "1.0"
XOR_KEY = 0x84
IMG_EXTS   = {'.png','.jpg','.jpeg','.bmp','.gif','.webp','.tga'}
AUDIO_EXTS = {'.ogg','.wav','.mp3','.flac','.mid','.midi','.wma'}

# ═══════════════════════════════════════
#  进度条
# ═══════════════════════════════════════
class PBar:
    def __init__(self, total, prefix=''):
        self.total = max(total, 1)
        self.prefix = prefix
        self.t0 = time.time()
        self.last_t = 0
    def draw(self, cur, msg=''):
        now = time.time()
        if cur < self.total and now - self.last_t < 0.2: return
        self.last_t = now
        pct = cur / self.total
        w = 30; filled = int(w * pct)
        bar = '█' * filled + '░' * (w - filled)
        elapsed = now - self.t0
        spd = cur / elapsed if elapsed > 0.1 else 0
        eta = (self.total - cur) / spd if spd > 0 else 0
        s = f"\r  {self.prefix} |{bar}| {cur}/{self.total} {pct*100:5.1f}%"
        if cur < self.total and 0 < eta < 9999: s += f" ETA {eta:.0f}s"
        if msg: s += f" {msg}"
        sys.stdout.write(s); sys.stdout.flush()
    def done(self, msg='✓'):
        self.draw(self.total, msg); print()

# ═══════════════════════════════════════
#  工具函数
# ═══════════════════════════════════════
def safe_name(raw):
    if isinstance(raw, bytes):
        for enc in ('utf-8','gbk','shift_jis','latin-1'):
            try: raw = raw.decode(enc); break
            except: continue
        else: raw = raw.decode('latin-1')
    return raw.replace('\x00','').strip() or 'unnamed'

def encode_name(name):
    for enc in ('utf-8','gbk'):
        try: return name.encode(enc)
        except: continue
    return name.encode('latin-1')

def get_ext(name):
    return os.path.splitext(name)[1].lower()

def match_filter(name, ftype):
    if ftype is None: return True
    ext = get_ext(name)
    if ftype == 'img':   return ext in IMG_EXTS
    if ftype == 'voice': return ext in AUDIO_EXTS
    return True

def get_outdir(src):
    """输出目录 = 父目录名称_解包"""
    src = os.path.abspath(src)
    parent = os.path.dirname(src)
    parent_name = os.path.basename(parent)
    grand_parent = os.path.dirname(parent)
    return os.path.join(grand_parent, parent_name + '_解包')

# ═══════════════════════════════════════
#  XOR 加解密
# ═══════════════════════════════════════
def xor_file(src, dst, key=XOR_KEY):
    with open(src, 'rb') as f: data = f.read()
    with open(dst, 'wb') as f: f.write(bytes(b ^ key for b in data))

def try_decrypt_nscript(outdir):
    dat = os.path.join(outdir, 'nscript.dat')
    if os.path.isfile(dat):
        txt = os.path.join(outdir, '0.txt')
        xor_file(dat, txt)
        print(f"  [*] 已解密: nscript.dat → 0.txt")
        return True
    return False

# ═══════════════════════════════════════
#  格式检测
# ═══════════════════════════════════════
def detect_format(fpath):
    try:
        with open(fpath, 'rb') as f: head = f.read(32)
    except: return None
    if len(head) < 8: return None
    ds4 = struct.unpack_from('<I', head, 0)[0]
    if head[4] == 0x22 and 4 < ds4 < os.path.getsize(fpath): return 'quote'
    num = struct.unpack_from('>H', head, 0)[0]
    ds6 = struct.unpack_from('>I', head, 2)[0]
    if 0 < num < 100000 and 6 < ds6 < os.path.getsize(fpath): return 'nsa'
    return None

# ═══════════════════════════════════════
#  解析：引号格式 (.ns2)
# ═══════════════════════════════════════
def parse_quote(fpath):
    fsize = os.path.getsize(fpath)
    with open(fpath, 'rb') as f:
        ds = struct.unpack('<I', f.read(4))[0]
        if ds > fsize or ds < 4: return None
        table = f.read(ds - 4)
    files, pos = [], 0
    while pos < len(table):
        if table[pos] != 0x22: pos += 1; continue
        pos += 1; nb = bytearray()
        while pos < len(table) and table[pos] != 0x22:
            if table[pos]: nb.append(table[pos])
            pos += 1
        if pos >= len(table): break
        pos += 1
        if pos + 4 > len(table): break
        sz = struct.unpack_from('<I', table, pos)[0]; pos += 4
        name = safe_name(bytes(nb))
        if name: files.append({'name': name, 'size': sz})
    return files, ds, 'quote'

# ═══════════════════════════════════════
#  解析：标准NSA格式 (.nsa)
# ═══════════════════════════════════════
def parse_nsa(fpath):
    fsize = os.path.getsize(fpath)
    with open(fpath, 'rb') as f:
        num = struct.unpack('>H', f.read(2))[0]
        ds  = struct.unpack('>I', f.read(4))[0]
        if ds > fsize or num > 100000: return None
        table = f.read(ds - 6)
    files, pos = [], 0
    for _ in range(num):
        if pos >= len(table): break
        nb = bytearray()
        while pos < len(table) and table[pos]:
            nb.append(table[pos]); pos += 1
        if pos >= len(table): break
        pos += 1
        if pos + 13 > len(table): break
        ct  = table[pos]; pos += 1
        off = struct.unpack_from('>I', table, pos)[0]; pos += 4
        cs  = struct.unpack_from('>I', table, pos)[0]; pos += 4
        os_ = struct.unpack_from('>I', table, pos)[0]; pos += 4
        name = safe_name(bytes(nb))
        if name:
            files.append({'name':name,'offset':off,'comp_size':cs,'orig_size':os_,'comp_type':ct})
    return files, ds, 'nsa'

# ═══════════════════════════════════════
#  解包
# ═══════════════════════════════════════
def extract(fpath, outdir, ftype=None):
    fmt = detect_format(fpath)
    if fmt == 'quote': result = parse_quote(fpath)
    elif fmt == 'nsa': result = parse_nsa(fpath)
    else: print(f"  [-] 无法识别格式，跳过"); return False
    if not result: print(f"  [-] 解析失败"); return False
    files, ds, _ = result
    filtered = [f for f in files if match_filter(f['name'], ftype)]
    if not filtered: print(f"  [-] 无匹配文件"); return False
    tag = {'img':'图片','voice':'音频'}.get(ftype, '全部')
    print(f"  [*] 格式:{fmt} 数据区:{ds} 总文件:{len(files)} 提取({tag}):{len(filtered)}")
    os.makedirs(outdir, exist_ok=True)
    pb = PBar(len(filtered), '解包'); ok = 0
    with open(fpath, 'rb') as f:
        if fmt == 'quote':
            f.seek(ds)
            for i, fi in enumerate(files):
                if match_filter(fi['name'], ftype):
                    clean = fi['name'].replace('\\', '/')
                    op = os.path.join(outdir, clean)
                    dp = os.path.dirname(op)
                    if dp: os.makedirs(dp, exist_ok=True)
                    rem = fi['size']
                    with open(op, 'wb') as wf:
                        while rem > 0:
                            ck = f.read(min(rem, 1 << 20))
                            if not ck: break
                            wf.write(ck); rem -= len(ck)
                    ok += 1; pb.draw(ok)
                else:
                    f.seek(fi['size'], 1)
        else:
            for i, fi in enumerate(filtered):
                clean = fi['name'].replace('\\', '/')
                op = os.path.join(outdir, clean)
                dp = os.path.dirname(op)
                if dp: os.makedirs(dp, exist_ok=True)
                f.seek(ds + fi['offset'])
                rem = fi['comp_size']
                with open(op, 'wb') as wf:
                    while rem > 0:
                        ck = f.read(min(rem, 1 << 20))
                        if not ck: break
                        wf.write(ck); rem -= len(ck)
                ok += 1; pb.draw(ok)
    pb.done(f'✓ {ok}/{len(filtered)} → {outdir}/')
    if ftype is None: try_decrypt_nscript(outdir)
    return True

# ═══════════════════════════════════════
#  打包：引号格式 (.ns2)
# ═══════════════════════════════════════
def pack_quote(indir, outfile):
    allf = []
    for root, _, fns in os.walk(indir):
        for fn in sorted(fns):
            fp = os.path.join(root, fn)
            rel = os.path.relpath(fp, indir).replace('/', '\\')
            allf.append((rel, fp))
    allf.sort(key=lambda x: x[0])
    if not allf: print("  [-] 目录为空"); return False
    entries = b''
    for rel, fp in allf:
        sz = os.path.getsize(fp)
        entries += b'\x22' + encode_name(rel) + b'\x22' + struct.pack('<I', sz)
    ds = 4 + len(entries)
    pb = PBar(len(allf), '打包')
    with open(outfile, 'wb') as wf:
        wf.write(struct.pack('<I', ds)); wf.write(entries)
        for i, (_, fp) in enumerate(allf):
            with open(fp, 'rb') as rf:
                while True:
                    ck = rf.read(1 << 20)
                    if not ck: break
                    wf.write(ck)
            pb.draw(i + 1)
    pb.done(f'✓ → {outfile}')
    return True

# ═══════════════════════════════════════
#  打包：标准NSA格式 (.nsa)
# ═══════════════════════════════════════
def pack_nsa(indir, outfile):
    allf = []
    for root, _, fns in os.walk(indir):
        for fn in sorted(fns):
            fp = os.path.join(root, fn)
            rel = os.path.relpath(fp, indir).replace('/', '\\')
            allf.append((rel, fp))
    allf.sort(key=lambda x: x[0])
    if not allf: print("  [-] 目录为空"); return False
    table, offset, finfo = b'', 0, []
    for rel, fp in allf:
        sz = os.path.getsize(fp)
        table += encode_name(rel) + b'\x00'
        table += struct.pack('>B', 0) + struct.pack('>I', offset)
        table += struct.pack('>I', sz) + struct.pack('>I', sz)
        finfo.append((fp, sz)); offset += sz
    ds = 6 + len(table)
    pb = PBar(len(allf), '打包')
    with open(outfile, 'wb') as wf:
        wf.write(struct.pack('>H', len(allf)))
        wf.write(struct.pack('>I', ds)); wf.write(table)
        for i, (fp, _) in enumerate(finfo):
            with open(fp, 'rb') as rf:
                while True:
                    ck = rf.read(1 << 20)
                    if not ck: break
                    wf.write(ck)
            pb.draw(i + 1)
    pb.done(f'✓ → {outfile}')
    return True

# ═══════════════════════════════════════
#  扫描
# ═══════════════════════════════════════
def find_ns_files(base='.'):
    r = []
    for p in ('*.ns2', '*.ns', '*.nsa'):
        r.extend(glob.glob(os.path.join(base, '**', p), recursive=True))
    return sorted(set(r))

def find_ns_in_path(path):
    if os.path.isfile(path):
        if get_ext(path) in ('.ns2', '.ns', '.nsa'): return [path]
        return []
    if os.path.isdir(path): return find_ns_files(path)
    return []

# ═══════════════════════════════════════
#  帮助
# ═══════════════════════════════════════
def show_help():
    print(f"""
╔══════════════════════════════════════════════════╗
║  NS2/NSA 解包/打包工具 v{VERSION}                  ║
║  coder by qwen3.8                               ║
╚══════════════════════════════════════════════════╝

用法:
  python ns_tool.py                                # TUI 交互界面
  python ns_tool.py help                           # 显示本帮助

命令行解包:
  python ns_tool.py -i <输入> [-o <输出>] [过滤]
  python ns_tool.py -i arc1.nsa                    # 解包(自动输出到父目录_解包)
  python ns_tool.py -i arc1.nsa -o out/            # 指定输出目录
  python ns_tool.py -i ./game/ -o out/             # 扫描目录解包
  python ns_tool.py -i arc1.nsa img                # 仅提取图片
  python ns_tool.py -i arc1.nsa voice              # 仅提取音频

过滤选项:
  img      仅图片 (png/jpg/bmp/gif/webp)
  voice    仅音频 (ogg/wav/mp3/flac)
  不加     全部提取 + 自动解密 nscript.dat

打包:
  python ns_tool.py pack <目录> [输出文件]
  输出以 .nsa 结尾 → NSA格式
  输出以 .ns2 结尾 → 引号格式

脚本加解密 (XOR 0x84):
  python ns_tool.py dec <nscript.dat> [输出0.txt]
  python ns_tool.py enc <0.txt> [输出nscript.dat]

输出目录规则:
  输入: /game/[ons]万华镜5/arc1.nsa
  输出: /game/[ons]万华镜5_解包/
""")

# ═══════════════════════════════════════
#  命令行模式
# ═══════════════════════════════════════
def cmd_mode(args):
    inp = out = None; ftypes = []; i = 0
    while i < len(args):
        a = args[i]
        if a == '-i' and i + 1 < len(args): inp = args[i+1]; i += 2
        elif a == '-o' and i + 1 < len(args): out = args[i+1]; i += 2
        elif a in ('img', 'voice'): ftypes.append(a); i += 1
        else: i += 1
    if not inp: print("错误: 需要 -i 指定输入"); return
    ftype = None
    if 'img' in ftypes and 'voice' not in ftypes: ftype = 'img'
    elif 'voice' in ftypes and 'img' not in ftypes: ftype = 'voice'
    targets = find_ns_in_path(inp)
    if not targets: print(f"未找到封包: {inp}"); return
    od = out if out else get_outdir(targets[0])
    print(f"[*] 输出目录: {od}/")
    for t in targets:
        print(f"\n[+] 解包: {t}")
        extract(t, od, ftype)
    print(f"\n全部完成 → {od}/")

# ═══════════════════════════════════════
#  TUI 模式
# ═══════════════════════════════════════
def tui_mode():
    while True:
        print(f"""
╔══════════════════════════════════╗
║  NS2/NSA 工具 v{VERSION}               ║
╠══════════════════════════════════╣
║  [1] 解包 (全部+脚本解密)        ║
║  [2] 封包                        ║
║  [3] 图片提取                    ║
║  [4] 音频提取                    ║
║  [5] 脚本文件加/解密             ║
║  [x] 退出                        ║
╚══════════════════════════════════╝""")
        c = input("  请选择: ").strip().lower()
        if c == 'x': print("  再见！"); break
        elif c == '1': tui_unpack(None)
        elif c == '2': tui_pack()
        elif c == '3': tui_unpack('img')
        elif c == '4': tui_unpack('voice')
        elif c == '5': tui_crypt()
        else: print("  无效选项")

def tui_unpack(ftype):
    tag = {'img':'图片','voice':'音频',None:'全部'}.get(ftype,'全部')
    path = input(f"  输入文件/目录 (回车=当前目录): ").strip() or '.'
    targets = find_ns_in_path(path)
    if not targets: print("  未找到封包文件"); return
    print(f"  找到 {len(targets)} 个文件:")
    for t in targets: print(f"    {t}")
    custom = input(f"  输出目录 (回车=自动): ").strip()
    od = custom if custom else get_outdir(targets[0])
    print(f"  输出到: {od}/")
    for t in targets:
        print(f"\n[+] 解包({tag}): {t}")
        extract(t, od, ftype)
    print("\n  完成！")

def tui_pack():
    indir = input("  输入目录: ").strip()
    if not indir or not os.path.isdir(indir): print("  目录不存在"); return
    out = input("  输出文件 (.nsa=NSA格式, .ns2=引号格式): ").strip()
    if not out: out = indir.rstrip('/') + '_repacked.ns2'
    if out.endswith('.nsa'): pack_nsa(indir, out)
    else:
        if not out.endswith('.ns2'): out += '.ns2'
        pack_quote(indir, out)

def tui_crypt():
    print("""
  [1] 解密 nscript.dat → 0.txt
  [2] 加密 0.txt → nscript.dat
  [x] 返回""")
    c = input("  请选择: ").strip()
    if c == '1':
        src = input("  nscript.dat 路径 (回车默认): ").strip() or 'nscript.dat'
        if not os.path.isfile(src): print("  文件不存在"); return
        dst = input("  输出路径 (回车=0.txt): ").strip() or '0.txt'
        xor_file(src, dst); print(f"  ✓ 解密: {src} → {dst}")
    elif c == '2':
        src = input("  0.txt 路径 (回车默认): ").strip() or '0.txt'
        if not os.path.isfile(src): print("  文件不存在"); return
        dst = input("  输出路径 (回车=nscript.dat): ").strip() or 'nscript.dat'
        xor_file(src, dst); print(f"  ✓ 加密: {src} → {dst}")

# ═══════════════════════════════════════
#  主入口
# ═══════════════════════════════════════
def main():
    args = sys.argv[1:]
    if not args:
        tui_mode()
    elif args[0].lower() == 'help':
        show_help()
    elif args[0] == '-i':
        cmd_mode(args)
    elif args[0].lower() == 'pack':
        if len(args) < 2: print("用法: python ns_tool.py pack <目录> [输出]"); return
        out = args[2] if len(args) > 2 else args[1].rstrip('/') + '_repacked.ns2'
        if out.endswith('.nsa'): pack_nsa(args[1], out)
        else:
            if not out.endswith('.ns2'): out += '.ns2'
            pack_quote(args[1], out)
    elif args[0].lower() in ('dec', 'decrypt'):
        src = args[1] if len(args) > 1 else 'nscript.dat'
        dst = args[2] if len(args) > 2 else '0.txt'
        if os.path.isfile(src): xor_file(src, dst); print(f"✓ 解密: {src} → {dst}")
        else: print(f"文件不存在: {src}")
    elif args[0].lower() in ('enc', 'encrypt'):
        src = args[1] if len(args) > 1 else '0.txt'
        dst = args[2] if len(args) > 2 else 'nscript.dat'
        if os.path.isfile(src): xor_file(src, dst); print(f"✓ 加密: {src} → {dst}")
        else: print(f"文件不存在: {src}")
    else:
        for t in args:
            if os.path.isfile(t):
                od = get_outdir(t)
                print(f"[+] 解包: {t} → {od}/")
                extract(t, od)
            elif os.path.isdir(t):
                targets = find_ns_files(t)
                if not targets: print(f"  未找到封包: {t}"); continue
                od = get_outdir(targets[0])
                print(f"[*] 输出: {od}/")
                for f in targets:
                    print(f"\n[+] 解包: {f}")
                    extract(f, od)
            else:
                print(f"  [-] 不存在: {t}")

if __name__ == '__main__':
    main()