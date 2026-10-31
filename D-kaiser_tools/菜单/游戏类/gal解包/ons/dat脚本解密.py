import sys
import os

# 固定的工作根目录
ROOT_DIR = "/storage/emulated/0/termux"

def resolve_path(path: str) -> str:
    """
    如果路径是相对路径，则相对于 ROOT_DIR 返回绝对路径；
    如果已经是绝对路径，则直接返回（但仍建议放在根目录下）。
    """
    if os.path.isabs(path):
        return path
    return os.path.join(ROOT_DIR, path)


def xor_file(input_file, output_file, key=0x84):
    """
    对文件进行 XOR 加密/解密（同一操作）
    :param input_file: 输入文件路径
    :param output_file: 输出文件路径
    :param key: 异或密钥，默认为0x84
    :return: 成功返回True，否则False
    """
    try:
        with open(input_file, 'rb') as f_in:
            data = f_in.read()
    except FileNotFoundError:
        print(f"错误：文件 {input_file} 未找到。")
        return False
    except Exception as e:
        print(f"读取文件时出错：{e}")
        return False

    # 对每个字节进行异或
    transformed_data = bytes([b ^ key for b in data])

    try:
        with open(output_file, 'wb') as f_out:
            f_out.write(transformed_data)
        print(f"操作成功，结果已保存到 {output_file}")
        return True
    except Exception as e:
        print(f"写入文件时出错：{e}")
        return False


def get_input_file(prompt, default):
    """获取用户输入的文件路径，如果直接回车则返回默认值"""
    user_input = input(prompt).strip()
    return user_input if user_input else default


def main():
    print("=" * 40)
    print("NScripter 脚本工具 (密钥 0x84)")
    print("=" * 40)
    print(f"工作根目录：{ROOT_DIR}")
    print("所有相对路径将基于此目录解析。")
    print("请选择操作：")
    print(" [1] 解密 nscript.dat → nscript_decoded.txt")
    print(" [2] 加密为 nscript.dat (从文本文件)")
    print(" [0] 退出")
    print("-" * 40)

    choice = input("请输入数字 (0/1/2): ").strip()

    if choice == '0':
        print("退出程序。")
        return
    elif choice == '1':
        # 解密模式
        default_input = resolve_path("nscript.dat")
        prompt = f"请输入要解密的文件 (默认 {default_input}): "
        input_file = get_input_file(prompt, default_input)
        input_file = resolve_path(input_file)          # 确保基于根目录

        # 自动生成输出文件名
        base, ext = os.path.splitext(input_file)
        output_file = f"{base}_decoded.txt"
        print(f"输出文件将保存为: {output_file}")
        xor_file(input_file, output_file)
    elif choice == '2':
        # 加密模式
        default_input = resolve_path("nscript_decoded.txt")
        prompt = f"请输入要加密的文本文件 (默认 {default_input}): "
        input_file = get_input_file(prompt, default_input)
        input_file = resolve_path(input_file)

        base, ext = os.path.splitext(input_file)
        if ext.lower() == '.txt':
            output_file = base + '.dat'
        else:
            output_file = input_file + '_encrypted.dat'
        print(f"输出文件将保存为: {output_file}")
        xor_file(input_file, output_file)
    else:
        print("无效的选择，请重新运行程序。")


if __name__ == "__main__":
    main()