package main

import (
	"bufio"
	"bytes"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
)

type Entry struct {
	Offset int64
	Size   int64
	Hex    string
	Desc   string
}

var (
	// 匹配 binwalk 输出行，例如：
	// 5397376                            0x525B80                           PNG image, total size: 2125920 bytes
	lineRe = regexp.MustCompile(`^\s*(\d+)\s+(0x[0-9A-Fa-f]+)\s+(.+?)\s*$`)

	// 匹配 total size: 2125920 bytes
	sizeRe = regexp.MustCompile(`total size:\s*(\d+)\s*bytes`)
)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintf(os.Stderr, "用法: %s <要分析的文件> [输出目录]\n", filepath.Base(os.Args[0]))
		fmt.Fprintf(os.Stderr, "示例: %s /storage/emulated/0/termux/game.droid\n", filepath.Base(os.Args[0]))
		fmt.Fprintf(os.Stderr, "默认输出目录: ./de_<原文件名>\n")
		os.Exit(1)
	}

	src := os.Args[1]

	// 默认输出到 ./de_原文件名
	// 如果你想输出到 ./de_game，可以手动指定第二个参数：
	// ./binde game.droid de_game
	outDir := "de_" + filepath.Base(src)
	if len(os.Args) >= 3 {
		outDir = os.Args[2]
	}

	entries, err := analyzeWithBinwalk(src)
	if err != nil {
		fmt.Fprintf(os.Stderr, "错误: %v\n", err)
		os.Exit(1)
	}

	if len(entries) == 0 {
		fmt.Fprintln(os.Stderr, "没有从 binwalk 输出中解析到带 total size 的条目。")
		os.Exit(0)
	}

	count, err := extractEntries(src, outDir, entries)
	if err != nil {
		fmt.Fprintf(os.Stderr, "提取失败: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("完成: 成功提取 %d/%d 个条目到 %s\n", count, len(entries), outDir)
}

// analyzeWithBinwalk 调用 binwalk 并解析输出
func analyzeWithBinwalk(path string) ([]Entry, error) {
	binwalk := os.Getenv("BINWALK")
	if binwalk == "" {
		binwalk = "binwalk"
	}

	cmd := exec.Command(binwalk, path)

	var out bytes.Buffer
	cmd.Stdout = &out
	cmd.Stderr = &out

	err := cmd.Run()

	// 如果 binwalk 返回非 0，但仍有输出，也尝试解析
	if err != nil && out.Len() == 0 {
		return nil, fmt.Errorf("执行 %s 失败: %w", binwalk, err)
	}

	entries := parseBinwalkOutput(out.Bytes())
	return entries, nil
}

// parseBinwalkOutput 解析 binwalk 文本输出
func parseBinwalkOutput(data []byte) []Entry {
	var entries []Entry

	sc := bufio.NewScanner(bytes.NewReader(data))
	sc.Buffer(make([]byte, 1024*1024), 1024*1024)

	for sc.Scan() {
		line := sc.Text()

		m := lineRe.FindStringSubmatch(line)
		if m == nil {
			continue
		}

		offset, err := strconv.ParseInt(m[1], 10, 64)
		if err != nil {
			continue
		}

		desc := m[3]

		sm := sizeRe.FindStringSubmatch(desc)
		if sm == nil {
			continue
		}

		size, err := strconv.ParseInt(sm[1], 10, 64)
		if err != nil || size <= 0 {
			continue
		}

		entries = append(entries, Entry{
			Offset: offset,
			Size:   size,
			Hex:    m[2],
			Desc:   desc,
		})
	}

	return entries
}

// extractEntries 根据 offset 和 size 从原文件中提取
func extractEntries(src, outDir string, entries []Entry) (int, error) {
	in, err := os.Open(src)
	if err != nil {
		return 0, err
	}
	defer in.Close()

	fi, err := in.Stat()
	if err != nil {
		return 0, err
	}
	fileSize := fi.Size()

	if err := os.MkdirAll(outDir, 0755); err != nil {
		return 0, err
	}

	manifestPath := filepath.Join(outDir, "extract_manifest.txt")
	manifest, err := os.Create(manifestPath)
	if err != nil {
		return 0, err
	}
	defer manifest.Close()

	fmt.Fprintf(manifest, "source_file: %s\n", src)
	fmt.Fprintf(manifest, "source_size: %d\n\n", fileSize)

	extracted := 0

	for i, e := range entries {
		if e.Offset < 0 || e.Offset >= fileSize {
			fmt.Fprintf(os.Stderr, "跳过: offset=%d 超出原文件范围(文件大小=%d)\n", e.Offset, fileSize)
			continue
		}

		size := e.Size
		available := fileSize - e.Offset

		if size > available {
			fmt.Fprintf(
				os.Stderr,
				"警告: offset=%d 请求大小=%d 超出文件末尾，改为读取 %d 字节\n",
				e.Offset,
				size,
				available,
			)
			size = available
		}

		ext := extFromDesc(e.Desc)
		name := makeFileName(i+1, e.Offset, e.Hex, ext)
		dst := filepath.Join(outDir, name)

		if err := writeRange(in, e.Offset, size, dst); err != nil {
			return extracted, fmt.Errorf("写入 %s 失败: %w", dst, err)
		}

		extracted++

		fmt.Printf(
			"[%03d] offset=%d (%s), size=%d -> %s\n",
			i+1,
			e.Offset,
			e.Hex,
			size,
			dst,
		)

		fmt.Fprintf(
			manifest,
			"[%03d] offset=%d (%s), size=%d, file=%s, desc=%s\n",
			i+1,
			e.Offset,
			e.Hex,
			size,
			name,
			e.Desc,
		)
	}

	return extracted, nil
}

// writeRange 从文件指定偏移读取 size 字节到目标文件
func writeRange(in *os.File, offset, size int64, dst string) error {
	if _, err := in.Seek(offset, io.SeekStart); err != nil {
		return err
	}

	out, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer out.Close()

	_, err = io.CopyN(out, in, size)
	if err == io.EOF {
		err = nil
	}

	return err
}

// makeFileName 生成输出文件名
// 例如：001_offset_525b80.png
func makeFileName(idx int, offset int64, hex, ext string) string {
	hex = strings.ToLower(strings.TrimPrefix(hex, "0x"))
	if hex == "" {
		hex = fmt.Sprintf("%x", offset)
	}

	return fmt.Sprintf("%03d_offset_%s%s", idx, hex, ext)
}

// extFromDesc 根据 binwalk 描述猜测扩展名
func extFromDesc(desc string) string {
	d := strings.ToLower(desc)

	switch {
	case strings.Contains(d, "png image"):
		return ".png"
	case strings.Contains(d, "jpeg"):
		return ".jpg"
	case strings.Contains(d, "jpg"):
		return ".jpg"
	case strings.Contains(d, "gif image"):
		return ".gif"
	case strings.Contains(d, "webp"):
		return ".webp"
	case strings.Contains(d, "bmp"):
		return ".bmp"
	case strings.Contains(d, "zip archive"):
		return ".zip"
	case strings.Contains(d, "gzip"):
		return ".gz"
	default:
		return ".bin"
	}
}