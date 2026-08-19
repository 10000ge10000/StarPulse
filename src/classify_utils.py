from __future__ import annotations

import logging
import re
from typing import Dict, List

from .config import CONFIG

_CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")

logger = logging.getLogger(__name__)


def is_chinese_text(text: str, ratio_threshold: float | None = None) -> bool:
    """Return True if the proportion of CJK characters in text >= threshold.

    If threshold is None: use CONFIG.classify.chinese_ratio_threshold.

    Args:
        text: Input text to check.
        ratio_threshold: Ratio threshold for CJK character proportion.
            Defaults to CONFIG.classify.chinese_ratio_threshold.

    Returns:
        True if CJK character proportion >= threshold, False otherwise.

    Example:
        >>> is_chinese_text("Hello 世界", 0.1)
        True
    """
    if not text:
        logger.debug("is_chinese_text: input text is empty")
        return False
    ratio_threshold = ratio_threshold if ratio_threshold is not None else CONFIG.classify.chinese_ratio_threshold
    chars = list(text)
    if not chars:
        logger.debug("is_chinese_text: no characters after parsing")
        return False
    chinese = sum(1 for c in chars if _CHINESE_RE.match(c))
    ratio = chinese / max(1, len(chars))
    result = ratio >= ratio_threshold
    logger.debug(
        "is_chinese_text: text_len=%d, chinese_count=%d, ratio=%.4f, threshold=%.2f, result=%s",
        len(chars), chinese, ratio, ratio_threshold, result,
    )
    return result


def any_chinese(text: str) -> bool:
    """Return True if there is at least one CJK character in text.

    Args:
        text: Input text to check.

    Returns:
        True if at least one CJK character found, False otherwise.

    Example:
        >>> any_chinese("Hello world")
        False
        >>> any_chinese("Hello 世界")
        True
    """
    if not text:
        logger.debug("any_chinese: input text is empty")
        return False
    result = bool(_CHINESE_RE.search(text))
    logger.debug("any_chinese: found_cjk=%s", result)
    return result


def is_chinese_project(item: Dict) -> bool:
    """Heuristic to decide if a repo is a Chinese project.

    Rules (OR):
    1. README contains any Chinese character (has_chinese_readme flag or sample text test)
    2. description/topics/license aggregated text has Chinese ratio over threshold
    3. presence of keyword in aggregated lowercased text

    Args:
        item: Repository data dict with keys: description, topics, license,
            readme_sample, has_chinese_readme.

    Returns:
        True if the project is classified as Chinese, False otherwise.

    Example:
        >>> is_chinese_project({
        ...     "description": "一个Python库",
        ...     "topics": ["python", "library"],
        ...     "license": "MIT",
        ...     "readme_sample": "",
        ...     "has_chinese_readme": False,
        ... })
        True
    """
    desc = item.get("description") or ""
    topics_list: List[str] = item.get("topics", []) or []
    topics = " ".join(topics_list)
    license_ = item.get("license") or ""
    readme_sample = item.get("readme_sample") or ""
    has_ch_readme_flag = item.get("has_chinese_readme") is True

    # Rule 1: README contains Chinese characters
    if has_ch_readme_flag or any_chinese(readme_sample):
        logger.debug("is_chinese_project: Rule1 triggered (has_chinese_readme or readme_sample)")
        return True

    # Rule 2: aggregated text has Chinese ratio over threshold
    aggregate = f"{desc} {topics} {license_}".strip()
    if is_chinese_text(aggregate):  # Rule 2 ratio
        logger.debug("is_chinese_project: Rule2 triggered (chinese ratio threshold)")
        return True

    # Rule 3: presence of chinese keywords in aggregated text
    lower_all = aggregate.lower()
    for kw in CONFIG.classify.chinese_keywords:
        if kw.lower() in lower_all:
            logger.debug("is_chinese_project: Rule3 triggered (keyword='%s')", kw)
            return True

    logger.debug("is_chinese_project: no rules triggered")
    return False
