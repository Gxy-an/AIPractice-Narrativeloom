# -*- coding: utf-8 -*-
"""人格池：类型化（题材）与功能化（创作任务）；小节标签（支持 2～10 节）。"""

from __future__ import annotations

from typing import Dict, List, Tuple

# 六节模板（用于扩展更多节时的相位提示）
_BEAT_HINTS_ZH = [
    ("开端·引入", "开端·铺垫", "发展·推进", "发展·转折", "高潮·对峙", "高潮·收束"),
]
_BEAT_HINTS_EN = [
    ("Opening · hook", "Opening · setup", "Rising · push", "Rising · turn", "Climax · confrontation", "Climax · resolution"),
]


def make_beat_labels(n: int, lang: str) -> List[Tuple[str, str]]:
    """生成 n 个小节标题与相位提示（2≤n≤10）。"""
    n = max(2, min(10, int(n)))
    zh = (lang or "zh") == "zh"
    hints = _BEAT_HINTS_ZH[0] if zh else _BEAT_HINTS_EN[0]
    out: List[Tuple[str, str]] = []
    for i in range(n):
        title = f"小节{i + 1}" if zh else f"Section {i + 1}"
        if n <= len(hints):
            hint = hints[i]
        else:
            slot = int(round(i * (len(hints) - 1) / max(1, n - 1)))
            hint = hints[min(max(0, slot), len(hints) - 1)]
        out.append((title, hint))
    return out


def beat_labels(lang: str) -> list:
    """兼容旧接口：默认 6 节。"""
    return make_beat_labels(6, lang)


BEAT_LABELS_ZH = make_beat_labels(6, "zh")
BEAT_LABELS_EN = make_beat_labels(6, "en")

# 类型化人格（中 / 英）
TYPIFIED_PERSONAS_ZH: List[Tuple[str, str]] = [
    (
        "奇幻世界构建者",
        "这位助理专门打造丰富而富于想象力的幻想世界，包含精细的魔法系统、神话生物和多样化的文化。",
    ),
    ("科幻未来学家", "这位助理专注于创造可信且创新的科幻背景。"),
    (
        "谜题解决者",
        "这位助理协助开发复杂且引人入胜的谜题，帮助设置线索、误导和情节转折，保持读者对结局的猜测直到最后一刻。",
    ),
    (
        "浪漫牵线人",
        "这位助理擅长创造引人入胜的浪漫故事情节，确保角色间的化学反应感觉真实，以及关系自然随时间发展。",
    ),
    (
        "历史研究员",
        "这位助理擅长将准确的历史细节和背景融入叙述中，或加入权谋斗争内容，使历史小说故事栩栩如生，让读者沉浸在特定的时期。",
    ),
    (
        "恐怖氛围创造者",
        "这位助理帮助在恐怖故事中建立紧张感和悬念，使用描述性语言和节奏营造不安的氛围，让读者保持紧张。",
    ),
    (
        "冒险向导",
        "这位助理专注于编写激动人心的冒险故事，设计激动人心的动作序列、危险的障碍和高风险的挑战，以供角色克服。",
    ),
    (
        "喜剧幽默家",
        "这位助理专注于将幽默和机智融入故事中，使用文字游戏、情境喜剧和角色互动，使读者发笑。",
    ),
    (
        "反乌托邦幻想家",
        "这位助理擅长构建反乌托邦设置，并探讨由此产生的社会和政治问题，帮助创造引人思考和警示性的故事。",
    ),
    (
        "魔幻现实主义爱好者",
        "这位助理协助将奇幻元素与日常现实相融合，创造既扎实又异想天开的故事，通常在其他普通场景中呈现魔幻事件。",
    ),
]

