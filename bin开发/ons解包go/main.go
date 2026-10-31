package main

import (
	"bytes"
	"encoding/binary"
	"fmt"
	"io"
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"
)

const Version = "1.0-go"
const XOR_KEY byte = 0x84

var imgExts = map[string]bool{
	".png":  true,
	".jpg":  true,
	".jpeg": true,
	".bmp":  true,
	".gif":  true,
	".webp": true,
	".tga":  true,
}

var audioExts = map[string]bool{
	".ogg":  true,
	".wav":  true,
	".mp3":  true,
	".flac": true,
	".mid":  true,
	".midi": true,
	".wma":  true,
}

type Entry struct {
	Name     string
	Size     uint32
	Offset   uint32
	CompSize uint32
	OrigSize uint32
	CompType byte
}

type PackFile struct {
	Rel  string
	Abs  string
	Size int64
}

func isFile(path string) bool {
	fi, err := os.Stat(path)
	return err == nil && !fi.IsDir()
}

func isDir(path string) bool {
	fi, err := os.Stat(path)
	return err == nil && fi.IsDir()
}

func fileSize(path string) int64 {
	fi, err := os.Stat(path)
	if err != nil {
		return 0
	}
	return fi.Size()
}

func absPath(path string) string {
	p, err := filepath.Abs(path)
	if err != nil {
		return path
	}
	return p
}

func mkdirForFile(path string) {
	dir := filepath.Dir(path)
	if dir != "" {
		os.MkdirAll(dir, 0755)
	}
}

func safeJoin(base, name string) string {
	clean := strings.ReplaceAll(name, "\\", "/")
	parts := strings.Split(clean, "/")

	safe := make([]string, 0, len(parts))
	for _, p := range parts {
		if p == "" || p == "." || p == ".." {
			continue
		}
		safe = append(safe, p)
	}

	if len(safe) == 0 {
		safe = append(safe, "unnamed")
	}

	return filepath.Join(append([]string{base}, safe...)...)
}

func matchFilter(name, ftype string) bool {
	if ftype == "" {
		return true
	}

	ext := strings.ToLower(filepath.Ext(name))

	if ftype == "img" {
		return imgExts[ext]
	}
	if ftype == "voice" {
		return audioExts[ext]
	}

	return true
}

func defaultOutdir(src string) string {
	abs := absPath(src)
	parent := filepath.Dir(abs)
	parentName := filepath.Base(parent)
	grand := filepath.Dir(parent)
	return filepath.Join(grand, parentName+"_解包")
}

func knownArchiveExt(path string) bool {
	ext := strings.ToLower(filepath.Ext(path))
	return ext == ".ns2" || ext == ".ns" || ext == ".nsa"
}

func findNSInPath(path string) []string {
	if isFile(path) {
		if knownArchiveExt(path) {
			return []string{path}
		}
		return nil
	}

	if !isDir(path) {
		return nil
	}

	var list []string

	filepath.WalkDir(path, func(p string, d fs.DirEntry, err error) error {
		if err != nil {
			return nil
		}
		if !d.IsDir() && knownArchiveExt(p) {
			list = append(list, p)
		}
		return nil
	})

	sort.Strings(list)
	return list
}

func detectFormat(path string) string {
	f, err := os.Open(path)
	if err != nil {
		return ""
	}
	defer f.Close()

	head := make([]byte, 32)
	n, _ := io.ReadFull(f, head)
	if n < 8 {
		return ""
	}

	size := fileSize(path)

	ds4 := binary.LittleEndian.Uint32(head[0:4])
	if head[4] == 0x22 && int64(ds4) > 4 && int64(ds4) < size {
		return "quote"
	}

	num := binary.BigEndian.Uint16(head[0:2])
	ds6 := binary.BigEndian.Uint32(head[2:6])
	if num > 0 && int(num) < 100000 && int64(ds6) > 6 && int64(ds6) < size {
		return "nsa"
	}

	return ""
}

