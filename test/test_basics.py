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


def test_complete_sculptor_section_rejects_garbage_and_keeps_seed():
    from narrativeloom.domain.character_names import complete_sculptor_section

    seed = "达芬奇·狗剩在猪圈墙上画《最后的晚餐》，模特是十二头猪。"
    bad_body = "- 沾满面粉：严谨务实的画家\n- 炭灰：猪圈里的旁观者"
    locked = extract_seed_cast_names(seed)
    out = complete_sculptor_section(
        bad_body,
        plot_sources=["猪圈墙上，沾满面粉的手在画"],
        locked_names=locked,
        target=2,
        seed=seed,
    )
    assert "达芬奇·狗剩" in out
    assert "沾满面粉" not in out
    assert "炭灰" not in out


def test_normalize_unified_outline_preserves_seed_protagonist():
    from narrativeloom.utils.display_utils import normalize_single_unified_outline

    seed = "达芬奇·狗剩在猪圈墙上画《最后的晚餐》，模特是十二头猪。"
    raw = (
        "【设定构建师】\n- 地点：猪圈\n- 时间：午后\n"
        "【人物塑造师】\n- 沾满面粉：画家\n- 炭灰：旁观者\n"
        "【剧情逻辑师】\n- 狗剩在墙上作画"
    )
    out = normalize_single_unified_outline(
        raw,
        role_names=["设定构建师", "人物塑造师", "剧情逻辑师"],
        locked_names=["达芬奇·狗剩"],
        character_target_total=2,
        seed=seed,
    )
    assert "达芬奇·狗剩" in out
    assert "沾满面粉" not in out
