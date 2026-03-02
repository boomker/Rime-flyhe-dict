#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抖音热榜词条抓取脚本
自动生成 Rime 输入法字典文件
使用 DeepSeek deepseek-chat 模型生成拼音
支持备用数据源
"""

import requests
import re
import os
import json
import datetime
from dateutil.relativedelta import relativedelta
from openai import OpenAI

# ==================== 配置 ====================
# 主数据源和备用数据源
PRIMARY_API_URL = "https://v2.xxapi.cn/api/douyinhot"
FALLBACK_API_URL = "https://v2.xxapi.cn/api/baiduhot"

OUTPUT_FILE = "./flypy_dyhot.dict.yaml"
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

# DeepSeek API 基础URL
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# 拼音缓存文件
CACHE_FILE = "./pinyin_cache.json"

# ==================== 辅助函数 ====================

def load_pinyin_cache():
    """加载拼音缓存"""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_pinyin_cache(cache):
    """保存拼音缓存"""
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
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
        
        # 分批处理（每次最多20个）
        batch_size = 20
        for i in range(0, len(uncached_keywords), batch_size):
            batch = uncached_keywords[i:i+batch_size]
            keywords_str = "\n".join([f"{i+1}. {kw}" for i, kw in enumerate(batch)])
            
            prompt = f"""请为以下中文热词标注汉语拼音。
要求：
1. 考虑句中多音字的正确读音（如"行长"应读"háng zhǎng"不是"xíng zhǎng"，"首都"应读"shǒu dū"不是"shū dū"）
2. 每个词一行，格式：汉字 拼音
3. 拼音之间用空格分隔
4. 只返回结果，不要其他说明

热词列表：
{keywords_str}

请开始："""

            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是一个专业的汉语拼音标注助手，擅长处理多音字和词组连读。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )
            
            result_text = response.choices[0].message.content
            
            # 解析结果
            for line in result_text.strip().split('\n'):
                line = line.strip()
                # 匹配 "汉字 拼音" 格式
                match = re.match(r'^\d+\.\s*(\S+)\s+(.+)$', line)
                if match:
                    kw = match.group(1)
                    pinyin = match.group(2).strip()
                    if kw in uncached_keywords:
                        cache[kw] = pinyin
            
            print(f"  已处理 {min(i+batch_size, len(uncached_keywords))}/{len(uncached_keywords)}")
            
    except Exception as e:
        print(f"DeepSeek API 调用失败: {e}")
        print("将使用 pypinyin 作为备用方案...")
        raise Exception(f"DeepSeek API 异常: {e}")
    
    return cache

def simple_pinyin(keyword):
    """简单的拼音转换（备用方案）"""
    try:
        from pypinyin import lazy_pinyin
        return ' '.join(lazy_pinyin(keyword))
    except ImportError:
        return ""

def simple_pinyin_batch(keywords, cache):
    """批量使用 pypinyin 转换"""
    print("使用 pypinyin 库生成拼音...")
    try:
        from pypinyin import lazy_pinyin
        for kw in keywords:
            if kw not in cache:
                cache[kw] = ' '.join(lazy_pinyin(kw))
        print(f"  pypinyin 处理完成 {len(keywords)} 个关键词")
    except ImportError:
        print("错误: pypinyin 库未安装")
        raise Exception("pypinyin 库未安装")
    
    return cache

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
        "ou": "z", "iao": "n", "uang": "l", "iang": "l",
        "en": "f", "eng": "g", "ng": "g", "ang": "h",
        "an": "j", "ao": "c", "ai": "d", "ian": "m",
        "in": "b", "uo": "o", "un": "y", "iu": "q",
        "uan": "r", "iong": "s", "ong": "s", "ue": "t",
        "ve": "t", "ui": "v", "ua": "x", "ia": "x",
        "ie": "p", "uai": "k", "ing": "k", "ei": "w",
    }
    zero = {
        "a": "aa", "an": "an", "ai": "ai", "ang": "ah",
        "o": "oo", "ou": "ou", "e": "ee", "n": "en",
        "en": "en", "eng": "eg", "ei": "ei", "er": "er",
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
    return ' '.join(flypy_list)

def get_pinyin(keyword, cache):
    """获取拼音"""
    if keyword in cache:
        return cache[keyword]
    
    # 使用简单方案作为后备
    pinyin = simple_pinyin(keyword)
    cache[keyword] = pinyin
    return pinyin

def fetch_hot_keywords_from_url(api_url, source_name):
    """从指定URL获取热榜关键词"""
    try:
        response = requests.get(api_url, timeout=15)
        data = response.json()
        
        if data.get('code') != 200:
            print(f"{source_name} API返回错误: {data.get('msg')}")
            return None, f"API错误: {data.get('msg')}"
        
        keywords = []
        for item in data.get('data', []):
            word = item.get('word', '')
            if word:
                # 清理关键词 - 去除特殊字符，只保留中文
                cleaned = re.sub(r'[^\u4e00-\u9fa5]', '', word)
                if cleaned and len(cleaned) >= 2:
                    keywords.append(cleaned)
        
        # 去重
        keywords = list(dict.fromkeys(keywords))
        return keywords, None
        
    except requests.Timeout:
        return None, "请求超时"
    except requests.RequestException as e:
        return None, f"网络异常: {str(e)}"
    except Exception as e:
        return None, f"未知错误: {str(e)}"

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
    return bool(re.match(r'^[\u4e00-\u9fa5]+$', keyword)) and len(keyword) >= 2

def sort_keywords(keywords, cache):
    """按照字符长度排序，长度相同则按拼音字母排序"""
    def sort_key(kw):
        pinyin = get_pinyin(kw, cache).replace(' ', '')
        return (len(kw), pinyin)
    
    return sorted(keywords, key=sort_key)

def read_existing_file(filepath):
    """读取现有文件内容，解析时间戳区块"""
    if not os.path.exists(filepath):
        return {"header": "", "blocks": []}
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 分离header和区块内容
    header_end = re.search(r'## \d{4}-\d{2}-\d{2} \{', content)
    if header_end:
        header = content[:header_end.start()].strip()
        block_content = content[header_end.start():]
    else:
        header = content.strip()
        block_content = ""
    
    # 提取所有时间戳区块
    blocks = []
    block_pattern = r'## (\d{4}-\d{2}-\d{2}) \{\n([\s\S]*?)\n## \1 \}'
    matches = re.findall(block_pattern, block_content)
    for timestamp, block_text in matches:
        lines = [line.strip() for line in block_text.split('\n') if line.strip()]
        # 转换旧的全拼行为双拼
        converted_lines = []
        for line in lines:
            if '\t' in line:
                parts = line.split('\t')
                if len(parts) >= 2:
                    keyword = parts[0]
                    old_pinyin = parts[1]
                    weight = parts[2] if len(parts) > 2 else "100"
                    # 转换为双拼
                    new_pinyin = convert_to_flypy(old_pinyin)
                    converted_lines.append(f"{keyword}\t{new_pinyin}\t{weight}")
                else:
                    converted_lines.append(line)
            else:
                converted_lines.append(line)
        
        blocks.append({
            'timestamp': timestamp,
            'lines': converted_lines
        })
    
    return {
        "header": header,
        "blocks": blocks
    }

def get_three_days_ago_timestamp():
    """获取3天前的时间戳"""
    three_days_ago = datetime.datetime.now() - relativedelta(days=3)
    return three_days_ago.strftime('%Y-%m-%d')

def generate_output(keywords, cache, existing_data):
    """生成带时间戳区块的输出内容"""
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    three_days_ago = (datetime.datetime.now() - datetime.timedelta(days=3)).strftime('%Y-%m-%d')
    
    # 文件头保持不变
    header = existing_data['header'] or f"""# Rime dictionary
