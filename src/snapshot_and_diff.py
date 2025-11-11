from __future__ import annotations

import json
import os
import base64
from datetime import datetime, timezone, timedelta
from typing import Dict, Tuple

from tenacity import retry, stop_after_attempt, wait_exponential
from github import Github

from .config import CONFIG
from .classify_utils import any_chinese


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _get_repo(client: Github, full_name: str):
    return client.get_repo(full_name)


def _client() -> Github:
    if CONFIG.github_token:
        return Github(CONFIG.github_token, per_page=100)
    return Github(per_page=100)


def _snapshot_path(ts: datetime) -> str:
    ds = ts.strftime("%Y%m%dT%H%M%SZ")
    return os.path.join(CONFIG.data_dir, f"snapshot_{ds}.json")


def _load_latest_snapshot() -> Tuple[dict | None, str | None]:
    if not os.path.isdir(CONFIG.data_dir):
        os.makedirs(CONFIG.data_dir, exist_ok=True)
    files = [f for f in os.listdir(CONFIG.data_dir) if f.startswith("snapshot_") and f.endswith(".json")]
    if not files:
        return None, None
    files.sort(reverse=True)
    path = os.path.join(CONFIG.data_dir, files[0])
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f), path


def take_snapshot(candidates: Dict[str, dict], prev_snapshot: dict | None = None) -> dict:
    client = _client()
    now = datetime.now(timezone.utc)
    data = {"timestamp": now.isoformat(), "repos": {}}

    for full_name in candidates.keys():
        try:
            repo = _get_repo(client, full_name)
            # README 检测（前 3000 字符）带缓存：若上一快照存在且 pushed_at 未变，则复用
            readme_sample = ""
            has_chinese_readme = False
            reused = False
            prev_repo = None
            if prev_snapshot:
                prev_repo = prev_snapshot.get("repos", {}).get(full_name)
            if prev_repo and prev_repo.get("pushed_at") and repo.pushed_at and prev_repo.get("pushed_at") == repo.pushed_at.isoformat():
                readme_sample = prev_repo.get("readme_sample") or ""
                has_chinese_readme = bool(prev_repo.get("has_chinese_readme"))
                reused = True
            if not reused:
                try:
                    readme = repo.get_readme()
                    if readme and readme.content:
                        decoded = base64.b64decode(readme.content).decode(errors="ignore")
                        readme_sample = decoded[:3000]
                        has_chinese_readme = any_chinese(readme_sample)
                except Exception:
                    pass

            data["repos"][full_name] = {
                "stars": repo.stargazers_count,
                "forks": repo.forks_count,
                "watchers": repo.subscribers_count,
                "language": repo.language,
                "topics": repo.get_topics() or [],
                "license": (repo.license.spdx_id if getattr(repo, "license", None) else None),
                "created_at": repo.created_at.isoformat() if getattr(repo, "created_at", None) else None,
                "pushed_at": repo.pushed_at.isoformat() if getattr(repo, "pushed_at", None) else None,
                "description": repo.description,
                "owner_type": (repo.owner.type if getattr(repo, "owner", None) else None),
                "readme_sample": readme_sample,
                "has_chinese_readme": has_chinese_readme,
            }
        except Exception:
            # 忽略单仓库错误
            continue

    # 保存
    path = _snapshot_path(now)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data


