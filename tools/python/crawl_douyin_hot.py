#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抖音热榜词条抓取脚本
自动生成 Rime 输入法字典文件
自动选择 DeepSeek 当前可用 pro 模型生成拼音
支持备用数据源
支持双拼（--encoding flypy，默认）与无声调全拼（--encoding quanpin）两种编码输出
"""

import argparse
import datetime
import json
import os
import re
import textwrap
import time

import requests
from dateutil.relativedelta import relativedelta
from openai import OpenAI

from deepseek_model import resolve_deepseek_pro_model
from flypy_codec import (
    convert_to_flypy,
    is_valid_flypy_code,
    is_valid_quanpin_code,
    normalize_pinyin_text,
)

# ==================== 配置 ====================
# 主数据源和备用数据源
PRIMARY_API_URL = "https://v2.xxapi.cn/api/douyinhot"
FALLBACK_API_URL = "https://v2.xxapi.cn/api/baiduhot"

ENCODING_FLYPY = "flypy"
ENCODING_QUANPIN = "quanpin"
ENCODINGS = (ENCODING_FLYPY, ENCODING_QUANPIN)


def output_file_for(encoding):
    """按编码模式返回输出文件路径（全拼使用 *_quanpin 中间文件，供 full_pinyin 分支使用）。"""
    if encoding == ENCODING_QUANPIN:
        return "./flypy_dyhot_quanpin.dict.yaml"
    return "./flypy_dyhot.dict.yaml"


DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

# DeepSeek API 基础URL
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# 拼音缓存文件
CACHE_FILE = "./pinyin_cache.json"
_RESOLVED_DEEPSEEK_MODEL = None

DYHOT_HEADER = textwrap.dedent(
    """\
    # Rime dictionary
    # encoding: utf-8

    ---
    name: flyhe_dyhot
    version: {today}
    sort: by_weight
    ...

    """
)

# ==================== 辅助函数 ====================


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


def load_pinyin_cache():
    """加载拼音缓存"""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cache = json.load(f)
                return {
                    keyword: normalize_pinyin_text(pinyin)
                    for keyword, pinyin in cache.items()
                    if normalize_pinyin_text(pinyin)
                }
        except:
            return {}
    return {}


def save_pinyin_cache(cache):
    """保存拼音缓存"""
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存缓存失败: {e}")


def generate_pinyin_with_deepseek(keywords, cache):
    """使用 DeepSeek 生成拼音"""
    if not DEEPSEEK_API_KEY:
        print("警告: 未设置 DEEPSEEK_API_KEY 环境变量，将使用 pypinyin 转换")
        return simple_pinyin_batch(keywords, cache)

    # 检查缓存
    uncached_keywords = [kw for kw in keywords if kw not in cache]
    if not uncached_keywords:
        print("所有关键词拼音已在缓存中")
        return cache

    print(f"需要为 {len(uncached_keywords)} 个关键词生成拼音...")

    try:
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
        model_name = get_deepseek_pro_model()
        print(f"使用 DeepSeek 模型: {model_name}")

        # 分批处理（每次最多20个）
        batch_size = 20
        for i in range(0, len(uncached_keywords), batch_size):
            batch = uncached_keywords[i : i + batch_size]
            keywords_str = "\n".join([f"{i+1}. {kw}" for i, kw in enumerate(batch)])

            prompt = textwrap.dedent(
                f"""\
                请为以下中文热词标注汉语拼音。
                要求：
                1. 考虑句中多音字的正确读音（如"行长"应读"hang zhang"不是"xing zhang"，"首都"应读"shou du"不是"shou dou"）
                2. 每个词一行，格式：汉字 拼音
                3. 拼音之间用空格分隔
                4. 拼音只使用小写英文字母，不要声调符号、不要数字、不要注释
                5. 只返回结果，不要其他说明

                热词列表：
                {keywords_str}

                请开始："""
            )

            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个专业的汉语拼音标注助手，擅长处理多音字和词组连读，并严格返回无声调拼音。",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=2000,
                reasoning_effort="high",
                extra_body={"thinking": {"type": "enabled"}},
            )

            result_text = response.choices[0].message.content

            # 解析结果
            for line in result_text.strip().split("\n"):
                line = line.strip()
                # 匹配 "1. 汉字 拼音" 或 "汉字 拼音" 格式
                match = re.match(r"^(?:\d+\.\s*)?(\S+)\s+(.+)$", line)
                if match:
                    kw = match.group(1)
                    pinyin = normalize_pinyin_text(match.group(2).strip())
                    if kw in uncached_keywords:
                        cache[kw] = pinyin

            print(
                f"  已处理 {min(i+batch_size, len(uncached_keywords))}/{len(uncached_keywords)}"
            )

            save_pinyin_cache(cache)

    except Exception as e:
        print(f"DeepSeek API 调用失败: {e}")
        print("将使用 pypinyin 作为备用方案...")
        raise Exception(f"DeepSeek API 异常: {e}")

    return cache


def get_deepseek_pro_model():
    """获取当前可用的 DeepSeek pro 模型名。"""
    global _RESOLVED_DEEPSEEK_MODEL
    if _RESOLVED_DEEPSEEK_MODEL:
        return _RESOLVED_DEEPSEEK_MODEL

    _RESOLVED_DEEPSEEK_MODEL = resolve_deepseek_pro_model(
        api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL
    )
    return _RESOLVED_DEEPSEEK_MODEL


def simple_pinyin(keyword):
    """简单的拼音转换（备用方案）"""
    try:
        from pypinyin import lazy_pinyin

        return " ".join(lazy_pinyin(keyword))
    except ImportError:
        return ""


def simple_pinyin_batch(keywords, cache):
    """批量使用 pypinyin 转换"""
    print("使用 pypinyin 库生成拼音...")
    try:
        from pypinyin import lazy_pinyin

        for kw in keywords:
            if kw not in cache:
                cache[kw] = " ".join(lazy_pinyin(kw))
        print(f"  pypinyin 处理完成 {len(keywords)} 个关键词")
    except ImportError:
        print("错误: pypinyin 库未安装")
        raise Exception("pypinyin 库未安装")

    return cache


def get_pinyin(keyword, cache):
    """获取拼音"""
    if keyword in cache:
        normalized = normalize_pinyin_text(cache[keyword])
        if normalized:
            cache[keyword] = normalized
            return normalized

    # 使用简单方案作为后备
    pinyin = normalize_pinyin_text(simple_pinyin(keyword))
    cache[keyword] = pinyin
    return pinyin


def fetch_hot_keywords_from_url(api_url, source_name):
    """从指定URL获取热榜关键词"""
    max_retries = 3
    retry_delay = 3

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(api_url, timeout=30)
            data = response.json()

            if data.get("code") != 200:
                print(f"{source_name} API返回错误: {data.get('msg')}")
                return None, f"API错误: {data.get('msg')}"

            keywords = []
            for item in data.get("data", []):
                word = item.get("word", "")
                if word:
                    if re.match(r"^[\u4e00-\u9fa5]+$", word) and len(word) >= 2:
                        keywords.append(word)

            keywords = list(dict.fromkeys(keywords))
            return keywords, None

        except requests.Timeout:
            if attempt < max_retries:
                print(f"  请求超时，{retry_delay}秒后重试 ({attempt}/{max_retries})...")
                time.sleep(retry_delay)
            else:
                return None, "请求超时"
        except requests.RequestException as e:
            if attempt < max_retries:
                print(
                    f"  网络异常: {str(e)}，{retry_delay}秒后重试 ({attempt}/{max_retries})..."
                )
                time.sleep(retry_delay)
            else:
                return None, f"网络异常: {str(e)}"
        except Exception as e:
            if attempt < max_retries:
                print(
                    f"  未知错误: {str(e)}，{retry_delay}秒后重试 ({attempt}/{max_retries})..."
                )
                time.sleep(retry_delay)
            else:
                return None, f"未知错误: {str(e)}"

    return None, "重试次数耗尽"


def fetch_hot_keywords():
    """获取热榜关键词（支持备用源）"""
    # 尝试主数据源
    print("尝试获取数据源: 抖音热榜...")
    keywords, error = fetch_hot_keywords_from_url(PRIMARY_API_URL, "抖音热榜")

    if keywords:
        return keywords, "抖音热榜"

    print(f"抖音热榜获取失败: {error}")

    # 尝试备用数据源
    print("尝试获取数据源: 百度热搜...")
    keywords, error = fetch_hot_keywords_from_url(FALLBACK_API_URL, "百度热搜")

    if keywords:
        return keywords, "百度热搜"

    print(f"百度热搜获取失败: {error}")

    return [], ""


def is_valid_keyword(keyword):
    """检查关键词是否有效（只包含中文）"""
    return bool(re.match(r"^[\u4e00-\u9fa5]+$", keyword)) and len(keyword) >= 2


def sort_keywords(keywords, cache):
    """按照字符长度排序，长度相同则按拼音字母排序"""

    def sort_key(kw):
        pinyin = get_pinyin(kw, cache).replace(" ", "")
        return (len(kw), pinyin)

    return sorted(keywords, key=sort_key)


def read_existing_file(filepath, encoding=ENCODING_FLYPY):
    """读取现有文件内容，解析时间戳区块"""
    if not os.path.exists(filepath):
        return {"header": "", "blocks": []}

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

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
        # 把旧行归一化到当前编码
        converted_lines = []
        for line in lines:
            if "\t" in line:
                parts = line.split("\t")
                if len(parts) >= 2:
                    keyword = parts[0]
                    old_pinyin = parts[1]
                    weight = parts[2] if len(parts) > 2 else "100"
                    # 编码已是目标格式时原样保留（转换不幂等，zh/ch/sh 音节二次转换会失效）
                    new_pinyin = old_pinyin.strip()
                    if not is_valid_code(new_pinyin, encoding):
                        new_pinyin = encode_code(new_pinyin, encoding)
                    if is_valid_code(new_pinyin, encoding):
                        converted_lines.append(f"{keyword}\t{new_pinyin}\t{weight}")
                else:
                    converted_lines.append(line)
            else:
                converted_lines.append(line)

        blocks.append({"timestamp": timestamp, "lines": converted_lines})

    return {"header": header, "blocks": blocks}


def get_three_days_ago_timestamp():
    """获取3天前的时间戳"""
    three_days_ago = datetime.datetime.now() - relativedelta(days=3)
    return three_days_ago.strftime("%Y-%m-%d")


def generate_output(keywords, cache, existing_data, encoding=ENCODING_FLYPY):
    """生成带时间戳区块的输出内容"""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    three_days_ago = (datetime.datetime.now() - datetime.timedelta(days=3)).strftime(
        "%Y-%m-%d"
    )

    # 文件头保持不变
    header = existing_data["header"] or DYHOT_HEADER.format(today=today)

    # 收集所有已有热词（用于去重）
    existing_keywords = set()
    for block in existing_data["blocks"]:
        for line in block["lines"]:
            if "\t" in line:
                existing_keywords.add(line.split("\t")[0])

    # 过滤掉已存在的热词
    new_keywords = [kw for kw in keywords if kw not in existing_keywords]

    # 生成新内容
    new_block_lines = []
    for kw in new_keywords:
        full_pinyin = get_pinyin(kw, cache)
        if full_pinyin:
            # 转换为目标编码
            code = encode_code(full_pinyin, encoding)
            if not is_valid_code(code, encoding):
                fallback_pinyin = normalize_pinyin_text(simple_pinyin(kw))
                if fallback_pinyin:
                    cache[kw] = fallback_pinyin
                    code = encode_code(fallback_pinyin, encoding)
            if is_valid_code(code, encoding):
                new_block_lines.append(f"{kw}\t{code}\t100")

    # 保留3天内的区块
    recent_blocks = [
        block
        for block in existing_data["blocks"]
        if block["timestamp"] >= three_days_ago
    ]

    # 构建新文件内容
    output_lines = [header]

    # 添加有效区块（保留空行）
    for block in recent_blocks:
        output_lines.append(f"## {block['timestamp']} {{")
        output_lines.extend(block["lines"])
        output_lines.append(f"## {block['timestamp']} }}")
        output_lines.append("")  # 区块间空行

    # 添加新区块（如果有新词）
    if new_block_lines:
        output_lines.append(f"## {today} {{")
        output_lines.extend(new_block_lines)
        output_lines.append(f"## {today} }}")
        output_lines.append("")  # 新区块后空行

    return "\n".join(output_lines)


# ==================== 主函数 ====================


def parse_args():
    parser = argparse.ArgumentParser(description="抖音热榜词条抓取脚本")
    parser.add_argument(
        "--encoding",
        choices=ENCODINGS,
        default=ENCODING_FLYPY,
        help="词库编码：flypy=小鹤双拼（默认），quanpin=无声调全拼（供 full_pinyin 分支）",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    encoding = args.encoding
    output_file = output_file_for(encoding)

    print("=" * 50)
    print("抖音热榜词条抓取脚本")
    print(f"编码模式: {encoding}")
    print("=" * 50)

    source_used = ""
    error_msg = None

    try:
        # 1. 获取热榜关键词
        print("\n[1/5] 获取热榜关键词...")
        keywords, source_used = fetch_hot_keywords()
        print(f"   获取到 {len(keywords)} 个关键词 (来源: {source_used})")

        if not keywords:
            raise Exception("无法获取热榜数据（抖音和百度热搜均失败）")

        # 2. 加载拼音缓存
        print("\n[2/5] 加载拼音缓存...")
        cache = load_pinyin_cache()
        print(f"   缓存中有 {len(cache)} 个词的拼音")

        # 3. 清理关键词（验证是否只包含中文）
        print("\n[3/5] 清理关键词...")
        valid_keywords = [kw for kw in keywords if is_valid_keyword(kw)]
        valid_keywords = list(dict.fromkeys(valid_keywords))
        print(f"   有效关键词: {len(valid_keywords)} 个")

        # 4. 使用 DeepSeek 生成拼音（只处理合法关键词）
        print("\n[4/5] 生成拼音...")
        cache = generate_pinyin_with_deepseek(valid_keywords, cache)
        save_pinyin_cache(cache)

        # 排序
        sorted_keywords = sort_keywords(valid_keywords, cache)
        print("   按长度和拼音排序完成")

        # 5. 生成输出文件
        print("\n[5/5] 生成输出文件...")
        existing_data = read_existing_file(output_file, encoding)
        output_content = generate_output(sorted_keywords, cache, existing_data, encoding)

        # 写入文件
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(output_content)

        print(f"   文件已写入: {output_file}")

        print("\n" + "=" * 50)
        print("完成!")
        print(f"日期: {datetime.datetime.now().strftime('%Y-%m-%d')}")
        print(f"关键词数量: {len(sorted_keywords)}")
        print(f"数据来源: {source_used}")
        print(f"编码模式: {encoding}")
        print("=" * 50)

    except Exception as e:
        error_msg = str(e)
        print(f"\n❌ 错误: {error_msg}")
        raise


if __name__ == "__main__":
    main()
