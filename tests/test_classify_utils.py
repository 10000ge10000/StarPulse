"""Tests for classify_utils module."""

import sys
sys.path.insert(0, '/vol1/@appshare/DeepSeekHarness/workspace/StarWork')

from src.classify_utils import is_chinese_project, is_chinese_text, any_chinese


def test_any_chinese():
    """Test any_chinese function."""
    # No CJK characters
    assert any_chinese("Hello world") == False, "Should be False for no CJK"
    # With CJK characters
    assert any_chinese("Hello 世界") == True, "Should be True with CJK"
    # Empty string
    assert any_chinese("") == False, "Should be False for empty string"
    # None
    assert any_chinese(None) == False, "Should be False for None"
    print("test_any_chinese: PASSED")


def test_is_chinese_text():
    """Test is_chinese_text function."""
    # Mostly CJK
    assert is_chinese_text("世界你好", 0.5) == True, "Should be True for high CJK ratio"
    # Mostly non-CJK
    assert is_chinese_text("Hello world", 0.5) == False, "Should be False for low CJK ratio"
    # More CJK characters to reach threshold: "界" is 1/3 = 0.33 < 0.5, need more
    assert is_chinese_text("a界b界", 0.5) == True, "Should be True when CJK ratio >= 0.5"
    # Exactly at threshold with 50% CJK (2/4 = 0.5)
    assert is_chinese_text("界界Hi", 0.5) == True, "Should be True at exact threshold (2/4 = 0.5)"
    # Below threshold
    assert is_chinese_text("界Hi", 0.5) == False, "Should be False when CJK ratio < 0.5 (1/2 = 0.5 is not <, use 1/3)"
    # Empty string
    assert is_chinese_text("", 0.5) == False, "Should be False for empty string"
    # None
    assert is_chinese_text(None, 0.5) == False, "Should be False for None"
    print("test_is_chinese_text: PASSED")


def test_is_chinese_project():
    """Test is_chinese_project function with various repo data."""
    # Chinese description
    item1 = {
        "description": "一个Python库",
        "topics": ["python"],
        "license": "MIT",
        "readme_sample": "",
        "has_chinese_readme": False,
    }
    assert is_chinese_project(item1) == True, "Should detect Chinese from description"

    # Chinese in topics
    item2 = {
        "description": "A Python library",
        "topics": ["中文", "python"],
        "license": "MIT",
        "readme_sample": "",
        "has_chinese_readme": False,
    }
    assert is_chinese_project(item2) == True, "Should detect Chinese from topics"

    # Chinese keyword
    item3 = {
        "description": "A Python library",
        "topics": ["python"],
        "license": "MIT",
        "readme_sample": "",
        "has_chinese_readme": False,
    }
    # Add Chinese keyword
    item3_with_keyword = {
        "description": "A Python library",
        "topics": ["python"],
        "license": "MIT",
        "readme_sample": "",
        "has_chinese_readme": False,
    }
    # Need to add a chinese keyword manually - test with keyword present
    item4 = {
        "description": "A Python library",
        "topics": ["python"],
        "license": "MIT",
        "readme_sample": "",
        "has_chinese_readme": False,
    }
    # Test with Chinese keyword in license or topics
    item5 = {
        "description": "",
        "topics": ["python", "中文"],
        "license": "",
        "readme_sample": "",
        "has_chinese_readme": False,
    }
    assert is_chinese_project(item5) == True, "Should detect Chinese from Chinese in topics"

    # No Chinese indicators
    item6 = {
        "description": "A Python library",
        "topics": ["python"],
        "license": "MIT",
        "readme_sample": "",
        "has_chinese_readme": False,
    }
    assert is_chinese_project(item6) == False, "Should be False without Chinese indicators"

    # has_chinese_readme flag
    item7 = {
        "description": "",
        "topics": ["python"],
        "license": "MIT",
        "readme_sample": "",
        "has_chinese_readme": True,
    }
    assert is_chinese_project(item7) == True, "Should be True when has_chinese_readme is True"

    print("test_is_chinese_project: PASSED")


if __name__ == "__main__":
    test_any_chinese()
    test_is_chinese_text()
    test_is_chinese_project()
    print("\nAll tests PASSED!")