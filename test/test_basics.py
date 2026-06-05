# -*- coding: utf-8 -*-
"""基础单元测试（纯函数）。"""

from narrativeloom.domain.coherence import analyze_story
from narrativeloom.utils.display_utils import prepare_mutation_display_text, repair_colon_split_name


def test_repair_colon_split_name():
    name, desc = repair_colon_split_name("阿依古", "丽是一名学生", context="阿依古丽")
    assert name == "阿依古丽"
    assert "丽" not in desc or desc.startswith("是")


def test_analyze_story_empty():
    count, issues = analyze_story([])
    assert count == 0
    assert issues == []


def test_prepare_mutation_display_text_passthrough():
    text = "普通段落"
    assert prepare_mutation_display_text(text, baseline=text) == text
