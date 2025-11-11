from __future__ import annotations

import re
from typing import Dict, List

from .config import CONFIG

_CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")


def is_chinese_text(text: str, ratio_threshold: float | None = None) -> bool:
    """Return True if the proportion of CJK characters in text >= threshold.
    If threshold is None: use CONFIG.classify.chinese_ratio_threshold.
    """
    if not text:
        return False
    ratio_threshold = ratio_threshold if ratio_threshold is not None else CONFIG.classify.chinese_ratio_threshold
    chars = list(text)
    if not chars:
        return False
    chinese = sum(1 for c in chars if _CHINESE_RE.match(c))
    ratio = chinese / max(1, len(chars))
    return ratio >= ratio_threshold


def any_chinese(text: str) -> bool:
    """Return True if there is at least one CJK character in text."""
    if not text:
        return False
    return bool(_CHINESE_RE.search(text))


def is_chinese_project(item: Dict) -> bool:
    """Heuristic to decide if a repo is a Chinese project.

    Rules (OR):
    1. README contains any Chinese character (has_chinese_readme flag or sample text test)
    2. description/topics/license aggregated text has Chinese ratio over threshold
    3. presence of keyword in aggregated lowercased text
    """
    desc = item.get("description") or ""
    topics_list: List[str] = item.get("topics", []) or []
    topics = " ".join(topics_list)
    license_ = item.get("license") or ""
    readme_sample = item.get("readme_sample") or ""
    has_ch_readme_flag = item.get("has_chinese_readme") is True

    # Rule 1
    if has_ch_readme_flag or any_chinese(readme_sample):
        return True

    aggregate = f"{desc} {topics} {license_}".strip()
    if is_chinese_text(aggregate):  # Rule 2 ratio
        return True

    lower_all = aggregate.lower()
    for kw in CONFIG.classify.chinese_keywords:
        if kw.lower() in lower_all:
            return True
    return False