func parseQuote(path string) ([]Entry, uint32, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, 0, err
	}
	defer f.Close()

	fi, err := f.Stat()
	if err != nil {
		return nil, 0, err
	}

	var ds uint32
	if err := binary.Read(f, binary.LittleEndian, &ds); err != nil {
		return nil, 0, err
	}

	if ds < 4 || int64(ds) > fi.Size() {
		return nil, 0, fmt.Errorf("bad quote ds")
	}

	table := make([]byte, ds-4)
	if _, err := io.ReadFull(f, table); err != nil {
		return nil, 0, err
	}

	var entries []Entry
	pos := 0

	for pos < len(table) {
		if table[pos] != 0x22 {
			pos++
			continue
		}

		pos++
		var name []byte

		for pos < len(table) && table[pos] != 0x22 {
			if table[pos] != 0 {
				name = append(name, table[pos])
			}
			pos++
		}

		if pos >= len(table) {
			break
		}

		pos++

		if pos+4 > len(table) {
			break
		}

		sz := binary.LittleEndian.Uint32(table[pos : pos+4])
		pos += 4

		entries = append(entries, Entry{
			Name: string(name),
			Size: sz,
		})
	}

	return entries, ds, nil
}

func parseNSA(path string) ([]Entry, uint32, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, 0, err
	}
	defer f.Close()

	fi, err := f.Stat()
	if err != nil {
		return nil, 0, err
	}

	var num uint16
	var ds uint32

	if err := binary.Read(f, binary.BigEndian, &num); err != nil {
		return nil, 0, err
	}
	if err := binary.Read(f, binary.BigEndian, &ds); err != nil {
		return nil, 0, err
	}

	if ds < 6 || int64(ds) > fi.Size() || int(num) > 100000 {
		return nil, 0, fmt.Errorf("bad nsa header")
	}

	table := make([]byte, ds-6)
	if _, err := io.ReadFull(f, table); err != nil {
		return nil, 0, err
	}

	var entries []Entry
	pos := 0

	for i := 0; i < int(num); i++ {
		if pos >= len(table) {
			break
		}

		start := pos
		for pos < len(table) && table[pos] != 0 {
			pos++
		}

		if pos >= len(table) {
			break
		}

		name := string(table[start:pos])
		pos++

		if pos+13 > len(table) {
			break
		}

		ct := table[pos]
		pos++

		off := binary.BigEndian.Uint32(table[pos : pos+4])
		pos += 4

		comp := binary.BigEndian.Uint32(table[pos : pos+4])
		pos += 4

		orig := binary.BigEndian.Uint32(table[pos : pos+4])
		pos += 4

		entries = append(entries, Entry{
			Name:     name,
			Offset:   off,
			CompSize: comp,
			OrigSize: orig,
			CompType: ct,
			Size:     comp,
		})
	}

	return entries, ds, nil
}

func copyToFile(r io.Reader, path string, n int64) error {
	mkdirForFile(path)

	wf, err := os.Create(path)
	if err != nil {
		return err
	}
	defer wf.Close()

	_, err = io.CopyN(wf, r, n)
	return err
}

func runExternal(name string, args ...string) int {
	cmd := exec.Command(name, args...)
	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	err := cmd.Run()
	if err != nil {
		if exitErr, ok := err.(*exec.ExitError); ok {
			return exitErr.ExitCode()
		}
		fmt.Println("执行失败:", err)
		return 1
	}

	return 0
}

func binwalkExtract(path, outdir string) bool {
	os.MkdirAll(outdir, 0755)

	fmt.Printf("  $ binwalk -e -C %s %s\n", outdir, path)
	code := runExternal("binwalk", "-e", "-C", outdir, path)

	if code == 0 {
		fmt.Printf("  [*] binwalk 输出目录: %s/\n", outdir)
		return true
	}

	fmt.Printf("  [-] binwalk 返回码: %d\n", code)
	return false
}

func binwalkFallback(path, outdir string) bool {
	bdir := filepath.Join(outdir, filepath.Base(path)+".binwalk")
	return binwalkExtract(path, bdir)
}

func xorFile(src, dst string) error {
	data, err := os.ReadFile(src)
	if err != nil {
		return err
	}

	for i := range data {
		data[i] ^= XOR_KEY
	}

	mkdirForFile(dst)
	return os.WriteFile(dst, data, 0644)
}

func tryDecryptNscript(outdir string) bool {
	dat := filepath.Join(outdir, "nscript.dat")
	if !isFile(dat) {
		return false
	}

	txt := filepath.Join(outdir, "0.txt")
	if err := xorFile(dat, txt); err != nil {
		fmt.Println("  [-] 解密失败:", err)
		return false
	}

	fmt.Println("  [*] 已解密: nscript.dat → 0.txt")
	return true
}

