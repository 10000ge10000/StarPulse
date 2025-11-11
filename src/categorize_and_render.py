from __future__ import annotations

import json
import os
from typing import Dict, List, Tuple, Iterable
from tabulate import tabulate

from .config import CONFIG
from .classify_utils import is_chinese_project

README_BEGIN = "<!-- BEGIN_AUTOGEN_RESULT -->"
README_END = "<!-- END_AUTOGEN_RESULT -->"


def split_cn_noncn(diff_top: List[dict]) -> Tuple[List[dict], List[dict]]:
    cn, noncn = [], []
    for item in diff_top:
        (cn if is_chinese_project(item) else noncn).append(item)
    return cn, noncn


def _load_recent_snapshots(k: int = None) -> List[dict]:
    if k is None:
        k = CONFIG.diff.trend_history_len
    paths: List[str] = []
    try:
        files = [f for f in os.listdir(CONFIG.data_dir) if f.startswith("snapshot_") and f.endswith(".json")]
        files.sort()
        for f in files[-k:]:
            paths.append(os.path.join(CONFIG.data_dir, f))
    except Exception:
        return []
    out: List[dict] = []
    for p in paths:
        try:
            with open(p, "r", encoding="utf-8") as fh:
                out.append(json.load(fh))
        except Exception:
            pass
    return out


def _spark(values: List[int]) -> str:
    if not values:
        return ""
    blocks = "▁▂▃▄▅▆▇█"
    lo, hi = min(values), max(values)
    if hi == lo:
        return blocks[0] * len(values)
    out_chars: List[str] = []
    rng = hi - lo
    for v in values:
        idx = int((v - lo) / rng * (len(blocks) - 1)) if rng else 0
        out_chars.append(blocks[idx])
    return "".join(out_chars)


def _build_trend_map(repos: Iterable[str], history_len: int | None = None) -> Dict[str, str]:
    recent = _load_recent_snapshots(history_len)
    names = list(set(repos))
    series: Dict[str, List[int]] = {n: [] for n in names}
    for snap in recent:
        r = snap.get("repos", {})
        for n in names:
            raw = r.get(n, {}).get("stars")
            series[n].append(raw if isinstance(raw, int) else None)
    out: Dict[str, str] = {}
    for n, vals in series.items():
        cleaned = [v for v in vals if isinstance(v, int)]
        out[n] = _spark(cleaned)
    return out


def _fmt_date(ts: str | None) -> str:
    if not ts or not isinstance(ts, str):
        return ""
    # Accept ISO formats like 2025-11-11T07:56:59.473243+00:00 or ending with Z
    try:
        # Normalize Zulu
        t = ts.replace("Z", "+00:00")
        from datetime import datetime
        d = datetime.fromisoformat(t).date()
        return d.isoformat()
    except Exception:
        # Fallback to first 10 chars if ISO-like
        return ts[:10] if len(ts) >= 10 else ts


def _md_link(repo_full_name: str) -> str:
    return f"[{repo_full_name}](https://github.com/{repo_full_name})"


def _truncate(text: str | None, limit: int) -> str:
    if not text:
        return "-"
    t = text.strip().replace("\n", " ")
    return t if len(t) <= limit else (t[:limit - 1] + "…")