def compute_diff(curr: dict, prev: dict | None) -> dict:
    if not prev:
        return {
            "timestamp": curr["timestamp"],
            "base_timestamp": None,
            "top": [],
            "stats": {},
        }

    diff_list = []
    prev_repos = prev.get("repos", {})
    new_repo_cutoff = None
    try:
        new_repo_cutoff = datetime.now(timezone.utc) - timedelta(days=CONFIG.diff.new_repo_days)
    except Exception:
        pass

    for full_name, now in curr.get("repos", {}).items():
        before = prev_repos.get(full_name)
        if not before:
            continue
        stars_now = now.get("stars", 0)
        stars_prev = before.get("stars", 0)
        delta = stars_now - stars_prev
        growth_rate = None
        if stars_prev >= CONFIG.diff.min_prev_stars_for_growth and stars_prev > 0:
            growth_rate = delta / stars_prev
        created_at_iso = now.get("created_at")
        is_new = False
        if created_at_iso and new_repo_cutoff:
            try:
                created_dt = datetime.fromisoformat(created_at_iso.replace("Z", "+00:00"))
                is_new = created_dt >= new_repo_cutoff
            except Exception:
                pass

        diff_entry = {
            "repo": full_name,
            "stars_now": stars_now,
            "stars_prev": stars_prev,
            "delta": delta,
            "growth_rate": growth_rate,
            "language": now.get("language"),
            "topics": now.get("topics", []),
            "license": now.get("license"),
            "owner_type": now.get("owner_type"),
            "description": now.get("description"),
            "readme_sample": now.get("readme_sample"),
            "has_chinese_readme": now.get("has_chinese_readme"),
            "created_at": created_at_iso,
            "is_new": is_new,
        }
        # 噪声过滤：超大仓库且 delta < min_delta_for_huge 则跳过
        if stars_prev >= CONFIG.diff.huge_repo_star_threshold and diff_entry["delta"] < CONFIG.diff.min_delta_for_huge:
            continue
        diff_list.append(diff_entry)

    # 排序
    diff_list.sort(key=lambda x: (x["delta"], x["growth_rate"] or -1), reverse=True)
    # 主榜：按 delta + growth 辅助
    top_n = diff_list[: CONFIG.diff.top_n]

    # 新项目榜：优先 growth_rate，其次 delta
    new_items = [d for d in diff_list if d.get("is_new")]
    new_items.sort(key=lambda x: ((x.get("growth_rate") or 0), x.get("delta")), reverse=True)
    top_new = new_items[: CONFIG.diff.top_n_new]

    # 增幅榜（growth_rate 排序），过滤 None，取前 top_n
    growth_candidates = [d for d in diff_list if d.get("growth_rate") is not None]
    growth_candidates.sort(key=lambda x: x.get("growth_rate"), reverse=True)
    top_growth = growth_candidates[: CONFIG.diff.growth_top_n]
    # 统计: 语言分布 + 中文/非中文分类 + 总仓库数
    from .classify_utils import is_chinese_project
    lang_counts: Dict[str, int] = {}
    chinese_count = 0
    non_chinese_count = 0
    for item in top_n:
        lang = item.get("language") or "Unknown"
        lang_counts[lang] = lang_counts.get(lang, 0) + 1
        if is_chinese_project(item):
            chinese_count += 1
        else:
            non_chinese_count += 1

    stats = {
        "languages": lang_counts,
        "categories": {
            "chinese": chinese_count,
            "non_chinese": non_chinese_count,
        },
        "total_diff_repos": len(diff_list),
        "top_n": len(top_n),
        "top_new_count": len(top_new),
        "new_repo_days": CONFIG.diff.new_repo_days,
        "growth_rank_count": len(top_growth),
    }

    return {
        "timestamp": curr["timestamp"],
        "base_timestamp": prev.get("timestamp"),
        "top": top_n,
        "stats": stats,
        "top_new": top_new,
        "top_growth": top_growth,
    }


def cleanup_old_snapshots(keep: int = 120) -> None:
    """Keep only the newest 'keep' snapshot files; delete older ones."""
    if not os.path.isdir(CONFIG.data_dir):
        return
    files = [f for f in os.listdir(CONFIG.data_dir) if f.startswith("snapshot_") and f.endswith(".json")]
    if len(files) <= keep:
        return
    files.sort(reverse=True)  # newest first
    to_delete = files[keep:]
    for fname in to_delete:
        try:
            os.remove(os.path.join(CONFIG.data_dir, fname))
        except Exception:
            pass


if __name__ == "__main__":
    # 简单连通性测试（需要先准备 candidates）
    pass