func extract(path, outdir, ftype string, useBinwalk bool) bool {
	format := detectFormat(path)

	if format == "" {
		fmt.Println("  [-] 无法识别格式:", path)

		if useBinwalk {
			fmt.Println("  [*] 尝试使用 binwalk 提取...")
			return binwalkFallback(path, outdir)
		}

		fmt.Println("      可加 --binwalk 调用 binwalk 再试")
		return false
	}

	var entries []Entry
	var ds uint32
	var err error

	if format == "quote" {
		entries, ds, err = parseQuote(path)
	} else {
		entries, ds, err = parseNSA(path)
	}

	if err != nil {
		fmt.Println("  [-] 解析失败:", err)

		if useBinwalk {
			return binwalkFallback(path, outdir)
		}

		return false
	}

	filtered := 0
	for _, e := range entries {
		if matchFilter(e.Name, ftype) {
			filtered++
		}
	}

	if filtered == 0 {
		fmt.Println("  [-] 无匹配文件")
		return false
	}

	os.MkdirAll(outdir, 0755)

	fmt.Printf("  [*] 格式:%s 数据区:%d 总文件:%d 提取:%d\n",
		format, ds, len(entries), filtered)

	f, err := os.Open(path)
	if err != nil {
		fmt.Println("  [-]", err)
		return false
	}
	defer f.Close()

	ok := 0

	if format == "quote" {
		f.Seek(int64(ds), io.SeekStart)

		for _, e := range entries {
			if matchFilter(e.Name, ftype) {
				outPath := safeJoin(outdir, e.Name)

				if err := copyToFile(f, outPath, int64(e.Size)); err == nil {
					ok++
				} else {
					fmt.Println("  [-]", err)
				}
			} else {
				f.Seek(int64(e.Size), io.SeekCurrent)
			}
		}
	} else {
		for _, e := range entries {
			if !matchFilter(e.Name, ftype) {
				continue
			}

			outPath := safeJoin(outdir, e.Name)
			f.Seek(int64(ds)+int64(e.Offset), io.SeekStart)

			if err := copyToFile(f, outPath, int64(e.CompSize)); err == nil {
				ok++
			} else {
				fmt.Println("  [-]", err)
			}
		}
	}

	fmt.Printf("  ✓ %d/%d → %s/\n", ok, filtered, outdir)

	if ftype == "" {
		tryDecryptNscript(outdir)
	}

	return true
}

func collectFiles(indir string) ([]PackFile, error) {
	var files []PackFile

	err := filepath.WalkDir(indir, func(p string, d fs.DirEntry, err error) error {
		if err != nil {
			return nil
		}

		if d.IsDir() {
			return nil
		}

		rel, err := filepath.Rel(indir, p)
		if err != nil {
			return nil
		}

		rel = strings.ReplaceAll(rel, "/", "\\")

		fi, err := d.Info()
		if err != nil {
			return nil
		}

		files = append(files, PackFile{
			Rel:  rel,
			Abs:  p,
			Size: fi.Size(),
		})

		return nil
	})

	sort.Slice(files, func(i, j int) bool {
		return files[i].Rel < files[j].Rel
	})

	return files, err
}

func appendFile(dst io.Writer, src string) error {
	rf, err := os.Open(src)
	if err != nil {
		return err
	}
	defer rf.Close()

	_, err = io.Copy(dst, rf)
	return err
}

func packQuote(indir, outfile string) error {
	files, err := collectFiles(indir)
	if err != nil {
		return err
	}

	if len(files) == 0 {
		return fmt.Errorf("目录为空")
	}

	var buf bytes.Buffer
	tmp := make([]byte, 4)

	for _, f := range files {
		buf.WriteByte(0x22)
		buf.WriteString(f.Rel)
		buf.WriteByte(0x22)

		binary.LittleEndian.PutUint32(tmp, uint32(f.Size))
		buf.Write(tmp)
	}

	ds := uint32(4 + buf.Len())

	mkdirForFile(outfile)

	wf, err := os.Create(outfile)
	if err != nil {
		return err
	}
	defer wf.Close()

	binary.LittleEndian.PutUint32(tmp, ds)
	wf.Write(tmp)
	wf.Write(buf.Bytes())

	for i, f := range files {
		if err := appendFile(wf, f.Abs); err != nil {
			return err
		}
		fmt.Printf("\r  打包 %d/%d", i+1, len(files))
	}

	fmt.Printf("\n✓ → %s\n", outfile)
	return nil
}

