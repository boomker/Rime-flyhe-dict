#!/usr/bin/env python3
"""
采集沪深北 A 股股票名称，生成 Rime 小鹤双拼词库。

输出文件：项目根目录下的 flypy_stock.dict.yaml

数据来源：
  - 沪深北 A 股：akshare stock_info_a_code_name（沪深京三所代码/简称）
  - 完整简称补全：akshare stock_info_sh_name_code / stock_info_sz_name_code /
                  stock_info_bj_name_code（交易所股票列表）
  - 备用：stock_zh_a_spot（新浪实时行情）
"""

from __future__ import annotations

import datetime
import re
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import pypinyin
from pypinyin import Style, lazy_pinyin

from flypy_codec import convert_to_flypy

# 手动补充股票名称中常见多音字的正确读音，pypinyin 会优先使用。
CUSTOM_PHRASES = {
    "长和": "chang he",
    "长实": "chang shi",
    "长江": "chang jiang",
    "长城": "chang cheng",
    "长安": "chang an",
    "长电": "chang dian",
    "长虹": "chang hong",
    "长航": "chang hang",
    "长春": "chang chun",
    "长沙": "chang sha",
    "银行": "yin hang",
    "中行": "zhong hang",
    "农行": "nong hang",
    "工行": "gong hang",
    "招行": "zhao hang",
    "重庆": "chong qing",
    "重工": "zhong gong",
}

for phrase, pinyin_str in CUSTOM_PHRASES.items():
    pypinyin.load_phrases_dict({phrase: [[p] for p in pinyin_str.split()]})

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = PROJECT_ROOT / "flypy_stock.dict.yaml"
DICT_WEIGHT = 100

# 交易状态/除权除息类前缀。ST/*ST 按需求保留为注释行，不在这里清理。
TRADE_MARKER_PREFIXES = ("XD", "XR", "DR")
UPPERCASE_RE = re.compile(r"[A-Z]")
LEADING_UPPERCASE_RE = re.compile(r"^([A-Z]+)(?=[\u3400-\u9fff])")
CJK_RE = re.compile(r"[\u3400-\u9fff]")

HEADER_TEMPLATE = """\
# Rime dictionary
# encoding: utf-8
#
# 股票名称词库（沪深北A股）
# 数据来源：AKShare / 交易所股票列表
# 更新时间：{date}
# 股票数量：{active_count}
# ST/*ST 注释数量：{commented_count}
#
# 使用方法：在 cn_dicts/ext/ 目录下放置此文件
# 并在 import_tables 中添加：
#   - cn_dicts/ext/flypy_stock
#
---
name: flypy_stock
version: "{date}"
sort: by_weight
...

"""


@dataclass(frozen=True)
class StockName:
    code: str
    name: str


@dataclass(frozen=True)
class DictRecord:
    name: str
    code: str
    flypy: str
    commented: bool = False


def import_akshare():
    """延迟导入 akshare，避免单元测试必须安装该网络依赖。"""
    import akshare as ak  # type: ignore[import-not-found]

    return ak


def normalize_code(code: Any) -> str:
    """把各种表格中的股票代码归一为 6 位数字字符串。"""
    raw = str(code).strip()
    if raw.endswith(".0"):
        raw = raw[:-2]
    digits = re.sub(r"\D", "", raw)
    return digits.zfill(6) if digits else ""


def normalize_stock_name(name: Any) -> str:
    """清理交易所简称中的全角字符和空白，如“万  科Ａ”->“万科A”。"""
    normalized = unicodedata.normalize("NFKC", str(name).strip())
    return re.sub(r"\s+", "", normalized)


def contains_uppercase_marker(name: str) -> bool:
    return bool(UPPERCASE_RE.search(normalize_stock_name(name)))


def is_st_stock_name(name: str) -> bool:
    normalized = normalize_stock_name(name)
    return normalized.startswith("*ST") or normalized.startswith("ST")


def is_a_suffix_stock_name(name: str) -> bool:
    """A 股简称尾字为 A 的条目需要单独聚拢。"""
    normalized = normalize_stock_name(name)
    return normalized.endswith("A") and not is_st_stock_name(normalized)


def extract_leading_uppercase_prefix(name: str) -> tuple[str, str]:
    """拆出中文名前的英文缩写，如 TCL中环 -> (TCL, 中环)。"""
    normalized = normalize_stock_name(name)
    match = LEADING_UPPERCASE_RE.match(normalized)
    if not match:
        return "", normalized
    prefix = match.group(1)
    return prefix, normalized[len(prefix) :]


