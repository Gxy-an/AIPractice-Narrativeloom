# -*- coding: utf-8 -*-
"""基础单元测试（纯函数）。"""

import re

import pytest

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


def _sculptor_names(text: str) -> list[str]:
    names: list[str] = []
    for ln in _sculptor_lines(text):
        probe = ln.lstrip("-·• ").strip()
        if "：" in probe:
            names.append(probe.split("：", 1)[0].strip())
        elif ":" in probe:
            names.append(probe.split(":", 1)[0].strip())
    return names


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
        plot_sources=["猪圈墙上，沾满面粉的手在画，老周在一旁看守"],
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
        "【剧情逻辑师】\n- 狗剩在墙上作画，老周在一旁看守"
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
    plot = "- 达芬奇被酒馆赶出后闯入猪圈，店主韩星将其锁在门外"
    out = complete_sculptor_section(
        bad_body,
        plot_sources=[plot],
        locked_names=locked,
        target=2,
        seed=seed,
    )
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert len(lines) >= 1
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
    plot = "- 老周赶走醉酒的达芬奇，仍允许他在猪圈作画"
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
    assert len(lines) >= 1
    assert "达芬奇·狗剩" in out
    assert "阿依古丽威" not in out
    assert "阿依古丽清" not in out


def test_rejects_time_and_object_as_character_names():
    from narrativeloom.domain.character_names import (
        complete_sculptor_section,
        extract_cast_from_narrative,
        is_false_person_name,
        parse_colon_lines,
    )
    from narrativeloom.utils.display_utils import extract_names_from_narrative, normalize_single_unified_outline

    seed = "李明在黎明整理老宅中的陶罐。"
    context = "时间：黎明\n地点：老宅\n周六下午，李明在陶罐旁整理旧物"
    for bad in ("黎明", "周六下", "陶罐", "周六", "下午"):
        assert is_false_person_name(bad, context=context), bad

    assert extract_names_from_narrative(context) == ["李明"]
    assert extract_cast_from_narrative(context) == ["李明"]
    assert parse_colon_lines(
        "- 黎明：清晨时分\n- 周六下：午后时光\n- 陶罐：角落旧物",
        context=context,
    ) == {}

    locked = ["李明"]
    out = complete_sculptor_section(
        "- 黎明：清晨\n- 周六下：午后\n- 陶罐：旧物",
        plot_sources=["- 周六下午李明在陶罐旁整理，王婶送来旧信"],
        locked_names=locked,
        target=2,
        seed=seed,
    )
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert len(lines) == 2
    assert "李明" in _sculptor_names("【人物塑造师】\n" + out)
    for bad in ("黎明", "周六下", "陶罐"):
        assert bad not in _sculptor_names("【人物塑造师】\n" + out)

    raw = (
        "【设定构建师】\n- 地点：老宅\n- 时间：黎明\n"
        "【人物塑造师】\n- 黎明：清晨\n- 周六下：午后\n- 陶罐：旧物\n"
        "【剧情逻辑师】\n- 周六下午李明在陶罐旁整理，王婶送来旧信"
    )
    normalized = normalize_single_unified_outline(
        raw,
        role_names=["设定构建师", "人物塑造师", "剧情逻辑师"],
        locked_names=locked,
        character_target_total=2,
        seed=seed,
    )
    sculptor = _sculptor_lines(normalized)
    assert len(sculptor) == 2
    names = _sculptor_names(normalized)
    assert "李明" in names
    for bad in ("黎明", "周六下", "陶罐"):
        assert bad not in names


def test_coerce_rejects_time_object_sculptor_lines():
    from narrativeloom.service.llm_client import _coerce_unified_plan_variants

    seed = "李明在黎明整理老宅中的陶罐。"
    raw = """【设定构建师】
- 地点：老宅
- 时间：黎明
【人物塑造师】
- 黎明：清晨时分
- 周六下：午后时光
- 陶罐：角落旧物
【剧情逻辑师】
- 周六下午李明在陶罐旁整理，王婶送来旧信"""
    out = _coerce_unified_plan_variants(
        [{"outline": raw}],
        plan_count=1,
        feedback_process=False,
        locked_character_names=["李明"],
        character_target_total=2,
        role_names=["设定构建师", "人物塑造师", "剧情逻辑师"],
        seed=seed,
    )[0]["outline"]
    sculptor = _sculptor_lines(out)
    assert len(sculptor) == 2
    names = _sculptor_names(out)
    assert "李明" in names
    for bad in ("黎明", "周六下", "陶罐"):
        assert bad not in names


def test_functional_plot_name_replaces_sculptor_only_hallucination():
    from narrativeloom.service.llm_client import _coerce_unified_plan_variants

    seed = "达芬奇·狗剩在猪圈墙上画《最后的晚餐》。"
    locked = extract_seed_cast_names(seed)
    raw = """【设定构建师】
- 地点：托斯卡乡村猪圈
- 时间：1502年午后
【人物塑造师】
- 达芬奇·狗剩：流浪画家
- 托斯卡：来访学者
【剧情逻辑师】
- 朱塞佩看见狗剩在猪圈画壁画，威胁要毁掉颜料
- 朱塞佩与狗剩争执颜料来源
【冲突设计师】
- 核心矛盾：艺术幻想与生存现实"""
    out = _coerce_unified_plan_variants(
        [{"outline": raw}],
        plan_count=1,
        feedback_process=False,
        locked_character_names=locked,
        character_target_total=2,
        role_names=["设定构建师", "人物塑造师", "剧情逻辑师", "冲突设计师"],
        seed=seed,
    )[0]["outline"]
    names = _sculptor_names(out)
    assert len(names) == 2
    assert "达芬奇·狗剩" in names
    assert "朱塞佩" in names
    assert "托斯卡" not in names


