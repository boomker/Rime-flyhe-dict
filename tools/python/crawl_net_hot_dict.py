#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网络热词词库更新脚本
生成 Rime 输入法小鹤双拼词库
"""

import os
import re
import datetime

# ==================== 配置 ====================
# 文件路径配置
DIFF_SG_FILE = "diff_sg.txt"
FLYPY_SGHOT_FILE = "flypy_sghot.dict.yaml"
FLYPY_DYHOT_FILE = "flypy_dyhot.dict.yaml"
CACHE_FILE = "pinyin_cache.json"

# DeepSeek API 配置 (通过环境变量或 GitHub Secrets 获取)
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# 3天前时间戳
THREE_DAYS_AGO = (datetime.datetime.now() - datetime.timedelta(days=3)).strftime(
    "%Y-%m-%d"
)
TODAY = datetime.datetime.now().strftime("%Y-%m-%d")


# ==================== 小鹤双拼转换 ====================


def pinyin_to_flypy(quanpin_list):
    """全拼拼音转为小鹤双拼码

    Args:
        quanpin_list: 全拼拼音列表，如 ['zhong', 'guo']

    Returns:
        小鹤双拼列表，如 ['vs', 'go']
    """
    from functools import lru_cache

    shengmu_dict = {"zh": "v", "ch": "i", "sh": "u"}
    yunmu_dict = {
        "ou": "z",
        "iao": "n",
        "uang": "l",
        "iang": "l",
        "en": "f",
        "eng": "g",
        "ng": "g",
        "ang": "h",
        "an": "j",
        "ao": "c",
        "ai": "d",
        "ian": "m",
        "in": "b",
        "uo": "o",
        "un": "y",
        "iu": "q",
        "uan": "r",
        "iong": "s",
        "ong": "s",
        "ue": "t",
        "ve": "t",
        "ui": "v",
        "ua": "x",
        "ia": "x",
        "ie": "p",
        "uai": "k",
        "ing": "k",
        "ei": "w",
    }
    zero = {
        "a": "aa",
        "an": "an",
        "ai": "ai",
        "ang": "ah",
        "o": "oo",
        "ou": "ou",
        "e": "ee",
        "n": "en",
        "en": "en",
        "eng": "eg",
        "ei": "ei",
        "er": "er",
        "ao": "ao",
    }

    @lru_cache(maxsize=None, typed=True)
    def to_flypy(pinyin_str):
        # 错误 Pinyin 返回原始拼音串
        if len(pinyin_str) == 1 and pinyin_str not in zero:
            return ""
        if pinyin_str in zero:
            return zero[pinyin_str]
        if len(pinyin_str) > 1 and pinyin_str[1] == "h":
            shengmu = shengmu_dict.get(pinyin_str[:2], pinyin_str[:2])
            yunmu = yunmu_dict.get(pinyin_str[2:], pinyin_str[2:])
            return shengmu + yunmu
        else:
            shengmu = pinyin_str[:1]
            yunmu = yunmu_dict.get(pinyin_str[1:], pinyin_str[1:])
            return f"{shengmu}{yunmu}"

    return [to_flypy(x) if x.isalpha() else x for x in quanpin_list]


def convert_to_flypy(full_pinyin):
    """将空格分隔的全拼转换为小鹤双拼

    Args:
        full_pinyin: 全拼字符串，如 "zhong guo"

    Returns:
        小鹤双拼字符串，如 "vs go"
    """
    pinyin_list = full_pinyin.split()
    flypy_list = pinyin_to_flypy(pinyin_list)
    return " ".join(flypy_list)


# ==================== 时间戳区块处理 ====================


def parse_timestamp_blocks(content):
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
        blocks.append({"timestamp": timestamp, "lines": lines})

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


def convert_quanpin_to_flypy_line(line):
    """转换全拼为小鹤双拼

    Args:
        line: 原始行，如 "中国\tzhong guo\t100"

    Returns:
        str: 转换后的行，如 "中国\tvs go\t100"
    """
    if "\t" not in line:
        return line

    parts = line.split("\t")
    if len(parts) >= 2:
        keyword = parts[0]
        quanpin = parts[1]
        weight = parts[2] if len(parts) > 2 else "100"

        # 转换为小鹤双拼
        flypy = convert_to_flypy(quanpin)
        return f"{keyword}\t{flypy}\t{weight}"

    return line


def wrap_existing_content_with_timestamp(filepath, timestamp):
    """将现有文件内容用时间戳包裹

    Args:
        filepath: 文件路径
        timestamp: 时间戳

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
    parsed = parse_timestamp_blocks(content)

    # 保留 header
    header = parsed.get("header", "")
    if not header:
        header = f"""# Rime dictionary
# encoding: utf-8

---
name: flypy_sghot
version: {timestamp}
sort: by_weight
...

"""

    # 收集所有现有条目
    all_lines = []
    for block in parsed.get("blocks", []):
        for line in block["lines"]:
            # 转换全拼为双拼
            converted_line = convert_quanpin_to_flypy_line(line)
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