def strip_trade_markers(name: str) -> str:
    """去掉非 ST 的交易提示前后缀，如 XD/XR/DR/C/N/S 前缀和 -UW 后缀。"""
    cleaned = normalize_stock_name(name)

    changed = True
    while changed:
        changed = False
        for marker in TRADE_MARKER_PREFIXES:
            if cleaned.startswith(marker) and CJK_RE.match(cleaned[len(marker) : len(marker) + 1]):
                cleaned = cleaned[len(marker) :]
                changed = True
                break

    cleaned = re.sub(r"-[A-Z]+$", "", cleaned)
    return cleaned


def get_pinyin(name: str) -> str:
    """将名称转换为小鹤双拼，以空格分隔；保留开头英文缩写编码。"""
    uppercase_prefix, chinese_name = extract_leading_uppercase_prefix(name)
    full_pinyin = " ".join(lazy_pinyin(chinese_name, style=Style.NORMAL, errors="ignore"))
    flypy = convert_to_flypy(full_pinyin)
    if uppercase_prefix and flypy:
        return f"{uppercase_prefix} {flypy}"
    return flypy


def is_valid_stock_code(code: str) -> bool:
    """检查股票词典编码，允许开头英文缩写 + 小鹤双拼。"""
    tokens = [token for token in code.split() if token]
    if not tokens:
        return False
    if re.fullmatch(r"[A-Z]+", tokens[0]):
        tokens = tokens[1:]
    return bool(tokens) and all(re.fullmatch(r"[a-z]{2}", token) for token in tokens)


def pick_column(columns: Iterable[Any], candidates: Iterable[str], fallback_index: int = 0) -> Any:
    columns = list(columns)
    for candidate in candidates:
        if candidate in columns:
            return candidate
    if not columns:
        raise ValueError("empty dataframe columns")
    return columns[min(fallback_index, len(columns) - 1)]


def dataframe_to_stock_names(
    df: Any,
    *,
    code_candidates: tuple[str, ...],
    name_candidates: tuple[str, ...],
) -> list[StockName]:
    code_col = pick_column(df.columns, code_candidates, 0)
    name_col = pick_column(df.columns, name_candidates, 1)

    rows: list[StockName] = []
    for _, row in df.iterrows():
        code = normalize_code(row.get(code_col, ""))
        name = normalize_stock_name(row.get(name_col, ""))
        if code and name:
            rows.append(StockName(code=code, name=name))
    return rows


def fetch_exchange_name_map(ak: Any | None = None) -> dict[str, str]:
    """从交易所股票列表获取代码 -> 官方股票简称，用于补全 XD/XR/DR 等临时简称。"""
    ak = ak or import_akshare()
    result: dict[str, str] = {}

    def add_rows(df: Any, code_candidates: tuple[str, ...], name_candidates: tuple[str, ...]) -> None:
        for stock in dataframe_to_stock_names(
            df,
            code_candidates=code_candidates,
            name_candidates=name_candidates,
        ):
            result[stock.code] = stock.name

    for symbol in ("主板A股", "科创板"):
        try:
            add_rows(
                ak.stock_info_sh_name_code(symbol=symbol),
                code_candidates=("证券代码", "code", "代码"),
                name_candidates=("公司简称", "证券全称", "证券简称", "name", "名称"),
            )
            print(f"  [补全] 上证 {symbol} 名称表已加载")
        except Exception as e:
            print(f"  [补全] 上证 {symbol} 名称表失败：{e}")

    try:
        add_rows(
            ak.stock_info_sz_name_code(symbol="A股列表"),
            code_candidates=("A股代码", "证券代码", "code", "代码"),
            name_candidates=("A股简称", "证券简称", "name", "名称"),
        )
        print("  [补全] 深证 A 股名称表已加载")
    except Exception as e:
        print(f"  [补全] 深证 A 股名称表失败：{e}")

    try:
        add_rows(
            ak.stock_info_bj_name_code(),
            code_candidates=("证券代码", "code", "代码"),
            name_candidates=("公司简称", "证券全称", "证券简称", "name", "名称"),
        )
        print("  [补全] 北证名称表已加载")
    except Exception as e:
        print(f"  [补全] 北证名称表失败：{e}")

    print(f"  [补全] 共加载 {len(result)} 个官方简称")
    return result


