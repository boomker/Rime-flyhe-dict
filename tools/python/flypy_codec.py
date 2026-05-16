#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
拼音归一化与小鹤双拼转换工具。
"""

from __future__ import annotations

import re
from functools import lru_cache

SHENGMU_DICT = {"zh": "v", "ch": "i", "sh": "u"}
YUNMU_DICT = {
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
ZERO_SHENGMU_DICT = {
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
TONE_TRANSLATION = str.maketrans(
    {
        "ā": "a",
        "á": "a",
        "ǎ": "a",
        "à": "a",
        "ē": "e",
        "é": "e",
        "ě": "e",
        "è": "e",
        "ī": "i",
        "í": "i",
        "ǐ": "i",
        "ì": "i",
        "ō": "o",
        "ó": "o",
        "ǒ": "o",
        "ò": "o",
        "ū": "u",
        "ú": "u",
        "ǔ": "u",
        "ù": "u",
        "ǖ": "v",
        "ǘ": "v",
        "ǚ": "v",
        "ǜ": "v",
        "ü": "v",
        "ń": "n",
        "ň": "n",
        "ǹ": "n",
        "ḿ": "m",
    }
)


def normalize_pinyin_syllable(syllable: str) -> str:
    """把带声调/数字/标点的拼音音节清洗为无声调小写形式。"""
    normalized = syllable.strip().lower().replace("u:", "v").translate(TONE_TRANSLATION)
    normalized = re.sub(r"[^a-zv]", "", normalized)
    return normalized


def normalize_pinyin_text(full_pinyin: str) -> str:
    """归一化空格分隔拼音串。"""
    normalized_tokens = [
        normalize_pinyin_syllable(token) for token in full_pinyin.split() if token.strip()
    ]
    return " ".join(token for token in normalized_tokens if token)


@lru_cache(maxsize=None, typed=True)
def to_flypy(pinyin_str: str) -> str:
    """单个无声调拼音音节转小鹤双拼。"""
    if len(pinyin_str) == 1 and pinyin_str not in ZERO_SHENGMU_DICT:
        return ""
    if pinyin_str in ZERO_SHENGMU_DICT:
        return ZERO_SHENGMU_DICT[pinyin_str]
    if len(pinyin_str) > 1 and pinyin_str[1] == "h":
        shengmu = SHENGMU_DICT.get(pinyin_str[:2], pinyin_str[:2])
        yunmu = YUNMU_DICT.get(pinyin_str[2:], pinyin_str[2:])
        return shengmu + yunmu

    shengmu = pinyin_str[:1]
    yunmu = YUNMU_DICT.get(pinyin_str[1:], pinyin_str[1:])
    return f"{shengmu}{yunmu}"


def pinyin_to_flypy(quanpin_list: list[str]) -> list[str]:
    """全拼列表转小鹤双拼列表。"""
    normalized_tokens = [normalize_pinyin_syllable(token) for token in quanpin_list]
    return [to_flypy(token) if token else "" for token in normalized_tokens]


def convert_to_flypy(full_pinyin: str) -> str:
    """把空格分隔的全拼/带声调拼音转为小鹤双拼。"""
    normalized_pinyin = normalize_pinyin_text(full_pinyin)
    if not normalized_pinyin:
        return ""

    flypy_tokens = pinyin_to_flypy(normalized_pinyin.split())
    if not all(flypy_tokens):
        return ""
    return " ".join(flypy_tokens)


def is_valid_flypy_code(code: str) -> bool:
    """检查词库编码是否为合法的小鹤双拼格式。"""
    tokens = [token for token in code.split() if token]
    return bool(tokens) and all(re.fullmatch(r"[a-z]{2}", token) for token in tokens)