def test_sanitize_typified_characters_filters_device():
    from narrativeloom.utils.display_utils import sanitize_typified_characters

    raw = (
        "- 达芬奇·狗剩：牧群编号D-07\n"
        "- 十二头猪：实验体M系列\n"
        "- 巡逻嗅探器：型号S-17B\n"
        "- 黑袍陌生人：通风管中的神秘面孔"
    )
    out = sanitize_typified_characters(
        raw,
        target=3,
        locked_names=["达芬奇·狗剩"],
        seed="达芬奇·狗剩在猪圈作画",
        key_events="黑袍陌生人从通风管现身；老周停在圈门察看",
    )
    names = _sculptor_names("【人物塑造师】\n" + out)
    assert "达芬奇·狗剩" in names
    assert "巡逻嗅探器" not in names
    assert "黑袍陌生人" in names
    assert len(names) >= 2
    assert not any(n.startswith("配角") for n in names)


def test_extract_verbed_cn_name_giuseppe():
    from narrativeloom.domain.character_names import extract_cast_from_narrative

    plot = "朱塞佩看见狗剩在猪圈画壁画，威胁要毁掉颜料"
    names = extract_cast_from_narrative(plot)
    assert "朱塞佩" in names


def test_rejects_verb_glued_name_colliding_with_compound_cast():
    from narrativeloom.domain.character_names import complete_sculptor_section, extract_seed_cast_names

    seed = "达芬奇·狗剩在猪圈墙上画《最后的晚餐》。"
    locked = extract_seed_cast_names(seed)
    body = (
        "- 达芬奇·狗剩：被绑在账房，用脚趾作画\n"
        "- 马可·猪倌：庄园管事，逼签契约\n"
        "- 马可惊：关键剧情人物，须在本节行动中有动机"
    )
    plot = "- 菲利波见达芬奇被绑，掏出红墨水，威胁要毁掉壁画"
    out = complete_sculptor_section(
        body,
        plot_sources=[plot],
        locked_names=locked,
        target=3,
        seed=seed,
    )
    names = _sculptor_names(out)
    assert len(names) == 3
    assert "达芬奇·狗剩" in names
    assert "马可·猪倌" in names
    assert "菲利波" in names
    assert "马可惊" not in names
    assert "马可认" not in names
    assert not any(n.startswith("配角") for n in names)


def test_fallback_prefers_plot_name_over_generic():
    from narrativeloom.domain.character_names import _fallback_supplementary_name

    existing = ["达芬奇·狗剩", "马可·猪倌"]
    plot = "安东尼奥砸碎猪骨，与马可·猪倌争执"
    name = _fallback_supplementary_name(
        existing, full="", seed="达芬奇·狗剩在猪圈作画", narrative=plot
    )
    assert name == "安东尼奥"


def test_sanitize_typified_rejects_verb_glued_duplicate():
    from narrativeloom.utils.display_utils import sanitize_typified_characters

    raw = (
        "- 达芬奇·狗剩：被绑在账房\n"
        "- 马可·猪倌：庄园管事\n"
        "- 马可惊：误拆姓名\n"
        "- 菲利波：铁匠"
    )
    out = sanitize_typified_characters(
        raw,
        target=3,
        locked_names=["达芬奇·狗剩"],
        seed="达芬奇·狗剩在猪圈作画",
        key_events="菲利波见达芬奇被绑，安东尼奥在旁砸骨",
    )
    names = _sculptor_names("【人物塑造师】\n" + out)
    assert "马可·猪倌" in names
    assert "马可惊" not in names
    assert not any(n.startswith("配角") for n in names)


def test_format_typified_brief_shows_up_to_five_events():
    from narrativeloom.utils.display_utils import format_typified_brief

    data = {
        "setting": "1480年佛罗伦萨猪圈",
        "characters": "- 朱丽叶·猪：流浪女巫",
        "key_events": "\n".join(f"- 事件{i}" for i in range(1, 6)),
    }
    _, _, ev_block = format_typified_brief(data, "zh")
    assert ev_block.count("·") == 5


def test_sanitize_preserves_prior_locked_character_description():
    from narrativeloom.utils.display_utils import sanitize_typified_characters

    prior = "- 朱丽叶·猪：披着橄榄枝斗篷的流浪女巫\n- 罗伦佐·屠夫：庄园管事"
    out = sanitize_typified_characters(
        "- 埃尔梅琳·烛焰：见证预言",
        target=2,
        locked_names=["朱丽叶·猪"],
        seed="种子",
        prior_characters_block=prior,
    )
    assert "流浪女巫" in out
    assert "承接前文既定人物" not in out


