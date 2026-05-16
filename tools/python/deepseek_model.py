#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DeepSeek 模型发现与选择工具。
"""

from __future__ import annotations

import os
import re
from typing import Iterable

import requests

DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEFAULT_TIMEOUT = 30
PRO_MODEL_SUFFIX = "-pro"
VERSIONED_PRO_PATTERN = re.compile(r"^deepseek-v(?P<major>\d+)(?:[.-](?P<extra>.*))?-pro$")


def rank_deepseek_pro_model(model_id: str) -> tuple[int, int, int, str]:
    """为 pro 模型生成排序键，优先版本号更高的正式版本。"""
    match = VERSIONED_PRO_PATTERN.match(model_id)
    if match:
        extra = match.group("extra") or ""
        # extra 为空表示更标准的 `deepseek-vN-pro`
        return (2, int(match.group("major")), 1 if not extra else 0, extra)

    if model_id.startswith("deepseek-") and model_id.endswith(PRO_MODEL_SUFFIX):
        return (1, 0, 0, model_id)

    return (0, 0, 0, model_id)


def select_best_pro_model(model_ids: Iterable[str]) -> str:
    """从模型列表中选择最合适的 pro 模型。"""
    candidates = sorted(
        {model_id for model_id in model_ids if rank_deepseek_pro_model(model_id)[0] > 0},
        key=rank_deepseek_pro_model,
        reverse=True,
    )
    if not candidates:
        raise ValueError("DeepSeek /models 返回中未找到可用的 pro 模型")
    return candidates[0]


def fetch_deepseek_models(
    api_key: str, base_url: str = DEEPSEEK_BASE_URL, timeout: int = DEFAULT_TIMEOUT
) -> list[str]:
    """调用 DeepSeek 官方 /models 接口获取模型列表。"""
    response = requests.get(
        f"{base_url.rstrip('/')}/models",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    return [item["id"] for item in payload.get("data", []) if item.get("id")]


def resolve_deepseek_pro_model(
    api_key: str, base_url: str = DEEPSEEK_BASE_URL, timeout: int = DEFAULT_TIMEOUT
) -> str:
    """自动解析当前可用的 DeepSeek pro 模型。"""
    model_ids = fetch_deepseek_models(api_key=api_key, base_url=base_url, timeout=timeout)
    return select_best_pro_model(model_ids)
