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
    assert "承接前文" not in out
    assert "本节须保留" not in out
    assert "达芬奇·狗剩" in out
    assert "画师" in out or "猪圈" in out or "作画" in out


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
    out = normalize_typified_key_events(events, min_lines=3, max_lines=5)
    lines = [ln.lstrip("-·• ").strip() for ln in out.splitlines() if ln.strip()]
    assert 3 <= len(lines) <= 5
    assert all(30 <= len(ln) <= 50 for ln in lines)
    assert sum(len(ln) for ln in lines) <= 300


def test_structured_cast_split_on_ampersand():
    from narrativeloom.domain.global_character_list import names_from_structured_characters_field

    raw = "韩星：记者 & 艾买提：师傅 & 交换：无效"
    names = names_from_structured_characters_field(raw)
    assert "韩星" in names
    assert "艾买提" in names
    assert "交换" not in names


def test_extract_character_names_from_text_ignores_prose_ner():
    from narrativeloom.utils.display_utils import extract_character_names_from_text

    prose = "交换发生在集市，老僧的警言回荡，星假装没听见韩星的呼唤。"
    assert extract_character_names_from_text(prose) == []


def test_sanitize_typified_uses_global_cast_not_prose_garbage():
    from narrativeloom.utils.display_utils import sanitize_typified_characters

    raw = "- 交换：市场从业者\n- 老僧的警：警告者\n- 星假装没：关键剧情人物"
    out = sanitize_typified_characters(
        raw,
        target=2,
        locked_names=["韩星"],
        seed="韩星在集市采访",
        global_cast_names=["韩星", "艾买提"],
    )
    assert "交换" not in out
    assert "老僧的警" not in out
    assert "星假装没" not in out
    assert "韩星" in out


def test_functional_coerce_respects_global_cast():
    from narrativeloom.service.llm_client import _coerce_unified_plan_variants

    seed = "韩星在克拉玛依采访。"
    raw = """【设定构建师】
- 地点：克拉玛依
- 时间：2024年秋
【人物塑造师】
- 交换：市场从业者
- 星假装没：关键剧情人物
【剧情逻辑师】
- 韩星假借采访接近艾买提
【冲突设计师】
- 核心矛盾：信任与隐瞒"""
    out = _coerce_unified_plan_variants(
        [{"outline": raw}],
        plan_count=1,
        feedback_process=False,
        locked_character_names=["韩星"],
        character_target_total=2,
        role_names=["设定构建师", "人物塑造师", "剧情逻辑师", "冲突设计师"],
        seed=seed,
        global_cast_names=["韩星", "艾买提"],
    )[0]["outline"]
    names = _sculptor_names(out)
    assert "韩星" in names
    assert "艾买提" in names
    assert "交换" not in names
    assert "星假装没" not in names
    assert "关键剧情人物" not in out


def test_is_false_person_name_rejects_phrase_fragments():
    from narrativeloom.domain.character_names import is_false_person_name

    for bad in ("透露任何", "过来", "数据时", "任何"):
        assert is_false_person_name(bad, context="不得透露任何信息")


def test_sanitize_typified_enforces_exact_target_count():
    from narrativeloom.utils.display_utils import sanitize_typified_characters

    raw = (
        "- 陈默：导师，地质学家\n"
        "- 林星：研究生助手\n"
        "- 奇拉：沙虫信使"
    )
    plot = "阿依夏在监控室呼叫赵工，陈默与林星赶到深井"
    out = sanitize_typified_characters(
        raw,
        target=4,
        locked_names=[],
        seed="克拉玛依深井",
        setting="公元2147年克拉玛依地下城",
        key_events=plot,
        global_cast_names=["陈默", "林星", "阿依夏", "赵工"],
    )
    names = _sculptor_names("【人物塑造师】\n" + out)
    assert len(names) == 4
    assert "透露任何" not in names
    assert "过来" not in names


def test_functional_syncs_plot_cast_and_rejects_phrase_names():
    from narrativeloom.service.llm_client import _coerce_unified_plan_variants

    seed = "艾克拜尔在克拉玛依地质勘探队实习。"
    raw = """【设定构建师】
- 地点：克拉玛依郊外深地实验室
- 时间：2189年下午
【人物塑造师】
- 陈洛：初级数据分析员
- 透露任何：本节主要人物，行动推动当前情节
- 数据时：青年研究员
【剧情逻辑师】
- 陈洛发现次声波记录中的节律脉冲
- 阿依夏姆把陈洛叫到办公室，讨论硅基生命体
【冲突设计师】
- 核心冲突：科学好奇与安全审查
- 戏剧冲突：阿依夏姆赌上学术声誉"""
    out = _coerce_unified_plan_variants(
        [{"outline": raw}],
        plan_count=1,
        feedback_process=False,
        locked_character_names=["艾克拜尔"],
        character_target_total=3,
        role_names=["设定构建师", "人物塑造师", "剧情逻辑师", "冲突设计师"],
        seed=seed,
    )[0]["outline"]
    names = _sculptor_names(out)
    assert len(names) == 3
    assert "陈洛" in names
    assert "阿依夏姆" in names
    assert "透露任何" not in names
    assert "数据时" not in names
    assert "过来" not in names


def test_functional_preserves_full_name_under_condense():
    from narrativeloom.utils.display_utils import condense_role_body

    body = "- 方岩坦：四十五岁副教授，韩星的研究导师"
    out = condense_role_body(body, max_lines=2, max_chars=44)
    assert "方岩坦" in out
    assert out.startswith("- 方岩坦")