def render_markdown(curr: dict, diff_res: dict, save_dir: str) -> str:
    top = diff_res.get("top", [])
    cn, noncn = split_cn_noncn(top)
    top_new = diff_res.get("top_new", [])
    cn_new, noncn_new = split_cn_noncn(top_new)
    top_growth = diff_res.get("top_growth", [])
    cn_growth, noncn_growth = split_cn_noncn(top_growth)

    trend_targets: List[str] = [x["repo"] for x in (cn + noncn + cn_growth + noncn_growth + cn_new + noncn_new)]
    trend_map = _build_trend_map(trend_targets, CONFIG.diff.trend_history_len)

    def _project_cell(x: dict) -> str:
        link = _md_link(x["repo"])
        desc = _truncate(x.get("description"), CONFIG.diff.description_max_len)
        if desc and desc != "-":
            # 在链接下方放简介，小字号，避免拉宽表格
            return f"{link}<br/><sub>{desc}</sub>"
        return link

    def rows(items: List[dict]) -> List[List[str | int]]:
        table: List[List[str | int]] = []
        for x in items:
            table.append([
                _project_cell(x),
                x.get("language") or "-",
                x.get("stars_prev", 0),
                x.get("stars_now", 0),
                x.get("delta", 0),
                f"{(x.get('growth_rate') or 0)*100:.2f}%",
                trend_map.get(x["repo"], ""),
            ])
        return table

    md: List[str] = []
    curr_date = _fmt_date(curr.get('timestamp'))
    base_date = _fmt_date(diff_res.get('base_timestamp'))
    md.append(f"## Star 增长榜（{curr_date}）")
    md.append("")
    # Beauty touch with calendar emoji
    md.append(f"🗓️ 基线快照：{base_date}")
    md.append("")
    stats = diff_res.get("stats", {})
    if stats:
        md.append("### 统计摘要")
        md.append("")
        md.append(f"- 参与 diff 仓库数：{stats.get('total_diff_repos')} | 展示 Top: {stats.get('top_n')} | 新项目窗口：{stats.get('new_repo_days')} 天")
        cats = stats.get('categories', {})
        md.append(f"- 中文: {cats.get('chinese', 0)} | 非中文: {cats.get('non_chinese', 0)} | 新项目数: {stats.get('top_new_count')}")
        langs = stats.get('languages', {})
        if langs:
            lang_line = ", ".join(f"{k}:{v}" for k, v in sorted(langs.items(), key=lambda x: -x[1]))
            md.append(f"- 语言分布: {lang_line}")
        md.append("")

    table_headers = ["项目", "语言", "Prev", "Now", "+", "%", "趋势"]

    md.append("## 中文项目（现有 Top）")
    md.append("")
    if cn:
        md.append(tabulate(rows(cn), headers=table_headers, tablefmt="github"))
    else:
        md.append("暂无上榜项目")
    md.append("")

    md.append("## 非中文项目（现有 Top）")
    md.append("")
    if noncn:
        md.append(tabulate(rows(noncn), headers=table_headers, tablefmt="github"))
    else:
        md.append("暂无上榜项目")
    md.append("")

    md.append("## 中文项目（增幅 Top）")
    md.append("")
    if cn_growth:
        md.append(tabulate(rows(cn_growth), headers=table_headers, tablefmt="github"))
    else:
        md.append("暂无上榜项目")
    md.append("")

    md.append("## 非中文项目（增幅 Top）")
    md.append("")
    if noncn_growth:
        md.append(tabulate(rows(noncn_growth), headers=table_headers, tablefmt="github"))
    else:
        md.append("暂无上榜项目")
    md.append("")

    md.append("## 新项目 - 中文")
    md.append("")
    if cn_new:
        md.append(tabulate(rows(cn_new), headers=table_headers, tablefmt="github"))
    else:
        md.append("暂无上榜新项目")
    md.append("")

    md.append("## 新项目 - 非中文")
    md.append("")
    if noncn_new:
        md.append(tabulate(rows(noncn_new), headers=table_headers, tablefmt="github"))
    else:
        md.append("暂无上榜新项目")
    md.append("")

    content = "\n".join(md)
    path = os.path.join(save_dir, "LATEST.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    readme_path = os.path.join(project_root, "README.md")
    try:
        existing = ""
        if os.path.exists(readme_path):
            with open(readme_path, "r", encoding="utf-8") as rf:
                existing = rf.read()
        if README_BEGIN in existing and README_END in existing:
            before = existing.split(README_BEGIN)[0]
            after = existing.split(README_END)[-1]
            new_readme = before + README_BEGIN + "\n\n" + content + "\n\n" + README_END + after
        else:
            new_readme = existing.rstrip() + "\n\n## 每日榜单\n\n" + README_BEGIN + "\n\n" + content + "\n\n" + README_END + "\n"
        with open(readme_path, "w", encoding="utf-8") as wf:
            wf.write(new_readme)
    except Exception:
        pass
    return content


def render_json(curr: dict, diff_res: dict, save_dir: str) -> dict:
    # 按中/非中拆分
    top = diff_res.get("top", [])
    cn, noncn = split_cn_noncn(top)

    out = {
        "timestamp": curr.get("timestamp"),
        "base_timestamp": diff_res.get("base_timestamp"),
        "stats": diff_res.get("stats"),
        "top_cn": cn,
        "top_noncn": noncn,
        "top_new": diff_res.get("top_new", []),
    }
    path = os.path.join(save_dir, "latest.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return out