func packNSA(indir, outfile string) error {
	files, err := collectFiles(indir)
	if err != nil {
		return err
	}

	if len(files) == 0 {
		return fmt.Errorf("目录为空")
	}

	var table bytes.Buffer
	tmp := make([]byte, 4)

	var offset uint32

	for _, f := range files {
		table.WriteString(f.Rel)
		table.WriteByte(0)
		table.WriteByte(0) // comp_type

		binary.BigEndian.PutUint32(tmp, offset)
		table.Write(tmp)

		binary.BigEndian.PutUint32(tmp, uint32(f.Size))
		table.Write(tmp)

		binary.BigEndian.PutUint32(tmp, uint32(f.Size))
		table.Write(tmp)

		offset += uint32(f.Size)
	}

	ds := uint32(6 + table.Len())

	mkdirForFile(outfile)

	wf, err := os.Create(outfile)
	if err != nil {
		return err
	}
	defer wf.Close()

	num := make([]byte, 2)
	binary.BigEndian.PutUint16(num, uint16(len(files)))
	wf.Write(num)

	binary.BigEndian.PutUint32(tmp, ds)
	wf.Write(tmp)
	wf.Write(table.Bytes())

	for i, f := range files {
		if err := appendFile(wf, f.Abs); err != nil {
			return err
		}
		fmt.Printf("\r  打包 %d/%d", i+1, len(files))
	}

	fmt.Printf("\n✓ → %s\n", outfile)
	return nil
}

func containsString(arr []string, s string) bool {
	for _, x := range arr {
		if x == s {
			return true
		}
	}
	return false
}

func smartExtract(args []string) {
	var inp, out string
	var filters, positional []string

	env := strings.ToLower(os.Getenv("ONS_BINWALK"))
	useBinwalk := env == "1" || env == "true" || env == "yes" || env == "on"

	i := 0
	for i < len(args) {
		a := args[i]

		switch {
		case a == "-i" || a == "--input":
			if i+1 < len(args) {
				inp = args[i+1]
				i += 2
			} else {
				i++
			}
		case a == "-o" || a == "--outdir" || a == "--out":
			if i+1 < len(args) {
				out = args[i+1]
				i += 2
			} else {
				i++
			}
		case a == "-b" || a == "--binwalk":
			useBinwalk = true
			i++
		case a == "img" || a == "voice":
			filters = append(filters, a)
			i++
		case a == "-h" || a == "--help":
			printHelp()
			return
		case strings.HasPrefix(a, "-"):
			fmt.Println("未知选项:", a)
			i++
		default:
			positional = append(positional, a)
			i++
		}
	}

	if inp == "" && len(positional) > 0 {
		inp = positional[0]
		positional = positional[1:]
	}

	if out == "" && len(positional) > 0 {
		out = positional[0]
	}

	ftype := ""

	if containsString(filters, "img") && !containsString(filters, "voice") {
		ftype = "img"
	} else if containsString(filters, "voice") && !containsString(filters, "img") {
		ftype = "voice"
	} else if len(filters) > 1 {
		fmt.Println("  [*] 同时指定 img/voice，将提取全部")
	}

	if inp == "" {
		printHelp()
		return
	}

	if isFile(inp) && !knownArchiveExt(inp) {
		if useBinwalk {
			od := out
			if od == "" {
				od = filepath.Join(filepath.Dir(absPath(inp)), filepath.Base(inp)+"_binwalk")
			}

			fmt.Println("[*] 非已知封包扩展名，使用 binwalk:", inp)
			binwalkExtract(inp, od)
			return
		}

		fmt.Println("[-] 不是已知封包扩展名:", inp)
		fmt.Println("    如要强行用 binwalk，可加 --binwalk")
		return
	}

	targets := findNSInPath(inp)

	if len(targets) == 0 {
		fmt.Println("未找到封包:", inp)

		if useBinwalk && isFile(inp) {
			od := out
			if od == "" {
				od = filepath.Join(filepath.Dir(absPath(inp)), filepath.Base(inp)+"_binwalk")
			}
			binwalkExtract(inp, od)
		}

		return
	}

	od := out
	if od == "" {
		od = defaultOutdir(targets[0])
	}

	fmt.Printf("[*] 输出目录: %s/\n", od)

	for _, t := range targets {
		fmt.Printf("\n[+] 解包: %s\n", t)
		extract(t, od, ftype, useBinwalk)
	}

	fmt.Printf("\n全部完成 → %s/\n", od)
}

