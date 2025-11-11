from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Dict


def env(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name)
    return v if v not in (None, "") else default


@dataclass
class SearchConfig:
    languages: List[str] = field(default_factory=lambda: [
        "Python", "JavaScript", "TypeScript", "Go", "Rust", "Java", "C#", "C++", "C",
    ])
    min_stars: int = 200
    max_candidates: int = 80
    topics: List[str] = field(default_factory=lambda: [
        "ai", "ml", "llm", "web", "devops", "docker", "kubernetes", "data", "security", "mobile"
    ])
    recent_days: int = 365  # 最近一年内有活动


@dataclass
class DiffConfig:
    min_prev_stars_for_growth: int = 50  # 上一快照星数低于该值时不计算增长率
    top_n: int = 30
    top_n_new: int = 20
    new_repo_days: int = 30  # 创建时间在该天数内视为“新项目”
    huge_repo_star_threshold: int = 100000  # 超大仓库星级阈值
    min_delta_for_huge: int = 2             # 超大仓库至少需要该增量才计入榜单
    growth_top_n: int = 30                  # 增幅榜单独 Top N
    trend_history_len: int = 30             # 趋势图使用的历史快照窗口长度
    description_max_len: int = 80           # 描述在表格中截断的最大字符数


@dataclass
class ClassifyConfig:
    chinese_keywords: List[str] = field(default_factory=lambda: [
        "中文", "中国", "汉化", "简体", "繁体", "国人", "zh-cn", "zh_cn", "zh-cn", "中文文档", "中文版"
    ])
    chinese_ratio_threshold: float = 0.1  # 文本中中文字符比例超过该阈值视为中文项目


@dataclass
class AppConfig:
    github_token: str | None = env("GH_TOKEN")
    search: SearchConfig = field(default_factory=SearchConfig)
    diff: DiffConfig = field(default_factory=DiffConfig)
    classify: ClassifyConfig = field(default_factory=ClassifyConfig)
    data_dir: str = os.path.join("data", "snapshots")
    output_dir: str = "output"
    locale: str = os.getenv("STARWORK_LOCALE", "zh")  # zh | en | both


CONFIG = AppConfig()
