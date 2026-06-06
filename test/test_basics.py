# -*- coding: utf-8 -*-
"""基础单元测试（纯函数）。"""

from narrativeloom.domain.coherence import analyze_story
from narrativeloom.domain.character_names import extract_seed_cast_names
from narrativeloom.utils.display_utils import (
    _html_escape_mutations,
    prepare_mutation_display_text,
    repair_colon_split_name,
)


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


def test_mutation_highlight_bare_brackets():
    html = _html_escape_mutations("⟦改动句⟧")
    assert "nl-mut-highlight" in html
    assert "改动句" in html
    assert "⟦" not in html


def test_mutation_highlight_standard_markers():
    html = _html_escape_mutations("⟦mut⟧改动句⟦/mut⟧")
    assert "nl-mut-highlight" in html
    assert "改动句" in html


def test_extract_seed_cast_compound_name():
    seed = "达芬奇·狗剩在猪圈墙上画《最后的晚餐》，模特是十二头猪"
    names = extract_seed_cast_names(seed)
    assert "达芬奇·狗剩" in names
