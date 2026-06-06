# -*- coding: utf-8 -*-
"""基础单元测试（纯函数）。"""

import re

from narrativeloom.domain.coherence import analyze_story
from narrativeloom.domain.character_names import extract_seed_cast_names
from narrativeloom.utils.display_utils import (
    _html_escape_mutations,
    prepare_mutation_display_text,
    repair_colon_split_name,
)


def _sculptor_lines(text: str) -> list[str]:
    m = re.search(r"【人物塑造师】\s*(.*?)(?=【|$)", text, re.S)
    block = (m.group(1) if m else text).strip()
    return [ln.strip() for ln in block.splitlines() if ln.strip()]


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
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert len(lines) == 2
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
    assert len(_sculptor_lines(out)) == 2
    assert "达芬奇·狗剩" in out
    assert "沾满面粉" not in out


def test_sculptor_rejects_llm_only_hallucinated_names():
    from narrativeloom.domain.character_names import complete_sculptor_section

    seed = "达芬奇·狗剩在猪圈墙上画《最后的晚餐》，模特是十二头猪。"
    locked = extract_seed_cast_names(seed)
    bad_body = "- 阿依古丽威：棋盘上的红衣主教\n- 阿依古丽清：关键剧情人物"
    plot = "- 达芬奇被酒馆赶出后闯入猪圈"
    out = complete_sculptor_section(
        bad_body,
        plot_sources=[plot],
        locked_names=locked,
        target=2,
        seed=seed,
    )
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert len(lines) == 2
    assert "达芬奇·狗剩" in out
    assert "阿依古丽威" not in out
    assert "阿依古丽清" not in out


def test_sculptor_allows_cross_section_name_from_plot():
    from narrativeloom.domain.character_names import complete_sculptor_section

    seed = "达芬奇·狗剩在猪圈墙上画《最后的晚餐》，模特是十二头猪。"
    locked = extract_seed_cast_names(seed)
    body = "- 韩星：房东的女儿"
    plot = "- 韩星偷拍达芬奇在猪圈作画的视频"
    out = complete_sculptor_section(
        body,
        plot_sources=[plot],
        locked_names=locked,
        target=2,
        seed=seed,
    )
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert len(lines) == 2
    assert "达芬奇·狗剩" in out
    assert "韩星" in out


def test_sculptor_accepts_valid_llm_second_character():
    from narrativeloom.domain.character_names import complete_sculptor_section

    seed = "达芬奇·狗剩在猪圈墙上画《最后的晚餐》，模特是十二头猪。"
    locked = extract_seed_cast_names(seed)
    body = "- 老周：猪圈看守，常来赶人"
    plot = "- 达芬奇被酒馆赶出后闯入猪圈"
    out = complete_sculptor_section(
        body,
        plot_sources=[plot],
        locked_names=locked,
        target=2,
        seed=seed,
    )
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert len(lines) == 2
    assert "达芬奇·狗剩" in out
    assert "老周" in out


def test_coerce_unified_plan_target_two_with_seed_only():
    from narrativeloom.service.llm_client import _coerce_unified_plan_variants

    seed = "达芬奇·狗剩在猪圈墙上画《最后的晚餐》，模特是十二头猪。"
    locked = extract_seed_cast_names(seed)
    raw = """【设定构建师】
- 地点：文艺复兴意大利某庄园猪圈
【人物塑造师】
- 阿依古丽威：棋盘上的红衣主教
- 阿依古丽清：关键剧情人物
【剧情逻辑师】
- 达芬奇被酒馆赶出后闯入猪圈
【冲突设计师】
- 核心矛盾：艺术与世俗"""
    out = _coerce_unified_plan_variants(
        [{"outline": raw}],
        plan_count=1,
        feedback_process=False,
        locked_character_names=locked,
        character_target_total=2,
        role_names=["设定构建师", "人物塑造师", "剧情逻辑师", "冲突设计师"],
        seed=seed,
    )[0]["outline"]
    lines = _sculptor_lines(out)
    assert len(lines) == 2
    assert "达芬奇·狗剩" in out
    assert "阿依古丽威" not in out
    assert "阿依古丽清" not in out