# encoding: utf-8

---
name: flyhe_dyhot
version: {today}
sort: by_weight
...

"""
    
    # 收集所有已有热词（用于去重）
    existing_keywords = set()
    for block in existing_data['blocks']:
        for line in block['lines']:
            if '\t' in line:
                existing_keywords.add(line.split('\t')[0])
    
    # 过滤掉已存在的热词
    new_keywords = [kw for kw in keywords if kw not in existing_keywords]
    
    # 生成新内容
    new_block_lines = []
    for kw in new_keywords:
        full_pinyin = get_pinyin(kw, cache)
        if full_pinyin:
            # 转换为小鹤双拼
            flypy_pinyin = convert_to_flypy(full_pinyin)
            new_block_lines.append(f"{kw}\t{flypy_pinyin}\t100")
    
    # 保留3天内的区块
    recent_blocks = [
        block for block in existing_data['blocks']
        if block['timestamp'] >= three_days_ago
    ]
    
    # 构建新文件内容
    output_lines = [header]
    
    # 添加有效区块（保留空行）
    for block in recent_blocks:
        output_lines.append(f"## {block['timestamp']} {{")
        output_lines.extend(block['lines'])
        output_lines.append(f"## {block['timestamp']} }}")
        output_lines.append("")  # 区块间空行
    
    # 添加新区块（如果有新词）
    if new_block_lines:
        output_lines.append(f"## {today} {{")
        output_lines.extend(new_block_lines)
        output_lines.append(f"## {today} }}")
        output_lines.append("")  # 新区块后空行
    
    return '\n'.join(output_lines)

# ==================== 主函数 ====================

def main():
    print("=" * 50)
    print("抖音热榜词条抓取脚本")
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
        
        # 3. 使用 DeepSeek 生成拼音
        print("\n[3/5] 生成拼音...")
        cache = generate_pinyin_with_deepseek(keywords, cache)
        save_pinyin_cache(cache)
        
        # 4. 清理关键词
        print("\n[4/5] 清理关键词...")
        valid_keywords = [kw for kw in keywords if is_valid_keyword(kw)]
        valid_keywords = list(dict.fromkeys(valid_keywords))
        print(f"   有效关键词: {len(valid_keywords)} 个")
        
        # 排序
        sorted_keywords = sort_keywords(valid_keywords, cache)
        print("   按长度和拼音排序完成")
        
        # 5. 生成输出文件
        print("\n[5/5] 生成输出文件...")
        existing_data = read_existing_file(OUTPUT_FILE)
        output_content = generate_output(sorted_keywords, cache, existing_data)
        
        # 写入文件
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write(output_content)
        
        print(f"   文件已写入: {OUTPUT_FILE}")
        
        print("\n" + "=" * 50)
        print("完成!")
        print(f"日期: {datetime.datetime.now().strftime('%Y-%m-%d')}")
        print(f"关键词数量: {len(sorted_keywords)}")
        print(f"数据来源: {source_used}")
        print("=" * 50)
        
    except Exception as e:
        error_msg = str(e)
        print(f"\n❌ 错误: {error_msg}")
        raise

if __name__ == "__main__":
    main()
