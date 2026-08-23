#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网络热词词库更新脚本
生成 Rime 输入法小鹤双拼词库（--encoding flypy，默认）
或无声调全拼词库（--encoding quanpin，供 full_pinyin 分支使用）
"""

import argparse
import datetime
import os
import re
import textwrap

from flypy_codec import (
    convert_to_flypy,
    is_valid_flypy_code,
    is_valid_quanpin_code,
    normalize_pinyin_text,
)

# ==================== 配置 ====================
# 文件路径配置
DIFF_SG_FILE = "diff_sg.txt"
TODAY = datetime.datetime.now().strftime("%Y-%m-%d")

ENCODING_FLYPY = "flypy"
ENCODING_QUANPIN = "quanpin"
ENCODINGS = (ENCODING_FLYPY, ENCODING_QUANPIN)


def dict_file_paths(encoding):
    """按编码模式返回（搜狗热词文件，抖音热词文件）路径。

    双拼沿用历史文件名；全拼使用 *_quanpin 后缀的本地中间文件，
    推送到 full_pinyin 分支时再改回正式文件名。
    """
    if encoding == ENCODING_QUANPIN:
        return "flypy_sghot_quanpin.dict.yaml", "flypy_dyhot_quanpin.dict.yaml"
    return "flypy_sghot.dict.yaml", "flypy_dyhot.dict.yaml"


SGHOT_HEADER = textwrap.dedent("""\
    # Rime dictionary
    # encoding: utf-8

    ---
    name: flypy_sghot
    version: {timestamp}
    sort: by_weight
    ...

    """)

QUANPIN_SGHOT_HEADER = textwrap.dedent("""\
    # Rime dictionary
    # encoding: utf-8
    # 热词编码为无声调全拼（full_pinyin 分支）

    ---
    name: flypy_sghot
    version: {timestamp}
    sort: by_weight
    ...

    """)


def sghot_header_template(encoding):
    return QUANPIN_SGHOT_HEADER if encoding == ENCODING_QUANPIN else SGHOT_HEADER


def encode_code(raw_code, encoding):
    """把原始拼音编码转换为指定编码（双拼或无声调全拼）。"""
    if encoding == ENCODING_QUANPIN:
        return normalize_pinyin_text(raw_code)
    return convert_to_flypy(raw_code)


def is_valid_code(code, encoding):
    """按编码模式校验词库编码。"""
    if encoding == ENCODING_QUANPIN:
        return is_valid_quanpin_code(code)
    return is_valid_flypy_code(code)


def encode_dict_line(line, encoding):
    """把词库行的编码列归一化为指定编码。"""
    if "\t" not in line:
        return line

    parts = line.split("\t")
    if len(parts) < 2:
        return line

    keyword = parts[0].strip()
    raw_code = parts[1].strip()
    weight = parts[2].strip() if len(parts) > 2 else "100"
    code = encode_code(raw_code, encoding)
    if is_valid_code(code, encoding):
        return f"{keyword}\t{code}\t{weight}"
    return line


def normalize_dict_line(line, encoding):
    """把词库行的编码列归一化为指定编码（双拼或无声调全拼）。"""
    return encode_dict_line(line, encoding)


# ==================== 时间戳区块处理 ====================


def parse_timestamp_blocks(content, encoding=ENCODING_FLYPY):
    """解析时间戳区块

    Returns:
        dict: {
            'header': 文件头部内容,
            'blocks': [{'timestamp': '2026-03-02', 'lines': [...]}]
        }
    """
    # 分离header和区块内容
    header_end = re.search(r"## \d{4}-\d{2}-\d{2} \{", content)
    if header_end:
        header = content[: header_end.start()].strip()
        block_content = content[header_end.start() :]
    else:
        header = content.strip()
        block_content = ""

    # 提取所有时间戳区块
    blocks = []
    block_pattern = r"## (\d{4}-\d{2}-\d{2}) \{\n([\s\S]*?)\n## \1 \}"
    matches = re.findall(block_pattern, block_content)
    for timestamp, block_text in matches:
        lines = [line.strip() for line in block_text.split("\n") if line.strip()]
        blocks.append(
            {
                "timestamp": timestamp,
                "lines": [normalize_dict_line(line, encoding) for line in lines],
            }
        )

    return {"header": header, "blocks": blocks}


def wrap_with_timestamp(content, timestamp):
    """将内容用时间戳包裹

    Args:
        content: 要包裹的内容
        timestamp: 时间戳，如 '2026-03-02'

    Returns:
        str: 包裹后的内容
    """
    return f"## {timestamp} {{\n{content}\n## {timestamp} }}"


def is_content_wrapped(content):
    """检查内容是否已被时间戳包裹

    Args:
        content: 文件内容

    Returns:
        bool: 是否已包裹
    """
    # 检查是否有时间戳区块格式
    return bool(re.search(r"## \d{4}-\d{2}-\d{2} \{", content))


def convert_dict_line(line, encoding):
    """转换全拼词库行到指定编码（双拼或保持无声调全拼）

    Args:
        line: 原始行，如 "中国\tzhong guo\t100"

    Returns:
        str: 转换后的行，双拼模式如 "中国\tvs go\t100"，全拼模式如 "中国\tzhong guo\t100"
    """
    if "\t" not in line:
        return line

    parts = line.split("\t")
    if len(parts) >= 2:
        keyword = parts[0]
        quanpin = parts[1]
        weight = parts[2] if len(parts) > 2 else "100"

        code = encode_code(quanpin, encoding)
        if is_valid_code(code, encoding):
            return f"{keyword}\t{code}\t{weight}"

    return line


def wrap_existing_content_with_timestamp(filepath, timestamp, encoding=ENCODING_FLYPY):
    """将现有文件内容用时间戳包裹

    Args:
        filepath: 文件路径
        timestamp: 时间戳
        encoding: 目标编码（双拼或无声调全拼）

    Returns:
        bool: 是否执行了包裹操作
    """
    if not os.path.exists(filepath):
        return False

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # 检查是否已被包裹
    if is_content_wrapped(content):
        print(f"  文件 {filepath} 已被时间戳包裹，跳过")
        return False

    # 解析内容
    parsed = parse_timestamp_blocks(content, encoding)

    # 保留 header
    header = parsed.get("header", "")
    if not header:
        header = sghot_header_template(encoding).format(timestamp=timestamp)

    # 收集所有现有条目
    all_lines = []
    for block in parsed.get("blocks", []):
        for line in block["lines"]:
            # 转换到目标编码
            converted_line = convert_dict_line(line, encoding)
            all_lines.append(converted_line)

    # 如果没有现有内容，直接返回
    if not all_lines:
        print(f"  文件 {filepath} 无内容需要包裹")
        return False

    # 写入包裹后的内容
    wrapped_content = (
        header + "\n" + wrap_with_timestamp("\n".join(all_lines), timestamp) + "\n"
    )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(wrapped_content)

    print(f"  已将 {filepath} 内容用时间戳 {timestamp} 包裹")
    return True


# ==================== diff_sg.txt 处理 ====================


def process_diff_sg_file(diff_file, output_file, timestamp, encoding=ENCODING_FLYPY):
    """处理 diff_sg.txt 文件，转换为指定编码并追加到词库

    Args:
        diff_file: diff_sg.txt 文件路径
        output_file: 输出词库文件路径
        timestamp: 时间戳
        encoding: 目标编码（双拼或无声调全拼）

    Returns:
        int: 处理的条目数量
    """
    if not os.path.exists(diff_file):
        print(" diff_sg.txt 文件不存在，跳过")
        return 0

    with open(diff_file, "r", encoding="utf-8") as f:
        diff_lines = f.readlines()

    # 解析现有文件
    if os.path.exists(output_file):
        with open(output_file, "r", encoding="utf-8") as f:
            existing_content = f.read()
        parsed = parse_timestamp_blocks(existing_content, encoding)
        header = parsed.get("header", "")

        # 收集所有已有热词（用于去重）
        existing_keywords = set()
        for block in parsed.get("blocks", []):
            for line in block["lines"]:
                if "\t" in line:
                    existing_keywords.add(line.split("\t")[0])
    else:
        header = sghot_header_template(encoding).format(timestamp=timestamp)
        existing_keywords = set()

    # 处理 diff_sg.txt 内容
    new_lines = []
    for line in diff_lines:
        line = line.strip()
        if not line or "\t" not in line:
            continue

        parts = line.split("\t")
        if len(parts) < 2:
            continue

        keyword = parts[0].strip()
        quanpin = parts[1].strip()

        # 跳过已存在的关键词
        if keyword in existing_keywords:
            continue

        # 转换为目标编码
        code = encode_code(quanpin, encoding)
        weight = parts[2].strip() if len(parts) > 2 else "100"
        if is_valid_code(code, encoding):
            new_lines.append(f"{keyword}\t{code}\t{weight}")

    if not new_lines:
        print("  无新条目需要添加")
        return 0

    new_lines.sort(key=lambda x: (len(x.split("\t")[0]), x.split("\t")[1]))

    # 追加到现有文件
    if os.path.exists(output_file):
        with open(output_file, "r", encoding="utf-8") as f:
            existing_content = f.read()

        # 检查是否需要添加新区块
        if is_content_wrapped(existing_content):
            # 已包裹，直接追加新区块
            wrapped_block = wrap_with_timestamp("\n".join(new_lines), timestamp)
            new_content = existing_content.rstrip() + "\n\n" + wrapped_block + "\n"
        else:
            # 未包裹，需要包裹现有内容后追加
            wrap_existing_content_with_timestamp(output_file, timestamp, encoding)
            with open(output_file, "r", encoding="utf-8") as f:
                existing_content = f.read()
            wrapped_block = wrap_with_timestamp("\n".join(new_lines), timestamp)
            new_content = existing_content.rstrip() + "\n\n" + wrapped_block + "\n"
    else:
        # 新建文件
        wrapped_block = wrap_with_timestamp("\n".join(new_lines), timestamp)
        new_content = header + "\n" + wrapped_block + "\n"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"  已添加 {len(new_lines)} 个新条目到 {output_file}")
    return len(new_lines)


# ==================== 3天前数据清理 ====================


def cleanup_old_entries(filepath, days=3, encoding=ENCODING_FLYPY):
    """清理指定天数之前的词条

    Args:
        filepath: 词库文件路径
        days: 保留天数，默认3天
        encoding: 目标编码（双拼或无声调全拼）

    Returns:
        int: 清理的条目数量
    """
    if not os.path.exists(filepath):
        return 0

    cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime(
        "%Y-%m-%d"
    )

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # 解析时间戳区块
    parsed = parse_timestamp_blocks(content, encoding)
    header = parsed.get("header", "")

    # 过滤保留指定天数内的区块
    recent_blocks = [
        block for block in parsed.get("blocks", []) if block["timestamp"] >= cutoff_date
    ]

    # 统计被删除的条目
    removed_count = 0
    for block in parsed.get("blocks", []):
        if block["timestamp"] < cutoff_date:
            removed_count += len(block["lines"])

    if removed_count == 0:
        print("  无需要清理的过期条目")
        return 0

    # 重建文件内容
    output_lines = [header]

    for block in recent_blocks:
        output_lines.append(f"## {block['timestamp']} {{")
        output_lines.extend(block["lines"])
        output_lines.append(f"## {block['timestamp']} }}")
        output_lines.append("")

    new_content = "\n".join(output_lines).strip() + "\n"

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"  已清理 {removed_count} 个过期条目（{cutoff_date}之前）")
    return removed_count


# ==================== 合并 dyhot 和 sghot 词库 ====================


def merge_dict_files(dyhot_file, sghot_file, timestamp, encoding=ENCODING_FLYPY):
    """合并抖音热词和搜狗热词词库

    Args:
        dyhot_file: 抖音热词文件
        sghot_file: 搜狗热词文件
        timestamp: 时间戳
        encoding: 目标编码（双拼或无声调全拼）

    Returns:
        bool: 是否执行了合并
    """
    if not os.path.exists(dyhot_file):
        print(f"  {dyhot_file} 不存在，跳过合并")
        return False

    # 读取抖音热词
    with open(dyhot_file, "r", encoding="utf-8") as f:
        dyhot_content = f.read()

    dyhot_parsed = parse_timestamp_blocks(dyhot_content, encoding)

    # 收集所有抖音热词
    dyhot_keywords = set()
    dyhot_lines = []
    for block in dyhot_parsed.get("blocks", []):
        for line in block["lines"]:
            if "\t" in line:
                keyword = line.split("\t")[0]
                dyhot_keywords.add(keyword)
                dyhot_lines.append(line)

    if not dyhot_lines:
        print("  无抖音热词需要合并")
        return False

    # 读取搜狗热词
    if os.path.exists(sghot_file):
        with open(sghot_file, "r", encoding="utf-8") as f:
            sghot_content = f.read()

        sghot_parsed = parse_timestamp_blocks(sghot_content, encoding)
        header = sghot_parsed.get("header", "")

        # 收集已存在的关键词
        existing_keywords = set()
        for block in sghot_parsed.get("blocks", []):
            for line in block["lines"]:
                if "\t" in line:
                    keyword = line.split("\t")[0]
                    existing_keywords.add(keyword)
    else:
        header = sghot_header_template(encoding).format(timestamp=timestamp)
        existing_keywords = set()

    # 过滤掉已存在的抖音热词
    new_dyhot_lines = [
        line for line in dyhot_lines if line.split("\t")[0] not in existing_keywords
    ]

    if not new_dyhot_lines:
        print("  所有抖音热词已存在于搜狗词库中")
        return False

    # 追加到搜狗热词文件
    wrapped_block = wrap_with_timestamp("\n".join(new_dyhot_lines), timestamp)

    if os.path.exists(sghot_file):
        with open(sghot_file, "r", encoding="utf-8") as f:
            existing_content = f.read()

        if is_content_wrapped(existing_content):
            new_content = existing_content.rstrip() + "\n\n" + wrapped_block + "\n"
        else:
            # 需要先包裹现有内容
            wrap_existing_content_with_timestamp(sghot_file, timestamp, encoding)
            with open(sghot_file, "r", encoding="utf-8") as f:
                existing_content = f.read()
            new_content = existing_content.rstrip() + "\n\n" + wrapped_block + "\n"
    else:
        new_content = header + "\n" + wrapped_block + "\n"

    with open(sghot_file, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"  已合并 {len(new_dyhot_lines)} 个抖音热词到 {sghot_file}")
    return True


# ==================== 版本号更新 ====================


def update_version(filepath):
    """更新词库版本号"""
    if not os.path.exists(filepath):
        return

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # 更新 version
    new_content = re.sub(r"version: \d{4}-\d{2}-\d{2}", f"version: {TODAY}", content)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"  已更新版本号为 {TODAY}")


# ==================== 主函数 ====================


def parse_args():
    parser = argparse.ArgumentParser(description="网络热词词库更新脚本")
    parser.add_argument(
        "--encoding",
        choices=ENCODINGS,
        default=ENCODING_FLYPY,
        help="词库编码：flypy=小鹤双拼（默认，提交到 main），quanpin=无声调全拼（提交到 full_pinyin 分支）",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    encoding = args.encoding
    sghot_file, dyhot_file = dict_file_paths(encoding)

    print("=" * 50)
    print("网络热词词库更新脚本")
    print(f"编码模式: {encoding}")
    print("=" * 50)

    timestamp = TODAY

    # 1. 处理 diff_sg.txt（搜狗增量更新）
    print("\n[1/4] 处理 diff_sg.txt...")
    process_diff_sg_file(DIFF_SG_FILE, sghot_file, timestamp, encoding)

    # 2. 合并抖音热词（从对应编码的抖音热词文件）
    print("\n[2/4] 合并抖音热词...")
    merge_dict_files(dyhot_file, sghot_file, timestamp, encoding)

    # 3. 清理过期条目（3天前）
    print("\n[3/4] 清理过期条目...")
    cleanup_old_entries(sghot_file, days=3, encoding=encoding)
    cleanup_old_entries(dyhot_file, days=3, encoding=encoding)

    # 4. 更新版本号
    print("\n[4/4] 更新版本号...")
    update_version(sghot_file)

    # diff_sg.txt 等中间文件的清理交给流水线（另一种编码模式还要复用）
    print("\n" + "=" * 50)
    print("完成!")
    print(f"日期: {timestamp}")
    print(f"输出: {sghot_file}")
    print("=" * 50)


if __name__ == "__main__":
    main()
