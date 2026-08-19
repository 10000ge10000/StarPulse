"""Tests for snapshot_and_diff module - compute_diff function."""

import sys
import json
import os
sys.path.insert(0, '/vol1/@appshare/DeepSeekHarness/workspace/StarWork')

from src.snapshot_and_diff import compute_diff


def test_compute_diff_no_prev():
    """Test compute_diff with no previous snapshot."""
    curr = {
        "timestamp": "2025-11-11T12:00:00Z",
        "repos": {
            "owner/repo1": {
                "stars": 100,
                "forks": 10,
                "language": "Python",
                "topics": ["python"],
                "license": "MIT",
                "description": "A Python library",
            }
        }
    }
    result = compute_diff(curr, None)
    assert result["base_timestamp"] is None, "base_timestamp should be None"
    assert len(result["top"]) == 0, "top should be empty when no prev"
    assert result["stats"] == {}, "stats should be empty dict when no prev"
    assert result["first_seen"] == [], "first_seen should be empty list when no prev"
    print("test_compute_diff_no_prev: PASSED")


def test_compute_diff_with_prev():
    """Test compute_diff with previous snapshot."""
    curr = {
        "timestamp": "2025-11-11T12:00:00Z",
        "repos": {
            "owner/repo1": {
                "stars": 105,  # delta = 5
                "forks": 12,
                "language": "Python",
                "topics": ["python"],
                "license": "MIT",
                "description": "A Python library",
                "created_at": "2025-01-01T00:00:00Z",
                "pushed_at": "2025-11-10T00:00:00Z",
            }
        }
    }
    prev = {
        "timestamp": "2025-11-10T12:00:00Z",
        "repos": {
            "owner/repo1": {
                "stars": 100,
                "forks": 10,
                "language": "Python",
                "topics": ["python"],
                "license": "MIT",
                "description": "A Python library",
                "created_at": "2025-01-01T00:00:00Z",
                "pushed_at": "2025-11-09T00:00:00Z",
            }
        }
    }
    result = compute_diff(curr, prev)
    assert result["base_timestamp"] is not None, "base_timestamp should be set"
    assert len(result["top"]) > 0, "top should have entries"
    # Check delta is calculated
    top_entry = result["top"][0]
    assert top_entry["delta"] == 5, f"delta should be 5, got {top_entry['delta']}"
    # Check growth_rate is calculated (5/100 = 0.05)
    assert top_entry["growth_rate"] == 0.05, f"growth_rate should be 0.05, got {top_entry['growth_rate']}"
    print("test_compute_diff_with_prev: PASSED")


def test_compute_diff_huge_repo_filter():
    """Test that huge repos with small delta are filtered out."""
    curr = {
        "timestamp": "2025-11-11T12:00:00Z",
        "repos": {
            "huge/repo1": {
                "stars": 100000,  # 100K stars - huge repo threshold
                "forks": 1000,
                "language": "Python",
                "topics": ["python"],
                "license": "MIT",
                "description": "A huge Python library",
                "created_at": "2025-01-01T00:00:00Z",
                "pushed_at": "2025-11-10T00:00:00Z",
            }
        }
    }
    prev = {
        "timestamp": "2025-11-10T12:00:00Z",
        "repos": {
            "huge/repo1": {
                "stars": 100000,
                "forks": 1000,
                "language": "Python",
                "topics": ["python"],
                "license": "MIT",
                "description": "A huge Python library",
                "created_at": "2025-01-01T00:00:00Z",
                "pushed_at": "2025-11-09T00:00:00Z",
            }
        }
    }
    result = compute_diff(curr, prev)
    # delta should be 0, which is < min_delta_for_huge (2), so should be filtered
    top_entries = [d for d in result["top"] if d["repo"] == "huge/repo1"]
    assert len(top_entries) == 0, "Huge repo with delta < 2 should be filtered out"
    print("test_compute_diff_huge_repo_filter: PASSED")


def test_compute_diff_first_seen():
    """Test that first_seen repos are collected."""
    curr = {
        "timestamp": "2025-11-11T12:00:00Z",
        "repos": {
            "new/repo1": {
                "stars": 10,
                "forks": 1,
                "language": "Rust",
                "topics": ["rust"],
                "license": "MIT",
                "description": "A new Rust project",
                "created_at": "2025-11-05T00:00:00Z",  # Within 30 days
                "pushed_at": "2025-11-10T00:00:00Z",
            }
        }
    }
    prev = {}  # No previous snapshots
    result = compute_diff(curr, prev)
    # first_seen should contain the new repo
    assert len(result["first_seen"]) > 0, "first_seen should have entries"
    repo_names = [f["repo"] for f in result["first_seen"]]
    assert "new/repo1" in repo_names, "new/repo1 should be in first_seen"
    print("test_compute_diff_first_seen: PASSED")


def test_compute_diff_growth_rate_none():
    """Test that growth_rate is None when stars_prev is too low."""
    curr = {
        "timestamp": "2025-11-11T12:00:00Z",
        "repos": {
            "small/repo1": {
                "stars": 3,  # Below min_prev_stars_for_growth (50)
                "forks": 1,
                "language": "Python",
                "topics": ["python"],
                "license": "MIT",
                "description": "A small Python project",
                "created_at": "2025-01-01T00:00:00Z",
                "pushed_at": "2025-11-10T00:00:00Z",
            }
        }
    }
    prev = {
        "timestamp": "2025-11-10T12:00:00Z",
        "repos": {
            "small/repo1": {
                "stars": 2,
                "forks": 1,
                "language": "Python",
                "topics": ["python"],
                "license": "MIT",
                "description": "A small Python project",
                "created_at": "2025-01-01T00:00:00Z",
                "pushed_at": "2025-11-09T00:00:00Z",
            }
        }
    }
    result = compute_diff(curr, prev)
    top_entries = [d for d in result["top"] if d["repo"] == "small/repo1"]
    # growth_rate should be None since stars_prev (2) < min_prev_stars_for_growth (50)
    assert len(top_entries) > 0, "small/repo1 should be in top"
    assert top_entries[0]["growth_rate"] is None, "growth_rate should be None for low star count"
    print("test_compute_diff_growth_rate_none: PASSED")


if __name__ == "__main__":
    test_compute_diff_no_prev()
    test_compute_diff_with_prev()
    test_compute_diff_huge_repo_filter()
    test_compute_diff_first_seen()
    test_compute_diff_growth_rate_none()
    print("\nAll compute_diff tests PASSED!")