def process_diff_sg_file(diff_file, output_file, timestamp):
    """处理 diff_sg.txt 文件，转换为小鹤双拼并追加到词库

    Args:
        diff_file: diff_sg.txt 文件路径
        output_file: 输出词库文件路径
        timestamp: 时间戳

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
        parsed = parse_timestamp_blocks(existing_content)
        header = parsed.get("header", "")

        # 收集所有已有热词（用于去重）
        existing_keywords = set()
        for block in parsed.get("blocks", []):
            for line in block["lines"]:
                if "\t" in line:
                    existing_keywords.add(line.split("\t")[0])
    else:
        header = f"""# Rime dictionary
# encoding: utf-8

---
name: flypy_sghot
version: {timestamp}
sort: by_weight
...

"""
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

        # 转换为小鹤双拼
        flypy = convert_to_flypy(quanpin)
        weight = parts[2].strip() if len(parts) > 2 else "100"
        new_lines.append(f"{keyword}\t{flypy}\t{weight}")

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
            wrap_existing_content_with_timestamp(output_file, timestamp)
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


def cleanup_old_entries(filepath, days=3):
    """清理指定天数之前的词条

    Args:
        filepath: 词库文件路径
        days: 保留天数，默认3天

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
    parsed = parse_timestamp_blocks(content)
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


def merge_dict_files(dyhot_file, sghot_file, timestamp):
    """合并抖音热词和搜狗热词词库

    Args:
        dyhot_file: 抖音热词文件
        sghot_file: 搜狗热词文件
        timestamp: 时间戳

    Returns:
        bool: 是否执行了合并
    """
    if not os.path.exists(dyhot_file):
        print(f"  {dyhot_file} 不存在，跳过合并")
        return False

    # 读取抖音热词
    with open(dyhot_file, "r", encoding="utf-8") as f:
        dyhot_content = f.read()

    dyhot_parsed = parse_timestamp_blocks(dyhot_content)

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

        sghot_parsed = parse_timestamp_blocks(sghot_content)
        header = sghot_parsed.get("header", "")

        # 收集已存在的关键词
        existing_keywords = set()
        for block in sghot_parsed.get("blocks", []):
            for line in block["lines"]:
                if "\t" in line:
                    keyword = line.split("\t")[0]
                    existing_keywords.add(keyword)
    else:
        header = f"""# Rime dictionary
# encoding: utf-8

---
name: flypy_sghot
version: {timestamp}
sort: by_weight
...

"""
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
            wrap_existing_content_with_timestamp(sghot_file, timestamp)
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


def main():
    print("=" * 50)
    print("网络热词词库更新脚本")
    print("=" * 50)

    timestamp = TODAY

    # 1. 处理 diff_sg.txt（搜狗增量更新）
    print("\n[1/5] 处理 diff_sg.txt...")
    process_diff_sg_file(DIFF_SG_FILE, FLYPY_SGHOT_FILE, timestamp)

    # 2. 合并抖音热词（从 flyhe_dyhot.dict.yaml）
    print("\n[2/5] 合并抖音热词...")
    merge_dict_files(FLYPY_DYHOT_FILE, FLYPY_SGHOT_FILE, timestamp)

    # 3. 清理过期条目（3天前）
    print("\n[3/5] 清理过期条目...")
    cleanup_old_entries(FLYPY_SGHOT_FILE, days=3)
    cleanup_old_entries(FLYPY_DYHOT_FILE, days=3)

    # 4. 更新版本号
    print("\n[4/5] 更新版本号...")
    update_version(FLYPY_SGHOT_FILE)

    # 5. 清理临时文件
    print("\n[5/5] 清理临时文件...")
    if os.path.exists(DIFF_SG_FILE):
        os.remove(DIFF_SG_FILE)
        print(f"  已删除 {DIFF_SG_FILE}")

    print("\n" + "=" * 50)
    print("完成!")
    print(f"日期: {timestamp}")
    print("=" * 50)


if __name__ == "__main__":
    main()