def test_functional_rejects_plot_fragment_as_character_name():
    from narrativeloom.service.llm_client import _coerce_unified_plan_variants

    seed = "达芬奇·狗剩在猪圈墙上画《最后的晚餐》。"
    locked = extract_seed_cast_names(seed)
    raw = """【设定构建师】
- 地点：文艺复兴意大利猪圈
- 时间：1502年午后
【人物塑造师】
- 达芬奇·狗剩：流浪画家
- 到朱塞佩：借猪圈，用分三头猪作饵
- 想借网红：老板
【剧情逻辑师】
- 朱塞佩撞见狗剩在猪圈画壁画，玛利亚出面调解
- 朱塞佩与狗剩争执颜料来源
【冲突设计师】
- 核心矛盾：艺术幻想与生存现实"""
    out = _coerce_unified_plan_variants(
        [{"outline": raw}],
        plan_count=1,
        feedback_process=False,
        locked_character_names=locked,
        character_target_total=3,
        role_names=["设定构建师", "人物塑造师", "剧情逻辑师", "冲突设计师"],
        seed=seed,
    )[0]["outline"]
    names = _sculptor_names(out)
    assert "达芬奇·狗剩" in names
    assert "朱塞佩" in names
    assert "到朱塞佩" not in names
    assert "想借网红" not in names
    assert "朱塞佩撞" not in names
    assert "玛利亚" in names
    assert "流浪画家" in out or "流浪" in out


def test_typified_locked_seed_gets_concrete_description_not_placeholder():
    from narrativeloom.utils.display_utils import sanitize_typified_characters

    seed = "达芬奇·狗剩在猪圈墙上画《最后的晚餐》，模特是十二头猪"
    raw = (
        "- 达芬奇·狗剩：承接前文既定人物，本节须保留\n"
        "- 咕噜·獠牙：先知猪，鼻环刻精灵符文"
    )
    out = sanitize_typified_characters(
        raw,
        target=2,
        locked_names=["达芬奇·狗剩"],
        seed=seed,
        setting="黄昏时分，发光沼泽旁的泥泞猪圈",
    )
    assert "达芬奇·狗剩" in out
    assert "承接前文" not in out
    assert "关键剧情人物" not in out


def test_functional_rejects_abstract_theme_and_scene_fragment_names():
    from narrativeloom.service.llm_client import _coerce_unified_plan_variants

    seed = "艾买提在克拉玛依老炼油厂整理车间设备。"
    locked = ["艾买提"]
    raw = """【设定构建师】
- 地点：克拉玛依老炼油厂
- 时间：1940年代末
【人物塑造师】
- 艾买提：师傅
- 神圣构图：关键剧情人物，动机与性格须在本小节行动中体现
- 生存现实：关键剧情人物，动机与性格须在本小节行动中体现
【剧情逻辑师】
- 艾买提在清理车间时发现苏联加密笔记
- 韩星假借采访接近艾买提
【冲突设计师】
- 核心矛盾：国家油矿数据与个人安危"""
    out = _coerce_unified_plan_variants(
        [{"outline": raw}],
        plan_count=1,
        feedback_process=False,
        locked_character_names=locked,
        character_target_total=2,
        role_names=["设定构建师", "人物塑造师", "剧情逻辑师", "冲突设计师"],
        seed=seed,
    )[0]["outline"]
    names = _sculptor_names(out)
    assert len(names) == 2
    assert "艾买提" in names
    assert "韩星" in names
    assert "神圣构图" not in names
    assert "生存现实" not in names
    assert "理车间时" not in names
    assert "关键剧情人物" not in out


def test_functional_rejects_workshop_time_fragment_name():
    from narrativeloom.service.llm_client import _coerce_unified_plan_variants

    seed = "艾买提在克拉玛依老炼油厂整理车间。"
    locked = ["艾买提"]
    raw = """【设定构建师】
- 地点：克拉玛依老炼油厂
- 时间：1940年代末
【人物塑造师】
- 艾买提：师傅
- 理车间时：关键剧情人物，动机与性格须在本小节行动中体现
【剧情逻辑师】
- 艾买提在清理车间时发现苏联加密笔记，韩星在旁观察
【冲突设计师】
- 核心矛盾：信任与隐瞒"""
    out = _coerce_unified_plan_variants(
        [{"outline": raw}],
        plan_count=1,
        feedback_process=False,
        locked_character_names=locked,
        character_target_total=2,
        role_names=["设定构建师", "人物塑造师", "剧情逻辑师", "冲突设计师"],
        seed=seed,
    )[0]["outline"]
    names = _sculptor_names(out)
    assert "艾买提" in names
    assert "韩星" in names
    assert "理车间时" not in names


def test_normalize_typified_key_events_respects_length_and_total_cap():
    from narrativeloom.utils.display_utils import normalize_typified_key_events

    events = "\n".join(f"- 事件条目{i}，" + "甲" * 35 for i in range(1, 7))
    out = normalize_typified_key_events(events, min_lines=3, max_lines=5, lang="zh")
    lines = [ln.lstrip("-·• ").strip() for ln in out.splitlines() if ln.strip()]
    assert 3 <= len(lines) <= 5
    assert all(30 <= len(ln) <= 50 for ln in lines)
    assert sum(len(ln) for ln in lines) <= 300