TYPIFIED_PERSONAS_EN: List[Tuple[str, str]] = [
    (
        "Fantasy World Builder",
        "Builds rich imaginative fantasy worlds with magic systems, mythical creatures, and diverse cultures.",
    ),
    (
        "Sci-Fi Futurist",
        "Creates believable, innovative science-fiction settings and futures.",
    ),
    (
        "Puzzle Solver",
        "Designs intricate mysteries with clues, red herrings, and twists that keep readers guessing.",
    ),
    (
        "Romance Matchmaker",
        "Crafts compelling romance with authentic chemistry and evolving relationships.",
    ),
    (
        "Historical Researcher",
        "Weaves accurate historical detail and intrigue into period fiction.",
    ),
    (
        "Horror Atmosphere Creator",
        "Builds dread and suspense through pacing, sensory detail, and unease.",
    ),
    (
        "Adventure Guide",
        "Writes high-stakes adventure with action, obstacles, and daring challenges.",
    ),
    (
        "Comedy Humorist",
        "Infuses wit, wordplay, situational comedy, and lively character banter.",
    ),
    (
        "Dystopian Visionary",
        "Constructs dystopian worlds and explores their social and political stakes.",
    ),
    (
        "Magical Realism Enthusiast",
        "Blends the fantastical with everyday reality in grounded, whimsical ways.",
    ),
]

# 反套路创意师：仅用于拼合后的「一键升级」，不参与并行片段生成
ANTI_CLICHE_ROLE_ZH = "反套路创意师"
ANTI_CLICHE_ROLE_EN = "Anti-Cliché Innovator"
ANTI_CLICHE_TASK_ZH = (
    "这位助理专职打破常规俗套叙事，拒绝模板化情节、脸谱化角色、直白式因果、套路化冲突；"
    "擅长在保留叙事逻辑与连贯性的前提下，制造意料之外的创意突变、反转设定、反差桥段与隐藏伏笔，"
    "让故事全程跳出预期、告别陈词滥调，始终保持新鲜的创意质感。"
    "如果当前是反套路创意师，请对内容进行创意突变，绝对避免俗套。"
)
ANTI_CLICHE_TASK_EN = (
    "Breaks trope-heavy plotting while preserving logic and continuity; "
    "delivers surprising turns, contrast beats, and hidden setups. "
    "When acting as this role, mutate the material creatively and avoid clichés absolutely."
)

CHARACTER_SCULPTOR_ZH = "人物塑造师"
CHARACTER_SCULPTOR_EN = "Character Sculptor"
SETTING_ARCHITECT_ZH = "设定构建师"
SETTING_ARCHITECT_EN = "Setting Architect"
CONTINUITY_CHECKER_ZH = "连贯性校验师"
CONTINUITY_CHECKER_EN = "Continuity Checker"

# 功能化人格（中 / 英）— 并行片段生成（8 职能）
FUNCTIONAL_PARALLEL_ZH: List[Tuple[str, str]] = [
    (
        "设定构建师",
        "这位助理专注设计故事的时空背景、物理场景与世界运行规则，精准构建具体地点、时间、环境特征与世界观设定，让故事场景立体饱满，杜绝场景单薄空洞，为叙事提供扎实的空间与规则基底。",
    ),
    (
        CHARACTER_SCULPTOR_ZH,
        "这位助理专注刻画角色的性格特质、核心动机、人物关系与行为逻辑；"
        "输出必须写出具体人物姓名（至少两名），格式为「姓名：身份、性格、与他人关系及本章行动驱动」的自然叙述；"
        "禁止使用「动机是」「关系是」「本节状态」等标签式用语，禁止单独写本节状态句；"
        "禁止无姓名的泛称堆砌；禁止写入世界规则、物理提醒、空间拓展、承接前文、核查等非人物条目。",
    ),
    (
        "剧情逻辑师",
        "这位助理专注梳理故事事件的因果链条、情节推进逻辑与叙事节奏，设计合理的事件顺序与发展脉络，规避剧情漏洞与逻辑断层，让情节推进自然顺滑、环环相扣。",
    ),
    (
        "氛围渲染师",
        "这位助理专注营造故事的情绪基调、感官体验与氛围感，通过环境、光影、音效、情绪描写传递叙事氛围，让故事具备强烈的代入感，告别干瘪平淡的叙事表达。",
    ),
    (
        "对话设计师",
        "这位助理专注设计贴合角色性格的台词、语气与互动方式，让角色对话自然生动、符合人物身份，推动情节发展、展现人物关系，杜绝生硬刻板的对话表达。",
    ),
    (
        "细节填充师",
        "这位助理专注补充故事的道具、伏笔、细节描写与小彩蛋，丰富叙事层次，埋下前后呼应的线索，让故事细节饱满、质感细腻，解决叙事粗糙无细节的问题。",
    ),
    (
        "冲突设计师",
        "这位助理专注设计故事的核心矛盾与戏剧冲突、悬念升级，制造情节起伏与高潮节点，让故事充满张力，解决剧情平淡无起伏的问题，推动叙事走向高潮。",
    ),
    (
        "连贯性校验师",
        "这位助理专注核查故事前后的逻辑一致性、人物状态连贯性与事件合理性，对标历史剧情修正矛盾点，确保新节拍与前文设定无缝衔接，维护叙事整体逻辑闭环。",
    ),
]

