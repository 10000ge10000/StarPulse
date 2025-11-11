from __future__ import annotations

import json
import os

from .config import CONFIG
from .fetch_candidates import fetch_candidates
from .snapshot_and_diff import take_snapshot, compute_diff, cleanup_old_snapshots
from .categorize_and_render import render_markdown, render_json


def main():
    # Ensure required directories exist on fresh runners
    os.makedirs(CONFIG.data_dir, exist_ok=True)
    os.makedirs(CONFIG.output_dir, exist_ok=True)

    # 1) 候选仓库（可定期更新集合；此处每次运行都刷新）
    candidates = fetch_candidates()

    # 2) 找到上一快照（先找 prev，再生成 curr 以便在快照阶段能重用缓存）
    files = sorted([f for f in os.listdir(CONFIG.data_dir) if f.startswith("snapshot_") and f.endswith(".json")])
    prev_path = os.path.join(CONFIG.data_dir, files[-1]) if files else None
    prev = None
    if prev_path and os.path.exists(prev_path):
        with open(prev_path, "r", encoding="utf-8") as f:
            prev = json.load(f)

    # 3) 当前快照（可复用上一快照的 README 数据）
    curr = take_snapshot(candidates, prev_snapshot=prev)

    # 4) 计算增量
    diff_res = compute_diff(curr, prev)

    # 5) 输出
    render_markdown(curr, diff_res, CONFIG.output_dir)
    render_json(curr, diff_res, CONFIG.output_dir)

    # 6) 清理过旧快照
    cleanup_old_snapshots(keep=120)


if __name__ == "__main__":
    main()