def test_typified_rejects_exchange_and_possessive_fragment_names():
    from narrativeloom.utils.display_utils import sanitize_typified_characters

    seed = "艾买提在天山驿站与阿依古丽交换商旅消息，一位老僧的警告在驿站回响。"
    plot = "- 艾买提向阿依古丽分享会说话的石头传闻\n- 老僧出言警告艾买提勿信谣言"
    raw = (
        "- 交换：集市从业者，熟稔本地风物\n"
        "- 老僧的警：互斥矛盾，阿依古丽不知该信谁\n"
        "- 阿依古丽：驿站掌柜之女"
    )
    out = sanitize_typified_characters(
        raw,
        target=2,
        locked_names=["艾买提"],
        seed=seed,
        setting="贞观年间天山驿站，旅人须分享消息方可留宿",
        key_events=plot,
    )
    names = _sculptor_names("【人物塑造师】\n" + out)
    assert len(names) == 2
    assert "艾买提" in names
    assert "阿依古丽" in names
    assert "交换" not in names
    assert "老僧的警" not in names
    assert "关键剧情人物" not in out


def test_functional_rejects_pretense_fragment_and_fills_target():
    from narrativeloom.service.llm_client import _coerce_unified_plan_variants

    seed = "韩星在废弃勘探点调查周教授的可疑举动。"
    locked = ["韩星"]
    raw = """【设定构建师】
- 地点：废弃勘探点空大厅
- 时间：当代深夜
【人物塑造师】
- 韩星：关键剧情人物，动机与性格须在本小节行动中体现
- 星假装没：关键剧情人物，动机与性格须在本小节行动中体现
【剧情逻辑师】
- 韩星假装没听见，却见周教授撕下登记簿一页
- 周教授追问韩星为何深夜出现在此
【冲突设计师】
- 核心矛盾：发现真相与掩盖过往"""
    out = _coerce_unified_plan_variants(
        [{"outline": raw}],
        plan_count=1,
        feedback_process=False,
        locked_character_names=locked,
        character_target_total=2,
        role_names=["设定构建师", "人物塑造师", "剧情逻辑师", "冲突设计师"],
        seed=seed,
    )[0]["outline"]
    names = _sculptor_names(out)
    assert len(names) == 2
    assert "韩星" in names
    assert "周教授" in names
    assert "星假装没" not in names
    assert "关键剧情人物" not in out


@pytest.mark.parametrize(
    "seed_plot_pair",
    [
        (
            "达芬奇·狗剩在猪圈墙上画《最后的晚餐》，模特是十二头猪",
            "朱塞佩看见狗剩在猪圈画壁画，老周在一旁看守",
            ["达芬奇·狗剩"],
            2,
            ["达芬奇·狗剩", "朱塞佩"],
        ),
        (
            "艾买提在克拉玛依老炼油厂整理车间设备",
            "艾买提在清理车间时发现笔记，韩星假借采访接近艾买提",
            ["艾买提"],
            2,
            ["艾买提", "韩星"],
        ),
        (
            "阿依古丽在天山驿站经营干果铺",
            "艾买提向阿依古丽分享石头传闻，老僧出面警告",
            ["阿依古丽"],
            2,
            ["阿依古丽", "艾买提"],
        ),
    ],
)
def test_sanitize_fills_exact_target_from_multiple_seeds(seed_plot_pair):
    from narrativeloom.utils.display_utils import sanitize_typified_characters

    seed, plot, locked, target, must_include = seed_plot_pair
    out = sanitize_typified_characters(
        "- 交换：无效\n- 老僧的警：无效",
        target=target,
        locked_names=locked,
        seed=seed,
        key_events=plot,
    )
    names = _sculptor_names("【人物塑造师】\n" + out)
    assert len(names) == target
    for name in must_include:
        assert name in names


@pytest.mark.parametrize(
    "bad_name",
    ["控中", "任何以", "任何召", "飘着麦秸", "时被翠花"],
)
def test_functional_rejects_scene_and_rule_fragments(bad_name):
    from narrativeloom.domain.character_names import complete_sculptor_section, is_false_person_name

    assert is_false_person_name(bad_name, context=bad_name)
    seed = "达芬奇·狗剩在猪圈墙上画《最后的晚餐》，模特是十二头猪"
    plot = "- 露辛达从蘑菇中现身警告狗剩；张晓红在监控中记录实验数据"
    out = complete_sculptor_section(
        f"- {bad_name}：本节主要人物，身处2147年火星殖民地生物实验舱",
        plot_sources=[plot],
        locked_names=["达芬奇·狗剩"],
        target=2,
        seed=seed,
        functional_mode=True,
    )
    assert bad_name not in out
    assert "达芬奇·狗剩" in out


