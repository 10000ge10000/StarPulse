from __future__ import annotations

from typing import List, Dict, Set
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass

from github import Github
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import CONFIG


@dataclass
class RepoBasic:
    full_name: str
    language: str | None
    stargazers_count: int
    description: str | None
    topics: List[str]
    license: str | None
    owner_type: str | None
    created_at: str
    pushed_at: str | None


def _build_queries() -> List[str]:
    cfg = CONFIG.search
    queries: List[str] = []
    base_time = datetime.now(timezone.utc) - timedelta(days=cfg.recent_days)
    updated_after = base_time.strftime("%Y-%m-%d")

    # 组合语言和主题以扩大覆盖面
    for lang in cfg.languages:
        q = f"language:{lang} stars:>={cfg.min_stars} pushed:>={updated_after}"
        queries.append(q)
    for topic in cfg.topics:
        q = f"topic:{topic} stars:>={cfg.min_stars} pushed:>={updated_after}"
        queries.append(q)

    # 再加一个通用兜底
    queries.append(f"stars:>={cfg.min_stars} pushed:>={updated_after}")
    return queries


def _get_client() -> Github:
    if CONFIG.github_token:
        return Github(CONFIG.github_token, per_page=100)
    return Github(per_page=100)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _search_once(client: Github, q: str):
    return client.search_repositories(query=q, sort="stars", order="desc")


def fetch_candidates(max_count: int | None = None) -> Dict[str, RepoBasic]:
    client = _get_client()
    queries = _build_queries()
    max_count = max_count or CONFIG.search.max_candidates

    seen: Set[str] = set()
    out: Dict[str, RepoBasic] = {}

    for q in queries:
        results = _search_once(client, q)
        for repo in results[:max_count]:  # 每个查询最多取 max_count，后续会去重
            fn = repo.full_name
            if fn in seen:
                continue
            seen.add(fn)
            topics = []
            try:
                topics = repo.get_topics() or []
            except Exception:
                topics = []
            out[fn] = RepoBasic(
                full_name=fn,
                language=repo.language,
                stargazers_count=repo.stargazers_count,
                description=repo.description,
                topics=topics,
                license=(repo.license.spdx_id if getattr(repo, "license", None) else None),
                owner_type=(repo.owner.type if getattr(repo, "owner", None) else None),
                created_at=repo.created_at.isoformat() if getattr(repo, "created_at", None) else "",
                pushed_at=repo.pushed_at.isoformat() if getattr(repo, "pushed_at", None) else None,
            )
            if len(out) >= max_count:
                break
        if len(out) >= max_count:
            break

    return out


if __name__ == "__main__":
    data = fetch_candidates()
    print(f"candidates: {len(data)}")
    # 简短预览
    for i, (k, v) in enumerate(data.items()):
        if i >= 5:
            break
        print(k, v.stargazers_count, v.language)