def fetch_cn_stocks() -> list[StockName]:
    """沪深北 A 股：优先代码简称表，备用新浪实时行情。"""
    ak = import_akshare()
    print("正在获取沪深北 A 股...")

    try:
        df = ak.stock_info_a_code_name()
        rows = dataframe_to_stock_names(
            df,
            code_candidates=("code", "代码", "证券代码", "A股代码"),
            name_candidates=("name", "名称", "证券简称", "A股简称"),
        )
        if len(rows) > 100:
            print(f"  [主接口] 沪深北 A 股：{len(rows)} 条")
            return rows
        print(f"  [主接口] 数据过少（{len(rows)}条），尝试备用...")
    except Exception as e:
        print(f"  [主接口] 失败：{e}，尝试备用...")

    time.sleep(2)

    try:
        df = ak.stock_zh_a_spot()
        rows = dataframe_to_stock_names(
            df,
            code_candidates=("代码", "code", "symbol"),
            name_candidates=("名称", "name"),
        )
        print(f"  [备用接口] 沪深北 A 股：{len(rows)} 条")
        return rows
    except Exception as e:
        print(f"  [备用接口] 失败：{e}")
        return []


def get_existing_count() -> int:
    """读取现有词库的条目数，用于防回退保护。"""
    if not OUTPUT_PATH.exists():
        return 0

    try:
        for line in OUTPUT_PATH.read_text(encoding="utf-8").splitlines():
            if line.startswith("# 股票数量："):
                return int(line.strip().split("：", 1)[1])
    except Exception:
        pass

    count = 0
    in_body = False
    for line in OUTPUT_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip() == "...":
            in_body = True
            continue
        if in_body and line.strip() and not line.startswith("#"):
            count += 1
    return count


def resolve_output_name(stock: StockName, exchange_name_map: dict[str, str]) -> str:
    """补全/清理股票简称；ST 名称保持原样用于注释。"""
    original = normalize_stock_name(stock.name)
    if is_st_stock_name(original):
        return original

    name = original
    if contains_uppercase_marker(original):
        name = normalize_stock_name(exchange_name_map.get(stock.code, original))

    return strip_trade_markers(name)


def build_dict_records(stocks: list[StockName], exchange_name_map: dict[str, str]) -> list[DictRecord]:
    """生成去重后的 Rime 词条记录。"""
    records_by_name: dict[str, DictRecord] = {}

    for stock in stocks:
        output_name = resolve_output_name(stock, exchange_name_map)
        if len(output_name) < 2 or output_name.isdigit():
            continue

        commented = is_st_stock_name(output_name)
        flypy = get_pinyin(output_name)
        if not is_valid_stock_code(flypy):
            print(f"  [跳过] 无法生成合法股票编码：{output_name!r} -> {flypy!r}")
            continue

        record = DictRecord(
            name=output_name,
            code=stock.code,
            flypy=flypy,
            commented=commented,
        )
        old = records_by_name.get(output_name)
        # 同名冲突时优先保留未注释记录。
        if old is None or (old.commented and not record.commented):
            records_by_name[output_name] = record

    return sorted(records_by_name.values(), key=record_sort_key)


def record_sort_key(record: DictRecord) -> tuple[int, str]:
    """ST 注释股在前；尾字 A 股聚拢后紧随；其余按名称排序。"""
    if record.commented:
        group = 0
    elif is_a_suffix_stock_name(record.name):
        group = 1
    else:
        group = 2
    return group, record.name


def render_record(record: DictRecord) -> str:
    line = f"{record.name}\t{record.flypy}\t{DICT_WEIGHT}"
    return f"# {line}" if record.commented else line


def generate_dict(stocks: list[StockName], exchange_name_map: dict[str, str] | None = None) -> None:
    exchange_name_map = exchange_name_map or {}
    records = build_dict_records(stocks, exchange_name_map)

    active_count = sum(not record.commented for record in records)
    commented_count = len(records) - active_count

    # 防回退保护：新数据比现有少时拒绝写入。
    existing = get_existing_count()
    if existing and active_count < existing * 0.9:
        print(f"[保护] 新数据（{active_count}条）少于现有数据（{existing}条）的 90%，放弃写入")
        raise SystemExit(0)

    today = datetime.date.today().isoformat()
    content = HEADER_TEMPLATE.format(
        date=today,
        active_count=active_count,
        commented_count=commented_count,
    )
    content += "\n".join(render_record(record) for record in records) + "\n"

    OUTPUT_PATH.write_text(content, encoding="utf-8")
    print(f"\n词库已写入：{OUTPUT_PATH}（启用 {active_count} 条，注释 {commented_count} 条）")


if __name__ == "__main__":
    stock_rows = fetch_cn_stocks()
    print(f"\n全部获取后共 {len(stock_rows)} 条")

    if not stock_rows:
        print("错误：所有接口均未返回数据，请检查网络或接口状态")
        raise SystemExit(1)

    full_name_map = fetch_exchange_name_map()
    generate_dict(stock_rows, full_name_map)