def test_functional_fills_plot_character_missing_from_sculptor():
    from narrativeloom.service.llm_client import _coerce_unified_plan_variants

    seed = "达芬奇·狗剩在猪圈墙上画《最后的晚餐》，模特是十二头猪"
    raw = """【设定构建师】
- 地点：2147年火星殖民地生物实验舱
【人物塑造师】
- 达芬奇·狗剩：外星生物学家
- 控中：本节主要人物，身处实验舱
【剧情逻辑师】
- 张晓红在监控中质疑狗剩的脑波同步实验
- 陈星通试图中止违规操作
【冲突设计师】
- 核心矛盾：科研伦理与艺术执念"""
    out = _coerce_unified_plan_variants(
        [{"outline": raw}],
        plan_count=1,
        feedback_process=False,
        locked_character_names=["达芬奇·狗剩"],
        character_target_total=2,
        role_names=["设定构建师", "人物塑造师", "剧情逻辑师", "冲突设计师"],
        seed=seed,
    )[0]["outline"]
    names = _sculptor_names(out)
    assert len(names) == 2
    assert "达芬奇·狗剩" in names
    assert "控中" not in names
    assert "张晓红" in names or "陈星通" in names


def test_parse_preset_protagonist_names():
    from narrativeloom.domain.character_names import parse_preset_protagonist_names

    assert parse_preset_protagonist_names("达芬奇·狗剩、翠花、韩星") == [
        "达芬奇·狗剩",
        "翠花",
        "韩星",
    ]
    assert parse_preset_protagonist_names("飘着麦秸") == []


def test_sanitize_preserves_wizard_preset_protagonist():
    from narrativeloom.utils.display_utils import sanitize_typified_characters

    out = sanitize_typified_characters(
        "- 阿依古丽·买买提：油城女儿\n- 艾力·哈森：工程师",
        target=2,
        locked_names=["达芬奇"],
        seed="我的导师来自新疆克拉玛依",
        max_characters=8,
    )
    assert "达芬奇" in out


def test_functional_preserves_wizard_preset_protagonist():
    from narrativeloom.utils.display_utils import normalize_single_unified_outline

    seed = "我的导师来自新疆克拉玛依"
    locked = ["达芬奇"]
    raw = """【设定构建师】
- 地点：克拉玛依老炼油厂
- 时间：1980年代末
【人物塑造师】
- 阿依古丽·买买提：油城女儿
- 艾力·哈森：工程师
【剧情逻辑师】
- 阿依古丽在车间整理设备，艾力前来协助
【冲突设计师】
- 核心矛盾：理想与现实"""
    out = normalize_single_unified_outline(
        raw,
        role_names=["设定构建师", "人物塑造师", "剧情逻辑师", "冲突设计师"],
        locked_names=locked,
        character_target_total=2,
        seed=seed,
        prior_character_profiles={"达芬奇": "向导既定主角"},
    )
    names = _sculptor_names(out)
    assert len(names) == 2
    assert "达芬奇" in names
    assert "向导既定主角" not in out
    assert "控中" not in out
    assert "任何以" not in out
    da_vinci_desc = out.split("- 达芬奇：", 1)[-1].split("\n", 1)[0]
    assert len(da_vinci_desc.strip()) >= 8
    assert "向导既定主角" not in da_vinci_desc


def test_functional_locked_names_get_setting_aware_bios():
    from narrativeloom.utils.display_utils import normalize_single_unified_outline

    seed = "我的导师来自新疆克拉玛依"
    locked = ["达芬奇", "热依扎"]
    raw = """【设定构建师】
- 地点：2147年中国空间站天穹号近地轨道
- 时间：2147年
- 场景：零重力生物实验舱
【人物塑造师】
- 达芬奇：向导既定主角
- 热依扎：向导既定主角
【剧情逻辑师】
- 达芬奇在实验舱发现导航数据干扰
- 热依扎与达芬奇在实验室相遇
【冲突设计师】
- 核心矛盾：科研伦理与艺术执念"""
    out = normalize_single_unified_outline(
        raw,
        role_names=["设定构建师", "人物塑造师", "剧情逻辑师", "冲突设计师"],
        locked_names=locked,
        character_target_total=2,
        seed=seed,
        prior_character_profiles={"达芬奇": "向导既定主角", "热依扎": "向导既定主角"},
    )
    assert "向导既定主角" not in out
    assert "达芬奇" in out and "热依扎" in out
    sculptor = out.split("【人物塑造师】")[-1].split("【")[0]
    assert "2147" in sculptor or "空间站" in sculptor or "实验" in sculptor


def test_functional_sculptor_exact_count_with_locked():
    from narrativeloom.domain.character_names import complete_sculptor_section

    seed = "达芬奇·狗剩在猪圈墙上画《最后的晚餐》"
    plot = "- 朱塞佩看见狗剩在猪圈画壁画，老周在一旁看守"
    out = complete_sculptor_section(
        "- 交换：无效\n- 老僧的警：无效",
        plot_sources=[plot],
        locked_names=["达芬奇·狗剩", "达芬奇"],
        target=3,
        seed=seed,
    )
    names = _sculptor_names("【人物塑造师】\n" + out)
    assert len(names) == 3
    assert "达芬奇·狗剩" in names or "达芬奇" in names


def test_rejects_object_like_person_names():
    from narrativeloom.domain.character_names import is_false_person_name

    assert is_false_person_name("腰挂水囊")
    assert is_false_person_name("绳索")
    assert is_false_person_name("水囊")
    assert not is_false_person_name("阿依古丽")