func printHelp() {
	fmt.Println(`
NS2/NSA 解包/打包工具 (Go 二进制版)
coder by qwen3.8 / ported from Python

用法:
  ons                                # 显示帮助
  ons help                           # 显示帮助
  ons version                        # 版本

命令行解包:
  ons -i <输入> [-o <输出>] [过滤] [--binwalk]
  ons <输入> [输出] [过滤] [--binwalk]

示例:
  ons -i arc1.nsa
  ons -i arc1.nsa -o out/
  ons -i ./game/ -o out/
  ons -i arc1.nsa img
  ons -i arc1.nsa voice
  ons -i unknown.bin --binwalk
  ons arc1.nsa out/ img

过滤:
  img      仅图片
  voice    仅音频
  不加     全部提取 + 自动解密 nscript.dat

打包:
  ons pack <目录> [输出文件]
  .nsa → NSA格式
  .ns2 → 引号格式

脚本加解密:
  ons dec <nscript.dat> [输出0.txt]
  ons enc <0.txt> [输出nscript.dat]

外部程序:
  ons binwalk <file> [参数...]
  ons exec <命令> [参数...]

说明:
  --binwalk 会在无法识别格式时调用:
      binwalk -e -C <输出目录> <文件>
`)
}

func main() {
	args := os.Args[1:]

	if len(args) == 0 {
		printHelp()
		return
	}

	cmd := strings.ToLower(args[0])

	switch cmd {
	case "help", "-h", "--help":
		printHelp()

	case "version", "-v", "--version":
		fmt.Println("ons", Version)

	case "-i", "--input":
		smartExtract(args)

	case "unpack", "x", "extract":
		smartExtract(args[1:])

	case "pack":
		if len(args) < 2 {
			fmt.Println("用法: ons pack <目录> [输出]")
			return
		}

		indir := args[1]
		if !isDir(indir) {
			fmt.Println("目录不存在:", indir)
			return
		}

		out := ""
		if len(args) > 2 {
			out = args[2]
		} else {
			out = strings.TrimRight(indir, "/") + "_repacked.ns2"
		}

		if strings.HasSuffix(strings.ToLower(out), ".nsa") {
			if err := packNSA(indir, out); err != nil {
				fmt.Println("打包失败:", err)
			}
		} else {
			if !strings.HasSuffix(strings.ToLower(out), ".ns2") {
				out += ".ns2"
			}

			if err := packQuote(indir, out); err != nil {
				fmt.Println("打包失败:", err)
			}
		}

	case "dec", "decrypt":
		src := "nscript.dat"
		dst := "0.txt"

		if len(args) > 1 {
			src = args[1]
		}
		if len(args) > 2 {
			dst = args[2]
		}

		if !isFile(src) {
			fmt.Println("文件不存在:", src)
			return
		}

		if err := xorFile(src, dst); err != nil {
			fmt.Println("失败:", err)
		} else {
			fmt.Printf("✓ 解密: %s → %s\n", src, dst)
		}

	case "enc", "encrypt":
		src := "0.txt"
		dst := "nscript.dat"

		if len(args) > 1 {
			src = args[1]
		}
		if len(args) > 2 {
			dst = args[2]
		}

		if !isFile(src) {
			fmt.Println("文件不存在:", src)
			return
		}

		if err := xorFile(src, dst); err != nil {
			fmt.Println("失败:", err)
		} else {
			fmt.Printf("✓ 加密: %s → %s\n", src, dst)
		}

	case "binwalk":
		if len(args) < 2 {
			fmt.Println("用法: ons binwalk <file> [更多参数]")
			return
		}
		os.Exit(runExternal("binwalk", args[1:]...))

	case "exec":
		if len(args) < 2 {
			fmt.Println("用法: ons exec <命令> [参数...]")
			return
		}
		os.Exit(runExternal(args[1], args[2:]...))

	default:
		smartExtract(args)
	}
}