FUNCTIONAL_PARALLEL_EN: List[Tuple[str, str]] = [
    (
        "Setting Architect",
        "Designs time, place, spatial layout, and world rules so scenes feel concrete and grounded.",
    ),
    (
        CHARACTER_SCULPTOR_EN,
        "Shapes character motives and relationships; every fragment must name at least two characters "
        "(Name: role/motive), never only pronouns or generic labels.",
    ),
    (
        "Plot Logic Designer",
        "Maps causal chains, beat order, and pacing without plot holes.",
    ),
    (
        "Atmosphere Renderer",
        "Delivers mood, sensory texture, and emotional tone for immersion.",
    ),
    (
        "Dialogue Designer",
        "Writes lines and interactions that fit character identity and advance the beat.",
    ),
    (
        "Detail Filler",
        "Adds props, foreshadowing, and tactile details that enrich the beat.",
    ),
    (
        "Conflict Designer",
        "Engineers core tensions, dramatic peaks, and suspense beats (no separate obstacle column).",
    ),
    (
        "Continuity Checker",
        "Audits consistency with prior beats and canon before the beat locks in.",
    ),
]

FUNCTIONAL_PERSONAS_ZH = FUNCTIONAL_PARALLEL_ZH + [(ANTI_CLICHE_ROLE_ZH, ANTI_CLICHE_TASK_ZH)]
FUNCTIONAL_PERSONAS_EN = FUNCTIONAL_PARALLEL_EN + [(ANTI_CLICHE_ROLE_EN, ANTI_CLICHE_TASK_EN)]

# 兼容旧导入名
TYPIFIED_PERSONAS = TYPIFIED_PERSONAS_ZH
FUNCTIONAL_SECTION_ROLES = FUNCTIONAL_PARALLEL_ZH
FUNCTIONAL_BACKGROUND_ROLES: List[Tuple[str, str]] = FUNCTIONAL_PARALLEL_ZH[:2]
FUNCTIONAL_PERSONAS = FUNCTIONAL_PERSONAS_ZH

_ROLE_ID_ZH = {name: i for i, (name, _) in enumerate(FUNCTIONAL_PERSONAS_ZH)}
_ROLE_ID_EN = {name: i for i, (name, _) in enumerate(FUNCTIONAL_PERSONAS_EN)}
_PARALLEL_ID_ZH = {name: i for i, (name, _) in enumerate(FUNCTIONAL_PARALLEL_ZH)}
_PARALLEL_ID_EN = {name: i for i, (name, _) in enumerate(FUNCTIONAL_PARALLEL_EN)}


def get_typified_personas(lang: str) -> List[Tuple[str, str]]:
    return TYPIFIED_PERSONAS_ZH if (lang or "zh") == "zh" else TYPIFIED_PERSONAS_EN