def test_sanitize_typified_rejects_object_fragment_names():
    from narrativeloom.utils.display_utils import sanitize_typified_characters

    raw = (
        "- 达芬奇·狗剩：地质学研究生\n"
        "- 佩奇：退休向导\n"
        "- 阿依古丽：巡逻队员\n"
        "- 腰挂水囊：熟悉当地秘密的向导\n"
        "- 绳索：熟悉当地秘密的油田后裔"
    )
    out = sanitize_typified_characters(
        raw,
        target=5,
        locked_names=["达芬奇·狗剩", "佩奇", "阿依古丽"],
        seed="达芬奇·狗剩与佩奇在克拉玛依",
        setting="克拉玛依魔鬼城",
        key_events="阿依古丽带领众人穿越风蚀地貌",
    )
    names = _sculptor_names("【人物塑造师】\n" + out)
    assert "腰挂水囊" not in names
    assert "绳索" not in names
    assert "达芬奇·狗剩" in names
    assert "佩奇" in names
    assert "阿依古丽" in names


def test_sanitize_typified_respects_lower_target_on_renorm():
    from narrativeloom.utils.display_utils import sanitize_typified_characters

    raw = (
        "- 达芬奇·狗剩：地质学研究生\n"
        "- 佩奇：退休向导\n"
        "- 阿依古丽：巡逻队员\n"
        "- 老周：油田后裔"
    )
    locked = ["达芬奇·狗剩", "佩奇", "阿依古丽"]
    out3 = sanitize_typified_characters(
        raw,
        target=3,
        locked_names=locked,
        seed="达芬奇·狗剩与佩奇、阿依古丽、老周在克拉玛依",
        key_events="老周带领众人穿越魔鬼城",
    )
    out5 = sanitize_typified_characters(
        raw,
        target=5,
        locked_names=locked,
        seed="达芬奇·狗剩与佩奇、阿依古丽、老周在克拉玛依",
        key_events="老周带领众人穿越魔鬼城",
    )
    names3 = _sculptor_names("【人物塑造师】\n" + out3)
    names5 = _sculptor_names("【人物塑造师】\n" + out5)
    assert len(names3) == 3
    assert len(names5) == 5
    assert set(names3).issubset(set(names5))


def test_sanitize_typified_trims_excess_to_target():
    from narrativeloom.utils.display_utils import sanitize_typified_characters

    raw = (
        "- 达芬奇·狗剩：地质学研究生\n"
        "- 佩奇：退休向导\n"
        "- 阿依古丽：巡逻队员\n"
        "- 老周：油田后裔\n"
        "- 老马：本地向导"
    )
    locked = ["达芬奇·狗剩", "佩奇", "阿依古丽"]
    seed = "达芬奇·狗剩、佩奇、阿依古丽、老周、老马在克拉玛依"
    plot = "老周与老马带领众人穿越魔鬼城"
    out = sanitize_typified_characters(
        raw,
        target=3,
        locked_names=locked,
        seed=seed,
        key_events=plot,
    )
    assert len(_sculptor_names("【人物塑造师】\n" + out)) == 3


def test_filter_valid_cast_names_preserves_preset():
    from narrativeloom.domain.character_names import filter_valid_cast_names

    names = filter_valid_cast_names(
        ["达芬奇·狗剩", "腰挂水囊", "绳索", "佩奇"],
        preserve=["达芬奇·狗剩", "佩奇"],
    )
    assert "达芬奇·狗剩" in names
    assert "佩奇" in names
    assert "腰挂水囊" not in names
    assert "绳索" not in names


def test_parse_preset_protagonist_names_english():
    from narrativeloom.domain.character_names import parse_preset_protagonist_names

    assert parse_preset_protagonist_names("Peppa, Kaelen, Zura") == ["Peppa", "Kaelen", "Zura"]
    assert parse_preset_protagonist_names("Da Vinci, Peppa") == ["Da Vinci", "Peppa"]


def test_get_consent_bundle_english():
    from narrativeloom.config.consent_content import get_consent_bundle

    meta, sections, statements = get_consent_bundle("en")
    assert "Informed Consent" in meta["title"]
    assert sections[0]["title"].startswith("1.")
    assert len(statements) >= 5
    assert all("I " in s or "I'" in s for s in statements)


def test_split_character_entries_keeps_more_than_five():
    from narrativeloom.utils.display_utils import _split_character_entries

    raw = "\n".join(f"- Name{i}: role {i}" for i in range(6))
    assert len(_split_character_entries(raw)) == 6


def test_sanitize_typified_keeps_all_locked_english():
    from narrativeloom.utils.display_utils import sanitize_typified_characters

    locked = ["Peppa", "Kaelen", "Zura"]
    raw = "- Peppa: wizard-pig assistant\n- Maiale: boar guardian"
    plot = (
        "- Kaelen plants seeds in the orbital farm\n"
        "- Peppa uses her neural implant\n"
        "- Zura threatens to terminate funding"
    )
    out = sanitize_typified_characters(
        raw,
        target=3,
        locked_names=locked,
        seed="Peppa and Kaelen on an orbital agri-station",
        key_events=plot,
    )
    names = _sculptor_names("【人物塑造师】\n" + out)
    assert "Peppa" in names
    assert "Kaelen" in names
    assert "Zura" in names
    assert len(names) == 3


