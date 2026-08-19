from __future__ import annotations

import json
import logging
import os
import base64
from datetime import datetime, timezone, timedelta
from typing import Dict, Tuple, Any

from tenacity import retry, stop_after_attempt, wait_exponential
from github import Github

from .config import CONFIG
from .classify_utils import any_chinese

logger = logging.getLogger(__name__)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _get_repo(client: Github, full_name: str):
    logger.debug("get_repo: full_name=%s", full_name)
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
        logger.debug("_load_latest_snapshot: no snapshot files found")
        return None, None
    files.sort(reverse=True)
    path = os.path.join(CONFIG.data_dir, files[0])
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f), path
    except Exception as e:
        logger.error("_load_latest_snapshot: failed to load %s: %s", path, e)
        return None, None


def take_snapshot(candidates: Dict[str, dict], prev_snapshot: dict | None = None) -> dict:
    client = _client()
    now = datetime.now(timezone.utc)
    data: Dict[str, Any] = {"timestamp": now.isoformat(), "repos": {}}

    for full_name in candidates.keys():
        try:
            repo = _get_repo(client, full_name)
        except Exception as e:
            logger.warning("take_snapshot: get_repo failed for %s: %s", full_name, e)
            continue

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
                else:
                    logger.debug("take_snapshot: no readme content for %s", full_name)
            except Exception as e:
                logger.warning("take_snapshot: get_readme failed for %s: %s", full_name, e)

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
        logger.debug("take_snapshot: processed %s", full_name)

    # 保存
    path = _snapshot_path(now)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("take_snapshot: saved snapshot to %s", path)
    except Exception as e:
        logger.error("take_snapshot: failed to save snapshot: %s", e)

    return data


def compute_diff(curr: dict, prev: dict | None) -> dict:
    if prev is None:
        logger.info("compute_diff: no previous snapshot (prev=None), returning empty diff")
        return {
            "timestamp": curr.get("timestamp", datetime.now(timezone.utc).isoformat()),
            "base_timestamp": None,
            "top": [],
            "stats": {},
            "top_new": [],
            "top_growth": [],
            "first_seen": [],
        }
    # prev is an empty dict {} - treat as no previous data, collect all curr repos as first_seen
    if not prev:
        logger.info("compute_diff: prev is empty dict, collecting all curr repos as first_seen")

    diff_list = []
    first_seen = []  # 本次新增出现的仓库（无上一快照）
    prev_repos = prev.get("repos", {})
    new_repo_cutoff = None
    try:
        new_repo_cutoff = datetime.now(timezone.utc) - timedelta(days=CONFIG.diff.new_repo_days)
    except Exception as e:
        logger.warning("compute_diff: failed to calculate new_repo_cutoff: %s", e)
        pass

    for full_name, now in curr.get("repos", {}).items():
        before = prev_repos.get(full_name)
        if not before:
            # 收集首见项目（等待下次才有增量）
            first_seen.append({
                "repo": full_name,
                "stars_now": now.get("stars", 0),
                "language": now.get("language"),
                "description": now.get("description"),
                "created_at": now.get("created_at"),
                "has_chinese_readme": now.get("has_chinese_readme"),
                "readme_sample": now.get("readme_sample"),
            })
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
            except Exception as e:
                logger.warning("compute_diff: failed to parse created_at %s: %s", created_at_iso, e)
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
            logger.debug("compute_diff: skipping huge repo %s with delta=%d", full_name, delta)
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
        "growth_rank_count": len(top_growth),
    }

    # 限制首现项目数量
    first_seen = first_seen[: CONFIG.diff.first_seen_max]

    result = {
        "timestamp": curr.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "base_timestamp": prev.get("timestamp") if prev else None,
        "top": top_n,
        "stats": stats,
        "top_new": top_new,
        "top_growth": top_growth,
        "first_seen": first_seen,
    }
    logger.info("compute_diff: generated diff with %d repos, %d chinese, %d non_chinese",
                len(diff_list), chinese_count, non_chinese_count)
    return result


def cleanup_old_snapshots(keep: int = 120) -> None:
    """Keep only the newest 'keep' snapshot files; delete older ones."""
    if not os.path.isdir(CONFIG.data_dir):
        logger.debug("cleanup_old_snapshots: data_dir does not exist")
        return
    files = [f for f in os.listdir(CONFIG.data_dir) if f.startswith("snapshot_") and f.endswith(".json")]
    if len(files) <= keep:
        logger.debug("cleanup_old_snapshots: %d files <= keep=%d, no cleanup", len(files), keep)
        return
    files.sort(reverse=True)  # newest first
    to_delete = files[keep:]
    deleted = 0
    for fname in to_delete:
        try:
            os.remove(os.path.join(CONFIG.data_dir, fname))
            deleted += 1
        except Exception as e:
            logger.warning("cleanup_old_snapshots: failed to delete %s: %s", fname, e)
    logger.info("cleanup_old_snapshots: deleted %d old snapshots", deleted)


if __name__ == "__main__":
    # 简单连通性测试（需要先准备 candidates）
    pass