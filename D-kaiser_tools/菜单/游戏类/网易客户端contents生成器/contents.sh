#!/bin/bash
mkdir 网易客户端工作目录
# 根目录路径
root_dir="/storage/emulated/0/termux/"

# 输出文件路径
output_file="/storage/emulated/0/termux/网易客户端工作目录/contents.json"

if [ ! -d "$root_dir" ]; then
    echo "根目录不存在：$root_dir"
    exit 1
fi

> "$output_file"

echo "{
    \"content\": [" > "$output_file"

find "$root_dir" -mindepth 1 -print0 | while IFS= read -r -d '' item; do
    relative_path="${item#$root_dir}"
    relative_path="${relative_path#/}"
    echo "        {
            \"path\": \"$relative_path\"
        }," >> "$output_file"
done

sed -i '$ s/,$//' "$output_file"

echo "]" >> "$output_file"

echo "}" >> "$output_file"

echo "文件和文件夹名称已写入到 $output_file"