def test_extract_english_names_from_narrative():
    from narrativeloom.utils.display_utils import extract_english_names_from_narrative

    plot = "Kaelen plants seeds. Peppa uses her implant. Zura threatens funding."
    names = extract_english_names_from_narrative(plot, limit=5)
    assert "Kaelen" in names
    assert "Peppa" in names
    assert "Zura" in names


def test_normalize_typified_key_events_english_allows_longer_lines():
    from narrativeloom.utils.display_utils import normalize_typified_key_events

    long_line = (
        "- Da Vinci hurls a bucket of limewash at the attackers while Peppa bolts through the mud-slicked pigsty"
    )
    out = normalize_typified_key_events(long_line, min_lines=1, max_lines=3, lang="en")
    line = out.lstrip("-·• ").strip()
    assert len(line) > 50
    assert not line.endswith("bur")
    assert "limewash" in line or "attackers" in line


def test_normalize_char_entry_repairs_possessive_split():
    from narrativeloom.utils.display_utils import _normalize_char_entry

    fixed = _normalize_char_entry("Knight: 's curse on the fresco")
    assert fixed.startswith("Knight's")
    assert "curse" in fixed


def test_canonicalize_to_locked_name():
    from narrativeloom.domain.character_names import canonicalize_to_locked_name

    assert canonicalize_to_locked_name("Vinci", ["Da Vinci", "Peppa"]) == "Da Vinci"
    assert canonicalize_to_locked_name("Peppa", ["Da Vinci", "Peppa"]) == "Peppa"


def test_condense_role_body_english_preserves_full_lines():
    from narrativeloom.utils.display_utils import condense_role_body

    long_line = (
        "- Location: A sterile biolab on a space station orbiting Earth in the year 2147"
    )
    out = condense_role_body(long_line, max_lines=3, max_chars=80, lang="en")
    assert "space station" in out
    assert not out.rstrip().endswith("statio")


def test_normalize_unified_en_setting_not_midword_cut():
    from narrativeloom.utils.display_utils import normalize_single_unified_outline

    outline = (
        "【Setting Architect】\n"
        "- Location: A sterile biolab on a space station orbiting Earth\n"
        "- Time: Late afternoon during a solar flare alert\n"
        "【Character Sculptor】\n"
        "- Leonardo da Vinci: painter stranded aboard the station\n"
        "- Peppa: curious pig mascot in a biolab suit\n"
        "【Plot Logic Designer】\n"
        "- Because Leonardo's art requires authentic fear, he tests pigments on Peppa\n"
        "【Conflict Designer】\n"
        "- Core conflict: Control over biology versus machine logic\n"
    )
    out = normalize_single_unified_outline(
        outline,
        role_names=[
            "Setting Architect",
            "Character Sculptor",
            "Plot Logic Designer",
            "Conflict Designer",
        ],
        lang="en",
        seed="Leonardo and Peppa on a space station",
        locked_names=["Leonardo da Vinci", "Peppa"],
    )
    assert "space station" in out
    assert "machine logic" in out
    assert "statio\n" not in out and not out.endswith("statio")


def test_localize_scrubs_zh_conflict_and_character_placeholders():
    from narrativeloom.utils.display_utils import localize_functional_outline

    raw = (
        "- 核心矛盾：与本节剧情目标相对立\n"
        "- 戏剧冲突：—\n"
        "- Peppa: 本节主要人物，行动推动当前情节"
    )
    out = localize_functional_outline(raw, lang="en")
    assert "核心矛盾" not in out
    assert "本节主要人物" not in out
    assert "Core conflict:" in out
    assert "main character who drives this beat's plot" in out


def test_localize_functional_outline_maps_zh_labels_to_en():
    from narrativeloom.utils.display_utils import localize_functional_outline

    raw = "- 地点：Milan pigsty\n- 核心冲突：art vs survival\n- 戏剧高潮：—"
    out = localize_functional_outline(raw, lang="en")
    assert "Location:" in out
    assert "Core conflict:" in out
    assert "Dramatic climax:" in out
    assert "地点" not in out
    assert "核心冲突" not in out


def test_functional_en_outline_normalization_uses_english_fallbacks():
    from narrativeloom.utils.display_utils import normalize_single_unified_outline

    role_names = [
        "Setting Architect",
        "Character Sculptor",
        "Plot Logic Designer",
        "Conflict Designer",
    ]
    outline = (
        "【Setting Architect】\n—\n"
        "【Character Sculptor】\n"
        "- Leonardo da Vinci: painted The Last Supper on a pigsty wall\n"
        "- Peppa: 本节主要人物，行动推动当前情节\n"
        "【Plot Logic Designer】\n—\n"
        "【Conflict Designer】\n"
    )
    out = normalize_single_unified_outline(
        outline,
        role_names=role_names,
        lang="en",
        seed="Leonardo da Vinci paints with Peppa in a Milan pigsty",
        locked_names=["Leonardo da Vinci", "Peppa"],
    )
    assert "本节主要人物" not in out
    assert "核心矛盾" not in out
    assert "Core conflict" in out
    assert "Peppa" in out