def get_functional_personas(lang: str) -> List[Tuple[str, str]]:
    return FUNCTIONAL_PERSONAS_ZH if (lang or "zh") == "zh" else FUNCTIONAL_PERSONAS_EN


def get_functional_parallel_personas(lang: str) -> List[Tuple[str, str]]:
    """参与并行片段生成的职能（不含反套路创意师）。"""
    return FUNCTIONAL_PARALLEL_ZH if (lang or "zh") == "zh" else FUNCTIONAL_PARALLEL_EN


def antitrope_role_name(lang: str) -> str:
    return ANTI_CLICHE_ROLE_ZH if (lang or "zh") == "zh" else ANTI_CLICHE_ROLE_EN


def antitrope_role_task(lang: str) -> str:
    return ANTI_CLICHE_TASK_ZH if (lang or "zh") == "zh" else ANTI_CLICHE_TASK_EN


def is_antitrope_role(name: str, lang: str) -> bool:
    return name == antitrope_role_name(lang)


def is_continuity_checker_role(name: str, lang: str) -> bool:
    zh = (lang or "zh") == "zh"
    return name == (CONTINUITY_CHECKER_ZH if zh else CONTINUITY_CHECKER_EN)


def is_unified_plan_excluded_role(name: str, lang: str) -> bool:
    """不参与「总体方案」拼合展示的职能（反套路、连贯性校验）。"""
    return is_antitrope_role(name, lang) or is_continuity_checker_role(name, lang)


def filter_unified_plan_role_names(names: List[str], lang: str) -> List[str]:
    return [n for n in names if n and not is_unified_plan_excluded_role(n, lang)]


def get_functional_unified_plan_personas(lang: str) -> List[Tuple[str, str]]:
    """参与总体方案统筹的职能（不含反套路、连贯性校验师）。"""
    return [
        (n, t)
        for n, t in get_functional_parallel_personas(lang)
        if not is_unified_plan_excluded_role(n, lang)
    ]


def is_character_sculptor_role(name: str, lang: str) -> bool:
    zh = (lang or "zh") == "zh"
    if zh:
        return name == CHARACTER_SCULPTOR_ZH
    return name == CHARACTER_SCULPTOR_EN


def is_setting_architect_role(name: str, lang: str) -> bool:
    zh = (lang or "zh") == "zh"
    if zh:
        return name == SETTING_ARCHITECT_ZH
    return name == SETTING_ARCHITECT_EN


def filter_parallel_role_names(names: List[str], lang: str) -> List[str]:
    allowed = {n for n, _ in get_functional_parallel_personas(lang)}
    return [n for n in names if n in allowed]


def filter_recommended_role_names(names: List[str], lang: str) -> List[str]:
    """推荐/勾选合法职能（含反套路创意师）。"""
    allowed = {n for n, _ in get_functional_personas(lang)}
    return [n for n in names if n in allowed]


def functional_role_order(lang: str) -> List[str]:
    return [n for n, _ in get_functional_parallel_personas(lang)]


def functional_recommendation_order(lang: str) -> List[str]:
    """界面排序：并行职能 + 反套路创意师（末位）。"""
    return functional_role_order(lang) + [antitrope_role_name(lang)]


def functional_task_by_name(name: str, lang: str) -> str:
    for n, t in get_functional_personas(lang):
        if n == name:
            return t
    return ""


def match_functional_role_across_langs(name: str, lang: str) -> str:
    """将任意语言下的职能名映射到当前界面语言。"""
    if is_antitrope_role(name, "zh") or is_antitrope_role(name, "en"):
        return antitrope_role_name(lang)
    if lang == "zh":
        if name in _PARALLEL_ID_ZH:
            return name
        idx = _PARALLEL_ID_EN.get(name)
        if idx is not None:
            return FUNCTIONAL_PARALLEL_ZH[idx][0]
    else:
        if name in _PARALLEL_ID_EN:
            return name
        idx = _PARALLEL_ID_ZH.get(name)
        if idx is not None:
            return FUNCTIONAL_PARALLEL_EN[idx][0]
    return name
