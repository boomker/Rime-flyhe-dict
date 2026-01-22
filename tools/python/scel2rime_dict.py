"""
搜狗细胞词库转鼠须管（Rime）词库

搜狗的 scel 词库是按照一定格式保存的 Unicode 编码文件，其中每两个字节表示一个字符（中文汉字或者英文字母），主要两部分:

1. 全局拼音表，在文件中的偏移值是 0x1540+4, 格式为 (py_idx, py_len, py_str)
    - py_idx: 两个字节的整数，代表这个拼音的索引
    - py_len: 两个字节的整数，拼音的字节长度
    - py_str: 当前的拼音，每个字符两个字节，总长 py_len

2. 汉语词组表，在文件中的偏移值是 0x2628 或 0x26c4, 格式为 (word_count, py_idx_count, py_idx_data, (word_len, word_str, ext_len, ext){word_count})，其中 (word_len, word, ext_len, ext){word_count} 一共重复 word_count 次, 表示拼音的相同的词一共有 word_count 个
    - word_count: 两个字节的整数，同音词数量
    - py_idx_count:  两个字节的整数，拼音的索引个数
    - py_idx_data: 两个字节表示一个整数，每个整数代表一个拼音的索引，拼音索引数
    - word_len:两个字节的整数，代表中文词组字节数长度
    - word_str: 汉语词组，每个中文汉字两个字节，总长度 word_len
    - ext_len: 两个字节的整数，可能代表扩展信息的长度，好像都是 10
    - ext: 扩展信息，一共 10 个字节，前两个字节是一个整数(不知道是不是词频)，后八个字节全是 0，ext_len 和 ext 一共 12 个字节

"""

import os
import glob
import datetime
import requests


def download_newest_scel_file(file_name):
    """从搜狗词库下载最新的 scel 文件"""
    # https://pinyin.sogou.com/d/dict/download_cell.php?id=4&name=网络流行新词【官方推荐】&f=detail
    url = "https://pinyin.sogou.com/d/dict/download_cell.php?id=4&name=%E7%BD%91%E7%BB%9C%E6%B5%81%E8%A1%8C%E6%96%B0%E8%AF%8D%E3%80%90%E5%AE%98%E6%96%B9%E6%8E%A8%E8%8D%90%E3%80%91"
    r = requests.get(url)
    with open(file_name, "wb") as f:
        f.write(r.content)


def convert_scel_to_rime():
    """使用 ImeWlConverterCmd.dll 进行转换"""
    scel_md5_files = glob.glob("*.scel")

    # 获取环境变量或默认值
    rime_freq = os.getenv("RIME_FREQ", "100")
    scel_output_file = "sogou_popular.dict.yaml"  # 始终输出为 sogou_popular.dict.yaml

    if scel_md5_files:
        scel_files_str = " ".join(scel_md5_files)
        command = f'''dotnet /tmp/imewlconverter/publish/ImeWlConverterCmd.dll -i:scel {scel_files_str} -r:{rime_freq} -ft:"rm:eng|rm:num|rm:space|rm:pun" -o:rime "{scel_output_file}"'''
        os.system(command)
    else:
        print("未找到 .scel 文件")


def update_yaml_file(dict_name, scel_output_file):
    """更新 Rime 词库的 YAML 文件格式"""
    data1 = """# Rime dictionary
# encoding: utf-8
#
#sogou 输入法网络流行新词
#
---
"""

    # 创建名称
    data2 = "name: " + dict_name + "\n"

    # 创建时间
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data3 = 'version: "' + now + '"\n'

    data4 = """
...

"""

    # 打开目标文件并写入数据
    with open(scel_output_file, "r+") as output_file:
        old = output_file.read()
        output_file.seek(0)
        output_file.write(data1)
        output_file.write(data2)
        output_file.write(data3)
        output_file.write(data4)
        output_file.write(old)


def main():
    file_name = "sogou_popular.scel"

    # 下载最新的 scel 文件
    download_newest_scel_file(file_name)

    # 转换 scel 为 Rime 词库
    convert_scel_to_rime()

    # 更新 YAML 文件
    dict_name = "sogou_popular"  # 请根据实际情况设置字典名称
    scel_output_file = "sogou_popular.dict.yaml"
    update_yaml_file(dict_name, scel_output_file)


if __name__ == "__main__":
    main()