def test_sanitize_typified_rejects_street_corner_false_name():
    from narrativeloom.domain.character_names import is_false_person_name
    from narrativeloom.utils.display_utils import sanitize_typified_characters

    setting = "乾隆二十八年盛夏，北京正阳门外大栅栏一带，街口石板滚烫，蝉鸣聒噪"
    assert is_false_person_name("街口却", context=setting)
    raw = (
        "- 张问樵：翰林院编修，查粮价\n"
        "- 赵铁柱：粮铺掌柜，担心被抢\n"
        f"- 街口却：{setting}茶棚布帘"
    )
    key_events = (
        "- 张问樵见粮铺挂缺货牌，骡车却往巷里运粮\n"
        "- 赵铁柱说内府太监逼商抬价\n"
        "- 慧明和尚悄悄塞给张问樵一张密笺"
    )
    out = sanitize_typified_characters(
        raw,
        target=3,
        seed="查粮价",
        setting=setting,
        key_events=key_events,
        require_narrative_grounding=False,
    )
    names = _sculptor_names("【人物塑造师】\n" + out)
    assert "街口却" not in names
    assert "慧明" in names
    assert len(names) == 3


def test_sanitize_typified_syncs_event_only_character():
    from narrativeloom.utils.display_utils import sanitize_typified_characters

    setting = "2005年北京胡同夏日午后"
    raw = "- 老张：退休木匠\n- 刘婶：邻居"
    key_events = (
        "- 老张发现冰窖门缝冒冷气\n"
        "- 小梅带来一张旧地契，说冰窖是她家祖产\n"
        "- 三人决定夜里下去探看"
    )
    out = sanitize_typified_characters(
        raw,
        target=3,
        setting=setting,
        key_events=key_events,
        require_narrative_grounding=False,
    )
    names = _sculptor_names("【人物塑造师】\n" + out)
    assert "小梅" in names
    assert len(names) == 3


def test_functional_outline_condenses_long_zh_bullets():
    from narrativeloom.utils.display_utils import normalize_single_unified_outline

    role_names = ["设定构建师", "人物塑造师", "剧情逻辑师", "冲突设计师"]
    long_plot = "- " + "甲" * 60
    outline = (
        "【设定构建师】\n"
        "- 地点：北京胡同\n"
        "- 时间：2005年夏\n"
        "- 场景：冰窖\n"
        "- 规则：邻里互助\n"
        "【人物塑造师】\n"
        "- 老张：退休木匠，担心冰窖出事\n"
        "【剧情逻辑师】\n"
        f"{long_plot}\n"
        f"{long_plot}\n"
        f"{long_plot}\n"
        f"{long_plot}\n"
        f"{long_plot}\n"
        "【冲突设计师】\n"
        f"{long_plot}\n"
        f"{long_plot}\n"
    )
    out = normalize_single_unified_outline(outline, role_names=role_names, lang="zh")
    assert "…" not in out and "..." not in out
    plot_block = out.split("【冲突设计师】", 1)[0].split("【剧情逻辑师】", 1)[1]
    plot_lines = [ln for ln in plot_block.splitlines() if ln.strip().startswith("-")]
    assert len(plot_lines) <= 3


def test_fit_complete_bullet_zh_keeps_label_clause():
    from narrativeloom.utils.display_utils import _fit_complete_bullet

    raw = "地点：1421年仲夏午后的紫禁城内阁，檐角铜铃轻响，壁上渗出水珠"
    fitted = _fit_complete_bullet(raw, 48, lang="zh")
    assert fitted.startswith("地点：")
    assert "…" not in fitted
    assert len(fitted) <= 48


def test_functional_outline_no_ellipsis_on_long_sentences():
    from narrativeloom.utils.display_utils import normalize_single_unified_outline

    role_names = ["设定构建师", "人物塑造师", "剧情逻辑师", "冲突设计师"]
    outline = (
        "【设定构建师】\n"
        "- 地点：1421年仲夏午后的紫禁城内阁，檐角铜铃轻响，壁上渗出水珠\n"
        "- 时间：1421年仲夏午后\n"
        "【人物塑造师】\n"
        "- 朱棣：刚登基的永乐帝，疑心未消\n"
        "- 李乐：御前小太监，善于察言观色\n"
        "【剧情逻辑师】\n"
        "- 朱棣命太医为徐皇后试方，却见药渣中混有异域香料\n"
        "- 李乐暗中记下太医与外国使节的接触\n"
        "- 徐皇后咳疾加重，内廷暗流涌动\n"
        "【冲突设计师】\n"
        "- 核心矛盾：帝后情深与宫廷阴谋\n"
        "- 戏剧冲突：太医被诬与外邦勾结\n"
    )
    out = normalize_single_unified_outline(outline, role_names=role_names, lang="zh")
    assert "…" not in out
    assert "朱棣命太医" in out or "太医" in out


def test_prose_length_budget_scales_by_section():
    from narrativeloom.service.llm_client import (
        PROSE_CHARS_PER_SECTION_MAX,
        PROSE_CHARS_PER_SECTION_MIN,
        _prose_length_budget,
    )

    lo, hi = _prose_length_budget(4)
    assert lo == 4 * PROSE_CHARS_PER_SECTION_MIN
    assert hi == 4 * PROSE_CHARS_PER_SECTION_MAX
    assert PROSE_CHARS_PER_SECTION_MIN >= 1000
    assert PROSE_CHARS_PER_SECTION_MAX > PROSE_CHARS_PER_SECTION_MIN

